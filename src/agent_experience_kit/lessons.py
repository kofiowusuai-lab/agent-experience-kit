"""Curated lesson export with an allowlist and supplementary privacy checks.

Pattern matching is not an exhaustive anonymizer. Human public review remains
required; this module never imports operational logs or historical databases.
"""
import re

_FIELDS = ('id', 'category', 'failure', 'correction', 'acceptance_criteria',
           'evidence_level', 'provenance', 'visibility', 'reviewed_for_public')
_PATTERNS = (
    re.compile(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}'),
    re.compile(r'/(?:Users|home)/', re.I),
    re.compile(r'(?<!\w)(?:\+?\d[\d () .-]{7,}\d)(?!\w)'),
    re.compile(r'\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16}|xox[baprs]-[A-Za-z0-9-]{10,})\b'),
    re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
)


def validate_lesson(lesson: dict) -> dict:
    """Return a schema-only copy; extra fields are intentionally excluded."""
    if not isinstance(lesson, dict):
        raise ValueError('lesson must be an object')
    for field in ('id', 'category', 'failure', 'correction'):
        if not isinstance(lesson.get(field), str) or not lesson[field].strip():
            raise ValueError(f'{field} must be a nonempty string')
    criteria = lesson.get('acceptance_criteria')
    if not isinstance(criteria, list) or not criteria or any(not isinstance(v, str) or not v.strip() for v in criteria):
        raise ValueError('acceptance_criteria must contain nonempty strings')
    enums = {'evidence_level': ('observed', 'reported', 'synthetic'),
             'provenance': ('direct_observation', 'retained_summary', 'synthetic_example'),
             'visibility': ('private', 'public')}
    for field, choices in enums.items():
        if lesson.get(field) not in choices:
            raise ValueError(f'invalid {field}')
    if (lesson['evidence_level'] == 'synthetic') != (lesson['provenance'] == 'synthetic_example'):
        raise ValueError('synthetic evidence and synthetic provenance must agree')
    if type(lesson.get('reviewed_for_public')) is not bool:
        raise ValueError('reviewed_for_public must be an explicit boolean')
    return {field: list(lesson[field]) if field == 'acceptance_criteria' else lesson[field] for field in _FIELDS}


def export_lessons(lessons: list[dict]) -> list[dict]:
    """Export all records or raise; never silently skip private records."""
    if not isinstance(lessons, list):
        raise ValueError('lessons must be a list')
    records = []
    for lesson in lessons:
        record = validate_lesson(lesson)
        if record['visibility'] != 'public' or record['reviewed_for_public'] is not True:
            raise ValueError('every exported lesson must be public and reviewed')
        for value in record.values():
            strings = value if isinstance(value, list) else [value]
            for item in strings:
                if isinstance(item, str) and any(pattern.search(item) for pattern in _PATTERNS):
                    raise ValueError('public lesson contains a possible contact, private path or secret')
        records.append(record)
    return records
