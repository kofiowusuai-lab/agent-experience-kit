# Central dashboard v0.2 design

Extend the open-source toolkit with an optional self-hosted audit hub. Local checkpoints remain usable offline; a transactional outbox synchronizes metadata to one PostgreSQL-backed server. The dashboard aggregates team-scoped runs, audit events, automated QA reports, human review decisions and normalized failure categories. This is an observable control plane, not a remote execution service.

## Architecture

- Python core remains standard-library-only. New local outbox and explicit `aek sync` use urllib with finite timeouts, idempotent event IDs and acknowledgement only after acceptance. No network calls occur inside a task transaction.
- Optional FastAPI + SQLAlchemy + psycopg server, PostgreSQL in Docker Compose. SQLite is allowed only in fast server unit tests; PostgreSQL integration tests run against the real engine.
- React + TypeScript + Vite dashboard served by FastAPI under the same origin. No browser token in localStorage. A login exchanges a scoped viewer/reviewer key for an opaque HttpOnly session with expiry, SameSite=Strict, Origin and CSRF checks for writes. HTTPS secure cookies default on; local loopback development explicitly permits HTTP.
- Credentials are provisioned by an operator CLI, hashed at rest, scoped to an organization and optionally a team, with ingest/viewer/reviewer roles. Agent keys cannot browse the dashboard; viewer keys cannot submit human reviews. Cross-organization access returns no records. Browser sessions are not an enterprise SSO implementation.

## Events and delivery

Every mutating core operation queues an event in the same SQLite transaction as state. Refresh-induced invalidation queues an event too. Events have UUID id, stable local UUID producer_id, positive monotonically increasing sequence, run_id, kind, UTC occurred_at and an allowlisted payload. File paths, file contents, origin/chat labels, free-text failure reasons and raw QA descriptions are excluded. Step/check names and run IDs remain operator-supplied metadata and need review before sharing.

Payload: `status` (pending/running/failed/completed), `steps` (id,state,attempts,approved,checks,artifact_hashes), optional `failure_code`, optional `qa` (passed,checks,defect_counts). Kinds: run_started, step_completed, step_failed, step_approved, evidence_invalidated, gate_rejected, snapshot_imported, qa_reviewed. Explicit first sync can seed a snapshot of old runs; it cannot recreate historical events. No local task is blocked by an unreachable hub.

The server assigns organization/team/agent from the authenticated key, not the request. Duplicate event IDs with identical payloads are acknowledged; conflicting reuse is rejected. Unique producer sequence prevents ambiguous history. Run projections advance only on a newer sequence; late delivery never rolls current state backward. Immutable history preserves received time separately from client time. A batch is bounded and transactional. Ingest permissions cannot mutate existing history through API routes. PostgreSQL administrators can alter storage; this is not a tamper-proof ledger.

## UI

Audience: engineering and operations leads managing many agents. Job: find work needing attention, inspect evidence and record a disposition. Palette: slate/navy #162C43, blue #356DD6, pale blue-gray #F1F5F9, white #FFFFFF, amber #B76B16, red #B94046. Display/body: locally hosted Barlow and Source Sans 3; data labels: IBM Plex Mono where available, system monospace fallback. Avoid marketing hero layouts; use a persistent narrow navigation rail and a light work surface.

Signature: a per-run step ribbon links current state to its acceptance/evidence history. Main view includes team/status/search filters, runs table, recent activity and failure patterns. Run detail provides step evidence hashes, paginated audit trail, automated QA outcomes and append-only human review history. Reviews and failure-pattern pages are functional API-driven views, not decorative navigation. Data is labeled as reported by agents, with last-ingested time and clear stale/empty/error states. Demo data is explicitly labeled and never mixes with real workspace data.

## Boundaries

No hosted deployment, spending, customer data import, SSO/SCIM, billing, remote agent control, or automatic publication. Deliver an isolated branch, Docker setup, reproducible synthetic demo, API and browser tests, and a GitHub reviewable change. Production hardening still includes external identity, retention, backups, TLS ingress and load testing appropriate to deployment.

## Acceptance

Existing 38 tests remain green. New tests prove outbox atomicity/offline behavior, sanitization, acknowledgement/replay, idempotent ingestion, sequence conflict/out-of-order handling, organization/team isolation, role separation, session expiry, Origin/CSRF checks, immutable reviews, filters/pagination and real PostgreSQL behavior. Browser checks cover login, overview, filters, run detail, QA/audit history, reviewer submission, empty/error states, mobile layout and keyboard focus. Build/package paths and Docker instructions are verified, with limitations documented.
