import json
from pathlib import Path
import publication_workflows as harness
p=Path(__file__).resolve().parents[1]
spec=json.loads((p/'evaluation/repair-20261017/focused-20min.json').read_text(encoding='utf-8'))
harness.SEQUENCES={'E05':spec['sequences']['E05'],'F01':['Using A = 4.00 and B = 3.00, calculate SGPA for A in a 2-credit course and B in a 4-credit course.','Correction: use B = 4.00 instead, keeping the same courses. Calculate the result.','Use the official A = 4.00 and B = 3.00 mapping again: A in a 2-credit course and B in a 4-credit course. Calculate SGPA.']}
(p/'evaluation/repair-20261017/focused-calculation-retest.json').write_text(json.dumps({'sequences':harness.SEQUENCES,'expected':'E05 conflictA3 clarified, unknowncredits notinvented;F01 correct20/6=3.33, B4conflictclarified, returnofficial3.33.'},indent=2),encoding='utf-8')
print(harness.run('focused-calculation-retest-20261017',set(harness.SEQUENCES),interval=10))
