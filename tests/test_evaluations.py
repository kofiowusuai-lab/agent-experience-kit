import json
from pathlib import Path
import unittest
from agent_experience_kit.evaluations import evaluate_cases


class EvaluationTests(unittest.TestCase):
    def test_synthetic_fixtures(self):
        cases = json.loads(Path('examples/qa-cases.json').read_text())
        result = evaluate_cases(cases)
        self.assertGreaterEqual(result['total'], 8)
        self.assertTrue(result['passed'], result)

    def test_mismatch_fails(self):
        review = dict(builder='builder', reviewer='reviewer', declared_pass=False, required_checks=[], checks={}, defects=[])
        result = evaluate_cases([dict(id='mismatch', review=review, expected_pass=True)])
        self.assertFalse(result['passed'])
        self.assertFalse(result['results'][0]['actual'])

    def test_strict_expected_boolean(self):
        with self.assertRaises(ValueError):
            evaluate_cases([dict(id='bad', review={}, expected_pass=1)])
