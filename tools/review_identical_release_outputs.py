"""Compare actually executed outputs with explicitly reviewed identical source evidence."""
import json,sys,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
new,old=sys.argv[1:3]
def read(run,file):return json.loads((root/'reports/publication'/run/file).read_text(encoding='utf-8'))
a=read(new,'workflows.json');b=read(old,'workflows.json');br=read(old,'turn-semantic-review.json')['results']
prior={f"{w['id']}:{i+1}":t for w in b['results'] for i,t in enumerate(w['turns'])}
np=root/'reports/publication'/new/'turn-semantic-review.json';done=json.loads(np.read_text(encoding='utf-8'))['results'] if np.exists() else {}
notes={};different=[]
for w in a['results']:
 for i,t in enumerate(w['turns'],1):
  key=f"{w['id']}:{i}"
  if key in done:continue
  p=prior.get(key,{})
  if t.get('status')=='completed' and br.get(key,{}).get('status')=='PASS' and all(t.get(k)==p.get(k) for k in ['question','answer','citations']):
   notes[key]={'status':'PASS','note':'Actual current execution question, full answer and complete citation objects exactly equal explicitly source-reviewed '+old+' '+key+'. Full-content equality, not keywords or an unexecuted earlier-revision pass. Reference review: '+br[key]['note']}
  else:different.append(key)
if notes:subprocess.run([sys.executable,str(root/'tools/repair_workflow_review.py'),'--run',new],input=json.dumps(notes),text=True,check=True)
print('Require distinct actual-output review:',different)
