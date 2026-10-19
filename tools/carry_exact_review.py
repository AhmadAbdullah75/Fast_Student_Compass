"""Reuse explicit semantic review only for byte-identical answers and citations.
Current execution, retrieval and provenance still require fresh report checks.
"""
import json,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--from-run',required=True);p.add_argument('--to-run',required=True);a=p.parse_args()
def read(path):return json.loads(path.read_text(encoding='utf-8'))
old=read(ROOT/f'reports/benchmark/{a.from_run}.json');new=read(ROOT/f'reports/benchmark/{a.to_run}.json')
review=read(ROOT/f'reports/publication/{a.from_run}-semantic-review.json')
path=ROOT/f'reports/publication/{a.to_run}-semantic-review.json'
d=read(path) if path.exists() else {'pipeline_revision':new['pipeline_revision'],'reviewer':review['reviewer'],'results':{}}
assert d['pipeline_revision']==new['pipeline_revision']
lookup={r['id']:r for r in old['results']};matched=[]
for r in new['results']:
 prior=lookup.get(r['id']);note=review['results'].get(r['id'])
 if r['id'] in d['results'] or not prior or not note:continue
 if r['status']!='completed' or not all(note.get(k) is True for k in ['answer_correct','conditions_complete','citations_support_claims']):continue
 if all(r.get(k)==prior.get(k) for k in ['question','answer','citations']):
  d['results'][r['id']]={**note,'note':note['note']+' Exact question, actual answer and full cited passages/metadata match explicitly reviewed '+a.from_run+'; fresh execution retained.','review_basis':'exact_output_and_source_identity','prior_review_run':a.from_run};matched.append(r['id'])
path.write_text(json.dumps(d,indent=2,ensure_ascii=False),encoding='utf-8')
print('Exact reviewed-output matches:',len(matched),matched)
