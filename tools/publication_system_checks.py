"""Isolated real-process HTTP recovery and actual persisted-index reuse checks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def serve(db_path,port,mode):
    from compass.config import Settings
    from compass.storage import ChatStore
    from compass.rag import ChatService,Answer
    from compass.web import create_app
    import uvicorn
    class Pipeline:
        manifest={'dataset_version':'recovery-fixture','fingerprint':'fixture'}
        def answer(self,q,turns):
            if '[crash]' in q:time.sleep(120)
            if '[timeout]' in q:raise TimeoutError('timeout SECRET')
            return Answer('A recovered answer [S1]',[{'id':'S1','references':[{'title':'Fixture','section':'Recovery','pdf_page':1,'printed_label':'1'}],'excerpt':'Recovery fixture evidence'}])
    class Service(ChatService):
        def __init__(self,s,db):super().__init__(s,db,Pipeline)
    settings=Settings()
    if mode=='missing-index':settings=Settings(root=Path(db_path).parent/'empty-workspace')
    if mode=='missing-key':
        os.environ.pop('GOOGLE_API_KEY',None);os.environ.pop('GEMINI_API_KEY',None)
    app=create_app(settings,ChatStore(Path(db_path)),Service if mode=='recovery' else None)
    uvicorn.run(app,host='127.0.0.1',port=port,log_level='error')

def run():
    import httpx
    from compass.config import Settings
    from compass.ingestion import ingest
    folder=ROOT/'reports/publication/system-checks'
    folder.mkdir(parents=True,exist_ok=True)
    results={'mode':'actual child-process termination/restart and real HTTP adapter; model double for failure injection','checks':{},'details':{}}
    processes=[];port=8503;base=f'http://127.0.0.1:{port}'
    client=httpx.Client(base_url=base,timeout=5)
    def launch(mode,db):
        log=(folder/(mode+'.log')).open('ab')
        process=subprocess.Popen([sys.executable,__file__,'--serve','--mode',mode,'--db',str(db),'--port',str(port)],
            cwd=ROOT,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        processes.append(process)
        for _ in range(100):
            if process.poll() is not None:raise RuntimeError('Test child failed; inspect isolated log')
            try:
                if client.get('/api/health').status_code==200:return process
            except httpx.HTTPError:pass
            time.sleep(.1)
        raise TimeoutError('Isolated child startup')
    def stop(p):
        p.kill();p.wait(timeout=10)
        time.sleep(.3)
    def submit(cid,q):
        r=client.post(f'/api/conversations/{cid}/turns',json={'question':q,'request_id':str(uuid4())})
        r.raise_for_status();return r.json()
    def wait(cid):
        for _ in range(100):
            rows=client.get(f'/api/conversations/{cid}').json()['turns']
            if rows and rows[-1]['status']!='pending':return rows[-1]
            time.sleep(.1)
        raise TimeoutError('Test child turn')
    try:
        db=folder/f'recovery-{uuid4().hex}.sqlite3'
        p=launch('recovery',db)
        cid=client.post('/api/conversations',json={}).json()['id']
        submit(cid,'Completed before restart');first=wait(cid)
        pending=submit(cid,'[crash] Interrupted before response')
        assert pending['status']=='pending' and pending['running']
        stop(p)
        p=launch('recovery',db)
        rows=client.get(f'/api/conversations/{cid}').json()['turns']
        assert rows[0]['answer']==first['answer'] and rows[0]['citations']==first['citations'] and rows[0]['created']==first['created']
        assert rows[1]['id']==pending['id'] and rows[1]['status']=='pending' and not rows[1]['running']
        assert client.delete(f'/api/turns/{pending["id"]}').status_code==204
        assert len(client.get(f'/api/conversations/{cid}').json()['turns'])==1
        results['checks']['UI11_real_process_crash_restart_preserves_completed_and_pending']=True
        results['checks']['UI11_interrupted_turn_discard_recovery']=True
        submit(cid,'[timeout] Provider timeout');failed=wait(cid)
        assert failed['status']=='failed' and 'SECRET' not in json.dumps(failed)
        results['checks']['UI10_provider_timeout_saved_and_sanitized']=True
        stop(p)
        for mode in ('missing-index','missing-key'):
            p=launch(mode,folder/f'{mode}-{uuid4().hex}.sqlite3')
            assert not client.get('/api/health').json()['ready']
            cid=client.post('/api/conversations',json={}).json()['id']
            submit(cid,'What attendance is required?');failed=wait(cid)
            assert failed['status']=='failed' and failed['answer'] is None
            assert failed['question']=='What attendance is required?'
            results['checks'][('UI17' if mode=='missing-index' else 'UI18')+'_'+mode]=True
            results['details'][mode]=failed['error']
            stop(p)
        class NoEmbeddings:
            def embed_documents(self,texts):raise AssertionError('Unchanged ingestion must not embed')
            def embed_query(self,text):raise AssertionError('Startup must not query embedding API')
        settings=Settings();manifest=settings.data/'manifest.json'
        before=hashlib.sha256(manifest.read_bytes()).hexdigest()
        state=ingest(settings,NoEmbeddings())
        assert state['status']=='unchanged' and before==hashlib.sha256(manifest.read_bytes()).hexdigest()
        results['checks']['UI16_real_index_reused_without_embeddings']=True
        results['details']['manifest_fingerprint']=state['fingerprint']
    finally:
        for p in processes:
            if p.poll() is None:stop(p)
        client.close()
        (folder/'results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(json.dumps(results,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--serve',action='store_true');parser.add_argument('--mode',default='recovery')
    parser.add_argument('--db');parser.add_argument('--port',type=int,default=8503);args=parser.parse_args()
    if args.serve:serve(args.db,args.port,args.mode)
    else:run()
