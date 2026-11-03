# Final browser QA

Tested 2026-11-01, starting at 08:32 UTC, in the T3 preview browser against `http://localhost:3001`. No browser fallback was needed. This is a test report, not a certification of every possible input.

Verdict: the app supports a rehearsed demo, but I would fix the major findings before an unrestricted live demo or before describing the UI as verified in the paper. All eight original agent tasks completed live and passed their format contracts. That does not mean the router always chose correctly or that a contract pass established task correctness. No blocker was found. Six confirmed findings are major: F01-F05 and U01. U06 and U07 remain unconfirmed in the narrower senses stated in their entries. The paper's earlier offline benchmark results were not re-evaluated here.

App source, agent prompts, deployment, plan checkboxes, and existing git changes were left alone. The only deliberate repository writes were this report and its screenshots. Runs, ledgers, and online memory were written by the app as part of testing. No commits or installs were made. The memory backup made before the first run is `/tmp/online.before-qa.jsonl`. Do not use the resulting online memory for paper measurements without removing these QA runs, especially the deliberately invalid Python tests.

## Coverage

| Area | Status | What was exercised and limits |
|---|---|---|
| 1. Eight live agents | Tested | UI tasks for code, spreadsheet, data-analysis, docx, slides, diagram, map, scene-3d. Both CSV agents received an attached file. Inspected artifacts and matching blocks. Sorted the grid, navigated all three slides and back, panned the map with its keyboard control and zoomed, dragged to orbit the 3D cube, downloaded and opened the DOCX, copied raw code. |
| 2. Routing | Tested | Selected cheap, balanced, fast, accurate on the same document task. Checked their tables and explanations. Tested vague `help`, ambiguous slides, a task no agent can perform, Hindi, pasted Python, HTML/script tags, and a 30,053-character prompt. Selected Slides from the below-0.5 picker. Wrong choices and the limited override are findings below. |
| 3. Just answer | Partly tested | Four real UI calls for 17 x 19, all returned 323. Verified `outcome-router-4m-v1`, revision `c1899de289a04d12100db370d81485cdf75e47ca`, in the actual response. Tested an idle call after more than the deployed 300-second scale-down window and its warm repeat. Idle end-to-end time was 18.127 s; warm was 2.917 s. A cold start is inferred, not independently established by Modal container telemetry. No deployment change or forced Modal outage was used. |
| 4. Lifecycle | Tested | Live streamed tool progress; simultaneous runs in separate tabs; leaving/reopening a run; reloading active and completed `?run=` links; double-click Run; Good and Bad; invalid-Python contract failure; DeepSeek reruns; later routes counting feedback. Found active-link recovery, stale decisions, CSV restoration, and rerun metadata defects. |
| 5. Failures | Partly tested | Stopped backend during use, observed unreachable UI, restarted it, checked direct and proxied status. Lowered cap through the confirmation dialog to $0.001, triggered a zero-cost stopped run, restored $0.25. Invalid run ID gave a 404 and readable toast. Malformed, empty, and oversized CSV uploads were attached. Malformed CSV was run live; oversized requests were rejected twice. The empty attachment was not run. Observed slow Modal response, but did not force timeout or provider failure. No weekly-limit error occurred. |
| 6. UI and UX | Partly tested | 1280 x 800 desktop, 768 x 900 tablet, 390 x 844 phone. Inspected empty states, route and answer skeletons, streamed progress, error/success toasts, cap dialog, block loading, raw/rendered switches, tooltips and accessible names. Keyboard Tab/Enter worked, the cap dialog trapped Tab focus between its two actions, and Escape dismissed it without changing settings; arrow navigation defects are below. Inspected browser console/network diagnostics. No physical screen reader or automated layout-shift measurement was used. |
| 7. Safety | Tested within stated scope | Literal script string in generated code; hostile Mermaid script/image labels; script tags in prompt; synthetic traversal filename through the actual file-input change handler and a live run. No script sentinel executed. Traversal filename became `.._.._qa-bad.csv` inside `work/inputs`. Key scan counts are below. Mermaid still fetched an image URL, which is a finding. This was not a full penetration test. |

### Agent checks

The CSV fixture was `item,quantity,price` with Apple 2 x 3, Banana 5 x 2, Cherry 1 x 8. Correct revenues are 6, 10, 8, totaling 24.

| Agent | Live task and result | Interaction / inspection |
|---|---|---|
| Code | Factorial with ValueError for negative input. Returned a correct loop, including 0! = 1. GLM, 17.79 s, $0.001668. | Code block rendered at desktop. Raw output Copy used separately on the script-string test; successful native clipboard write contained the exact Python source. |
| Spreadsheet | Multiply quantity by price, add total, sort descending. CSV correctly contains Banana 10, Cherry 8, Apple 6. GLM, 24.84 s, $0.002248. | Grid rendered at 390 and 1280; column A sorting changed rows to Apple/Banana/Cherry and set `aria-sort=ascending`. Chart agreed with CSV. Generated summary contradicted both, see U06. |
| Data analysis | Total revenue, highest item, bar chart. Returned 24, Banana, and bars 10/8/6. GLM, 26.99 s, $0.002340. | Answers, insights, labels and chart rendered. Keys `q1`, `q2`, `q3` are terse but understandable beside the prompt. |
| Document | Formal meeting minutes with Attendees and action-item table. GLM, 42.07 s, $0.003562. | Preview rendered. Download produced a 38,431-byte DOCX; `.venv` python-docx opened it with 29 paragraphs and one table. The more detailed initial DOCX prompt routed to Slides, see F05. |
| Slides | Three garden slides: Goals, Schedule, Budget. MiMo, 38.60 s, $0.001349. | Below-0.5 picker required an explicit Slides choice. Next reached slides 2 and 3; Previous returned to 2. All three requested topics were present. Invented figures were disclosed in the agent note. |
| Diagram | Start-to-Finish flowchart containing hostile text labels. MiMo, 133.38 s, $0.002409. | Diagram rendered and source-copy action succeeded. Scripts did not run. Labels did not survive as literal text, and image requests occurred, see F09. |
| Map | Paris and London labeled points, exact requested longitude-first coordinates. GLM, 17.18 s, $0.001891. | Both markers and basemap rendered. Focused canvas and ArrowRight panned; Zoom in changed the view. Map controls have accessible names. |
| 3D scene | Red cube, gray floor, camera and lighting. DeepSeek, 36.39 s, $0.005699. | Rendered on phone with lighting and floor. Dragging canvas toward the Raw output button changed the visible cube face and horizon. [Before](screenshots/scene-mobile.png) and [after](screenshots/scene-orbit.png) screenshots verify orbit. |

Recorded examples were also opened for Code, Map and Document. No weekly-limit fallback was needed. The eight-agent result above comes from live calls, not recorded examples.

## Functional findings

### F01. Active run links silently lose the run

- Severity: major. Area: lifecycle. Confirmed twice, using Code and Spreadsheet.
- Steps: start a run; reload its `?run=<id>` URL before it finishes; leave the page open until the backend completes it.
- Expected: restore the running state and reconnect progress or poll for completion.
- Actual: blank task and "No route yet". Completion never appears. Reloading again after completion does restore the result.
- Evidence: [reload screenshot](screenshots/reload-mid-run.png); `data/ui-runs/20261101-140315-942b/run.json` and `data/ui-runs/20261101-140337-05ea/run.json` show completed backend runs.
- Likely cause: `components/app.tsx:110` returns immediately when a fetched run is still running and installs no subscription or retry.

### F02. Editing a routed task keeps an executable stale decision

- Severity: major. Area: routing/run integrity. Reproduced on desktop and phone; one live execution confirmed the mismatch.
- Steps: route `Write a Python function add(a,b) that returns their sum.`; replace the textarea with `Create a Word document with meeting minutes.`; click the existing Run GLM on the code agent button without routing again.
- Expected: invalidate the old decision or reroute the edited task before spending.
- Actual: Code/100% remains selected, but the backend receives the new document task. Run `20261101-140916-b5c6` produced a Python document-generation script in the Code block instead of a document preview/download. The UI still presents the earlier code-task confidence.
- Evidence: [result](screenshots/stale-route-result.png); `data/ui-runs/20261101-140916-b5c6/run.json`. The second reproduction stopped at the still-enabled stale Run button and made no duplicate paid call.
- Likely cause: `components/app.tsx:339` only updates text on change; `components/app.tsx:168` sends current text alongside the old decision at line 174.

### F03. Reopening a CSV run drops the input on rerun

- Severity: major. Area: attachment persistence. Confirmed in two live reruns.
- Steps: open `?run=20261101-140817-b562`, a failed CSV run; click Rerun on DeepSeek without reattaching the CSV.
- Expected: rerun the same task with the original input, or require reattachment before starting.
- Actual: `csv_name` becomes null; the new workspace has no `inputs/` directory. DeepSeek spends time searching for the missing data. The first rerun reports no input and no computed sum, yet passes the spreadsheet format contract.
- Evidence: `20261101-141153-3bf0` and `20261101-141243-8328`; [missing-input result](screenshots/missing-csv-rerun.png). Inspect their `data/ui-runs/<id>/work/` folders against the original input folder.
- Likely cause: run restoration at `components/app.tsx:111` restores text/result only; `components/app.tsx:172` sends the empty in-memory CSV state; `agents/adhoc.py:90` creates inputs only from that field. `rerun_of` does not restore files.

### F04. DeepSeek reruns inherit the previous model's confidence

- Severity: major. Area: result provenance. Confirmed on two fresh route/fail/rerun cycles.
- Steps: route the deliberate invalid-Python task, run GLM, then click Rerun on DeepSeek without reloading first.
- Expected: show DeepSeek's estimate or identify a manual model override with appropriate metadata.
- Actual: result says Model DeepSeek, but its confidence is GLM's old estimate and the runner-up is DeepSeek itself. First cycle showed 90%; second showed 77%. Reloading the original failure before rerunning gives "chosen by hand" instead, so the bug depends on retained route state.
- Evidence: [screenshot](screenshots/rerun-confidence.png); `data/ui-runs/20261101-140644-9112/run.json` and `data/ui-runs/20261101-140904-c5c9/run.json` contain GLM in `route.model` and DeepSeek in `model`.
- Likely cause: `components/app.tsx:174` copies the original preference decision unchanged into the manually overridden rerun; `components/result-view.tsx:50` displays that decision's confidence.

### F05. An explicit Word document task routes to Slides without a correction control

- Severity: major. Area: agent routing. Exact prompt submitted twice, same result.
- Steps: route `Create a Word document project brief titled Community Garden. Include sections Goals, Schedule and Budget, with a table listing Seeds 50, Tools 100, total 150. Provide a .docx.`
- Expected: Document agent, or a way to correct an unsuitable choice before running.
- Actual: Slides 79%, Document 21%; only the Slides run action is available. The later meeting-minutes wording did reach Document, so the agent itself works.
- Evidence: [routing screenshot](screenshots/routing-docx.png) and `/tmp/qa-routing-probes.json`; repeat generated Slides with the same 79/21 vote. No paid call was made for this misroute. The original task text is preserved verbatim above.
- Likely cause: `routing/route.py:85` nearest-neighbor voting favors presentation-like structure; `components/app.tsx:391` only offers a picker below the confidence threshold, and `components/decision-panel.tsx:153` limits it to the top two choices.

### F06. Hindi code request cannot select Code

- Severity: minor. Area: language coverage. Exact prompt submitted twice.
- Steps: route `एक पायथन फ़ंक्शन लिखें जो दो संख्याओं को जोड़ता है।`, asking for a Python function that adds two numbers.
- Expected: Code, or at least a Code override.
- Actual: Data analysis 47%, Document 40%; only those two choices appear. Code is unavailable.
- Evidence: [Hindi picker](screenshots/routing-hindi.png) and `/tmp/qa-routing-probes.json`; no paid call. The English pasted-code control routed to Code at 100%.
- Likely cause: the English embedding model selected at `routing/memory.py:107`, plus the top-two-only picker at `components/decision-panel.tsx:153`.

### F07. Long input silently loses a decisive task at the end

- Severity: minor. Area: input/routing limits. Reproduced twice.
- Steps: submit `"A ".repeat(15000) + "Write a Python function add(a,b) returning their sum."`, 30,053 characters.
- Expected: an input-length warning or routing that preserves the actual instruction.
- Actual: Data analysis 66%, Code 27%, with a CSV warning and no Code override. No length warning appears.
- Evidence: [long-input route](screenshots/routing-long.png) and `/tmp/qa-routing-probes.json`; both route-only probes produced the same result; no paid call.
- Likely cause: `routing/memory.py:108` passes the full text to an encoder with a finite token window; the UI has no length guidance or task-preserving truncation. This is a routing limitation, not evidence of a server crash.

### F08. Oversized CSV becomes a false backend-outage error

- Severity: minor. Area: upload/failure handling. Reproduced twice.
- Steps: attach a 2,040,004-byte CSV made from `a,b\n` plus 510,000 `x,1\n` rows; route a spreadsheet transformation; click Run.
- Expected: reject the upload with its size limit and keep the backend status accurate.
- Actual: POST `/api/py/runs` returns 500, with "The router backend is not answering" and a sticky "Backend unreachable" toast. Direct and proxied `/status` both remain 200. No run is created and no model cost is incurred.
- Evidence: [screenshot](screenshots/large-csv-error.png); browser diagnostics recorded two POST 500s at 08:39:51 and 08:39:52 UTC. Python's limit is 2,000,000 request bytes.
- Likely cause: early size rejection at `routing/server.py:256` before consuming the proxied body, combined with no file-size validation at `components/app.tsx:358` and generic 5xx classification at `lib/api.ts:159`. The precise proxy-side 500 cause was not isolated.

### F09. Hostile Mermaid labels produce image requests and lose literal text

- Severity: minor. Area: untrusted output. Confirmed during live rendering and again after reopening the saved run.
- Steps: open `?run=20261101-140514-4f32`. Its label includes `<img src=x onerror="window.__qaXSS=2">` and a script tag, requested as literal text.
- Expected: escaped literal labels without interpreting markup or fetching the image.
- Actual: the script sentinel stays unset and the image's event handler is removed, which is good. But a real `img` with src `http://localhost:3001/x` remains in the diagram. Each fresh render made three `/x` requests returning 404. The payload labels are blank/quotes instead of literal text.
- Evidence: [diagram](screenshots/hostile-mermaid.png); browser resource entries and DOM inspection recorded the image source, null `onerror`, and unset `window.__qaXSS` on both renders.
- Likely cause: `components/blocks/mermaid/mermaid-theme.ts:158` enables HTML labels; strict mode at line 164 strips execution hooks but still permits image markup before SVG insertion at `components/blocks/mermaid/mermaid-diagram.tsx:65`.

## UI findings

### U01. Contract messages claim content correctness that was never checked

- Severity: major. Area: result wording/paper evidence. Confirmed in live Spreadsheet and Data analysis, then reopened; missing-input rerun makes the problem explicit.
- Steps: run either free-text CSV task; inspect Contract passed. Also open `?run=20261101-141153-3bf0`, which has no source CSV and computes no sum.
- Expected: distinguish schema/format validity from verified task answers.
- Actual: Spreadsheet says "expected cells match"; Data analysis says "3 answers correct". The missing-input result also says "expected cells match" while displaying zero inputs and no sum. No gold answers or expected cells were supplied for these free-text runs.
- Evidence: [missing-input result](screenshots/missing-csv-rerun.png), [spreadsheet](screenshots/spreadsheet-mobile.png), and the respective run JSON contract details.
- Likely cause: `agents/adhoc.py:43` calls suite validators with an empty check; `agents/validators/__init__.py:254` and `:290` return unconditional correctness wording after optional content checks. `components/result-view.tsx:59` prints the detail unchanged.

### U02. ARIA tabs do not support arrow-key navigation

- Severity: minor. Area: accessibility. Repeated ArrowRight twice from the Task tab.
- Steps: focus the Task tab and press ArrowRight. Repeat. Then use Tab and Enter.
- Expected: arrow keys move through a tablist, with one tab in its ordinary tab order.
- Actual: focus and selection remain on Task. Every tab has `tabIndex=0`. Tab then Enter does open Recorded examples, so a keyboard workaround exists.
- Evidence: `/tmp/qa-accessibility.json`, accessibility tree and evaluated active element on both presses. Task and Mode tablists share this implementation.
- Likely cause: `components/app.tsx:253` and `:311` apply tab roles to buttons without arrow handlers, panel associations, or roving tab index.

### U03. Just answer confidence is unexplained and has the wrong tooltip

- Severity: minor. Area: routing explanation. Reproduced on all four answer calls.
- Steps: ask `What is 17 multiplied by 19? Reply with only the integer.` with cheap preference; inspect the probability list and confidence hint.
- Expected: explain the preference threshold and define this router's confidence.
- Actual: "picked GLM with confidence 7%" sits beside Nemotron 81%. The generic hint defines confidence using nearest past tasks and agent vote share, although this response comes from the separate Modal classifier. The returned threshold/easy score is not explained.
- Evidence: [phone answer](screenshots/just-answer-mobile.png); `/tmp/qa-browser-evidence.json` contains the captured response. The choice itself follows the deployed policy: easy score 0.8119 exceeds 0.74, so cheap chooses GLM. This is not an argmax routing defect.
- Likely cause: `components/app.tsx:489` uses the generic `HINT.confidence` from `components/term.tsx:9` and omits the threshold rule available in the response.

### U04. Answer timing hides most of the idle-call wait

- Severity: minor. Area: latency reporting. Observed on the idle call and warm repeat.
- Steps: submit the arithmetic prompt after idle, then repeat warm; compare request elapsed time with the result's displayed seconds.
- Expected: label model-call time clearly and show end-to-end wait when reporting latency.
- Actual: idle request took 18.127 s but showed 1.6 s plus 917 ms routing; warm request took 2.917 s but showed 1.7 s plus 349 ms routing. Startup and transport time are excluded without a label.
- Evidence: captured request timing in this report and `/tmp/qa-browser-evidence.json`; [answer screenshot](screenshots/just-answer-mobile.png).
- Likely cause: `components/app.tsx:502` displays backend `answer.wall_s`, while Modal startup happens before the backend answer call in `app/api/answer/route.ts:23`.

### U05. Long agent notes begin in the middle of a sentence

- Severity: polish. Area: output readability. Confirmed with Diagram, malformed CSV, and missing-input rerun.
- Steps: inspect the agent note on `20261101-140514-4f32` or `20261101-141153-3bf0`; reopen the link.
- Expected: full text, an expandable note, or an explicit truncation marker.
- Actual: notes begin ", balanced ..." or "-computed sum ...". There is no marker that earlier text was discarded. Markdown markers also remain literal in the note.
- Evidence: [diagram](screenshots/hostile-mermaid.png), [missing-input result](screenshots/missing-csv-rerun.png), and `result.final_text` in run JSON.
- Likely cause: `agents/run.py:106` keeps only the final 500 characters; `components/result-view.tsx:82` prints them as plain text without indicating truncation.

### U06. Spreadsheet summary contradicts the correctly transformed file

- Severity: minor. Area: generated content. Unconfirmed as a repeat-generation defect; the saved wrong text persisted on two reopenings.
- Steps: open `?run=20261101-140337-05ea`; compare Sort order finding with its grid, chart and raw CSV.
- Expected: Banana 10, Cherry 8, Apple 6.
- Actual: summary says "Cherry (8), Apple (6), Banana (4)" under "total desc". CSV and chart correctly show Banana 10, Cherry 8, Apple 6.
- Evidence: `data/ui-runs/20261101-140337-05ea/work/out/changes.json` versus `result.csv`; the finding is visible in the saved run.
- Likely cause: model-authored findings are accepted without checking agreement with the CSV in `agents/validators/__init__.py:251`. No second generation of this exact task was purchased.

### U07. Enter in the cap field did not leave its confirmation open

- Severity: minor. Area: keyboard interaction. Unconfirmed outside browser automation.
- Steps: edit the cap to `0.249`, explicitly click its input, and press Enter. Repeated twice; the value was valid and Set was enabled.
- Expected: the confirmation dialog remains open for review, matching the input's Enter handler.
- Actual: no dialog remained and focus moved to the body. Clicking Set opened the dialog correctly; Tab cycled through its two actions and Escape dismissed it. The cap was never changed by this test.
- Evidence: `/tmp/qa-accessibility.json`. This may depend on the automation key sequence, so it needs a physical-keyboard check before being treated as confirmed.
- Likely cause: possible default Enter activation after focus moves into the dialog; `components/app.tsx:550` opens it on keydown without preventing the default action.

## Routing and recovery observations

The four preferences were internally consistent on the same correctly routed meeting-minutes task before feedback: cheap/balanced/accurate chose GLM, estimated 51%, $0.0058, 70 s; fast chose Nemotron, 42%, approximately $0.014, 27 s. Their candidate tables supported those choices. Equal rounded percentages can hide small differences; the underlying decisions retain four decimal places.

After Good on the live DOCX, a later route showed GLM past runs increasing from 10 to 11 and pass estimate from 51% to 61%, with estimated cost/time changing to $0.0053/65 s. Good on Code and Data analysis and Bad on Spreadsheet saved successfully. The Run button double-click for the first factorial task created one run. Independent tabs ran concurrently. Completed links reopened correctly, including after backend restart. An invalid `?run=qa-does-not-exist` showed "Could not reopen that run / no such run" and a 404, without crashing the app.

`help` produced a 47% Data analysis / 30% Document picker. A physical pizza-delivery request produced Document 22% / Map 20% and waited for a user choice. Pasted Python routed Code at 100%. HTML/script tags stayed inert in the textarea. The arithmetic answer's real Modal response identifies the four-model outcome router, not the older two-model or agent router. All four arithmetic answers were correct. There was no router fallback error in the captured responses.

Backend stop/restart was performed after pending runs finished. The unreachable alert appeared within the polling interval and routing disabled; both status endpoints returned 200 after restart. A saved link opened while the backend was unavailable required a reload after recovery to load its result. This was seen once and remains an unconfirmed recovery limitation. The backend was not killed in the middle of an executing Docker run, so orphan-container recovery was not tested.

No major horizontal page overflow was found at the three tested widths. Internal grid/code/table scrolling is required for wide content. Rendered data and scenes loaded after skeletons; this was a visual inspection, not a measured CLS score. Existing error toasts remain sticky after recovery until dismissed, as the design specifies. Console failures corresponded to the intentional invalid-run 404, intentional backend outage, large-upload 500s, and hostile-label `/x` 404s. Event streams also logged `ERR_ABORTED` when navigation closed them. No unrelated application exception was confirmed.

The native clipboard read API was denied by the preview browser. To verify copy content, I wrapped `writeText` in the page, called the original native method, and captured the successful argument. Code copied the exact Python source; Copy answer copied `323`. No clipboard or source-code polyfill was installed.

## Safety and spend

The traversal filename test used a browser `File` named `../../qa-bad.csv` through the file input's real change handler. The displayed and backend name was `.._.._qa-bad.csv`; the agent read `/work/inputs/.._.._qa-bad.csv`. It did not escape the inputs directory. The malformed file contained an unterminated quote. GLM identified the parser error and did not invent a sum; its schema failure was correctly exposed as raw output.

The script-string Code run preserved `<script>window.__qaCodeXSS=1</script>` as source text. `window.__qaCodeXSS` stayed unset. Mermaid's `window.__qaXSS` also stayed unset. Strict sanitization removed its event handler, but did not prevent the image fetch described in F09.

The actual `CMD_API_KEY` value was read privately by the scan process from `.env.modal`, passed to `rg` over stdin, and never printed or injected into a browser. Only counts were emitted:

| Scan scope | Key hits |
|---|---:|
| Captured page text and input values from all six QA tabs | 0 |
| 64 fetched same-origin response bodies, including status, run JSON and loaded resources | 0 |
| All `data/ui-runs` folders | 0 |
| Client static bundles under `.next` | 0 |

This covers captured content and fetched responses, not every historical response byte from before instrumentation. Browser captures and response copies are in `/tmp/qa-browser-evidence.json` and `/tmp/qa-network-responses/`. Run/event records remain under `data/ui-runs/`. Scanning did not expose the key, Modal tokens, or their values in this report.

Initial cumulative backend spend was $0.01432. Final cumulative spend was $0.06433, so this QA added $0.05001. The 19 agent runs total $0.049966 in their result records; the remainder is the four tiny answer calls and cumulative display rounding. The cap was briefly $0.001 and is restored to $0.25. It was never raised above $0.25. Cap-test run `20261101-141016-f884` stopped at zero cost and appended no memory record. No weekly-usage-limit error occurred.

## Run and verdict ledger

All IDs below were created through UI actions. Null user verdict means I did not press Good or Bad; failed contracts still auto-append `passed=false`. The list includes deliberate failures and reproduction runs, so its pass ratio must not be used as an agent benchmark. Just answer calls have no run ID or user verdict and do not append agent outcome memory.

| Run ID | Agent / model | Status | User verdict | Cost USD | Purpose |
|---|---|---|---|---:|---|
| `20261101-140315-942b` | code / GLM | passed | Good | 0.001668 | Factorial; Good |
| `20261101-140337-05ea` | spreadsheet / GLM | passed | Bad | 0.002248 | Revenue CSV transform; Bad |
| `20261101-140400-7a2c` | data-analysis / GLM | passed | Good | 0.002340 | Revenue analysis; Good |
| `20261101-140421-e8c4` | docx / GLM | passed | Good | 0.003562 | Meeting minutes DOCX; Good |
| `20261101-140437-488d` | slides / MiMo | passed | null | 0.001349 | Garden slides; picked Slides |
| `20261101-140452-4592` | scene-3d / DeepSeek | passed | null | 0.005699 | Red cube scene |
| `20261101-140452-b5db` | map / GLM | passed | null | 0.001891 | Paris/London map |
| `20261101-140514-4f32` | diagram / MiMo | passed | null | 0.002409 | Hostile Mermaid labels |
| `20261101-140617-ee93` | code / GLM | failed | null | 0.001321 | Intentional invalid Python |
| `20261101-140644-9112` | code / DeepSeek | failed | null | 0.001645 | DeepSeek rerun with stale route |
| `20261101-140741-7d47` | code / Nemotron | passed | null | 0.003250 | Literal script string |
| `20261101-140744-3b7f` | code / DeepSeek | failed | null | 0.001015 | DeepSeek rerun after reopening |
| `20261101-140817-b562` | spreadsheet / GLM | failed | null | 0.003232 | Malformed/traversal CSV |
| `20261101-140843-f5a3` | code / GLM | failed | null | 0.000957 | Second intentional invalid Python |
| `20261101-140904-c5c9` | code / DeepSeek | failed | null | 0.002250 | Second stale-route DeepSeek rerun |
| `20261101-140916-b5c6` | code / GLM | passed | null | 0.003363 | Edited task using stale Code decision |
| `20261101-141016-f884` | spreadsheet / DeepSeek | stopped | null | 0.000000 | Cap test; no memory append |
| `20261101-141153-3bf0` | spreadsheet / DeepSeek | passed | null | 0.005545 | Reopened CSV rerun; input lost |
| `20261101-141243-8328` | spreadsheet / DeepSeek | passed | null | 0.006222 | Repeat reopened CSV rerun; input lost |

The four explicit verdicts were Code Good, Spreadsheet Bad, Data analysis Good, and Document Good. Six deliberate/observed contract failures auto-recorded failure without a user verdict. The cap-stopped run appended nothing. The other successful runs remain without a verdict. Online UI records increased from 9 to 27.

Final check: cumulative spend $0.06433; QA spend $0.05001; cap $0.25; stopped state `null`; no QA runs still running.

## Handoff

Demo: suitable for a rehearsed path with fixed prompts, with the major lifecycle and provenance limitations disclosed. Fix F01-F05 and U01 before inviting arbitrary tasks or presenting UI statistics as dependable evidence. Paper: the existing offline evaluation can be described on its own terms, but this test does not support a claim of unrestricted end-to-end UI reliability or automatic correctness checking for free-text tasks. Clean the QA memory before any later evaluation.

Both web and backend servers were checked running at handoff. The backend uses `--max-usd 0.25`. No source fix was attempted. Final verification was at 08:47 UTC.

## Fix status

Fixed on 2026-11-01 and checked in the T3 preview browser at `http://localhost:3001`, once before the fix (the steps above) and once after. Live spend for the checks was USD 0.0083 of the USD 0.10 allowed; the cap stayed at 0.25. Nothing is committed.

| Finding | Status | What changed and how it was checked |
|---|---|---|
| F01 | Fixed | `components/app.tsx` reconnects to the progress stream of a running `?run=` link. Reloaded `20261101-142931-0669` mid-run: the running view and its events came back, then the result. |
| F02 | Fixed | `lib/route-state.ts` `isStale` hides the decision and the Run button after any edit; the backend also refuses a `routed_text` that differs from `text`. Edited a routed task in the browser: no Run button, "Route again" note. |
| F03 | Fixed | A rerun sends no file. `routing/server.py` `stored_csv` reads the original run's `upload/` copy (or `work/inputs/`), and refuses with a message if it is gone. Live rerun of `...b562` after a reload reused `.._.._qa-bad.csv` (`20261101-142636-4b9b`). |
| F04 | Fixed | The backend keeps a routing decision only for the model it chose. A rerun carries none, so the result says "manual rerun, DeepSeek estimate N% pass" with runner-up "none". Checked on the reload path (`...4b9b`) and the no-reload path (`...0669`). Old saved runs get the same check in `result-view.tsx`. |
| F05, F06 | Fixed | "Change agent" lists all eight agents on every route and on the low-vote picker. It routes again for that agent, so the models are re-estimated; the vote is untouched. The QA Word-document task now reaches Document (GLM 61%) in one click. |
| U01 | Fixed | `agents/adhoc.py` `free_text_detail` rewrites the wording for free-text runs only: "format valid: spreadsheet has the required files ... Cell values were not checked." `agents/validators` is unchanged. Seen live in `...4b9b`. Runs saved before the fix keep their old wording. |
| F07 | Fixed | The page warns above 1,500 characters. The backend embeds a longer task as its first and last 300 characters. The QA 30,053-character prompt now routes to Code at 100%. Reading 400 + 1,100 characters did not fix it, because the filler still dominated. |
| F08 | Fixed | The browser rejects a CSV over 1 MB with an inline size error. The backend drains the body and returns a 413 with a readable message, also through the Next proxy. |
| F09 | Fixed | `htmlLabels: false` in the vendored theme. The hostile run now has no `img` and makes no `/x` request. The `<img>` label shows as literal text. The `<script>` label still renders blank, because Mermaid's strict mode strips it. Normal nodes and edges render as before. |
| U02 | Fixed | New `components/tab-list.tsx`: arrows, Home and End move and select; only the selected tab has `tabIndex` 0. Both tablists use it. Panel associations were not added. |
| U03 | Fixed | The answer panel shows easy score, threshold and what they mean, with their own tooltips, and a separate tooltip for the router's confidence. |
| U04 | Fixed | The answer shows total wait (16.0 s on the check) and labels model call and routing time separately. |
| U05 | Fixed | A note of 500 characters or more gets a leading ellipsis and "cut: only the last 500 characters are kept". |
| U06 | Not changed | Model-written text, as the task says. |
| U07 | Fixed in the browser | Enter in the cap field now calls `preventDefault`. After the fix, Enter left the dialog open with focus on "Keep". The cap stayed 0.25. A physical keyboard was not tried. |

Tests added: `lib/route-state.test.ts` (stale decision, limits, tab keys), `routing/test_server.py` (CSV rerun lookup, rerun metadata, stale text, long-task text, 413), and two cases in `agents/test_adhoc.py` (free-text wording, suite wording kept).

Memory: the 31 UI test records (27 from the QA, 4 from these checks) moved from `data/memory/online.jsonl` to `data/memory/online.test-archive.jsonl`. `/status` showed 4,935 records before my checks (27 UI + 4 live online); my 4 live checks made it 4,939 (35 online). It now shows 4,908 records, 4 online, 0 UI, after. Routing rests on the 320 paid runs and the 4 live `route.py` runs. The pre-cleanup file is at `/tmp/online.before-cleanup.jsonl`.

## Retest

Tested independently on 2026-11-01 from 11:41 UTC in T3 preview at `http://localhost:3001`, after the Fix status handoff. This section supersedes the first-pass readiness verdict. App code, prompts, deployment, cap and git staging were left unchanged. No Good or Bad buttons were pressed. Browser-created runs and spend records were left intact. The user separately authorized a temporary move and restoration of one CSV for the missing-file test.

### Finding checks

The original prompts, saved links and actions above were used. "Partly fixed" means the tested behavior improved but part of the original finding remains. It does not mean the fix thread's narrower claim was false.

| Finding | Retest result | Independent evidence |
|---|---|---|
| F01 | Confirmed fixed | Started Code `20261101-171118-e909`, reloaded while running, saw restored progress and the finished factorial result without another reload. Repeated with Spreadsheet `20261101-171547-c878` at 390 px: queued state, tool events, restored task text and completed result all arrived. |
| F02 | Confirmed fixed | Routed the original add-function task, replaced it with the original meeting-minutes task. At both 1280 and 390 px, the executable route disappeared and "Route again" appeared. No paid call was needed to verify the disabled path. |
| F03 | Confirmed fixed | Opened the original failed CSV run `20261101-140817-b562` and pressed Rerun on DeepSeek. New run `20261101-171225-b2fa` read the original 20-byte malformed CSV and reported its parse error. Both its `upload/` and `work/inputs/` copies match the original bytes. Also moved the original's only CSV to `/tmp` with user permission, pressed Rerun, and received "The input file ... is gone ... Attach the CSV again and start a new run." No new run was created. Restored SHA-256 `cfc7602c11998562f63dd69e47c4500757f699a08fdb9dda0ba2b4d8ff3a0563`. [Refusal](screenshots/retest-missing-csv-refusal.png). |
| F04 | Confirmed fixed | Fresh route/fail/rerun without reloading: GLM failure `20261101-171152-fb78` became DeepSeek `20261101-171244-a849`, with "manual rerun, DeepSeek estimate 88% pass" and runner-up "none". The restored CSV rerun independently showed DeepSeek 98%, none. Old saved mismatch `20261101-140644-9112` also displays manual metadata. [Phone result](screenshots/retest-rerun-mobile.png). |
| F05 | Partly fixed | Exact Word-project-brief prompt still automatically selects Slides 79%, Document 21%. All eight correction choices are now available. One Document click recalculated the models and selected GLM at 52%; the live DOCX completed with the requested headings and 50/100/150 budget table. Thus the correction-control claim holds; the automatic misroute remains. Run `20261101-171157-124d`. |
| F06 | Confirmed fixed | Exact Hindi prompt still gives Data analysis 47%, Document 40%, but Code is now available at 7%. Clicking Code produced a Code route with recalculated model estimates and an executable Code action. This meets the original expectation of a Code override; language routing itself is unchanged. No paid call. |
| F07 | Confirmed fixed | Original 30,053-character input now shows the explicit first/last-300-character warning and selects Code at 100%. Checked at 390 px. No paid call. |
| F08 | Partly fixed | Original 2,040,004-byte file now gets a readable 2.0 MB / 1.0 MB limit message. Oversized POST through the browser proxy separately returns a readable 413; status remains healthy. However, the original UI Run step still starts a paid job after dropping the rejected file. Repeated at both widths, see R01. |
| F09 | Partly fixed | Reopened the original hostile Mermaid run twice. Each render had zero `img` elements, zero `/x` resource requests and no XSS sentinel. Normal nodes and edges rendered. The image label is now literal text, but strict sanitization still removes the script label and strips the image event attribute. The image-fetch fix holds; exact literal preservation does not. |
| U01 | Partly fixed | New Spreadsheet runs explicitly say "Cell values were not checked"; new Data analysis `20261101-171537-7cc5` says "The answers were not checked." Independently checked revenue 24 and Banana 10 from the fixture. But original reproduction link `20261101-141153-3bf0` still says "expected cells match" despite zero inputs and no sum, as the fix handoff disclosed. Saved free-text results still overclaim validation. |
| U02 | Confirmed fixed | Task/Recorded examples and Run an agent/Just answer now move selection and focus with ArrowRight. Mode Home and End select the endpoints. Only the selected button in each of these two tablists has tabIndex 0. Panel associations remain absent. Nearby Recorded examples agent tabs still have the old keyboard behavior, see R02. |
| U03 | Confirmed fixed | Live arithmetic answer explains GLM 7%, easy score 81%, cheap threshold 74% and why GLM was chosen. Hovered the separate confidence and threshold controls: their tooltips describe Modal probabilities and preference policy, not nearest-task votes. Correct answer 323, actual response identifies `outcome-router-4m-v1`. |
| U04 | Confirmed fixed | Browser fetch measurement was 2700.6 ms; UI showed 2.7 s total wait and separately 1.0 s model call / 316 ms routing. Startup/transport are no longer hidden in the only displayed latency. Idle and warm follow-up measurements are recorded below. |
| U05 | Confirmed fixed | Reopened the original Diagram and missing-input Spreadsheet links. Both 500-character tails now have a leading ellipsis and "cut: only the last 500 characters are kept". New long notes use the same marker. Literal Markdown remains, but the missing-text disclosure requested in the original finding is present. |
| U07 | Confirmed fixed in T3 preview | At 390 px, edited cap to 0.249, clicked the input, pressed Enter. Confirmation stayed open with focus on Keep $0.250. Escaped and repeated, with the same result. Dismissed and cancelled the edit. The cap stayed 0.25. Physical keyboard behavior remains outside this browser test. |

U06 was outside the requested retest and was not changed or reclassified. The new good-input Spreadsheet run agreed with its output, but that does not establish that model-authored summaries always agree.

### New and nearby findings

#### R01. Run starts a paid job after rejecting an oversized attachment

- Severity: major. Area: input integrity / spend. Confirmed twice, at 1280 and 390 px.
- Steps: attach the original 2,040,004-byte CSV using the real file-input change handler; route `Multiply quantity by price in the attached spreadsheet, add revenue and sort descending.`; press Run GLM on the spreadsheet agent despite the inline size error.
- Expected: refuse the run until the attachment error is resolved, without creating a job or spending.
- Actual: the POST omits CSV data and starts a job. Desktop run `20261101-171342-1758` spent $0.002657 and produced an empty result after searching for the absent file. Phone repeat `20261101-171415-52bb` spent $0.007500 and generated a six-row sample dataset instead. Both passed the format contract, now correctly labeled as format-only validation. The second run discloses the sample in its findings and note, but still processes invented input after a rejected upload.
- Evidence: both saved run records have `csv_name: null`; captured browser POST for the first run contained no CSV fields and returned 200 with the run ID. [Phone result](screenshots/retest-large-csv-mobile-result.png).
- Likely cause: client rejection clears attachment state while leaving Run enabled; a missing CSV is only a warning. No source edit was made to verify a repair.

#### R02. Recorded examples' agent tabs retain the old keyboard defect

- Severity: minor. Area: accessibility. Confirmed by two ArrowRight presses from Code.
- Steps: open Recorded examples, focus Code, press ArrowRight; repeat.
- Expected: Spreadsheet receives focus and selection, with a roving tab index.
- Actual: Code remains focused and selected; all eight agent tabs have tabIndex 0. Clicking Document works and renders the saved example. This is a nearby residual issue; this retest does not establish that the fix introduced it.
- Evidence: T3 DOM checks on both presses returned focus Code, selection Code, and tabIndex 0 for all eight. Rendered/Raw output tabs also retain tabIndex 0 on both buttons, though their arrow behavior was not retested.
- Likely cause: the two top-level tablists were updated, while these tab controls use separate implementations.

### Regression runs and limits

Each of Code, Document and Diagram started from a freshly navigated page. Code returned a valid factorial with negative-input ValueError. Document rendered the project brief and downloaded a 37,573-byte DOCX. Diagram rendered Start, Process and Finish. The good CSV runs gave Banana 10, Cherry 8, Apple 6, total 24; raw Spreadsheet output agreed. Rendered/raw switches worked. Recorded examples Code and Document opened without live generation. Change agent was checked on both a high-vote Slides route and the low-vote Hindi picker.

| Run ID | Purpose | Result | Cost USD |
|---|---|---|---:|
| `20261101-171118-e909` | Code regression, reload active link | passed | 0.001421 |
| `20261101-171152-fb78` | Original deliberate invalid-Python reproduction | failed as intended | 0.001328 |
| `20261101-171157-124d` | Word prompt, Change agent, DOCX regression | passed | 0.004457 |
| `20261101-171208-e33b` | Fresh Diagram regression | passed | 0.000927 |
| `20261101-171225-b2fa` | Restored malformed CSV rerun | passed format, parse error disclosed | 0.003524 |
| `20261101-171244-a849` | No-reload DeepSeek rerun provenance | failed as intended | 0.001238 |
| `20261101-171342-1758` | Oversized CSV through Run, desktop | ran without input | 0.002657 |
| `20261101-171415-52bb` | Same reproduction, phone | ran with generated sample | 0.007500 |
| `20261101-171537-7cc5` | Fresh Data analysis validation wording | passed | 0.002256 |
| `20261101-171547-c878` | Spreadsheet reload, good CSV, validation wording | passed | 0.001767 |

The ten agent runs total $0.027075. No user verdicts were submitted. Deliberately invalid Python still auto-records failure, so these runs are not benchmark data.

Checked page layouts at 1280 x 800 and 390 x 844. Task, route, answer, DOCX, notes and CSV results remained readable; sampled document scroll widths equaled viewport widths. The grid scrolls internally. [Desktop Spreadsheet](screenshots/retest-spreadsheet-desktop.png) and [phone DOCX](screenshots/retest-docx-mobile.png) capture representative layouts. No unrelated application exception was observed in sampled preview console diagnostics. Request diagnostics were watched during use. Expected negative responses were the missing-file refusal and oversized-request 413; navigation also closes event streams. Preview snapshots bound their history and sometimes omitted older diagnostics, so this is not a complete retained network trace. No weekly usage limit error occurred.

The downloaded DOCX also opened with python-docx: 19 paragraphs and one table. Additional arithmetic checks after more than five minutes idle and on a subsequent repeat both returned 323. The idle request took 2.733 s and showed 2.7 s total, 1.4 s model call, 343 ms routing. The repeat took 19.653 s and showed 19.7 s total, 1.7 s model call, 954 ms routing. The longer wait was visible and correctly reported; these timings do not independently establish which request started a new Modal container. Three answer calls cost $0.000032 in their responses. [Long-wait answer](screenshots/retest-answer-long-wait.png).

### Cleanup and readiness

Moved exactly the ten records appended by these agent runs to the end of `data/memory/online.test-archive.jsonl`. The original four proof records in `online.jsonl` are byte-identical to the pre-retest copy at `/tmp/retest-online-before.jsonl`. Restarted the backend in a detached process with `.venv/bin/python routing/server.py --port 8765 --max-usd 0.25`, PID 3658163, log `/tmp/agent-route-retest-backend.log`. Direct `/status`, proxied `/api/py/status`, and a T3 browser fetch agree: **4,908 records, 0 UI records**, cap **$0.25**, stopped state **null**. The disk online file has four records. No agent run remains active. Both servers remain running. The git-status path list matches the starting list; no staging, commit, install or app-source edit was performed.

Final spend is $0.09976 cumulative, up from $0.07266, for **$0.02710 retest spend** by the rounded backend ledger. This is below the $0.05 allowance. The cap was never changed. No weekly usage limit error occurred.

**Readiness verdict: not ready for an unrestricted demo.** Eleven of the fifteen requested findings are confirmed fixed; four are partly fixed. No blocker was found. R01 is a new confirmed major issue: rejected uploads can still trigger paid jobs with missing or synthesized input. U01 remains major for historical free-text results because their old validation claims are still displayed. F05's automatic misroute also remains, although its correction control now works. F09 has only the literal-label limitation left; its image-fetch defect is fixed. R02 is a minor keyboard gap in Recorded examples. A rehearsed demo using checked prompts and valid small attachments remains reasonable, but arbitrary input should wait for R01 and the misleading historical validation wording to be addressed.

Final verification: 2026-11-01, 11:50 UTC.

## After the retest

Fixed on 2026-11-01 and checked in T3 preview, with no paid calls.

| Finding | Status | What changed and how it was checked |
|---|---|---|
| R01 | Fixed | `components/app.tsx` disables Run while a CSV error stands. With a 2.0 MB file, the Run GLM button went disabled; "run without one" clears the error and enables it. Run was never pressed. |
| U01 | Fixed | `routing/server.py` applies `free_text_detail` when loading saved runs. `20261101-141153-3bf0` now reads "Cell values were not checked". |
| R02 | Fixed | The Recorded examples agent tabs and the Rendered/Raw tabs use `TabList`. ArrowRight from Code moved focus and selection, with one tab at `tabIndex` 0. The Rendered/Raw tabs were not separately exercised. |

Left as is: F05 and F06 (the kNN vote is what the paper evaluates; "Change agent" is the correction), and F09's script label, which Mermaid strips. No third Codex pass was run on these three fixes.
