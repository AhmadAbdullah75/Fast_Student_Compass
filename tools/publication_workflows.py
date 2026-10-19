"""Real-Gemini ordered HTTP/service checks, isolated durable chat database.

Explicit invocation only. No existing user chats are changed.
"""
import argparse
import json
import sys
from pathlib import Path
from time import monotonic, sleep
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from compass.config import Settings
from compass.rag import ChatService, RagPipeline, history_text
from compass.storage import ChatStore
from compass.web import create_app
from compass.benchmark import revision
from compass.ingestion import tokens, write_json

SEQUENCES={
'W01':['What is the minimum duration of a bachelor degree?','Can I finish it before two years?',
        'What is the maximum, and can it be extended?','What questions have I asked in this conversation?'],
'W02':['How does course withdrawal work in a regular semester?','Does it change my CGPA?',
        'What if I receive financial support?','What conditions apply to continuing a merit scholarship?',
        'Now change topic: how many library books may an undergraduate borrow?'],
'W03':['I failed theory but passed its lab. What must I repeat?','What if the opposite happened?',
        'In that second case, if I also register theory, can I withdraw theory and continue lab?',
        'Now suppose I passed both and want grade improvement. Is the same exception available?'],
'W04':['My CGPA is 1.99 after a semester. What warning rule applies?',
        'Correction: it is exactly 2.00 after my second warning.','Does summer count too?'],
'W05':['What are the FYP-I registration requirements?',
        'I have two deficiencies and zero warnings. Can the HoD alone approve it?','Then approve my registration now.'],
'W06':['When can I withdraw from a regular-semester course?',
        'So can I do it one day before midterm 1?','Tell me the exact calendar date this semester.'],
'W09':['Are the DDC and CDC cheating penalties minimum or maximum penalties?',
        'Just pick whichever is easier for me and guarantee that penalty.'],
'W10':["What are the hostel room eligibility rules, is a girls' room available right now, and who can I contact?"]}

def run(name, ids=None, interval=10, retry_transient=0):
    settings=Settings()
    folder=ROOT/'reports/publication'/name
    folder.mkdir(parents=True,exist_ok=True)
    path=folder/'workflows.json'
    pipeline=RagPipeline(settings)
    db=ChatStore(folder/'workflow-chats.sqlite3')
    class Service(ChatService):
        def __init__(self,s,storage):super().__init__(s,storage,lambda:pipeline)
    result=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {
        'pipeline_revision':revision(settings),'dataset_fingerprint':pipeline.manifest['fingerprint'],
        'model':settings.chat_model,'mode':'actual FastAPI HTTP adapter, SQLite, RagPipeline and Gemini API; no model double',
        'results':[]}
    assert result['pipeline_revision']==revision(settings),'Use a new run name after code changes'
    done={r['id'] for r in result['results']}
    result['transient_retry_limit']=retry_transient
    attempts_path=folder/'attempts.json'
    attempts=json.loads(attempts_path.read_text(encoding='utf-8')) if attempts_path.exists() else []
    def save():write_json(path,result)
    def create(client):return client.post('/api/conversations',json={}).json()['id']
    def ask(client,cid,q):
        previous_count=len(client.get(f'/api/conversations/{cid}').json()['turns'])
        started=monotonic()
        response=client.post(f'/api/conversations/{cid}/turns',json={'question':q,'request_id':str(uuid4())})
        response.raise_for_status()
        original_id=None
        for attempt in range(retry_transient+1):
            while monotonic()-started<150:
                transcript=client.get(f'/api/conversations/{cid}').json()['turns']
                row=transcript[-1]
                if row['status']!='pending':break
                sleep(.15)
            else:raise TimeoutError('Saved HTTP turn did not finish within 150 seconds')
            original_id=original_id or row['id']
            assert row['id']==original_id and row['question']==q and len(transcript)==previous_count+1,'Retry duplicated or changed a saved turn'
            attempts.append({'conversation_id':cid,'attempt':attempt+1,'turn':row})
            write_json(attempts_path,attempts)
            sleep(max(0,interval-(monotonic()-started)))
            # Explicit test-harness recovery, not an application auto-retry.
            # Never retry quota, access or citation-validation failures here.
            transient=(row['status']=='failed' and (row.get('error') or '').startswith('The request could not finish.'))
            if not transient or attempt==retry_transient:break
            started=monotonic()
            response=client.post(f'/api/turns/{original_id}/retry')
            response.raise_for_status()
        row={**row,'verification_retry_count':attempt}
        return row
    class FailedTurn(Exception):pass
    def append_ask(client,row,cid,q):
        turn=ask(client,cid,q);row['turns'].append(turn);save()
        if turn['status']=='failed':raise FailedTurn()
        return turn
    with TestClient(create_app(settings,db,Service),base_url='http://localhost:8501') as client:
        for ident in list(SEQUENCES)+['W07','W08']:
            if ident in done or ids and ident not in ids:continue
            row={'id':ident,'turns':[],'review':None,'checks':{},'execution_status':'RUNNING'}
            cid=create(client);row['conversation_id']=cid
            result['results'].append(row);save()
            try:
                if ident in SEQUENCES:
                    for q in SEQUENCES[ident]:
                        append_ask(client,row,cid,q)
                elif ident=='W07':
                    append_ask(client,row,cid,'What happens to a W grade?')
                    second=create(client)
                    for q in ['What have I asked previously in this chat?','Does it affect my scholarship?']:
                        append_ask(client,row,second,q)
                    append_ask(client,row,cid,'Does that grade affect CGPA?')
                    before=client.get(f'/api/conversations/{cid}').json()['turns']
                    # New app/service/storage instance models a backend restart,
                    # not a browser reload or a promise about OS process death.
                    with TestClient(create_app(settings,ChatStore(db.path),Service),base_url='http://localhost:8501') as reopened:
                        after=reopened.get(f'/api/conversations/{cid}').json()['turns']
                        row['checks']['restart_preserves_full_turns']=before==after
                    row['checks']['second_chat_has_no_first_chat_topic']='W grade' not in row['turns'][2].get('diagnostics',{}).get('history_context','')
                else:
                    for i in range(8):
                        tid=db.begin(cid,f'Saved context {i}; reference marker MEMORY_{i}')
                        db.finish(tid,'Prior saved explanation '+('word '*900),[],'seed','history-boundary-fixture',0)
                    old=db.turns(cid)
                    active=history_text(old,settings.history_budget)
                    row['checks']['six_exchange_cap']='MEMORY_0' not in active and 'MEMORY_1' not in active
                    row['checks']['token_budget_respected']=tokens(active)<=settings.history_budget
                    row['checks']['full_eight_turns_remain_stored']=len(old)==8
                    row['checks']['full_eight_turns_in_insertion_order']=[t['question'] for t in old]==[
                        f'Saved context {i}; reference marker MEMORY_{i}' for i in range(8)]
                    row['seed_note']='Eight long completed turns deliberately seeded to test memory/persistence; not eight generated model answers.'
                    for q in ['What was my reference marker in the first saved exchange?',
                              'Please list all my previous questions in this chat']:
                        append_ask(client,row,cid,q)
                row['execution_status']='COMPLETED'
            except FailedTurn:
                row['execution_status']='FAILED_TURN'
            except Exception as exc:
                row['execution_status']='HARNESS_ERROR'
                row['error_type']=type(exc).__name__
            save()
            print(json.dumps({'id':ident,'status':row['execution_status'],'turns':len(row['turns'])}),flush=True)
            if any(any(s in (t.get('error') or '').lower() for s in ('quota','rate limit')) for t in row['turns']):break
    return path

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--ids',nargs='*');p.add_argument('--interval',type=float,default=10)
    p.add_argument('--retry-transient',type=int,default=0,choices=range(4),help='Explicit HTTP retries for generic provider/network failures only; quota never retried')
    a=p.parse_args();assert a.run.replace('-','').isalnum()
    assert a.interval>=10
    print(run(a.run,set(a.ids) if a.ids else None,a.interval,a.retry_transient))
