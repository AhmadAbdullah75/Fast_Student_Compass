"""Observed release failures replayed against real source passages; no provider calls."""
import json
import sqlite3
from pathlib import Path
import pytest
from langchain_core.runnables import RunnableLambda
from compass.policy import parse_rewrite, source_reply, align_policy_claims, preserve_policy_language
from compass.rag import RagPipeline, pack_evidence, friendly_error
from compass.config import Settings
from compass.ingestion import chunks
from compass.benchmark import revision

@pytest.fixture(scope='module')
def real_sources():
    docs,_,_=chunks(Settings())
    return docs

def packed(docs, filename, page):
    subset=[d for d in docs if any(r['filename']==filename and r['pdf_page']==page for r in json.loads(d.metadata['references']))]
    return pack_evidence(subset,12000)[1]

@pytest.mark.parametrize('q,expected,wrong',[
 ('I passed theory but failed its associated lab. What must I repeat?','only Lab','both theory'),
 ('I failed theory but passed its associated lab. What must I repeat?','both theory','only Lab'),
 ('Theory passed, lab failed. What should I repeat?','only Lab','both theory'),
])
def test_opposite_conditions_select_actual_rule(real_sources,q,expected,wrong):
    text,route=source_reply(q,packed(real_sources,'Academic_Rules_Handbook_2026.pdf',20))
    assert expected.lower() in text.lower() and wrong.lower() not in text.lower()
    assert route=='theory_lab_source_rule'

def test_no_rule_is_invented_without_evidence():
    assert source_reply('I passed theory but failed lab. What must I repeat?',{}) is None

@pytest.mark.parametrize('raw',['plain search','{}','null','[]','{"question":"x","unresolved":"false"}','{"question":"","unresolved":false}','{"question":"x","unresolved":false,"extra":1}'])
def test_malformed_rewrite_fails_closed(raw):
    with pytest.raises(ValueError,match='interpretation'):parse_rewrite(raw)

def test_valid_rewrite():
    assert parse_rewrite('{"question":"Does W affect CGPA?","unresolved":false}')=={'question':'Does W affect CGPA?','unresolved':False}

def test_ambiguity_skips_retrieval_and_generation(tmp_path):
    calls=[]
    class Store:
        def as_retriever(self,**kw):return RunnableLambda(lambda _:pytest.fail('Unresolved questions must not retrieve'))
    p=RagPipeline(Settings(root=tmp_path),Store(),RunnableLambda(lambda v, **kwargs:calls.append(v) or '{"question":"What fee?","unresolved":true}'))
    r=p.answer('And its price?', [{'question':'What are the hostel and gym facilities?','answer':'Context','status':'completed'}])
    assert r.diagnostics['route']=='clarification' and len(calls)==1 and not r.citations

@pytest.mark.parametrize('q',['What is the fee?','What is its cost?','What are the fees?','How much is that fee?'])
def test_fee_clarifies_locally(q,tmp_path):
    class Store:
        def as_retriever(self,**kw):return RunnableLambda(lambda _:pytest.fail('No retrieval'))
    p=RagPipeline(Settings(root=tmp_path),Store(),RunnableLambda(lambda _:pytest.fail('No model')))
    r=p.answer(q,[]);assert r.diagnostics['route']=='clarification' and r.diagnostics['api_calls']==0

@pytest.mark.parametrize('q',['What limits apply when transferring credits from another university?','Can I transfer credits from a different university?'])
def test_external_transfer_cannot_use_readmission_rules(q,tmp_path):
    class Store:
        def as_retriever(self,**kw):return RunnableLambda(lambda _:pytest.fail('Excluded scope'))
    r=RagPipeline(Settings(root=tmp_path),Store(),RunnableLambda(lambda _:pytest.fail('No model'))).answer(q,[])
    assert r.diagnostics['route']=='scope_boundary' and 'Readmission rules cannot' in r.answer

def test_rector_quotes_but_does_not_resolve_ambiguity(real_sources):
    sources={**packed(real_sources,'Academic_Rules_Handbook_2026.pdf',30)}
    # Pack together so source IDs cannot collide across pages.
    docs=[d for d in real_sources if any(r['id']=='academic' and r['pdf_page'] in (30,31) for r in json.loads(d.metadata['references']))]
    text,_=source_reply('What are the Rector list credit requirements?',pack_evidence(docs,12000)[1])
    assert '30 credit hours' in text and 'regular course load' in text
    assert 'cannot be established' in text and 'apply cumulatively' not in text

def test_ai_lab_inconsistent_timing_is_explicit(real_sources):
    text,_=source_reply('Exactly how long is an AI-enabled lab? It says first 2.5 hours.',packed(real_sources,'Academic_Rules_Handbook_2026.pdf',50))
    assert 'ambiguous' in text and '2.5' in text and 'half' in text

def test_generated_scholarship_clause_cannot_cite_medal(real_sources):
    docs=[d for d in real_sources if any((r['id']=='academic' and r['pdf_page']==32) or (r['id']=='scholarships' and r['pdf_page']==1) for r in json.loads(d.metadata['references']))]
    sources=pack_evidence(docs,16000)[1]
    medal=next(k for k,s in sources.items() if any(r['id']=='academic' for r in s['references']))
    text=align_policy_claims('What conditions apply to a merit scholarship?',f'Students must not have failed, repeated or withdrawn from a course [{medal}].',sources)
    assert f'[{medal}]' not in text
    with pytest.raises(ValueError,match='medal evidence'):
        align_policy_claims('Merit scholarship conditions?',f'No failed, repeated or withdrawn course [{medal}].',{medal:sources[medal]})

def test_modal_boundary_and_approval_language(real_sources):
    sources=packed(real_sources,'Academic_Rules_Handbook_2026.pdf',19)
    sid=next(iter(sources))
    assert 'should not' in preserve_policy_language(f'You must not register for more than five courses [{sid}].',sources)
    sources={'S1':{'excerpt':'It is suspended if CGPA falls below the minimum.'}}
    assert 'at or above' in preserve_policy_language('Keep your CGPA above 2.00 [S1].',sources)
    sources={'S1':{'excerpt':'Retake examination application may be considered in the following cases.'}}
    assert 'may be considered' in preserve_policy_language("A student can get a retake for a sibling wedding [S1].",sources)

@pytest.mark.parametrize('message,expected',[('429 quota PerDay','daily'),('429 quota PerMinute','rate limit'),('429 quota SECRET','did not identify')])
def test_quota_distinction_does_not_leak(message,expected):
    result=friendly_error(RuntimeError(message));assert expected in result and 'SECRET' not in result

def test_fixture_replay_recorded_wrong_answers(real_sources):
    row=json.loads((Path(__file__).parent/'fixtures/release-recorded.json').read_text(encoding='utf-8'))['theory_lab']
    question,answer,d=row['question'],row['answer'],row['trace']
    assert 'fails in theory' in answer.lower()
    sources={k:{'excerpt':next(x['passage'] for x in d['retrieved'] if x['chunk_id']==cid)} for k,cid in d['packed_source_ids'].items()}
    corrected,_=source_reply(question,sources)
    assert 'only Lab' in corrected


def test_explicit_theory_lab_never_generates_without_required_rule(tmp_path):
    from langchain_core.documents import Document
    doc=Document(page_content='Unrelated campus facilities.',metadata={'chunk_id':'unrelated','references':json.dumps([{'filename':'guide.pdf','pdf_page':1}])})
    class Store:
        def as_retriever(self,**kw):return RunnableLambda(lambda _:[doc])
    p=RagPipeline(Settings(root=tmp_path),Store(),RunnableLambda(lambda _:pytest.fail('Cannot generate a theory rule without its evidence')))
    r=p.answer('I passed theory but failed lab. What must I repeat?',[])
    assert r.answer=='I could not find this information in the provided documents.'
    assert r.diagnostics['validation']=='required_theory_lab_rule_not_retrieved'

def test_actual_rechecking_output_removes_unrelated_retake_citation():
    from compass.policy import align_rechecking_citations
    x=json.loads((Path(__file__).parent/'fixtures/release-recorded.json').read_text(encoding='utf-8'))['rechecking']
    sources={c['id']:{'chunk_id':c['chunk_id'],'excerpt':c['excerpt']} for c in x['citations']}
    text=align_rechecking_citations(x['question'],x['answer'],sources)
    assert '[S4]' not in text and '[S2]' in text and 'seven days' in text
    with pytest.raises(ValueError,match='retake evidence'):
        align_rechecking_citations(x['question'],'A prescribed fee is required [S4].',{'S4':sources['S4']})

@pytest.mark.parametrize('q',['Who is Ms. Nooria Fatima in CFD financial assistance?','Can I install MS Office on a lab PC?'])
def test_ms_title_and_office_are_not_postgraduate_intents(q):
    from compass.rag import unsupported_request
    from compass.policy import mixed_degree
    assert not unsupported_request(q)
    assert not mixed_degree('I am an undergraduate. '+q)

@pytest.mark.parametrize('q',['What are MS scholarship requirements?','What HEC scholarships cover MS and PhD?'])
def test_real_postgraduate_scope_remains_excluded(q):
    from compass.rag import unsupported_request
    assert unsupported_request(q)

def test_rechecking_application_retains_mandatory_prescribed_form(real_sources):
    from compass.rag import complete_condition_coverage
    sources=packed(real_sources,'Academic_Rules_Handbook_2026.pdf',26)
    sid=next(iter(sources))
    r=complete_condition_coverage('How soon must I apply for final-exam rechecking, is there a fee, and when is it refunded?',f'A prescribed fee is required [{sid}].',sources)
    assert 'prescribed form together with rechecking fee' in r.answer
