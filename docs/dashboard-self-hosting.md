# Self-hosting the audit dashboard

The v0.2 dashboard preview extends the existing local kit. One hub collects scoped, agent-reported metadata across machines. PostgreSQL is the central store; local SQLite remains the offline checkpoint and delivery queue. No private history is imported automatically.

```mermaid
flowchart LR
  A[Agent task checkpoints] --> B[Transactional local outbox]
  B -->|Explicit bounded sync| C[Scoped ingestion API]
  C --> D[(PostgreSQL audit history)]
  D --> E[Team dashboard]
  E --> F[Append-only human reviews]
  F --> D
```

## Docker

Requires Docker with Compose. From this checkout:

```sh
cp .env.example .env
# Edit .env: replace POSTGRES_PASSWORD with a random URL-safe password.
docker compose up --build -d
docker compose exec hub aek-hub init --organization "Acme" --team "Engineering"
```

Use the returned organization/team UUIDs to issue keys:

```sh
docker compose exec hub aek-hub key --organization ORG_UUID --team TEAM_UUID --role ingest --label "build-agent-01"
docker compose exec hub aek-hub key --organization ORG_UUID --role reviewer --label "Operations lead"
```

Key commands deliberately display a newly issued credential. Capture it privately; do not paste it into issues, source files, shared logs or screenshots. Agent keys need a team. Viewer/reviewer keys may be team-scoped or organization-wide. Only the host operator can provision keys; no public administration endpoint exists.

Open `http://127.0.0.1:8787` and enter a viewer or reviewer key. Browser login exchanges it for an expiring HttpOnly session. Revoking its backing key invalidates session access too.

Compose binds the hub to loopback and keeps PostgreSQL on the private container network. For shared hosting, use a TLS reverse proxy, set the exact `AEK_PUBLIC_ORIGIN=https://your-host`, set `AEK_ALLOW_INSECURE_LOCALHOST=0`, and configure routing/access controls deliberately. The app refuses insecure cookies for a non-loopback origin. Do not expose the loopback development configuration directly.

## Python and Node development

Use Python 3.10+ and Node 22.12+:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[hub,hub-test]'
npm ci --prefix dashboard
npm run build --prefix dashboard
# Set AEK_DATABASE_URL privately to postgresql+psycopg://USER:PASSWORD@HOST/DB.
export AEK_PUBLIC_ORIGIN=http://127.0.0.1:8787
export AEK_ALLOW_INSECURE_LOCALHOST=1
export AEK_STATIC_DIR="$PWD/dashboard/dist"
aek-hub serve
```

The optional hub dependencies do not change the standard-library-only agent client. The built UI is served from the same origin as the API. Vite development with a second port requires setting the configured public origin to that exact development origin; see dashboard/README.md.

## Synthetic demonstration

With the hub running and the same `AEK_DATABASE_URL` available in a second terminal:

```sh
aek-hub demo --url http://127.0.0.1:8787 --output .aek/demo-credentials.json
```

This explicitly creates a fictional Aster Labs workspace, 12 agents, three teams and 36 runs through the real ingestion API. Its credential file is created with restrictive permissions and never overwritten. The UI labels this workspace **SYNTHETIC DEMO**. All receipt activity initially appears on the actual seed day; historical activity is not fabricated. Earlier data is not read or modified. Repeated seeding requires a deliberate new output file and creates another workspace.

## Connect agents

Use a separate scoped ingest key for each agent/producer and keep it in the agent's environment or secret store:

```sh
# Set AEK_INGEST_TOKEN privately; do not place the key in command arguments.
aek sync --url https://your-hub.example --db .aek/state.db
# Record an automated QA verdict locally, then sync its sanitized summary:
aek review review.json --run RUN_ID --db .aek/state.db
```

`sync` sends one batch, up to 100 events, with a finite timeout and no automatic retries. Repeat on a bounded schedule while its `pending` count is nonzero. Redirects are rejected to prevent credential forwarding. A batch is acknowledged locally only when the server returns exactly all submitted IDs as accepted or identical duplicates. Lost responses are safe to replay. Failed deliveries leave the queue intact and never block local task execution.

On first explicit sync, old runs without events are refreshed and imported as current snapshots. Past actions cannot be reconstructed. After an interrupted local operation, refresh `aek status RUN_ID` before syncing when current artifact validity matters. Queued events represent recorded checkpoints, not a live inspection of every machine's filesystem.

Automatically shared fields exclude artifact paths, filenames, contents, origins, raw exception text and raw QA descriptions. Run/step/check names are still supplied by the operator: treat them as potentially sensitive metadata. Explicit human review notes are shared with the workspace. There is no automatic redaction of those notes.

## What the dashboard provides

- Team/status/search filters, SQL-backed pagination and current reported run progress.
- Audit events with producer sequence, client occurrence time and server receipt time.
- Reported artifact hashes and QA checks/severity counts.
- Immutable API-level human review history; dispositions do not silently change agent state.
- Normalized failure-event categories and affected-run counts.
- Explicit refresh, no hidden browser token persistence, and readonly viewer access.

Late delivery adds history without rolling the latest state backward. Producer ownership is bound to an ingest key. v1 key rotation requires a deliberately provisioned producer identity/migration; it is not an automatic takeover. Active-agent counts mean received activity in the last 24 hours, not a heartbeat-backed online guarantee.

## Limits and production work

This is a self-hosted foundation, not a completed enterprise identity or compliance product. Reviewer labels identify provisioned credentials; they do not establish an independently authenticated human identity. SSO/SCIM, user invitations, retention controls, evidence object storage, background delivery workers, signed receipts, migrations beyond the initial schema, backups and workload-specific load testing remain deployment work.

History is append-only through API routes, not cryptographically tamper-proof against database administrators. The schema uses application scope checks and uniqueness constraints; database administrator access remains trusted. Local queues retain delivered events in this version and need an operator retention policy before long-term fleet use.

Wire limits include 100 events/2 MB per request, 1,000 steps per event and 200-character run/step identifiers. Oversized otherwise-valid local contracts remain local until adapted; a rejected batch stays queued. No contract, result or business outcome is independently proven merely because an agent submitted it.

## Verify a change

```sh
python -m unittest discover -s tests -v
python -m unittest discover -s tests/hub -v
# Set AEK_TEST_DATABASE_URL to a test PostgreSQL database for the same tests on PostgreSQL.
# With a hub running against it, set AEK_INTEGRATION_URL to its origin:
python -m unittest discover -s tests/integration -v
npm run build --prefix dashboard
# Set AEK_E2E_REVIEWER_KEY and AEK_E2E_VIEWER_KEY to synthetic workspace keys:
cd dashboard
npx playwright install chromium
npx playwright test
```

Tests provision isolated synthetic organizations. Do not use production credentials for integration tests. Browser checks cover desktop/mobile login, evidence, human reviews, filters, empty/error recovery, session handling and viewer restrictions.
