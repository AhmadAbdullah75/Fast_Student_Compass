import json
from pathlib import Path
import pytest
from compass.policy import preserve_policy_language,source_reply
ROW=json.loads((Path(__file__).parent/'fixtures/repair-warning-citation.json').read_text(encoding='utf-8'))['turn']
D=ROW['diagnostics'];DOCS={x['chunk_id']:x for x in D['retrieved']}
ALL={sid:{'chunk_id':cid,'excerpt':DOCS[cid]['passage'],'references':DOCS[cid]['references']} for sid,cid in D['packed_source_ids'].items()}
def test_actual_wrong_warning_citation_is_blocked():
    with pytest.raises(ValueError,match='approval rule'):
        preserve_policy_language(ROW['answer'],ALL)
def test_actual_second_warning_query_quotes_specific_retrieved_rule():
    text,route=source_reply(ROW['question'],ALL)
    assert route=='second_warning_new_course'
    assert '[S2]' in text and '[S1]' not in text
    assert 'recommended by the HoD' in text and 'Controller of Examinations' in text

def test_general_warning_passage_cannot_stand_in_for_specific_rule():
    text,route=source_reply(ROW['question'],{'S1':ALL['S1']})
    assert text=='I could not find this information in the provided documents.'
    assert route=='required_warning_rule_missing'

def test_correct_citation_survives_validation():
    text,_=source_reply(ROW['question'],ALL)
    assert preserve_policy_language(text,ALL)==text

@pytest.mark.parametrize('question',[
    'I am on first warning. May I register a new course?',
    'I am not on second warning. Can I register a new course?',
    'Compare first and second warnings for a new course.',
    'Explain second warning new course rules and the theory lab repeat rule.',
    'Explain second warning new course rules and scholarship conditions.',
])
def test_narrow_reply_does_not_swallow_other_scenarios(question):
    assert source_reply(question,ALL) is None

def test_rechecking_deadline_keeps_source_modality():
    sources={'S1':{'excerpt':'Student application should r each the Examination O ffice within seven days of the announcement of the result.'}}
    actual='The application must reach the Examination Office within seven days. [S1]'
    assert preserve_policy_language(actual,sources)=='The application should reach the Examination Office within seven days. [S1]'
