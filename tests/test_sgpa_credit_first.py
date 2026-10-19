"""Natural complete course lists exposed by fresh real-provider conversation."""
import json
from pathlib import Path
import pytest
from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda
from compass.config import Settings
from compass.rag import RagPipeline,sgpa_reply
from test_sgpa import sources

@pytest.mark.parametrize('question',[
 'Calculate SGPA for three courses: 3 credits with A, 2 credits with B, and 1 credit with C. Use official grade points.',
 'Calculate SGPA: 3-credit course with A, 2-credit course with B, 1-credit course with C.',
 'Compute SGPA: A in a 3-credit course, 2 credits with B, and C in a 1-credit course.',
])
def test_complete_credit_first_and_mixed_lists_calculate(question):
 result=sgpa_reply(question,sources())
 assert result.diagnostics['calculation']['weighted_points']=='20.00'
 assert result.diagnostics['calculation']['total_credits']=='6'
 assert result.diagnostics['calculation']['rounded_sgpa']=='3.33'

@pytest.mark.parametrize('question',[
 'Calculate SGPA: 3 credits with A and B.',
 'Calculate SGPA: 3 credits with A, another 2-credit course.',
 'Calculate SGPA: 0 credits with A.',
 'Calculate SGPA: 3 credits with X.',
 'Calculate SGPA: 3 credits with A and a repeated 2 credits with B.',
])
def test_credit_first_does_not_hide_unknown_or_missing_courses(question):
 result=sgpa_reply(question,sources())
 assert result.diagnostics['route']=='clarification'
 assert 'calculation' not in result.diagnostics


def test_recorded_complete_credit_first_question_uses_actual_retrieved_table(tmp_path):
 data=json.loads((Path(__file__).parent/'fixtures/release-sgpa-credit-first-20261018.json').read_text(encoding='utf-8'))
 row=data['turns'][0]
 docs=[Document(page_content=d['passage'],metadata={'chunk_id':d['chunk_id'],'references':json.dumps(d['references'])}) for d in row['diagnostics']['retrieved']]
 class Store:
  def as_retriever(self,**kw):return RunnableLambda(lambda _:docs)
 def forbidden(*a,**kw):raise AssertionError('Supported SGPA must not delegate arithmetic to generator')
 result=RagPipeline(Settings(root=tmp_path),Store(),RunnableLambda(forbidden)).answer(row['question'],[])
 assert result.diagnostics['calculation']['rounded_sgpa']=='3.33'
 assert result.citations


@pytest.mark.parametrize('definition',['A is defined as 3.00','define A as 3.00','A = 3.00'])
def test_natural_grade_definitions_must_not_override_documented_points(definition):
 result=sgpa_reply('Calculate SGPA: 3 credits with A and 2 credits with B; '+definition+'.',sources())
 assert result.diagnostics['route']=='clarification'
 assert 'conflict' in result.answer.lower()


def test_official_grade_reference_after_complete_course_list_is_not_an_extra_course():
 question='Calculate SGPA for three courses: 4 credits with A, 2 credits with B, and 1 credit with C, using the official grade point for A.'
 result=sgpa_reply(question,sources())
 assert result.diagnostics['calculation']['rounded_sgpa']=='3.43'


def test_rewrite_can_put_official_before_the_grade():
 result=sgpa_reply('Calculate SGPA: 4 credits with official A, 2 credits with B, and 1 credit with C using official grade points.',sources())
 assert result.diagnostics['calculation']['rounded_sgpa']=='3.43'

def test_rewritten_point_before_grade_preserves_conflict_detection():
 result=sgpa_reply('Calculate SGPA: 3 credits with a grade point of 3.00 for A, 2 credits with B, and 1 credit with C. Use official grade points for B and C.',sources())
 assert result.diagnostics['route']=='clarification' and 'conflict' in result.answer.lower()

def test_matching_point_before_grade_retains_the_letter_and_credits():
 result=sgpa_reply('Calculate SGPA: 3 credits with a grade point of 4.00 for A and 2 credits with B. Use official grade points for A and B.',sources())
 assert result.diagnostics['calculation']['rounded_sgpa']=='3.60'
