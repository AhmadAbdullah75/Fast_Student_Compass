"""Run the frozen 51-turn bank through the real HTTP/service lifecycle."""
import argparse
import json
from pathlib import Path
import publication_workflows as harness

ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',required=True)
    parser.add_argument('--ids',nargs='*')
    args=parser.parse_args()
    assert args.run.replace('-','').isalnum()
    spec=json.loads((ROOT/'evaluation/release-20261018/new-conversations-final.json').read_text(encoding='utf-8'))
    order=['C04','C08','C11','C07','C12','C10','C01','C02','C03','C05','C06','C09']
    harness.SEQUENCES={key:spec['sequences'][key] for key in order}
    print(harness.run(args.run,set(args.ids) if args.ids else set(order),interval=12))
