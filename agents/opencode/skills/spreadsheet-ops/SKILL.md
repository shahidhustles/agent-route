---
name: spreadsheet-ops
description: Checklist for CSV cleaning and transformation tasks with an op log: trace row counts, averages and ranks. Load before writing result.csv and changes.json.
license: MIT
metadata:
  source: original, written for agent-route from the agents-cc-20261031 failures
---
# Cleaning a table so the numbers hold

Baseline failures were rare and numeric: an average computed over the wrong rows, and a row count off by one after dedupe or filter. Do the work in pandas, then make the log describe what you did.

## Method

1. Load the CSV with `dtype=str` first and look at it: columns, blanks, duplicate rows, mixed formats. Note each defect before fixing any.
2. Apply the task's steps in the order it gives them. Order matters: trim before dedupe, cast before filter, filter before aggregate.
3. After each step, print the row count and a sample. Keep a running list: step, rows before, rows after.
4. Dedupe means exact duplicates unless the task names key columns. Compare after trimming and case-folding only when the task says rows differing in case or spaces are the same.
5. Missing values: fill or drop exactly as the task says. If it does not say, keep the row and fill nothing.
6. Averages and sums use the rows that remain at that step, after casting to numbers; blanks are skipped, not zero.
7. Group results keep the task's group names as they appear in the data.
8. Write `out/result.csv` with `index=False`. Dates stay in the format the task asks for.

## The change log

- `ops` lists the operations you applied, in order, using only the shapes in your agent prompt. Each op matches what the code did, with the same columns and values.
- `findings` states what you counted: rows removed and why, values filled, groups produced. Each number comes from your printed trace.

## Self-check before you finish

Reload `out/result.csv`. Confirm the header, the row count against your trace, that no column holds mixed types, and that every op in `changes.json` has the exact field names the prompt lists.
