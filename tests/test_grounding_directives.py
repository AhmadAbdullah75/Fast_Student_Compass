import json
from pathlib import Path
import pytest
from compass.rag import local_reply
CASES=json.loads((Path(__file__).resolve().parents[1]/'evaluation/repair-20261017/grounding-directive-holdout12.json').read_text(encoding='utf-8'))['cases']
@pytest.mark.parametrize('case',CASES,ids=[c['id'] for c in CASES])
def test_instruction_without_policy_subject_does_not_retrieve(case):
    result=local_reply(case['question'],[])
    assert result is not None
    assert result.diagnostics['route']=='grounding_boundary'
    assert result.diagnostics['api_calls']==0 and result.citations==[]
@pytest.mark.parametrize('q',['What are the graduation requirements?','Quote the evidence for the gym registration fee.','Does the handbook require a definite answer from students?'])
def test_actual_policy_questions_still_retrieve(q):
    assert local_reply(q,[]) is None
