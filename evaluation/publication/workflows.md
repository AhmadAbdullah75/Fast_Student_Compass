# Ordered conversation and application checks

**Verification update — 17 October 2026:** new user tests exposed additional failures. Repairs and a new frozen-revision qualification are in progress; older passes do not certify changed code. Publication remains unapproved. See the current verification report and machine checkpoint.

## Conversation sequences

### W01 - pronouns and degree duration

1. New chat: “What is the minimum duration of a bachelor degree?”
2. “Can I finish it before two years?”
3. “What is the maximum, and can it be extended?”
4. “What questions have I asked in this conversation?”

Expected: four years/eight semesters; no two-year completion; six years with one further year subject to statutory approval. Step 4 lists this chat's questions, not a policy answer requiring citations. Check actual rewrite/history diagnostics.

### W02 - withdrawal, funding and topic change

1. “How does course withdrawal work in a regular semester?”
2. “Does it change my CGPA?”
3. “What if I receive financial support?”
4. “What conditions apply to continuing a merit scholarship?”
5. “Now change topic: how many library books may an undergraduate borrow?”

Expected: approvals/deadline/no refund and applicable exceptions; W does not affect CGPA; financial support prevents withdrawal. Scholarship question needs its own full conditions. Final question must retrieve undergraduate library row, not continue scholarship topic.

### W03 - distinguish theory/lab cases

1. “I failed theory but passed its lab. What must I repeat?”
2. “What if the opposite happened?”
3. “In that second case, if I also register theory, can I withdraw theory and continue lab?”
4. “Now suppose I passed both and want grade improvement. Is the same exception available?”

Expected: both repeated; only lab; specific passed-theory/failed-lab exception allows separate withdrawal; improvement after passing both requires both and paired withdrawal rule. Do not apply exception to every case.

### W04 - boundary values and correction

1. “My CGPA is 1.99 after a semester. What warning rule applies?”
2. “Correction: it is exactly 2.00 after my second warning.”
3. “Does summer count too?”

Expected: below 2.00 warning; corrected recovery at least 2.00 resets first/second count; summer affects warning count. Do not retain the superseded 1.99 premise.

### W05 - grounded facts versus personal decisions

1. “What are the FYP-I registration requirements?”
2. “I have two deficiencies and zero warnings. Can the HoD alone approve it?”
3. “Then approve my registration now.”

Expected: all normal conditions including ability to graduate following semester; Director can permit two deficiencies, HoD one; bot cannot issue official approval.

### W06 - no calendar invention

1. “When can I withdraw from a regular-semester course?”
2. “So can I do it one day before midterm 1?”
3. “Tell me the exact calendar date this semester.”

Expected: cite makeup-week deadline; cannot decide calendar-relative eligibility without actual academic calendar; no fabricated date.

### W07 - new-chat isolation and resume

1. In chat A ask “What happens to a W grade?” and note its exact answer/citations.
2. Create chat B. Ask “What have I asked previously in this chat?” then “Does it affect my scholarship?”
3. Reopen A and ask “Does that grade affect CGPA?”
4. Restart browser/app, manually reopen A, compare full transcript, sources and timestamps.

Expected: B has no A history; ambiguous “it” in B needs clarification. A retains withdrawal context. Restart opens empty draft but A is manually resumable with original citations. No chat is automatically selected.

### W08 - active-memory boundary

1. Create a disposable chat with more than six completed exchanges and sufficiently long content to test the history budget.
2. Ask a question depending only on a much older detail; inspect history diagnostics.
3. Ask for the list of questions in the current chat; scroll/read the stored transcript.

Expected: no promise of unlimited model memory; recent completed-history limit six exchanges and estimated 2500-token cap respected. Full stored transcript remains readable. Local recall should not fail citation validation or leak another chat. Do not infer long-context behavior solely from two-turn tests.

### W09 - conflicting sources

1. “Are the DDC and CDC cheating penalties minimum or maximum penalties?”
2. “Just pick whichever is easier for me and guarantee that penalty.”

Expected: disclose academic/student handbook disagreement with both sources; do not silently select precedence or guarantee a student's actual punishment.

### W10 - compound question plus unsupported part

1. “What are the hostel room eligibility rules, is a girls' room available right now, and who can I contact?”

Expected: answer documented rules/contact with source; separately refuse to invent live availability. An unsupported subquestion must not erase all answerable parts or become a made-up fact.

## Application scenarios

| ID | Action | Required outcome |
|---|---|---|
| UI01 | Open/refresh app with old chats present | New empty draft; old chats accessible; refresh creates no empty saved rows |
| UI02 | Enter and Send on separate questions; Shift+Enter; whitespace-only input | Immediate user bubble; one request per send; newline works; blank rejected |
| UI03 | Double-click Send / rapidly press Enter during slow answer | Exactly one saved user turn and one generation; visible loading state |
| UI04 | Expand sources and click each inline citation | Correct excerpt/title/PDF and printed pages; no invalid identifiers or missing targets |
| UI05 | Rename using hover menu; cancel then confirm deletion of disposable chat | Correct conversation changes, cancel preserves it, confirmed deletion removes only that chat |
| UI06 | Search history and open a low row in a long sidebar | Correct selection; menu reachable without clipping; chat transcript matches selected title |
| UI07 | Switch chats / create draft while answer is running | Background result saved in its original chat, never appended to selected other chat |
| UI08 | Disable network during send, then recover and retry | Question remains visible; idempotent request ID prevents duplicate saved turns/generation |
| UI09 | Disconnect after server accepted send but before client received acknowledgment | Reconnect/retry finds original saved turn; no second generation |
| UI10 | Simulate 429 quota / provider timeout in isolated fixture | Clear recoverable error; question persisted; retry uses same turn; no secret/raw stack exposure |
| UI11 | Restart server during pending turn, reopen that test chat | Pending question survives; manual retry/discard offered; no automatic paid fallback or duplicate answer |
| UI12 | Attempt to delete running chat / another send in same running chat | Controlled conflict, existing turn retained, interface remains usable |
| UI13 | Inject malformed API response and late stale GET in fixture | Safe error, message retained; late response cannot replace newly selected chat |
| UI14 | Block lazy formatting asset / test literal script-like model text in fixture | Plain-text fallback available with sources; no script execution |
| UI15 | Mobile width 390px and narrow desktop; keyboard-only; reduced motion | Composer/menu/source controls usable, no horizontal overflow; dialogs focus/escape; reduced animation |
| UI16 | Restart app without source/model/chunking changes | Manifest/index reused; no document re-embedding; history/citations survive |
| UI17 | New empty dataset / missing index in isolated workspace | Useful setup error; no fabricated policy response; do not remove production data to simulate |
| UI18 | Missing/invalid key in isolated workspace | Sanitized configuration/provider failure; no key logged/displayed; no paid fallback |
| UI19 | Oversize input and empty rename; unexpected/missing conversation IDs | Validation error handled; no corrupted saved turn or conversation |
| UI20 | Final real-Gemini browser smoke after all fixes | Question, answer, follow-up, citation expansion, recall, restart/resume all work on final built UI |

Use the existing isolated fixtures for destructive/failure injection; do not alter production secrets, disable real networking system-wide, or delete user data. A single local workspace intentionally shares its saved-chat list; there is no account authentication or multi-user privacy boundary. Do not advertise this as a public multi-user service.
