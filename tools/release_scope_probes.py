"""Explicit current-revision holdout probes; no production conversation writes."""
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from compass.benchmark import revision, quota_scope
from compass.config import Settings
from compass.ingestion import write_json
from compass.rag import RagPipeline, friendly_error

CASES = [
    ('honorific', 'How can I contact Ms. Nooria Fatima about financial assistance?'),
    ('mixed-scope', 'Compare the maximum internal sponsorship semesters for a bachelor student and a PhD student; explain what your indexed sources cover.'),
    ('external-transfer', 'I am applying from a different university, not seeking readmission. What percentage of my credits can transfer to FAST?'),
    ('ambiguous-fee', 'What is the fee?'),
]
settings = Settings()
path = ROOT / 'reports/publication/hardening-form-scope-20261017/results.json'
report = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {
    'pipeline_revision': revision(settings),
    'mode': 'Fresh Codex-authored direct-pipeline probes with actual provider; not independent human holdout',
    'results': [],
}
assert report['pipeline_revision'] == revision(settings)
pipeline = RagPipeline(settings)
for ident, question in CASES:
    if any(row['id'] == ident for row in report['results']):
        continue
    started = time.monotonic()
    row = {'id': ident, 'question': question}
    try:
        row.update(asdict(pipeline.answer(question, [])))
    except Exception as exc:
        row.update(status='failed', error=friendly_error(exc), error_type=type(exc).__name__, quota_scope=quota_scope(exc))
    row['latency_seconds'] = time.monotonic() - started
    report['results'].append(row)
    write_json(path, report)
    print(json.dumps(row, ensure_ascii=False), flush=True)
    if row['status'] == 'failed' and 'quota' in row['error'].lower():
        report['stop_reason'] = 'quota'
        write_json(path, report)
        break
    time.sleep(max(0, 10 - (time.monotonic() - started)))
