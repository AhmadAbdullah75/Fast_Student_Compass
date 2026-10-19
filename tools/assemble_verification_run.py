"""Combine explicitly reviewed same-revision attempts without erasing failures.

Input order is chronological: the last listed attempt for an ID is selected.
No model calls, inferred semantic passes, or publication approval occur here.
"""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from compass.ingestion import write_json

def assemble(name,runs,suite='evaluation/publication/question-bank.json'):
    reports=[];selected={};attempts={};reviews={};totals=[]
    for run in runs:
        report=json.loads((ROOT/f'reports/benchmark/{run}.json').read_text(encoding='utf-8'))
        if reports:
            for key in ('pipeline_revision','dataset_fingerprint','chat_model','suite_digest'):
                assert report[key]==reports[0][key],f'Mismatched {key}; do not combine revisions or suites'
        reports.append(report)
        path=ROOT/f'reports/publication/{run}-semantic-review.json'
        manual=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'results':{}}
        assert not manual.get('pipeline_revision') or manual['pipeline_revision']==report['pipeline_revision']
        assert len({r['id'] for r in report['results']})==len(report['results'])
        totals.append({'run':run,'attempted':len(report['results']),
            'completed':sum(r['status']=='completed' for r in report['results']),
            'failed_ids':[r['id'] for r in report['results'] if r['status']!='completed']})
        for index,row in enumerate(report['results']):
            ident=row['id']
            attempts.setdefault(ident,[]).append({'run':run,'result_index':index,'status':row['status'],
                'error_type':row.get('error_type'),'started_utc':row.get('started_utc'),
                'latency_seconds':row['latency_seconds']})
            selected[ident]=deepcopy(row)
            selected[ident]['verification_provenance']={'run':run,'result_index':index}
            reviews.pop(ident,None)
            if ident in manual['results']:
                reviews[ident]=deepcopy(manual['results'][ident])
                reviews[ident]['note']=f"Selected actual attempt: {run}. "+reviews[ident].get('note','')
    bank=json.loads((ROOT/suite).read_text(encoding='utf-8'))['cases']
    output={k:deepcopy(v) for k,v in reports[0].items() if k not in ('results','rss_mib')}
    output.update(run=name,mode='Evidence aggregate of actual same-revision attempts; no new inference',
        assembled_utc=datetime.now(timezone.utc).isoformat(),source_runs=runs,source_run_totals=totals,
        total_case_attempts=sum(t['attempted'] for t in totals),
        selected_status_counts=dict(Counter(r['status'] for r in selected.values())),
        results=[{**selected[c['id']],'verification_attempts':attempts[c['id']]}
                 for c in bank if c['id'] in selected])
    write_json(ROOT/f'reports/benchmark/{name}.json',output)
    write_json(ROOT/f'reports/publication/{name}-semantic-review.json',{
        'pipeline_revision':output['pipeline_revision'],
        'reviewer':'Codex comparison of actual selected responses with source-reviewed key/passages; not independent university certification',
        'source_runs':runs,'results':reviews})
    print(json.dumps({'run':name,'unique_cases':len(selected),'total_case_attempts':output['total_case_attempts'],
        'selected_status_counts':output['selected_status_counts'],'reviewed_selected_cases':len(reviews),
        'source_run_totals':totals},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--runs',nargs='+',required=True)
    p.add_argument('--suite',default='evaluation/publication/question-bank.json')
    a=p.parse_args()
    assert all(n.replace('-','').replace('_','').isalnum() for n in [a.run]+a.runs)
    assemble(a.run,a.runs,a.suite)
