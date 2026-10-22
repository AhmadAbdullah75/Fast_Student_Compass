# Reproducible checks

The repository keeps a compact regression suite for storage, conversation routing, source preparation, API behavior and failure recovery. Historical transcript dumps, dated repair scripts and repeated evaluation banks are not needed to run the application and are no longer in the default branch.

## Python regressions

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

These tests do not call Gemini or need a key/prebuilt index. Fixtures use temporary databases and controlled models/embeddings. The dataset check reads the four included PDFs and verifies exact reviewed SHA-256 hashes. The source-path checks cover bundled-file preference, old-workspace fallback and traversal rejection.

## React browser workflows

After installing/building the frontend:

```powershell
cd frontend
npx.cmd playwright install chromium
npm.cmd run test:e2e
cd ..
```

Playwright starts `tests/web_test_server.py` at port 8502 with an isolated database and controlled answers. It covers immediate messages, loading, new drafts, history restoration, rename/delete, retry/idempotency, network failures, sources, safe rendering, keyboard controls and mobile layout. It does not establish Gemini answer accuracy. Port 8502 must be free; normal app use is at 8501.

## Local dataset reproduction

```powershell
.\.venv\Scripts\python.exe -m compass.cli audit
.\.venv\Scripts\python.exe -m compass.cli prepare
```

These require no provider access. The unchanged approved collection produces 108 chunks. Preparation writes page metadata and text to ignored `reports/prepared-chunks.json`. Verify hashes and source scope before replacing any PDF. Preflight and ingest are separate, explicitly invoked API-consuming operations.

## A short manual live check

With your own key, completed ingestion and the application running, use these as a small smoke check, not comprehensive semantic certification:

| Check | Expected behavior / evidence to inspect |
|---|---|
| Ask what happens when theory fails but lab passes; then reverse the outcome | Separate repetition rules and lab-only exception; Academic Rules PDF p.20. |
| Correct the case to passing both for grade improvement | Preserve the correction and the applicable theory/lab withdrawal restriction; p.20. |
| Ask the warning rule at CGPA 1.99, then exactly 2.00 | Preserve strict numeric boundaries and applicable warning-count reset conditions; pp.24-25. |
| Ask rechecking procedure, deadline and refund wording | Prescribed form/fee, “should” within seven days, refund if marks increase; pp.26-27. Do not invent an “only if” exclusion. |
| Ask two undergraduate library items nine days overdue, then replace with one item twelve days overdue | PKR 180 then PKR 120 at the printed PKR 10/item/day; Handbook p.33. Treat as supplied-input arithmetic, not a personal bill. |
| Ask an unqualified “What is the deadline?” in a new chat | Clarify rather than invent a procedure or date. |
| Ask to infer PhD sponsorship from undergraduate rules | Decline the excluded inference; do not claim it is absent from the original PDF. |
| Request earlier questions / recap | Reflect this saved chat; do not search policy PDFs for personal history. |
| Start a new chat, refresh, reopen the earlier chat | Empty draft by default; old messages remain available manually and isolated. |

Read each answer and its actual passages. Check answer meaning, conditions, retrieval coverage and citation applicability separately. Record failed attempts rather than silently retrying until one succeeds. On quota exhaustion, stop live requests and check project limits.

## Verification boundaries

Cleanup verification on 23 October 2026:

- A fresh Python environment installed the pinned runtime and optional test dependencies; `pip check` passed, and Streamlit was absent. PDF font-parsing support remains included.
- A separate clean Git checkout, with no `.env`, old dataset folder, index or prepared reports supplied, passed **78 Python checks** using that fresh environment.
- Its bundled-PDF preparation reproduced **108 chunks** and content fingerprint `b13c59ecc7ad2ccf99b339e99aeeb948cf46cb8d476dbe071bf6c6e01292d8d9` without API calls.
- Fresh `npm ci` and the production React build passed. All **25 Chromium workflow checks** passed with controlled answers, none skipped or flaky.
- The fresh built application served HTML/health and completed chat creation, rename and deletion in an isolated workspace.
- The existing development index was reused unchanged with an embedding implementation that forbids API calls.

These checks verify packaging and local behavior. They do not claim a fresh live Gemini answer evaluation or Google-account eligibility/quota validation.

Repository cleanup preserved the chat models, reviewed source content, chunking, applicability rules and answer pipeline. The new dataset location reproduces the same 108 chunks and active content fingerprint. Automated workflow passes are not a universal semantic proof; the full historical live question bank was not rerun for this packaging change. Independent high-impact university-policy review remains pending. See `LIMITATIONS.md`.
