import unittest
from agent_experience_kit.qa import evaluate_review


def report(**updates):
    value = dict(builder='builder', reviewer='reviewer', declared_pass=True,
                 required_checks=['render'], checks={'render': True}, defects=[])
    value.update(updates)
    return value


class ReviewTests(unittest.TestCase):
    def test_clean_pass(self):
        self.assertTrue(evaluate_review(report())['passed'])

    def test_blocking_defects_downgrade_declared_pass(self):
        for severity in ('critical', 'major'):
            with self.subTest(severity=severity):
                self.assertFalse(evaluate_review(report(defects=[dict(severity=severity, description='Broken output')]))['passed'])

    def test_minor_warning_can_pass(self):
        self.assertTrue(evaluate_review(report(defects=[dict(severity='minor', description='Spacing')]))['passed'])

    def test_required_checks_fail_closed(self):
        for checks in ({}, {'render': False}):
            self.assertFalse(evaluate_review(report(checks=checks))['passed'])

    def test_missing_and_self_reviewer_block(self):
        for reviewer in ('', None, 'builder'):
            value = report(reviewer=reviewer)
            if reviewer is None:
                del value['reviewer']
            self.assertFalse(evaluate_review(value)['passed'])

    def test_explicit_self_review_permission(self):
        self.assertTrue(evaluate_review(report(reviewer='builder', requires_independent_review=False))['passed'])

    def test_declared_fail_blocks(self):
        self.assertFalse(evaluate_review(report(declared_pass=False))['passed'])

    def test_malformed_values_rejected(self):
        for changes in ({'declared_pass': 1}, {'checks': {'render': 1}}, {'required_checks': 'render'}, {'requires_independent_review': 1}, {'defects': [{'severity': 'unknown', 'description': 'Issue'}]}, {'builder': ''}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                evaluate_review(report(**changes))

class StrictPolicyTests(unittest.TestCase):
    def test_empty_required_checks_block(self):
        self.assertFalse(evaluate_review(report(required_checks=[], checks={}))['passed'])

    def test_extra_false_check_blocks(self):
        self.assertFalse(evaluate_review(report(checks={'render': True, 'captions': False}))['passed'])

    def test_duplicate_required_names_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_review(report(required_checks=['render', 'render']))
