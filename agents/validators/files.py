"""Validators for the file contract: the agents' real .pptx, .docx, .xlsx and self-contained HTML outputs.

validate_files(agent, check, workspace) opens the artifact and returns {'passed': bool, 'detail': str}. It reads
Office files with the standard library (zipfile and regular expressions), so the host needs no Office packages and
never executes anything from the file. `check` may hold `slides` (exact count), `min_slides`, `pages_min_words`,
`keywords` (strings or lists of alternatives, matched against the file's text), `sheets` (names that must exist).
The JSON validators in `__init__.py` stay as they are for the recorded suite.
"""
import json
import pathlib
import re
import zipfile

MAX_PART = 40_000_000  # bytes a single zip entry may expand to
PLACEHOLDER = re.compile(r'lorem ipsum|\[insert|\bTODO\b|\bTBD\b|\bx{4,}\b', re.I)
EXCEL_ERRORS = ('#REF!', '#DIV/0!', '#VALUE!', '#NAME?', '#N/A', '#NULL!', '#NUM!')

ARTIFACTS = {
    'code': ['out/solution.py'],
    'spreadsheet': ['out/workbook.xlsx'],
    'data-analysis': ['out/analysis.xlsx'],
    'docx': ['out/document.docx'],
    'slides': ['out/deck.pptx'],
    'diagram': ['out/diagram.html'],
    'map': ['out/map.html', 'out/map.geojson'],
    'scene-3d': ['out/scene.html'],
}


class Fail(Exception):
    pass


def need(cond, detail):
    if not cond:
        raise Fail(detail)


def open_zip(path, name):
    need(path.is_file(), f'missing artifact out/{path.name}')
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise Fail(f'{path.name} is not a valid {name} file (not a zip archive)')
    for info in z.infolist():
        need(info.file_size < MAX_PART, f'{path.name} has an oversized part {info.filename}')
    return z


def xml_text(z, member):
    try:
        return z.read(member).decode('utf-8', errors='replace')
    except KeyError:
        raise Fail(f'{member} is missing from the file')


def runs(xml, tag):
    return [re.sub(r'&amp;', '&', re.sub(r'&lt;', '<', re.sub(r'&gt;', '>', t)))
            for t in re.findall(rf'<{tag}(?: [^>]*)?>([^<]*)</{tag}>', xml)]


def keywords_missing(text, keywords):
    low = text.casefold()
    return [(kw if isinstance(kw, list) else [kw])[0] for kw in keywords or []
            if not any(o.casefold() in low for o in (kw if isinstance(kw, list) else [kw]))]


def check_text(text, check):
    bad = PLACEHOLDER.search(text)
    need(not bad, f'placeholder text left in the file: "{bad[0]}"' if bad else '')
    missing = keywords_missing(text, check.get('keywords'))
    need(not missing, f'missing required content: {missing[:5]}')


def validate_slides(check, ws):
    path = ws / 'out' / 'deck.pptx'
    z = open_zip(path, 'PowerPoint')
    slides = sorted((n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml', n)),
                    key=lambda n: int(re.search(r'(\d+)', n)[1]))
    need(slides, 'the deck has no slides')
    if check.get('slides'):
        need(len(slides) == check['slides'], f'the deck has {len(slides)} slides, the task asked for {check["slides"]}')
    need(len(slides) >= check.get('min_slides', 1), f'the deck has {len(slides)} slides, fewer than {check.get("min_slides")}')
    texts, visual, empty = [], 0, 0
    for n in slides:
        xml = xml_text(z, n)
        t = ' '.join(runs(xml, 'a:t'))
        texts.append(t)
        empty += not t.strip()
        visual += bool(re.search(r'<p:pic[ >/]|<p:graphicFrame[ >/]|<a:prstGeom prst="(?!rect")', xml))
    all_text = '\n'.join(texts)
    words = len(all_text.split())
    need(words >= 15, f'the deck has only {words} words of text')
    need(not empty, f'{empty} of {len(slides)} slides have no text')
    check_text(all_text, check)
    return f'opens: {len(slides)} slides, {words} words, {visual} with a picture, chart or shape'


def validate_docx(check, ws):
    path = ws / 'out' / 'document.docx'
    z = open_zip(path, 'Word')
    xml = xml_text(z, 'word/document.xml')
    paras = re.findall(r'<w:p[ >].*?</w:p>', xml, re.S)
    text = '\n'.join(' '.join(runs(p, 'w:t')) for p in paras)
    words = len(text.split())
    need(words >= check.get('min_words', 40), f'the document has only {words} words')
    headings = len(re.findall(r'<w:pStyle w:val="(?:Heading|heading|Title)[^"]*"', xml))
    tables = xml.count('<w:tbl>')
    check_text(text, check)
    def attr(tag, name):
        m = re.search(rf'<{tag} [^>]*w:{name}="(\d+)"', xml)
        return int(m[1]) if m else None

    page, left, right = attr('w:pgSz', 'w'), attr('w:pgMar', 'left'), attr('w:pgMar', 'right')
    if None not in (page, left, right):
        room = page - left - right
        for tag in re.findall(r'<w:tblW [^>]*>', xml):
            if 'w:type="dxa"' in tag:
                w = int(re.search(r'w:w="(\d+)"', tag)[1])
                need(w <= room + 20, f'a table is {w} twips wide but the text area is {room}, so it runs off the page')
    return f'opens: {words} words, {headings} headings, {tables} tables'


def validate_workbook(check, ws, name, need_chart=False, need_sheet=None):
    path = ws / 'out' / name
    z = open_zip(path, 'Excel')
    book = xml_text(z, 'xl/workbook.xml')
    sheets = [re.sub('&amp;', '&', s) for s in re.findall(r'<sheet [^>]*name="([^"]+)"', book)]
    need(sheets, 'the workbook has no sheets')
    for s in check.get('sheets', []) + ([need_sheet] if need_sheet else []):
        need(s in sheets, f'sheet "{s}" is missing (sheets: {sheets})')
    cells = formulas = uncached = 0
    parts = [n for n in z.namelist() if re.fullmatch(r'xl/worksheets/sheet\d+\.xml', n)]
    strings = ' '.join(runs(xml_text(z, 'xl/sharedStrings.xml'), 't')) if 'xl/sharedStrings.xml' in z.namelist() else ''
    for n in parts:
        xml = xml_text(z, n)
        cells += len(re.findall(r'<c [^>]*>', xml))
        for m in re.finditer(r'<c [^>]*>(.*?)</c>', xml, re.S):
            if '<f' in m[1]:
                formulas += 1
                uncached += '<v>' not in m[1]
        bad = [e for e in EXCEL_ERRORS if f'<v>{e}</v>' in xml]
        need(not bad, f'formula errors in the workbook: {bad}')
    charts = len([n for n in z.namelist() if re.fullmatch(r'xl/charts/chart\d+\.xml', n)])
    need(cells >= 4, f'the workbook has only {cells} cells')
    need(not uncached, f'{uncached} formulas have no calculated value; run recalc.py')
    if need_chart:
        need(charts >= 1, 'the workbook has no chart')
    check_text(strings, check)
    return f'opens: {len(sheets)} sheets, {cells} cells, {formulas} formulas, {charts} charts'


EXTERNAL = re.compile(r'''(?:src|href)\s*=\s*["']\s*(?:https?:)?//|@import\s+(?:url\()?["']?\s*https?:|url\(\s*["']?https?:''', re.I)


def read_html(ws, name):
    path = ws / 'out' / name
    need(path.is_file(), f'missing artifact out/{name}')
    html = path.read_text(errors='replace')
    need(len(html) > 400, f'{name} is nearly empty')
    need(not EXTERNAL.search(html), f'{name} loads something from the network; it must be self-contained')
    return html


def validate_diagram(check, ws):
    html = read_html(ws, 'diagram.html')
    shapes = len(re.findall(r'<(?:rect|circle|ellipse|polygon|path|line|polyline)\b', html))
    labels = len(re.findall(r'<text\b', html))
    need('<svg' in html and shapes >= 3, 'diagram.html has no drawn SVG shapes')
    need(labels >= 2, 'diagram.html has no text labels')
    check_text(re.sub(r'<[^>]+>', ' ', html), check)
    return f'opens: inline SVG with {shapes} shapes and {labels} labels, no network references'


def validate_map(check, ws):
    html = read_html(ws, 'map.html')
    gj = ws / 'out' / 'map.geojson'
    need(gj.is_file(), 'missing artifact out/map.geojson')
    try:
        data = json.loads(gj.read_text())
    except ValueError as e:
        raise Fail(f'map.geojson is not valid JSON: {str(e)[:100]}')
    feats = data.get('features') if isinstance(data, dict) else None
    need(data.get('type') == 'FeatureCollection' and feats, 'map.geojson is not a non-empty FeatureCollection')
    need(all(isinstance(f, dict) and f.get('geometry') for f in feats), 'a feature in map.geojson has no geometry')
    need('<svg' in html, 'map.html has no inline SVG')
    check_text(re.sub(r'<[^>]+>', ' ', html), check)
    return f'opens: {len(feats)} features in GeoJSON, map.html draws inline SVG, no network references'


def validate_scene(check, ws):
    html = read_html(ws, 'scene.html')
    need('THREE' in html and re.search(r'WebGLRenderer', html), 'scene.html does not create a three.js renderer')
    need(len(html) > 100_000, 'three.js is not inlined into scene.html')
    need('OrbitControls' in html, 'scene.html has no orbit controls')
    check_text(re.sub(r'<[^>]+>', ' ', re.sub(r'<script.*?</script>', ' ', html, flags=re.S)), check)
    return f'opens: three.js inlined ({len(html) // 1024} KB), renderer and orbit controls present, no network references'


def validate_files(agent, check, ws):
    ws = pathlib.Path(ws)
    try:
        if agent == 'slides':
            return {'passed': True, 'detail': validate_slides(check, ws)}
        if agent == 'docx':
            return {'passed': True, 'detail': validate_docx(check, ws)}
        if agent == 'spreadsheet':
            return {'passed': True, 'detail': validate_workbook(check, ws, 'workbook.xlsx')}
        if agent == 'data-analysis':
            return {'passed': True, 'detail': validate_workbook(check, ws, 'analysis.xlsx', need_chart=True)}
        if agent == 'diagram':
            return {'passed': True, 'detail': validate_diagram(check, ws)}
        if agent == 'map':
            return {'passed': True, 'detail': validate_map(check, ws)}
        if agent == 'scene-3d':
            return {'passed': True, 'detail': validate_scene(check, ws)}
    except Fail as e:
        return {'passed': False, 'detail': str(e)}
    raise ValueError(f'no file validator for {agent}')
