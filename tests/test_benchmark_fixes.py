import pytest
from langchain_core.runnables import RunnableLambda
from compass.config import Settings
from compass.rag import (ABSTAIN, RagPipeline, unsupported_request,
    linked_retrieval_questions, complete_condition_coverage, pack_evidence)
from test_compass import document

@pytest.mark.parametrize('question',[
    'What is my personal FLEX attendance today?',
    'What is my CGPA?', 'Can you check my grades?',
    'What time does my bus leave tomorrow morning?',
    'Is a girls hostel room available right now?',
    'Is the Honhaar scholarship application open today and what is its current deadline?',
    'Approve my study loan and confirm that I am officially eligible.'])
def test_explicit_live_personal_and_official_requests_abstain(question,tmp_path):
    assert unsupported_request(question)
    class Store:
        def as_retriever(self,**kwargs):
            return RunnableLambda(lambda q:pytest.fail('No retrieval needed for unsupported action'))
    pipeline=RagPipeline(Settings(root=tmp_path),Store(),RunnableLambda(lambda p:pytest.fail('No API needed')))
    result=pipeline.answer(question,[])
    assert result.answer==ABSTAIN and result.diagnostics['api_calls']==0

@pytest.mark.parametrize('question',[
    'How can I check my attendance on FLEX?',
    'Can I check my grades on FLEX?',
    'What is my attendance requirement?',
    'What happens if my CGPA falls below 2.00?',
    'Who approves my withdrawal?',
    'What is the documented withdrawal deadline?',
    'How do I apply for a hostel room?',
    'Which office handles bus transport?',
    'What conditions apply to a merit scholarship?'])
def test_documented_policy_and_self_service_questions_remain_answerable(question):
    assert not unsupported_request(question)

def test_withdrawal_grade_cross_reference_keeps_six_chunks(tmp_path):
    searches=[]
    broad=[]
    for i in range(6):
        d=document('A policy paragraph'); d.metadata['chunk_id']=str(i); broad.append(d)
    grade=document('W appears on the transcript but does not affect CGPA.')
    grade.metadata['chunk_id']='grading'
    class Store:
        def as_retriever(self,**kwargs):
            def search(q):
                searches.append(q)
                return [grade] if q.startswith('What grade is assigned') else broad
            return RunnableLambda(search)
    pipeline=RagPipeline(Settings(root=tmp_path),Store(),RunnableLambda(lambda p:'W does not affect CGPA [S1].'))
    result=pipeline.answer('Explain course withdrawal approvals and grade impact',[])
    assert len(searches)==3 and len(pipeline.last_documents)==6
    assert result.citations[0]['chunk_id']=='grading'
    assert len(result.diagnostics['retrieval_queries'])==3
    assert linked_retrieval_questions('How does course registration work?')==[]

def test_rectors_list_retains_retrieved_regular_load_condition():
    _,sources=pack_evidence([document('7.5 Only those students are included in this list who have completed the semester with regular course load prescribed in the study plan. 7.6 Dean list.')])
    result=complete_condition_coverage("What exactly is required for the Rector's List?",'SGPA 4.00 and at least 30 credit hours [S1].',sources)
    assert 'regular course load prescribed' in result.answer
    assert 'Dean list' not in result.answer

def test_fyp_eligibility_retains_hod_next_semester_graduation_condition():
    _,sources=pack_evidence([document('4.12 A student shall register for FYP-I in his/her second last semester. The Head of Department will approve registration in FYP-I based on the student\u2019s ability to graduate in the subsequent semester. 4.13 The Head can allow one deficiency.')])
    result=complete_condition_coverage('What are the normal FYP-I requirements?',
        'Pass the prescribed courses and have zero warnings [S1].',sources)
    assert 'ability to graduate in the subsequent semester' in result.answer
    assert 'Head of Department will approve' in result.answer
    assert 'one deficiency' not in result.answer
