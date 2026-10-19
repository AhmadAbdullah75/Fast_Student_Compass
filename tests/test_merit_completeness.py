"""Actual general-continuation omission, with source/category controls."""
import json
import re
from pathlib import Path
from compass.rag import complete_condition_coverage, linked_retrieval_questions
from compass.policy import source_reply, align_policy_claims
import pytest

ROW=json.loads((Path(__file__).parent/'fixtures/release-merit-completeness-20261018.json').read_text(encoding='utf-8'))['turn']
DOCS={d['chunk_id']:d for d in ROW['diagnostics']['retrieved']}
SOURCES={sid:{'chunk_id':cid,'excerpt':DOCS[cid]['passage'],'references':DOCS[cid]['references']}
         for sid,cid in ROW['diagnostics']['packed_source_ids'].items()}

def with_warning():
    corpus=json.loads((Path(__file__).parents[1]/'reports/prepared-chunks.json').read_text(encoding='utf-8'))['chunks']
    d=next(d for d in corpus if any(r['id']=='academic' and r['pdf_page']==24 for r in json.loads(d['metadata']['references'])))
    return {**SOURCES,'S99':{'chunk_id':d['metadata']['chunk_id'],'excerpt':d['text'],'references':json.loads(d['metadata']['references'])}}

def test_recorded_general_answer_omitted_actual_internal_warning_rule():
    assert 'CGPA' not in ROW['answer']
    result=complete_condition_coverage(ROW['question'],ROW['answer'],SOURCES)
    assert 'CGPA falls below' in result.answer and 'shall be restored' in result.answer
    assert '8 semesters' in result.answer and 'regular' in result.answer
    assert 'Study Loan' not in result.answer

def test_general_continuation_retrieves_official_warning_threshold():
    assert any('Minimum CGPA required to avoid' in q for q in linked_retrieval_questions(ROW['question']))

def test_threshold_is_quoted_only_from_actual_packed_warning_rule():
    result=complete_condition_coverage(ROW['question'],ROW['answer'],with_warning())
    assert re.search(r'2\.\s*00',result.answer) and '[S99]' in result.answer
    assert any(c['id']=='S99' for c in result.citations)

def test_missing_warning_threshold_does_not_invent_its_numeric_value():
    source={sid:s for sid,s in SOURCES.items() if '2.00' not in s['excerpt']}
    # Actual recorded answer cites only these continuing-merit passages.
    result=complete_condition_coverage(ROW['question'],ROW['answer'],source)
    assert 'CGPA falls below' in result.answer and '2.00' not in result.answer

def test_loan_paragraph_alone_does_not_establish_internal_merit_condition():
    source={'S1':{'excerpt':'Merit Scholarships for Bachelor Students. This scholarship is for four years and equal to full tuition fee.'},
            'S2':{'excerpt':'Study loans are discontinued if CGPA falls below2.00.'}}
    result=complete_condition_coverage(ROW['question'],'The cited passage describes merit scholarships [S1].',source)
    assert 'CGPA' not in result.answer and 'suspended' not in result.answer

def test_explicit_semester_only_numeric_comparison_stays_narrow():
    text,route=source_reply('My semester GPA is3.10 and cumulative GPA is1.99. Have I met only the semester-GPA condition for merit-scholarship continuation?',with_warning())
    assert route=='merit_gpa_conditions' and 'meets' in text
    assert 'suspended' not in text and 'CGPA' not in text

def threshold_fixture():
    row=json.loads((Path(__file__).parent/'fixtures/release-merit-threshold-citation-20261018.json').read_text(encoding='utf-8'))
    docs={d['chunk_id']:d for d in row['trace']['retrieved']}
    sources={sid:{'excerpt':docs[cid]['passage']} for sid,cid in row['trace']['packed_source_ids'].items()}
    return row,sources

def test_actual_composite_threshold_gets_own_supporting_locator():
    row,sources=threshold_fixture()
    text=align_policy_claims(row['question'],row['answer'],sources)
    assert re.search(r'semester GPA of 3\.0 or higher \[S3\]',text)
    assert 'ineligible [S1]' in text

def test_wrong_threshold_is_rejected_not_silently_corrected():
    row,sources=threshold_fixture()
    with pytest.raises(ValueError,match='semester-GPA threshold'):
        align_policy_claims(row['question'],'Maintain a semester GPA of 3.50 or higher [S1].',sources)

def test_loan_gpa_does_not_authorize_merit_semester_threshold():
    with pytest.raises(ValueError,match='semester-GPA threshold'):
        align_policy_claims('Merit-scholarship continuation?', 'Maintain a semester GPA of 3.0 or higher [S1].',{'S1':{'excerpt':'Study loans discontinue below CGPA2.00.'}})

def test_already_supported_threshold_does_not_get_duplicate_locator():
    row,sources=threshold_fixture()
    text='Maintain a semester GPA of 3.0 or higher [S3].'
    assert align_policy_claims(row['question'],text,sources)==text

def test_supplied_semester_gpa_is_not_reinterpreted_as_threshold():
    row,sources=threshold_fixture()
    text='The supplied semester GPA is3.20 [S1].'
    assert align_policy_claims(row['question'],text,sources)==text

@pytest.mark.parametrize('text',[
    'The rule does not require a semester GPA of 3.50 or higher; maintain a semester GPA of 3.0 or higher [S3].',
    'A semester GPA of 3.50 or higher is not required; maintain a semester GPA of 3.0 or higher [S3].',
])
def test_correction_of_false_threshold_is_not_rejected(text):
    row,sources=threshold_fixture()
    assert align_policy_claims(row['question'],text,sources)==text

@pytest.mark.parametrize('group',['[S3, S1]','[S1, S3]','[S1; S3]'])
def test_grouped_existing_threshold_support_is_not_duplicated(group):
    row,sources=threshold_fixture()
    text='Maintain a semester GPA of 3.0 or higher '+group+'.'
    assert align_policy_claims(row['question'],text,sources)==text

def scheme_fixture():
    row=json.loads((Path(__file__).parent/'fixtures/release-merit-scheme-scope-20261018.json').read_text(encoding='utf-8'))
    docs={d['chunk_id']:d for d in row['trace']['retrieved']}
    sources={sid:{'excerpt':docs[cid]['passage']} for sid,cid in row['trace']['packed_source_ids'].items()}
    return row,sources

def test_recorded_generic_internal_gpa_scope_is_replaced_by_scoped_source_composition():
    row,sources=scheme_fixture()
    assert row['answer'].startswith('Internal scholarships, including merit scholarships, are subject')
    text,route=source_reply(row['question'],sources)
    assert route=='merit_continuation_source_rules'
    assert 'Merit-scholarship semester-GPA' in text
    assert 'Continuation of merit' in text and 'semester GPA of 3.0' in text
    assert 'Internal scholarships, including' not in text
    assert 'not available in summer semester' in text
    assert 'CGPA falls below' in text and 'shall be restored' in text

def test_general_merit_composition_does_not_drop_other_policy_topics():
    _,sources=scheme_fixture()
    assert source_reply('Explain merit-scholarship continuation and library borrowing limits.',sources) is None

def test_merit_composition_requires_the_actual_summer_prohibition_when_asked():
    row,sources=scheme_fixture()
    partial={k:s for k,s in sources.items() if 'not available in summer semester' not in ' '.join(s['excerpt'].split())}
    result=source_reply(row['question'],partial)
    assert result is None or result[1]!='merit_continuation_source_rules'


def test_personal_award_confirmation_is_explicitly_declined():
    _,sources=scheme_fixture()
    text,route=source_reply('Which printed continuation requirements apply to an undergraduate merit scholarship, and can you confirm my award from them?',sources)
    assert route=='merit_continuation_source_rules'
    assert 'cannot confirm a personal scholarship award' in text
    assert 'Continuation of merit' in text


@pytest.mark.parametrize('question',[
 'For merit-scholarship continuation, can my award be verified from the policy text?',
 'Explain merit-scholarship continuation and distinguish it from confirmation of my personal award.',
])
def test_personal_award_passive_and_noun_confirmation(question):
    _,sources=scheme_fixture()
    text,route=source_reply(question,sources)
    assert 'cannot confirm a personal scholarship award' in text


def test_recorded_withdrawal_hod_or_director_does_not_drop_a_required_approval():
    from compass.policy import preserve_policy_language
    row=json.loads((Path(__file__).parent/'fixtures/release-withdrawal-approval-20261018.json').read_text(encoding='utf-8'))
    sources={c['id']:{'excerpt':c['excerpt']} for c in row['citations']}
    result=preserve_policy_language(row['answer'],sources)
    assert '(or the Director' not in result
    assert 'Documented withdrawal approval clauses' in result
    assert 'Request for withdrawal must be approved by the HoD.' in result
    assert 'first semester unless necessitated by unavoidable circumstances' in result


def test_alternative_withdrawal_approval_without_both_source_clauses_is_rejected():
    from compass.policy import preserve_policy_language
    with pytest.raises(ValueError,match='alternative withdrawal approval'):
        preserve_policy_language('Withdrawal requires HoD or Director approval [S1].',{'S1':{'excerpt':'Request for withdrawal must be approved by the HoD.'}})


def test_separate_approvals_and_unrelated_fyp_discretion_are_not_rewritten():
    from compass.policy import preserve_policy_language
    for text in ['Withdrawal requires HoD approval and Director approval in the first-semester exception.','The HoD or Director can allow FYP registration under their respective deficiency rules.']:
        assert preserve_policy_language(text,{})==text


def test_actual_director_rather_than_hod_substitution_is_not_authorized():
    from compass.policy import preserve_policy_language
    row=json.loads((Path(__file__).parent/'fixtures/release-withdrawal-replacement-20261018.json').read_text(encoding='utf-8'))
    sources={c['id']:{'excerpt':c['excerpt']} for c in row['citations']}
    result=preserve_policy_language(row['answer'],sources)
    assert 'rather than the HoD' not in result
    assert 'Request for withdrawal must be approved by the HoD.' in result
    assert 'Director of the campus.' in result


@pytest.mark.parametrize('question',[
 'Does Director approval replace HoD approval for first-semester withdrawal?',
 'Can the Director first-semester exception dispense with the documented HoD withdrawal approval?',
 'Explain the parent countersignature, HoD approval and first-semester Director rule for withdrawal.',
])
def test_withdrawal_approval_questions_quote_both_clauses_without_inferred_waiver(question):
    row=json.loads((Path(__file__).parent/'fixtures/release-withdrawal-approval-20261018.json').read_text(encoding='utf-8'))
    sources={c['id']:{'excerpt':c['excerpt']} for c in row['citations']}
    text,route=source_reply(question,sources)
    assert route=='withdrawal_approval_source_clauses'
    assert 'do not state that Director approval replaces or waives' in text
    assert 'countersigned' in text and 'HoD' in text and 'Director' in text


def test_department_contact_keeps_printed_name_as_well_as_mailbox():
    row=json.loads((Path(__file__).parent/'fixtures/release-contact-name-20261019.json').read_text(encoding='utf-8'))
    sources={c['id']:{'excerpt':c['excerpt']} for c in row['citations']}
    text,route=source_reply(row['question'],sources)
    assert route=='department_contact_source_excerpt'
    assert 'Irfan Matloob' in text and 'Irran' not in text
    assert 'cfd.sesecretary@nu.edu.pk' in text and '666' in text
