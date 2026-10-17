"""Deterministic QA policy; supplied checks are assertions, not independent proof."""


def evaluate_review(report: dict) -> dict:
    """Validate a report and fail closed on blocking defects or absent evidence."""
    if not isinstance(report, dict):
        raise ValueError('review must be an object')
    builder = report.get('builder')
    reviewer = report.get('reviewer', '')
    if not isinstance(builder, str) or not builder.strip():
        raise ValueError('builder must be a nonempty string')
    if not isinstance(reviewer, str):
        raise ValueError('reviewer must be a string')
    independent = report.get('requires_independent_review', True)
    declared = report.get('declared_pass')
    if type(independent) is not bool or type(declared) is not bool:
        raise ValueError('review flags must be booleans')
    required = report.get('required_checks')
    checks = report.get('checks')
    defects = report.get('defects')
    if not isinstance(required, list) or any(not isinstance(v, str) or not v.strip() for v in required):
        raise ValueError('required_checks must be a list of nonempty strings')
    if len(set(required)) != len(required):
        raise ValueError('required_checks contains duplicate names')
    if not isinstance(checks, dict) or any(not isinstance(k, str) or not k.strip() or type(v) is not bool for k, v in checks.items()):
        raise ValueError('checks must map names to booleans')
    if not isinstance(defects, list):
        raise ValueError('defects must be a list')
    for defect in defects:
        if not isinstance(defect, dict) or defect.get('severity') not in ('critical', 'major', 'minor') or not isinstance(defect.get('description'), str) or not defect['description'].strip():
            raise ValueError('each defect needs severity and nonempty description')
    reasons = []
    if not required:
        reasons.append('At least one required check is needed.')
    for name, passed in checks.items():
        if passed is False and name not in required:
            reasons.append(f'Supplied check did not pass: {name}')
    if not declared:
        reasons.append('Reviewer declared failure.')
    if independent and not reviewer.strip():
        reasons.append('Independent reviewer is required.')
    elif independent and builder.strip().casefold() == reviewer.strip().casefold():
        reasons.append('Builder cannot independently review their own work.')
    for name in required:
        if checks.get(name) is not True:
            reasons.append(f'Required check did not pass: {name}')
    for defect in defects:
        if defect['severity'] in ('critical', 'major'):
            reasons.append(f"{defect['severity']} defect: {defect['description']}")
    return {'passed': not reasons, 'reasons': reasons}
