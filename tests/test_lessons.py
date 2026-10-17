import unittest
from agent_experience_kit.lessons import validate_lesson, export_lessons


def lesson(**updates):
    value = dict(id='synthetic-review', category='quality', failure='A declared pass hid a defect.', correction='Apply explicit blocking checks.', acceptance_criteria=['No blocking defects remain.'], evidence_level='synthetic', provenance='synthetic_example', visibility='public', reviewed_for_public=True)
    value.update(updates)
    return value


class LessonTests(unittest.TestCase):
    def test_valid_lesson(self):
        self.assertEqual(validate_lesson(lesson())['id'], 'synthetic-review')

    def test_allowlist_drops_extra_fields(self):
        exported = export_lessons([lesson(source_log='confidential', internal_id='hidden')])
        self.assertNotIn('source_log', exported[0])
        self.assertNotIn('internal_id', exported[0])

    def test_export_requires_public_review_all_or_none(self):
        for updates in ({'visibility': 'private'}, {'reviewed_for_public': False}):
            with self.assertRaises(ValueError):
                export_lessons([lesson(), lesson(**updates)])

    def test_malformed_lesson(self):
        for updates in ({'evidence_level': 'verified'}, {'provenance': 'raw_log'}, {'reviewed_for_public': 1}, {'acceptance_criteria': []}, {'id': ''}):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                validate_lesson(lesson(**updates))

    def test_public_fields_scanned(self):
        for field in ('id', 'category', 'failure', 'correction', 'acceptance_criteria'):
            for sensitive in ('person@example.com', '/Users/person/private', '/home/person/private', '+1 (202) 555-0123', 'sk-abcdefghijklmnopqrstuvwxyz123456', 'ghp_abcdefghijklmnopqrstuvwxyz1234567890'):
                value = [sensitive] if field == 'acceptance_criteria' else sensitive
                with self.subTest(field=field, sensitive=sensitive), self.assertRaises(ValueError):
                    export_lessons([lesson(**{field: value})])

class ProvenanceTests(unittest.TestCase):
    def test_synthetic_evidence_and_provenance_must_agree(self):
        for changes in ({'evidence_level': 'observed'}, {'evidence_level': 'reported'}, {'provenance': 'direct_observation'}, {'provenance': 'retained_summary'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_lesson(lesson(**changes))
