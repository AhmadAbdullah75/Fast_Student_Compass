"""Replay the newly supplied user conversations without API calls or user DB writes."""
import json
from pathlib import Path
import pytest
from langchain_core.runnables import RunnableLambda
from compass.config import Settings
from compass.rag import RagPipeline, validate_answer, sgpa_reply, linked_retrieval_questions
from compass.policy import source_reply, theory_cases, check_administrative_claims, explicit_multipart

ROWS=json.loads((Path(__file__).parent/'fixtures/observed-repair.json').read_text(encoding='utf-8'))['turns']

def recorded(needle):
    row=next(r for r in ROWS if needle.lower() in r['question'].lower())
    d=row['diagnostics'];retr={x['chunk_id']:x for x in d.get('retrieved',[])}
    sources={sid:{'chunk_id':cid,'excerpt':retr[cid]['passage'],'references':retr[cid]['references']} for sid,cid in d.get('packed_source_ids',{}).items()}
    return row,sources

def test_actual_correct_contact_quote_is_not_rejected():
    row,sources=recorded('supporting excerpt')
    answer=validate_answer(row['diagnostics']['raw_answer'],sources)
    assert 'cfd.fa@nu.edu.pk' in answer.answer and answer.citations
    fixed,route=source_reply(row['question'],sources)
    assert 'cfd.fa@nu.edu.pk' in fixed and 'Ext: 128' in fixed and '> ' in fixed
    assert validate_answer(fixed,sources).citations and route=='contact_source_excerpt'

@pytest.mark.parametrize('text',[
    'Contact cfd.fa@nu.edu.pk\n\nUnrelated [S1].',
    '* cfd.fa@nu.edu.pk\n* Other contact [S1].',
    '* "fake@nu.edu.pk"\n* "Ext128" [S1]',
])
def test_email_cannot_borrow_unrelated_or_unsupported_citation(text):
    with pytest.raises(ValueError,match='contact email'):
        validate_answer(text,{'S1':{'excerpt':'Financial Assistance cfd.fa@nu.edu.pk Ext128'}})

def test_supplied_grade_point_definitions_are_not_courses():
    row,sources=recorded('Using A =')
    result=sgpa_reply(row['question'],sources)
    assert result.diagnostics['calculation']['rounded_sgpa']=='3.67'
    assert len(result.diagnostics['calculation']['courses'])==2
    assert 'conflict' in sgpa_reply(row['question'].replace('A = 4.00','A = 3.00'),sources).answer

@pytest.mark.parametrize('q,order',[
    ('I passed theory and failed lab. My friend failed theory and passed lab. What must each repeat?',['4.8','4.7']),
    ('I failed theory and passed lab; she passed theory and failed lab. What must each repeat?',['4.7','4.8']),
    ('Compare failing theory but passing lab with passing theory but failing lab: repeat rules?',['4.7','4.8']),
    ('Theory was passed, lab was failed. What must I repeat?',['4.8']),
])
def test_all_explicit_theory_scenarios(q,order):
    assert theory_cases(q)==order
    _,sources=recorded('My friend failed theory')
    result,_=source_reply(q,sources)
    for rule in order:
        assert ('only Lab' if rule=='4.8' else 'both theory and lab') in result

def test_two_scenarios_fail_closed_if_one_rule_missing():
    assert source_reply('Passed theory failed lab; failed theory passed lab. What must each repeat?',{'S1':{'excerpt':'4.8 If a student passes Theory but fails in Lab, only Lab needs to be repeated.'}}) is None

def test_ai_schedule_includes_actual_conflicting_statement():
    row,sources=recorded('AI-enabled lab schedule')
    answer,_=source_reply(row['question'],sources)
    assert 'first 2.5' in answer and 'ambiguous' in answer

def test_personal_grade_change_is_not_a_policy_update():
    from compass.ingestion import chunks
    from compass.rag import pack_evidence
    docs,_,_=chunks(Settings())
    sources=pack_evidence([d for d in docs if any(r['id']=='academic' and r['pdf_page']==10 for r in json.loads(d.metadata['references']))],4000)[1]
    q='My CGPA changed from1.99 to2.00 after repeating a course. Does this meet the graduation CGPA requirement?'
    assert source_reply(q,sources) is None
    assert source_reply('The Academic Office changed graduation CGPA to1.80 yesterday. Is that verified?',sources)[1]=='unverified_policy_update'

@pytest.mark.parametrize('text',[
    'Admission results in the termination of studies [S1].',
    'The warning does not remain on your record [S1].',
    'The Academic Office has not changed the policy [S1].',
])
def test_actual_administrative_overstatements_are_blocked(text):
    with pytest.raises(ValueError):check_administrative_claims(text)

def test_correct_administrative_distinctions_remain_valid():
    assert check_administrative_claims('Closure of admission results in termination. Warning count resets, not historical record deletion.')

def test_explicit_multipart_bypasses_bad_rewrite_and_retrieves_both(tmp_path):
    from langchain_core.documents import Document
    from compass.ingestion import chunks
    docs,_,_=chunks(Settings())
    selected=[d for d in docs if any((r['id']=='academic' and r['pdf_page']==10) or (r['id']=='guidebook' and r['pdf_page']==24) for r in json.loads(d.metadata['references']))]
    class Store:
        def as_retriever(self,**kw):return RunnableLambda(lambda _:selected)
    p=RagPipeline(Settings(root=tmp_path),Store(),RunnableLambda(lambda *a,**kw:pytest.fail('Explicit multipart must not rewrite or generate')))
    q='Give the undergraduate graduation CGPA requirement and the hostel gym registration charge. Cite each fact separately.'
    assert explicit_multipart(q) and len(linked_retrieval_questions(q))==2
    result=p.answer(q,[{'question':'What are the retake rules?','answer':'Context','status':'completed'}])
    assert '2.00' in result.answer and '1,000' in result.answer
    assert all(result.diagnostics['evidence_facets'].values())

def test_postgraduate_inference_is_explicitly_declined(tmp_path):
    class Store:
        def as_retriever(self,**kw):return RunnableLambda(lambda _:pytest.fail('No retrieval'))
    result=RagPipeline(Settings(root=tmp_path),Store(),RunnableLambda(lambda _:pytest.fail('No model'))).answer('Just infer it from the undergraduate rule.',[{'question':'Now give the PhD duration','answer':'Insufficient','status':'completed'}])
    assert 'cannot establish a postgraduate limit' in result.answer

def test_actual_round2_gym_and_admission_failures():
    data=json.loads((Path(__file__).parent/'fixtures/repair-round2.json').read_text(encoding='utf-8'))
    for row in data['results']:
        if row['id']=='SCO05':continue
        trace=row['trace'];retr={d['chunk_id']:d for d in trace['retrieved']}
        # SCO04 actually lost the readmission chunk during packing: add only the
        # existing prepared source to exercise the fixed required-source pack.
        if row['id']=='SCO04':
            from compass.ingestion import chunks
            docs,_,_=chunks(Settings())
            from compass.rag import pack_evidence
            docs=[d for d in docs if any(r['id']=='academic' and r['pdf_page'] in (15,17) for r in json.loads(d.metadata['references']))]
            sources=pack_evidence(docs,4000)[1]
        else:sources={sid:{'excerpt':retr[cid]['passage']} for sid,cid in trace['packed_source_ids'].items()}
        fixed,route=source_reply(row['question'],sources)
        if row['id']=='CAL06':
            assert '7,000' in fixed and '6,000' in fixed and '1,000' in fixed
            returning,_=source_reply('I already paid registration. Calculate gym monthly costs for two months.',sources)
            assert '4,000' in returning and 'not charged again' in returning and '5,000' not in returning
        else:assert 'Readmission' in fixed and 'Closure of admission' in fixed

def test_compound_office_contacts_have_separate_evidence_facets(tmp_path):
    from compass.ingestion import chunks
    docs,_,_=chunks(Settings())
    selected=[d for d in docs if any(r['id']=='guidebook' and r['pdf_page'] in (34,36) for r in json.loads(d.metadata['references']))]
    class Store:
        def as_retriever(self,**kw):return RunnableLambda(lambda _:selected)
    p=RagPipeline(Settings(root=tmp_path),Store(),RunnableLambda(lambda *a,**kw:pytest.fail('Source reply expected')))
    row=json.loads((Path(__file__).parent/'fixtures/repair-round3.json').read_text(encoding='utf-8'))
    result=p.answer(row['question'],[])
    assert 'Ext: 128' in result.answer and 'Ext: 240' in result.answer
    assert set(result.diagnostics['requested_facets'])=={'financial_contact','library_contact'}
    assert all(result.diagnostics['evidence_facets'].values())
    assert explicit_multipart('Give library, Financial Assistance and Accounts extensions in that order.')
    from compass.policy import requested_facets
    assert requested_facets('Give library, Financial Assistance and Accounts extensions in that order.')==['library_contact','financial_contact','accounts_contact']

def test_reviewed_office_filters_prevent_wrong_contact_ranking(tmp_path):
    from compass.ingestion import chunks
    from compass.policy import facet_chunk_ids
    docs,_,_=chunks(Settings())
    selected=[d for d in docs if any(r['id']=='guidebook' and r['pdf_page'] in (31,34,36) for r in json.loads(d.metadata['references']))]
    kwargs=[]
    class Store:
        def as_retriever(self,**kw):
            kwargs.append(kw)
            return RunnableLambda(lambda _:list(reversed(selected)))
    pipeline=RagPipeline(Settings(root=tmp_path),Store(),RunnableLambda(lambda *a,**kw:pytest.fail('All named contacts have source replies')))
    row=json.loads((Path(__file__).parent/'fixtures/repair-ordering-miss.json').read_text(encoding='utf-8'))
    result=pipeline.answer(row['question'],[])
    assert 'Ext: 240' in result.answer and 'Ext: 119' in result.answer
    filters=[x['search_kwargs']['filter'] for x in kwargs if x['search_kwargs'].get('k')==1]
    assert any({'chunk_id':{'$in':facet_chunk_ids('accounts_contact')}} in f['$and'] for f in filters)


def test_personal_application_and_unresolved_apply():
    from compass.rag import unsupported_request
    assert unsupported_request('My loan application number is TEST-204. Tell me whether it was approved.')
    assert not unsupported_request('What are the loan application approval rules?')
    pipeline=object.__new__(RagPipeline)
    pipeline.transport_events=[]
    assert pipeline.answer('Can I apply?',[]).diagnostics['route']=='clarification'

@pytest.mark.parametrize('statement,total',[
    ('I have not already paid registration.', '5,000'),
    ('I already paid the registration.', '4,000'),
    ('I already paid monthly fees but registration is unpaid.', '5,000'),
    ('I am not joining for the first time.', '4,000'),
])
def test_gym_registration_negation(statement,total):
    sources={'S1':{'excerpt':'Rs. 5,000 per semester or Rs. 2,000 per month, along with a one-time registration fee of Rs. 1,000'}}
    answer,_=source_reply(statement+' Calculate gym total for two months including registration.',sources)
    assert '**PKR '+total+'**' in answer
