import json
from pathlib import Path
import publication_workflows as harness
spec=json.loads((Path(__file__).resolve().parents[1]/'evaluation/release-20261018/new-conversations.json').read_text(encoding='utf-8'))
harness.SEQUENCES=spec['sequences']
print(harness.run('release-new-conversations-20261018',set(harness.SEQUENCES),interval=12))
