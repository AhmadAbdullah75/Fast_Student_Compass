"""Actual missed recall wording and boundaries; no provider calls permitted."""
import pytest
from langchain_core.runnables import RunnableLambda
from compass.conversation import is_history_request
from compass.rag import RagPipeline, ChatService, local_reply
from compass.config import Settings
from compass.storage import ChatStore

@pytest.mark.parametrize('question',[
 'List the questions have I asked in this chat?',
 'Please list the questions have I asked in this chat.',
 'Can you list the questions have I asked in this chat?',
 'List the questions I asked in this chat',
 'List the questions did I ask in this chat?',
 'Show me the questions I have asked in this conversation.',
 'Could you show me the questions have I asked in our conversation?',
 "Please show me the questions I’ve asked in this chat.",
 'Repeat all the questions I asked earlier in this chat.',
 'Which questions have I asked in this conversation?',
 'Enumerate the questions have I asked so far in this chat.',
])
def test_word_order_variants_recall_actual_saved_questions(question):
    turns=[{'question':'How does course withdrawal work?','status':'completed'},
           {'question':'What is the library fine?','status':'completed'}]
    answer=local_reply(question,turns)
    assert answer.diagnostics=={'route':'conversation_history','api_calls':0}
    assert answer.answer.index(turns[0]['question'])<answer.answer.index(turns[1]['question'])
    assert not answer.citations

@pytest.mark.parametrize('question',[
 'What questions can I ask about scholarships?',
 'List the questions on an examination paper.',
 'List the questions I have to answer for admission.',
 'List the questions I asked about scholarship eligibility.',
 'What questions have I asked the Academic Office?',
 'Show me the questions for the final examination.',
 'List the questions have I asked in the admissions interview?',
 'List the questions I asked in this chat and explain the withdrawal deadline.',
 'Which questions are allowed in an AI lab quiz?',
 'List all my course withdrawal requirements.',
 'What is the deadline for rechecking?',
 'What must Ali and Sara repeat?',
])
def test_policy_or_mixed_requests_are_not_swallowed_by_recall(question):
    assert not is_history_request(question)
    assert local_reply(question,[]) is None

def test_actual_pipeline_service_persistence_and_chat_isolation_without_network(tmp_path):
    def forbidden(*args,**kwargs):pytest.fail('Recall must not call a model or retriever')
    class Store:
        def as_retriever(self,**kwargs):return RunnableLambda(forbidden)
    settings=Settings(root=tmp_path)
    def pipeline():return RagPipeline(settings,Store(),RunnableLambda(forbidden))
    database=tmp_path/'test-chats.sqlite3'
    storage=ChatStore(database)
    first=storage.create();second=storage.create()
    for question in ['Four months of gym including registration?', 'One library item twelve days overdue?']:
        tid=storage.begin(first,question)
        storage.finish(tid,'Seeded saved answer',[],'fixture','fixture',0)
    service=ChatService(settings,storage,pipeline)
    missed='List the questions have I asked in this chat?'
    result=service.ask(first,missed)
    assert result.status=='completed' and result.diagnostics['api_calls']==0
    assert '1. Four months' in result.answer and '2. One library item' in result.answer
    assert missed not in result.answer
    restarted=ChatService(settings,ChatStore(database),pipeline)
    again=restarted.ask(first,'List the questions I asked in this chat')
    assert missed in again.answer and again.diagnostics['api_calls']==0
    isolated=restarted.ask(second,missed)
    assert 'not asked any earlier questions' in isolated.answer
    assert len(ChatStore(database).turns(first))==4


def test_missed_word_order_completes_through_real_http_worker_without_model(tmp_path):
    from fastapi.testclient import TestClient
    from compass.web import create_app
    from time import monotonic,sleep
    def forbidden(*args,**kwargs):pytest.fail('HTTP recall must not call model or retriever')
    class Store:
        def as_retriever(self,**kwargs):return RunnableLambda(forbidden)
    class Service(ChatService):
        def __init__(self,settings,storage):
            super().__init__(settings,storage,lambda:RagPipeline(settings,Store(),RunnableLambda(forbidden)))
    storage=ChatStore(tmp_path/'http-chats.sqlite3')
    cid=storage.create()
    tid=storage.begin(cid,'What is the gym registration charge?')
    storage.finish(tid,'Seeded answer',[],'fixture','fixture',0)
    with TestClient(create_app(Settings(root=tmp_path),storage,Service),base_url='http://localhost:8501') as client:
        result=client.post(f'/api/conversations/{cid}/turns',json={'question':'List the questions have I asked in this chat?','request_id':__import__('uuid').uuid4().hex})
        assert result.status_code==202
        deadline=monotonic()+5
        while monotonic()<deadline:
            turn=client.get(f'/api/conversations/{cid}').json()['turns'][-1]
            if turn['status']!='pending':break
            sleep(.01)
        assert turn['status']=='completed'
        assert 'What is the gym registration charge?' in turn['answer']
        assert turn['diagnostics']['api_calls']==0
        assert turn['diagnostics']['route']=='conversation_history'
        assert not turn['citations']
