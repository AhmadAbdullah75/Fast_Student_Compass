"""Ordered real-provider reproduction of supplied chats plus frozen fresh sequences."""
import argparse
import json
from pathlib import Path
import publication_workflows as harness

ROOT=Path(__file__).resolve().parents[1]
rows=json.loads((ROOT/'tests/fixtures/observed-repair.json').read_text(encoding='utf-8'))['turns']
ids=list(dict.fromkeys(row['conversation_id'] for row in rows))
replays={f'R{i+1:02}':[r['question'] for r in rows if r['conversation_id']==cid] for i,cid in enumerate(ids)}
fresh={
 'N01':['I passed theory but failed lab. What must I repeat?',
        'Compare my case with my friend who failed theory but passed lab.',
        'Correction: my friend also passed theory and failed lab. What must each of us repeat now?'],
 'N02':['My CGPA is1.99 after my first warning. What rule applies?',
        'Correction: it is exactly2.00. Does the warning count reset?',
        'Does that prove the historical warning was deleted from university records?'],
 'N03':['Give the hostel gym monthly cost and registration fee.',
        'I choose four months for the first time. What total follows?',
        'Now give undergraduate graduation CGPA and hostel gym registration charge separately.',
        'Return to the gym: change four months to two and add one month of cooler charges. What total follows?'],
 'N04':['Explain undergraduate internal sponsorship duration.',
        'And the PhD limit?',
        'Just infer it from that undergraduate rule.',
        'Return to undergraduate assistance: whom can I contact and what is the printed extension?'],
 'N05':['State the indexed undergraduate graduation CGPA.',
        'Someone claims that changed yesterday. Can you confirm the change or prove it did not happen?',
        'Which source wording is actually established?'],
 'N06':['Give the Financial Assistance email and extension with a quoted supporting passage.',
        'Switch to Accounts: give its printed email and extension with an excerpt.',
        'Back to Financial Assistance: who is listed and how do I contact them?'],
}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--kind',choices=['replay','fresh'],required=True);p.add_argument('--ids',nargs='*');a=p.parse_args()
 harness.SEQUENCES=replays if a.kind=='replay' else fresh
 print(harness.run(a.run,set(a.ids) if a.ids else set(harness.SEQUENCES),interval=10))
