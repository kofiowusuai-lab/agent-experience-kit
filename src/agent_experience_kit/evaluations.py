"""Synthetic policy regression evaluations; no model calls or quality claims."""
from .qa import evaluate_review


def evaluate_cases(cases: list[dict]) -> dict:
    if not isinstance(cases, list) or not cases:
        raise ValueError('cases must be a nonempty list')
    results = []
    seen = set()
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get('id'), str) or not case['id'].strip():
            raise ValueError('each case needs a nonempty id')
        if case['id'] in seen:
            raise ValueError('case ids must be unique')
        seen.add(case['id'])
        if type(case.get('expected_pass')) is not bool:
            raise ValueError('expected_pass must be a boolean')
        verdict = evaluate_review(case.get('review'))
        results.append({'id': case['id'], 'passed': verdict['passed'] == case['expected_pass'],
                        'expected': case['expected_pass'], 'actual': verdict['passed'],
                        'reasons': verdict['reasons']})
    return {'passed': all(result['passed'] for result in results), 'total': len(results), 'results': results}
