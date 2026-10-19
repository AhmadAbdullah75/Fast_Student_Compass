"""Actual discovery failures plus negative controls; no live API requests."""
import json
from pathlib import Path
import pytest
from compass.rag import validate_answer
from compass.policy import source_reply, external_transfer, preserve_policy_language

ROWS={r['id']:r for r in json.loads((Path(__file__).parent/'fixtures/release-discovery-20261018.json').read_text(encoding='utf-8'))['results']}

def sources(row):
    docs={d['chunk_id']:d for d in row['trace']['retrieved']}
    return {sid:{'chunk_id':cid,'excerpt':docs[cid]['passage'],'references':docs[cid]['references']}
            for sid,cid in row['trace']['packed_source_ids'].items()}

@pytest.mark.parametrize('question',[
    ROWS['P_A13']['question'],
    'How quickly should I apply for rechecking, is payment required, and when is it refunded?',
    'Tell me the rechecking application timing, fee and refund condition.',
    'Is rechecking free to apply for, and when is the fee refunded?',
])
def test_refund_shortcut_must_not_discard_application_questions(question):
    result=source_reply(question,sources(ROWS['P_A13']))
    assert result is None or result[1]!='rechecking_refund_wording'

def test_rechecking_procedure_quotes_all_three_actual_rules():
    row=ROWS['P_A13'];text,route=source_reply(row['question'],sources(row))
    assert route=='rechecking_procedure_wording'
    assert 'prescribed form together with rechecking fee' in text
    assert 'seven days' in text and 'should' in text and 'refunded if' in text

def test_rechecking_procedure_does_not_invent_upfront_fee_exemption():
    row=ROWS['P_A13']
    text,route=source_reply('Is rechecking free to apply for? Include how quickly I should apply and when the fee is refunded.',sources(row))
    assert route=='rechecking_procedure_wording' and 'unless' not in text.lower()

def test_exact_returned_fee_variant_uses_actual_rechecking_clauses():
    row=ROWS['P_A13']
    text,route=source_reply('Is rechecking free to apply for? Include how quickly I should apply and when the fee is returned.',sources(row))
    assert route=='rechecking_procedure_wording'
    assert 'seven days' in text and 'refunded if' in text

def test_plural_rechecking_applications_keep_should():
    row=ROWS['P_A13'];sid=next(k for k,v in sources(row).items() if '5.21' in v['excerpt'])
    text=f'Applications for rechecking must reach the Examination Office within seven days [{sid}].'
    assert 'Applications for rechecking should reach' in preserve_policy_language(text,sources(row))

def test_actual_correct_cs_contact_comparison_completes():
    row=ROWS['P_N058']
    answer=validate_answer(row['raw_answer'],sources(row))
    assert 'cfd.cssecretary@nu.edu.pk' in answer.answer
    assert 'cfd.csacademic@nu.edu.pk' in answer.answer
    for line in answer.answer.splitlines():
        if '@' in line:assert '[S' in line

@pytest.mark.parametrize('replacement',[
    'invented@nu.edu.pk', 'cfd.csacademic@nu.edu.pk',
])
def test_contact_heading_does_not_authorize_wrong_mailbox_or_role(replacement):
    row=ROWS['P_N058']
    text=row['raw_answer'].replace('cfd.cssecretary@nu.edu.pk',replacement)
    with pytest.raises(ValueError,match='contact email'):
        validate_answer(text,sources(row))

def test_contact_heading_cannot_borrow_an_unrelated_citation():
    row=ROWS['P_N058'];s=sources(row)
    wrong=next(k for k,v in s.items() if 'cfd.cssecretary@nu.edu.pk' not in v['excerpt'])
    text=f'The CS Department Secretary email is cfd.cssecretary@nu.edu.pk [{wrong}].'
    with pytest.raises(ValueError,match='contact email'):validate_answer(text,s)

def test_arbitrary_uncited_contact_prose_does_not_inherit_later_citation():
    row=ROWS['P_N058']
    with pytest.raises(ValueError,match='contact email'):
        validate_answer('Email cfd.cssecretary@nu.edu.pk for anything.\n\nUnrelated paragraph [S1].',sources(row))

@pytest.mark.parametrize('question',[
    ROWS['P_X07']['question'],
    'As a new external applicant, how much credit can transfer?',
    'What is the transferable-credit ceiling for applicants from outside FAST?',
    'Can a fresh external-university applicant transfer half of degree credits?',
])
def test_external_credit_paraphrases_use_coverage_boundary(question):
    assert external_transfer(question)

@pytest.mark.parametrize('question',[
    'Can I transfer between FAST campuses?',
    'What credits can a former FAST student transfer upon readmission?',
])
def test_supported_internal_transfer_and_readmission_are_not_excluded(question):
    assert not external_transfer(question)

def test_hyphenated_new_course_restriction_uses_actual_quote():
    row=ROWS['R_AA10'];text,route=source_reply(row['question'],sources(row))
    assert route=='second_warning_new_course'
    assert 'Controller of Examinations' in text and 'HoD' in text
    assert '4.5(e)' not in text

@pytest.mark.parametrize('question',[
    'Infer a masters sponsorship maximum from the bachelor eight-semester rule.',
    'Can you infer the PhD sponsorship cap using the undergraduate allowance?',
    'Just infer the postgraduate funding duration from bachelor funding.',
    'Please infer a PhD sponsorship duration even though only undergraduate rules are indexed.',
    'Use these undergraduate rules to tell me the PhD sponsorship limit.',
])
def test_inference_premise_is_not_a_separate_undergraduate_request(question,tmp_path):
    from compass.rag import RagPipeline
    from compass.config import Settings
    from langchain_core.runnables import RunnableLambda
    class Store:
        def as_retriever(self,**kwargs):
            return RunnableLambda(lambda _:pytest.fail('Excluded inference must not retrieve undergraduate rules'))
    model=RunnableLambda(lambda _:pytest.fail('Excluded inference must not call the provider'))
    result=RagPipeline(Settings(root=tmp_path),Store(),model).answer(question,[])
    assert result.diagnostics['route']=='scope_boundary'
    assert 'cannot establish' in result.answer
    assert '8 semesters' not in result.answer

def test_actual_summer_minimum_enrollment_preserves_should_and_shall():
    row=ROWS['R_MUL06']
    text=preserve_policy_language(row['answer'],sources(row))
    assert 'students should register' in text
    assert 'students must register' not in text
    assert 'course shall be dropped' in text
    assert '80%' in text

def test_summer_modality_is_not_changed_without_own_supporting_citation():
    text='A minimum of ten (10) students must register in a summer course [S9].'
    assert preserve_policy_language(text,sources(ROWS['R_MUL06']))==text

def test_summer_enrollment_attendance_does_not_add_regular_entitlement():
    row=ROWS['R_MUL06'];text,route=source_reply(row['question'],sources(row))
    assert route=='summer_enrollment_wording'
    assert 'students should register' in text and 'course shall be dropped' in text
    assert '80%' in text and '100%' not in text and '20%' not in text

def test_summer_enrollment_shortcut_does_not_drop_other_requested_subject():
    row=ROWS['R_MUL06']
    result=source_reply('Explain summer minimum enrollment, attendance and financial assistance.',sources(row))
    assert result is None or result[1]!='summer_enrollment_wording'

@pytest.mark.parametrize('question',[
    'Use these undergraduate rules to tell me the PhD sponsorship limit.',
    'Using the bachelor sponsorship allowance, tell me the masters funding duration.',
    'What is the doctoral sponsorship maximum based on the undergraduate rule?',
    'Given these undergraduate sponsorship rules, what is the masters allowance?',
    'Establish a PhD funding duration from the bachelor eight-semester rule.',
    'Tell me the postgraduate funding limit using only undergraduate sponsorship information.',
])
def test_undergraduate_basis_is_not_a_requested_degree_subject(question):
    from compass.policy import mixed_degree
    assert not mixed_degree(question)

@pytest.mark.parametrize('question',[
    'Compare undergraduate and masters internal sponsorship limits.',
    'Give the undergraduate internal sponsorship limit and tell me whether it establishes a PhD maximum.',
    'Who handles undergraduate financial assistance, and can you use those rules to establish doctoral duration?',
])
def test_separately_requested_undergraduate_information_stays_in_scope(question):
    from compass.policy import mixed_degree
    assert mixed_degree(question)
