import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / 'pool'))
from score import last_boxed, normalize_math, score_bfcl, score_math, score_mcq, score_squad  # noqa: E402


def text(content):
    return {'content': content}


class MathTest(unittest.TestCase):
    def test_boxed_with_nested_braces(self):
        self.assertEqual(last_boxed(r'so \boxed{\frac{1}{2}} done'), r'\frac{1}{2}')

    def test_equivalent_forms(self):
        for a, b in [(r'\dfrac{1}{2}', r'\frac12'), (r'\$1,000', '1000'), (r'90^\circ', '90'), ('5.0', '5')]:
            self.assertEqual(normalize_math(a), normalize_math(b))

    def test_mismatch_flags_review(self):
        out = score_math({'answer': '3'}, text(r'\boxed{4}'))
        self.assertFalse(out['passed'])
        self.assertTrue(out['review'])

    def test_missing_box_fails_without_review(self):
        self.assertNotIn('review', score_math({'answer': '3'}, text('3')))


class McqTest(unittest.TestCase):
    def test_last_answer_line_wins(self):
        self.assertTrue(score_mcq({'answer': 'C'}, text('Answer: B... wait.\nAnswer: **C**'))['passed'])

    def test_no_letter(self):
        self.assertFalse(score_mcq({'answer': 'C'}, text('I think C'))['passed'])


class SquadTest(unittest.TestCase):
    def test_span_inside_sentence(self):
        self.assertTrue(score_squad({'answers': ['Denver Broncos']}, text('The Denver Broncos.'))['passed'])

    def test_unanswerable(self):
        self.assertTrue(score_squad({'answers': []}, text('Unanswerable'))['passed'])
        self.assertFalse(score_squad({'answers': ['x']}, text('unanswerable'))['passed'])


class BfclTest(unittest.TestCase):
    truth = [{'area': {'base': [10], 'height': [5], 'unit': ['units', '']}}]

    def call(self, args, name='area'):
        return {'tool_calls': [{'function': {'name': name, 'arguments': json.dumps(args)}}]}

    def test_optional_arg_may_be_omitted(self):
        self.assertTrue(score_bfcl({'ground_truth': self.truth}, self.call({'base': 10, 'height': 5.0}))['passed'])

    def test_wrong_value_and_extra_arg(self):
        self.assertFalse(score_bfcl({'ground_truth': self.truth}, self.call({'base': 11, 'height': 5}))['passed'])
        self.assertFalse(score_bfcl({'ground_truth': self.truth}, self.call({'base': 10, 'height': 5, 'x': 1}))['passed'])

    def test_no_call(self):
        self.assertFalse(score_bfcl({'ground_truth': self.truth}, {'tool_calls': []})['passed'])


if __name__ == '__main__':
    unittest.main()
