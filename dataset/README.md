# Approved reference dataset

These four PDFs are bundled so a Git clone can reproduce the reviewed source collection. They are the unchanged originals used by `sources.json`; no API key, user conversation or vector database is included.

| File | Reference | Document date metadata |
|---|---|---|
| [Academic_Rules_Handbook_2026.pdf](Academic_Rules_Handbook_2026.pdf) | Undergraduate Academic Rules and Regulations 2026 | 2026-06 |
| [Student_Handbook_2026.pdf](Student_Handbook_2026.pdf) | Student Handbook 2026 | 2026-06 |
| [Student-Guide-Book-2026.pdf](Student-Guide-Book-2026.pdf) | CFD Student Guide Book 2026 | 2026 |
| [FAST_Financial_Assistance_Scholarships.pdf](FAST_Financial_Assistance_Scholarships.pdf) | Financial Assistance / Scholarships (webpage snapshot) | Snapshot; see sources.json |

The PDFs are university reference material, not policy authored by this chatbot. Source URLs not recorded in `sources.json` are unknown; none are invented. A document/publication or collection date is not proof that a rule remains current. No new open-content license or official endorsement is asserted.

## Use

The application automatically reads this folder. From the repository root after installing Python dependencies:

```powershell
.\.venv\Scripts\python.exe -m compass.cli audit
.\.venv\Scripts\python.exe -m compass.cli prepare
```

These steps are local and require no API key. With your own configured key, run preflight and ingest as explained in the main README. Approved section ranges, campus/degree scope, printed-page labels and reviewed OCR/table overrides live in `sources.json`. The original PDFs include material outside the approved indexed scope; availability of a full PDF does not expand the chatbot's supported coverage automatically.

## SHA-256 verification

```text
4cfee3e191b84aeb9168f17656c7642212ff52b90f2780d028b33c154aa74b62  Academic_Rules_Handbook_2026.pdf
717eb4b8d37e50185ffe952735c08ef19edd16074d547f10ebd22cf23da67c4d  Student_Handbook_2026.pdf
3e7a66e1020b8a6693e749f9221a3113aae87f679aea3fb43c7be0e873018d33  Student-Guide-Book-2026.pdf
13d5a2cd4b23ff10d67dae97b069afffb0e22d8918457f42cc32bbb2adee2630  FAST_Financial_Assistance_Scholarships.pdf
```

The app verifies these reviewed hashes before preparation. Do not replace a file or change its hash without inspecting extraction, tables, scope and page mappings. Current approved preparation produces 108 chunks. Existing workspaces can still use `data/originals/` only when the corresponding bundled file is absent; the bundled version takes precedence.
