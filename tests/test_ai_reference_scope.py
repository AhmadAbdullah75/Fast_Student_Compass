import json
from pathlib import Path
from compass.rag import complete_condition_coverage,linked_retrieval_questions
DATA=json.loads((Path(__file__).parent/'fixtures/release-ai-reference-scope-20261018.json').read_text(encoding='utf-8'))['turns']
def sources(row):return {sid:{'chunk_id':chunk,'excerpt':next(d['passage'] for d in row['diagnostics']['retrieved'] if d['chunk_id']==chunk),'references':next(d['references'] for d in row['diagnostics']['retrieved'] if d['chunk_id']==chunk)} for sid,chunk in row['diagnostics']['packed_source_ids'].items()}
def test_explicit_permission_is_not_citation_intent():
 row=DATA[0]
 assert not any('images of the prompts' in q for q in linked_retrieval_questions(row['question']))
 base=row['diagnostics']['raw_answer']
 result=complete_condition_coverage(row['question'],base,sources(row))
 assert 'Additionally, students must include images' not in result.answer

def test_preparation_only_does_not_get_unqualified_submitted_content_supplement():
 row=DATA[3]
 result=complete_condition_coverage(row['diagnostics']['search_question'],row['diagnostics']['raw_answer'],sources(row))
 assert 'Additionally, students must include images' not in result.answer

def test_incorporated_image_question_retains_prompt_evidence():
 row=DATA[2];s=sources(row)
 sid=next(k for k,v in s.items() if 'Referencing Generative AI Tools' in v['excerpt'])
 result=complete_condition_coverage('How should I cite an AI-generated image embedded in my submitted assignment?',f'Reference the incorporated image in the assignment and reference list. [{sid}]',s)
 assert 'images of the prompts' in result.answer


def test_preparation_exception_added_to_image_answer_keeps_its_actual_subject():
 row=DATA[2];s=sources(row)
 sid=next(k for k,v in s.items() if 'Referencing Generative AI Tools' in v['excerpt'])
 result=complete_condition_coverage('How should I cite an AI-generated image in my submitted assignment?',f'Reference the incorporated image. [{sid}]',s)
 assert 'in the preparation of work does not require citation' in result.answer
 assert 'assignment brief specifically states otherwise' in result.answer
