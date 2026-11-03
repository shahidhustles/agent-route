# Relay UI verification

Verified 2026-11-02 in the T3 browser at localhost:3001, with the backend at 8765.

## What changed

The entry page, conversation layout, composer, navigation, run progress, feedback controls, and routing details now use a chat layout. assistant-ui owns the message history and running state. Agent events are AI SDK tool parts; routing and artifact data are message metadata. The existing eight artifact renderers remain in use.

Plain chat streams provider deltas and forwards earlier user and assistant turns. The thinking indicator remains visible while routing waits. The backend adds streaming to `/answer` and cancellation at `/runs/<id>/cancel`. New runs save their initial state so a backend restart can identify interrupted work. The proxy drains streamed usage and waits for in-flight requests before returning a run's cost, including after cancellation.

## Browser evidence

| Flow | Evidence |
|---|---|
| Entry | White canvas, Inter, grey sidebar, centered composer. Fresh reload defaults to Balanced and Agent off. |
| Plain chat | Two Cheap chats. The second recalled mango from the first. A MutationObserver captured visible text changing from `I will remember man` to `I will remember mango.` across successive updates. |
| Agent run | Spreadsheet run `20261102-122204-2360`, Cheap, GLM, passed. Steps appeared progressively, with the newest step running. |
| Shimmer | Browser computed `tw-shimmer-translate` on the running step's pseudo-element, about 1.94 s per cycle. |
| Artifact split | Live spreadsheet showed Jan/Feb/Mar sales 12/18/25 and doubled values 24/36/50. The artifact card reopened the panel. |
| Reply information | Live popup showed votes, runner-up, all four mode picks, estimates, sample counts, past runs, actual cost/time, and override controls. |
| Verdicts | Live spreadsheet was marked failed, then passed. Both backend updates succeeded. |
| Change agent/model | Live rerun `20261102-122330-848e` started as Data analysis on DeepSeek with the stored CSV. Backend SIGTERM interrupted completion. A later free stream fixture completed the full popup-to-rerun-to-artifact path and confirmed Cheap plus both overrides in the request. |
| Stop | Code run `20261102-122542-b4b5` stopped and its container exited. An additional accidental start `20261102-124550-5c12` stopped before any provider request and displayed `Stopped by you.` in chat. |
| New chat and history | New chat clears the conversation and artifact. Session-local conversations can be reopened without Assistant Cloud. Reload clears this session-only history. |
| CSV | Valid CSV attached and enabled Agent. Invalid row width produced `Too many fields: expected 2 fields but parsed 3`. Stored CSV was read during the live rerun. |
| Eight artifact types | Recorded code in CodeMirror, spreadsheet grid, analysis chart, document, slides, Mermaid SVG, map canvas and labels, and 3D canvas all rendered. Slides advanced to page 2. |
| DOCX | Browser completed a 42,419-byte download. Fetch independently returned 200, the DOCX MIME type, and ZIP file signature. |
| Phone | 390 x 844. Composer and controls fit. Artifact is a full-screen dialog, focus stays inside, Escape closes it. Page had no horizontal overflow. |
| Tablet | 900px width, no page overflow. |
| Keyboard | Focus outline visible. Artifact dialog traps focus. |
| Reduced motion | CSS disables animation and smooth scrolling under reduced motion; tw-shimmer also pauses its pseudo-element. T3 has no reduced-motion emulation control, so this was inspected in CSS rather than emulated. |
| Backend down | Stopped the backend, sent a message, and observed the inline backend-unavailable response. Restarted it afterwards. |
| Spend/provider stops | Free route tests confirm a readable stop response and no downstream paid call. The live cap was never lowered or deliberately reached. |

The free browser fixture replaced fetch only in the test tab and used real recorded artifacts. Reload removed it. It made no provider calls. Screenshot names without `recorded-rerun` show live runs or the actual entry/error screens.

## Automated checks

- `bun run typecheck`: passed.
- `bun test`: 50 passed, 235 expectations.
- Python suites with `.venv/bin` first on PATH: 118 passed. System Chrome closed its connection under Puppeteer, which failed `test_diagram_renders` and would have failed every live diagram run, so `agents/validators/js/puppeteer.json` now points at the installed Chrome headless-shell binary.
- Added tests cover SSE chunk boundaries, stream-to-tool mapping, rerun forwarding, readable spend/offline states, real streamed history and settled cost, pending usage after cancellation, and workspace-scoped container cancellation.
- Frontend design lint: zero failures. Warnings concern sidebar labels, code fonts, and composer/focus shadows.

## Spend and memory

Before paid testing, `online.jsonl` had 5 lines and `/status` reported $0.10840 spent with a $0.25 cap. Provider test requests added $0.0054591 across 14 provider requests. Final ledger total is $0.1138565; the cap remains $0.25. Modal infrastructure charges are not exposed by this ledger.

There were three agent attempts that reached the provider, plus one accidental extra start stopped before its first provider request. This exceeded the requested maximum of three starts. No further paid calls followed.

Moved the single added memory row into `data/memory/online.test-archive.jsonl`, leaving the original 5 rows. Restarted the backend after cleanup; it reports the original 4,909 memory records and one pre-existing UI record.

## Screenshots and visual review

- `screenshots/chat-entry.png`
- `screenshots/chat-running.png`
- `screenshots/chat-artifact.png`
- `screenshots/chat-info.png`
- `screenshots/chat-entry-phone.png`
- `screenshots/chat-scene-phone.png`
- `screenshots/chat-backend-down.png`
- `screenshots/chat-recorded-rerun.png`

Looked at the entry, running agent, artifact split, and information dialog against the requested ChatGPT reference. Fixed the phone dialog's independent CSS translate, removed the duplicate New Thread control, gave sessions prompt-based names, collapsed finished tool groups, restored neutral tokens, removed monospace artifact-card captions, and hid the Next.js development badge.

## Remaining limits

The live Change agent rerun did not finish because the backend exited. Its selections and CSV reuse were observed live; completion was verified with free recorded data. OS reduced-motion emulation and Modal billing were not available. Dark mode was left out.

## Retained old UI files

These files remain on disk but have no path from the mounted page. They only import one another where applicable.

- `components/app.tsx`
- `components/decision-panel.tsx`
- `components/recorded-view.tsx`
- `components/result-view.tsx`
- `components/run-progress.tsx`
- `components/term.tsx`

The unused starter `components/assistant-ui/elements/thread.aui.tsx` also remains. The old `/api/answer` compatibility route remains on disk. No commits were made. Router policies, model training, benchmark data, agent definitions, memory schema, and paper files were not changed.
