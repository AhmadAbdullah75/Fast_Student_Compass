"""Resumable live probes of newly observed issues; original chats are read-only."""
import json,sqlite3,sys,time
from dataclasses import asdict
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from compass.rag import RagPipeline,friendly_error
from compass.config import Settings
from compass.benchmark import revision,quota_scope
from compass.ingestion import write_json
CASES=[
 ('opposite-lab','I passed theory but failed its associated lab. What must I repeat?', [('I failed theory but passed the lab. What must I repeat?','Both parts must be repeated.')]),
 ('opposite-theory','I failed theory but passed its associated lab. What must I repeat?', [('I passed theory but failed the lab. What must I repeat?','Only lab needs repeating.')]),
 ('fee','What is the fee?', [('Can I withdraw from a course?','Withdrawal conditions apply.')]),
 ('rector','What exactly are the Rector’s List credit-hour requirements? Does at least 30 credit hours clearly mean credits in that semester?',[]),
 ('ai-duration','Exactly how long is an AI-enabled lab? The policy mentions 2.5 hours, a final half-hour, and prompts from the first 2.5 hours.',[]),
 ('transfer','What limits apply when transferring credits from another university?',[]),
 ('merit-citations','My CGPA is still 3.40. Does that change the semester-GPA condition?', [('Explain the SGPA requirement for continuing a merit scholarship.','Continuation requires semester GPA of3.0 or higher.'),('What if it is2.90?','Below the required SGPA.')]),
 ('mixed','How many semesters of internal sponsorship are allowed for bachelor’s, master’s, and PhD students?',[]),
 ('five-courses','I am an undergraduate student. My CGPA is1.90, and this is my first academic warning. What registration conditions apply?',[]),
 ('retake','Can I get a retake for my cousin’s wedding? What about my sibling’s wedding?',[]),
 ('warning-boundary','Correction: after my second academic warning, my CGPA is exactly2.00. What is my warning count?',[]),
 ('fresh-lab','Theory passed, lab failed. What should I repeat?',[]),
 ('fresh-scholarship','My SGPA is3.0 and CGPA2.0. Does CGPA alone put me below the warning threshold for internal sponsorship?',[]),
]
settings=Settings();folder=settings.root/'reports/publication/hardening-20261017';path=folder/'live-probes.json'
report=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'pipeline_revision':revision(settings),'started_utc':datetime.now(timezone.utc).isoformat(),'results':[]}
assert report['pipeline_revision']==revision(settings),'Use a new report after product changes'
pipeline=RagPipeline(settings)
for ident,q,history in CASES:
 if any(r['id']==ident for r in report['results']):continue
 start=time.monotonic();row={'id':ident,'question':q,'history':history}
 try:
  result=pipeline.answer(q,[{'question':a,'answer':b,'status':'completed'} for a,b in history]);row.update(asdict(result));row['trace']=result.diagnostics
 except Exception as e:
  row.update(status='failed',error=friendly_error(e),error_type=type(e).__name__,quota_scope=quota_scope(e),trace=pipeline.diagnostics(q,''))
 row['latency_seconds']=time.monotonic()-start;report['results'].append(row);write_json(path,report)
 print(json.dumps({'id':ident,'status':row['status'],'answer':row.get('answer'), 'error':row.get('error')},ensure_ascii=False),flush=True)
 if row['status']=='failed' and 'quota' in row['error'].lower():report['stop_reason']='quota';write_json(path,report);break
 time.sleep(max(0,10*(2 if history else 1)-(time.monotonic()-start)))
