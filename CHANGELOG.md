# Changelog

## 0.1.1

- Close the corruption-test SQLite connection explicitly, allowing temporary database cleanup on Windows. Runtime behavior is unchanged.

## 0.1.0

Initial alpha release:

- Model-independent Python library and JSON CLI.
- Transactional SQLite task checkpoints, dependency gates, origin matching, approval assertions and bounded attempt records.
- Streaming file hashes with evidence refresh and descendant invalidation.
- QA policy that rejects blocking defects, missing acceptance checks and required self-review.
- Structured curated lessons with reviewed public export and supplementary sensitive-pattern screening.
- Twelve synthetic policy cases, nine specialist playbooks and a portable agent skill.
- Offline demonstration, clean-install checks and multi-version CI.

External runtimes supply agents, provider execution and authenticated approvals. This release does not import private histories or establish model/business performance.
