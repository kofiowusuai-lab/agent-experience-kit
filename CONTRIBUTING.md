# Contributing

Contributions should make task contracts, evidence gates, and reusable operational lessons clearer and more reliable. The project is MIT-licensed and maintained by Kedolabs.

Keep changes focused. Explain the behavior being changed, a concrete failure it prevents, and how you verified it. Read `docs/design.md` before changing contract, QA, or export semantics. Document compatibility changes and limitations alongside implementation.

## Evidence and examples

Use synthetic fixtures and invented scenarios. Do not submit raw agent histories, customer data, credentials, private paths, contact lists, or private identifiers. Real public data requires appropriate consent and redistribution rights; public availability alone is insufficient. Manually review lesson records and exported files using `docs/privacy.md`.

Playbooks should include a purpose, input contract, steps, acceptance evidence, fail/repair rules, synthetic example, and limitations. Distinguish operator assertions from automatic verification. Avoid claims that local policy evaluations measure model intelligence or business performance.

## Validation

The runtime and tests use the Python standard library. From the repository root, run:

```sh
python -m unittest discover -s tests -v
```

Add regression coverage for meaningful behavior changes, especially rejection paths. Tests must run offline without provider credentials or paid requests. Do not weaken a critical-defect gate, origin check, or privacy guard merely to make a fixture pass. If packaging changes, also follow the build and clean-install checks documented in the repository.

Before opening a pull request, inspect the diff for private data, run relevant checks, and describe their actual results. Include concise reproduction steps for bugs and note any checks you could not run. Do not put security vulnerabilities or sensitive reproduction material in a public pull request; see `SECURITY.md`.
