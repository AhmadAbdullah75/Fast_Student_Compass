import json,re
from pathlib import Path
from compass.rag import linked_retrieval_questions
from compass.policy import FACETS,requested_facets,source_reply

ROOT=Path(__file__).resolve().parents[1]
ROW=json.loads((ROOT/'tests/fixtures/release-single-contact-facet-20261018.json').read_text(encoding='utf-8'))['row']
CORPUS=json.loads((ROOT/'reports/prepared-chunks.json').read_text(encoding='utf-8'))['chunks']
SOURCES={}
for name in ['financial_contact','accounts_contact','library_contact']:
 c=next(c for c in CORPUS if re.search(FACETS[name][2],' '.join(c['text'].split()),re.I))
 SOURCES[f'S{len(SOURCES)+1}']={'excerpt':c['text'],'chunk_id':c['metadata']['chunk_id'],'references':json.loads(c['metadata']['references'])}

def test_single_requested_contact_has_link_even_when_other_subject_is_warning():
 assert FACETS['financial_contact'][1] in linked_retrieval_questions(ROW['question'])

def test_library_borrowing_does_not_become_library_email_intent():
 facets=requested_facets('State the undergraduate library borrowing limit and Financial Assistance email.')
 assert facets==['financial_contact']

def test_contact_shortcut_does_not_drop_requested_library_policy():
 q='State the undergraduate library borrowing limit and Financial Assistance and Accounts emails.'
 assert source_reply(q,SOURCES) is None

def test_explicit_library_email_and_borrowing_retains_contact_facet():
 assert 'library_contact' in requested_facets('Give library borrowing rules and the library email.')

def test_contact_directory_request_retains_all_named_offices():
 assert set(requested_facets('Give library, Accounts and Financial Assistance contact emails.'))=={'library_contact','accounts_contact','financial_contact'}

def test_policy_contact_compound_stays_on_full_answer_chain():
 assert source_reply(ROW['question'],SOURCES) is None
