"""Report any frozen question bank using explicit semantic judgments only."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from compass.rag import citation_ids

def report(run,suite):
 raw=json.loads((ROOT/f'reports/benchmark/{run}.json').read_text(encoding='utf-8'))
 bank=json.loads((ROOT/suite).read_text(encoding='utf-8'))['cases']
 p=ROOT/f'reports/publication/{run}-semantic-review.json'
 notes=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {'results':{}}
 assert not notes.get('pipeline_revision') or notes['pipeline_revision']==raw['pipeline_revision']
 corpus={c['metadata']['chunk_id']:c for c in json.loads((ROOT/'reports/prepared-chunks.json').read_text(encoding='utf-8'))['chunks']}
 actual={r['id']:r for r in raw['results']};rows=[]
 for c in bank:
  r=actual.get(c['id'],{});n=notes['results'].get(c['id'],{})
  valid=citation_ids(r.get('answer',''))=={s['id'] for s in r.get('citations',[])}
  for s in r.get('citations',[]):
   d=corpus.get(s['chunk_id'])
   valid &= bool(d and d['text']==s['excerpt'] and json.loads(d['metadata']['references'])==s['references'] and r.get('trace',{}).get('packed_source_ids',{}).get(s['id'])==s['chunk_id'])
  semantic=all(n.get(k) is True for k in ['answer_correct','conditions_complete','citations_support_claims'])
  status=('NOT_RUN' if not r else 'EXECUTION_FAILED' if r['status']!='completed' else 'PENDING_REVIEW' if not n else 'PASS' if semantic and valid and r.get('retrieval_complete') is not False and r.get('evidence_complete') is not False else 'NEEDS_FIX')
  rows.append({'id':c['id'],'status':status,'citation_provenance':valid,'review':n.get('note')})
 summary={'run':run,'pipeline_revision':raw['pipeline_revision'],'suite':suite,'questions':len(bank),'executed':len(actual),'completed':sum(r['status']=='completed' for r in raw['results']),'semantic_reviewed':len(notes['results']),'passed':sum(r['status']=='PASS' for r in rows),'retrieval':{'pass':sum(r['status']=='completed' and r.get('retrieval_complete') is True for r in raw['results']),'denominator':sum(r['status']=='completed' and r.get('retrieval_complete') is not None for r in raw['results'])},'packed_evidence':{'pass':sum(r['status']=='completed' and r.get('evidence_complete') is True for r in raw['results']),'denominator':sum(r['status']=='completed' and r.get('evidence_complete') is not None for r in raw['results'])},'pending_or_failed':[r['id'] for r in rows if r['status']!='PASS'],'citation_provenance_failures':[r['id'] for r in rows if r['id'] in actual and not r['citation_provenance']],'availability_failures':[{'id':r['id'],'error':r.get('error'),'quota_scope':r.get('quota_scope')} for r in raw['results'] if r['status']!='completed'],'metrics_note':'Retrieval/evidence percentages cover completed cases only. Provider-blocked attempts are separately retained; they are not semantic passes or established retrieval algorithm failures.','publication_ready':False}
 (ROOT/f'reports/publication/{run}-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
 (ROOT/f'reports/publication/{run}-scorecard.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
 print(json.dumps(summary,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--suite',required=True);a=p.parse_args();report(a.run,a.suite)
