"""Assemble current evidence without inferring semantic or publication approval."""
import argparse
import hashlib
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def read(relative, default=None):
    path = ROOT / relative
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def write(relative, value):
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def main(args):
    summary = read(f'reports/publication/{args.run}-summary.json')
    raw = read(f'reports/benchmark/{args.run}.json')
    revision = raw['pipeline_revision']
    if args.provenance:
        regression_provenance = read(args.provenance)
        assert regression_provenance['pipeline_revision'] == revision, 'Regression evidence must match core revision'
        for name, digest in regression_provenance['evidence_sha256'].items():
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, f'Regression evidence changed: {name}'
    workflow = read(f'reports/publication/{args.workflows}/workflows.json', {'results': []})
    judgments = read(f'reports/publication/{args.workflows}/workflow-semantic-review.json', {'results': {}})
    live = read(f'reports/publication/{args.live}/results.json', {})
    for evidence in (workflow, judgments, live):
        if evidence.get('pipeline_revision'):
            assert evidence['pipeline_revision'] == revision, 'Do not combine core revisions'
    corpus = {c['metadata']['chunk_id']: c for c in read('reports/prepared-chunks.json')['chunks']}
    provenance = []
    for sequence in workflow['results']:
        for turn in sequence.get('turns', []):
            for citation in turn.get('citations', []):
                source = corpus.get(citation['chunk_id'])
                if (not source or source['text'] != citation['excerpt']
                    or json.loads(source['metadata']['references']) != citation['references']
                    or turn.get('diagnostics', {}).get('packed_source_ids', {}).get(citation['id']) != citation['chunk_id']):
                    provenance.append({'sequence': sequence['id'], 'turn': turn['id'], 'citation': citation['id']})
    actual = {w['id']: w for w in workflow['results']}
    conversations = []
    for ident in [f'W{i:02}' for i in range(1, 11)]:
        row = actual.get(ident, {})
        review = judgments['results'].get(ident, {})
        passed = (row.get('execution_status') == 'COMPLETED' and review.get('status') == 'PASS'
                  and bool(row.get('turns')) and all(t['status'] == 'completed' for t in row['turns'])
                  and all(row.get('checks', {}).values()) and not any(p['sequence'] == ident for p in provenance))
        conversations.append({'id': ident, 'status': 'PASS' if passed else 'NOT_VERIFIED',
                              'turns_executed': len(row.get('turns', [])),
                              'note': review.get('note', 'No current semantic pass assigned.')})
    python = {k: 0 for k in ('tests', 'failures', 'errors', 'skipped')}
    for suite in ET.parse(ROOT / args.python).getroot().iter('testsuite'):
        for key in python:
            python[key] += int(suite.get(key, 0))
    browser = read('reports/react-playwright.json')['stats']
    system = read('reports/publication/system-checks/results.json')
    regressions = (python['tests'] >= 121 and not any(python[k] for k in ('failures', 'errors', 'skipped'))
                   and browser['expected'] >= 24 and not any(browser[k] for k in ('unexpected', 'skipped', 'flaky'))
                   and len(system['checks']) == 6 and all(system['checks'].values()))
    descriptions = [
        'Chromium fresh opening/reload and manual saved-chat selection',
        'Enter/Send immediate bubble; Shift+Enter; blank validation',
        'Slow generation duplicate suppression and HTTP idempotency',
        'Expanded excerpts, citation anchors, PDF/printed labels and safe formatting',
        'Hover rename/delete, cancel, Escape and isolation',
        'History search and long-sidebar menu positioning',
        'Switch/new draft during background generation',
        'Injected network interruption and recovery',
        'Lost acknowledgment and creation-response recovery without duplicate generation',
        'Injected quota/timeout recovery plus bounded transport-retry unit tests',
        'Owned process termination/restart preserves completed/pending turns; retry/discard',
        'HTTP controlled conflict for running-chat deletion/second send',
        'Malformed response and stale GET handling',
        'Blocked formatting asset fallback and inert script-like text',
        '390px/mobile and narrow layout, keyboard dialogs and reduced motion',
        'Real index reuse with embedding calls forbidden; process persistence',
        'Isolated missing-index failure preserves question',
        'Isolated missing-key failure and access-error regression tests',
        'Oversize/empty/missing-ID validation and malformed error handling',
        'Actual Gemini browser answers, follow-up/topic change, sources, recall and resume',
    ]
    app = {'pipeline_revision': revision,
           'mode': 'Chromium HTTP fixtures/system failures; UI20 separately uses the real provider',
           'python_evidence': args.python, 'browser_evidence': 'reports/react-playwright.json',
           'system_evidence': 'reports/publication/system-checks/results.json',
           'live_evidence': f'reports/publication/{args.live}/results.json',
           'checks': [{'id': f'UI{i:02}',
                       'status': 'PASS' if regressions and (i != 20 or live.get('full_fresh_live_gate_passed') is True) else 'NOT_VERIFIED',
                       'evidence': description} for i, description in enumerate(descriptions, 1)]}
    technical = (summary['question_suite_gate_met'] and all(c['status'] == 'PASS' for c in conversations)
                 and all(c['status'] == 'PASS' for c in app['checks']) and not provenance)
    times = [r['latency_seconds'] for r in raw['results'] if r['status'] == 'completed' and r.get('trace', {}).get('route') == 'document_rag']
    source_runs = raw.get('source_runs', [args.run])
    attempts = [item for name in source_runs for item in read(f'reports/benchmark/{name}.json')['results']]
    failures = [{'run': name, 'id': r['id'], 'error_type': r.get('error_type'), 'quota_scope': r.get('quota_scope')}
                for name in source_runs for r in read(f'reports/benchmark/{name}.json')['results'] if r['status'] != 'completed']
    state = {'generated_utc': datetime.now(timezone.utc).isoformat(), 'pipeline_revision': revision,
             'dataset_fingerprint': raw['dataset_fingerprint'], 'model': raw['chat_model'],
             'technical_release_gate_met': technical, 'publication_ready': False, 'questions': summary,
             'source_runs': source_runs, 'logical_case_attempts': len(attempts),
             'first_run_attempted': len(read(f'reports/benchmark/{source_runs[0]}.json')['results']),
             'first_run_completed': sum(r['status'] == 'completed' for r in read(f'reports/benchmark/{source_runs[0]}.json')['results']),
             'recorded_failed_attempts': failures,
             'observed_chat_server_failures': sum(len(r.get('trace', {}).get('transport_failures', [])) for r in attempts),
             'python': python, 'browser': browser,
             'regression_provenance': args.provenance,
             'application_checks_passed': sum(r['status'] == 'PASS' for r in app['checks']),
             'conversation_sequences_passed': sum(r['status'] == 'PASS' for r in conversations),
             'workflow_citation_provenance_failures': provenance,
             'fresh_browser_passed': live.get('full_fresh_live_gate_passed', False),
             'human_policy_review': 'NOT_PERFORMED', 'joint_user_live_test': 'PENDING',
             'completed_policy_latency': {'cases': len(times), 'median_seconds': statistics.median(times) if times else None,
                                          'maximum_seconds': max(times) if times else None},
             'active_blocker': args.blocker,
             'readiness_note': 'Independent policy-domain review and the joint unseen human-authored live test remain required. Finite tests do not prove universal accuracy.'}
    bank = read('evaluation/publication/question-bank.json')['cases']
    notes = read(f'reports/publication/{args.run}-semantic-review.json')['results']
    completed = {r['id'] for r in raw['results'] if r['status'] == 'completed'}
    retrieval_pass = {r['id'] for r in raw['results'] if r.get('retrieval_complete') is True and r.get('evidence_complete') is True}
    pending = {'pipeline_revision': revision, 'publication_ready': False, 'active_blocker': args.blocker,
               'answer_execution_pending_or_failed': [c['id'] for c in bank if c['id'] not in completed],
               'semantic_needs_fix': summary['needs_fix'],
               'semantic_review_pending': [c['id'] for c in bank if c['id'] not in notes],
               'retrieval_pending_or_failed': [c['id'] for c in bank if c.get('retrieval_facets') and c['id'] not in retrieval_pass],
               'semantic_reviewed': summary['semantic_reviewed'],
               'conversation_sequences_pending': [r['id'] for r in conversations if r['status'] != 'PASS'],
               'application_checks_pending': [r['id'] for r in app['checks'] if r['status'] != 'PASS'],
               'human_gates_pending': ['Independent policy-domain review', 'Joint fresh human-authored live test']}
    write('reports/publication/final-status.json', state)
    write('reports/publication/conversation-checks.json', {'pipeline_revision': revision, 'checks': conversations})
    write('reports/publication/application-checks.json', app)
    write('evaluation/publication/pending-tests.json', pending)
    print(json.dumps(state, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    parser.add_argument('--workflows', required=True)
    parser.add_argument('--live', required=True)
    parser.add_argument('--python', default='reports/publication-transport-python.xml')
    parser.add_argument('--blocker', default=None)
    parser.add_argument('--provenance', help='Optional current-core regression evidence hashes to verify')
    main(parser.parse_args())
