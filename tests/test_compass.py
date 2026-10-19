import json
from types import SimpleNamespace
import pytest
from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda
from compass.config import Settings
from compass.storage import ChatStore
from compass.rag import ChatService, RagPipeline, Answer, ABSTAIN, history_text, pack_evidence, validate_answer
from compass.models import GeminiEmbeddings
from compass.ingestion import CachedEmbeddings, tokens

@pytest.fixture
def storage(tmp_path):
    return ChatStore(tmp_path/'chats.sqlite3')

def test_persistence_isolation_and_cascade(storage):
    first, second = storage.create(),storage.create()
    tid = storage.begin(first,'A first question')
    storage.finish(tid,'Answer',[{'id':'S1'}],'test','v1',.1)
    reopened = ChatStore(storage.path)
    assert reopened.turns(first)[0]['citations']==[{'id':'S1'}]
    assert reopened.turns(second)==[]
    reopened.rename(first,'Renamed')
    assert any(c['title']=='Renamed' for c in reopened.list())
    reopened.delete(first)
    assert reopened.turns(first)==[]

@pytest.mark.parametrize('backward_clock',[False,True])
def test_transcript_preserves_insertion_order_with_tied_or_backward_timestamps(storage,monkeypatch,backward_clock):
    import compass.storage as module
    cid=storage.create('ordered-chat')
    ids=iter(['z-last-uuid','m-middle-uuid','a-first-uuid'])
    monkeypatch.setattr(module,'uuid4',lambda:SimpleNamespace(hex=next(ids)))
    for i in range(3):
        stamp=f'2026-10-{16-i if backward_clock else 16:02}T12:00:00+00:00'
        monkeypatch.setattr(module,'now',lambda value=stamp:value)
        tid=storage.begin(cid,f'Question {i}')
        storage.finish(tid,f'Answer {i}',[],'fixture','fixture',0)
    reopened=ChatStore(storage.path)
    assert [t['question'] for t in reopened.turns(cid)]==['Question 0','Question 1','Question 2']
    from compass.rag import local_reply
    recalled=local_reply('What questions have I asked?',reopened.turns(cid)).answer
    assert recalled.index('Question 0')<recalled.index('Question 1')<recalled.index('Question 2')


def test_failure_retry_no_duplicate_and_redaction(storage,tmp_path):
    class Fake:
        manifest = {'dataset_version':'v1','fingerprint':'123'}
        def answer(self, question, turns):
            return Answer('Supported [S1]',[{'id':'S1'}])
    cid = storage.create()
    def fail():
        raise RuntimeError('429 quota key=SECRET')
    service = ChatService(Settings(root=tmp_path),storage,fail)
    result = service.ask(cid,'Question')
    assert result.status=='failed' and 'SECRET' not in result.answer
    with pytest.raises(ValueError):
        service.ask(cid,'Duplicate')
    service.pipeline_factory = Fake
    assert service.retry(result.turn_id).status=='completed'
    assert len(storage.turns(cid))==1
    service.retry(result.turn_id)
    assert len(storage.turns(cid))==1

def test_interrupted_turn_survives_restart(storage,tmp_path):
    cid = storage.create()
    tid = storage.begin(cid,'Interrupted')
    reopened = ChatStore(storage.path)
    assert reopened.get_turn(tid)['status']=='pending'
    reopened.retry(tid)
    assert len(reopened.turns(cid))==1
    reopened.discard(tid)
    assert reopened.turns(cid)==[]

def test_history_window():
    turns = [{'question':f'q{i}','answer':f'a{i}','status':'completed'} for i in range(10)]
    text = history_text(turns)
    assert 'q3' not in text and 'q4' in text and 'q9' in text
    assert tokens(history_text(turns,20))<=20

def document(text='University policy text'):
    return Document(page_content=text,metadata={'chunk_id':'abc','references':json.dumps([
        {'title':'Handbook','pdf_page':2,'section':'Rules','printed_label':'1'}])})

def test_citations_and_budget():
    evidence,sources = pack_evidence([document()])
    assert 'S1' in evidence
    assert validate_answer('A rule [S1]',sources).citations[0]['references'][0]['pdf_page']==2
    with pytest.raises(ValueError):
        validate_answer('Invented [S99]',sources)
    with pytest.raises(ValueError,match='could not be validated'):
        validate_answer('An uncited rule',sources)
    assert validate_answer(ABSTAIN,sources).answer==ABSTAIN
    assert pack_evidence([document()],1)==('',{})

def test_lcel_followup_and_scope_filter(tmp_path):
    requests,searches = [],[]
    def model(prompt, **kwargs):
        messages = prompt.to_messages()
        requests.append(messages)
        if 'Rewrite' in messages[0].content:
            return json.dumps({'question':'Scholarship consequences of course withdrawal','unresolved':False})
        return 'The document says this [S1]'
    class Store:
        def as_retriever(self,**kwargs):
            assert kwargs['search_type']=='similarity'
            assert kwargs['search_kwargs']['filter']['$and'][0]['campus']['$in']==['all','CFD']
            return RunnableLambda(lambda q: searches.append(q) or [document()])
    pipeline = RagPipeline(Settings(root=tmp_path),Store(),RunnableLambda(model))
    assert pipeline.answer('Withdrawal?',[]).citations
    assert len(requests)==1
    pipeline.answer('What about scholarships?',[{'question':'Withdrawal?','answer':'Earlier answer','status':'completed'}])
    assert searches[-1]=='Scholarship consequences of course withdrawal'
    assert len(requests)==3

def test_embedding_separate_calls_and_cache(tmp_path):
    calls=[]
    class Models:
        def embed_content(self,**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(embeddings=[SimpleNamespace(values=[3.,4.])])
    settings=Settings(root=tmp_path,dimensions=2)
    embedding=GeminiEmbeddings(settings,SimpleNamespace(models=Models()))
    cached=CachedEmbeddings(settings,embedding)
    assert cached.embed_documents(['first','second'])==[[.6,.8],[.6,.8]]
    cached.embed_documents(['first','second'])
    assert len(calls)==2
    embedding.embed_query('question')
    assert len(calls)==3
    assert calls[-1]['contents'].startswith('task: question answering')
    assert all(isinstance(c['contents'],str) for c in calls)

def test_grouped_and_lowercase_citations():
    _,sources=pack_evidence([document(),document('Another policy')])
    answer=validate_answer('A supported statement [s1, S2].',sources)
    assert '[S1] [S2]' in answer.answer
    assert {c['id'] for c in answer.citations}=={'S1','S2'}
    with pytest.raises(ValueError,match='invalid source'):
        validate_answer('A statement [S1, S999]',sources)

def test_first_semester_is_not_first_year():
    _,sources=pack_evidence([document('Students in their first semester need approval.')])
    with pytest.raises(ValueError,match='first-semester'):
        validate_answer('First-year students need approval [S1].',sources)
    assert validate_answer('First-semester students need approval [S1].',sources).citations

def test_meta_chat_and_greeting_need_no_model(tmp_path):
    from compass.rag import local_reply
    assert local_reply('hello what can you do',[]).diagnostics['api_calls']==0
    turns=[{'question':'What is attendance?','status':'completed'}, {'question':'Failed question','status':'failed'}]
    reply=local_reply('what questions i have asked',turns)
    assert 'What is attendance?' in reply.answer and 'Failed question' not in reply.answer
    assert 'not find' not in reply.answer
    assert local_reply('What conditions apply to a scholarship?',turns) is None

def test_long_previous_answer_does_not_erase_question():
    history=history_text([{'question':'Can I graduate in three years?', 'answer':'Long answer '*1500,'status':'completed'}],100)
    assert 'Can I graduate in three years?' in history
    assert tokens(history)<=100

def test_retrieval_trace_persists(storage,tmp_path):
    cid=storage.create(); tid=storage.begin(cid,'A question')
    storage.finish(tid,'Answer',[],'test','v1',.1,{'search_question':'Standalone question'})
    assert ChatStore(storage.path).turns(cid)[0]['diagnostics']['search_question']=='Standalone question'

def test_calendar_query_does_not_infer_permission():
    from compass.rag import calendar_reply
    _,sources=pack_evidence([document('4.25 The deadline to withdraw from a course is the last day of the makeup week of every semester.')])
    result=calendar_reply('Can I withdraw one day before midterm 1?',sources)
    assert 'cannot confirm' in result.answer and result.citations
    assert not result.answer.startswith(('Yes','No,'))
    assert calendar_reply('What is the minimum degree duration?',sources) is None

def test_schema_upgrade_preserves_old_messages(storage):
    cid=storage.create(); tid=storage.begin(cid,'Existing question')
    storage.finish(tid,'Old answer',[],'old-model','old-dataset',1.0)
    with storage.connect() as db:
        db.execute('ALTER TABLE turns DROP COLUMN diagnostics')
    migrated=ChatStore(storage.path)
    assert migrated.turns(cid)[0]['answer']=='Old answer'
    assert migrated.turns(cid)[0]['diagnostics']=={}

def test_followup_service_uses_only_current_chat_and_saves_failures(storage,tmp_path):
    first,second=storage.create(),storage.create()
    tid=storage.begin(first,'Private question in first chat')
    storage.finish(tid,'Previous answer',[],'test','v1',.1)
    requests=[]
    class Store:
        def as_retriever(self,**kwargs): return RunnableLambda(lambda q:[document()])
    def invalid(prompt):
        requests.append(prompt.to_messages()[-1].content)
        return 'Unsupported source [S999]'
    pipeline=RagPipeline(Settings(root=tmp_path),Store(),RunnableLambda(invalid))
    service=ChatService(Settings(root=tmp_path),storage,lambda:pipeline)
    result=service.ask(second,'New question in a separate chat')
    assert result.status=='failed'
    assert all('Private question' not in r for r in requests)
    saved=storage.turns(second)[0]
    assert saved['diagnostics']['retrieved']
    assert saved['diagnostics']['raw_answer']=='Unsupported source [S999]'
