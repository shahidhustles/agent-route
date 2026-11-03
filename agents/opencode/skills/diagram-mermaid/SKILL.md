---
name: diagram-mermaid
description: Mermaid syntax pitfalls and completeness checks for flowcharts, sequence, ER, class, state diagrams. Load before writing diagram.json.
license: MIT
metadata:
  source: original, written for agent-route from the agents-cc-20261031 failures
---
# Writing Mermaid that parses and covers the task

Baseline failures: invalid JSON from unescaped quotes and newlines in `source`, a Mermaid parse error, and missing named content (a login flow with five failure paths had too few).

## Write the file safely

Build the JSON in Python: put the Mermaid in a triple-quoted string, then `json.dump({"format":"mermaid","source":src}, f)`. Never hand-type Mermaid inside a JSON string. Strip nothing inside the source, and add no Markdown fences.

## Cover the task

1. List every actor, step, state, entity and branch the task names, with counts ("five failure cases" means five distinct failure edges, each labelled).
2. Use the task's words for node labels. Every item on the list appears at least once.
3. Pick the diagram type the task asks for, or the default in your agent prompt.

## Syntax pitfalls

- Quote labels that contain parentheses, commas, colons, slashes, `#` or quotes: `A["Check (retry)"]`. Do not put `"` inside a quoted label; use `'`.
- Node IDs are plain letters, digits and underscores. A node ID `end` breaks flowcharts; write `endNode`. Do not start an ID with `o` or `x` right after `---`, which Mermaid reads as an edge marker.
- One statement per line. Decision nodes use `{...}` and each outgoing edge has a label: `D -->|yes| E`.
- Flowchart edge labels: `A -->|label| B`. Sequence messages: `A->>B: text`, replies `B-->>A: text`. Group sequence steps with `alt`/`else`/`end`, `loop`, `opt`, each closed by `end`.
- State diagrams: `stateDiagram-v2`, transitions `A --> B: event`, start and finish `[*]`.
- ER diagrams: entity names without spaces, relationships `A ||--o{ B : has`, attributes `type name PK`. Put no `:` or text after attributes except the key marker or a quoted comment.
- Class diagrams: members as `+type name` and `+method()`; relations `<|--`, `*--`, `o--`, `-->`.
- Notes and comments: `%% comment` on its own line. No semicolons at line ends needed.
- Gantt and timeline use their own syntax; copy the header and a sample line shape exactly.

## Self-check before you finish

Read the source line by line. Count brackets and quotes per line, confirm every `alt` or `loop` has an `end`, confirm every task item from step 1 appears, and load the JSON with `json.load` to prove it parses.
