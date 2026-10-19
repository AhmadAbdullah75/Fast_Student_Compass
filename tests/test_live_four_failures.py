import json
from pathlib import Path
from compass.policy import source_reply
ROWS=json.loads((Path(__file__).parent/'fixtures/live-four-failures-20261019.json').read_text(encoding='utf-8'))
def replay(fragment):
 r=next(r for r in ROWS if fragment in r['question'])
 d=json.loads(r['diagnostics']);c=json.loads(r['citations'])
 return source_reply(d['search_question'],{x['id']:{'excerpt':x['excerpt']} for x in c})
def test_actual_contradictory_gym_total_replaced_by_single_decimal_total():
 text,route=replay('three gym months')
 assert route=='combined_gym_cooler_source_calculation'
 assert '**PKR 13,000**' in text and '9,000' not in text
def test_actual_ai_multipart_covers_permission_timing_and_recency():
 text,route=replay('duration unambiguous')
 assert 'unless explicitly allowed' in text and '10%' in text
 assert 'ambiguous' in text and 'first 2.5' in text
 assert 'cannot verify' in text and 'yesterday' in text
def test_actual_warning_reply_also_answers_scholarship_condition_question():
 text,route=replay('every scholarship condition is satisfied')
 assert 'not deletion' in text and 'does not establish that every scholarship condition' in text


def test_library_calculation_returns_total_not_just_rate():
    row=next(r for r in ROWS if 'one library item is twelve' in r['question'])
    sources={c['id']:{'excerpt':c['excerpt']} for c in json.loads(row['citations'])}
    text,route=source_reply('Calculate the fine for one undergraduate library item twelve days overdue.',sources)
    assert route=='source_grounded_library_calculation' and '**PKR 120**' in text


def test_erase_history_variant_cannot_be_swallowed_by_general_scholarship_reply():
    row=next(r for r in ROWS if 'every scholarship condition is satisfied' in r['question'])
    sources={c['id']:{'excerpt':c['excerpt']} for c in json.loads(row['citations'])}
    q='My CGPA is exactly 2.00 after my second warning. Does this prove all merit-scholarship conditions and erase the warning history?'
    text,route=source_reply(q,sources)
    assert route=='warning_count_not_record_erasure'
    assert 'not deletion' in text and 'does not establish that every scholarship condition' in text

def test_warning_history_requires_linked_reset_evidence():
    from compass.rag import linked_retrieval_questions
    queries=linked_retrieval_questions('Does CGPA2.00 prove all merit-scholarship conditions and erase the warning history?')
    assert 'Rule 5.7' in queries[0]
