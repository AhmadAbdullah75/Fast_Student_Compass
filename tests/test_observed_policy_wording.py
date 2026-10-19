import json
from pathlib import Path
import pytest
from compass.policy import preserve_policy_language,source_reply
ROWS=json.loads((Path(__file__).parent/'fixtures/repair-policy-wording.json').read_text(encoding='utf-8'))['turns']
def sources(row):return {c['id']:{k:v for k,v in c.items() if k!='id'} for c in row['citations']}
def test_recorded_refund_converse_is_not_justified_by_cited_if_clause():
    with pytest.raises(ValueError,match='exclusive'):
        preserve_policy_language(ROWS[0]['answer'],sources(ROWS[0]))
def test_recorded_application_modality_keeps_should():
    text=preserve_policy_language(ROWS[1]['answer'],sources(ROWS[1]))
    assert 'must apply' not in text and 'should apply' in text
@pytest.mark.parametrize('row',ROWS)
def test_recorded_questions_get_literal_source_reply(row):
    text,route=source_reply(row['question'],sources(row))
    assert route in ['rechecking_refund_wording','aid_application_wording']
    assert 'must apply' not in text


def test_supported_contrast_is_not_changed_into_self_contradiction():
    text='The Financial Aid form wording says should apply, not must apply [S1].'
    assert preserve_policy_language(text,sources(ROWS[1]))==text

def test_explicitly_uncertain_refund_statement_is_not_rejected():
    text='The rechecking clause does not state that the fee is not refunded when marks remain unchanged [S1].'
    assert preserve_policy_language(text,sources(ROWS[0]))==text

def test_wording_shortcut_does_not_omit_another_requested_subject():
    from compass.policy import policy_wording_reply
    assert policy_wording_reply('Explain the rechecking refund clause and gym registration fee.',sources(ROWS[0])) is None
    assert policy_wording_reply('Give rechecking steps and the form deadline, including refunds.',sources(ROWS[0])) is None


def test_aid_wording_shortcut_does_not_replace_general_eligibility_question():
    from compass.policy import policy_wording_reply
    assert policy_wording_reply('What CGPA is needed to be eligible for financial assistance?',sources(ROWS[1])) is None
