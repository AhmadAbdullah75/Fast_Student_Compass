import json
from pathlib import Path
import re
from compass.rag import complete_condition_coverage
from compass.rag import linked_retrieval_questions
from compass.policy import source_reply

ROW=json.loads((Path(__file__).parent/'fixtures/repair-fyp-warning.json').read_text(encoding='utf-8'))['turn']

def test_actual_fyp_deficiency_answer_preserves_zero_warning_condition():
    sources={s['id']:{k:v for k,v in s.items() if k!='id'} for s in ROW['citations']}
    result=complete_condition_coverage(ROW['question'],ROW['answer'],sources)
    assert re.search(r'warning count must be zero',result.answer,re.I)

def test_nonzero_warning_does_not_gain_a_deficiency_waiver():
    sources={s['id']:{k:v for k,v in s.items() if k!='id'} for s in ROW['citations']}
    text,route=source_reply('May FYP-I begin despite a nonzero warning count just because only one course is missing?',sources)
    assert route=='fyp_deficiency_conditions'
    assert 'do not establish permission to waive' in text
    assert 'warning count must be zero' in text
    assert 'Head of department can allow' in text
    assert 'Director of the campus can allow' in text

def test_missing_zero_warning_evidence_does_not_authorize_registration():
    sources={'S1':{'excerpt':'4.13 The Head of department can allow registration in FYP-I where there is a deficiency of one course.'}}
    text,route=source_reply(ROW['question'],sources)
    assert route=='required_fyp_rule_missing'
    assert text=='I could not find this information in the provided documents.'

def test_deficiency_warning_permission_identifies_fyp_scope():
    question='Does Campus Director permission for two deficient courses itself establish a warning-count waiver?'
    assert any('FYP-I' in query for query in linked_retrieval_questions(question))
    sources={s['id']:{k:v for k,v in s.items() if k!='id'} for s in ROW['citations']}
    text,route=source_reply(question,sources)
    assert route=='fyp_deficiency_conditions' and 'FYP-I' in text
