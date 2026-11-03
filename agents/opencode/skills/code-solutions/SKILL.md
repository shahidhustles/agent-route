---
name: code-solutions
description: Checklist for correct Python solutions to function or program tasks: read the spec, test edge cases, match the exact behaviour. Load before writing solution.py.
license: MIT
metadata:
  source: original, written for agent-route from the agents-cc-20261031 failures
---
# Writing a Python solution that passes hidden tests

Baseline failures came from a spec read loosely: an inverted boolean in a check, and a mistaken reading of what counts as a match. The tests are hidden, so the examples in the task are your only ground truth.

## Method

1. Restate the spec in one line to yourself: inputs, output type, what is true or false. For boolean tasks, say what `True` means in words.
2. Run every example in the task exactly as given, and assert the expected value. A passing assert beats a belief.
3. Think through the boundary cases before writing the final code:
   - empty input, one element, duplicates, negatives and zero;
   - type of the result: `int` versus `float`, `tuple` versus `list`, `None` versus an empty value;
   - ordering, and what happens on ties;
   - whether the task wants the first, last or all matches.
4. When the task text and a worked example disagree, trust the example, and mention the conflict in one line.
5. Use the signature, name and return type the task gives. Do not print inside a function that returns a value.
6. Prefer the simple standard approach over a clever one. Avoid mutating arguments unless the task says so.

## Reading hints

- "Check whether" returns a bool; "find" returns the value; "count" returns an int.
- "Subset", "substring" and "subsequence" mean different things. "Consecutive" means adjacent.
- Rounding or formatting instructions apply to the returned value.
- Programs that read stdin print exactly what the task specifies, one trailing newline, nothing else.

## Self-check before you finish

Run the file once with your edge cases and the task examples. Read `out/solution.py` back: no fences, no top-level test code or debug prints, imports present.
