import json
from pathlib import Path
import pytest
from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda
from compass.config import Settings
from compass.rag import RagPipeline, unsupported_request, linked_retrieval_questions

ROOT=Path(__file__).resolve().parents[1]
ROWS=json.loads((ROOT/'tests/fixtures/release-live-email-20261018.json').read_text(encoding='utf-8'))['results']
CORPUS=json.loads((ROOT/'reports/prepared-chunks.json').read_text(encoding='utf-8'))['chunks']

@pytest.mark.parametrize('i',[0,1])
def test_printed_email_subquestion_is_not_discarded(i):
 assert not unsupported_request(ROWS[i]['question'])

@pytest.mark.parametrize('i,mailbox',[(0,'girlshostel'),(1,'hostelsupervisor')])
def test_requested_gender_contact_has_fixed_link_before_generation(i,mailbox):
 assert any(mailbox in q for q in linked_retrieval_questions(ROWS[i]['question']))

@pytest.mark.parametrize('i,mailbox,extension',[(0,'girlshostel','399'),(1,'hostelsupervisor','382')])
def test_actual_static_passages_answer_contact_without_live_inventory(i,mailbox,extension,tmp_path):
 docs=[Document(page_content=c['text'],metadata=c['metadata']) for c in CORPUS if
       'cfd.girlshostel@nu.edu.pk' in c['text'] or 'As per policy, single-' in c['text']]
 class Store:
  def as_retriever(self,**kwargs):return RunnableLambda(lambda q:docs)
 def forbidden(_):raise AssertionError('Static printed contact and inventory boundary use actual retrieved text')
 a=RagPipeline(Settings(root=tmp_path),Store(),RunnableLambda(forbidden)).answer(ROWS[i]['question'],[])
 assert 'cannot confirm live room availability' in a.answer
 assert f'cfd.{mailbox}@nu.edu.pk' in a.answer and extension in a.answer
 assert a.citations and 'not available to you' not in a.answer

def test_separate_sentence_printed_contact_is_supported():
 assert not unsupported_request('Is a room vacant today? Give the printed girls hostel email.')

def test_both_hostel_contact_queries_are_preserved():
 qs=linked_retrieval_questions('Is a room available today and give printed girls and boys hostel emails.')
 assert any('girlshostel' in q for q in qs) and any('hostelsupervisor' in q for q in qs)

def test_both_actual_hostel_contacts_are_answered(tmp_path):
 docs=[Document(page_content=c['text'],metadata=c['metadata']) for c in CORPUS if
       'cfd.girlshostel@nu.edu.pk' in c['text'] or 'As per policy, single-' in c['text']]
 class Store:
  def as_retriever(self,**kwargs):return RunnableLambda(lambda q:docs)
 def forbidden(_):raise AssertionError('Actual printed contacts should suffice')
 a=RagPipeline(Settings(root=tmp_path),Store(),RunnableLambda(forbidden)).answer('Is a room available today and give printed girls and boys hostel emails and extensions.',[])
 assert 'cfd.girlshostel@nu.edu.pk' in a.answer and '399' in a.answer
 assert 'cfd.hostelsupervisor@nu.edu.pk' in a.answer and '382' in a.answer
 assert 'cannot confirm live room availability' in a.answer
