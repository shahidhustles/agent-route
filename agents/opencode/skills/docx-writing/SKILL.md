---
name: docx-writing
description: Quality checklist for business documents (proposals, memos, SOPs, charters, ADRs, handbooks). Load before writing the document.
license: MIT
metadata:
  source: original, written for agent-route from the agents-cc-20261031 judge notes
---
# Writing a document that survives a reviewer

A reviewer reads for facts, arithmetic and safety first, structure second. Most low scores in the baseline came from three things: invented facts presented as real, numbers that do not add up, and domain advice that is wrong or unsafe.

## Before you write

1. List every section, number, date, name and constraint in the task. This is the checklist. Each item appears in the document, with the task's own figures and wording.
2. Pick the shape of the document type:
   - Memo: To/From/Date/Subject lines, the decision or ask in the first two sentences, then reasons, then next steps.
   - Proposal or grant: need, approach, timeline, budget, outcomes, risks.
   - Project charter: purpose, scope in and out, deliverables, milestones, budget, roles, risks, success measures.
   - ADR: context, options with trade-offs, decision, consequences, follow-ups. Every option the task names gets a fair hearing.
   - SOP or handbook: purpose, scope, roles, numbered steps in the order they happen, what to do when something goes wrong, who to call.
   - Event or training plan: schedule by day and hour, owners, costs, logistics, contingencies.

## Facts and numbers

- Use the task's figures as given. Never change, round away or contradict them.
- Details the task leaves open (names, dates, owners) may be invented. Keep them consistent, and mark invented figures with "assumed" or "to be confirmed" in the sentence. Never invent evidence: statistics, survey results, quotes, benchmarks, legal citations, prior performance. Say what to measure or collect instead.
- Every total, percentage and duration is computed, not guessed. Before finishing, run a short Python check that the budget lines sum to the stated total, dates fall in the right order and span the stated length, and units match (storage, per day versus per month, lakh versus million).
- Count capacity against need: seats, vehicles, rooms, staff hours, storage.

## Safety and domain correctness

- For SOPs, medical, chemical, electrical, legal or financial content, write only what is standard and correct. When unsure of a threshold or rule, state the principle and refer to the official standard or manufacturer sheet instead of inventing a limit.
- Put immediate-danger steps first: isolate the hazard, evacuate, call emergency services. Never tell a reader to open, cut, or tamper with a damaged hazardous item.
- Hand medical, legal or insurance decisions to a qualified person, named by role.

## Style

- Plain sentences. Each paragraph says something specific. Delete filler openers and closing summaries that restate the document.
- Lead each section with its conclusion. Use a bullet list for parallel items and a numbered list for ordered steps.
- Length follows the contract in your agent prompt.

## Self-check before you finish

Read `out/document.json` back and tick each:
- Every item on your step-1 checklist is present.
- The numbers reconcile (the Python check ran).
- No placeholder text and no invented evidence.
- The `.docx` exists and its headings match the Markdown.
