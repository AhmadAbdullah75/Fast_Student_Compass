# Live sample review - 15 October 2026

**Historical sample:** the results below describe the 15 October source-review sample, not the current release gate. See [the current verification report](../../reports/publication/verification-report.md) for the latest attempted, failed and pending cases.

Real configured Gemini API, existing index and RagPipeline; no fake answers. No browser rerun in this task. This is a 12-question sample, not full-suite approval. User chat database was not modified by this pipeline-only benchmark.

- 12/12 API completions; 12/12 answers correctly address the central requested issue.
- 8/12 satisfy the stricter completeness review; 4/12 have missing qualifications/checklist details. These are not counted as full passes.
- 11/12 have complete required retrieved and packed facets after strengthening the evidence checks; N025 misses the continuation on academic PDF53.
- Citations in the sample resolve to retrieved source records and support the claims actually made; this does not excuse omitted requirements.
- 79 Python regression tests passed again (22.84 seconds). Code tests are not semantic proof.

The initial coarse page-range metrics reported retrieval true in all12. Stronger facet review found the N025 gap. Raw results are preserved unchanged; current review records the stronger assessment. The question bank was strengthened after reviewing those traces, so use a new run name for a full run.

| Case | Completeness | Evidence facets | Review |
|---|---|---|---|
| N005 | PASS | PASS | Credit-weighted SGPA 25/8=3.125, rounded3.13, correct grade table and citation. |
| N006 | PASS | PASS | Correctly rejects highest-grade premise and uses latest D. Numeric grade points are supporting context, not asked for. |
| N015 | INCOMPLETE_CHECKLIST | PASS | Correct rechecking process and eligibility after missing viewing. Omits seven-day application limit and fee refund when marks increase. Core answer is correct; strict application-guidance checklist is incomplete. |
| N025 | INCOMPLETE_CHECKLIST | MISSING | Correct preparation versus quoted-content distinction. Missing prompt-image requirement on PDF53; that continuation was absent from retrieved and packed evidence. |
| N040 | PASS | PASS | Correctly rejects unconditional renewal; waiting list and recall qualification included. Restating all borrowing-table numbers is not required by this question. |
| N041 | PASS | PASS | Correct PKR60 calculation and rate. Ceiling does not change this small example and its omission is not a material error. |
| N042 | PASS | PASS | Correctly limits explicit VPN statement to faculty, without extending to undergraduates. |
| N053 | INCOMPLETE_CHECKLIST | PASS | Correctly rejects unlimited trips and states six per semester. Omits bus/driver availability condition; girls frequency is ancillary to this boys-specific question. |
| N056 | PASS | PASS | Correct one-time registration and first semester/month totals6000/3000. |
| N060 | PASS | PASS | All three requested office matches correct and grounded. Question asks office matching, so contact-address details in key are optional supporting context. Does not invent an actual live route. |
| N064 | PASS | PASS | Correctly distinguishes collection date from effective date. Extra provenance details are supporting context. |
| N067 | INCOMPLETE_CHECKLIST | PASS | Correctly presents medical-certificate section differences with both sources. Omits final committee/Director decision qualification despite having retrieved it. |

Next work before release: fix/verify N025 evidence continuation, improve material qualification coverage in N015/N053/N067, run all187 questions and30 workflows on final revision, then human review/fresh-question live test. No application code, chunking, models or index was changed in this question-authoring pass. All release scorecard rows remain NOT_RUN until the agreed full release run; this sample is recorded separately.

Current question difficulties: {'simple': 68, 'intermediate': 47, 'complex': 45, 'confusing': 27}.
