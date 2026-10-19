import json
from threading import Event
from time import monotonic, sleep
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from compass.config import Settings
from compass.storage import ChatStore
from compass.rag import ChatService, Answer
from compass.web import create_app

@pytest.fixture
def web(tmp_path):
    gate=Event();gate.set()
    calls=[]
    class Pipeline:
        manifest={'dataset_version':'web-fixture','fingerprint':'fixture'}
        def answer(self,q,turns):
            gate.wait(5);calls.append((q,[t['question'] for t in turns]))
            if 'quota' in q and sum(c[0]==q for c in calls)==1:raise RuntimeError('429 SECRET')
            return Answer('A documented answer [S1]',[{'id':'S1','excerpt':'Exact source','references':[{'title':'Fixture','section':'Rules','pdf_page':2,'printed_label':'1'}]}],diagnostics={'route':'document_rag'})
    class Service(ChatService):
        def __init__(self,settings,storage):super().__init__(settings,storage,Pipeline)
    storage=ChatStore(tmp_path/'data/chats.sqlite3')
    app=create_app(Settings(root=tmp_path),storage,Service)
    with TestClient(app,base_url='http://localhost:8501') as client:
        yield client,storage,gate,calls
        gate.set()

def create(client):return client.post('/api/conversations',json={}).json()['id']
def submit(client,cid,q='Question',request_id=None):return client.post(f'/api/conversations/{cid}/turns',json={'question':q,'request_id':request_id or uuid4().hex})
def wait(client,cid,status='completed'):
    end=monotonic()+6
    while monotonic()<end:
        turns=client.get(f'/api/conversations/{cid}').json()['turns']
        if turns and turns[-1]['status']==status:return turns[-1]
        sleep(.02)
    pytest.fail('Worker did not finish')

def test_new_workspace_reads_do_not_create_or_select_old_chats(web):
    client,db,_,_=web
    old=create(client)
    assert len(client.get('/api/conversations').json())==1
    assert len(client.get('/api/conversations').json())==1
    cid=uuid4().hex
    assert client.post('/api/conversations',json={'id':cid}).json()['id']==cid
    client.post('/api/conversations',json={'id':cid})
    assert len(db.list())==2 and db.turns(old)==[]

def test_submit_returns_pending_before_generation_and_deduplicates(web):
    client,db,gate,calls=web;cid=create(client);rid=uuid4().hex
    gate.clear()
    response=submit(client,cid,request_id=rid)
    assert response.status_code==202
    tid=response.json()['id']
    assert response.json()['running'] and response.json()['status']=='pending'
    assert not calls and db.get_turn(tid)['question']=='Question'
    assert submit(client,cid,request_id=rid).json()['id']==tid
    assert submit(client,cid,'Different',rid).status_code==409
    assert submit(client,cid,'Duplicate new submission').status_code==409
    assert client.delete(f'/api/conversations/{cid}').status_code==409
    assert client.delete(f'/api/turns/{tid}').status_code==409
    gate.set();answer=wait(client,cid)
    assert len(calls)==1 and answer['citations'][0]['references'][0]['pdf_page']==2
    assert client.post(f'/api/turns/{tid}/retry').json()['status']=='completed'
    assert len(db.turns(cid))==1

def test_failure_retry_same_turn_and_sanitized_error(web):
    client,db,_,calls=web;cid=create(client)
    tid=submit(client,cid,'quota please').json()['id']
    failed=wait(client,cid,'failed')
    assert 'quota' in failed['error'] and 'SECRET' not in json.dumps(failed)
    client.post(f'/api/turns/{tid}/retry');done=wait(client,cid)
    assert done['id']==tid and len(db.turns(cid))==1 and len(calls)==2

def test_resume_history_rename_delete_and_isolation(web):
    client,db,_,calls=web;first=create(client);second=create(client)
    submit(client,first,'First');wait(client,first)
    submit(client,first,'Follow-up');wait(client,first)
    assert calls[-1][1]==['First']
    assert ChatStore(db.path).turns(first)[0]['citations']
    submit(client,second,'Separate');wait(client,second)
    assert calls[-1][1]==[]
    assert client.patch(f'/api/conversations/{first}',json={'title':'Renamed'}).json()['title']=='Renamed'
    assert client.delete(f'/api/conversations/{first}').status_code==204
    assert db.turns(first)==[] and client.get(f'/api/conversations/{first}').status_code==404
    assert len(db.turns(second))==1

def test_interrupted_turn_retry_and_discard(web):
    client,db,_,_=web;cid=create(client)
    tid=db.begin(cid,'Interrupted')
    row=client.get(f'/api/conversations/{cid}').json()['turns'][0]
    assert row['status']=='pending' and not row['running']
    assert client.delete(f'/api/turns/{tid}').status_code==204
    tid=db.begin(cid,'Interrupted again')
    client.post(f'/api/turns/{tid}/retry');wait(client,cid)
    assert len(db.turns(cid))==1

@pytest.mark.parametrize('q',['','   ','x'*6001])
def test_invalid_input_does_not_persist(web,q):
    client,db,_,_=web;cid=create(client)
    assert submit(client,cid,q).status_code==422
    assert db.turns(cid)==[]

def test_local_origin_boundary_and_missing_resources(web):
    client,_,_,_=web
    assert client.post('/api/conversations',json={},headers={'Origin':'https://example.com'}).status_code==403
    assert client.post('/api/conversations',json={},headers={'Origin':'http://localhost:8501'}).status_code==201
    assert client.post('/api/turns/missing/retry').status_code==404
    assert client.get('/api/health').headers['cache-control']=='no-store'
    assert client.get('/.env').status_code==404
    assert client.get('/api/conversations',headers={'Host':'evil.example'}).status_code==400

def test_security_headers_and_unexposed_internal_files(web):
    client,_,_,_=web
    r=client.get('/api/health')
    assert r.headers['x-frame-options']=='DENY'
    assert r.headers['referrer-policy']=='no-referrer'
    for path in ['/data/chats.sqlite3','/data/chroma/chroma.sqlite3','/compass/policy_categories.json','/api/v2/tenants','/api/v2/tenants/default_tenant/databases/default_database/collections']:
        assert client.get(path).status_code==404


def test_sql_and_prompt_like_title_stays_data(web):
    client,db,_,_=web;cid=create(client)
    title="'); DROP TABLE turns; -- <script>alert(1)</script>"
    assert client.patch(f'/api/conversations/{cid}',json={'title':title}).status_code==200
    assert client.get(f'/api/conversations/{cid}').json()['title']==title
    assert db.list()
