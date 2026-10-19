# CFD Student Compass - before-publication test pack

**Verification update —18October2026:** complete pre-publication verification is in progress at the user's new request. Earlier focused approval is historical. Follow `reports/publication/CONTINUE-TESTING.md` and `reports/publication/release-complete-20261018/checkpoint.json`. No publication readiness is claimed.

Use [the continuation instructions](../../reports/publication/CONTINUE-TESTING.md) for exact checkpoint commands. Do not combine different core revisions; retain every failed attempt.

This pack is a test specification, not a certificate of universal accuracy. It contains **187 questions: 79 existing regressions and 108 additions**, covering all **31 indexed sections** of the four sources. Expected answers are source-checked by Codex; a university/domain reviewer has not independently certified them. The PDFs contain material outside the approved index. See `coverage.md` before making coverage claims.

## Files

- `questions.md`: student test sheet, without answers. Start a new chat for each standalone question. Cases with history show their required context.
- `answer-key.md`: minimum correct behavior, PDF evidence locations, and provenance for every question. This is a fact checklist, not an exact-match answer string.
- `coverage.md`: every indexed section mapped to question IDs, source hash verification, and excluded topics.
- `scorecard.csv`: historical187-question results; these are not qualification for the latest revision. Current execution and pending IDs are recorded in `pending-tests.json` and the current report.
- `question-bank.json`: full machine-readable bank, including clarification and adversarial tests.
- `benchmark-compatible.json`: the earlier177-case subset, retained for compatibility. The full release run now uses `question-bank.json` to execute all187, including X-series outputs that require manual judgment.
- `workflows.md`: ordered conversation and application scenarios, including recoverable failures.
- `live-sample-review.md`: actual results of twelve new live pipeline checks, including four incomplete-checklist findings. Raw answers/traces are preserved separately. This is not a complete release run.

## Run the app and test

From the project folder in Git Bash:

```bash
source .venv/Scripts/activate
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./run.ps1
```

Open http://localhost:8501. For live manual testing use the question sheet, then compare with the answer key. Do not paste expected answers into the chatbot: that contaminates the test. Use a separate test conversation and avoid deleting existing personal conversations.

For a resumable terminal run against the actual configured Gemini API:

```bash
python -m compass.benchmark --run publication-release-1 --suite evaluation/publication/question-bank.json --interval 7
```

This consumes free API quota. Run sequentially and keep billing disabled. Results are checkpointed under `reports/benchmark/publication-release-1.json`. Resuming skips previously recorded IDs, including failed attempts; use a new run name for explicit failure retests. After a code/index/suite change, use a new full run; resume an unchanged checkpoint for unexecuted cases and retest recorded failures under a separate name. Do not change suite/code/index during a resumable run. A crash or provider error is a failed attempt, not permission to overwrite the result. The benchmark records diagnostics; it does **not** automatically certify answer accuracy. API availability and raw request success are different from correctness.

Useful independent regression commands:

```bash
python -m pytest -q
cd frontend
npm run build
npx playwright test
```

Browser fixture tests exercise the built UI and HTTP adapter with a model double. They do not establish Gemini's policy accuracy. Terminal semantic benchmarks exercise the real retrieval/answer pipeline but do not establish browser behavior. Both are needed.

## Score each policy question independently

1. **Retrieval:** inspect Response details/diagnostics or benchmark trace, not just the visible citation titles. Check that the selected six chunks contain every required fact, exception, authority and applicability. Record a failure when an essential facet is absent even if the model guesses correctly.
2. **Packed evidence:** verify required passages actually reached the answer prompt within the evidence budget. A relevant result discarded from the prompt does not count as successful grounding.
3. **Accuracy:** compare the generated answer with the key and original source. Check every numeric threshold, unit, date scope, negation, exception and approving authority. Extra unsupported advice can fail an otherwise correct answer.
4. **Citations:** each displayed identifier must resolve to retrieved evidence with correct PDF/printed page metadata. Then check that the passage supports the nearby claim. A real document title alone is insufficient.
5. **Unsupported/ambiguous requests:** explicit limits, clarification or qualified partial answer are appropriate. No invented personal records, current availability, official approval, excluded-campus details or current dates. A clarification question need not have a policy citation. Source-grounded corrections to a false premise do require evidence.
6. **Reliability:** save latency, provider failures, retry behavior and review notes. Count API failures separately and in the overall completion denominator; do not count only completed answers to hide failures.

For broad multi-page ranges in the key, automatic page presence is only a coarse screening check. Human review must inspect the exact passage and all required facts. Do not treat a page match or `retrieval_complete=true` as semantic proof.

## Release gate

- Run every bank case and ordered workflow; no NOT_RUN, unreviewed or unexplained failure can be called verified.
- Report first-attempt completion, retrieval, packed-evidence, semantic accuracy, citation correctness and abstention/clarification separately, with counts and denominators. Keep historical failed attempts.
- For this finite release suite require every critical policy condition, calculation, privacy/isolation check and failure-recovery scenario to pass; fix and rerun failing cases plus related regressions. The earlier 90% development threshold is not a license to leave known harmful answer errors.
- Repeat the full agreed release suite on the final code/index/model revision after fixes; targeted reruns alone are not a final full-run result.
- Have a human familiar with university policy review high-impact financial/academic decisions and all source conflicts. The source, not fluent phrasing, determines correctness.
- Ask fresh questions that are not in this development bank during the final joint live test. Keep some human-authored cases unseen during tuning.
- Record scope exclusions and snapshot dates in the project description. Resolve scope expansion decisions before advertising whole-document coverage.

Passing the finite release gate supports a bounded readiness statement; it cannot promise that every future question will be answered correctly. No publication has been performed by preparing this pack.
