"""Local HTTP adapter around the existing saved-turn / RAG service.

Run one process on loopback. SQLite owns durability; the worker owns only live
execution. A server restart leaves interrupted questions available for retry.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
import json
from pathlib import Path
from threading import RLock
from uuid import UUID
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field
from .config import Settings
from .storage import ChatStore
from .rag import ChatService

class Question(BaseModel):
    question: str = Field(min_length=1,max_length=6000)
    request_id: UUID

class Rename(BaseModel):
    title: str = Field(min_length=1,max_length=100)

class CreateChat(BaseModel):
    id: UUID | None = None

def create_app(settings=None, storage=None, service_factory=None):
    settings=settings or Settings()
    storage=storage or ChatStore(settings.data/'chats.sqlite3')
    service=(service_factory or ChatService)(settings,storage)
    lock=RLock()
    active=set()
    executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='compass-answer')

    @asynccontextmanager
    async def lifespan(app):
        yield
        executor.shutdown(wait=True)

    app=FastAPI(title='CFD Student Compass',lifespan=lifespan,docs_url='/api/docs',openapi_url='/api/openapi.json')
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=['localhost','127.0.0.1'])
    app.state.storage=storage

    @app.middleware('http')
    async def local_only(request:Request,call_next):
        # Same-origin browser mutations only; no wildcard CORS or public bind.
        origin=request.headers.get('origin')
        if request.method not in ('GET','HEAD','OPTIONS') and origin:
            allowed={f'http://{host}:{port}' for host in ('localhost','127.0.0.1') for port in (8501,5173)}
            if request.url.hostname in ('localhost','127.0.0.1'):
                allowed.add(str(request.base_url).rstrip('/'))
            if origin not in allowed:
                return JSONResponse({'detail':'This local workspace accepts same-origin requests only.'},status_code=403)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='no-referrer'
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control']='no-store'
        return response

    def require_chat(cid):
        with storage.connect() as db:
            row=db.execute('SELECT * FROM conversations WHERE id=?',(cid,)).fetchone()
        if row is None:raise HTTPException(404,'Conversation no longer exists.')
        return dict(row)

    def turn(tid):
        try:row=storage.get_turn(tid)
        except ValueError:raise HTTPException(404,'Question no longer exists.')
        row['citations']=json.loads(row['citations'])
        row['diagnostics']=json.loads(row['diagnostics'])
        with lock:row['running']=tid in active
        return row

    def run(tid):
        try:
            service._run(tid)
        except Exception:
            # Never expose SDK exceptions, keys, or request internals.
            storage.fail(tid,'The request was interrupted. Your question is saved; please retry.')
        finally:
            with lock:active.discard(tid)

    def enqueue(tid):
        with lock:
            if tid in active:return
            active.add(tid)
            try:executor.submit(run,tid)
            except Exception:
                active.discard(tid)
                storage.fail(tid,'The worker could not start. Your question is saved; please retry.')

    @app.get('/api/health')
    def health():
        manifest=settings.data/'manifest.json'
        version=None
        if manifest.exists():
            try:version=json.loads(manifest.read_text(encoding='utf-8')).get('dataset_version')
            except (ValueError,OSError):pass
        try:settings.require_key();key=True
        except ValueError:key=False
        return {'status':'ok','ready':bool(key and version),'dataset_version':version,'chat_model':settings.chat_model}

    @app.get('/api/conversations')
    def list_chats():return storage.list()

    @app.post('/api/conversations',status_code=201)
    def create_chat(body:CreateChat=CreateChat()):
        cid=storage.create(body.id.hex if body.id else None)
        return require_chat(cid)

    @app.get('/api/conversations/{cid}')
    def load_chat(cid:str):
        chat=require_chat(cid)
        chat['turns']=[turn(t['id']) for t in storage.turns(cid)]
        return chat

    @app.patch('/api/conversations/{cid}')
    def rename_chat(cid:str,body:Rename):
        with lock:
            require_chat(cid)
            if not body.title.strip():raise HTTPException(422,'Enter a chat title.')
            storage.rename(cid,body.title)
            return require_chat(cid)

    @app.delete('/api/conversations/{cid}',status_code=204)
    def delete_chat(cid:str):
        with lock:
            require_chat(cid)
            if any(t['id'] in active for t in storage.turns(cid)):
                raise HTTPException(409,'Wait for this conversation’s answer to finish before deleting it.')
            storage.delete(cid)

    @app.post('/api/conversations/{cid}/turns',status_code=202)
    def submit(cid:str,body:Question):
        with lock:
            require_chat(cid)
            if not body.question.strip():raise HTTPException(422,'Enter a question.')
            try:tid=storage.begin(cid,body.question,str(body.request_id))
            except ValueError as exc:raise HTTPException(409,str(exc))
            row=turn(tid)
            # An idempotent replay of a failed turn must not spend quota again.
            if row['status']=='pending':enqueue(tid)
            return turn(tid)

    @app.post('/api/turns/{tid}/retry',status_code=202)
    def retry(tid:str):
        with lock:
            row=turn(tid)
            if row['status']!='completed' and tid not in active:
                storage.retry(tid)
                enqueue(tid)
            return turn(tid)

    @app.delete('/api/turns/{tid}',status_code=204)
    def discard(tid:str):
        with lock:
            row=turn(tid)
            if tid in active:raise HTTPException(409,'An answer is still being generated.')
            if row['status']=='completed':raise HTTPException(409,'Completed messages cannot be discarded individually.')
            storage.discard(tid)

    assets=settings.root/'frontend/dist'
    if assets.exists():
        app.mount('/assets',StaticFiles(directory=assets/'assets'),name='assets')

    @app.get('/')
    def index():
        if not (assets/'index.html').exists():
            raise HTTPException(503,'Build the React frontend first: cd frontend; npm install; npm run build')
        return FileResponse(assets/'index.html',headers={'Cache-Control':'no-cache'})

    return app

app=create_app()
