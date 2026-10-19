import json
from pathlib import Path
import pytest
from compass.policy import align_policy_claims,source_reply
ROWS=json.loads((Path(__file__).parent/'fixtures/repair-scholarship-loan.json').read_text(encoding='utf-8'))['turns']
@pytest.mark.parametrize('row',ROWS)
def test_actual_unrequested_loan_claim_rejected(row):
    with pytest.raises(ValueError,match='loan scheme'):
        align_policy_claims(row['diagnostics']['interpretation']['question'],row['answer'],{})

CORPUS=json.loads((Path(__file__).resolve().parents[1]/'reports/prepared-chunks.json').read_text(encoding='utf-8'))['chunks']
def policy_sources():
    ids=['4def6caa1d1c7b6f5799c251d22609e410454da6b546ea9863ddb97c52fff9c7','e25b53dd5bac0b72c259223c2e7f2412a1415d20f6acf688ff1d8337627cfcfb']
    return {f'S{i+1}':{'excerpt':next(c['text'] for c in CORPUS if c['metadata']['chunk_id']==cid)} for i,cid in enumerate(ids)}
@pytest.mark.parametrize('semester,cumulative,expected',[
    ('3.10','1.99','meets the documented suspension condition'),
    ('3.10','2.00','does not meet that below-threshold suspension condition'),
    ('2.90','2.00','does not meet the merit-scholarship semester-GPA condition'),
    ('3.00','2.01','meets the merit-scholarship semester-GPA condition'),
])
def test_merit_comparisons_use_actual_scholarship_and_warning_sources(semester,cumulative,expected):
    q=f'My semester GPA is{semester} and cumulative GPA is{cumulative}. Must my merit-scholarship continue?'
    text,route=source_reply(q,policy_sources())
    assert expected in text and 'loan' not in text and route=='merit_gpa_conditions'
    assert '[S1]' in text and '[S2]' in text and 'not a verified university record' in text

def test_missing_warning_evidence_does_not_apply_loan_rule():
    text,route=source_reply('My SGPA is3.10 and CGPA is1.99. Must my merit scholarship continue?',{'S1':policy_sources()['S1']})
    assert route=='incomplete_merit_gpa_evidence' and 'cannot confirm continued funding' in text

def test_hyphenated_merit_scholarship_retrieves_warning_rule():
    from compass.rag import linked_retrieval_questions
    assert any('5.4' in q for q in linked_retrieval_questions('My SGPA is3.10 and CGPA is1.99. Must my merit-scholarship continue?'))


def test_merit_shortcut_does_not_swallow_an_explicit_other_subject():
    from compass.policy import merit_gpa_reply
    assert merit_gpa_reply('My SGPA is3.10 and CGPA is1.99. Must my merit scholarship continue, and what is the gym registration fee?',policy_sources()) is None
