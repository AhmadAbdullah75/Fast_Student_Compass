import json
from pathlib import Path
from compass.rag import align_explicit_citations, citation_ids
from compass.policy import source_reply

ROWS=json.loads((Path(__file__).parent/'fixtures/release-formula-fyp-20261018.json').read_text(encoding='utf-8'))['results']
def sources(row):
 return {sid:{'chunk_id':cid,'excerpt':next(d['passage'] for d in row['trace']['retrieved'] if d['chunk_id']==cid),'references':next(d['references'] for d in row['trace']['retrieved'] if d['chunk_id']==cid)} for sid,cid in row['trace']['packed_source_ids'].items()}

def test_recorded_formula_does_not_cite_rechecking_paragraph():
 row=ROWS[0];text=align_explicit_citations(row['answer'],sources(row))
 assert 'S5' not in citation_ids(text)
 assert 'S1' in citation_ids(text) and 'S3' in citation_ids(text)
 assert 'most recent grade points' in text

def test_broad_fyp_requirements_include_actual_normal_rules():
 row=ROWS[1];text,route=source_reply(row['question'],sources(row))
 assert 'passed all courses' in text and 'study' in text
 assert 'second last' in text and 'subsequent semester' in text
 assert 'zero' in text and 'one course' in text and 'two courses' in text
 assert len(citation_ids(text))>=2

def test_formula_filter_does_not_rewrite_a_different_formula():
 row=ROWS[0];text='SGPA = (P1+C1)/C [S5].'
 assert align_explicit_citations(text,sources(row))==text

def test_formula_filter_does_not_claim_to_validate_arbitrary_numeric_answers():
 row=ROWS[0];text='My calculated SGPA is3.25 [S5].'
 assert align_explicit_citations(text,sources(row))==text

def test_narrow_fyp_permission_keeps_its_scope():
 row=ROWS[1];text,route=source_reply('With zero warnings and one course deficiency, who can allow my FYP-I registration?',sources(row))
 assert 'one course' in text and 'zero' in text
 assert 'normal_registration' not in route
