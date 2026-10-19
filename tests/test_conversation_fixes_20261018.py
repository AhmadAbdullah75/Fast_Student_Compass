import json
from pathlib import Path
import pytest
from langchain_core.runnables import RunnableLambda
from compass.config import Settings
from compass.rag import local_reply, RagPipeline
from compass.policy import source_reply, preserve_policy_language
from compass.conversation import deadline_reference,is_history_request,saved_recap

CHUNKS=json.loads((Path(__file__).parent/'fixtures/conversation-fixes-20261018.json').read_text(encoding='utf-8'))['chunks']
SOURCES={f'S{i}':{'chunk_id':c['metadata']['chunk_id'],'excerpt':c['text'],'references':json.loads(c['metadata']['references'])} for i,c in enumerate(CHUNKS,1)}
HISTORY=[{'question':'How do I withdraw from a course?','answer':'Withdrawal follows the makeup-week deadline. [S1]','status':'completed','citations':[{'id':'S1','excerpt':'Withdrawal follows the makeup-week deadline.','references':[{'title':'Test fixture','pdf_page':1}]}],'diagnostics':{'route':'document_rag'}}]

@pytest.mark.parametrize('question',[
    'List the questions I have asked in this chat.',
    'Please list all the questions I have asked in this conversation.',
    'Can you list the questions I asked earlier in this chat?',
])
def test_natural_recall_never_uses_policy_retrieval(question):
    result=local_reply(question,HISTORY)
    assert result is not None and result.diagnostics['route']=='conversation_history'
    assert HISTORY[0]['question'] in result.answer

def test_bare_deadline_without_topic_clarifies_without_retrieval(tmp_path):
    class Store:
        def as_retriever(self,**kw):return RunnableLambda(lambda _:pytest.fail('Ambiguous deadline must not retrieve'))
    pipeline=RagPipeline(Settings(root=tmp_path),Store(),RunnableLambda(lambda *a,**kw:pytest.fail('No model for missing topic')))
    result=pipeline.answer("What's the deadline?",[])
    assert result.diagnostics['route']=='clarification' and 'Which deadline' in result.answer

def test_recapping_recall_failures_does_not_repeat_them_as_policy_topics():
    turns=HISTORY+[dict(HISTORY[0],question='List the questions I have asked in this chat.',answer='Parents may visit the campus. [S1]')]
    result=local_reply('Give me a short recap of this conversation.',turns)
    assert 'Withdrawal follows the makeup-week deadline.' in result.answer
    assert 'Parents may visit' not in result.answer
    assert 'A document-based answer with sources was saved' not in result.answer

def test_exam_minimum_conflict_is_explicit_and_source_backed():
    text,route=source_reply('What is the minimum penalty for cheating in exams?',SOURCES)
    assert route=='disciplinary_source_conflict'
    assert 'zero' in text.lower() and 'minimum penalty' in text.lower()
    assert 'precedence' in text.lower() and 'conflict' in text.lower()

def test_rechecking_intervening_phrase_does_not_strengthen_should():
    text='Your student application for rechecking must reach the Examination Office within seven days. [S1]'
    evidence={'S1':{'excerpt':'Student application should r each the Examination O ffice within seven days of the announcement of the result.'}}
    assert 'application for rechecking should reach' in preserve_policy_language(text,evidence)

@pytest.mark.parametrize('q',["What's the deadline?",'What is my deadline?',"When's the deadline?",'When is it due?','By when?','Deadline?'])
def test_missing_and_multiple_deadline_topics_clarify(q):
    assert deadline_reference(q,[])['unresolved']
    turns=HISTORY+[dict(HISTORY[0],question='How many days do I have for rechecking?'),dict(HISTORY[0],question='How many library items may I borrow?')]
    assert deadline_reference(q,turns)['unresolved']

def test_unique_deadline_topic_preserves_supported_followup():
    resolved=deadline_reference("What's the deadline?",HISTORY)
    assert not resolved['unresolved'] and 'withdraw' in resolved['question']
    assert deadline_reference('What is the rechecking deadline?',HISTORY) is None

@pytest.mark.parametrize('q',['What questions can I ask about scholarships?','List the questions on an examination paper.','Show all my course withdrawal requirements.'])
def test_policy_questions_do_not_become_chat_recall(q):
    assert not is_history_request(q)

def test_short_recap_is_bounded_and_does_not_reuse_source_labels():
    turns=[dict(HISTORY[0],question=f'Topic {i}?',answer=f'Saved conclusion {i}. [S1]') for i in range(20)]
    text=saved_recap(turns)
    assert '4 of 20' in text and text.count('Saved reply excerpt:')==4
    assert '[S1]' not in text and 'Saved conclusion 19' in text

def test_penalty_comparison_requires_actual_both_sources():
    general=next(s for s in SOURCES.values() if 'Academic Dishonesty' in s['excerpt'])
    assert source_reply('Minimum cheating penalty in an exam?',{'S1':general})[1]=='required_disciplinary_comparison_missing'

def test_ddc_cdc_comparison_shows_both_minimum_and_maximum():
    text,route=source_reply('Compare DDC and CDC penalties for cheating.',SOURCES)
    assert route=='disciplinary_source_conflict'
    assert 'minimum punishment' in text and 'maximum pun' in text and 'precedence' in text

def test_contact_or_approval_question_does_not_get_penalty_essay():
    assert source_reply('Who must approve suspension for cheating?',SOURCES) is None

def test_prescribed_form_must_is_not_weakened():
    line='Application to recheck a final exam must be submitted on the prescribed form. [S1]'
    assert preserve_policy_language(line,{'S1':{'excerpt':'Student application should r each the Examination O ffice within seven days.'}})==line


def test_rechecking_to_recheck_phrase_preserves_should():
    evidence={'S1':{'excerpt':'Student application should r each the Examination O ffice within seven days of the announcement of the result.'}}
    text='An application to recheck a final examination must reach the Examination Office within seven days. [S1]'
    assert 'examination should reach' in preserve_policy_language(text,evidence)


def test_disciplinary_scholarship_does_not_make_financial_aid_automatic():
    text,route=source_reply('Could being found guilty of cheating by the CDC cost me my scholarship or financial aid?',SOURCES)
    assert route=='disciplinary_honors_conditions'
    assert '8.18' not in text or 'scholarship' in text
    assert 'financial aid' not in text.lower() or 'may' in text.lower() or 'does not establish automatic' in text.lower()
    assert 'automatically' not in text.lower() or 'does not' in text.lower()


def test_honors_rule_alone_does_not_claim_unretrieved_handbook_recommendation():
    academic={k:v for k,v in SOURCES.items() if any(r['id']=='academic' for r in v['references'])}
    text,route=source_reply('Does cheating cancel my financial aid?',academic)
    assert route=='disciplinary_honors_conditions'
    assert 'handbook describes' not in text.lower()
    assert 'does not establish automatic' in text.lower()


@pytest.mark.parametrize('phrase',['application to recheck an examination paper','application to recheck a final examination','application for final examination rechecking','application for rechecking','application'])
def test_rechecking_arrival_modality_paraphrases(phrase):
    evidence={'S1':{'excerpt':'Student application should r each the Examination O ffice within seven days of the announcement of the result.'}}
    result=preserve_policy_language(phrase+' must reach the Examination Office within seven days. [S1]',evidence)
    assert 'should reach' in result and 'must reach' not in result
    assert preserve_policy_language(phrase+' must reach the office. [S2]',evidence).endswith('must reach the office. [S2]')
