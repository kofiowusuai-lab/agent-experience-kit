# Dashboard API v1

All JSON routes are under `/api`. Errors use a `detail` string. All stored datetimes are UTC ISO strings. All read endpoints require viewer/reviewer authentication. Optional `team_id` filter is further intersected with the key's own team scope. Limits default to 50, maximum 200; offsets nonnegative. Keys are opaque random strings with SHA-256 digests at rest. No unauthenticated data endpoint exists except `/health` (boolean readiness only).

## Authentication

- `POST /api/login` body `{key: string}`; Origin must equal configured public origin. Only viewer/reviewer keys accepted. Sets HttpOnly SameSite Strict cookie. Returns the same payload as `/api/me`.
- `GET /api/me`: `{organization:{id,name,demo:boolean},actor:{label,role},teams:[{id,name}],csrf_token:string}`.
- `POST /api/logout`: checks Origin + `X-CSRF-Token`, revokes session and clears cookie.
- Ingest uses `Authorization: Bearer KEY` only. Other API routes may use viewer/reviewer bearer auth or a browser session. Browser mutation routes require matching Origin and CSRF; bearer requests are explicitly authenticated and do not rely on cookies.

## Ingestion

`POST /api/ingest`, ingest role only: `{events:[EVENT]}` (1..100 events, bounded body size). Event shape is defined in dashboard-design.md. Response `{accepted:[event_id],duplicates:[event_id]}`. Identical retry accepted as duplicate; conflicting id/sequence reuse 409 and entire batch rolled back. Producer ownership is bound to the provisioning agent key; another writer cannot take over its identity. Token rotation requires deliberate provisioning/producer migration in v1.

## Query responses

`GET /api/overview?team_id=`:
`{runs:{total,completed,failed,running,pending},agents:{total,active},events_total,unreviewed_failures,latest_ingestion_at,activity:[{date,events,failures}],failures:[{code,count}],teams:[{id,name,runs,failed}]}`.
Active means received an event within 24 hours, not a heartbeat-backed online guarantee. Activity is the last 7 UTC receipt days. Failure counts are normalized failure events, not inferred business outcomes.

`GET /api/runs?team_id=&status=&search=&limit=&offset=`:
`{items:[RUN],total,limit,offset}`. Search run_id/agent. Status pending/running/failed/completed.
RUN: `{id,run_id,producer_id,agent,team_id,team_name,status,step_count,completed_steps,attempts,last_event_at,last_received_at,last_sequence,review_count}`. `id` is the server's opaque run UUID, distinct from producer-supplied run_id.

`GET /api/runs/{id}`:
`{run:RUN,steps:[STEP],reviews:[REVIEW]}`. STEP: `{id,state,attempts,approved,checks,artifact_hashes}`. Hashes are reported byte identities, not independently verified central artifacts. Reviews newest first, bounded latest 100; full paginated history is available below.

`GET /api/runs/{id}/events?limit=&offset=`:
`{items:[{id,kind,sequence,occurred_at,received_at,payload}],total,limit,offset}` sorted newest sequence first.

`GET /api/reviews?team_id=&run_id=&limit=&offset=`:
`{items:[REVIEW],total,limit,offset}`.
REVIEW: `{id,run_id,run_label,team_id,team_name,outcome,note,reviewer,created_at}`.

`POST /api/runs/{id}/reviews`, reviewer role only:
`{outcome: accepted|needs_changes|escalated,note:string(1..2000)}`. Returns REVIEW. Reviewer is taken from authenticated key; no client-supplied identity accepted. Reviews append only and never overwrite agent state or earlier decisions.

`GET /api/failures?team_id=`:
`{items:[{code,count,affected_runs,last_seen}],total}`. Codes from event failure_code; step_failed defaults external_failure; failed qa_reviewed defaults qa_failed. Unknown failures never produce invented causes. No raw exception text is uploaded automatically.

## Backend implementation interface

`aek_hub.app.create_app(database_url, origin='http://127.0.0.1:8787', static_dir=None, secure_cookie=True)` returns FastAPI app. `aek_hub.app.from_env()` uses AEK_DATABASE_URL, AEK_PUBLIC_ORIGIN, AEK_STATIC_DIR, AEK_ALLOW_INSECURE_LOCALHOST (only loopback HTTP). No hardcoded production key.

`aek_hub.database.Database(url)` exposes `initialize()`, `create_organization(name,demo=False)->id`, `create_team(org_id,name)->id`, `issue_key(org_id,team_id,role,label)->plain_key`, `revoke_key(plain_key)`, `close()`. Root integrates provisioning CLI and demo seed using these APIs. Backend owns server package and server tests; integration owns CLI/packaging and public docs.
