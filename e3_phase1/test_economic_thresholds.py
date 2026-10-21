import json
import unittest
from pathlib import Path
from e3_economic_thresholds import analyze, review_analysis


class TestEconomics(unittest.TestCase):
    def test_weak_correctness_threshold(self):
        x = review_analysis(708, 102, 810, .75, .75, .05)
        self.assertAlmostEqual(x['accuracy_gain'], (102*.75*.75-708*.05)/810)
        self.assertAlmostEqual(x['break_even_review_cost_over_error_loss'], x['accuracy_gain'])

    def test_cheap_flagged_threshold(self):
        x = review_analysis(6, 77, 810, .75, .75, .05)
        self.assertEqual(x['review_count'], 83)
        self.assertAlmostEqual(x['break_even_review_cost_over_error_loss'], (77*.75*.75-6*.05)/83)

    def test_strong_validator_false_change_zero(self):
        self.assertAlmostEqual(review_analysis(0,102,810,.75,.75,.15)['break_even_review_cost_over_error_loss'], .5625)

    def test_strong_ai_review_not_positive(self):
        self.assertEqual(review_analysis(810,0,810,.75,.75,.05)['break_even_review_cost_over_error_loss'], -.05)

    def test_zero_cost_no_gain(self):
        x = review_analysis(0,0,810,1,1,0)
        self.assertIsNone(x['break_even_review_cost_over_error_loss'])

    def test_invalid_counts(self):
        with self.assertRaises(ValueError):
            review_analysis(810,1,810,.5,.5,.05)

    def test_real_saved_stage1_fixture(self):
        fixture = Path(__file__).parent / 'stage1_fixture.json'
        if not fixture.exists():
            self.skipTest('Optional Stage1 fixture not packaged')
        result = analyze(json.loads(fixture.read_text(encoding='utf-8')))
        self.assertEqual(len(result['validator_routes']['cheap_validator']['profiles']), 36)
        self.assertEqual(len(result['validator_routes']['strong_validator']['profiles']), 36)


if __name__ == '__main__':
    unittest.main()
