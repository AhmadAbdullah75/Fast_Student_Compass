import json
from pathlib import Path
from compass.policy import source_reply,preserve_policy_language
ROW=json.loads((Path(__file__).parent/'fixtures/release-ai-modality-20261018.json').read_text(encoding='utf-8'))['case']
def sources():
 return {sid:{'chunk_id':cid,'excerpt':next(d['passage'] for d in ROW['trace']['retrieved'] if d['chunk_id']==cid),'references':next(d['references'] for d in ROW['trace']['retrieved'] if d['chunk_id']==cid)} for sid,cid in ROW['trace']['packed_source_ids'].items()}
def test_recorded_nonlab_grading_rule_uses_actual_modal_words():
 text,route=source_reply(ROW['question'],sources())
 assert route=='ai_nonlab_grading_rule'
 assert 'grading distribution should be clearly stated' in text
 assert 'demonstrations should take place' in text
 assert '10-15%' in text and 'majority' in text

def test_recorded_generated_modals_are_aligned_to_their_cited_rule():
 text=preserve_policy_language(ROW['answer'],sources())
 assert 'distribution (allocating a small percentage to submissions and the majority to quizzes or demonstrations) should be clearly stated' in text
 assert 'demonstrations should take place' in text

def test_assignment_quiz_obligation_stays_mandatory():
 s=sources();sid=next(k for k,v in s.items() if '6.1 Use in Non-Lab' in v['excerpt'])
 text=f'All course assignments must include associated quizzes or demonstrations. [{sid}]'
 assert preserve_policy_language(text,s)==text

def test_unrelated_citation_cannot_authorize_modal_repair():
 text='The grading distribution must be clearly stated in the course outline. [S1]'
 assert preserve_policy_language(text,{'S1':{'excerpt':'Unrelated rule.'}})==text


def test_nonlab_rule_does_not_swallow_requested_prompt_record_guidance():
 assert source_reply('How are AI-enabled non-lab assignments graded and what prompt records should I provide?',sources()) is None

def test_nonlab_rule_does_not_replace_requested_assessment_categories():
 assert source_reply('Compare the three AI assessment categories for non-lab grading.',sources()) is None


def test_incorporated_image_referencing_keeps_should_distinct_from_prompt_must():
 import json
 from compass.rag import pack_evidence
 from langchain_core.documents import Document
 corpus=json.loads((Path(__file__).resolve().parents[1]/'reports/prepared-chunks.json').read_text(encoding='utf-8'))['chunks']
 docs=[Document(page_content=c['text'],metadata=c['metadata']) for c in corpus if any(r['id']=='academic' and r['pdf_page'] in [52,53] for r in json.loads(c['metadata']['references']))]
 _,s=pack_evidence(docs,4000)
 before='An embedded AI figure must be referenced within the assignment and in the reference list. [S1] Students must include images of their prompts. [S2]'
 after=preserve_policy_language(before,s)
 assert 'figure should be referenced' in after
 assert 'Students must include images' in after


def test_nonlab_rule_does_not_swallow_explicit_lab_comparison():
 assert source_reply('Compare grading of AI-enabled non-lab assignments and lab assignments.',sources()) is None
