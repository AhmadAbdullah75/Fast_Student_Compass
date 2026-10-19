import json
import pytest
from langchain_core.documents import Document
from compass.rag import pack_evidence, complete_condition_coverage, local_reply, history_text

def sources(*texts):
    return pack_evidence([Document(page_content=text,metadata={'chunk_id':str(i),
        'references':json.dumps([{'title':'Reviewed source','pdf_page':i+1}])}) for i,text in enumerate(texts)])[1]

def test_merit_gpa_only_answer_includes_retrieved_eligibility_conditions():
    evidence=sources('Continuation is subject to semester GPA of 3.0 or higher.',
        'This scholarship is for four years of un-interrupted studies with standard courses and is equal to the full tuition fee. '
        'A student registering for less or more credit hours than specified shall not be eligible for Merit Scholarship. '
        'Student must not have failed, repeated or withdrawn from a course in that semester.')
    answer=complete_condition_coverage('What conditions apply to continuing a merit scholarship?',
        'Maintain semester GPA of 3.0 or higher [S1].',evidence)
    assert 'standard courses' in answer.answer and 'less or more credit hours' in answer.answer
    assert 'failed, repeated or withdrawn' in answer.answer
    assert {c['id'] for c in answer.citations}=={'S1','S2'}

def test_guard_does_not_invent_a_missing_condition():
    evidence=sources('The document only discusses GPA.')
    answer=complete_condition_coverage('How do I keep a merit scholarship?', 'The document discusses GPA [S1].',evidence)
    assert 'Related conditions' not in answer.answer
    assert 'four years' not in answer.answer


def test_merit_condition_cites_scholarship_not_identical_medal_wording():
    clause='Student must not have failed, repeated or withdrawn from a course in that semester.'
    evidence=sources('Position medals: '+clause,
        'This scholarship is for four years of un-interrupted studies with standard courses and is equal to the full tuition fee. '+clause)
    result=complete_condition_coverage('What conditions apply to continuing a merit scholarship?',
        'Maintain semester GPA of 3.0 or higher [S2].',evidence)
    assert clause+' [S2]' in result.answer and '[S1]' not in result.answer
    medal_only=sources('Position medals: '+clause)
    result=complete_condition_coverage('What conditions apply to continuing a merit scholarship?',
        'The available source discusses position medals [S1].',medal_only)
    assert clause not in result.answer


def test_merit_continuation_retrieves_preceding_conditions_after_withdrawal_rewrite(tmp_path):
    from langchain_core.runnables import RunnableLambda
    from compass.config import Settings
    from compass.rag import RagPipeline, linked_retrieval_questions
    gpa = Document(page_content='Continuation of merit scholarship requires semester GPA of 3.0 or higher.',
        metadata={'chunk_id':'gpa','references':json.dumps([{'title':'Handbook','pdf_page':4}])})
    full = Document(page_content=(
        'This scholarship is for four years of un-interrupted studies with standard courses, labs and final year projects and is equal to the full tuition fee. '
        'A student registering for less or more credit hours than specified shall not be eligible for Merit Scholarship. '
        'Student must not have failed, repeated or withdrawn from a course in that semester.'),
        metadata={'chunk_id':'eligibility','references':json.dumps([{'title':'Handbook','pdf_page':3}])})
    queries=[]
    class Store:
        def as_retriever(self, **kwargs):
            def retrieve(q):
                queries.append(q)
                return [full] if 'four years of uninterrupted studies' in q else [gpa]
            return RunnableLambda(retrieve)
    replies=iter([json.dumps({'question':'What conditions apply to continuing a merit scholarship after a course withdrawal during a regular semester?', 'unresolved':False}),
                  'Maintain semester GPA of 3.0 or higher [S1].'])
    pipeline=RagPipeline(Settings(root=tmp_path),Store(),RunnableLambda(lambda _, **kwargs:next(replies)))
    result=pipeline.answer('What conditions apply to continuing a merit scholarship?',[
        {'question':'What if I receive financial support?', 'answer':'Financial support prevents withdrawal.', 'status':'completed'}])
    assert len(queries)==3 and len(result.diagnostics['retrieved'])<=6
    assert any('Minimum CGPA required to avoid' in query for query in queries)
    assert 'four years' in result.answer and 'less or more credit hours' in result.answer
    assert 'failed, repeated or withdrawn' in result.answer and len(result.citations)==2
    assert linked_retrieval_questions('What is the PEEF scholarship?')==[]

def test_coupling_rule_includes_its_exception_from_same_evidence():
    evidence=sources('4.6 A student must withdraw from both. '
        '4.8 If a student passes Theory but fails in Lab, only Lab needs to be repeated. '
        'If also registered for Theory, s/he may withdraw from Theory later and continue with the lab. '
        '4.9 A student who passed both may improve grades.')
    answer=complete_condition_coverage('How do I withdraw from a course?',
        'Theory and lab must be withdrawn together [S1].',evidence)
    assert 'If a student passes Theory but fails in Lab' in answer.answer
    assert 'continue with the lab' in answer.answer
    assert '4.9' not in answer.answer

def test_summary_does_not_reissue_previous_policy_claims_or_stale_citations():
    turns=[{'question':'How do I withdraw?', 'answer':'Wrong old policy statement [S1].',
        'citations':[{'id':'S1'}], 'status':'completed'},
        {'question':'Hello', 'answer':'Capabilities', 'status':'completed',
         'diagnostics':{'route':'capabilities'}}]
    answer=local_reply('give me summary of our conversation',turns)
    assert answer.diagnostics['route']=='conversation_summary' and answer.diagnostics['api_calls']==0
    assert 'How do I withdraw?' in answer.answer
    assert 'Wrong old policy' not in answer.answer and '[S1]' not in answer.answer
    assert 'Hello' not in answer.answer
    assert local_reply('Summarize the withdrawal policy',turns) is None

def test_context_strips_source_ids_that_belong_to_previous_retrievals():
    text=history_text([{'question':'A previous question','answer':'A previous answer [S1, S3].','status':'completed'}])
    assert '[S1' not in text and 'S3]' not in text
    assert 'A previous answer' in text

@pytest.mark.parametrize('question',[
    'what questions i asked','What questions I asked?', 'what questions have I asked',
    'Which questions did I ask?', 'what questions i have asked',
    'what questions did I ask you in this chat', 'show my questions',
    'please list all my previous questions', 'repeat my earlier questions in our conversation',
    'can you tell me what questions i have asked',
    'Could you please tell me what questions I have asked?',
    'Please tell me which questions I asked earlier',
    'Would you remind me what questions I asked you?',
    'Can you list my previous questions?',
    'Show me my earlier questions',
    'What have I asked previously in this chat?',
    'What did I ask earlier in our conversation?',
    'What questions have I asked before in this chat?',
    'Please show me my questions in this chat'])
def test_question_history_variants_use_saved_history(question):
    turns=[{'question':'Earlier policy question','status':'completed'}]
    answer=local_reply(question,turns)
    assert answer is not None and answer.diagnostics['route']=='conversation_history'
    assert answer.diagnostics['api_calls']==0
    assert 'Earlier policy question' in answer.answer

@pytest.mark.parametrize('question',[
    'What questions should I ask the scholarship office?',
    'What questions are asked in examinations?',
    'Which questions can I ask about course withdrawal?',
    'Can you tell me what questions are asked in examinations?',
    'Please tell me what questions I should ask the scholarship office'])
def test_policy_questions_are_not_mistaken_for_chat_recall(question):
    assert local_reply(question,[]) is None

def test_standard_courses_do_not_mask_missing_uninterrupted_study_condition():
    evidence=sources('This scholarship is for four years of un-interrupted studies with standard courses and is equal to the full tuition fee.')
    answer=complete_condition_coverage('What conditions apply to continuing a merit scholarship?',
        'Register for standard courses [S1].',evidence)
    assert 'un-interrupted studies' in answer.answer


@pytest.mark.parametrize('question',[
 'Correction: only one library item, fourteen days late. Keep the gym question separate.',
 'Correction: one library item is twelve days overdue. Keep the gym and cooler calculation separate.',
 'Correction: one library item is twelve days overdue.',
])
def test_explicit_library_correction_keeps_prior_gym_calculation_out_of_model_context(tmp_path,question):
    from langchain_core.runnables import RunnableLambda
    from compass.config import Settings
    from compass.rag import RagPipeline
    doc=Document(page_content='Undergraduate library fine: PKR10 per item per day.',metadata={'chunk_id':'library','references':json.dumps([{'title':'Handbook','pdf_page':33}])})
    class Store:
        def as_retriever(self,**kwargs):return RunnableLambda(lambda q:[doc])
    prompts=[]
    def model(prompt,**kwargs):
        prompts.append(str(prompt))
        return 'One library item for fourteen days: PKR140 [S1].'
    pipeline=RagPipeline(Settings(root=tmp_path),Store(),RunnableLambda(model))
    prior=[{'question':'Two gym months plus one cooler month?', 'answer':'PKR8000 prior gym calculation.', 'status':'completed'}]
    result=pipeline.answer(question,prior)
    assert len(prompts)==1
    assert 'PKR8000 prior gym calculation' not in prompts[0]
    assert 'Keep the gym question separate' not in prompts[0]
    assert '140' in result.answer and len(prior)==1
