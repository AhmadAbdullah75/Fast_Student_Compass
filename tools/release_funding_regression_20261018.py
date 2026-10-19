import json
from pathlib import Path
import publication_workflows as harness
ROOT=Path(__file__).resolve().parents[1]
spec=json.loads((ROOT/'evaluation/release-20261018/new-conversations-final.json').read_text(encoding='utf-8'))
harness.SEQUENCES={'C04':spec['sequences']['C04']}
print(harness.run('release-funding-regression-20261018',{'C04'},interval=12))
