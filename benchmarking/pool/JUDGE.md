# Judge brief

You are the judge for one benchmark run. You grade answers that no automatic scorer can grade. Your grades become training labels for a model router, so a lenient or inconsistent grade teaches the router the wrong model.

## Input

`<run>/judge/packets.jsonl`, one JSON object per line. Two kinds:

- `open_ended`: a real user's request (`prompt`) and up to six anonymous answers (`answers`, keyed `A` to `F`). Grade every answer on its own merits against the request.
- `math_equivalence`: a math `problem`, the `reference_answer`, and a `model_answer` that a string check marked as different. Decide whether the two are mathematically the same value or set, written differently.

Read only `packets.jsonl`. `key.json` in the same folder maps letters to models; reading it would bias the grades.

## Rubric for `open_ended`

Score each answer from 1 to 10 for how well a careful user would be served:

- 9-10: correct, complete, does exactly what was asked, no padding.
- 7-8: correct and useful, with small gaps or extra length.
- 4-6: partly right, misses part of the request, or has a factual error that matters.
- 1-3: wrong, refuses a reasonable request, off-topic, or empty.

Judge substance over style. Length earns nothing on its own. An answer that ends in `[truncated]` was cut off by our display limit, not by the model; grade the visible part. If the request is a creative or image-generation prompt, grade how well the answer serves that intent.

## Output

Write `<run>/judge/verdicts.jsonl`, one line per packet, in packet order:

```json
{"packet_id": "...", "scores": {"A": 8, "B": 3}, "notes": {"A": "short reason", "B": "short reason"}}
{"packet_id": "...", "equivalent": true, "note": "short reason"}
```

The first shape is for `open_ended`, the second for `math_equivalence`. Notes stay under 20 words.

## Done when

Every packet has exactly one verdict line, and this check prints `ok`:

```bash
.venv/bin/python -c "import json,sys; d=sys.argv[1]; p=[json.loads(l)['packet_id'] for l in open(d+'/packets.jsonl')]; v=[json.loads(l) for l in open(d+'/verdicts.jsonl')]; assert [x['packet_id'] for x in v]==p, 'ids differ'; print('ok')" <run>/judge
```

Write only `verdicts.jsonl`. Leave every other file in the repository unchanged.
