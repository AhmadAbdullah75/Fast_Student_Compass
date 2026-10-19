"""Resumable source-reviewed live checks; no model grades its own answers."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from time import perf_counter, sleep
import psutil
from datetime import datetime, timezone
from .config import Settings
from .ingestion import open_index, read_json, write_json
from .rag import RagPipeline, friendly_error, history_text

def normalized(text):
    return ' '.join(text.casefold().split())

def facet_found(facet, documents):
    for option in facet['any_of']:
        for doc in documents:
            refs=doc['references']
            if not any(r['id']==option['source'] and r['pdf_page'] in option['pages'] for r in refs):
                continue
            if all(normalized(anchor) in normalized(doc['passage']) for anchor in option.get('anchors',[])):
                return True
    return False

def revision(settings):
    root=settings.root
    paths=list((root/'compass').glob('*.py'))+list((root/'compass').glob('*.json'))
    paths+=list((root/'frontend/src').rglob('*'))
    paths+=[root/name for name in ('sources.json','requirements-lock.txt','run.ps1','frontend/package-lock.json','frontend/index.html')]
    digest=hashlib.sha256()
    for path in sorted((p for p in paths if p.is_file()), key=lambda p:p.relative_to(root).as_posix()):
        digest.update(path.relative_to(root).as_posix().encode()+b'\0'+path.read_bytes()+b'\0')
    return digest.hexdigest()[:16]


def quota_scope(exc):
    """Classify existing error metadata without recording messages or secrets."""
    seen=set();messages=[];pending=[exc]
    while pending:
        current=pending.pop()
        if current is None or id(current) in seen:continue
        seen.add(id(current));messages.append(str(current))
        pending.extend([getattr(current,'__cause__',None),getattr(current,'__context__',None)])
    text=' '.join(messages)
    if re.search(r'PerDay|per day|daily|generate_content_free_tier_requests.*?limit:\s*500',text,re.I|re.S):return 'daily'
    if re.search(r'PerMinute|per minute',text,re.I):return 'minute'
    return 'unspecified'

def run(settings, name, ids=None, suite=None, interval=9):
    suite=Path(suite) if suite else settings.root/'evaluation/comprehensive.json'
    cases=read_json(suite)['cases']
    suite_digest=hashlib.sha256(json.dumps(cases,sort_keys=True).encode()).hexdigest()
    if not all(c.get('source_reviewed_by') for c in cases):
        raise ValueError('Expected behavior must be source-reviewed before live evaluation.')
    target=settings.root/'reports/benchmark'/f'{name}.json'
    store,manifest=open_index(settings)
    current_revision=revision(settings)
    report=read_json(target) if target.exists() else {'run':name,'pipeline_revision':current_revision,
        'started_utc':datetime.now(timezone.utc).isoformat(),
        'dataset_fingerprint':manifest['fingerprint'],'chat_model':settings.chat_model,
        'reviewer':'Codex source comparison; not independent human certification',
        'suite':suite.name,'suite_digest':suite_digest,'results':[]}
    if report.get('suite_digest',suite_digest)!=suite_digest:
        raise ValueError('Question suite changed. Use a new run name.')
    if report['pipeline_revision']!=current_revision or report['dataset_fingerprint']!=manifest['fingerprint']:
        raise ValueError('Code or dataset changed. Use a new run name; do not mix revisions.')
    done={r['id'] for r in report['results']}
    pipeline=RagPipeline(settings,store,manifest=manifest)
    for case in cases:
        if case['id'] in done or ids and case['id'] not in ids:
            continue
        started=perf_counter()
        started_utc=datetime.now(timezone.utc).isoformat()
        try:
            answer=pipeline.answer(case['question'],case.get('history',[]))
            trace=answer.diagnostics
            docs=trace.get('retrieved',[])
            packed_ids=set(trace.get('packed_source_ids',{}).values())
            packed=[d for d in docs if d['chunk_id'] in packed_ids]
            facets=case.get('retrieval_facets',[])
            retrieval=[facet_found(f,docs) for f in facets]
            evidence=[facet_found(f,packed) for f in facets]
            result={'id':case['id'],'question':case['question'],'difficulty':case['difficulty'],
                'expected_behavior':case['expected_behavior'],'expected_answer':case['expected_answer'],
                'answer':answer.answer,'citations':answer.citations,'trace':trace,'status':answer.status,
                'retrieval_facets_found':retrieval,'packed_facets_found':evidence,
                'retrieval_complete':all(retrieval) if facets else None,
                'evidence_complete':all(evidence) if facets else None,
                'review':None}
        except Exception as exc:
            trace=pipeline.diagnostics(case['question'],history_text(case.get('history',[]),settings.history_budget))
            docs=trace.get('retrieved',[])
            packed_ids=set(trace.get('packed_source_ids',{}).values())
            packed=[d for d in docs if d['chunk_id'] in packed_ids]
            facets=case.get('retrieval_facets',[])
            result={'id':case['id'],'question':case['question'],'difficulty':case['difficulty'],
                'expected_behavior':case['expected_behavior'],'expected_answer':case['expected_answer'],
                'status':'failed','error':friendly_error(exc),'trace':trace,
                'error_type':type(exc).__name__,
                'provider_http_code':getattr(exc,'code',None),
                'provider_status':getattr(exc,'status',None),
                'quota_scope':quota_scope(exc) if any(s in friendly_error(exc).lower() for s in ('quota','rate limit')) else None,
                'retrieval_complete':all(facet_found(f,docs) for f in facets) if facets else None,
                'evidence_complete':all(facet_found(f,packed) for f in facets) if facets else None,
                'raw_answer':pipeline.last_raw_answer,'review':None}
        result['latency_seconds']=round(perf_counter()-started,3)
        result['started_utc']=started_utc
        result['completed_utc']=datetime.now(timezone.utc).isoformat()
        report['results'].append(result)
        report['rss_mib']=round(psutil.Process().memory_info().rss/1024**2,1)
        write_json(target,report)
        print(json.dumps({'id':result['id'],'status':result['status'],'retrieval':result.get('retrieval_complete'),
                          'seconds':result['latency_seconds']},ensure_ascii=False),flush=True)
        if result['status']=='failed' and any(s in result.get('error','').lower() for s in ('quota','rate limit')):
            print('Stopped after quota failure; completed results are checkpointed.',flush=True)
            break
        # Sequential calls; account for the extra rewrite call on follow-ups.
        if result.get('trace',{}).get('route')=='document_rag' or result['status']=='failed':
            calls=2 if case.get('history') else 1
            sleep(max(0,interval*calls-(perf_counter()-started)))
    return target

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',required=True)
    parser.add_argument('--ids',nargs='*')
    parser.add_argument('--suite',help='Optional source-reviewed JSON suite; defaults to evaluation/comprehensive.json')
    parser.add_argument('--interval',type=float,default=9,help='Minimum seconds per generation request; use >=5 for 15-RPM free access')
    args=parser.parse_args()
    if not args.run.replace('-','').replace('_','').isalnum():
        parser.error('Use a simple run name.')
    if args.interval<5:parser.error('Keep at least five seconds per generation request.')
    print(run(Settings(),args.run,set(args.ids) if args.ids else None,args.suite,args.interval))

if __name__=='__main__':
    main()
