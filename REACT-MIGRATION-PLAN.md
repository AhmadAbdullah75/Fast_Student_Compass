# React migration plan

Inspection and research completed before implementation, 15 October 2026.

## Findings

The existing Streamlit app calls `ChatService` directly; there is no HTTP API. `ChatStore` owns durable SQLite conversations and pending/failed/completed turns. Session state is only the selected-chat cursor. `ChatService._run` loads the selected conversation's preceding turns, invokes the fixed LCEL RAG pipeline, validates citations, and saves answers, provenance, and diagnostics. Generation is synchronous. Existing conversations must remain in `data/chats.sqlite3`; neither originals nor the persisted Chroma collection needs migration.

## Decisions

- React + TypeScript + Vite in `frontend/`; Lucide icons, local bundled font, Markdown/GFM and math rendering. Forest sidebar, off-white canvas, sage accents, responsive welcome cards, fixed composer and restrained motion with reduced-motion support.
- Thin FastAPI adapter; unchanged RAG/model/retrieval workflow. Serve built React assets and API from one localhost origin at port 8501; Vite development proxy is optional.
- Empty draft on every full page opening, including refresh. Do not automatically select an old chat or create empty database rows on refresh. Save a conversation when its first message is sent.
- Optimistically display the user message before awaiting the API. Persist the turn before running generation in a bounded worker. Poll saved turns until complete. Show actual loading, not simulated token streaming; answers become visible only after existing citation validation.
- Add an optional unique client request ID to SQLite turns for safe resend after a lost response. Retry an existing turn; never insert a second question. Interrupted jobs survive as pending turns and can be explicitly retried after restart.
- Sidebar: New Chat, search, date groups, hover/focus/touch menu, rename/delete dialogs. User bubbles on the right, assistant on the left, both timestamped. Expandable source excerpts and an optional technical-details panel.
- Errors: retain optimistic questions on network failure, reconnect without changing IDs, reject duplicate submissions and empty/oversized input, block deleting a running conversation, expose retry/discard for failed or interrupted work. Protect against stale chat-load responses.
- No new accounts, deployment, paid service, model weights or index rebuild.

## Validation

Run existing Python regression tests plus API tests against isolated SQLite. Run Playwright against the actual built React UI and a controlled real HTTP backend to verify immediate rendering during a delayed answer, Enter/Send, duplicate prevention, loading, sources, timestamps, menus, persistence, new-chat refresh behavior, chat switching during generation, network interruptions, malformed responses and recovery. Capture desktop/mobile screenshots and inspect layout. Separately test the real Gemini-backed API in a temporary chat, then delete only that test chat. Record exactly which checks passed and any limitations.

## Research

- [Vercel chatbot reference](https://vercel.com/templates/other/chatbot): conversation navigation and source presentation; visual reference only, not a provider migration.
- [React effects](https://react.dev/reference/react/useEffect): cleanup and guarding stale async results.
- [WAI dialogs](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/), [menu buttons](https://www.w3.org/WAI/ARIA/apg/patterns/menu-button/): keyboard and focus behavior.
- [FastAPI static files](https://fastapi.tiangolo.com/tutorial/static-files/), [background tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/): serving React and keeping long work out of the request response path.
- [Vite guide](https://vite.dev/guide/): lightweight frontend build, Node runtime requirements.
