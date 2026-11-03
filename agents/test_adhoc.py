import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import adhoc  # noqa: E402


class SummarizeEvent(unittest.TestCase):
    def test_tool_event_shows_the_command(self):
        ev = {'type': 'tool_use', 'part': {'tool': 'shell', 'state': {'status': 'completed', 'input': {'command': 'ls -la\npwd'}}}}
        self.assertEqual(adhoc.summarize_event(ev), {'kind': 'tool', 'tool': 'shell', 'text': 'ls -la'})

    def test_skill_event_reads_as_a_loaded_skill(self):
        ev = {'type': 'tool_use', 'part': {'tool': 'skill', 'state': {'status': 'completed', 'input': {'id': 'docx-writing'}}}}
        self.assertEqual(adhoc.summarize_event(ev), {'kind': 'tool', 'tool': 'skill', 'text': 'loaded docx-writing'})

    def test_token_and_text_events(self):
        self.assertEqual(adhoc.summarize_event({'type': 'step_finish', 'part': {'tokens': {'input': 5, 'output': 7}}}),
                         {'kind': 'tokens', 'input': 5, 'output': 7})
        self.assertEqual(adhoc.summarize_event({'type': 'text', 'part': {'text': 'done'}})['text'], 'done')

    def test_unknown_event_is_dropped(self):
        self.assertEqual(adhoc.summarize_event({'type': 'reasoning', 'part': {'text': ' plan it '}}),
                         {'kind': 'thinking', 'text': 'plan it'})
        self.assertIsNone(adhoc.summarize_event({'type': 'reasoning', 'part': {'text': ''}}))
        self.assertIsNone(adhoc.summarize_event({'type': 'session_idle'}))


class ContractCheck(unittest.TestCase):
    def workspace(self, files):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ws = pathlib.Path(tmp.name)
        for name, body in files.items():
            (ws / name).parent.mkdir(parents=True, exist_ok=True)
            (ws / name).write_text(body)
        return ws

    def test_code_needs_a_parsing_file(self):
        self.assertTrue(adhoc.contract_check('code', self.workspace({'out/solution.py': 'print(1)\n'}))['passed'])
        bad = adhoc.contract_check('code', self.workspace({'out/solution.py': 'def (:\n'}))
        self.assertFalse(bad['passed'])
        self.assertIn('syntax error', bad['detail'])
        self.assertFalse(adhoc.contract_check('code', self.workspace({}))['passed'])

    def test_slides_open_the_real_deck(self):
        import zipfile
        ws = self.workspace({})
        (ws / 'out').mkdir(exist_ok=True)
        with zipfile.ZipFile(ws / 'out/deck.pptx', 'w') as z:
            z.writestr('ppt/slides/slide1.xml', '<p:sld><a:t>Churn fell after the onboarding redesign shipped in March and annual plans renewed more often than monthly ones</a:t></p:sld>')
        self.assertTrue(adhoc.contract_check('slides', ws)['passed'])
        self.assertFalse(adhoc.contract_check('slides', self.workspace({'out/slides.json': '[]'}))['passed'])

    def test_free_text_wording_claims_only_what_was_checked(self):
        sheet = adhoc.free_text_detail('spreadsheet', '3 ops, 4 rows, expected cells match')
        self.assertIn('format valid: spreadsheet has the required files', sheet)
        self.assertNotIn('expected cells match', sheet)
        analysis = adhoc.free_text_detail('data-analysis', '3 answers correct, bar chart with 3 points')
        self.assertIn('format valid', analysis)
        self.assertNotIn('correct', analysis)
        self.assertEqual(adhoc.free_text_detail('slides', '3 slides match the deck schema'), '3 slides match the deck schema')

    def test_suite_validators_keep_their_wording(self):
        import validators
        self.assertIn('expected cells match', open(pathlib.Path(validators.__file__)).read())

    def test_read_artifact_returns_text_files(self):
        ws = self.workspace({'out/slides.json': '[]'})
        art = adhoc.read_artifact('slides', ws)
        self.assertEqual(art['files'], {'slides.json': '[]'})
        self.assertEqual(art['binary'], {})


if __name__ == '__main__':
    unittest.main()
