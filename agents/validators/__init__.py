"""Validators for the eight phase 2 agents.

validate(agent, check, workspace) reads the agent's artifact from its fixed
path under <workspace>/out/ and returns {'passed': bool, 'detail': str}.
`check` is the task's check spec for that agent (see agents/tasks/README.md).
Docx, slides, and map runs also get a judge verdict later; this module only
covers the automatic part.
"""
import json
import math
import pathlib
import re
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
JS = HERE / 'js'
sys.path.insert(0, str(HERE.parents[1] / 'benchmarking' / 'pool'))
import score as pool_score  # noqa: E402

ARTIFACTS = {
    'code': ['out/solution.py'],
    'spreadsheet': ['out/result.csv', 'out/changes.json'],
    'data-analysis': ['out/analysis.json'],
    'docx': ['out/document.json', 'out/document.docx'],
    'slides': ['out/slides.json'],
    'diagram': ['out/diagram.json'],
    'map': ['out/map.json'],
    'scene-3d': ['out/scene.jsonl'],
}
JUDGED = {'docx', 'slides', 'map'}
NUM_TOL = 0.002  # relative tolerance, with an absolute floor that allows rounding to 1 decimal
ABS_TOL = 0.051


class Fail(Exception):
    pass


def ok(detail):
    return {'passed': True, 'detail': detail}


def need(cond, detail):
    if not cond:
        raise Fail(detail)


def load_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise Fail(f'{path.name} is not valid JSON: {str(e)[:120]}')


def to_number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else None
    if isinstance(value, str):
        s = value.strip().replace(',', '').replace('$', '').replace('%', '')
        try:
            return float(s)
        except ValueError:
            return None
    return None


def close(got, want, tol=None):
    g, w = to_number(got), to_number(want)
    if g is None or w is None:
        return isinstance(got, str) and isinstance(want, str) and got.strip().casefold() == want.strip().casefold()
    tol = NUM_TOL if tol is None else tol
    return abs(g - w) <= max(ABS_TOL, tol * abs(w))


def numbers_in(text):
    return [float(m.replace(',', '')) for m in re.findall(r'-?\d[\d,]*\.?\d*(?:[eE]-?\d+)?|-?\.\d+', text)
            if to_number(m.replace(',', '')) is not None]


def has_numbers(found, wanted):
    missing = [w for w in wanted if not any(close(f, w) for f in found)]
    need(not missing, f'missing expected values {missing[:5]}')


def keyword_hits(text, keywords):
    """Each keyword is a string or a list of alternatives; return the ones not found."""
    low = text.casefold()
    missing = []
    for kw in keywords or []:
        options = kw if isinstance(kw, list) else [kw]
        if not any(o.casefold() in low for o in options):
            missing.append(options[0])
    return missing


def check_keywords(text, keywords):
    missing = keyword_hits(text, keywords)
    need(not missing, f'missing required content: {missing[:5]}')


# --- code -----------------------------------------------------------------

def validate_code(check, ws):
    path = ws / 'out/solution.py'
    code = path.read_text()
    need(code.strip(), 'empty solution.py')
    kind = check['type']
    if kind in ('code_stdio', 'code_func'):
        fn = pool_score.score_code_stdio if kind == 'code_stdio' else pool_score.score_code_func
        out = fn(check, {'content': code})
        return {'passed': bool(out['passed']), 'detail': out['detail']}
    if kind == 'code_numbers':
        files = {'solution.py': code}
        for name in check.get('inputs', []):
            files[pathlib.Path(name).name] = (ws / 'inputs' / pathlib.Path(name).name).read_text()
        proc = sandbox_with_inputs(files, check.get('timeout_s', 60))
        need(proc is not None, 'sandbox timeout')
        need(proc.returncode == 0, f'solution.py exited {proc.returncode}: {(proc.stderr.strip().splitlines() or [""])[-1][:160]}')
        has_numbers(numbers_in(proc.stdout), check['expect_numbers'])
        return ok('printed every expected value')
    raise ValueError(f'unknown code check {kind}')


def sandbox_with_inputs(files, timeout_s):
    """Run solution.py with its input files beside it, in both . and inputs/."""
    with tempfile.TemporaryDirectory() as tmp:
        (pathlib.Path(tmp) / 'inputs').mkdir()
        for name, body in files.items():
            pathlib.Path(tmp, name).write_text(body)
            if name != 'solution.py':
                pathlib.Path(tmp, 'inputs', name).write_text(body)
        argv = ['docker', 'run', '--rm', '--network', 'none', '--memory', '1g', '--cpus', '1', '--pids-limit', '64',
                '-v', f'{tmp}:/src:ro', '-w', '/work', '--tmpfs', '/work:uid=1000', 'agent-route-opencode',
                'sh', '-c', 'cp -r /src/. /work/ && python solution.py']
        try:
            return subprocess.run(argv, capture_output=True, text=True, timeout=timeout_s + 30)
        except subprocess.TimeoutExpired:
            return None


# --- spreadsheet ----------------------------------------------------------

STR, NUM, ANY = str, (int, float), (str, int, float, bool)
# Port of the block's agentOpSchema (lib/ops/schema.ts), minus aiColumn and
# generateRows: those call a model per row, which the sandbox cannot do.
OPS = {
    'dropColumns': {'columns': list},
    'renameColumn': {'from': STR, 'to': STR},
    'fillMissing': {'column': STR, 'method': ('value', 'mean', 'median', 'mode'), 'value?': ANY},
    'dedupeRows': {'columns?': list, 'keep?': ('first', 'last')},
    'castColumn': {'column': STR, 'to': ('number', 'date', 'string', 'boolean')},
    'trimWhitespace': {'columns?': list},
    'filterRows': {'column': STR, 'operator': ('eq', 'neq', 'gt', 'gte', 'lt', 'lte', 'contains', 'isEmpty', 'isNotEmpty'),
                   'value?': ANY},
    'sortRows': {'column': STR, 'direction?': ('asc', 'desc')},
    'addComputedColumn': {'left': STR, 'name': STR, 'operator': ('add', 'subtract', 'multiply', 'divide'), 'right': STR},
    'aggregate': {'groupBy': list, 'measures': list},
    'textLength': {'column': STR, 'name': STR},
    'rankRows': {'by': STR, 'name': STR, 'direction?': ('asc', 'desc'), 'groupBy?': list},
}
MEASURE_FNS = ('sum', 'avg', 'count', 'min', 'max')
CHART_TYPES = ('bar', 'line', 'area', 'pie')


def check_op(op):
    need(isinstance(op, dict), 'op is not an object')
    name = op.get('op')
    need(name in OPS, f'unknown op {name!r}')
    spec = OPS[name]
    for key, kind in spec.items():
        optional = key.endswith('?')
        key = key.rstrip('?')
        if key not in op:
            need(optional, f'{name} missing {key}')
            continue
        value = op[key]
        if isinstance(kind, tuple) and all(isinstance(k, str) for k in kind):
            need(value in kind, f'{name}.{key}={value!r} not allowed')
        elif kind is list:
            need(isinstance(value, list) and (optional or value), f'{name}.{key} must be a non-empty list')
        else:
            need(isinstance(value, kind) and value != '', f'{name}.{key} has the wrong type')
    extra = set(op) - {k.rstrip('?') for k in spec} - {'op'}
    need(not extra, f'{name} has unknown fields {sorted(extra)}')
    if name == 'aggregate':
        for m in op['measures']:
            need(isinstance(m, dict) and m.get('fn') in MEASURE_FNS and isinstance(m.get('as'), str),
                 'aggregate measure needs fn and as')


def read_csv(path):
    import csv
    with open(path, newline='') as f:
        rows = list(csv.reader(f))
    need(rows and rows[0], 'result.csv is empty')
    header = [h.strip() for h in rows[0]]
    return header, [dict(zip(header, r)) for r in rows[1:] if any(c.strip() for c in r)]


def find_column(header, name):
    for h in header:
        if h.casefold() == name.casefold():
            return h
    raise Fail(f'result.csv has no column {name!r} (has {header[:10]})')


def check_table(check, header, rows, label):
    if 'expect_rows' in check:
        need(len(rows) == check['expect_rows'], f'{label} has {len(rows)} rows, want {check["expect_rows"]}')
    for col in check.get('expect_columns', []):
        find_column(header, col)
    for col in check.get('forbid_columns', []):
        need(all(h.casefold() != col.casefold() for h in header), f'{label} still has column {col!r}')
    for cell in check.get('expect_cells', []):
        keys = {find_column(header, k): v for k, v in cell['key'].items()}
        vc = find_column(header, cell['column'])
        hits = [r for r in rows if all(close((r.get(k) or '').strip(), v, 0) for k, v in keys.items())]
        need(hits, f'no row with {cell["key"]}')
        need(close((hits[0].get(vc) or '').strip(), cell['value'], cell.get('tol')),
             f'{cell["key"]}: {cell["column"]}={hits[0].get(vc)!r}, want {cell["value"]!r}')
    if 'expect_order' in check:
        col = find_column(header, check['expect_order']['column'])
        want = check['expect_order']['values']
        got = [r.get(col, '') for r in rows[:len(want)]]
        need(all(close(g, w, 0) for g, w in zip(got, want)) and len(got) == len(want),
             f'first rows of {col} are {got}, want {want}')
    if 'expect_numbers' in check:
        has_numbers([n for r in rows for v in r.values() if (n := to_number(v)) is not None], check['expect_numbers'])
    if 'expect_names' in check:
        want = {w.casefold() for w in check['expect_names']}
        cols = [{(r.get(h) or '').strip().casefold() for r in rows} for h in header]
        need(any(c == want for c in cols), f'no column holds exactly the expected {len(want)} names')


def validate_spreadsheet(check, ws):
    header, rows = read_csv(ws / 'out/result.csv')
    changes = load_json(ws / 'out/changes.json')
    need(isinstance(changes, dict) and isinstance(changes.get('ops'), list) and changes['ops'],
         'changes.json needs a non-empty "ops" list')
    need(len(changes['ops']) <= 20, 'more than 20 ops')
    for op in changes['ops']:
        check_op(op)
    if changes.get('chart') is not None:
        c = changes['chart']
        need(isinstance(c, dict) and c.get('type') in CHART_TYPES and c.get('title') and c.get('xKey')
             and isinstance(c.get('yKeys'), list) and c['yKeys'], 'chart does not match the chart spec schema')
    for f in changes.get('findings') or []:
        need(isinstance(f, dict) and f.get('label') and 'value' in f, 'finding needs label and value')
    check_table(check, header, rows, 'result.csv')
    return ok(f'{len(changes["ops"])} ops, {len(rows)} rows, expected cells match')


# --- data analysis --------------------------------------------------------

DA_CHARTS = ('bar', 'line', 'scatter', 'histogram', 'pie', 'area')


def validate_data_analysis(check, ws):
    doc = load_json(ws / 'out/analysis.json')
    need(isinstance(doc, dict), 'analysis.json must be an object')
    answers = doc.get('answers')
    need(isinstance(answers, dict), 'analysis.json needs an "answers" object')
    chart = doc.get('chart')
    need(isinstance(chart, dict), 'analysis.json needs a "chart" object')
    need(chart.get('chartType') in DA_CHARTS, f'chartType {chart.get("chartType")!r} not supported')
    need(isinstance(chart.get('title'), str) and chart['title'], 'chart needs a title')
    need(isinstance(chart.get('xAxisKey'), str) and chart['xAxisKey'], 'chart needs xAxisKey')
    ykeys = chart.get('yAxisKeys')
    need(isinstance(ykeys, list) and ykeys, 'chart needs yAxisKeys')
    data = chart.get('data')
    need(isinstance(data, list) and data and all(isinstance(p, dict) for p in data), 'chart needs data points')
    if chart['chartType'] == 'pie':
        need(all('name' in p and 'value' in p for p in data), 'pie data points need name and value')
    else:
        need(all(chart['xAxisKey'] in p or 'bin' in p for p in data), 'data points miss the xAxisKey')
        need(all(any(k in p for k in ykeys) for p in data), 'data points miss the yAxisKeys')
    if 'chart_types' in check:
        need(chart['chartType'] in check['chart_types'], f'chartType {chart["chartType"]}, want one of {check["chart_types"]}')
    for qid, want in (check.get('answers') or {}).items():
        need(qid in answers, f'no answer for {qid}')
        need(close(answers[qid], want['value'], want.get('tol')), f'{qid}={answers[qid]!r}, want {want["value"]!r}')
    if 'expect_numbers' in check:
        found = [n for v in answers.values() for n in ([to_number(v)] if not isinstance(v, str) else numbers_in(v))
                 if n is not None]
        has_numbers(found, check['expect_numbers'])
    return ok(f'{len(answers)} answers correct, {chart["chartType"]} chart with {len(data)} points')


# --- docx -----------------------------------------------------------------

def validate_docx(check, ws):
    doc = load_json(ws / 'out/document.json')
    need(isinstance(doc, dict) and isinstance(doc.get('title'), str) and doc['title'].strip(),
         'document.json needs a title')
    md = doc.get('markdown')
    need(isinstance(md, str) and md.strip(), 'document.json needs markdown')
    need(re.search(r'^#{1,3} \S', md, re.M), 'markdown has no heading')
    import docx
    try:
        word = docx.Document(str(ws / 'out/document.docx'))
    except Exception as e:  # python-docx raises several types for broken files
        raise Fail(f'document.docx does not open: {str(e)[:120]}')
    text = '\n'.join(p.text for p in word.paragraphs)
    text += '\n'.join(c.text for t in word.tables for r in t.rows for c in r.cells)
    words = len(text.split())
    need(words >= check.get('min_words', 100), f'document.docx has {words} words, want >= {check.get("min_words", 100)}')
    check_keywords(md, check.get('keywords'))
    return ok(f'docx opens, {words} words')


# --- slides ---------------------------------------------------------------

def validate_slides(check, ws):
    deck = load_json(ws / 'out/slides.json')
    need(isinstance(deck, list) and deck, 'slides.json must be a non-empty array')
    for i, s in enumerate(deck):
        need(isinstance(s, dict), f'slide {i} is not an object')
        need(isinstance(s.get('title'), str) and s['title'].strip(), f'slide {i} needs a title')
        need(isinstance(s.get('bullets'), list) and all(isinstance(b, str) for b in s['bullets']),
             f'slide {i} needs a bullets array of strings')
        for key in ('body', 'id', 'imageUrl'):
            need(key not in s or isinstance(s[key], str), f'slide {i} {key} must be a string')
    lo, hi = check.get('min_slides', 1), check.get('max_slides', 30)
    need(lo <= len(deck) <= hi, f'{len(deck)} slides, want {lo}-{hi}')
    check_keywords(json.dumps(deck, ensure_ascii=False), check.get('keywords'))
    return ok(f'{len(deck)} slides match the deck schema')


# --- diagram --------------------------------------------------------------

SMART = {'‘': "'", '’': "'", '“': '"', '”': '"'}


def sanitize_mermaid(src):
    """The block's light repairs: strip fences, straighten quotes."""
    src = src.strip()
    src = re.sub(r'^```(?:mermaid)?\s*\n?', '', src, flags=re.I)
    src = re.sub(r'\n?```\s*$', '', src)
    for a, b in SMART.items():
        src = src.replace(a, b)
    return src.strip()


def render_mermaid(src):
    with tempfile.TemporaryDirectory() as tmp:
        inp, out = pathlib.Path(tmp, 'd.mmd'), pathlib.Path(tmp, 'd.svg')
        inp.write_text(src)
        try:
            proc = subprocess.run([str(JS / 'node_modules/.bin/mmdc'), '-p', str(JS / 'puppeteer.json'), '-q',
                                   '-i', str(inp), '-o', str(out)], capture_output=True, text=True, timeout=90)
        except subprocess.TimeoutExpired:
            raise Fail('mermaid render timed out')
        if proc.returncode != 0 or not out.exists():
            err = [l for l in proc.stderr.splitlines() if 'Error' in l or 'error' in l]
            raise Fail(f'mermaid does not render: {(err or proc.stderr.splitlines() or ["?"])[0][:200]}')
        return out.stat().st_size


def validate_diagram(check, ws):
    doc = load_json(ws / 'out/diagram.json')
    need(isinstance(doc, dict) and doc.get('format') == 'mermaid', 'diagram.json needs format "mermaid"')
    src = doc.get('source')
    need(isinstance(src, str) and src.strip(), 'diagram.json needs source')
    src = sanitize_mermaid(src)
    first = next(l.strip() for l in src.splitlines() if l.strip() and not l.strip().startswith('%%'))
    if 'diagram_types' in check:
        need(any(first.startswith(t) for t in check['diagram_types']),
             f'diagram starts with {first[:30]!r}, want one of {check["diagram_types"]}')
    check_keywords(src, check.get('keywords'))
    size = render_mermaid(src)
    return ok(f'{first.split()[0]} renders ({size} bytes svg)')


# --- map ------------------------------------------------------------------

GEOMS = ('Point', 'LineString', 'Polygon', 'MultiPoint', 'MultiLineString', 'MultiPolygon')


def is_position(p):
    return (isinstance(p, list) and len(p) in (2, 3) and all(to_number(v) is not None and not isinstance(v, str) for v in p)
            and -180 <= p[0] <= 180 and -90 <= p[1] <= 90)


def check_geometry(g, i):
    t, c = g.get('type'), g.get('coordinates')
    need(t in GEOMS, f'feature {i} geometry type {t!r} not supported')
    need(isinstance(c, list) and c, f'feature {i} needs coordinates')
    depth = {'Point': 0, 'LineString': 1, 'MultiPoint': 1, 'Polygon': 2, 'MultiLineString': 2, 'MultiPolygon': 3}[t]

    def walk(node, d):
        if d == 0:
            need(is_position(node), f'feature {i} has a bad position {str(node)[:40]} (want [lng, lat])')
            return
        need(isinstance(node, list) and node, f'feature {i} coordinates nest wrongly for {t}')
        for n in node:
            walk(n, d - 1)
    walk(c, depth)
    if t == 'LineString':
        need(len(c) >= 2, f'feature {i} LineString needs 2+ positions')
    rings = [c] if t == 'Polygon' else c if t == 'MultiPolygon' else []
    for poly in rings:
        for ring in poly:
            need(len(ring) >= 4 and ring[0][:2] == ring[-1][:2], f'feature {i} polygon ring is not closed')


def km(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def positions(g):
    c = g['coordinates']
    return [c] if g['type'] == 'Point' else [p for p in _flatten(c)]


def _flatten(node):
    if is_position(node):
        yield node
    else:
        for n in node:
            yield from _flatten(n)


def validate_map(check, ws):
    doc = load_json(ws / 'out/map.json')
    need(isinstance(doc, dict) and doc.get('format') == 'geojson', 'map.json needs format "geojson"')
    col = doc.get('collection')
    need(isinstance(col, dict) and col.get('type') == 'FeatureCollection', 'collection must be a FeatureCollection')
    feats = col.get('features')
    need(isinstance(feats, list) and feats, 'collection needs features')
    for i, f in enumerate(feats):
        need(isinstance(f, dict) and f.get('type') == 'Feature' and isinstance(f.get('geometry'), dict),
             f'feature {i} is not a GeoJSON Feature')
        need(f.get('properties') is None or isinstance(f['properties'], dict), f'feature {i} properties must be an object')
        check_geometry(f['geometry'], i)
    need(len(feats) >= check.get('min_features', 1), f'{len(feats)} features, want >= {check.get("min_features", 1)}')
    types = {f['geometry']['type'] for f in feats}
    for t in check.get('geometry_types', []):
        options = t if isinstance(t, list) else [t]
        need(types & set(options), f'no {"/".join(options)} feature')
    # Places count when marked by a point or a region; a route line passing nearby does not.
    points = [p for f in feats if 'LineString' not in f['geometry']['type'] for p in positions(f['geometry'])]
    for target in check.get('places', []):
        best = min((km(p, (target['lon'], target['lat'])) for p in points), default=float('inf'))
        need(best <= target.get('tol_km', 25), f'nothing within {target.get("tol_km", 25)} km of {target["name"]} '
                                                 f'(nearest {best:.0f} km)')
    if 'expect_names' in check:
        names = [str((f.get('properties') or {}).get('name', '')).casefold() for f in feats
                 if f['geometry']['type'] == 'Point']
        missing = [n for n in check['expect_names'] if not any(n.casefold() in m for m in names)]
        need(not missing, f'no point named {missing[:4]}')
        need(len(names) == len(check['expect_names']), f'{len(names)} points, want exactly {len(check["expect_names"])}')
    return ok(f'{len(feats)} valid features')


# --- scene ----------------------------------------------------------------

def validate_scene(check, ws):
    path = ws / 'out/scene.jsonl'
    try:
        proc = subprocess.run(['bun', str(JS / 'scene.mjs'), 'validate', str(path)], capture_output=True, text=True,
                              timeout=60, cwd=JS)
        out = json.loads(proc.stdout.strip().splitlines()[-1])
    except (subprocess.TimeoutExpired, IndexError, json.JSONDecodeError):
        raise Fail('scene validator crashed')
    need(out['passed'], out['detail'])
    types = out['types']
    need(len(types) >= check.get('min_elements', 1), f'{len(types)} elements, want >= {check.get("min_elements", 1)}')
    for t in check.get('require_types', []):
        options = t if isinstance(t, list) else [t]
        need(set(options) & set(types), f'scene has no {"/".join(options)}')
    return ok(out['detail'])


VALIDATORS = {
    'code': validate_code,
    'spreadsheet': validate_spreadsheet,
    'data-analysis': validate_data_analysis,
    'docx': validate_docx,
    'slides': validate_slides,
    'diagram': validate_diagram,
    'map': validate_map,
    'scene-3d': validate_scene,
}


def validate(agent, check, workspace):
    ws = pathlib.Path(workspace)
    missing = [p for p in ARTIFACTS[agent] if not (ws / p).is_file()]
    if missing:
        return {'passed': False, 'detail': f'missing artifact {", ".join(missing)}'}
    try:
        return VALIDATORS[agent](check, ws)
    except Fail as e:
        return {'passed': False, 'detail': str(e)}
