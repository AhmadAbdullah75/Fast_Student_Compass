import json
from pathlib import Path
from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda
from compass.config import Settings
from compass.rag import RagPipeline,complete_condition_coverage,linked_retrieval_questions,ABSTAIN
from compass.policy import source_reply
ROOT=Path(__file__).resolve().parents[1]
ROW=json.loads((ROOT/'tests/fixtures/release-ai-undergraduate-grading-20261018.json').read_text(encoding='utf-8'))['turn']
CORPUS=json.loads((ROOT/'reports/prepared-chunks.json').read_text(encoding='utf-8'))['chunks']
REF=next(c for c in CORPUS if any(r['id']=='academic' and r['pdf_page']==52 for r in json.loads(c['metadata']['references'])))
def sources(row):
 return {sid:{'chunk_id':cid,'excerpt':next(d['passage'] for d in row['diagnostics']['retrieved'] if d['chunk_id']==cid),'references':next(d['references'] for d in row['diagnostics']['retrieved'] if d['chunk_id']==cid)} for sid,cid in row['diagnostics']['packed_source_ids'].items()}
def test_undergraduate_does_not_mean_grading_intent():
 result=complete_condition_coverage(ROW['diagnostics']['search_question'],ROW['diagnostics']['raw_answer'],sources(ROW))
 assert 'grading distribution' not in result.answer

def test_citation_query_links_reference_policy_not_only_prompt_continuation():
 queries=linked_retrieval_questions(ROW['diagnostics']['search_question'])
 assert any('assignment brief' in q and 'Referencing Generative AI' in q for q in queries)

def test_prep_reference_rule_requires_actual_exemption_evidence():
 text,route=source_reply(ROW['question'],sources(ROW))
 assert text==ABSTAIN and route=='required_ai_reference_rule_missing'

def test_actual_full_reference_rule_preserves_its_brief_exception():
 s={'S1':{'excerpt':REF['text'],'references':json.loads(REF['metadata']['references']),'chunk_id':REF['metadata']['chunk_id']}}
 text,route=source_reply(ROW['question'],s)
 assert route=='ai_preparation_reference_rule'
 assert 'does not require citation' in text and 'assignment brief specifically states otherwise' in text

def test_fixed_reference_link_packs_missing_policy_within_six_chunks(tmp_path):
 bad=[Document(page_content=d['passage'],metadata={'chunk_id':d['chunk_id'],'references':json.dumps(d['references'])}) for d in ROW['diagnostics']['retrieved']]
 reference=Document(page_content=REF['text'],metadata=REF['metadata'])
 class Store:
  def as_retriever(self,**kw):
   return RunnableLambda(lambda q:[reference] if 'Referencing Generative AI' in q else bad)
 def forbidden(*a,**kw):raise AssertionError('Narrow source-backed reference answer needs no generation call')
 p=RagPipeline(Settings(root=tmp_path),Store(),RunnableLambda(forbidden));result=p.answer(ROW['diagnostics']['search_question'],[])
 assert 'assignment brief specifically states otherwise' in result.answer
 assert any(any(r['pdf_page']==52 for r in c['references']) for c in result.citations)
 assert len(result.diagnostics['retrieved'])<=6


def test_explicit_negative_incorporation_preserves_preparation_only_scope():
 s={'S1':{'excerpt':REF['text'],'references':json.loads(REF['metadata']['references']),'chunk_id':REF['metadata']['chunk_id']}}
 text,route=source_reply('I use AI solely for preparation, not incorporated submitted content. Does citation always become compulsory if the brief says nothing?',s)
 assert route=='ai_preparation_reference_rule' and 'assignment brief' in text

def test_positive_incorporated_subquestion_is_not_removed_by_preparation_shortcut():
 from compass.policy import ai_preparation_only
 assert not ai_preparation_only('Compare AI solely for preparation with an embedded AI image in my submitted work.')
