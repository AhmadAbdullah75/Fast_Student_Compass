import json
from pathlib import Path
import pytest
from compass.policy import source_reply,generic_assistance_contact
from compass.rag import linked_retrieval_questions,validate_answer

ROW=json.loads((Path(__file__).parent/'fixtures/repair-generic-assistance.json').read_text(encoding='utf-8'))['turn']
D=ROW['diagnostics'];DOCS={x['chunk_id']:x for x in D['retrieved']}
SOURCES={sid:{'chunk_id':cid,'excerpt':DOCS[cid]['passage'],'references':DOCS[cid]['references']} for sid,cid in D['packed_source_ids'].items()}

def test_actual_broad_directory_with_incorrect_email_remains_blocked():
    with pytest.raises(ValueError,match='contact email'):
        validate_answer(D['raw_answer'],SOURCES)

def test_generic_assistance_contact_qualifies_scope_and_quotes_actual_office():
    question=D['search_question']
    assert any('Financial Assistance office' in q for q in linked_retrieval_questions(question))
    text,route=source_reply(question,SOURCES)
    assert route=='qualified_assistance_contact'
    assert text.startswith('If you mean financial assistance')
    assert 'cfd.fa@nu.edu.pk' in text and '128' in text
    assert 'shsecretary' not in text and 'Campus Leadership' not in text
    assert validate_answer(text,SOURCES).status=='completed'

@pytest.mark.parametrize('question',[
    'Give academic assistance contacts.', 'Who can I contact for medical assistance?',
    'List all assistance offices.', 'Give technical assistance email.',
])
def test_explicit_other_assistance_is_not_assumed_financial(question):
    assert not generic_assistance_contact(question)
