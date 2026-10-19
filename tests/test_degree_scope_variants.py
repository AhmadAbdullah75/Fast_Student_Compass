import json
from pathlib import Path
import pytest
from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda
from compass.config import Settings
from compass.policy import mixed_degree, undergraduate_part, requested_facets, SCOPE_NOTE
from compass.rag import RagPipeline, ABSTAIN

ROOT=Path(__file__).resolve().parents[1]
ROWS=json.loads((ROOT/'tests/fixtures/release-degree-scope-20261018.json').read_text(encoding='utf-8'))['results']
CORPUS=json.loads((ROOT/'reports/prepared-chunks.json').read_text(encoding='utf-8'))['chunks']

class Store:
 def as_retriever(self,**kwargs):
  docs=[Document(page_content=c['text'],metadata=c['metadata']) for c in CORPUS if
        'Bachelors: 8 semesters' in c['text'] or 'cfd.fa@nu.edu.pk' in c['text']]
  return RunnableLambda(lambda q:docs)

@pytest.mark.parametrize('i',[0,1,3])
def test_pure_postgraduate_variant_explains_coverage(tmp_path,i):
 p=RagPipeline(Settings(root=tmp_path),Store(),RunnableLambda(lambda _:ABSTAIN))
 a=p.answer(ROWS[i]['question'],[])
 assert SCOPE_NOTE in a.answer
 assert '8 semesters' not in a.answer

def test_do_not_substitute_undergraduate_is_not_a_positive_undergraduate_request():
 assert not mixed_degree(ROWS[0]['question'])

def test_mixed_doctoral_contact_preserves_requested_contact_facet():
 assert mixed_degree(ROWS[5]['question'])
 q=undergraduate_part(ROWS[5]['question'])
 assert 'financial_contact' in requested_facets(q)
 assert 'doctoral' not in q.lower()

def test_mixed_comparison_does_not_become_self_comparison():
 assert 'with undergraduate sponsorship' not in undergraduate_part(ROWS[2]['question'])

def test_mixed_sponsorship_quotes_supported_portion_even_if_generator_abstains(tmp_path):
 p=RagPipeline(Settings(root=tmp_path),Store(),RunnableLambda(lambda _:ABSTAIN))
 a=p.answer(ROWS[2]['question'],[])
 assert '8 semesters' in a.answer and 'tuition' in a.answer
 assert SCOPE_NOTE in a.answer and a.citations

def test_mixed_contact_answers_contact_and_declines_doctoral_inference(tmp_path):
 p=RagPipeline(Settings(root=tmp_path),Store(),RunnableLambda(lambda _:ABSTAIN))
 a=p.answer(ROWS[5]['question'],[])
 assert 'Nooria' in a.answer and 'cfd.fa@nu.edu.pk' in a.answer
 assert SCOPE_NOTE in a.answer and a.citations

@pytest.mark.parametrize('q',['Who manages MS Office licenses?', 'Who is Ms. Nooria Fatima?', 'I want to graduate with CGPA2.00.'])
def test_non_degree_uses_do_not_become_postgraduate_scope(tmp_path,q):
 p=RagPipeline(Settings(root=tmp_path),Store(),RunnableLambda(lambda _:ABSTAIN))
 assert SCOPE_NOTE not in p.answer(q,[]).answer

def test_mixed_scope_keeps_multiple_supported_clauses():
 q=undergraduate_part('Give undergraduate gym charges and library borrowing limits and infer doctoral sponsorship.')
 assert 'gym charges' in q and 'library borrowing' in q and 'doctoral' not in q

def test_postgraduate_clause_first_keeps_supported_second_clause():
 q=undergraduate_part('Give doctoral sponsorship and undergraduate library limits.')
 assert 'undergraduate library' in q and 'doctoral' not in q

def test_partial_sponsorship_does_not_invent_missing_rule(tmp_path):
 class Empty:
  def as_retriever(self,**kwargs):return RunnableLambda(lambda q:[])
 a=RagPipeline(Settings(root=tmp_path),Empty(),RunnableLambda(lambda _:ABSTAIN)).answer(ROWS[2]['question'],[])
 assert '8 semesters' not in a.answer and not a.citations and SCOPE_NOTE in a.answer

def test_shared_sponsorship_predicate_survives_degree_reduction():
 q=undergraduate_part('Do bachelor and Master’s internal sponsorships both have the same documented maximum?')
 assert 'internal sponsorships' in q

def test_compact_cgpa_gets_supported_graduation_comparison(tmp_path):
 row=json.loads((ROOT/'tests/fixtures/release-scope-holdout-20261018.json').read_text(encoding='utf-8'))['results'][6]
 docs=[Document(page_content=d['passage'],metadata={'chunk_id':d['chunk_id'],'references':json.dumps(d['references'])}) for d in row['trace']['retrieved']]
 class Recorded:
  def as_retriever(self,**kwargs):return RunnableLambda(lambda q:docs)
 def forbidden(_):raise AssertionError('Actual graduation clause should answer this narrow supplied-CGPA question')
 a=RagPipeline(Settings(root=tmp_path),Recorded(),RunnableLambda(forbidden)).answer(row['question'],[])
 assert '1.99 is below 2.00' in a.answer and a.citations
