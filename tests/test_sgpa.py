"""The observed wrong SGPA must be prevented by source-grounded arithmetic."""
import pytest
from langchain_core.runnables import RunnableLambda
from compass.rag import sgpa_reply, pack_evidence, RagPipeline, ABSTAIN
from compass.config import Settings
from test_compass import document

TABLE = '''Grade Points
A+ 4.00 C+ 2.33
A 4.00 C 2.00
A- 3.67 C- 1.67
B+ 3.33 D+ 1.33
B 3.00 D 1.00
B- 2.67 F 0.00
SGPA = (P1*C1 + P2*C2 + P3*C3 + P4*C4)/C
C is the total number of credits attempted in the semester.'''
QUESTION = 'I earned A in a 3-credit course, B in another 3-credit course, and C in a 2-credit course. Calculate my SGPA.'


def sources(text=TABLE):
    return pack_evidence([document(text)])[1]


def test_observed_sgpa_error_uses_correct_weighted_sum_and_rounding():
    result = sgpa_reply(QUESTION, sources())
    assert '25.00 / 8 = 3.125' in result.answer and '**3.13**' in result.answer
    assert len(result.citations) == 1
    assert result.diagnostics['calculation']['weighted_points'] == '25.00'


def test_other_grades_credits_and_decimal_rounding():
    result = sgpa_reply('B+ in a 2-credit course and A- in a 3-credit course. Compute SGPA.', sources())
    assert result.diagnostics['calculation']['rounded_sgpa'] == '3.53'
    assert '17.67 / 5 = 3.534' in result.answer


def test_points_are_extracted_from_evidence_not_a_hardcoded_mapping():
    result = sgpa_reply(QUESTION, sources(TABLE.replace('A 4.00', 'A 3.50')))
    assert result.diagnostics['calculation']['rounded_sgpa'] == '2.94'


@pytest.mark.parametrize('question', [
    'A in a 0-credit course. Calculate SGPA.',
    'X in a 3-credit course. Calculate SGPA.',
    'A in a 3-credit course and B. Calculate SGPA.',
    'A in a 3-credit course, B in an unknown-credit course. Calculate SGPA.',
    'A in a 3-credit course and a repeated B in a 2-credit course. Calculate SGPA.',
    'A in a 3-credit course, and another 2-credit course. Calculate SGPA.',
])
def test_incomplete_unknown_or_ambiguous_course_lists_are_not_partially_calculated(question):
    result = sgpa_reply(question, sources())
    assert result.diagnostics['route'] == 'clarification'
    assert 'calculation' not in result.diagnostics and not result.citations


def test_missing_formula_or_points_does_not_fabricate_source_support():
    assert sgpa_reply(QUESTION, sources('Grade Points A 4.00')) .answer == ABSTAIN
    assert sgpa_reply(QUESTION, {}) .answer == ABSTAIN
    assert sgpa_reply('Explain SGPA calculation and repeated-course CGPA.', sources()) is None


def test_real_pipeline_uses_retrieved_table_without_model_arithmetic(tmp_path):
    class Store:
        def as_retriever(self, **kwargs):
            return RunnableLambda(lambda q: [document(TABLE)])
    def must_not_generate(prompt):
        raise AssertionError('Explicit supported SGPA arithmetic must not call the generator')
    pipeline = RagPipeline(Settings(root=tmp_path), Store(), RunnableLambda(must_not_generate))
    result = pipeline.answer(QUESTION, [])
    assert '**3.13**' in result.answer
    assert result.diagnostics['calculation']['rounded_sgpa'] == '3.13'
    assert result.diagnostics['packed_source_ids']['S1'] == result.citations[0]['chunk_id']
