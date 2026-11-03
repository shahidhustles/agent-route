# Agent skills

Live agents build real files with Anthropic's own skills, and the app previews those files. This replaces the first design (our own MIT skills over JSON contracts), which the 2026-11-01 vetting rejected Anthropic's skills for. The user decided this on 2026-11-02 and the decision is final.

## Source, pin and licence

Skills come from `https://github.com/anthropics/skills`, folder `skills/`, pinned at commit `ca45fc496a3436251f191354091d557da31c15b5`. Their licence is Anthropic's proprietary terms (`LICENSE.txt` inside each folder), which bar copying and derivatives outside Anthropic's services. So the repo never tracks them and nothing edits them:

```
agents/sandbox/fetch_skills.sh      # fetches the pin into agents/opencode/skills-files (gitignored), unmodified
```

The script fetches `pptx`, `docx`, `xlsx`, `pdf` and `frontend-design`, then copies our own MIT `code-solutions` beside them. `docker_argv(contract='files')` in `agents/run.py` mounts that folder read-only at `/home/runner/.config/opencode/skills`, so each skill's scripts resolve at `/home/runner/.config/opencode/skills/<skill>/scripts/...`. Anything specific to this project (output path, truthfulness rule, QA budget) lives in the agent prompts, `agents/opencode/agent/*.md`.

## Mapping

| Agent | Skill | Output |
|---|---|---|
| slides | `pptx` | `out/deck.pptx` (pptxgenjs) |
| docx | `docx` | `out/document.docx` (docx-js) |
| spreadsheet | `xlsx` | `out/workbook.xlsx` (openpyxl, `recalc.py`) |
| data-analysis | `xlsx` | `out/analysis.xlsx` with native charts. No repo skill teaches charting beyond `xlsx`, so it has no second skill |
| diagram | `frontend-design` | `out/diagram.html`, inline SVG (Graphviz `dot` is installed for layout) |
| map | `frontend-design` | `out/map.geojson` plus `out/map.html`, inline SVG projected from the GeoJSON |
| scene-3d | `frontend-design` | `out/scene.html` with three.js r147 inlined |
| code | `code-solutions` (ours) | `out/solution.py`, unchanged. No Anthropic skill beats a 40-line test-first checklist for one stdlib file |

I chose `frontend-design` for the three HTML agents because it is design guidance, not a toolchain. `web-artifacts-builder` runs `npm install` and fetches components at build time, which the sandbox forbids. `canvas-design` makes raster art, not diagrams. `npx skills find` was not rerun for this change.

Every prompt carries the truthfulness rule near the top ("Use only facts from the request and the attached files... mark any assumption"). That targets the known failure on slides and docx in `agents-cc-20261031`: invented interviews, survey numbers and quotes.

## Sandbox

`agents/sandbox/Dockerfile` installs what the skills name, so a run never installs anything: Node with `pptxgenjs`, `docx`, `react-icons`, `react`, `react-dom`, `sharp` and `three@0.147`; LibreOffice Writer, Impress and Calc; `poppler-utils`, `pandoc`, `graphviz`; `markitdown`, `Pillow`, `defusedxml`, `lxml`, `openpyxl`; Carlito, Caladea, Liberation, DejaVu and URW fonts (metric-compatible stand-ins for Calibri, Cambria and Century Schoolbook). The image is 3.2 GB. Limits for `files` runs: `--memory 3g`, `--pids-limit 512`, run timeout 900 s (JSON runs keep 2g, 256, 600). `opencode` 2.1.4 still loads skills from the read-only mount.

`build.sh` assembles its build context under `agents/sandbox/.ctx.*` because `/tmp` is a quota-limited tmpfs.

## Contracts and checks

`docker_argv(contract='json')` is the recorded suite: `agents/opencode/agent-json` prompts, `agents/opencode/skills`, and the JSON validators in `agents/validators/__init__.py`. `agents-cc-20261031` still reproduces. `agents/adhoc.py` (the app) uses `contract='files'` and `agents/validators/files.py`, which opens the real file with the standard library: slide count, words, pictures or charts, placeholder text, formula errors and uncalculated formulas, a chart in an analysis workbook, inline SVG, inlined three.js, and no network reference in HTML. `agents/test_files.py` covers it.

## Preview

The artifact panel shows the real result for runs under the file contract. Recorded artifacts and runs saved before this change keep the JSON renderers.

- `.pptx`, `.docx`, `.xlsx`: `agents/preview.py` runs `ar-preview` in the agent image with `--network none --read-only --cap-drop ALL`, the input mounted read-only. LibreOffice makes a PDF and `pdftoppm` makes page images and thumbnails (about 3 s). The panel shows slides with previous and next, arrow keys and thumbnails; documents as scrolling pages; workbooks as a sheet grid with fills, fonts and number formats (`ar-sheets-json`) plus the printed pages, where charts show. A skeleton shows during conversion, and a failure shows the message with a retry. Download links serve the real file.
- `.html`: the panel loads `GET /runs/<id>/view/<name>` in an iframe with `sandbox="allow-scripts"` and no same-origin access. The backend also sends a CSP (`default-src 'none'`, inline script and style only), so the page cannot reach the network even if an agent ignores the rule.

`/?artifact=<run id>` reopens a run's preview. `agents/fixtures/make_fixture_runs.py` builds free hand-written fixtures (deck, document, workbook, diagram, map, scene) as runs `fixture-*`, to test the panel without a model call.

## Sandbox helpers and what the first runs taught

- `ar-look <file> <out.jpg>` renders a deck, document or workbook into one labelled contact sheet, so an agent reads one image per review round instead of one per page. It replaced per-slide conversion, which drove a 28-call, USD 0.043 slides run to 12 calls and USD 0.020.
- `/usr/local/lib/ar/pptx_helpers.js` gives `icon()` (react-icons to PNG) and the pptxgenjs shape names. The skill points at a `pptxgenjs.md` reference that its pinned commit does not contain, so agents had been guessing names.
- The docx validator rejects a table wider than the text area. A GLM docx run produced 12060-twip tables on a 9026-twip text width, and the contact sheet showed them clipped at the page edge.
- Diagram and map prompts now ask for a main SVG with a viewBox of at most 800 units; the first runs rendered a tiny diagram next to an oversized legend.
- Prompts forbid inventing the story around the numbers (market, customer pain, how the pilot ran); GLM wrote such claims unlabelled until the rule was added, and some mild interpretation still slips through.

## Known gaps

- Agent runs take 2 to 6 minutes on GLM; docx and diagram runs still spend several calls on review.
- The backend's `?artifact` links need the run's artifact, which a stopped run does not store.
- `agents/test_validators.py::test_diagram_renders` fails on this machine: the recorded-suite mermaid check (host puppeteer with Chrome headless shell 153) dies with `ConnectionClosedError`. It does not touch the live file contract.
