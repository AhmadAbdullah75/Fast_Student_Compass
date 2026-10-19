"""Record explicit reviewer judgments; never infer semantic passes from keywords."""
import sys,json,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--show',type=int,default=0);p.add_argument('--suite',default='evaluation/publication/question-bank.json');a=p.parse_args()
r=json.loads((ROOT/f'reports/benchmark/{a.run}.json').read_text(encoding='utf-8'))
path=ROOT/f'reports/publication/{a.run}-semantic-review.json'
d=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'pipeline_revision':r['pipeline_revision'],'reviewer':'Codex explicit actual-output/source comparison; not independent human university review','results':{}}
assert d['pipeline_revision']==r['pipeline_revision']
if a.show:
 bank={c['id']:c for c in json.loads((ROOT/a.suite).read_text(encoding='utf-8'))['cases']}
 for x in [x for x in r['results'] if x['id'] not in d['results'] and x['status']=='completed'][:a.show]:
  print('\n'+x['id']+' '+bank[x['id']]['question']+'\nEXPECTED: '+bank[x['id']]['expected_answer']+'\nACTUAL: '+x.get('answer',x.get('error','')))
  print('CITES:',[(c['id'],[(z['id'],z['pdf_page']) for z in c['references']]) for c in x.get('citations',[])],'R/E:',x.get('retrieval_complete'),x.get('evidence_complete'))
 print('Executed:',len(r['results']),'Reviewed:',len(d['results']),'Execution failures:',[x['id'] for x in r['results'] if x['status']!='completed'])
else:
 notes=json.load(sys.stdin)
 for ident,value in notes.items():
  row=next(x for x in r['results'] if x['id']==ident)
  assert row['status']=='completed' and value['status'] in ('PASS','NEEDS_FIX') and value['note'].strip()
  passed=value['status']=='PASS'
  d['results'][ident]={'answer_correct':passed,'conditions_complete':passed,'citations_support_claims':passed,'note':value['note']}
 path.write_text(json.dumps(d,indent=2,ensure_ascii=False),encoding='utf-8')
 print('Recorded explicit judgments:',list(notes))
