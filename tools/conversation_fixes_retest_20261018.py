import json
from pathlib import Path
import publication_workflows as harness
spec=json.loads((Path(__file__).resolve().parents[1]/'evaluation/repair-20261017/conversation-fixes-retest-20261018.json').read_text())
harness.SEQUENCES=spec['sequences']
print(harness.run('conversation-fixes-retest-20261018',set(harness.SEQUENCES),interval=10))
