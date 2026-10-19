import json
from pathlib import Path
import pytest
from compass.policy import requested_facets,source_reply

ROW=json.loads((Path(__file__).parent/'fixtures/release-undergraduate-facet-20261018.json').read_text(encoding='utf-8'))['turn']
def sources():
 d=ROW['diagnostics']
 return {sid:{'chunk_id':cid,'excerpt':next(x['passage'] for x in d['retrieved'] if x['chunk_id']==cid),'references':next(x['references'] for x in d['retrieved'] if x['chunk_id']==cid)} for sid,cid in d['packed_source_ids'].items()}

@pytest.mark.parametrize('q',[ROW['question'],'How does undergraduate CGPA affect my merit scholarship?','Does CGPA1.99 suspend undergraduate funding?'])
def test_undergraduate_is_not_graduation_intent(q):
 assert 'graduation_cgpa' not in requested_facets(q)

def test_actual_undergraduate_funding_case_uses_both_gpa_conditions():
 fixed=source_reply(ROW['question'],sources())
 assert fixed is not None
 text,route=fixed
 assert route=='merit_gpa_conditions'
 assert '1.99' in text and '2.00' in text and 'suspended' in text
 assert 'graduation' not in text.lower()

@pytest.mark.parametrize('q',['Give graduation minimum CGPA and gym registration fee.','Does CGPA1.99 satisfy graduation and what is the gym registration fee?'])
def test_explicit_graduation_and_gym_still_have_both_facets(q):
 assert set(requested_facets(q))=={'graduation_cgpa','gym_registration'}
