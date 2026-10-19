# Verification scope — 20 October 2026

The latest focused run recorded product fingerprint `0f74ddadcdad07a8` before repository documentation changes. It is historical evidence for that product revision, not a claim that every test bank passed after every change.

| Executed check | Result | Method |
|---|---|---|
| Ordered conversational cases | 15 completed and source-reviewed | Actual Gemini, retrieval, FastAPI and isolated SQLite |
| React live conversation | 5 completed; 10 workflow checks passed | Actual provider through Chromium and isolated backend |
| Targeted Python regressions | 59 passed | Offline fixtures/integration checks |
| Chromium workflow suite | 25 passed, none skipped/flaky | Controlled answer backend |
| Restart/configuration/index reuse | 6 passed | Actual child processes with failure-injection doubles |

Cases covered opposite theory/lab outcomes, corrections, malformed saved-question recall, gym/cooler and library arithmetic, GPA boundaries, warning records, postgraduate-inference refusal, financial assistance contacts, ambiguous deadlines, rechecking/refunds, disciplinary conflicts and AI permission/timing/recency.

Actual answers were compared with cited excerpts. Cited identifiers and reference metadata resolved to retrieved passages. No material failure or API quota error was observed in this focused execution. This is an agent source comparison, not independent university certification. No product changes were needed during the run.

Manifest and embedding-cache hashes remained unchanged. Tests used isolated chat databases. Separate live activity changed the production-chat hash during the run, so a byte-identical production database was not claimed or restored.

## Remaining limits

- The complete historical question bank was not rerun on the latest product revision.
- Independent review of high-impact university-policy interpretations remains pending.
- Public hosting, authentication, multiuser isolation and deployment are outside the agreed scope.
- Finite tests and targeted guards do not guarantee future semantic correctness.

Detailed local artifacts are generated under ignored `reports/publication/final-focused-20261020/` and `reports/publication/final-focused-browser-20261020/`. Raw transcripts, chat databases, original PDFs and credentials are intentionally not published. Reproduction tools and question materials are included in `tools/` and `evaluation/`; live reruns require approved local PDFs, a built index, provider access and available quota.

Conclusion: focused technical checks passed. Suitable for a local academic demonstration with disclosed limits; unconditional university-policy/public-service approval is not claimed.

## GitHub packaging verification

The source publication was checked in a separate local Git clone, using the existing Python dependency environment:

- Without private dataset files: the README's focused dataset-independent command passed **59 checks**.
- The full suite initially failed because approved PDFs/prepared chunks are intentionally absent from a bare checkout. These failures were retained as missing-prerequisite findings, not counted as passes. The README now explains this requirement.
- After supplying the approved PDFs and prepared chunks only inside that temporary local checkout: **515 Python checks passed** in 36.14 seconds, with no provider calls. This is not a fresh dependency-install test or a full live semantic qualification.
- Python and JSON publishable files parsed successfully. The tracked-file scan found no active `.env` secret or recognized credential pattern; generated data, reports, dependencies and builds were excluded.
- Commits were checked for one changed file each. README and ignore rules have separate descriptive commits; timestamps were not backdated.

No original PDFs, raw prepared corpus, API key or chat database is part of the GitHub upload. The privacy/data prerequisites therefore remain relevant when reproducing the tests.
