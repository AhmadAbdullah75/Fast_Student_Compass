"""Publication-specific regressions and isolated HTTP failure checks."""
import json
from time import monotonic, sleep
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from langchain_core.runnables import RunnableLambda
from compass.config import Settings
from compass.storage import ChatStore
from compass.rag import ChatService, Answer, RagPipeline, ABSTAIN, complete_condition_coverage, pack_evidence, unsupported_request
from compass.web import create_app
from test_compass import document

def test_windows_checkpoint_replacement_retries_without_losing_report(tmp_path,monkeypatch):
    from pathlib import Path
    from compass.ingestion import write_json
    real=Path.replace;attempts=[]
    def temporarily_locked(self,target):
        attempts.append(target)
        if len(attempts)<3:raise PermissionError('Windows transient reader lock')
        return real(self,target)
    monkeypatch.setattr(Path,'replace',temporarily_locked)
    target=tmp_path/'result.json'
    write_json(target,{'results':[{'id':'saved'}]})
    assert json.loads(target.read_text())['results'][0]['id']=='saved' and len(attempts)==3

def test_withdrawal_clauses_reference_their_own_rule_not_neighboring_page():
    _,sources=pack_evidence([document('4.25 Withdrawal deadline is makeup week.'),
        document('4.22 Fee is not refunded for a withdrawn course. 4.23 Application for withdrawal must be countersigned by the parent or guardian of the student.')])
    answer=complete_condition_coverage('What are withdrawal fees?',
        'Fees are not refunded for withdrawn courses [S1]. The application must be countersigned by the parent or guardian of the student [S1].',sources)
    assert answer.answer.count('[S2]')==2 and '[S1]' not in answer.answer
    qualified=complete_condition_coverage('Compare drop and withdrawal fees',
        'Fee is explicitly not refunded for a withdrawn course [S1].',sources)
    assert '[S2]' in qualified.answer and '[S1]' not in qualified.answer
    with pytest.raises(ValueError,match='invalid source'):
        complete_condition_coverage('Withdrawal fees','No fee is refunded for a withdrawn course [S99].',sources)

def test_first_year_false_premise_can_be_corrected_without_scope_guard_failure():
    from compass.rag import validate_answer
    _,sources=pack_evidence([document('Students are not allowed to withdraw from any course in the first semester unless unavoidable circumstances.')])
    assert validate_answer('The restriction is first semester, not the entire first year [S1].',sources)
    with pytest.raises(ValueError,match='first-year'):
        validate_answer('Students are not allowed to withdraw during the first year [S1].',sources)

def test_model_clarification_is_not_rejected_as_an_uncited_policy(tmp_path):
    from compass.rag import CLARIFY
    class Store:
        def as_retriever(self,**kwargs):return RunnableLambda(lambda q:[document()])
    p=RagPipeline(Settings(root=tmp_path),Store(),RunnableLambda(lambda p:'CLARIFY: '+CLARIFY))
    result=p.answer('Tell me about the other option',[])
    assert result.answer==CLARIFY and result.diagnostics['route']=='clarification' and not result.citations

def test_clear_excluded_campus_and_degree_abstain_without_generation():
    assert unsupported_request('Tell me the room-allocation rules specifically for Lahore campus hostels.')
    assert unsupported_request('What are the MS and PhD internal sponsorship limits?')
    assert not unsupported_request('Which campuses have hostel facilities?')

def test_summer_procedure_keeps_explicitly_requested_deadline_and_fee_condition():
    _,sources=pack_evidence([document('6.8 A student can withdraw from a summer course on or before the last day of classes. '
        '6.9 Summer courses cannot be dropped; hence, fee is neither refunded nor carried forward. 6.10 Next rule.')])
    result=complete_condition_coverage('Can I drop a summer course and what is the withdrawal deadline?',
        'Summer courses cannot be dropped [S1].',sources)
    assert 'last day of classes' in result.answer and 'neither refunded nor carried forward' in result.answer

def test_comparison_retains_both_registration_and_withdrawal_approval_rules():
    _,sources=pack_evidence([document('4.19 Drop requests within first two weeks. Approval of the Head of Department is essential. 4.20 No first semester drops. '
        '4.23 Application for withdrawal must be countersigned by the parent or guardian and approved by HoD. 4.24 Next rule.')])
    result=complete_condition_coverage('Compare dropping and withdrawing: timing, restrictions and fees.',
        'Dropping is in the first two weeks; withdrawal is later [S1].',sources)
    assert 'countersigned by the parent or guardian' in result.answer and 'Head of Department is essential' in result.answer

def test_long_history_budget_includes_paragraph_separators():
    from compass.rag import history_text
    from compass.ingestion import tokens
    turns=[{'question':f'Saved context {i}; reference marker MEMORY_{i}',
            'answer':'Prior saved explanation '+('word '*900),'status':'completed'} for i in range(8)]
    context=history_text(turns,2500)
    assert tokens(context)<=2500 and 'MEMORY_7' in context and 'MEMORY_0' not in context

def test_general_withdrawal_includes_paired_rule_and_its_exception():
    from compass.rag import linked_retrieval_questions
    _,sources=pack_evidence([document('4.6 A student cannot withdraw from Theory or Lab independently. '
        '4.7 Other rule. 4.8 If a student passes Theory but fails in Lab, only Lab needs to be repeated. '
        'If also registered for Theory, the student may withdraw Theory and continue Lab. 4.9 Next rule.')])
    result=complete_condition_coverage('How does course withdrawal work in a regular semester?',
        'Apply before the documented deadline [S1].',sources)
    assert 'cannot withdraw from Theory or Lab independently' in result.answer
    assert 'passes Theory but fails in Lab' in result.answer
    assert any('Theory and lab' in q for q in linked_retrieval_questions('How does course withdrawal work?'))
    assert not linked_retrieval_questions('How does summer withdrawal work?')

def test_first_saved_detail_comes_from_transcript_not_truncated_model_context():
    from compass.rag import local_reply
    turns=[{'question':f'Reference marker MEMORY_{i}','status':'completed','answer':'context '*900} for i in range(8)]
    result=local_reply('What was my reference marker in the first saved exchange?',turns)
    assert 'MEMORY_0' in result.answer and 'MEMORY_6' not in result.answer
    assert result.diagnostics['api_calls']==0
    assert 'no earlier' in local_reply('What was my first saved question?',[]).answer.lower()

def test_discretionary_fyp_permission_is_not_changed_to_a_required_grant():
    _,sources=pack_evidence([document('4.14 The Director of the campus can allow registration in FYP-I where there is deficiency of two courses.')])
    result=complete_condition_coverage('Who can allow FYP-I with two deficiencies?',
        'The Director of the campus is required to allow registration when there is a deficiency of two courses [S1].',sources)
    assert 'may allow registration' in result.answer and 'is required to allow' not in result.answer

def test_contact_domains_must_match_the_cited_printed_address():
    from compass.rag import validate_answer
    _,sources=pack_evidence([document('EXAMINATION OFFICE cfd.academics@edu.pk Ext: 113')])
    assert validate_answer('Examination Office: cfd.academics@edu.pk [S1].',sources)
    corrected=validate_answer('Examination Office: cfd.academics@nu.edu.pk [S1].',sources)
    assert 'cfd.academics@edu.pk' in corrected.answer and '@nu.edu.pk' not in corrected.answer
    with pytest.raises(ValueError,match='contact email'):
        validate_answer('Examination Office: invented.office@nu.edu.pk [S1].',sources)
    _,ambiguous=pack_evidence([document('cfd.academics@edu.pk cfd.academics@other.edu.pk')])
    with pytest.raises(ValueError,match='contact email'):
        validate_answer('Office: cfd.academics@nu.edu.pk [S1].',ambiguous)

def test_misleading_bare_polarity_is_not_the_displayed_opening():
    from compass.rag import validate_answer
    _,sources=pack_evidence([document('W appears on the transcript but does not affect CGPA.')])
    result=validate_answer('Yes, a W appears on the transcript but does not affect CGPA [S1].',sources)
    assert result.answer.startswith('a W') and 'does not affect CGPA' in result.answer

def test_ai_guidance_keeps_retrieved_verification_and_outline_qualifications():
    _,sources=pack_evidence([document('However, students must critically evaluate any content generated using AI. '
        'This grading distribution should be clearly stated in the course outline.')])
    citation=complete_condition_coverage('Must I cite AI quotations?', 'Included quotations require citation [S1].',sources)
    grading=complete_condition_coverage('How are AI assignments checked and graded?', 'Use quizzes [S1].',sources)
    assert 'critically evaluate' in citation.answer
    assert 'course outline' in grading.answer

def test_nonlab_quiz_answer_keeps_submission_and_quiz_mark_split():
    _,sources=pack_evidence([document('A small percentage (typically 10-15%) of the total marks will be allotted to the assignment submissions. '
        'The majority of the marks will be based on the assignment quizzes or demonstrations. '
        'This grading distribution should be clearly stated in the course outline.')])
    result=complete_condition_coverage('How are AI-assisted non-lab assignments checked rather than graded only on submission?',
        'Assignments include associated quizzes or demonstrations [S1].',sources)
    assert '10-15%' in result.answer and 'majority of the marks' in result.answer

def test_turnitin_answer_includes_the_student_report_service():
    _,sources=pack_evidence([document('Library prepare the Turnitin report for the similarity check for the students of the University, '
        'in addition to the administration of the Turnitin.')])
    result=complete_condition_coverage('Does the library help with Turnitin?', 'The library provides instruction [S1].',sources)
    assert 'similarity check' in result.answer

def test_rewriting_uses_student_intent_without_incidental_assistant_exception(tmp_path):
    captured=[]
    class Store:
        def as_retriever(self,**kwargs):return RunnableLambda(lambda q:[document('Both parts must be repeated for improvement.')])
    def model(prompt, **kwargs):
        rendered=prompt.to_string()
        captured.append(rendered)
        if 'Rewrite the latest question' in rendered:
            return json.dumps({'question':'After passing both theory and lab, does the separate theory withdrawal exception apply for grade improvement?', 'unresolved':False})
        return 'Both parts must be repeated for improvement [S1].'
    p=RagPipeline(Settings(root=tmp_path),Store(),RunnableLambda(model))
    turns=[{'question':'If I passed theory but failed lab, may I withdraw theory and continue lab?',
            'answer':'The specific exception applies. Unrelated first-semester exception needs Director approval.',
            'status':'completed'}]
    result=p.answer('Now I passed both. Is the same exception available for grade improvement?',turns)
    assert 'Unrelated first-semester' not in captured[0]
    assert 'passed theory but failed lab' in captured[0]
    assert 'Unrelated first-semester' in captured[1]
    assert 'first-semester' not in result.diagnostics['retrieval_history_context']

def test_four_society_interests_keep_all_activity_descriptions_before_filler():
    targets={}
    for name,text in [('speaking','BOL debating public speaking declamations MUNs'),
                      ('literary','Sukhan literary poetry prose'),
                      ('cybersecurity','Cybersecurity ethical hacking digital forensics CTF practice'),
                      ('startup','Startup entrepreneurship mentorship workshops pitch competitions')]:
        d=document(text);d.metadata['chunk_id']=name;targets[name]=d
    mentor=document('Society mentors BOL debating');mentor.metadata['chunk_id']='mentor-list'
    fillers=[]
    for i in range(6):
        d=document('Other campus services');d.metadata['chunk_id']=f'filler-{i}';fillers.append(d)
    class Store:
        def as_retriever(self,**kwargs):
            assert kwargs['search_kwargs']['filter']['$and'][0]['campus']['$in']==['all','CFD']
            def search(q):
                if kwargs['search_kwargs']['k']==6:return fillers
                key=next(k for k in targets if k in q.lower())
                return [mentor,targets[key]]+fillers
            return RunnableLambda(search)
    p=RagPipeline(Settings(evidence_budget=650),Store(),RunnableLambda(lambda prompt:'Four documented matches [S1] [S2] [S3] [S4].'))
    p.answer('Suggest societies for public speaking, poetry, cybersecurity and entrepreneurship.',[])
    assert len(p.last_documents)==6
    assert set(targets)<=set(s['chunk_id'] for s in p.last_sources.values())

def wait(client,cid):
    end=monotonic()+8
    while monotonic()<end:
        row=client.get(f'/api/conversations/{cid}').json()['turns'][-1]
        if row['status']!='pending':return row
        sleep(.02)
    pytest.fail('HTTP turn did not finish')

def submit(client,cid,q):
    response=client.post(f'/api/conversations/{cid}/turns',json={'question':q,'request_id':str(uuid4())})
    assert response.status_code==202
    return wait(client,cid)

def test_new_missing_index_fails_saved_without_fabricated_answer(tmp_path):
    db=ChatStore(tmp_path/'chats.sqlite3')
    with TestClient(create_app(Settings(root=tmp_path),db),base_url='http://localhost:8501') as c:
        cid=c.post('/api/conversations',json={}).json()['id']
        row=submit(c,cid,'Explain attendance requirements')
        assert row['status']=='failed' and row['answer'] is None
        assert 'No reviewed index' in row['error'] and len(db.turns(cid))==1

def test_missing_key_and_auth_failure_are_sanitized_and_retryable(tmp_path,monkeypatch):
    monkeypatch.delenv('GOOGLE_API_KEY',raising=False)
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    settings=Settings(root=tmp_path)
    with pytest.raises(ValueError,match='API key'):settings.require_key()
    db=ChatStore(tmp_path/'chats.sqlite3')
    class Pipeline:
        manifest={'dataset_version':'fixture','fingerprint':'fixture'}
        def answer(self,q,turns):raise RuntimeError('403 API key invalid SECRET')
    class Service(ChatService):
        def __init__(self,s,store):super().__init__(s,store,Pipeline)
    with TestClient(create_app(settings,db,Service),base_url='http://localhost:8501') as c:
        assert c.get('/api/health').json()['ready'] is False
        cid=c.post('/api/conversations',json={}).json()['id']
        row=submit(c,cid,'Policy question')
        assert row['status']=='failed' and 'API access failed' in row['error']
        assert 'SECRET' not in json.dumps(row) and len(db.turns(cid))==1

def test_timeout_retries_existing_turn_after_service_restart(tmp_path):
    db=ChatStore(tmp_path/'chats.sqlite3');calls=[]
    class Pipeline:
        manifest={'dataset_version':'fixture','fingerprint':'fixture'}
        def answer(self,q,turns):
            calls.append(q)
            if len(calls)==1:raise TimeoutError('provider timeout SECRET')
            return Answer('Saved answer [S1]',[{'id':'S1'}])
    class Service(ChatService):
        def __init__(self,s,store):super().__init__(s,store,Pipeline)
    with TestClient(create_app(Settings(root=tmp_path),db,Service),base_url='http://localhost:8501') as c:
        cid=c.post('/api/conversations',json={}).json()['id'];row=submit(c,cid,'Timeout recovery')
        assert row['status']=='failed' and 'SECRET' not in row['error']
    with TestClient(create_app(Settings(root=tmp_path),ChatStore(db.path),Service),base_url='http://localhost:8501') as c:
        assert c.post(f'/api/turns/{row["id"]}/retry').status_code==202
        completed=wait(c,cid)
        assert completed['status']=='completed' and completed['id']==row['id']
        assert len(db.turns(cid))==1 and calls==['Timeout recovery']*2

def test_restart_pending_turn_and_invalid_rename(tmp_path):
    db=ChatStore(tmp_path/'chats.sqlite3');cid=db.create();tid=db.begin(cid,'Persisted pending question')
    with TestClient(create_app(Settings(root=tmp_path),ChatStore(db.path)),base_url='http://localhost:8501') as c:
        row=c.get(f'/api/conversations/{cid}').json()['turns'][0]
        assert row['id']==tid and row['status']=='pending' and not row['running']
        assert c.patch(f'/api/conversations/{cid}',json={'title':'   '}).status_code==422
        assert c.get('/api/conversations/missing').status_code==404
        assert c.delete(f'/api/turns/{tid}').status_code==204

def test_source_continuation_and_qualified_rules_are_preserved():
    texts=[
        'Additionally, students must include images of the prompts they used with the Generative AI tool to ensure transparency and proper attribution.',
        'Moreover, transportation shall be provided subject to the availability of a bus and driver.',
        'Above are just the guidelines. Final decision rests with the Campus Committee and the Campus Director.',
        '5.21 Student application must reach the office within seven days. 5.22 Next rule. 5.25 Rechecking fee will be refunded if marks increase.']
    for q,text,required in [
        ('Must I cite AI quotations?',texts[0],'include images'),
        ('Are hostel shopping trips unlimited?',texts[1],'availability'),
        ('Is a retake medical certificate sufficient?',texts[2],'Final decision'),
        ('Can I apply for rechecking?',texts[3],'seven days')]:
        _,sources=pack_evidence([document(text)])
        result=complete_condition_coverage(q,'A source-grounded main rule [S1].',sources)
        assert required in result.answer and result.citations


def test_preparatory_ai_reference_exemption_preserves_assignment_brief_exception():
    passage = ('Therefore, the use of Generative AI for similar purposes need not be referenced '
               'unless an assignment brief specifically states otherwise.')
    _, sources = pack_evidence([document(passage)])
    answer = complete_condition_coverage('If I only use AI to explore ideas, must I cite it?',
        'Preparatory use does not require citation [S1].', sources)
    assert passage in answer.answer and len(answer.citations) == 1
    already = complete_condition_coverage('Must I cite preparatory AI use?',
        'No citation is needed unless the assignment brief requires it [S1].', sources)
    assert 'Related conditions' not in already.answer


def test_warning_new_course_answer_preserves_offered_failed_courses_and_load_limit():
    passage = ('4.4 A student under academic warning or probation: '
               'a) Must register for all such courses, in which the grade was F, provided these courses are being offered. '
               'b) Should register for all such courses, in which the grade was D, D+ or C-, provided these courses are being offered. '
               'c) Should not register for more than five courses. '
               'd) Parents/guardian will be called to the campus for a meeting.')
    _, sources = pack_evidence([document(passage)])
    main = 'New courses require HoD recommendation and Controller approval [S1].'
    result = complete_condition_coverage('On my second warning, can I register a new course?', main, sources)
    assert 'Must register' in result.answer and 'being offered' in result.answer
    assert 'more than five courses' in result.answer and 'D+' in result.answer
    assert 'Parents/guardian' not in result.answer  # Do not append a potentially truncated next-page rule.
    complete = 'Register offered failed F courses; take no more than five courses [S1].'
    assert complete_condition_coverage('What can I register on warning?', complete, sources).answer == complete
    assert complete_condition_coverage('Can I register a new course?', main, sources).answer == main
    assert complete_condition_coverage('Can I register FYP-I with two deficiencies and zero warnings?', main, sources).answer == main


def test_honors_answer_does_not_invent_cgpa_expansion():
    from compass.rag import validate_answer
    _, sources = pack_evidence([document('Students earning high CGPA receive distinguishing remarks. CGPA of 3.90 or more: Suma cum laude.')])
    result = validate_answer('Students earning high Cumulative Grade Point Awards (CGPA) receive Suma cum laude at 3.90 or more [S1].', sources)
    assert result.answer == 'Students earning high CGPA receive Suma cum laude at 3.90 or more [S1].'
    assert result.citations[0]['id'] == 'S1'
    original = 'Graduation Awards use CGPA thresholds [S1].'
    assert validate_answer(original, sources).answer == original


def test_direct_deadline_wording_comparison_quotes_both_retrieved_rules():
    from compass.rag import deadline_comparison_reply
    summer = 'A student can withdraw from a summer course on or before the last day of classes.'
    regular = 'The deadline to withdraw from a course is the last day of the makeup week of every semester.'
    _, sources = pack_evidence([document(summer + '\n' + regular)])
    result = deadline_comparison_reply('Do summer and regular withdrawal deadlines use the same wording?', sources)
    assert 'different wording' in result.answer and summer in result.answer and regular in result.answer
    assert result.diagnostics['source_only_deadline_comparison'] is True
    assert result.citations and 'cannot' not in result.answer
    # No explicit current date or permission is derived from those reference points.
    assert deadline_comparison_reply('Compare summer and regular withdrawal deadlines and financial support rules.', sources) is None
    assert deadline_comparison_reply('How do I withdraw?', sources) is None
    assert deadline_comparison_reply('Do summer and regular withdrawal deadlines use the same wording?', {}) is None


def test_deadline_comparison_pipeline_does_not_ask_model_to_compare_explicit_text(tmp_path):
    text = ('A student can withdraw from a summer course on or before the last day of classes. '
            'The deadline to withdraw from a course is the last day of the makeup week of every semester.')
    class Store:
        def as_retriever(self, **kwargs):return RunnableLambda(lambda q: [document(text)])
    pipeline = RagPipeline(Settings(root=tmp_path), Store(),
        RunnableLambda(lambda prompt: pytest.fail('Explicit source comparison does not need a model call')))
    result = pipeline.answer('Do summer and regular withdrawal deadlines use the same wording?', [])
    assert 'different wording' in result.answer and result.diagnostics['packed_source_ids']

def test_ambiguous_followup_in_new_chat_does_not_steal_other_chat_context(tmp_path):
    class Store:
        def as_retriever(self,**kwargs):return RunnableLambda(lambda q:pytest.fail('Ambiguity should not retrieve'))
    p=RagPipeline(Settings(root=tmp_path),Store(),RunnableLambda(lambda p:pytest.fail('No generation')))
    result=p.answer('Does it affect my scholarship?',[])
    assert result.diagnostics['route']=='clarification' and '?' in result.answer
    assert p.answer('Approve my study loan and confirm that I am officially eligible.',[]).answer==ABSTAIN

def test_mixed_live_and_document_question_stays_on_document_route():
    assert not unsupported_request("What are hostel eligibility rules, is a room available right now, and who can I contact?")
    assert unsupported_request('Is a room available right now?')
