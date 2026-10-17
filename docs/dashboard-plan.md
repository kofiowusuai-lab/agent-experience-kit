# Dashboard implementation plan

1. Backend lane owns `src/aek_hub/database.py`, `app.py`, `models.py` (and internal modules), `tests/hub/*`. Implement PostgreSQL-compatible schema, scoped keys/sessions, bounded immutable ingest, monotonic projection, query/review endpoints and negative tests. Verify SQLite unit tests first, then real PostgreSQL integration with root.
2. Sync lane owns `src/agent_experience_kit/store.py`, new `sync.py`, `tests/test_sync.py`, `tests/test_outbox.py`. Implement transactional local outbox, safe snapshots, explicit sync API, recorded QA summaries and backward compatibility. No CLI edits; root integrates commands against agreed APIs.
3. Dashboard lane owns `dashboard/*` except integration-owned browser tests. Build functional React/TypeScript UI against dashboard-api.md, scoped login, overview/run/audit/review/failure views, responsive and accessible states. Install current registry dependencies and commit lockfile via integration lane.
4. Integration lane owns optional dependencies, CLI extensions, server provisioning/demo CLI, Docker Compose, docs, PostgreSQL/browser tests, CI and Git integration. Verify end-to-end actual core events → sync → PostgreSQL → authenticated UI → human review. Use synthetic data only.
5. Review spec compliance and code quality independently. Resolve failures. Run original/new tests, browser checks, builds, clean installs and public-source secret scan. Push a feature branch and open a reviewable PR with concrete validation. Hosted deployment remains a separate decision.

Tests precede new behaviors. Each lane has separate files and reports evidence; one lane commits and pushes. No user credentials, real agent history or raw local audit databases are imported.
