---
name: slides-writing
description: Quality checklist for slide decks (pitches, QBRs, trainings, research findings, proposals). Load before writing slides.json.
license: MIT
metadata:
  source: original, written for agent-route from the agents-cc-20261031 judge notes
---
# Writing a deck a reviewer would present

The baseline decks passed the format check and lost points on content: invented traction, interview counts and quotes stated as fact, and arithmetic that did not hold (quarterly downtime from an uptime percentage, reductions that do not reach the target). Fix those first.

## Plan the deck

1. List what the task supplies: slide count, metrics, dates, names, asks. Each one lands on a slide, using the task's values.
2. Give every slide one point, and write its title as the point: "Churn fell to 2.1%" beats "Churn".
3. Order by audience need:
   - Pitch: problem, solution, market, product, traction or plan, business model, team, ask.
   - QBR or progress report: headline results, metrics against targets, wins, issues, roadmap, asks.
   - Research findings: question and method, findings ranked by importance, evidence, recommendations, next steps.
   - Training: why it matters, rules, examples, what to do when it goes wrong, who to contact.
   - Budget or hiring proposal: need, options, cost, return, timeline, decision wanted.
   - Personal talk (toast, book summary): opening hook, three or four beats, a closing line.
4. First slide states the topic and audience. Last slide states the ask, next steps or the one thing to remember.

## Content rules

- Bullets are short claims with a number, name or date. No bullet repeats the title.
- The task's figures are fixed. Compute derived figures with Python and check them: 99.9% uptime over 90 days is about 2.2 hours of downtime, not 9. Percent changes and reductions compound; a goal like net zero needs the remaining gap stated honestly.
- Never invent evidence. For findings, traction, customer results, credentials or quotes the task did not give, do not write numbers as fact. Write the structure and mark placeholders as targets or assumptions ("target: 50 pilot users") or say what to collect.
- Dates move forward and match the task's timeline.
- Use `body` for one sentence of context when bullets alone would mislead. Keep strings free of Markdown.

## Self-check before you finish

Read `out/slides.json` back and tick each:
- The slide count equals the task's request.
- Each supplied metric appears once and correctly.
- Every derived number was computed in Python.
- No bullet over about 15 words, no slide with more than 5 bullets.
- The deck reads in order without the task text beside it.
