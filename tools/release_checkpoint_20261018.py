"""Read-only evidence assembly; no API requests and no inferred semantic passes."""
import json,hashlib,sqlite3,csv,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from compass.config import Settings
from compass.benchmark import revision
FOLDER=ROOT/'reports/publication/release-complete-20261018'
def read(path,default=None):
 p=ROOT/path
 return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default
def write(path,data):
 (ROOT/path).write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
rev=revision(Settings());baseline=read(FOLDER/'baseline.json');spec=read('evaluation/release-20261018/new-conversations-final.json')
active_names=['release-contact-retest-v15-20261019','release-timebox-regressions-v14-20261019','release-current-conversations-v5-20261018','release-current-conversations-v4-20261018','release-current-conversations-v3-20261018','release-current-conversations-v2-20261018','release-current-conversations-20261018','release-acceptance-conversations-v2-20261018','release-acceptance-conversations-20261018','release-full-conversations-20261018','release-qualified-conversations-20261018','release-final-conversations-20261018','release-new-conversations-20261018']
active_run=next((name for name in active_names if read(f'reports/publication/{name}/workflows.json',{}).get('pipeline_revision')==rev),active_names[0])
raw=read(f'reports/publication/{active_run}/workflows.json',{'results':[]})
review=read(f'reports/publication/{active_run}/turn-semantic-review.json',{'results':{}})
if raw.get('pipeline_revision')!=rev:raw={'results':[]}
actual={f"{w['id']}:{i+1}":t for w in raw['results'] for i,t in enumerate(w['turns'])}
rows=[];blockers=[]
for ident,questions in spec['sequences'].items():
 for i,q in enumerate(questions,1):
  key=f'{ident}:{i}';turn=actual.get(key);note=review['results'].get(key,{})
  state='NOT_RUN' if not turn else 'EXECUTION_FAILED' if turn['status']!='completed' else 'PENDING_REVIEW' if not note else note['status']
  rows.append({'id':key,'question':q,'execution':turn['status'] if turn else 'NOT_RUN','semantic':state,'note':note.get('note',''),'evidence_revision':raw.get('pipeline_revision') if turn else None})
  if turn and turn['status']=='failed' and any(s in (turn.get('error') or '').lower() for s in ['quota','rate limit']):blockers.append({'run':active_run,'case':key,'message':turn['error']})
bank=read('evaluation/release-20261018/complete648.json')['cases'];br=read('reports/benchmark/release-qualification-v15-20261019.json',{'results':[]});bn=read('reports/publication/release-qualification-v15-20261019-semantic-review.json',{'results':{}})
if br.get('pipeline_revision')!=rev:br={'results':[]};bn={'results':{}}
auxiliary=[]
# Discovery suites are all included in the576-case qualification bank.
for name,suite in []:
 ar=read(f'reports/benchmark/{name}.json',{'results':[]});an=read(f'reports/publication/{name}-semantic-review.json',{'results':{}})
 cases=read('evaluation/release-20261018/'+suite)['cases']
 if ar.get('pipeline_revision')!=rev:ar={'results':[]};an={'results':{}}
 auxiliary.append({'run':name,'required':len(cases),'executed':len(ar['results']),'reviewed':len(an['results']),'pending':[c['id'] for c in cases if c['id'] not in an['results']]})
 for item in ar['results']:
  if item['status']=='failed' and any(x in item.get('error','').lower() for x in ['quota','rate limit']):blockers.append({'run':name,'case':item['id'],'message':item['error'],'quota_scope':item.get('quota_scope')})
for t in br['results']:
 if t['status']=='failed' and any(s in t.get('error','').lower() for s in ['quota','rate limit']):blockers.append({'run':'release-qualification-v15-20261019','case':t['id'],'message':t['error'],'quota_scope':t.get('quota_scope')})
discovery=read('reports/benchmark/release-discovery-20261018.json',{'results':[]})
discovery_notes=read('reports/publication/release-discovery-20261018-semantic-review.json',{'results':{}})
for item in discovery['results']:
 if item['status']=='failed' and any(x in (item.get('error') or '').lower() for x in ['quota','rate limit']):blockers.append({'run':'release-discovery-20261018','case':item['id'],'message':item['error'],'quota_scope':item.get('quota_scope')})
workflow_inventory=[]
for wp in sorted((ROOT/'reports/publication').glob('*/workflows.json')):
 wr=json.loads(wp.read_text(encoding='utf-8'))
 if wr.get('pipeline_revision')!=rev:continue
 workflow_inventory.append({'run':wp.parent.name,'sequences':len(wr.get('results',[])),'turns_executed':sum(len(w.get('turns',[])) for w in wr.get('results',[]))})
 for w in wr.get('results',[]):
  for index,t in enumerate(w.get('turns',[]),1):
   if t.get('status')=='failed' and any(term in (t.get('error') or '').lower() for term in ['quota','rate limit']):blockers.append({'run':wp.parent.name,'case':f"{w['id']}:{index}",'message':t['error']})
con=sqlite3.connect('file:'+str(ROOT/'data/chats.sqlite3')+'?mode=ro',uri=True);con.row_factory=sqlite3.Row
payload={t:[dict(r) for r in con.execute('SELECT * FROM '+t+' ORDER BY id')] for t in ['conversations','turns']};con.close()
ph=hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
checks={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest for name,digest in baseline['hashes'].items()}
integrity={'production_unchanged':ph==baseline['production_hash'],'production_hash':ph,'conversations':len(payload['conversations']),'turns':len(payload['turns']),'baseline_files_unchanged':checks};write(FOLDER/'integrity.json',integrity)
state={'utc':datetime.now(timezone.utc).isoformat(),'pipeline_revision':rev,'status':'BLOCKED_BY_QUOTA' if blockers else 'COMPLETE_VERIFICATION_IN_PROGRESS','publication_ready':False,'active_blocker':blockers[0] if blockers else None,'fresh_conversations':{'required':len(rows),'executed':len(actual),'completed':sum(t['status']=='completed' for t in actual.values()),'reviewed_pass':sum(r['semantic']=='PASS' for r in rows),'needs_fix':[r['id'] for r in rows if r['semantic']=='NEEDS_FIX'],'pending':[r['id'] for r in rows if r['semantic']!='PASS']},'discovery':{'run':'release-discovery-20261018','pipeline_revision':discovery.get('pipeline_revision'),'required':421,'executed':len(discovery['results']),'reviewed':len(discovery_notes['results']),'execution_failures':[x['id'] for x in discovery['results'] if x['status']!='completed'],'note':'Discovery evidence only; never substituted for frozen final qualification.'},'auxiliary_suites':auxiliary,'current_workflow_inventory':workflow_inventory,'standalone':{'run':'release-qualification-v15-20261019','suite':'evaluation/release-20261018/complete648.json','required':len(bank),'executed':len(br['results']),'reviewed':len(bn['results']),'not_run':[c['id'] for c in bank if c['id'] not in {r['id'] for r in br['results']}]},'offline':read(FOLDER/'offline-evidence.json'),'integrity':integrity,'pending_stages':['complete648 standalone qualification cases and source-based reviews','original10ordered workflows','existing6fresh workflows','supplied replay conversations','final real-provider React smoke and20application-check report','independent policy review and joint fresh human live test'],'active_conversation_run':active_run,'historical_initial_run':'release-new-conversations-20261018 retains47attempts including8quality failures and1provider failure; never overwritten.','note':'Earlier focused approval superseded by new complete-verification request. Unexecuted cases are not passed. Evidence carries its actual revision.'}
focused=read(FOLDER/'focused-status.json',{})
if focused.get('pipeline_revision')==rev and focused.get('status')=='FOCUSED_VERIFICATION_COMPLETE_HUMAN_GATES_PENDING':
 state['historical_full_verification_status']=state['status']
 state['historical_full_verification_blocker']=state['active_blocker']
 state['status']=focused['status'];state['active_blocker']=None
 state['focused_verification']=focused
 state['pending_stages']=focused['remaining_publication_gates']
 state['note']='User narrowed scope to risk-based testing. Full-bank historical attempts retained; not claimed passed. PriorW04quota attempt resolved by successful complete replay.'
write(FOLDER/'checkpoint.json',state);write('reports/publication/final-status.json',state)
write(FOLDER/'new-conversation-scorecard.json',rows)
write('evaluation/publication/pending-tests.json',{'pipeline_revision':rev,'publication_ready':False,'active_blocker':state['active_blocker'],'full_verification_requested':True,'fresh_pending':state['fresh_conversations']['pending'],'standalone_not_run':state['standalone']['not_run'],'pending_stages':state['pending_stages']})
print(json.dumps({'pipeline_revision':rev,'status':state['status'],'active_blocker':state['active_blocker'],'fresh_conversations':{k:state['fresh_conversations'][k] for k in ['required','executed','completed','reviewed_pass','needs_fix']},'standalone':{k:state['standalone'][k] for k in ['required','executed','reviewed']}}))
