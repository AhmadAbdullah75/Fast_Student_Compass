"""Actual API embeddings + actual LCEL retrieval, with generation deliberately skipped.

This is not an answer-quality pass. Runs after chat quota exhaustion without
switching models/providers or simulating vectors.
"""
import json
from pathlib import Path
import sys
import argparse
import hashlib
from datetime import datetime,timezone
from time import perf_counter,sleep
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from compass.config import Settings
from compass.rag import RagPipeline,history_text,friendly_error
from compass.benchmark import facet_found,revision
from compass.ingestion import write_json

def run(name='retrieval-only',ids=None):
    settings=Settings();pipeline=RagPipeline(settings)
    bank=json.loads((ROOT/'evaluation/publication/question-bank.json').read_text(encoding='utf-8'))['cases']
    prior=json.loads((ROOT/'reports/benchmark/publication-candidate-4.json').read_text(encoding='utf-8'))
    searches={r['id']:r.get('trace',{}).get('search_question') for r in prior['results']}
    target=ROOT/f'reports/publication/{name}.json'
    suite_digest=hashlib.sha256(json.dumps(bank,sort_keys=True).encode()).hexdigest()
    result=json.loads(target.read_text(encoding='utf-8')) if target.exists() else {
        'pipeline_revision':revision(settings),'dataset_fingerprint':pipeline.manifest['fingerprint'],
        'suite_digest':suite_digest,'started_utc':datetime.now(timezone.utc).isoformat(),
        'mode':'Actual configured Gemini embedding API + persisted Chroma + same LCEL retrieve step; no generation or new follow-up rewriting',
        'answer_accuracy':'NOT_TESTED_BY_THIS_RUN','results':[]}
    assert result['pipeline_revision']==revision(settings)
    assert result.get('suite_digest',suite_digest)==suite_digest,'Use a new run name after changing the test bank'
    done={r['id'] for r in result['results']}
    for c in bank:
        if ids and c['id'] not in ids:continue
        if c['id'] in done:continue
        started=perf_counter();row={'id':c['id'],'status':'NOT_APPLICABLE','answer_tested':False}
        if c.get('retrieval_facets'):
            search=(searches.get(c['id']) if c.get('history') else c['question'])
            if not search:
                row['status']='BLOCKED_REWRITE';row['note']='Follow-up rewriting requires exhausted chat quota.'
            else:
                try:
                    history=history_text(c.get('history',[]),settings.history_budget)
                    # Reuse the exact LCEL retrieval callable employed by answer().
                    value=pipeline.chain.steps[1].invoke({'question':c['question'],'search':search,'history':history})
                    trace=pipeline.diagnostics(c['question'],history)
                    docs=trace['retrieved'];packed_ids=set(trace['packed_source_ids'].values())
                    packed=[d for d in docs if d['chunk_id'] in packed_ids]
                    row.update(status='COMPLETED',retrieval_complete=all(facet_found(f,docs) for f in c['retrieval_facets']),
                        packed_complete=all(facet_found(f,packed) for f in c['retrieval_facets']),trace=trace,
                        rewrite_note='Earlier real rewrite reused; not reverified in this run' if c.get('history') else 'Standalone question; no rewrite required')
                except Exception as exc:
                    row.update(status='FAILED',error=friendly_error(exc))
        row['latency_seconds']=round(perf_counter()-started,3)
        result['results'].append(row);write_json(target,result)
        print(json.dumps({k:row[k] for k in ('id','status','retrieval_complete','packed_complete') if k in row}),flush=True)
        if 'quota' in row.get('error','').lower():break
        if c.get('retrieval_facets'):sleep(max(0,2-(perf_counter()-started)))
    return target

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run',default='retrieval-only');parser.add_argument('--ids',nargs='*')
    args=parser.parse_args();assert args.run.replace('-','').isalnum()
    print(run(args.run,set(args.ids) if args.ids else None))
