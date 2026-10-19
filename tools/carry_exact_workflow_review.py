"""Carry explicit reviewed meaning only for identical executed question/answer/citations."""
import json,argparse,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--from-run',required=True);p.add_argument('--to-run',required=True);a=p.parse_args()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
old=ROOT/'reports/publication'/a.from_run;new=ROOT/'reports/publication'/a.to_run
raw=read(old/'workflows.json');current=read(new/'workflows.json');notes=read(old/'turn-semantic-review.json')['results']
existing=read(new/'turn-semantic-review.json')['results'] if (new/'turn-semantic-review.json').exists() else {}
def mapping(raw):return {f"{w['id']}:{i+1}":t for w in raw['results'] for i,t in enumerate(w['turns'])}
lookup=mapping(raw);values={}
for key,t in mapping(current).items():
 prior=lookup.get(key);note=notes.get(key)
 if key in existing or not prior or not note or note['status']!='PASS' or t['status']!='completed':continue
 if all(t.get(k)==prior.get(k) for k in ['question','answer','citations']):values[key]={'status':'PASS','note':note['note']+' Exact actual question/answer/full citations match explicitly reviewed '+a.from_run+'.'}
if values:subprocess.run([sys.executable,str(ROOT/'tools/repair_workflow_review.py'),'--run',a.to_run],input=json.dumps(values),text=True,check=True)
else:print('No new exact reviewed matches.')
