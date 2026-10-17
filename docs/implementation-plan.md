# Implementation plan

Goal: ship the public v0.1 described in design.md with executable examples and verifiable local behavior.

1. Core lane: write failing unittest cases for contract validation, SQLite restart/resume, dependency gates, origin isolation, attempt limits and artifact mutation. Implement `store.py`, run the tests and report evidence. Own only store.py and test_store.py.
2. Quality lane: write failing tests for strict QA and public lesson export; implement `qa.py`, `lessons.py`, synthetic `evaluations.py` and their tests. Own only these modules/tests and examples/qa-cases.json, examples/lesson.json.
3. Documentation lane: create nine specialist playbooks, integration guidance, contribution policy and privacy guidance from generalized lessons. No raw audit evidence or transcript identifiers. Own playbooks and docs excluding design/implementation plan.
4. Integration lane: implement CLI after writing subprocess acceptance tests; add packaging, sample contract/review, README, MIT licence and CI. Verify every documented command in a temporary directory; build wheel and sdist, install wheel in a fresh virtual environment and run evaluations. Review other lanes for spec compliance, then request independent code review.
5. Release: resolve review findings; review all tracked files and built artifacts for private information; commit as authenticated human identity; create public GitHub repository and push. Verify remote visibility, commit and CI. Publishing is explicitly requested by the user.

Use separate files for independent lanes and one integration lane for Git operations. No subagent commits or external writes. Tests precede implementation. This new standalone repository provides isolation from existing user projects. No dependency on the private audit directory is permitted.
