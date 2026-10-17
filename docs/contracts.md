# Data contracts

All inputs are UTF-8 JSON. Validation raises `ValueError`; the CLI prints a JSON error on stderr and exits 2. State and review schemas are independent: an external adapter must inspect a QA verdict before asserting its corresponding completion check.

## Task contract

```json
{
  "id": "example-run",
  "origin": "local:example",
  "steps": [
    {
      "id": "verify",
      "depends_on": [],
      "required_checks": ["matches_brief"],
      "min_artifacts": 1,
      "max_attempts": 3,
      "requires_approval": false
    }
  ]
}
```

Run IDs, origins, step IDs and check names must be nonempty strings. Step IDs and list entries must be unique. Dependencies must reference another declared step, and the graph must be acyclic. Steps need not be declared in execution order.

Only `id` and `origin` are required at run level, alongside a nonempty `steps` list. A step requires `id`; defaults are `depends_on: []`, `required_checks: []`, `min_artifacts: 1`, `max_attempts: 3`, `requires_approval: false`. Unknown contract fields are not persisted. An empty check list permits a file-only checkpoint; use explicit acceptance checks for substantive verification. `min_artifacts` must be a nonnegative integer, `max_attempts` a positive integer, and approval a JSON boolean. Boolean values cannot substitute for integers.

Completion takes a checks object containing only boolean values and a list of distinct regular-file paths. Every named required check must be `true`. Other checks are stored but do not gate this low-level checkpoint; use the stricter QA report policy for quality verdicts. A file must still match its SHA-256 digest at refresh time. The gate checks hashes, not whether a file satisfies the brief. Use immutable files and external access controls.

States are `pending`, `failed` and `done`. A successful first completion or explicit failed attempt increments attempts. An invalid completion is rolled back. Repeating an identical completion does not increment attempts. Missing/changed evidence resets affected steps and descendants to pending, clears their approval/checks/evidence and preserves attempts. No asynchronous worker is created.

## QA report

```json
{
  "builder": "producer",
  "reviewer": "reviewer",
  "requires_independent_review": true,
  "declared_pass": true,
  "required_checks": ["matches_brief"],
  "checks": {"matches_brief": true},
  "defects": []
}
```

Every field is required except `reviewer` (defaults to an empty string) and `requires_independent_review` (defaults to true). An empty reviewer fails independent review. Equal builder/reviewer names after trimming and case folding fail independent review. Setting independent review false explicitly permits self-review; it does not authenticate either party.

Defects have `severity` (`critical`, `major` or `minor`) and a nonempty `description`. Critical and major defects block acceptance regardless of declared pass. Minor defects may pass. There must be at least one required check, every required check must explicitly pass, and any supplied false check blocks the verdict. Duplicate required check names are malformed. Output is `{"passed": true, "reasons": []}` or a failed verdict with reasons.

## Curated lesson

Use [the synthetic example](../examples/lesson.json). Required fields are `id`, `category`, `failure`, `correction`, nonempty `acceptance_criteria`, `evidence_level`, `provenance`, `visibility` and `reviewed_for_public`.

Evidence levels: `observed`, `reported`, `synthetic`. Provenance: `direct_observation`, `retained_summary`, `synthetic_example`. Synthetic evidence and synthetic-example provenance must occur together. An observed result is a claim by the curator, not a verification performed by the exporter.

Visibility is `private` or `public`; public review is a strict boolean. `validate_lesson` validates and returns an allowlisted copy; it does not approve publication or screen private text. `export_lessons` checks every record is explicitly public and reviewed, then applies supplementary sensitive-pattern checks to the allowlisted fields. Extra fields are discarded. Failure rejects the whole batch. Never treat either function as an automatic anonymizer.

## Evaluation cases

A nonempty array of objects with unique `id`, a `review` matching the QA schema and strict boolean `expected_pass`. Each result reports whether actual and expected verdicts agree. Malformed cases abort with an input error instead of being counted as a passing negative test. This runner exercises policy; supply an external model's reports through your own adapter if you want to evaluate its output against the same rules.
