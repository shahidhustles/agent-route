"""Unit tests for agents/validators. Run: .venv/bin/python -m unittest discover -s agents -p 'test_*.py'

The code tests need Docker (agent-route-sandbox, agent-route-opencode); the diagram
tests need Chrome for mermaid-cli; the scene tests need bun.
"""
import json
import pathlib
import sys

import shutil
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from validators import validate  # noqa: E402


def ws(tmp_path, files):
    for name, body in files.items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(body, bytes):
            p.write_bytes(body)
        else:
            p.write_text(body if isinstance(body, str) else json.dumps(body))
    return tmp_path


def test_missing_artifact(tmp_path):
    out = validate('slides', {}, tmp_path)
    assert not out['passed'] and 'missing artifact' in out['detail']


# --- code -----------------------------------------------------------------

FUNC_CHECK = {'type': 'code_func', 'test': 'assert add(2, 3) == 5\nassert add(-1, 1) == 0', 'timeout_s': 10}


def test_code_func_pass_and_fail(tmp_path):
    assert validate('code', FUNC_CHECK, ws(tmp_path, {'out/solution.py': 'def add(a, b):\n    return a + b\n'}))['passed']
    bad = validate('code', FUNC_CHECK, ws(tmp_path, {'out/solution.py': 'def add(a, b):\n    return a - b\n'}))
    assert not bad['passed']


def test_code_stdio(tmp_path):
    check = {'type': 'code_stdio', 'timeout_s': 5, 'tests': [{'input': '2 3\n', 'output': '5\n'}]}
    good = 'a, b = map(int, input().split())\nprint(a + b)\n'
    assert validate('code', check, ws(tmp_path, {'out/solution.py': good}))['passed']
    assert not validate('code', check, ws(tmp_path, {'out/solution.py': 'print(4)\n'}))['passed']


def test_code_numbers_reads_inputs(tmp_path):
    check = {'type': 'code_numbers', 'inputs': ['d.csv'], 'expect_numbers': [6.0, 15.5]}
    files = {'inputs/d.csv': 'g,v\na,1\na,5\nb,15.5\n',
             'out/solution.py': 'import pandas as pd\ndf = pd.read_csv("inputs/d.csv")\nprint(df.groupby("g").v.sum())\n'}
    assert validate('code', check, ws(tmp_path, files))['passed']
    files['out/solution.py'] = 'print("a 6")\n'
    assert not validate('code', check, ws(tmp_path, files))['passed']


# --- spreadsheet ----------------------------------------------------------

SHEET_CHECK = {'expect_rows': 2, 'forbid_columns': ['notes'], 'expect_order': {'column': 'id', 'values': ['b', 'a']},
               'expect_cells': [{'key': {'id': 'a'}, 'column': 'total', 'value': 10.0},
                                {'key': {'id': 'b', 'region': 'West'}, 'column': 'total', 'value': 12.5}]}
OPS = {'ops': [{'op': 'trimWhitespace'}, {'op': 'dropColumns', 'columns': ['notes']},
               {'op': 'addComputedColumn', 'name': 'total', 'left': 'price', 'operator': 'multiply', 'right': 'qty'},
               {'op': 'sortRows', 'column': 'total', 'direction': 'desc'}],
       'chart': {'type': 'bar', 'title': 'Totals', 'xKey': 'id', 'yKeys': ['total']},
       'findings': [{'label': 'Rows', 'value': 2}]}


def test_spreadsheet_pass(tmp_path):
    files = {'out/result.csv': 'id,region,price,qty,total\nb,West,2.5,5,12.5\na,East,5,2,10\n', 'out/changes.json': OPS}
    out = validate('spreadsheet', SHEET_CHECK, ws(tmp_path, files))
    assert out['passed'], out


SHEET_FAILURES = [
    ('id,region,price,qty,total\na,East,5,2,10\nb,West,2.5,5,12.5\n', OPS, 'first rows'),
    ('id,region,price,qty,total\nb,West,2.5,5,12.5\na,East,5,2,11\n', OPS, 'want 10'),
    ('id,region,notes,total\nb,West,,12.5\na,East,,10\n', OPS, 'still has column'),
    ('id,region,price,qty,total\nb,West,2.5,5,12.5\na,East,5,2,10\n', {'ops': [{'op': 'aiColumn', 'fn': 'write'}]}, 'unknown op'),
    ('id,region,price,qty,total\nb,West,2.5,5,12.5\na,East,5,2,10\n', {'ops': [{'op': 'sortRows', 'column': 'x', 'direction': 'up'}]}, 'not allowed'),
    ('id,region,price,qty,total\nb,West,2.5,5,12.5\na,East,5,2,10\n', {'ops': [{'op': 'sortRows', 'col': 'x'}]}, 'missing column'),
]


def test_spreadsheet_failures(tmp_path):
    for csv, ops, reason in SHEET_FAILURES:
        out = validate('spreadsheet', SHEET_CHECK, ws(tmp_path, {'out/result.csv': csv, 'out/changes.json': ops}))
        assert not out['passed'] and reason in out['detail'], out


def test_spreadsheet_numbers_and_names(tmp_path):
    files = {'out/result.csv': 'store,sales\nPune,1200.5\nDelhi,900\n', 'out/changes.json': {'ops': [{'op': 'trimWhitespace'}]}}
    assert validate('spreadsheet', {'expect_numbers': [900, 1200.5], 'expect_names': ['delhi', 'Pune']}, ws(tmp_path, files))['passed']
    assert not validate('spreadsheet', {'expect_names': ['Pune']}, ws(tmp_path, files))['passed']
    assert not validate('spreadsheet', {'expect_numbers': [905]}, ws(tmp_path, files))['passed']


# --- data analysis --------------------------------------------------------

def analysis(**over):
    doc = {'answers': {'q1': 1234.5678, 'q2': 'North'},
           'chart': {'chartType': 'bar', 'title': 'Revenue', 'xAxisKey': 'region', 'yAxisKeys': ['revenue'],
                     'data': [{'region': 'North', 'revenue': 1}, {'region': 'South', 'revenue': 2}]}}
    doc.update(over)
    return doc


DA_CHECK = {'answers': {'q1': {'value': 1234.57}, 'q2': {'value': 'north'}}, 'chart_types': ['bar', 'pie']}


def test_analysis_pass(tmp_path):
    assert validate('data-analysis', DA_CHECK, ws(tmp_path, {'out/analysis.json': analysis()}))['passed']


def test_analysis_failures(tmp_path):
    wrong = analysis(answers={'q1': 1300, 'q2': 'North'})
    assert 'want 1234.57' in validate('data-analysis', DA_CHECK, ws(tmp_path, {'out/analysis.json': wrong}))['detail']
    line = analysis()
    line['chart']['chartType'] = 'line'
    assert not validate('data-analysis', DA_CHECK, ws(tmp_path, {'out/analysis.json': line}))['passed']
    nochart = analysis()
    del nochart['chart']
    assert not validate('data-analysis', DA_CHECK, ws(tmp_path, {'out/analysis.json': nochart}))['passed']
    assert not validate('data-analysis', DA_CHECK, ws(tmp_path, {'out/analysis.json': 'not json'}))['passed']


def test_analysis_numbers_inside_strings(tmp_path):
    doc = analysis(answers={'North': 'about 1,200.40 total', 'South': 950})
    assert validate('data-analysis', {'expect_numbers': [1200.4, 950]}, ws(tmp_path, {'out/analysis.json': doc}))['passed']


# --- docx -----------------------------------------------------------------

def make_docx(path, paragraphs):
    import docx
    d = docx.Document()
    d.add_heading('Memo', 1)
    for p in paragraphs:
        d.add_paragraph(p)
    path.parent.mkdir(parents=True, exist_ok=True)
    d.save(str(path))


def test_docx(tmp_path):
    md = '# Memo\n\nWe switch to Gusto.\n\n## Risks\n\n- Migration'
    ws(tmp_path, {'out/document.json': {'title': 'Memo', 'markdown': md}})
    make_docx(tmp_path / 'out/document.docx', ['word ' * 120])
    check = {'min_words': 100, 'keywords': ['Gusto', ['risk', 'hazard']]}
    assert validate('docx', check, tmp_path)['passed']
    assert 'missing required' in validate('docx', {'keywords': ['PayFast']}, tmp_path)['detail']
    assert 'words' in validate('docx', {'min_words': 500}, tmp_path)['detail']
    (tmp_path / 'out/document.docx').write_text('not a zip')
    assert 'does not open' in validate('docx', check, tmp_path)['detail']


def test_docx_needs_heading(tmp_path):
    ws(tmp_path, {'out/document.json': {'title': 'Memo', 'markdown': 'no heading here'}})
    make_docx(tmp_path / 'out/document.docx', ['word ' * 120])
    assert 'heading' in validate('docx', {}, tmp_path)['detail']


# --- slides ---------------------------------------------------------------

DECK = [{'title': 'Crumb', 'bullets': []}, {'title': 'Market', 'body': 'Big.', 'bullets': ['2,300 users']}]


def test_slides(tmp_path):
    assert validate('slides', {'min_slides': 2, 'max_slides': 2, 'keywords': ['crumb', ['2300', '2,300']]},
                    ws(tmp_path, {'out/slides.json': DECK}))['passed']
    assert not validate('slides', {'min_slides': 3}, tmp_path)['passed']
    ws(tmp_path, {'out/slides.json': [{'title': 'x', 'bullets': 'not a list'}]})
    assert 'bullets' in validate('slides', {}, tmp_path)['detail']
    ws(tmp_path, {'out/slides.json': {'slides': DECK}})
    assert not validate('slides', {}, tmp_path)['passed']


# --- diagram --------------------------------------------------------------

def test_diagram_renders(tmp_path):
    src = '```mermaid\nflowchart LR\n  A[Lint] --> B[Deploy to staging]\n```'
    out = validate('diagram', {'diagram_types': ['flowchart', 'graph'], 'keywords': ['lint', 'staging']},
                   ws(tmp_path, {'out/diagram.json': {'format': 'mermaid', 'source': src}}))
    assert out['passed'], out


def test_diagram_failures(tmp_path):
    ws(tmp_path, {'out/diagram.json': {'format': 'mermaid', 'source': 'flowchart LR\n  A[Start --> B{{'}})
    assert 'does not render' in validate('diagram', {}, tmp_path)['detail']
    ws(tmp_path, {'out/diagram.json': {'format': 'mermaid', 'source': 'flowchart LR\n  A --> B'}})
    assert 'want one of' in validate('diagram', {'diagram_types': ['sequenceDiagram']}, tmp_path)['detail']
    ws(tmp_path, {'out/diagram.json': {'source': 'flowchart LR\n  A --> B'}})
    assert 'format' in validate('diagram', {}, tmp_path)['detail']


# --- map ------------------------------------------------------------------

def feature(geom_type, coords, name=None):
    return {'type': 'Feature', 'properties': {'name': name} if name else {}, 'geometry': {'type': geom_type, 'coordinates': coords}}


def fc(*features):
    return {'format': 'geojson', 'collection': {'type': 'FeatureCollection', 'features': list(features)}}


MAP_CHECK = {'min_features': 3, 'geometry_types': ['Point', ['LineString', 'MultiLineString']],
             'places': [{'name': 'Eiffel Tower', 'lon': 2.2945, 'lat': 48.8584, 'tol_km': 2}]}


def test_map_pass(tmp_path):
    doc = fc(feature('Point', [2.2945, 48.8584], 'Eiffel Tower'), feature('Point', [2.3376, 48.8606], 'Louvre'),
             feature('LineString', [[2.2945, 48.8584], [2.3376, 48.8606]]))
    assert validate('map', MAP_CHECK, ws(tmp_path, {'out/map.json': doc}))['passed']


def test_map_failures(tmp_path):
    swapped = fc(feature('Point', [48.8584, 2.2945], 'Eiffel Tower'), feature('Point', [2.3376, 48.8606]),
                 feature('LineString', [[2.29, 48.85], [2.33, 48.86]]))
    assert 'Eiffel' in validate('map', MAP_CHECK, ws(tmp_path, {'out/map.json': swapped}))['detail']
    open_ring = fc(feature('Polygon', [[[0, 0], [1, 0], [1, 1], [0, 1]]]))
    assert 'not closed' in validate('map', {}, ws(tmp_path, {'out/map.json': open_ring}))['detail']
    empty = fc({})
    assert not validate('map', {}, ws(tmp_path, {'out/map.json': empty}))['passed']
    bare = {'type': 'FeatureCollection', 'features': [feature('Point', [0, 0])]}
    assert 'format' in validate('map', {}, ws(tmp_path, {'out/map.json': bare}))['detail']


def test_map_expect_names(tmp_path):
    doc = fc(feature('Point', [73.89, 18.53], 'Pune Koregaon Park store'), feature('Point', [72.87, 19.11], 'Mumbai Andheri'))
    assert validate('map', {'expect_names': ['Pune Koregaon Park', 'Mumbai Andheri']}, ws(tmp_path, {'out/map.json': doc}))['passed']
    assert 'exactly' in validate('map', {'expect_names': ['Mumbai Andheri']}, tmp_path)['detail']


# --- scene ----------------------------------------------------------------

def jsonl(*patches):
    return '\n'.join(json.dumps(p) for p in patches) + '\n'


GOOD_SCENE = jsonl(
    {'op': 'add', 'path': '/root', 'value': 'scene'},
    {'op': 'add', 'path': '/elements/scene', 'value': {'type': 'Group', 'props': {}, 'children': ['light', 'spin', 'cam']}},
    {'op': 'add', 'path': '/elements/light', 'value': {'type': 'AmbientLight', 'props': {'intensity': 0.4}, 'children': []}},
    {'op': 'add', 'path': '/elements/spin', 'value': {'type': 'Spin', 'props': {'speed': 1}, 'children': ['ball']}},
    {'op': 'add', 'path': '/elements/ball', 'value': {'type': 'Sphere', 'props': {'radius': 1, 'material': {'color': '#f00'}}, 'children': []}},
    {'op': 'add', 'path': '/elements/cam', 'value': {'type': 'PerspectiveCamera', 'props': {'position': [5, 5, 5]}, 'children': []}},
)


def test_scene_pass(tmp_path):
    out = validate('scene-3d', {'min_elements': 5, 'require_types': ['Sphere', ['Spin', 'Float']]},
                   ws(tmp_path, {'out/scene.jsonl': GOOD_SCENE}))
    assert out['passed'], out


def test_scene_failures(tmp_path):
    assert 'no Stars' in validate('scene-3d', {'require_types': ['Stars']}, ws(tmp_path, {'out/scene.jsonl': GOOD_SCENE}))['detail']
    bad_prop = GOOD_SCENE.replace('"radius": 1', '"radius": "big"')
    assert 'radius' in validate('scene-3d', {}, ws(tmp_path, {'out/scene.jsonl': bad_prop}))['detail']
    unknown = GOOD_SCENE.replace('"Sphere"', '"Blob"')
    assert not validate('scene-3d', {}, ws(tmp_path, {'out/scene.jsonl': unknown}))['passed']
    dark = GOOD_SCENE.replace('"AmbientLight"', '"Box"')
    assert 'light' in validate('scene-3d', {}, ws(tmp_path, {'out/scene.jsonl': dark}))['detail']
    assert 'invalid patch' in validate('scene-3d', {}, ws(tmp_path, {'out/scene.jsonl': 'nope'}))['detail']


class ValidatorTest(unittest.TestCase):
    """Runs each test_* function above in a fresh temporary workspace."""


def _case(fn):
    def run(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:
            fn(tmp)
        finally:
            shutil.rmtree(tmp)
    return run


for _name in ['test_missing_artifact', 'test_code_func_pass_and_fail', 'test_code_stdio', 'test_code_numbers_reads_inputs', 'test_spreadsheet_pass', 'test_spreadsheet_failures', 'test_spreadsheet_numbers_and_names', 'test_analysis_pass', 'test_analysis_failures', 'test_analysis_numbers_inside_strings', 'test_docx', 'test_docx_needs_heading', 'test_slides', 'test_diagram_renders', 'test_diagram_failures', 'test_map_pass', 'test_map_failures', 'test_map_expect_names', 'test_scene_pass', 'test_scene_failures']:
    setattr(ValidatorTest, _name, _case(globals()[_name]))


if __name__ == '__main__':
    unittest.main()
