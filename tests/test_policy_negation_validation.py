import json
from pathlib import Path
import pytest
from compass.policy import check_administrative_claims

def test_actual_qualified_snapshot_answer_is_not_a_claim_of_no_policy_change():
 data=json.loads((Path(__file__).parent/'fixtures/release-policy-change-validation-20261018.json').read_text(encoding='utf-8'))
 raw=data['turns'][1]['diagnostics']['raw_answer']
 assert check_administrative_claims(raw)==raw

@pytest.mark.parametrize('text',[
 'I cannot confirm that the University has not changed its policy.',
 'The documents do not establish that the University has not changed the rule.',
 'Without asserting that the Academic Office has not changed anything, I can quote the indexed rule.',
])
def test_explicitly_negated_claim_is_allowed(text):assert check_administrative_claims(text)==text

@pytest.mark.parametrize('text',[
 'The University has not changed the minimum graduation CGPA.',
 'The Academic Office has not changed the rule.',
 'Without claiming that the University has not changed it, the University has not changed the rule.',
 'The University has not changed the rule, although this is unverified.',
])
def test_affirmative_no_change_claim_is_still_rejected(text):
 with pytest.raises(ValueError,match='static documents'):check_administrative_claims(text)
