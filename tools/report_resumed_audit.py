"""Assemble the resumed audit from actual execution and explicit semantic review.

Does not infer semantic passes or authorize publication. Run publication_report
first; preserve failed runs and the source-review notes beside the raw traces.
"""
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import statistics
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'reports/publication'
RUN='publication-release-structural-20261016'

def read(path):
    return json.loads((ROOT/path).read_text(encoding='utf-8'))

def save(path,value):
    (ROOT/path).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

def main():
    summary=read(f'reports/publication/{RUN}-summary.json')
    raw=read(f'reports/benchmark/{RUN}.json')
    workflows=read('reports/publication/release-structural-20261016/workflows.json')
    review=read('reports/publication/release-structural-20261016/workflow-semantic-review.json')
    live=read('reports/publication/structural-live-20261016/results.json')
    revision=raw['pipeline_revision']
    assert revision==workflows['pipeline_revision']==review['pipeline_revision']==live['pipeline_revision']
    corpus={c['metadata']['chunk_id']:c for c in read('reports/prepared-chunks.json')['chunks']}
    provenance=[]
    for sequence in workflows['results']:
        for turn in sequence['turns']:
            for citation in turn.get('citations',[]):
                doc=corpus.get(citation['chunk_id'])
                if (not doc or doc['text']!=citation['excerpt']
                    or json.loads(doc['metadata']['references'])!=citation['references']
                    or turn.get('diagnostics',{}).get('packed_source_ids',{}).get(citation['id'])!=citation['chunk_id']):
                    provenance.append({'sequence':sequence['id'],'turn':turn['id'],'citation':citation['id']})
    cases={r['id']:r for r in workflows['results']}
    conversation=[]
    for ident in [f'W{i:02}' for i in range(1,11)]:
        row=cases.get(ident,{})
        judgment=review['results'].get(ident,{})
        passed=(row.get('execution_status')=='COMPLETED' and judgment.get('status')=='PASS'
            and all(t['status']=='completed' for t in row.get('turns',[]))
            and all(row.get('checks',{}).values()) and not any(p['sequence']==ident for p in provenance))
        conversation.append({'id':ident,'status':'PASS' if passed else 'NOT_VERIFIED',
            'turns_executed':len(row.get('turns',[])),'note':judgment.get('note','No semantic pass assigned.')})
    suites=ET.parse(ROOT/'reports/publication-structural-python.xml').getroot().iter('testsuite')
    python={k:0 for k in ('tests','failures','errors','skipped')}
    for suite in suites:
        for k in python:python[k]+=int(suite.get(k,0))
    browser=read('reports/react-playwright.json')['stats']
    system=read('reports/publication/system-checks/results.json')
    invalid=read('reports/publication/resumed-invalid-key-live-check.json')
    retrieval=read('reports/publication/retrieval-structural-20261016.json')
    assert retrieval['pipeline_revision']==revision
    bank=read('evaluation/publication/question-bank.json')['cases']
    required={c['id'] for c in bank if c.get('retrieval_facets')}
    retrieved={r['id'] for r in retrieval['results'] if r.get('retrieval_complete') is True and r.get('packed_complete') is True}
    retrieval_summary={'required':len(required),'passed':len(required & retrieved),
        'pending_or_failed':sorted(required-retrieved),
        'mode':'Actual embedding API and fixed retrieval queries; no generation. F-series reuse explicitly recorded historical standalone rewrites, not new rewrite verification.'}
    quota=read('reports/publication/resumed-final-quota-diagnostic.json')
    resources=read('reports/publication/resumed-resources.json')
    policy_times=[r['latency_seconds'] for r in raw['results'] if r['status']=='completed' and r.get('trace',{}).get('route')=='document_rag']
    policy_latency={'completed_policy_cases':len(policy_times),'median_seconds':statistics.median(policy_times) if policy_times else None,
                    'maximum_seconds':max(policy_times) if policy_times else None}
    regressions=(python['tests']==106 and not any(python[k] for k in ('failures','errors','skipped'))
        and browser['expected']==24 and not any(browser[k] for k in ('unexpected','skipped','flaky'))
        and all(system['checks'].values()) and invalid['passed'])
    app=read('reports/publication/application-checks.json')
    for row in app['checks']:
        row['status']='PASS' if regressions and (row['id']!='UI20' or live['full_fresh_live_gate_passed']) else 'NOT_VERIFIED'
        row['evidence']='Current 24-case Chromium HTTP-fixture suite, 106 Python regressions, process recovery checks; '+(
            'actual Gemini fresh browser answers/follow-up/recall/source expansion/resume.' if row['id']=='UI20'
            else row['evidence'])
    app.update(pipeline_revision=revision,mode='Fixture/system checks plus separately identified actual-Gemini browser test')
    save('reports/publication/application-checks.json',app)
    save('reports/publication/conversation-checks.json',{'pipeline_revision':revision,'checks':conversation,'citation_provenance_failures':provenance})
    technical=(summary['question_suite_gate_met'] and all(r['status']=='PASS' for r in conversation)
        and all(r['status']=='PASS' for r in app['checks']) and regressions)
    state={'generated_utc':datetime.now(timezone.utc).isoformat(),'pipeline_revision':revision,
        'dataset_fingerprint':raw['dataset_fingerprint'],'model':raw['chat_model'],
        'technical_release_gate_met':technical,'publication_ready':False,'questions':summary,
        'python':python,'browser':browser,'application_checks_passed':sum(r['status']=='PASS' for r in app['checks']),
        'conversation_sequences_passed':sum(r['status']=='PASS' for r in conversation),
        'workflow_citation_provenance_failures':provenance,'fresh_browser_passed':live['full_fresh_live_gate_passed'],
        'human_policy_review':'NOT_PERFORMED','joint_user_live_test':'PENDING',
        'retrieval_only':retrieval_summary,'provider_quota_diagnostic':quota,
        'completed_policy_latency':policy_latency,'resources':resources,
        'readiness_note':'Final answer-generation/conversation gates remain incomplete; daily generation quota is exhausted. Independent policy review and joint fresh human-authored live test also remain required.' if not technical else
            'Publication requires the documented independent policy review and joint fresh human-authored live test, even if technical gates pass.'}
    for filename in ('verification-report.md','final-status.json'):
        p=FOLDER/filename;backup=FOLDER/(p.stem+'-before-resumed-audit'+p.suffix)
        if p.exists() and not backup.exists():backup.write_bytes(p.read_bytes())
    save('reports/publication/final-status.json',state)
    pending=[c['id'] for c in read('evaluation/publication/question-bank.json')['cases']
        if c['id'] not in {r['id'] for r in raw['results'] if r['status']=='completed'}]
    semantic=read(f'reports/publication/{RUN}-semantic-review.json')['results']
    save('evaluation/publication/pending-tests.json',{'pipeline_revision':revision,'publication_ready':False,
        'answer_execution_pending_or_failed':pending,'semantic_needs_fix':summary['needs_fix'],
        'semantic_review_pending':[c['id'] for c in read('evaluation/publication/question-bank.json')['cases'] if c['id'] not in semantic],
        'retrieval_pending_or_failed':retrieval_summary['pending_or_failed'],
        'semantic_reviewed':summary['semantic_reviewed'],
        'conversation_sequences_pending':[r['id'] for r in conversation if r['status']!='PASS'],
        'application_checks_pending':[r['id'] for r in app['checks'] if r['status']!='PASS'],
        'human_gates_pending':['Independent policy-domain review','Joint fresh human-authored live test']})
    report=f'''# Resumed publication verification — 16 October 2026 (Pakistan)

**Technical release gate: {"MET" if technical else "NOT MET"}. Publication readiness: NOT CONFIRMED.** No deployment or publication was performed.

**Active execution blocker:** Google confirmed HTTP 429 `GenerateRequestsPerDayPerProjectPerModel-FreeTier`, limit **500** for the selected model. Its estimated retry time was `{quota.get('provider_estimated_retry_utc','not supplied')}` (approximately 05:00 Pakistan time on 16 October; provider estimate, not a guarantee). {len(pending)} prepared answers still require a completed final-revision response, and {sum(r['status']!='PASS' for r in conversation)} ordered sequences require completion. No paid fallback or billing change was made. The independent university-policy review and joint human-authored live test also remain outstanding.

Frozen revision `{revision}`; chat `{raw['chat_model']}`; dataset `{raw['dataset_fingerprint']}`. The 108-chunk index, embedding model, dimensions and splitting were preserved. Test chats used isolated databases.

| Final-revision check | Actual result |
|---|---|
| Prepared questions executed | {summary['executed']}/187 |
| Completed responses | {summary['completed']}/187 |
| Responses semantically reviewed | {summary['semantic_reviewed']}/187 |
| Answer/evidence/citation combined passes | {summary['passed']}/187 |
| Retrieval facets | {summary['retrieval']['pass']}/{summary['retrieval']['denominator']} |
| Packed evidence facets | {summary['packed_evidence']['pass']}/{summary['packed_evidence']['denominator']} |
| Separate fixed-query retrieval-only audit | {retrieval_summary['passed']}/{retrieval_summary['required']} |
| Citation provenance failures | {len(summary['citation_provenance_failures'])} |
| Ordered conversations | {state['conversation_sequences_passed']}/10 |
| Application checks | {state['application_checks_passed']}/20 |
| Python regressions | {python['tests']-python['failures']-python['errors']-python['skipped']}/{python['tests']} |
| Chromium fixture tests | {browser['expected']}/24; {browser['unexpected']} unexpected failures |
| Fresh real-provider browser check | {live['status']} |

The first complete resumed baseline produced 187 responses, with 181 combined passes and six answer defects (N024, N025, N027, N044, N056, N061). It retrieved and packed all 165 required evidence sets. Those failures remain in `publication-resumed-20261016-questions.md` and its raw benchmark. Interrupted intermediate runs are not full-release passes.

The retrieval-only audit uses the actual embedding API and the same persisted index/retrieval step. It does not generate answers. Its F-series cases explicitly reuse recorded standalone queries and therefore do not establish fresh follow-up rewriting. A source-facet pass is not an answer-quality pass.

All 30 mentor cases also had the exact expected name and email together in a packed passage; see [the association check](./mentor-packed-exact-match-structural.json). This checks evidence fidelity, not unexecuted generated answers.

The real-browser smoke questions are outside the 187-case bank but were reused across harness reruns. New provider responses were checked; this is not an independent unseen holdout set or the pending joint human live test.

## Fixes and actual retesting

- General withdrawal retrieval now includes the paired theory/lab rule and its passed-theory/failed-lab exception.
- Current-chat recall recognizes the previously failing paraphrase without a model request or policy citation requirement.
- Follow-up rewriting receives bounded student questions only, keeping incidental assistant checklists out of retrieval intent. Full bounded conversation remains available to answer generation. A later W03 regression was recorded and structurally corrected before this final revision; its complete actual-provider retest is retained with explicit provenance.
- Answers open with the substantive rule; misleading bare yes/no prefixes are removed. Remote-exam guidance preserves same-day/time restrictions.
- Source-only completion retains AI critical-evaluation and course-outline qualifications, and the student Turnitin-report service.
- Cost comparisons include first-payment arithmetic. Contacts preserve printed domains; only a unique same-mailbox address in cited evidence can repair a changed domain. Unknown/ambiguous mailboxes are rejected.
- The fresh-browser harness was corrected to select the first of multiple restored user messages. Its failed attempt is archived beside the successful rerun; this was a harness selector error, not an application pass.

No new splitting or embedding change was justified by the successful source-facet retrieval measurements. These finite-case checks do not prove universal retrieval or answer correctness.

## Evidence

- [Per-question answers and review](./{RUN}-questions.md), [metrics](./{RUN}-summary.json), [semantic notes](./{RUN}-semantic-review.json).
- [187-row scorecard](../../evaluation/publication/scorecard.csv), [pending gates](../../evaluation/publication/pending-tests.json).
- [Raw final responses and retrieval traces](../benchmark/{RUN}.json).
- [Final ordered HTTP conversations](./release-structural-20261016/workflows.json) and [review](./release-structural-20261016/workflow-semantic-review.json).
- [Retrieval-only trace](./retrieval-structural-20261016.json), [provider quota diagnosis](./resumed-final-quota-diagnostic.json), [unchanged original-source hashes](./resumed-source-integrity.json).
- [Application checks](./application-checks.json), [process/setup failure checks](./system-checks/results.json), [invalid-key endpoint check](./resumed-invalid-key-live-check.json).
- [Fresh real-Gemini browser check](./structural-live-20261016/results.json), [browser regressions](../react-playwright/index.html), [Python results](../publication-structural-python.xml).

## Limits and outstanding publication criteria

This is Codex source comparison, not independent university certification. A policy-domain human must review high-impact academic/financial answers and the conflicting DDC/CDC and medical-certificate provisions. The joint live test with fresh human-authored questions has not occurred.

The app covers 31 approved indexed sections, not every page of the four PDFs. Sources are dated snapshots; listed contacts, amounts and policies are not live-verified. Personal FLEX records, current availability, current calendars and official approvals remain unsupported. Free API quotas and network availability still apply.

There are no accounts or a multi-user privacy boundary: this is one local workspace. Submitted questions are durable, but an unsent composer draft is not a saved conversation. History sent to the model remains the most recent six completed exchanges within the estimated 2,500-token budget; full transcripts remain stored. Token budgets use estimates, not an exact provider tokenizer. Automated coverage is Chromium desktop/mobile simulation, not every browser or device.

Retrieval rewriting uses recent student questions to prevent incidental assistant content from changing the topic. References depending only on assistant details may require clarification. Known fixes have targeted/unit evidence, but the incomplete final full run cannot establish that every final-revision policy answer is correct.

Latency across the {policy_latency['completed_policy_cases']} completed final-revision document-policy cases: median {policy_latency['median_seconds']}s, maximum {policy_latency['maximum_seconds']}s. The raw overall median ({summary['median_latency_seconds']}s) includes zero-API local replies and is not a generation-speed measurement. Cold startup and browser/network rendering are excluded; these are observations, not speed guarantees.

Observed idle Python server RSS was {resources['idle_server_rss_mib']} MiB, excluding the browser and not a peak measurement. Selected on-disk directories are recorded in [resource measurements](./resumed-resources.json); those numbers are not a whole-project total. All four existing chats and 28 turns survived the final server restart unchanged; see [saved-data check](./current-user-data-after-restart.json).

Run locally with `powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./run.ps1` from the project folder and open http://localhost:8501. Keep billing disabled. No paid service or local model download was introduced.

After quota is available, run `powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./verify-publication.ps1` for a new complete execution cycle, then source-review every actual response. The current benchmark run contains a recorded A08 failure; resuming its name alone skips recorded IDs, including failures. Use a new run name for a full release rerun or an explicitly documented failed-case retest. Do not erase the failed attempt. The exact pending list is linked above.
'''
    (FOLDER/'verification-report.md').write_text(report,encoding='utf-8')
    print(json.dumps({'technical_release_gate_met':technical,'publication_ready':False,
        'questions_passed':summary['passed'],'workflows_passed':state['conversation_sequences_passed'],
        'application_checks_passed':state['application_checks_passed']},indent=2))

if __name__=='__main__':main()
