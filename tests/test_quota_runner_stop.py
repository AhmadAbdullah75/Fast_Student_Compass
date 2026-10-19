import json
from pathlib import Path
import pytest
import compass.benchmark as benchmark
from compass.config import Settings
@pytest.mark.parametrize('message',['429 rate limit PerMinute','429 quota PerDay'])
def test_benchmark_stops_all_further_requests_on_any_quota(tmp_path,monkeypatch,message):
 suite=tmp_path/'cases.json';suite.write_text(json.dumps({'cases':[{'id':i,'question':i,'difficulty':'simple','expected_behavior':'answer','expected_answer':'fixture','source_reviewed_by':'fixture'} for i in ['one','two']]}))
 calls=[]
 class Pipeline:
  last_raw_answer=''
  def __init__(self,*a,**kw):pass
  def answer(self,q,history):calls.append(q);raise Exception(message)
  def diagnostics(self,*a):return {}
 monkeypatch.setattr(benchmark,'RagPipeline',Pipeline)
 monkeypatch.setattr(benchmark,'open_index',lambda s:(None,{'fingerprint':'fixture'}))
 monkeypatch.setattr(benchmark,'sleep',lambda _:None)
 benchmark.run(Settings(root=tmp_path),'fixture',suite=suite,interval=12)
 assert calls==['one']


def test_http_conversation_runner_stops_next_sequence_on_minute_quota(tmp_path,monkeypatch):
 import time
 from tools import publication_workflows as harness
 calls=[]
 class Pipeline:
  manifest={'dataset_version':'fixture','fingerprint':'fixture'}
  def __init__(self,*a,**kw):pass
  def answer(self,q,history):calls.append(q);raise Exception('429 rate limit PerMinute')
 monkeypatch.setattr(harness,'ROOT',tmp_path)
 monkeypatch.setattr(harness,'Settings',lambda:Settings(root=tmp_path))
 monkeypatch.setattr(harness,'RagPipeline',Pipeline)
 monkeypatch.setattr(harness,'SEQUENCES',{'F01':['first'],'F02':['must not send']})
 monkeypatch.setattr(harness,'sleep',lambda value:time.sleep(min(value,0.001)))
 harness.run('fixture',{'F01','F02'},interval=10)
 assert calls==['first']
 r=json.loads((tmp_path/'reports/publication/fixture/workflows.json').read_text())
 assert len(r['results'])==1 and r['results'][0]['execution_status']=='FAILED_TURN'
