---
name: analysis-answers
description: Checklist for data-analysis tasks that return computed answers plus a chart: compute from the data, keep types, verify chart points. Load before writing analysis.json.
license: MIT
metadata:
  source: original, written for agent-route from the agents-cc-20261031 runs
---
# Answering questions with computed numbers

## Method

1. Load the file with pandas. Print `dtypes`, `head()` and the count of missing values per column before computing anything.
2. Answer each question with code, never by eye. Use the exact column the question names. Print each answer with its question ID.
3. Respect the wording: "mean" versus "median", "per group" versus "overall", sample versus population standard deviation (pandas defaults to sample), "top" meaning highest.
4. Ties and ordering: if two groups tie for first, pick by the order of the question text, and say so in `insights`.
5. Keep numbers unrounded unless the task says how to round. Use native Python numbers in the JSON (`float(x)`, `int(x)`), not numpy types.
6. Category answers match the data's own spelling and case.
7. The chart plots the data of the main question: one point per category or bin, at most 50 points, with the keys your `xAxisKey` and `yAxisKeys` name. Sort bars by the question's order or by value, whichever the question implies.
8. `insights` each carry a number that appears in your printed output.

## Self-check before you finish

Reload `out/analysis.json`. Confirm every question ID has an answer of the right type, each chart point has the declared keys, and no value is NaN (JSON cannot hold it).
