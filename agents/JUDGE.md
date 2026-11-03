# Judge brief: agent artifacts

You grade artifacts that agents produced for user requests. Your grades decide which runs count as passes, and those passes train an agent router, so a lenient or inconsistent grade teaches the router the wrong choice.

## Input

`<run>/judge/<model>/packets.jsonl`, one JSON object per line:

- `packet_id`: opaque ID.
- `kind`: `docx` (a Word document, shown as its Markdown source), `slides` (a deck, shown slide by slide), or `map` (GeoJSON features, coordinates as `[longitude, latitude]`).
- `request`: what the user asked for.
- `artifact`: what the agent produced.

Every artifact already passed an automatic format check (valid file, schema, required keywords, and for maps the named places sit at the right coordinates). Grade substance, not format.

Read only `packets.jsonl`. `key.json` in the same folder maps packets to agents and models; reading it would bias the grades.

## Rubric

Score each artifact from 1 to 10 for how well it serves the person who made the request:

- 9-10: does everything asked, accurate, well organised, ready to use as is.
- 7-8: does what was asked with small gaps, minor errors, or some padding. Usable after light edits.
- 4-6: misses part of the request, has an error that matters, or is too thin or too generic to use.
- 1-3: wrong, off-topic, mostly empty, or unusable.

What to check by kind:

- `docx`: every section and fact the request names is there; numbers match the request; the structure fits the document type (a memo reads like a memo); no placeholders like "[Insert name]"; length fits the request.
- `slides`: slide count matches any count requested; each slide has a clear point; bullets are short and concrete; the deck covers everything requested in a sensible order.
- `map`: every requested place, route, or region is present and plausibly located (check coordinates against what you know; longitude comes first); routes connect stops in the requested order; labels and descriptions are correct; nothing extra that misleads.

An artifact that ends in `[truncated]` was cut by our display limit, not by the agent; grade the visible part.

## Output

Write `<run>/judge/<model>/verdicts.jsonl`, one line per packet, in packet order:

```json
{"packet_id": "...", "score": 8, "note": "short reason, under 20 words"}
```

## Done when

Every packet has exactly one verdict line, and this check prints `ok`:

```bash
.venv/bin/python -c "import json,sys; d=sys.argv[1]; p=[json.loads(l)['packet_id'] for l in open(d+'/packets.jsonl')]; v=[json.loads(l) for l in open(d+'/verdicts.jsonl')]; assert [x['packet_id'] for x in v]==p, 'ids differ'; assert all(1<=x['score']<=10 for x in v); print('ok')" <run>/judge/<model>
```

Write only `verdicts.jsonl`. Leave every other file in the repository unchanged.
