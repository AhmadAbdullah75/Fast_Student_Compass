# Architecture

The default application is React + FastAPI. There is no Streamlit runtime, deployment layer, agent, corrective retrieval loop or local model download.

## Preparation

`sources.json` defines four source filenames, reviewed SHA-256 hashes, inclusive PDF page ranges, printed labels, campus/degree applicability and reviewed extraction overrides. The app reads `dataset/` first, with `data/originals/` as a compatibility fallback. Each original must match its reviewed hash.

`compass/ingestion.py` extracts and selects evidence, splits near paragraph/line boundaries (600 estimated tokens, 80 overlap), deduplicates matching scoped text and retains source pages. It embeds chunks separately using Gemini Embedding 2 at 768 dimensions and stores vectors in local Chroma. Cached document embeddings and the manifest allow unchanged ingestion without new embeddings. Old cache/collection versions can accumulate disk use.

## A question

1. React immediately displays the question and sends a client request UUID.
2. FastAPI validates and persists a pending turn, returns HTTP 202, and queues it on one answer worker. The UI polls the saved transcript.
3. Local routes handle recognized recall, recap and selected scope/clarification requests. Otherwise bounded recent history helps interpret a standalone retrieval question. Unresolved references can require clarification.
4. Query embedding and filtered similarity retrieval find applicable undergraduate/all-campus/CFD passages. Fixed linked queries support selected facets; at most six evidence chunks fit within a 4,000-estimated-token budget.
5. Gemini receives the question, evidence and bounded context. Prior assistant answers are conversation context, never new policy evidence.
6. Citation identifiers and targeted high-risk policy/contact/calculation checks run. The app saves a completed answer or sanitized recoverable failure.

This is polling rather than token-by-token generation streaming. Selected transient server errors have bounded transport retries; quota and answer validation do not trigger automatic full-pipeline regeneration.

## State and storage

- `data/chats.sqlite3`: durable transcripts, turn states, citations and optional diagnostics.
- `data/chroma/`: persistent evidence index.
- `data/embedding-cache.sqlite3`: cached document vectors.
- `data/manifest.json`: dataset/configuration fingerprint.

Full history remains readable. New policy reasoning uses up to six completed exchanges within 2,500 estimated tokens. Saved-question recall is separate; recap extracts selected old replies without verifying them anew. Request IDs and explicit retry/discard preserve recoverability without adding duplicate turns. Use one server process.

## Local API

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/health` | Readiness |
| GET / POST | `/api/conversations` | List/create chats |
| GET / PATCH / DELETE | `/api/conversations/{id}` | Load/rename/delete |
| POST | `/api/conversations/{id}/turns` | Save and queue question |
| POST | `/api/turns/{id}/retry` | Retry a recoverable turn |
| DELETE | `/api/turns/{id}` | Discard unfinished turn |

Interactive documentation: http://localhost:8501/api/docs.

## Code map

`frontend/src/App.tsx` handles chat state/UI; `api.ts` defines typed requests and response validation; `AnswerMarkdown.tsx` renders safe Markdown/math. `compass/web.py` adapts HTTP to the service and worker; `storage.py` owns SQLite; `rag.py` composes the pipeline; `policy.py` and `conversation.py` implement targeted evidence/intent handling; `models.py` connects to Google; `cli.py` exposes audit, prepare, preflight and ingest.
