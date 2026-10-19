import json
from pathlib import Path
import pytest
from compass.policy import source_reply
ROOT=Path(__file__).resolve().parents[1]
TURN=json.loads((ROOT/'tests/fixtures/repair-room-policy.json').read_text(encoding='utf-8'))['turn']
D=TURN['diagnostics'];DOCS={x['chunk_id']:x for x in D['retrieved']}
SOURCES={sid:{'chunk_id':cid,'excerpt':DOCS[cid]['passage'],'references':DOCS[cid]['references']} for sid,cid in D['packed_source_ids'].items()}
CASES=json.loads((ROOT/'evaluation/repair-20261017/room-policy-holdout12.json').read_text(encoding='utf-8'))['cases']
@pytest.mark.parametrize('q',[TURN['question']]+[x['question'] for x in CASES])
def test_mixed_personal_room_and_policy_does_not_discard_supported_conditions(q):
    text,route=source_reply(q,SOURCES)
    assert route=='hostel_room_policy'
    assert 'cannot determine' in text and 'Medical Officer' in text and 'Hall Management Committee' in text
    assert 'competent authority' in text and 'shared rooms' in text and 'top CGPAs' in text
    assert '[S1]' in text


def test_room_shortcut_preserves_other_requested_subjects():
    from compass.policy import hostel_room_reply,merit_gpa_reply
    assert hostel_room_reply('What are hostel room eligibility rules, is a girls room available, and who can I contact?',SOURCES) is None
    assert hostel_room_reply('Explain room allocation rules and the gym registration fee.',SOURCES) is None
    assert merit_gpa_reply('My SGPA is3.10 and CGPA is1.99. Will my merit scholarship continue, and what are room-allocation rules?',SOURCES) is None

def test_missing_room_exception_does_not_emit_incomplete_rule():
    from compass.policy import hostel_room_reply
    assert hostel_room_reply(TURN['question'],{'S1':{'excerpt':'As per policy, single- and double-occupancy rooms are for graduating batches. The new batch will be accommodated in shared rooms.'}}) is None
