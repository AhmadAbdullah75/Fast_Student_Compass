import json
from pathlib import Path
from compass.rag import linked_retrieval_questions
from compass.policy import source_reply,preserve_policy_language
ROWS=json.loads((Path(__file__).parent/'fixtures/release-quote-intent-20261018.json').read_text(encoding='utf-8'))['cases']
def sources(row):return {sid:{'chunk_id':cid,'excerpt':next(d['passage'] for d in row['trace']['retrieved'] if d['chunk_id']==cid),'references':next(d['references'] for d in row['trace']['retrieved'] if d['chunk_id']==cid)} for sid,cid in row['trace']['packed_source_ids'].items()}
def test_quote_course_rule_is_not_ai_content_citation_intent():
 assert not any('Referencing Generative AI' in q or 'images of the prompts' in q for q in linked_retrieval_questions(ROWS[0]['question']))

def test_quote_course_rule_returns_actual_nonlab_wording():
 text,route=source_reply(ROWS[0]['question'],sources(ROWS[0]))
 assert route=='ai_nonlab_grading_rule' and 'distribution should be clearly stated' in text

def test_active_course_outline_must_is_aligned_only_to_actual_should():
 text=preserve_policy_language(ROWS[0]['answer'],sources(ROWS[0]))
 assert 'course outline should clearly state' in text

def test_literal_ai_reference_quote_has_no_stronger_intro_and_both_page_citations():
 text,route=source_reply(ROWS[1]['question'],sources(ROWS[1]))
 assert route=='ai_reference_literal_wording'
 assert 'should be referenced' in text and 'must include images' in text
 assert 'Students must reference' not in text
 assert '[S1]' in text and '[S2]' in text

def test_literal_ai_quote_does_not_invent_missing_continuation():
 row=ROWS[1];s={k:v for k,v in sources(row).items() if all(x['pdf_page']!=53 for x in v['references'])}
 text,route=source_reply(row['question'],s)
 assert route=='required_ai_reference_continuation_missing' and text=='I could not find this information in the provided documents.'


def test_literal_reference_rule_does_not_answer_caption_generation():
 assert source_reply('Please quote an AI image caption for me.',sources(ROWS[1])) is None


def test_narrow_incorporated_reference_question_uses_actual_wording_without_quote_command():
 text,route=source_reply('What referencing and prompt evidence applies to an AI-generated figure in submitted work?',sources(ROWS[1]))
 assert route=='ai_reference_literal_wording' and 'should be referenced' in text and 'must include images' in text

def test_reference_rule_does_not_silently_drop_requested_external_style():
 assert source_reply('How do I reference an AI-generated image in APA style?',sources(ROWS[1])) is None


def test_request_to_cite_policy_sources_is_not_ai_content_reference_topic():
 from compass.policy import ai_reference_intent
 assert not ai_reference_intent('Explain AI-enabled non-lab grading and cite your sources.')
 assert not ai_reference_intent('Explain AI assessment categories with citations.')

def test_ai_api_quota_is_not_ai_quotation_intent():
 from compass.policy import ai_reference_intent
 assert not ai_reference_intent('What are the AI API quotas?')

def test_true_ai_content_reference_intent_is_retained():
 from compass.policy import ai_reference_intent
 assert ai_reference_intent('What referencing and prompt-image evidence applies to an AI-generated figure?')
 assert ai_reference_intent('Please quote the policy for referencing an AI-generated image.')
