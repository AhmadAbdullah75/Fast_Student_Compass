import json
from pathlib import Path
import publication_workflows as harness
from compass.rag import RagPipeline,friendly_error
from compass.benchmark import quota_scope
ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'reports/publication/release-full-conversations-20261018'
class TracedPipeline(RagPipeline):
 def answer(self,q,turns):
  try:return super().answer(q,turns)
  except Exception as exc:
   FOLDER.mkdir(parents=True,exist_ok=True)
   p=FOLDER/'sanitized-error-types.json';rows=json.loads(p.read_text(encoding='utf-8')) if p.exists() else []
   rows.append({'question':q,'exception_type':type(exc).__name__,'http_code':getattr(exc,'code',None),'safe_message':friendly_error(exc),'quota_scope':quota_scope(exc) if 'quota' in friendly_error(exc).lower() else None})
   p.write_text(json.dumps(rows,indent=2),encoding='utf-8')
   raise
harness.RagPipeline=TracedPipeline
spec=json.loads((ROOT/'evaluation/release-20261018/new-conversations-final.json').read_text(encoding='utf-8'))
harness.SEQUENCES={k:spec['sequences'][k] for k in ['C11','C07','C12','C08','C10','C01','C02','C03','C04','C05','C06','C09']}
print(harness.run('release-full-conversations-20261018',set(harness.SEQUENCES),interval=12))
