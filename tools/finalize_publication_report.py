"""Assemble the bounded, evidence-backed report for this blocked release audit."""
import csv
import json
import re
import sys
from datetime import datetime,timezone
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from compass.config import Settings
from compass.benchmark import revision,normalized

def read(path):return json.loads((ROOT/path).read_text(encoding='utf-8'))
def write(path,value):(ROOT/path).write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8')

def main():
    folder=ROOT/'reports/publication';folder.mkdir(exist_ok=True)
    current=revision(Settings())
    bank=read('evaluation/publication/question-bank.json')['cases']
    local=read('reports/benchmark/publication-current-local.json')
    retrieval=read('reports/publication/retrieval-final-1.json')
    assert local['pipeline_revision']==retrieval['pipeline_revision']==current
    assert len(bank)==len(retrieval['results'])==187
    cited={c['id']:c for c in bank}
    by_ret={r['id']:r for r in retrieval['results']}
    by_local={r['id']:r for r in local['results']}
    current_review=read('reports/publication/publication-current-local-semantic-review.json')
    browser=read('reports/react-playwright.json')['stats']
    assert browser['expected']==24 and browser['unexpected']==0
    suite=next(ET.parse(ROOT/'reports/publication-python.xml').getroot().iter('testsuite'))
    assert suite.attrib['tests']=='97' and suite.attrib['failures']=='0' and suite.attrib['errors']=='0'
    system=read('reports/publication/system-checks/results.json')
    assert all(system['checks'].values())
    fresh=read('reports/publication/current-fresh-browser/results.json')
    assert fresh['pipeline_revision']==current
    memory=read('reports/publication/current-memory-final/workflows.json')['results'][0]
    assert memory['execution_status']=='COMPLETED' and all(memory['checks'].values())
    assert 'MEMORY_0' in memory['turns'][0]['answer'] and 'MEMORY_6' not in memory['turns'][0]['answer']
    required=[c for c in bank if c.get('retrieval_facets')]
    ret_pass=[c['id'] for c in required if by_ret[c['id']].get('retrieval_complete') is True and by_ret[c['id']].get('packed_complete') is True]
    ret_block=[c['id'] for c in required if by_ret[c['id']]['status']=='FAILED']
    mentors=[]
    for c in required:
        if not c['id'].startswith('M') or c['id'] not in ret_pass:continue
        t=by_ret[c['id']]['trace'];packed=set(t['packed_source_ids'].values())
        name=c['expected_answer'].split(';')[0]
        email=re.search(r'[\w.+-]+@[\w.-]+\.pk',c['expected_answer']).group()
        assert any(normalized(name) in normalized(d['passage']) and email in d['passage'] for d in t['retrieved'] if d['chunk_id'] in packed)
        mentors.append(c['id'])
    historical_names=['publication-baseline-all','publication-candidate-1','publication-candidate-2',
        'publication-candidate-2-interrupted-checkpoint','publication-candidate-3','publication-candidate-4','publication-final-1','publication-current-local']
    attempted=set();completed=set()
    for name in historical_names:
        for r in read(f'reports/benchmark/{name}.json')['results']:
            attempted.add(r['id'])
            if r['status']=='completed':completed.add(r['id'])
    pending=[c['id'] for c in bank if c['id'] not in by_local]
    fields=['id','difficulty','question','run_date','code_revision','dataset_fingerprint','model','status',
        'retrieval_all_facets','packed_evidence_complete','answer_correct','conditions_complete','citations_resolve',
        'citations_support_claims','abstention_or_clarification_correct','latency_seconds','reviewer','evidence_or_failure','retest_run']
    rows=[]
    for c in bank:
        ident=c['id'];ret=by_ret[ident]
        row=dict(id=ident,difficulty=c['difficulty'],question=c['question'],code_revision=current,
            dataset_fingerprint=local['dataset_fingerprint'],model=local['chat_model'],status='BLOCKED_CHAT_QUOTA',
            evidence_or_failure='Final-revision answer generation and semantic/citation-support review pending daily chat quota reset.')
        if ident in ret_pass:
            row.update(retrieval_all_facets=True,packed_evidence_complete=True,
                retest_run='retrieval-final-1 (retrieval only)',run_date=retrieval['started_utc'])
        if ident in ret_block:
            row.update(status='BLOCKED_CHAT_AND_EMBEDDING_QUOTA',
                evidence_or_failure='Embedding daily1000 quota blocked retrieval; chat daily500 quota also blocks generation.')
        if ident in by_local:
            actual=by_local[ident];manual=current_review['results'][ident]
            assert actual['status']=='completed' and all(manual[k] for k in ['answer_correct','conditions_complete','citations_support_claims'])
            row.update(status='PASS',answer_correct=True,conditions_complete=True,citations_resolve='N/A',
                citations_support_claims='N/A',abstention_or_clarification_correct=True,
                latency_seconds=actual['latency_seconds'],run_date=actual['started_utc'],
                reviewer=current_review['reviewer'],evidence_or_failure=manual['note'],retest_run='publication-current-local')
        rows.append(row)
    with (ROOT/'evaluation/publication/scorecard.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    write('evaluation/publication/pending-tests.json',dict(pipeline_revision=current,publication_ready=False,
        answer_generation_or_review_pending=pending,retrieval_blocked=ret_block,
        ordered_workflows_requiring_final_live_run=['W01','W02','W03','W04','W05','W06','W07','W09','W10'],
        app_check_blocked=['UI20'],reason='Provider daily chat500 and embedding1000 limits exhausted. No model/provider switch or billing change.'))
    app_evidence={
        'UI01':'24-test browser suite: fresh opening/reload, plus real isolated browser empty draft',
        'UI02':'Browser Enter/Send/Shift+Enter/blank-input tests and real immediate question rendering',
        'UI03':'Browser slow-answer duplicate suppression; HTTP idempotency regression',
        'UI04':'Real saved Gemini answer exact excerpts/PDF+printed labels in current browser; inline anchors and fixture formatting tests',
        'UI05':'Browser hover rename/delete/cancel/Escape tests on isolated chats',
        'UI06':'Browser search and long-list portal-menu tests',
        'UI07':'Browser switch/new draft during generation; HTTP saved-chat isolation',
        'UI08':'Browser network interruption and reconnect tests',
        'UI09':'Browser lost-acknowledgment and lost-creation-response idempotency tests',
        'UI10':'Actual daily quota in browser; isolated injected quota and timeout recovery tests',
        'UI11':'Actual owned child-process kill/restart with SQLite pending/completed records; fixture retry/discard tests',
        'UI12':'HTTP tests reject running-chat deletion and second unfinished send',
        'UI13':'Browser malformed payload and stale-GET tests',
        'UI14':'Browser failed-lazy-asset fallback, literal HTML/script nonexecution and KaTeX fixture tests',
        'UI15':'Chromium390px mobile/narrow desktop, keyboard dialog and reduced-motion tests',
        'UI16':'Actual current manifest/index reuse with embedding delegate that raises if invoked; user-data hash unchanged after server restart',
        'UI17':'Isolated actual HTTP app without index saves question and returns useful failure',
        'UI18':'Isolated missing-key app, authentication-error regression, actual dummy-invalid-key endpoint request',
        'UI19':'Browser+HTTP6000-character validation, blank rename and missing resource tests',
        'UI20':'Fresh real-provider browser answering blocked by daily quota; no answer-accuracy pass assigned'}
    app_rows=[dict(id=k,status='BLOCKED_DAILY_QUOTA' if k=='UI20' else 'PASS',evidence=v) for k,v in app_evidence.items()]
    write('reports/publication/application-checks.json',dict(pipeline_revision=current,checks=app_rows))
    workflow_rows=[]
    for i in range(1,11):
        ident=f'W{i:02}'
        if ident=='W08':status='PASS';note='Current HTTP run: eight seeded long turns retained; history estimate<=2500; original first-question lookup and complete question list correct; both final requests local, no model calls.'
        elif ident=='W10':status='BLOCKED_FINAL_RERUN';note='Earlier actual Gemini/HTTP sequence passed with policies+contacts and explicit live-availability limit. Current-revision generation rerun blocked.'
        elif ident=='W01':status='BLOCKED_PARTIAL';note='One live policy response completed, second follow-up hit daily quota; remaining steps not run. Do not count the sequence as passed.'
        else:status='NOT_RUN_QUOTA';note='Not executed as a complete live sequence. Component fixtures do not establish model semantics.'
        workflow_rows.append(dict(id=ident,status=status,note=note))
    write('reports/publication/conversation-checks.json',dict(checks=workflow_rows))
    summary=dict(generated_utc=datetime.now(timezone.utc).isoformat(),pipeline_revision=current,
        dataset_fingerprint=local['dataset_fingerprint'],publication_ready=False,
        python_tests_passed=97,browser_tests_passed=24,application_checks_passed=19,application_checks_blocked=['UI20'],
        historical_unique_questions_attempted=len(attempted),historical_unique_questions_completed=len(completed),
        current_question_responses_passed=len(by_local),current_questions_pending=len(pending),
        retrieval_required=len(required),retrieval_and_packed_facets_passed=len(ret_pass),retrieval_blocked=ret_block,
        mentor_rows_exactly_matched_in_current_packed_evidence=len(mentors),
        final_ordered_sequences_passed=['W08'],final_ordered_sequences_not_complete=[x['id'] for x in workflow_rows if x['status']!='PASS'],
        chat_daily_quota=500,embedding_daily_quota=1000,fresh_live_gate_passed=fresh['full_fresh_live_gate_passed'])
    write('reports/publication/final-status.json',summary)
    lines=['# Publication verification - blocked by free API quotas','',
        f'Generated {summary["generated_utc"]}. **NOT READY FOR PUBLICATION.** Current pipeline revision `{current}`; dataset fingerprint `{local["dataset_fingerprint"]}`.',
        '', 'The requested full final verification is incomplete. Failures were investigated and code fixes implemented, but the provider exhausted daily generation and embedding quotas. No paid billing, alternate provider/model, deployment or publishing was enabled. All recorded passes refer to executed checks; blocked cases have no semantic pass.',
        '', '## Results actually obtained','', '| Check | Result | Evidence |','|---|---|---|',
        '| Python regression suite | 97 passed, zero failures/errors | `../publication-python.xml` |',
        '| Built React + HTTP browser fixture | 24 passed, zero unexpected failures | `../react-playwright.json` |',
        '| Application workflow matrix | 19 passed; UI20 fresh answering blocked | `application-checks.json` |',
        f'| Current retrieval + evidence packing | {len(ret_pass)}/{len(required)} required document cases passed; M29 blocked | `retrieval-final-1.json` |',
        '| Actual source display | Saved real-Gemini excerpts and PDF/printed labels matched exactly; inline links worked | `current-fresh-browser/results.json` |',
        f'| Current prepared-question responses | {len(by_local)}/187 local/scope/history cases passed; {len(pending)} need final answering/review | `../../evaluation/publication/scorecard.csv` |',
        '| Ordered conversations | W08 passed on current code; W01 partial/quota; W10 passed earlier but needs final rerun; seven other live sequences not run | `conversation-checks.json` |',
        '| Final fresh policy-answer test | Attempted; provider quota blocked answer generation | `current-fresh-browser/results.json` |',
        '| Default app restart | Four existing conversations, every saved field/citation unchanged | `default-server-restart-after.json` |',
        '', 'The browser fixture uses a deterministic model double and isolated chat database. Its passes establish UI/HTTP behavior, not policy accuracy. Process/configuration tests use actual HTTP apps and actual process termination with controlled failure injection. The fresh browser attempt uses the real provider/index. Its successful recovery/rendering checks do not turn its blocked answer test into a pass.',
        '', '## Question and source review','',
        f'Across this audit\'s developmental revisions, {len(attempted)}/187 unique prepared question IDs were attempted and {len(completed)} produced at least one completed response. This is historical coverage, not a final-version pass. The largest full-run attempt stopped at97 cases:96 completed responses, one quota failure,90 unexecuted. Codex source comparison accepted95 of those96 completed responses; T04 had a discretionary-permission wording error, subsequently fixed and unit-tested. That run used an earlier revision. Failed/interrupted attempts remain available; they have not been silently replaced.',
        '', 'See `publication-candidate-4-questions.md` and `publication-candidate-4-semantic-review.json` for those individual historical reviews. Citation IDs, excerpts and page metadata of84 cited historical answers (172 displayed reference records) resolved to the prepared corpus. This is separate from judging whether every nearby clause is semantically supported. The final generated-answer citation audit is still pending.',
        '', 'All31 indexed sections are represented. Multi-part evidence checks were strengthened so a matching page alone cannot satisfy missing subparts. Two false-negative checks were corrected for existing PDF extraction spacing (`w eekends`, `indi rectly`) without changing document content or re-embedding. Current successful retrieval cases satisfy every declared facet and the4000-estimated-token packed-evidence budget. The four short follow-up retrieval checks reuse previously recorded real rewrites; new rewrite behavior belongs to the blocked conversation tests.',
        '', f'For {len(mentors)} of30 mentor cases, the expected mentor name and email were also checked together inside an actual packed passage. M29 remained blocked after an explicit retry; its earlier-revision result is not counted as a current pass. Coarse/anchor checks remain evidence-screening checks, not semantic certification of ungenerated answers.',
        '', '## Quota evidence','',
        '- Chat: provider429 `GenerateRequestsPerDayPerProjectPerModel-FreeTier`, value500 (`policy-quota-diagnostic.json`).',
        '- Embeddings: provider429 `EmbedContentRequestsPerDayPerUserPerProjectPerModel-FreeTier`, value1000 (`m29-provider-diagnostic.json`).',
        '- Short access probes briefly succeeded, but did not establish remaining capacity. The structured daily-quota violations are the decisive evidence. No further bulk generation was attempted after daily exhaustion was identified.',
        '', '## Fixes and retests','',
        '1. AI citation continuation: fixed cross-reference retrieval brings the prompt-image requirement into evidence. A real retest included it; current retrieval also passes.',
        '2. Procedural omissions: source-only guards retain rechecking deadlines/refund terms, retake authority, summer withdrawal deadline/non-refund, and shopping transport availability. Relevant real developmental retests and current regression tests passed.',
        '3. Misattached citations: explicit no-refund/countersign assertions are bound to their already-retrieved supporting passage. Unknown identifiers still fail validation. Real A12/F04 retests and regression checks verified the observed failures.',
        '4. Scope and clarification: other-campus facilities and postgraduate requests abstain; ambiguous standalone requests clarify; mixed policy/live questions can answer supported parts. The real mixed hostel test passed earlier; final rerun is blocked.',
        '5. Conversation memory: count separator tokens in the2500 estimate; do not guess the first saved marker from a truncated window. A local first-question lookup reads the stored transcript. Current W08 HTTP retest passes, including persistence of all eight seeded turns.',
        '6. FYP permission wording: preserve discretionary “may allow,” including normal next-semester graduation conditions. The fix is unit-tested; final live generation is pending.',
        '7. Compound retrieval: separate interest queries, twelve semantic candidates for linked lookups, lexical topic overlap, and priority packing retain debating/poetry/cybersecurity/startup evidence within six chunks. A second linked lookup retains hostel complaint escalation along with contact information. Actual embedding/Chroma retests passed.',
        '8. Windows report locking: bounded atomic-replacement retries preserve checkpoints. The94-case interrupted checkpoint remains saved separately. A filtered retrieval-runner variable collision was also corrected and its multi-case rerun executed.',
        '', 'No embedding model, dimensions, source selection, chunk boundaries, stored original PDFs or active vector collection was changed. The current simple LCEL RAG remains fixed retrieval + generation, without agents, grading models or corrective loops.',
        '', '## Remaining work before publication','',
        '1. After both free quotas reset, execute all187 responses on the unchanged final revision, then source-score accuracy, material conditions, retrieval and claim-level citation support. Use a new run name; old interrupted/earlier-revision reports are historical.',
        '2. Execute all ten ordered conversations on that revision, including the seven not executed live, W01\'s remaining steps and W10\'s final rerun. Do not substitute fixtures for live semantic results.',
        '3. Complete the fresh real-provider browser test (new lab-hours calculation, follow-up and library fine/topic change). The success branch is not verified while quota-blocked.',
        '4. Have a university-policy-aware human review high-impact financial/academic answers and the genuine DDC/CDC wording conflict, then perform the agreed joint live test with fresh human questions.',
        '', 'Exact pending IDs are in `../../evaluation/publication/pending-tests.json`; the187-row scorecard distinguishes retrieval-only success from missing answers. Chromium was tested; Firefox/Safari and a formal accessibility audit were not. This remains a single local workspace with no authentication or deployment. The index intentionally excludes new-admission/graduate/other-campus and selected local-listing material; do not advertise complete whole-PDF coverage. Narrow safeguards and a finite suite cannot guarantee every future answer.',
        '', '## Resume without buying anything','',
        'From the project folder, after AI Studio confirms both quotas have reset:', '', '```bash',
        'powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./verify-publication.ps1','```','',
        'The script runs regressions, a new full question run, ordered workflows and the fresh browser test. It stops when execution is incomplete/blocked and never declares semantic accuracy or publishes. Its syntax was checked; this complete script has not been run end-to-end because today\'s quotas are exhausted. New answers still require source-based scoring. The current app is running at http://localhost:8501 with all existing saved chats preserved.']
    (folder/'verification-report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
