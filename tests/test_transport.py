"""Transport recovery must not repeat quota calls or create duplicate chat turns."""
import pytest
from google.genai.errors import ServerError, ClientError
from langchain_core.runnables import RunnableLambda
from langchain_google_genai.chat_models import GoogleRateLimitError
from compass.models import transient_chat_retry

def provider_error(code):
    cls=ServerError if code>=500 else ClientError
    return cls(code,{'error':{'code':code,'message':'Synthetic provider failure','status':'INTERNAL'}})

@pytest.mark.parametrize('code',[500,502,503,504])
def test_transient_server_failure_recovers_with_bounded_same_request(code):
    calls=[];events=[]
    def flaky(value):
        calls.append(value)
        if len(calls)<3:raise provider_error(code)
        return 'Recovered'
    wrapped=transient_chat_retry(RunnableLambda(flaky),events,wait=False)
    assert wrapped.invoke('same request')=='Recovered'
    assert calls==['same request']*3
    assert [e['http_code'] for e in events]==[code,code]

def test_persistent_server_failure_stops_after_three_attempts():
    calls=[];events=[]
    def unavailable(value):
        calls.append(value);raise provider_error(503)
    with pytest.raises(ServerError):
        transient_chat_retry(RunnableLambda(unavailable),events,wait=False).invoke('request')
    assert len(calls)==3 and len(events)==3

@pytest.mark.parametrize('code',[400,401,403,404,429,501])
def test_quota_access_bad_request_and_other_codes_are_not_retried(code):
    calls=[];events=[]
    def rejected(value):
        calls.append(value);raise provider_error(code)
    with pytest.raises((ClientError,ServerError)):
        transient_chat_retry(RunnableLambda(rejected),events,wait=False).invoke('request')
    assert len(calls)==1 and events==[]

@pytest.mark.parametrize('exc',[GoogleRateLimitError('429 daily quota'),ValueError('invalid source reference')])
def test_classified_quota_and_validation_errors_are_not_retried(exc):
    calls=[]
    def rejected(value):
        calls.append(value);raise exc
    with pytest.raises(type(exc)):
        transient_chat_retry(RunnableLambda(rejected),wait=False).invoke('request')
    assert len(calls)==1

def test_internal_transport_recovery_saves_one_completed_question(tmp_path,monkeypatch):
    from compass.config import Settings
    from compass.storage import ChatStore
    from compass.rag import RagPipeline,ChatService
    from test_compass import document
    calls=[]
    def flaky(prompt):
        calls.append(prompt)
        if len(calls)<3:raise provider_error(500)
        return 'One campus library is listed [S1].'
    class Store:
        def as_retriever(self,**kwargs):
            return RunnableLambda(lambda q:[document('One campus library is listed.')])
    monkeypatch.setattr('compass.rag.chat_model',lambda settings,transport_events=None:
        transient_chat_retry(RunnableLambda(flaky),transport_events,wait=False))
    settings=Settings(root=tmp_path);db=ChatStore(tmp_path/'chats.sqlite3');cid=db.create()
    pipeline=RagPipeline(settings,Store())
    result=ChatService(settings,db,lambda:pipeline).ask(cid,'How many campus libraries are listed?')
    assert result.status=='completed' and len(calls)==3
    turns=db.turns(cid)
    assert len(turns)==1 and turns[0]['status']=='completed'
    assert len(turns[0]['diagnostics']['transport_failures'])==2
    assert turns[0]['citations'][0]['id']=='S1'
