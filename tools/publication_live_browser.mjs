// Actual built React + real backend/index/provider, isolated test-chat database.
import { chromium } from '../frontend/node_modules/playwright/index.mjs';
import { spawn, execFileSync } from 'node:child_process';
import { mkdir, open, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
import path from 'node:path';
import { createHash } from 'node:crypto';
const root=fileURLToPath(new URL('../',import.meta.url));
const runName=process.argv[2]??'fresh-browser';
const freshVariant=process.argv.includes('--fresh-variant');
assert(/^[a-zA-Z0-9-]+$/.test(runName));
const folder=path.join(root,'reports','publication',runName);
await mkdir(folder,{recursive:true});
try {const old=await readFile(path.join(folder,'results.json'));await writeFile(path.join(folder,`results-${Date.now()}.json`),old)}catch{}
const database=path.join(folder,`chats-${Date.now()}.sqlite3`);
let seededRealAnswer=false;
try{
  const oldDatabase=path.join(root,'reports','publication','candidate4-http','workflow-chats.sqlite3');
  await readFile(oldDatabase);
  execFileSync(path.join(root,'.venv','Scripts','python.exe'),['-c',
    "import sqlite3,sys; a=sqlite3.connect(sys.argv[1]); b=sqlite3.connect(sys.argv[2]); a.backup(b); b.execute(\"UPDATE conversations SET title='Saved real source rendering' WHERE id IN (SELECT conversation_id FROM turns WHERE question LIKE 'What are the hostel room eligibility rules,%')\"); b.commit(); a.close(); b.close()",
    oldDatabase,database],{windowsHide:true});
  seededRealAnswer=true;
}catch{}
const log=await open(path.join(folder,'server.log'),'a');
const child=spawn(path.join(root,'.venv','Scripts','python.exe'),[
  path.join(root,'tools','publication_system_checks.py'),'--serve','--mode','live',
  '--db',database,'--port','8504'],
  {cwd:root,windowsHide:true,stdio:['ignore',log.fd,log.fd]});
const base='http://127.0.0.1:8504';
const report={started_utc:new Date().toISOString(),status:'RUNNING',checks:{},turns:[],errors:[],fresh_answer_accuracy:null};
report.question_set_note=freshVariant?'New Codex-authored numeric inputs for this verification run; not an independent human-authored holdout.':'Earlier smoke questions reused; not an unseen holdout.';
report.pipeline_revision=execFileSync(path.join(root,'.venv','Scripts','python.exe'),['-c','from compass.benchmark import revision; from compass.config import Settings; print(revision(Settings()))'],{cwd:root,windowsHide:true}).toString().trim();
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
const api=async url=>{const r=await page.request.get(base+url);assert(r.ok());return r.json()};
async function waitTurn(cid,index=0){
  const end=Date.now()+140000;
  while(Date.now()<end){
    const t=(await api(`/api/conversations/${cid}`)).turns[index];
    if(t&&t.status!=='pending')return t;
    await new Promise(r=>setTimeout(r,250));
  }
  throw new Error('Live turn timeout');
}
try{
  let ready=false;
  for(let i=0;i<100;i++){
    if(child.exitCode!==null)throw new Error('Isolated live server exited');
    try{await api('/api/health');ready=true;break}catch{}
    await new Promise(r=>setTimeout(r,150));
  }
  assert(ready);
  const before=JSON.parse(await readFile(path.join(root,'data','manifest.json'),'utf8')).fingerprint;
  await page.goto(base);
  const composer=page.getByRole('textbox',{name:'Message Student Compass'});
  await composer.waitFor();
  await page.waitForFunction(()=>!document.querySelector('textarea').disabled);
  assert(await page.locator('.exchange').count()===0);report.checks.opens_empty=true;
  const q=freshVariant?'If six credits are all lab work, how many practical hours per week follow from the handbook rule?':'For two lab credits, how many practical hours per week does the handbook imply?';
  const created=page.waitForResponse(r=>r.url()===base+'/api/conversations'&&r.request().method()==='POST');
  await composer.fill(q);await composer.press('Enter');
  await page.locator('.user-bubble').waitFor({timeout:1500});report.checks.immediate_question=true;
  const cid=(await(await created).json()).id;
  let first=await waitTurn(cid);report.turns.push(first);
  if(first.status==='failed'){
    assert.match(first.error,/quota/i);
    await page.getByRole('button',{name:'Retry answer'}).waitFor();
    report.checks.real_quota_error_is_recoverable=true;
    // The user requested no further API calls after a quota block.
    report.quota_note='Stopped without retry; user must update the local .env before continuation.';
    report.status='BLOCKED_BY_QUOTA';
  }else{
    assert.match(first.answer,freshVariant?/\b18\b|eighteen/i:/\b6\b|six/i);
    assert(first.citations.some(c=>c.references.some(r=>r.id==='academic'&&r.pdf_page===8)));
    await page.locator('.sources>summary').click();await page.locator('.source-card>summary').first().click();
    report.checks.fresh_source_display=true;
    const more=freshVariant?[
      ['And if those lab credits were reduced to three, what weekly practical hours would remain?',/\b9\b|nine/i],
      ['Switch to the library: three undergraduate books are each five days overdue. Calculate the combined fine from the table.',/\b150\b/]
    ]:[['Then what would one lab credit require per week?',/\b3\b|three/i],
       ['Now change topic: two undergraduate library books are each four days late. What is their combined fine?',/\b80\b/]];
    for(const [next,expected] of more){
      await page.waitForFunction(()=>!document.querySelector('textarea').disabled);
      await composer.fill(next);await composer.press('Enter');
      const turn=await waitTurn(cid,report.turns.length);report.turns.push(turn);
      assert(turn.status==='completed');assert.match(turn.answer,expected);assert(turn.citations.length);
    }
    report.checks.fresh_followup_and_topic_change=true;
    await page.waitForFunction(()=>!document.querySelector('textarea').disabled);
    await composer.fill('What questions have I asked in this chat?');await composer.press('Enter');
    const recall=await waitTurn(cid,report.turns.length);report.turns.push(recall);
    assert(recall.status==='completed'&&recall.answer.includes(q)&&recall.answer.includes(more[1][0]));
    assert(recall.diagnostics.api_calls===0);report.checks.fresh_local_recall=true;
    report.fresh_answer_accuracy=true;report.status='COMPLETED';
  }
  await page.request.patch(base+`/api/conversations/${cid}`,{data:{title:'Final fresh publication check'}});
  await page.reload();await page.waitForFunction(()=>!document.querySelector('textarea').disabled);
  assert(await page.locator('.exchange').count()===0);report.checks.reload_starts_empty=true;
  await page.getByRole('button',{name:'Final fresh publication check',exact:true}).click();
  await page.locator('.user-bubble').first().waitFor();
  assert((await page.locator('.user-bubble').first().innerText())===q);report.checks.failed_or_completed_chat_resumes=true;
  assert(before===JSON.parse(await readFile(path.join(root,'data','manifest.json'),'utf8')).fingerprint);
  report.checks.index_unchanged=true;
  if(seededRealAnswer){
    await page.getByRole('button',{name:'Saved real source rendering',exact:true}).click();
    const chats=await api('/api/conversations');const saved=chats.find(c=>c.title==='Saved real source rendering');
    const turn=(await api(`/api/conversations/${saved.id}`)).turns[0];
    await page.locator('.sources>summary').click();
    assert(await page.locator('.source-card').count()===turn.citations.length);
    for(let i=0;i<turn.citations.length;i++){
      const card=page.locator('.source-card').nth(i);await card.locator('summary').click();
      const content=await card.locator('.source-body pre').textContent();
      assert(content.replaceAll('\r\n','\n')===turn.citations[i].excerpt.replaceAll('\r\n','\n'));
      for(const ref of turn.citations[i].references){
        assert((await card.textContent()).includes(`PDF page ${ref.pdf_page} · Printed page ${ref.printed_label}`));
      }
    }
    await page.locator('.inline-citation').first().click();
    report.checks.actual_saved_gemini_sources_render_exact_excerpts_and_page_labels=true;
    report.source_display_note='Previously generated real-Gemini W10 answer; rendering check only, not new answer generation.';
  }
  await page.screenshot({path:path.join(folder,'live-result.png'),fullPage:true,animations:'disabled'});
}catch(error){report.errors.push(error.message);report.status='FAILED';process.exitCode=1}
finally{
  report.completed_utc=new Date().toISOString();
  report.full_fresh_live_gate_passed=report.status==='COMPLETED'&&report.fresh_answer_accuracy===true&&!report.errors.length;
  await writeFile(path.join(folder,'results.json'),JSON.stringify(report,null,2));
  await browser.close();
  if(child.exitCode===null){
    if(process.platform==='win32')execFileSync('taskkill',['/PID',String(child.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'});
    else child.kill('SIGKILL');
  }
  await log.close();
  console.log(JSON.stringify({status:report.status,checks:report.checks,full_fresh_live_gate_passed:report.full_fresh_live_gate_passed,errors:report.errors},null,2));
}
