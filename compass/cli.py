"""Run from the project directory: python -m compass.cli --help."""
import argparse
import json
from time import perf_counter
import psutil
from .config import Settings
from .ingestion import audit, ingest, open_index, write_json, chunks, tokens
from .models import GeminiEmbeddings, chat_model
from .rag import RagPipeline, SCOPE_FILTER, friendly_error

def preflight(settings):
    settings.require_key()
    emb = GeminiEmbeddings(settings)
    doc = emb.embed_documents(['An undergraduate may ask the university office for clarification.'])[0]
    query = emb.embed_query('Who clarifies university policy?')
    response = chat_model(settings).invoke('Reply with the word READY only.')
    return {'chat_model':settings.chat_model, 'response':str(response.content),
            'embedding_model':settings.embedding_model, 'document_dimensions':len(doc),
            'query_dimensions':len(query),
            'note':'Access check only. This does not establish free billing status or remaining quota; verify AI Studio.'}

def evaluate(settings, input_path, output_path):
    rows = [json.loads(line) for line in input_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    if not rows or any(not r.get('manually_verified') for r in rows):
        raise ValueError('Every evaluation question needs manually verified expected behavior and evidence before live evaluation.')
    for row in rows:
        if row.get('expected_behavior') not in ('answer','abstain'):
            raise ValueError('Expected behavior must be answer or abstain.')
        if row['expected_behavior']=='answer' and (not row.get('expected_answer') or not row.get('supporting_evidence')):
            raise ValueError('Answerable questions need a manually checked answer and supporting page/section records.')
    index, manifest = open_index(settings)
    pipeline = RagPipeline(settings, store=index, manifest=manifest)
    results = []
    for row in rows:
        started = perf_counter()
        result = pipeline.answer(row['question'],row.get('history',[]))
        # Human review fields intentionally remain blank. A model never grades itself.
        results.append({**row, 'actual_answer':result.answer,'actual_citations':result.citations,
                        'retrieved':[{'chunk_id':d.metadata['chunk_id'],
                                      'references':json.loads(d.metadata['references']),
                                      'passage':d.page_content} for d in pipeline.last_documents],
                        'search_question':pipeline.last_search,
                        'latency_seconds':perf_counter()-started, 'answer_correct':None,
                        'retrieval_correct':None,'citations_correct':None,'conditions_complete':None,
                        'abstention_correct':None})
        write_json(output_path, {'dataset_version':manifest['dataset_version'], 'results':results,
            'review_required':True, 'rss_mib':psutil.Process().memory_info().rss/1024**2,
            'data_mib':sum(p.stat().st_size for p in settings.data.rglob('*') if p.is_file())/1024**2})
    return {'questions':len(results),'output':str(output_path),'status':'awaiting manual scoring'}

def score(path):
    report = json.loads(path.read_text(encoding='utf-8'))
    rows = report['results']
    answerable = [r for r in rows if r['expected_behavior']=='answer']
    unsupported = [r for r in rows if r['expected_behavior']=='abstain']
    required = ['answer_correct','retrieval_correct','citations_correct','conditions_complete']
    if any(any(r.get(k) is None for k in required) for r in answerable) or any(r.get('abstention_correct') is None for r in unsupported):
        raise ValueError('Complete the manual scoring fields before calculating acceptance results.')
    def rate(key, values):
        return sum(r[key] is True for r in values)/len(values) if values else None
    rates = {k:rate(k,answerable) for k in required}
    rates['abstention_correct'] = rate('abstention_correct',unsupported)
    passed = (len(rows)>=40 and bool(answerable) and bool(unsupported)
        and rates['answer_correct']>=.9 and rates['retrieval_correct']>=.9
        and rates['citations_correct']==1 and rates['conditions_complete']>=.9
        and rates['abstention_correct']==1)
    return {'rates':rates,'questions':len(rows),'passed':passed}

def main():
    parser = argparse.ArgumentParser(description='Local CFD Student Compass tools')
    sub = parser.add_subparsers(dest='command',required=True)
    for name in ('audit','prepare','preflight','ingest'):
        sub.add_parser(name)
    evaluation = sub.add_parser('evaluate')
    evaluation.add_argument('--input',type=str,default='evaluation/questions.jsonl')
    evaluation.add_argument('--output',type=str,default='reports/evaluation.json')
    scoring = sub.add_parser('score')
    scoring.add_argument('--input',type=str,default='reports/evaluation.json')
    args = parser.parse_args()
    settings = Settings()
    try:
        if args.command=='audit':
            result = audit(settings)
        elif args.command=='prepare':
            docs, fingerprint, config = chunks(settings)
            write_json(settings.root/'reports/prepared-chunks.json',{'fingerprint':fingerprint,
                'chunks':[{'text':d.page_content,'metadata':d.metadata} for d in docs]})
            result = {'chunks':len(docs),'max_estimated_tokens':max(tokens(d.page_content) for d in docs),
                      'fingerprint':fingerprint,'api_calls':0}
        elif args.command=='preflight':
            result = preflight(settings)
        elif args.command=='ingest':
            result = ingest(settings)
            result = {key:result[key] for key in ('status','dataset_version','chunks','collection')}
        elif args.command=='evaluate':
            result = evaluate(settings,settings.root / args.input,settings.root / args.output)
        else:
            result = score(settings.root / args.input)
        print(json.dumps(result,indent=2,ensure_ascii=False))
    except Exception as exc:
        message = str(exc) if isinstance(exc,(ValueError,FileNotFoundError)) else friendly_error(exc)
        parser.exit(1, message+'\n')

if __name__=='__main__':
    main()
