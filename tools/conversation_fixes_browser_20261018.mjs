import {chromium} from '../frontend/node_modules/playwright/index.mjs';
import {spawn,execFileSync} from 'node:child_process';
import {mkdir,readFile,writeFile,open} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import assert from 'node:assert/strict';
const root=fileURLToPath(new URL('../',import.meta.url));
const folder=path.join(root,'reports/publication/conversation-fixes-browser-20261018');await mkdir(folder,{recursive:true});
const db=path.join(folder,`chats-${Date.now()}.sqlite3`);const log=await open(path.join(folder,'server.log'),'a');
const child=spawn(path.join(root,'.venv/Scripts/python.exe'),[path.join(root,'tools/publication_system_checks.py'),'--serve','--mode','live','--db',db,'--port','8504'],{cwd:root,windowsHide:true,stdio:['ignore',log.fd,log.fd]});
const browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1440,height:1000}});const base='http://127.0.0.1:8504';
const report={status:'RUNNING',started_utc:new Date().toISOString(),checks:{},turns:[],errors:[],pipeline_revision:execFileSync(path.join(root,'.venv/Scripts/python.exe'),['-c','from compass.config import Settings;from compass.benchmark import revision;print(revision(Settings()))'],{cwd:root,windowsHide:true}).toString().trim()};
const get=async url=>{const r=await page.request.get(base+url);assert(r.ok());return r.json()};
let cid;
async function send(question){
 const composer=page.getByRole('textbox',{name:'Message Student Compass'});await page.waitForFunction(()=>!document.querySelector('textarea').disabled);
 const created=cid?null:page.waitForResponse(r=>r.url()===base+'/api/conversations'&&r.request().method()==='POST');
 await composer.fill(question);await composer.press('Enter');await page.getByText(question,{exact:true}).last().waitFor({timeout:1500});
 if(created)cid=(await(await created).json()).id;
 const end=Date.now()+140000;while(Date.now()<end){const rows=(await get('/api/conversations/'+cid)).turns;const turn=rows.at(-1);if(turn&&turn.question===question&&turn.status!=='pending'){report.turns.push(turn);if(turn.status==='failed')throw new Error(turn.error);await page.locator('.exchange').last().locator('.answer-footer').waitFor({state:'attached',timeout:15000});assert.equal(await page.locator('.user-bubble').last().textContent(),question);report.checks.completed_answers_render=true;return turn}await new Promise(r=>setTimeout(r,200))}throw new Error('Timeout waiting for saved turn');
}
try{
 let ready=false;for(let i=0;i<100;i++){if(child.exitCode!==null)throw new Error('Server exited');try{await get('/api/health');ready=true;break}catch{}await new Promise(r=>setTimeout(r,150))}assert(ready);
 await page.goto(base);await page.getByRole('textbox',{name:'Message Student Compass'}).waitFor();
 assert(await page.locator('.exchange').count()===0);report.checks.starts_empty=true;
 let turn=await send("What's the deadline?");assert.match(turn.answer,/Which deadline/i);assert.equal(turn.diagnostics.api_calls,0);report.checks.ambiguous_deadline_clarifies=true;
 turn=await send('For withdrawing from a course.');assert.match(turn.answer,/last day of the makeup week/i);assert(turn.citations.length);report.checks.explicit_followup_answers_with_sources=true;
 turn=await send('List the questions I have asked in this chat.');assert.equal(turn.diagnostics.route,'conversation_history');assert(turn.answer.includes("What's the deadline?")&&turn.answer.includes('For withdrawing'));assert(!turn.citations.length);report.checks.exact_history_request_local=true;
 turn=await send('Give me a short recap of this conversation.');assert.equal(turn.diagnostics.route,'conversation_summary');assert.match(turn.answer,/Saved reply excerpt/);assert(!turn.answer.includes('A document-based answer with sources was saved'));report.checks.useful_bounded_recap=true;
 turn=await send('What is the minimum penalty for cheating in exams?');assert.match(turn.answer,/conflict/i);assert.match(turn.answer,/precedence/i);assert(turn.citations.length>=2);report.checks.exam_conflict_disclosed=true;
 const last=page.locator('.exchange').last();assert.match(await last.locator('.assistant-content').textContent(),/conflicting penalty wording/);const source=last.locator('.sources>summary');await source.click();await last.locator('.source-card>summary').last().click();await last.scrollIntoViewIfNeeded();report.checks.sources_expand=true;
 await page.screenshot({path:path.join(folder,'live-result.png'),fullPage:true,animations:'disabled'});
 await page.request.patch(base+'/api/conversations/'+cid,{data:{title:'Conversation fix verification'}});await page.reload();await page.waitForFunction(()=>!document.querySelector('textarea').disabled);assert.equal(await page.locator('.exchange').count(),0);report.checks.reload_is_empty=true;
 await page.getByRole('button',{name:'Conversation fix verification',exact:true}).click();await page.locator('.user-bubble').first().waitFor();assert.equal(await page.locator('.user-bubble').count(),5);report.checks.saved_chat_restores=true;
 report.status='PASS';
}catch(e){report.status=/quota/i.test(e.message)?'BLOCKED_BY_QUOTA':'FAILED';report.errors.push(e.message);process.exitCode=1}
finally{report.completed_utc=new Date().toISOString();await writeFile(path.join(folder,'results.json'),JSON.stringify(report,null,2));await browser.close();if(child.exitCode===null)execFileSync('taskkill',['/PID',String(child.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'});await log.close();console.log(JSON.stringify({status:report.status,checks:report.checks,errors:report.errors},null,2))}
