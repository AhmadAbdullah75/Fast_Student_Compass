"""Explicit live acceptance run; isolated storage, sequential calls, quota stop."""
import hashlib
import json
from pathlib import Path
import publication_workflows as harness

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'reports/publication/final-focused-20261020'
FOLDER.mkdir(parents=True, exist_ok=True)
harness.SEQUENCES = {
    'C1': [
        'Ali failed theory but passed its lab. Sara passed theory but failed its lab. What must each repeat?',
        'Correction: Ali passed both and wants grade improvement. Sara is unchanged. If both register for theory and lab, can each withdraw theory and continue only lab? Explain separately.',
        'List the questions have I asked in this chat?',
    ],
    'C2': [
        'Using the printed monthly rates, calculate four months of hostel gym use for a first-time member, including registration.',
        'Change that to three gym months and add two months of cooler charges. Show each component and one consistent total.',
        'Separate topic: two undergraduate library items are each nine days overdue. Calculate the fine.',
        'Correction: one library item is twelve days overdue. Keep the gym and cooler calculation separate.',
    ],
    'C3': [
        'My semester GPA is 3.20 and my CGPA is 1.99. Is my undergraduate merit scholarship guaranteed to continue? Explain the different roles of these GPAs.',
        'Correction: my CGPA is exactly 2.00. Does that prove every scholarship condition is satisfied and erase my previous warning history?',
        'Now use the undergraduate sponsorship rules to infer the maximum PhD sponsorship duration.',
        'Return to undergraduate financial assistance: give the printed contact person, email and extension.',
    ],
    'C4': [
        'What is the deadline?',
        'I mean final-examination rechecking. Give the procedure, deadline wording and refund condition. Does the refund sentence prove that no increase in marks makes a refund impossible?',
        'Compare DDC and CDC penalties in the Academic Rules and Student Handbook. If wording conflicts, can you guarantee which penalty I would receive?',
        'Explain when AI is permitted in Programming Fundamentals labs and the documented timing. Is the duration unambiguous? Can these PDFs confirm whether the policy changed yesterday?',
    ],
}
def hashes():
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (ROOT/'data/chats.sqlite3', ROOT/'data/manifest.json', ROOT/'data/embedding-cache.sqlite3')}
before = hashes()
(FOLDER/'baseline.json').write_text(json.dumps({'hashes': before, 'sequences': harness.SEQUENCES}, indent=2), encoding='utf-8')
try:
    print(harness.run('final-focused-20261020', set(harness.SEQUENCES), interval=10), flush=True)
finally:
    after = hashes()
    (FOLDER/'integrity.json').write_text(json.dumps({'before':before, 'after':after, 'unchanged': before == after}, indent=2), encoding='utf-8')
