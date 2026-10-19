"""Freeze unobserved discovery cases; never infer semantic or release passes."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser()
p.add_argument('--bank',default='evaluation/release-20261018/complete552.json')
p.add_argument('--output',default='evaluation/release-20261018/discovery-remaining.json')
a=p.parse_args()
target=ROOT/a.output
if target.exists():
 print('Existing frozen discovery bank preserved:',a.output)
 raise SystemExit(0)
source=ROOT/a.bank
bank=json.loads(source.read_text(encoding='utf-8'))['cases']
by_id={c['id']:c for c in bank}
observed={}
for path in sorted((ROOT/'reports/benchmark').glob('release-*20261018.json')):
 raw=json.loads(path.read_text(encoding='utf-8'))
 if not isinstance(raw.get('results'),list):continue
 for row in raw['results']:
  case=by_id.get(row.get('id'))
  if not case or row.get('question')!=case['question'] or row.get('status')!='completed':continue
  observed.setdefault(case['id'],[]).append({'run':path.stem,'pipeline_revision':raw.get('pipeline_revision'),'execution':'completed','semantic':'See explicit review for this actual run; completion is not a pass.'})
remaining=[c for c in bank if c['id'] not in observed]
target.write_text(json.dumps({'cases':remaining,'purpose':'Discovery only. Prior completed attempts may have different revisions or semantic failures. This subset does not certify release; final full bank must execute on the frozen product.','source_bank':a.bank,'source_bank_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'frozen_before_execution':True},indent=2),encoding='utf-8')
inventory={'full_bank':a.bank,'required':len(bank),'previously_observed_completed_cases':len(observed),'remaining_discovery':len(remaining),'previous_evidence':observed,'discovery_bank':a.output,'release_passes_inferred':0,'note':'Known semantic failures remain in issue register and actual retests. All full-bank cases remain required for final frozen qualification.'}
(ROOT/'reports/publication/release-complete-20261018/discovery-inventory.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
print(json.dumps({k:inventory[k] for k in ['required','previously_observed_completed_cases','remaining_discovery','release_passes_inferred']}))
