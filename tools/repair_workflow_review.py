"""Explicit per-turn review of ordered real-provider tests; no inferred passes."""
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--show',type=int,default=0);a=p.parse_args()
folder=ROOT/'reports/publication'/a.run
raw=json.loads((folder/'workflows.json').read_text(encoding='utf-8'))
path=folder/'turn-semantic-review.json'
notes=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'pipeline_revision':raw['pipeline_revision'],'reviewer':'Codex explicit actual-output/source review; not independent university certification','results':{}}
assert notes['pipeline_revision']==raw['pipeline_revision']
turns={f"{w['id']}:{i+1}":t for w in raw['results'] for i,t in enumerate(w['turns'])}
if a.show:
 for key,t in [(key,t) for key,t in turns.items() if key not in notes['results']][:a.show]:
  print('\n'+key+' '+t['status']+'\nQUESTION: '+t['question']+'\nACTUAL: '+(t.get('answer') or t.get('error') or ''))
  print('CITES:',[(c['id'],[(r['id'],r['pdf_page']) for r in c['references']]) for c in t.get('citations',[])])
 print('Sequences:',[(w['id'],w['execution_status'],len(w['turns'])) for w in raw['results']],'Reviewed:',len(notes['results']))
else:
 values=json.load(sys.stdin)
 for key,note in values.items():
  assert key in turns and note['status'] in ['PASS','NEEDS_FIX'] and note['note'].strip()
  assert turns[key]['status']=='completed' or note['status']=='NEEDS_FIX'
  notes['results'][key]=note
 path.write_text(json.dumps(notes,indent=2),encoding='utf-8')
 corpus={c['metadata']['chunk_id']:c for c in json.loads((ROOT/'reports/prepared-chunks.json').read_text(encoding='utf-8'))['chunks']}
 provenance=[]
 for key,t in turns.items():
  for c in t.get('citations',[]):
   doc=corpus.get(c['chunk_id'])
   if not doc or doc['text']!=c['excerpt'] or json.loads(doc['metadata']['references'])!=c['references'] or t.get('diagnostics',{}).get('packed_source_ids',{}).get(c['id'])!=c['chunk_id']:provenance.append([key,c['id']])
 review={'pipeline_revision':raw['pipeline_revision'],'reviewer':notes['reviewer'],'citation_provenance_failures':provenance,'results':{}}
 for w in raw['results']:
  keys=[f"{w['id']}:{i+1}" for i in range(len(w['turns']))]
  passed=(w['execution_status']=='COMPLETED' and keys and all(t['status']=='completed' for t in w['turns']) and all(notes['results'].get(k,{}).get('status')=='PASS' for k in keys) and all(w['checks'].values()) and not any(k in keys for k,_ in provenance))
  review['results'][w['id']]={'status':'PASS' if passed else 'NOT_VERIFIED','note':f'{sum(k in notes["results"] for k in keys)}/{len(keys)} actual turns explicitly reviewed; full sequence execution and source provenance also required.'}
 (folder/'workflow-semantic-review.json').write_text(json.dumps(review,indent=2),encoding='utf-8')
 print('Recorded',list(values),'sequence status',review['results'])
