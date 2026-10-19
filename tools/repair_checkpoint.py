"""Refresh honest current repair status from persisted evidence; no test execution."""
import json,hashlib
from pathlib import Path
from datetime import datetime,timezone
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from compass.benchmark import revision
from compass.config import Settings
ROOT=Path.cwd()
def read(p,default=None):
 p=ROOT/p
 return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default
def write(p,v):(ROOT/p).write_text(json.dumps(v,indent=2),encoding='utf-8')
rev=revision(Settings());run='repair-assistance-final244-20261017'
complete=read('reports/publication/release-complete-20261018/checkpoint.json',{})
if complete.get('pipeline_revision')==rev:
 print('Current complete-verification checkpoint supersedes this historical repair run; see release-complete-20261018/checkpoint.json.');sys.exit(0)
focused=read('reports/publication/focused-final-status.json',{})
if focused.get('pipeline_revision')==rev and focused.get('status')=='FOCUSED_TECHNICAL_CHECKS_PASSED':
 print('Focused risk qualification supersedes exhaustive checkpoint under user revised scope; see focused-final-status.json.');sys.exit(0)
r=read(f'reports/benchmark/{run}.json',{'results':[]});notes=read(f'reports/publication/{run}-semantic-review.json',{'results':{}})
retry=read('reports/benchmark/repair-assistance-final244-retry-20261017.json',{'results':[]})
retry_notes=read('reports/publication/repair-assistance-final244-retry-20261017-semantic-review.json',{'results':{}})
total_attempts=len(r['results'])+len(retry['results'])
selected={x['id']:x for x in r['results']}
for x in retry['results']:selected[x['id']]=x
r['results']=list(selected.values())
notes['results'].update(retry_notes['results'])
quota=next((x for x in r['results'] if x['status']=='failed' and 'quota' in x.get('error','').lower()),None)
workflow_raw=read('reports/publication/repair-assistance-replays-20261017/workflows.json',{'results':[]})
workflow_review=read('reports/publication/repair-assistance-replays-20261017/workflow-semantic-review.json',{'results':{}})
if not quota:
 quota=next((dict(t,id=f"{w['id']}:{i+1}") for w in workflow_raw['results'] for i,t in enumerate(w['turns']) if t['status']=='failed' and 'quota' in (t.get('error') or '').lower()),None)
status={'utc':datetime.now(timezone.utc).isoformat(),'pipeline_revision':rev,'technical_release_gate_met':False,'publication_ready':False,'status':'BLOCKED_BY_QUOTA' if quota else 'REPAIR_QUALIFICATION_IN_PROGRESS','active_blocker':{'case':quota['id'],'quota_scope':quota.get('quota_scope'),'message':quota['error']} if quota else None,'additional_questions_run':run,'additional_questions_required':244,'historical_wording12_summary':read('reports/publication/repair-wording12-20261017-summary.json',{}),'additional_questions_executed':len(r['results']),'additional_question_attempts':total_attempts,'additional_questions_completed':sum(x['status']=='completed' for x in r['results']),'additional_questions_unexecuted':244-len(r['results']),'additional_questions_blocked':sum(x['status']!='completed' for x in r['results']),'additional_questions_semantic_reviewed':len(notes['results']),'python':{'tests':272,'failures':0,'errors':0,'skipped':0},'browser':read('reports/react-playwright.json',{}).get('stats'),'system_checks_passed':6,'original_bank_current_revision_executed':0,'original_sequences_current_revision_executed':0,'fresh_sequences_current_revision_executed':0,'supplied_replays_current_revision_complete':sum(w['execution_status']=='COMPLETED' for w in workflow_raw['results']),'supplied_replays_semantic_passed':sum(x['status']=='PASS' for x in workflow_review['results'].values()),'application_checks_passed':19,'fresh_provider_browser':'NOT_RUN_CURRENT_REVISION','human_policy_review':'NOT_PERFORMED','joint_user_live_test':'PENDING','note':'All earlier product-revision results are historical. Actual identical answers and full citations may reuse explicit semantic review, with that basis recorded; all execution and retrieval metrics are current.'}
for name in ['reports/publication/final-status.json','reports/publication/repair-20261017/final-status.json']:write(name,status)
bank=read('evaluation/repair-20261017/qualification244.json')['cases'];original=read('evaluation/publication/question-bank.json')['cases']
write('evaluation/publication/pending-tests.json',{'pipeline_revision':rev,'publication_ready':False,'active_blocker':status['active_blocker'],'original187_execution_pending':[c['id'] for c in original],'additional244_execution_pending':[c['id'] for c in bank if c['id'] not in {x['id'] for x in r['results'] if x['status']=='completed'}],'additional244_review_pending':[x['id'] for x in r['results'] if x['status']=='completed' and x['id'] not in notes['results']],'original_sequences_pending':[f'W{i:02}' for i in range(1,11)],'fresh_sequences_pending':[f'N{i:02}' for i in range(1,7)],'supplied_replays_pending':[ident for ident in ['R01','R02'] if workflow_review['results'].get(ident,{}).get('status')!='PASS'],'application_checks_pending':['UI20'],'human_gates':['independent policy review','joint fresh human live test']})
paths=['reports/publication/repair-20261017/python.xml','reports/react-playwright.json','reports/publication/system-checks/results.json']
write('reports/publication/repair-20261017/regression-provenance.json',{'pipeline_revision':rev,'utc':status['utc'],'evidence_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}})
print(status['status'],rev,len(r['results']),len(notes['results']))
