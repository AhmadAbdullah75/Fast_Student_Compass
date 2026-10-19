// Explicit live check: consumes free Gemini quota. Normal startup never runs it.
import { chromium } from '../frontend/node_modules/playwright/index.mjs';
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import assert from 'node:assert/strict';
const report={started:new Date().toISOString(),checks:{},turns:[],errors:[]};
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
const base='http://127.0.0.1:8501';
const request=page.request;
const json=async path=>{const r=await request.get(base+path);assert(r.ok());return r.json()};
const hash=chats=>createHash('sha256').update(JSON.stringify(chats.sort((a,b)=>a.id.localeCompare(b.id)))).digest('hex');
const manifest=JSON.parse(await readFile(new URL('../data/manifest.json',import.meta.url),'utf8'));
const before=await json('/api/conversations');
let cid;
async function waitAnswer(index){
  const limit=Date.now()+90000;
  while(Date.now()<limit){
    const chat=await json(`/api/conversations/${cid}`);
    const t=chat.turns[index];
    if(t?.status==='failed')throw new Error(t.error);
    if(t?.status==='completed')return t;
    await new Promise(resolve=>setTimeout(resolve,800));
  }
  throw new Error('Timed out waiting for the saved live answer.');
}
try{
  await page.goto(base);
  await page.waitForFunction(()=>!document.querySelector('textarea')?.disabled);
  report.checks.opens_empty_despite_existing_history=await page.locator('.exchange').count()===0;
  await page.screenshot({path:fileURLToPath(new URL('../reports/react-live-welcome.png',import.meta.url)),animations:'disabled',fullPage:true});
  const question='What is the minimum duration of a bachelor degree?';
  const creation=page.waitForResponse(r=>r.url()===base+'/api/conversations'&&r.request().method()==='POST');
  await page.getByRole('textbox',{name:'Message Student Compass'}).fill(question);
  await page.getByRole('textbox',{name:'Message Student Compass'}).press('Enter');
  await page.locator('.user-bubble').waitFor({state:'visible',timeout:1500});
  cid=(await(await creation).json()).id;
  const first=await waitAnswer(0);
  report.turns.push(first);
  assert.match(first.answer,/four|\b4\b/i);
  assert.match(first.answer,/8|eight/i);
  assert(first.citations.some(c=>c.references.some(r=>r.id==='academic'&&r.pdf_page===10)));
  report.checks.real_retrieval_answer_and_correct_page=true;
  await page.locator('.sources>summary').first().waitFor({state:'visible'});
  await page.locator('.inline-citation').first().waitFor({state:'visible'});
  report.checks.real_citation_link_rendered=true;
  await page.locator('.sources>summary').first().click();
  await page.locator('.source-card>summary').first().click();
  report.checks.real_source_excerpt_displayed=await page.locator('.source-body pre').first().isVisible();
  await page.screenshot({path:fileURLToPath(new URL('../reports/react-live-chat.png',import.meta.url)),animations:'disabled',fullPage:true});
  await page.waitForFunction(()=>!document.querySelector('textarea')?.disabled);
  await page.getByRole('textbox',{name:'Message Student Compass'}).fill('Can I complete it in less than two years?');
  await page.getByRole('button',{name:'Send message',exact:true}).click();
  const second=await waitAnswer(1);report.turns.push(second);
  assert.match(second.answer,/four|\b4\b/i);
  assert(second.diagnostics.history_context.includes(question));
  assert.match(second.diagnostics.search_question,/bachelor|degree/i);
  report.checks.real_followup_uses_saved_context=true;
  await page.waitForFunction(()=>!document.querySelector('textarea')?.disabled);
  await page.getByRole('textbox',{name:'Message Student Compass'}).fill('can you tell me what questions i have asked');
  await page.getByRole('button',{name:'Send message',exact:true}).click();
  const recall=await waitAnswer(2);report.turns.push(recall);
  assert(recall.answer.includes(question)&&recall.answer.includes('Can I complete it in less than two years?'));
  assert(recall.diagnostics.api_calls===0);
  report.checks.local_recall_lists_real_prior_questions=true;
  const renamed=await request.patch(base+`/api/conversations/${cid}`,{data:{title:'React live verification'}});assert(renamed.ok());
  await page.reload();
  await page.waitForFunction(()=>!document.querySelector('textarea')?.disabled);
  assert(await page.locator('.exchange').count()===0);
  await page.getByRole('button',{name:'React live verification',exact:true}).click();
  await page.waitForFunction(()=>document.querySelectorAll('.exchange').length===3);
  report.checks.real_chat_resumes_after_reload=true;
  report.checks.model_is_unchanged=first.model==='gemini-3.5-flash-lite';
  report.checks.index_is_unchanged=manifest.fingerprint===JSON.parse(await readFile(new URL('../data/manifest.json',import.meta.url),'utf8')).fingerprint;
}catch(error){report.errors.push(error.message);process.exitCode=1}
finally{
  if(cid){
    const removed=await request.delete(base+`/api/conversations/${cid}`);
    report.checks.own_test_chat_removed=removed.status()===204;
  }
  const after=await json('/api/conversations');
  report.checks.existing_conversation_metadata_unchanged=hash(before)===hash(after);
  report.existing_chat_count=before.length;
  report.completed=new Date().toISOString();
  report.all_passed=Object.values(report.checks).every(Boolean)&&!report.errors.length;
  await writeFile(new URL('../reports/react-live-smoke.json',import.meta.url),JSON.stringify(report,null,2));
  console.log(JSON.stringify({all_passed:report.all_passed,checks:report.checks,errors:report.errors},null,2));
  await browser.close();
  if(!report.all_passed)process.exitCode=1;
}
