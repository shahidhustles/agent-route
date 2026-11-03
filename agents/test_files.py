"""Tests for the file contract: validators that open real .pptx/.docx/.xlsx/.html, the live docker command, preview paths."""
import json
import pathlib
import sys
import tempfile
import unittest
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run  # noqa: E402  (before validators, which put benchmarking/pool and its own run.py on sys.path)
import preview  # noqa: E402
from validators import files  # noqa: E402


def slide(text, pic=False):
    return (f'<p:sld><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>{text}</a:t></a:r></a:p></p:txBody></p:sp>'
            + ('<p:pic/>' if pic else '') + '</p:spTree></p:cSld></p:sld>')


def make_zip(path, parts):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, 'w') as z:
        for name, body in parts.items():
            z.writestr(name, body)


class Workspace(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.ws = pathlib.Path(tmp.name)

    def check(self, agent, check=None):
        return files.validate_files(agent, check or {}, self.ws)


class Slides(Workspace):
    def test_deck_counts_slides_words_and_visuals(self):
        make_zip(self.ws / 'out/deck.pptx', {
            'ppt/slides/slide1.xml': slide('Quarterly results and why churn fell for annual plans after the onboarding redesign'),
            'ppt/slides/slide2.xml': slide('Next steps for the onboarding team this quarter', pic=True)})
        out = self.check('slides', {'slides': 2})
        self.assertTrue(out['passed'], out)
        self.assertIn('2 slides', out['detail'])
        self.assertIn('1 with a picture', out['detail'])

    def test_wrong_count_placeholder_and_broken_files_fail(self):
        make_zip(self.ws / 'out/deck.pptx', {'ppt/slides/slide1.xml': slide('Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut labore et dolore')})
        self.assertIn('placeholder', self.check('slides')['detail'])
        self.assertIn('asked for 3', self.check('slides', {'slides': 3})['detail'])
        (self.ws / 'out/deck.pptx').write_bytes(b'not a zip')
        self.assertIn('not a valid PowerPoint', self.check('slides')['detail'])

    def test_missing_deck_fails(self):
        self.assertIn('missing artifact', self.check('slides')['detail'])

    def test_keywords_must_appear(self):
        make_zip(self.ws / 'out/deck.pptx', {'ppt/slides/slide1.xml': slide('Churn fell after the onboarding redesign shipped in March and annual plans renewed at a higher rate')})
        self.assertTrue(self.check('slides', {'keywords': ['churn']})['passed'])
        self.assertIn('missing required content', self.check('slides', {'keywords': ['revenue']})['detail'])


class Docx(Workspace):
    def test_headings_words_and_tables_are_counted(self):
        body = ('<w:document><w:body><w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Proposal</w:t></w:r></w:p>'
                + ''.join(f'<w:p><w:r><w:t>word{i} filler words here</w:t></w:r></w:p>' for i in range(20)) + '<w:tbl></w:tbl></w:body></w:document>')
        make_zip(self.ws / 'out/document.docx', {'word/document.xml': body})
        out = self.check('docx')
        self.assertTrue(out['passed'], out)
        self.assertIn('1 headings, 1 tables', out['detail'])

    def test_short_document_fails(self):
        make_zip(self.ws / 'out/document.docx', {'word/document.xml': '<w:document><w:p><w:r><w:t>hi</w:t></w:r></w:p></w:document>'})
        self.assertIn('only 1 words', self.check('docx')['detail'])

    def test_table_wider_than_the_text_area_fails(self):
        para = '<w:p><w:r><w:t>' + 'word ' * 60 + '</w:t></w:r></w:p>'
        page = '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>'
        make_zip(self.ws / 'out/document.docx', {'word/document.xml': f'<w:document>{para}<w:tbl><w:tblPr><w:tblW w:type="dxa" w:w="12060"/></w:tblPr></w:tbl>{page}</w:document>'})
        self.assertIn('runs off the page', self.check('docx')['detail'])
        make_zip(self.ws / 'out/document.docx', {'word/document.xml': f'<w:document>{para}<w:tbl><w:tblPr><w:tblW w:type="dxa" w:w="9026"/></w:tblPr></w:tbl>{page}</w:document>'})
        self.assertTrue(self.check('docx')['passed'])


class Workbook(Workspace):
    def book(self, name, sheet, charts=0, sheets=('Data',)):
        parts = {'xl/workbook.xml': '<workbook><sheets>' + ''.join(f'<sheet name="{s}" sheetId="1"/>' for s in sheets) + '</sheets></workbook>',
                 'xl/worksheets/sheet1.xml': sheet}
        for i in range(charts):
            parts[f'xl/charts/chart{i + 1}.xml'] = '<c:chartSpace/>'
        make_zip(self.ws / 'out' / name, parts)

    ROWS = '<sheetData><row><c r="A1" t="inlineStr"><is><t>x</t></is></c><c r="B1"><v>1</v></c><c r="C1"><v>2</v></c><c r="D1"><f>B1+C1</f><v>3</v></c></row></sheetData>'

    def test_formulas_with_values_pass(self):
        self.book('workbook.xlsx', self.ROWS)
        out = self.check('spreadsheet')
        self.assertTrue(out['passed'], out)
        self.assertIn('1 formulas', out['detail'])

    def test_uncalculated_formulas_and_errors_fail(self):
        self.book('workbook.xlsx', self.ROWS.replace('<v>3</v>', ''))
        self.assertIn('recalc.py', self.check('spreadsheet')['detail'])
        self.book('workbook.xlsx', self.ROWS.replace('<v>3</v>', '<v>#DIV/0!</v>'))
        self.assertIn('formula errors', self.check('spreadsheet')['detail'])

    def test_analysis_needs_a_chart(self):
        self.book('analysis.xlsx', self.ROWS)
        self.assertIn('no chart', self.check('data-analysis')['detail'])
        self.book('analysis.xlsx', self.ROWS, charts=1)
        self.assertTrue(self.check('data-analysis')['passed'])


class Html(Workspace):
    def write(self, name, text):
        (self.ws / 'out').mkdir(exist_ok=True)
        (self.ws / 'out' / name).write_text(text)

    SVG = '<html><body>' + '<svg><rect/><rect/><circle/><text>A</text><text>B</text></svg>' + ' pad' * 100 + '</body></html>'

    def test_diagram_needs_shapes_labels_and_no_network(self):
        self.write('diagram.html', self.SVG)
        self.assertTrue(self.check('diagram')['passed'])
        self.write('diagram.html', self.SVG.replace('<svg>', '<link href="https://fonts.example/x.css"><svg>'))
        self.assertIn('network', self.check('diagram')['detail'])

    def test_map_needs_geojson_and_svg(self):
        self.write('map.html', self.SVG)
        self.assertIn('map.geojson', self.check('map')['detail'])
        self.write('map.geojson', json.dumps({'type': 'FeatureCollection', 'features': [
            {'type': 'Feature', 'properties': {}, 'geometry': {'type': 'Point', 'coordinates': [2.35, 48.85]}}]}))
        self.assertTrue(self.check('map')['passed'])

    def test_scene_needs_inlined_three(self):
        self.write('scene.html', '<script>THREE WebGLRenderer OrbitControls</script>' + ' pad' * 40_000)
        self.assertTrue(self.check('scene-3d')['passed'])
        self.write('scene.html', '<script src="three.js"></script>THREE')
        self.assertFalse(self.check('scene-3d')['passed'])


class Docker(unittest.TestCase):
    def mounts(self, contract):
        argv = run.docker_argv('n', pathlib.Path('/w'), 'slides', 'cc/x', 'p', contract=contract)
        return [a for a in argv if a.endswith(':ro')], argv

    def test_files_contract_mounts_anthropic_skills_and_new_prompts_read_only(self):
        mounts, argv = self.mounts('files')
        self.assertTrue(any(m.endswith('opencode/skills-files:/home/runner/.config/opencode/skills:ro') for m in mounts))
        self.assertTrue(any(m.endswith('opencode/agent:/home/runner/.config/opencode/agent:ro') for m in mounts))
        self.assertEqual(argv[argv.index('--memory') + 1], '3g')

    def test_json_contract_is_the_recorded_suite_setup(self):
        mounts, argv = self.mounts('json')
        self.assertTrue(any(m.endswith('opencode/skills:/home/runner/.config/opencode/skills:ro') for m in mounts))
        self.assertTrue(any(m.endswith('opencode/agent-json:/home/runner/.config/opencode/agent:ro') for m in mounts))
        self.assertEqual(argv[argv.index('--memory') + 1], '2g')


class Preview(unittest.TestCase):
    def test_container_has_no_network_and_a_read_only_input(self):
        argv = preview.preview_argv('n', pathlib.Path('/src'), 'deck.pptx', pathlib.Path('/out'))
        self.assertEqual(argv[argv.index('--network') + 1], 'none')
        self.assertIn('--read-only', argv)
        self.assertIn('/src:/in:ro', argv)
        self.assertEqual(argv[-3:], ['ar-preview', '/in/deck.pptx', '/out'])

    def test_non_office_file_is_refused(self):
        with self.assertRaises(preview.PreviewError):
            preview.build_preview('/etc/passwd', '/tmp/x')


class FileAgents(unittest.TestCase):
    """Each file-contract prompt allows only its skills and carries the truthfulness rule."""
    SKILLS = {'slides': {'pptx'}, 'docx': {'docx'}, 'spreadsheet': {'xlsx'}, 'data-analysis': {'xlsx'},
              'diagram': {'frontend-design'}, 'map': {'frontend-design'}, 'scene-3d': {'frontend-design'}, 'code': {'code-solutions'}}

    def test_prompts(self):
        import re
        for agent, skills in self.SKILLS.items():
            text = (HERE / 'opencode/agent' / f'{agent}.md').read_text()
            block = re.search(r'^  skill:\n((?:    .+\n)+)', text, re.M)[1]
            rules = dict(re.findall(r'^    "?([^":\s]+)"?: (\w+)$', block, re.M))
            self.assertEqual(rules, {'*': 'deny', **{s: 'allow' for s in skills}}, agent)
            first = text.split('---\n', 2)[2].lstrip().splitlines()[0]
            for s in skills:
                self.assertIn(f'load the `{s}` skill', first, agent)
            if agent != 'code':
                self.assertIn('Use only facts from the request and the attached files', text, agent)
                self.assertLess(text.index('## Truthfulness'), text.index('## Method'), agent)


if __name__ == '__main__':
    unittest.main()
