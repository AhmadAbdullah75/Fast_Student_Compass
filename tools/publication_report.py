"""Assemble trace-backed scores; semantic fields require explicit reviewer input."""
import argparse
import csv
import json
from pathlib import Path
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from compass.rag import citation_ids
from compass.ingestion import write_json

def build(name):
    folder=ROOT/'reports/publication';folder.mkdir(exist_ok=True)
    bank=json.loads((ROOT/'evaluation/publication/question-bank.json').read_text(encoding='utf-8'))['cases']
    report=json.loads((ROOT/f'reports/benchmark/{name}.json').read_text(encoding='utf-8'))
    review_path=folder/f'{name}-semantic-review.json'
    reviewed=json.loads(review_path.read_text(encoding='utf-8')) if review_path.exists() else {'results':{}}
    assert not reviewed.get('pipeline_revision') or reviewed['pipeline_revision']==report['pipeline_revision']
    actual={r['id']:r for r in report['results']}
    prepared=json.loads((ROOT/'reports/prepared-chunks.json').read_text(encoding='utf-8'))
    corpus={c['metadata']['chunk_id']:c for c in prepared['chunks']}
    fields=['id','difficulty','question','run_date','code_revision','dataset_fingerprint','model','status',
        'retrieval_all_facets','packed_evidence_complete','answer_correct','conditions_complete','citations_resolve',
        'citations_support_claims','abstention_or_clarification_correct','latency_seconds','reviewer','evidence_or_failure','retest_run']
    rows=[];details=['# Question-by-question release results','',
        f'Run: {name}. Revision: {report["pipeline_revision"]}. This report never auto-passes semantic accuracy.','']
    provenance_failures=[]
    for case in bank:
        ident=case['id'];item=actual.get(ident);manual=reviewed['results'].get(ident,{})
        row={'id':ident,'difficulty':case['difficulty'],'question':case['question'],'status':'NOT_RUN',
             'code_revision':report['pipeline_revision'],'dataset_fingerprint':report['dataset_fingerprint'],'model':report['chat_model']}
        if item:
            valid=True
            cited=item.get('citations',[])
            trace=item.get('trace',{})
            ids=citation_ids(item.get('answer',''))
            if ids!={c['id'] for c in cited}:valid=False
            for c in cited:
                doc=corpus.get(c['chunk_id'])
                if not doc or doc['text']!=c['excerpt'] or json.loads(doc['metadata']['references'])!=c['references']:
                    valid=False
                if trace.get('packed_source_ids',{}).get(c['id'])!=c['chunk_id']:valid=False
            if not valid:provenance_failures.append(ident)
            row.update(retrieval_all_facets=item.get('retrieval_complete'),packed_evidence_complete=item.get('evidence_complete'),
                       citations_resolve=valid,latency_seconds=item['latency_seconds'],run_date=item.get('started_utc',report.get('started_utc','not recorded')))
            for key in ('answer_correct','conditions_complete','citations_support_claims','abstention_or_clarification_correct'):
                if key in manual:row[key]=manual[key]
            required=('answer_correct','conditions_complete','citations_support_claims')
            status=('API_OR_VALIDATION_FAILED' if item['status']!='completed' else
                'PENDING_SEMANTIC_REVIEW' if not all(k in manual for k in required) else
                'PASS' if valid and all(manual[k] is True for k in required)
                    and item.get('retrieval_complete') is not False and item.get('evidence_complete') is not False else 'NEEDS_FIX')
            row.update(status=status,reviewer=reviewed.get('reviewer','') if manual else '',
                evidence_or_failure=manual.get('note',item.get('error','')),retest_run=name)
            details += [f'## {ident} - {status}', '',case['question'],'', '**Expected:** '+case['expected_answer'],'',
                '**Actual:**', '',item.get('answer',item.get('error','No answer saved.')),'',
                f'**Retrieval:** {item.get("retrieval_complete")}; **packed evidence:** {item.get("evidence_complete")}; **citation provenance:** {valid}.', '',
                '**Semantic review:** '+manual.get('note','NOT REVIEWED; no accuracy pass assigned.'),'']
        else:
            details += [f'## {ident} - NOT_RUN','',case['question'],'',
                'No response was produced in this run. No accuracy, completeness or citation-support pass is assigned.','']
        rows.append(row)
    with (ROOT/'evaluation/publication/scorecard.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    latencies=[r['latency_seconds'] for r in report['results']]
    summary={'run':name,'pipeline_revision':report['pipeline_revision'],'dataset_fingerprint':report['dataset_fingerprint'],
        'questions':len(bank),'executed':len(actual),'not_run':len(bank)-len(actual),
        'completed':sum(r['status']=='completed' for r in report['results']),
        'execution_failures':[r['id'] for r in report['results'] if r['status']!='completed'],
        'semantic_reviewed':sum(r['id'] in reviewed['results'] for r in report['results']),
        'passed':sum(r['status']=='PASS' for r in rows),'needs_fix':[r['id'] for r in rows if r['status']=='NEEDS_FIX'],
        'retrieval':{'pass':sum(r.get('retrieval_complete') is True for r in report['results']),
                     'denominator':sum(r.get('retrieval_complete') is not None for r in report['results'])},
        'packed_evidence':{'pass':sum(r.get('evidence_complete') is True for r in report['results']),
                     'denominator':sum(r.get('evidence_complete') is not None for r in report['results'])},
        'citation_provenance_failures':provenance_failures,
        'answers_with_citations':sum(bool(r.get('citations')) for r in report['results']),
        'displayed_references':sum(len(c.get('references',[])) for r in report['results'] for c in r.get('citations',[])),
        'median_latency_seconds':statistics.median(latencies) if latencies else None,
        'max_latency_seconds':max(latencies) if latencies else None,
        'question_suite_gate_met':len(rows)==187 and all(r['status']=='PASS' for r in rows),
        'publication_ready':False,
        'readiness_note':'Also requires all ordered/application workflows, final fresh browser test and policy-domain human review. A question-suite pass alone is insufficient.'}
    write_json(folder/f'{name}-summary.json',summary)
    (folder/f'{name}-questions.md').write_text('\n'.join(details)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);args=parser.parse_args();build(args.run)
