import unittest, uuid
from fastapi.testclient import TestClient
from aek_hub.app import create_app


class HubTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app("sqlite:///:memory:", secure_cookie=False)
        self.db = self.app.state.database
        self.org = self.db.create_organization("Synthetic", True)
        self.team = self.db.create_team(self.org, "Engineering")
        self.writer = self.db.issue_key(self.org, self.team, "ingest", "Agent")
        self.reader = self.db.issue_key(self.org, None, "viewer", "Observer")
        self.reviewer = self.db.issue_key(self.org, None, "reviewer", "Reviewer")
        self.client = TestClient(self.app)
        self.producer = str(uuid.uuid4())

    def tearDown(self):
        self.client.close()
        self.db.close()

    def auth(self, key):
        return {"Authorization": "Bearer " + key}

    def event(self, seq=1, status="running"):
        return dict(
            id=str(uuid.uuid4()),
            producer_id=self.producer,
            sequence=seq,
            run_id="demo-run",
            kind="run_started",
            occurred_at="2026-10-17T12:00:00Z",
            payload=dict(status=status, steps=[]),
        )

    def ingest(self, events, key=None):
        return self.client.post(
            "/api/ingest",
            json={"events": events},
            headers=self.auth(key or self.writer),
        )

    def test_ingest_retry_conflict_and_order(self):
        latest = self.event(2, "completed")
        old = self.event()
        self.assertEqual(self.ingest([latest, old]).status_code, 200)
        self.assertEqual(self.ingest([latest]).json()["duplicates"], [latest["id"]])
        bad = self.event(2)
        self.assertEqual(self.ingest([bad]).status_code, 409)
        runs = self.client.get("/api/runs", headers=self.auth(self.reader)).json()
        self.assertEqual(runs["items"][0]["status"], "completed")
        self.assertEqual(runs["total"], 1)

    def test_isolation_and_roles(self):
        self.ingest([self.event()])
        other = self.db.create_organization("Other")
        key = self.db.issue_key(other, None, "reviewer", "Other")
        rid = self.client.get("/api/runs", headers=self.auth(self.reader)).json()[
            "items"
        ][0]["id"]
        self.assertEqual(
            self.client.get("/api/runs/" + rid, headers=self.auth(key)).status_code, 404
        )
        self.assertEqual(
            self.client.get("/api/runs", headers=self.auth(self.writer)).status_code,
            403,
        )
        self.assertEqual(self.ingest([self.event(3)], self.reader).status_code, 403)
        self.assertEqual(
            self.client.post(
                "/api/runs/" + rid + "/reviews",
                json={"outcome": "accepted", "note": "Checked"},
                headers=self.auth(self.reader),
            ).status_code,
            403,
        )
        result = self.client.post(
            "/api/runs/" + rid + "/reviews",
            json={"outcome": "accepted", "note": "Checked"},
            headers=self.auth(self.reviewer),
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["reviewer"], "Reviewer")

    def test_session_and_csrf(self):
        self.assertEqual(
            self.client.post("/api/login", json={"key": self.reader}).status_code, 403
        )
        response = self.client.post(
            "/api/login",
            json={"key": self.reader},
            headers={"Origin": "http://127.0.0.1:8787"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.post("/api/logout").status_code, 403)
        self.assertEqual(
            self.client.post(
                "/api/logout",
                headers={
                    "Origin": "http://127.0.0.1:8787",
                    "X-CSRF-Token": response.json()["csrf_token"],
                },
            ).status_code,
            200,
        )
        self.assertEqual(self.client.get("/api/me").status_code, 401)

    def test_bounds_ownership_and_atomicity(self):
        self.assertEqual(self.ingest([]).status_code, 422)
        ev = self.event()
        self.ingest([ev])
        rival = self.db.issue_key(self.org, self.team, "ingest", "Rival")
        self.assertEqual(self.ingest([self.event(2)], rival).status_code, 409)
        new = self.event(3)
        bad = self.event(1)
        self.assertEqual(self.ingest([new, bad]).status_code, 409)
        rid = self.client.get("/api/runs", headers=self.auth(self.reader)).json()[
            "items"
        ][0]["id"]
        self.assertEqual(
            self.client.get(
                "/api/runs/" + rid + "/events", headers=self.auth(self.reader)
            ).json()["total"],
            1,
        )

    def test_sync_wire_shape_and_aggregates(self):
        ev = self.event()
        ev["kind"] = "qa_reviewed"
        ev["payload"]["steps"] = [
            dict(
                id="verify",
                state="done",
                attempts=1,
                approved=True,
                checks={"test": True},
                artifact_hashes=["a" * 64],
            )
        ]
        ev["payload"]["qa"] = dict(
            passed=False, checks={"test": False}, defect_counts={"critical": 1}
        )
        response = self.ingest([ev])
        self.assertEqual(response.status_code, 200, response.text)
        overview = self.client.get(
            "/api/overview", headers=self.auth(self.reader)
        ).json()
        self.assertEqual(overview["failures"], [{"code": "qa_failed", "count": 1}])
        rows = self.client.get("/api/runs", headers=self.auth(self.reader)).json()
        self.assertEqual(rows["items"][0]["completed_steps"], 1)

    def test_team_scope_filters_pagination_and_foreign_review(self):
        self.ingest([self.event()])
        second = self.db.create_team(self.org, "Other team")
        writer = self.db.issue_key(self.org, second, "ingest", "Second")
        ev = self.event()
        ev["producer_id"] = str(uuid.uuid4())
        ev["run_id"] = "another"
        self.ingest([ev], writer)
        scoped = self.db.issue_key(self.org, self.team, "reviewer", "Scoped")
        result = self.client.get(
            "/api/runs?limit=1&offset=1", headers=self.auth(self.reader)
        ).json()
        self.assertEqual(result["total"], 2)
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(
            self.client.get(
                "/api/runs?team_id=" + second, headers=self.auth(scoped)
            ).json()["total"],
            0,
        )
        foreign = self.client.get(
            "/api/runs?team_id=" + second, headers=self.auth(self.reader)
        ).json()["items"][0]["id"]
        self.assertEqual(
            self.client.post(
                "/api/runs/" + foreign + "/reviews",
                json={"outcome": "accepted", "note": "Attempt"},
                headers=self.auth(scoped),
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                "/api/runs?search=another", headers=self.auth(self.reader)
            ).json()["total"],
            1,
        )
        self.assertEqual(
            self.client.get(
                "/api/runs?limit=201", headers=self.auth(self.reader)
            ).status_code,
            422,
        )

    def test_revocation_expiry_and_hashed_credentials(self):
        from sqlalchemy import select
        from aek_hub.database import keys, sessions

        response = self.client.post(
            "/api/login",
            json={"key": self.reader},
            headers={"Origin": "http://127.0.0.1:8787"},
        )
        self.assertEqual(response.status_code, 200)
        with self.db.engine.begin() as c:
            self.assertNotIn(self.reader, str(c.execute(select(keys)).all()))
            self.assertNotIn(
                self.client.cookies.get("aek_session"),
                str(c.execute(select(sessions)).all()),
            )
            c.execute(sessions.update().values(expires_at="2000-01-01T00:00:00+00:00"))
        self.assertEqual(self.client.get("/api/me").status_code, 401)
        self.db.revoke_key(self.reader)
        self.assertEqual(
            self.client.get("/api/me", headers=self.auth(self.reader)).status_code, 401
        )

    def test_strict_payload_bounds(self):
        ev = self.event()
        ev["payload"]["steps"] = [
            dict(
                id="test",
                state="pending",
                attempts=0,
                approved="yes",
                checks={},
                artifact_hashes=[],
            )
        ]
        self.assertEqual(self.ingest([ev]).status_code, 422)
        ev = self.event()
        ev["payload"]["private_path"] = "/secret"
        self.assertEqual(self.ingest([ev]).status_code, 422)
        self.assertEqual(
            self.ingest([self.event() for _ in range(101)]).status_code, 422
        )
        self.assertEqual(
            self.client.post(
                "/api/ingest", content="x" * 2_000_001, headers=self.auth(self.writer)
            ).status_code,
            413,
        )

    def test_metadata_hash_and_qa_validation(self):
        ev = self.event()
        step = dict(
            id="same",
            state="pending",
            attempts=0,
            approved=False,
            checks={},
            artifact_hashes=["/private/file"],
        )
        ev["payload"]["steps"] = [step]
        self.assertEqual(self.ingest([ev]).status_code, 422)
        step["artifact_hashes"] = []
        ev["payload"]["steps"] = [step, step]
        self.assertEqual(self.ingest([ev]).status_code, 422)
        ev["payload"]["steps"] = []
        ev["payload"]["qa"] = dict(
            passed=False, checks={}, defect_counts={"critical": -1}
        )
        self.assertEqual(self.ingest([ev]).status_code, 422)

    def test_ingest_key_requires_team(self):
        with self.assertRaises(ValueError):
            self.db.issue_key(self.org, None, "ingest", "Unscoped")

    def test_latest_receipt_advances_for_late_event(self):
        from sqlalchemy import select
        from aek_hub.database import runs, events

        self.ingest([self.event(2, "completed")])
        self.ingest([self.event(1)])
        with self.db.engine.connect() as c:
            run = (
                c.execute(select(runs).where(runs.c.org_id == self.org))
                .mappings()
                .one()
            )
            latest = c.execute(
                select(events.c.received_at)
                .where(events.c.org_id == self.org)
                .order_by(events.c.received_at.desc())
            ).scalar()
        self.assertEqual(run["last_received_at"], latest)
        self.assertEqual(run["last_sequence"], 2)

    def test_response_security_headers(self):
        result = self.client.get("/api/me", headers=self.auth(self.reader))
        self.assertEqual(result.headers.get("cache-control"), "no-store")
        self.assertEqual(result.headers.get("x-content-type-options"), "nosniff")
        self.assertIn(
            "frame-ancestors 'none'", result.headers.get("content-security-policy", "")
        )

    def test_multi_producer_lock_order_is_stable(self):
        from sqlalchemy import event

        seen = []

        def capture(conn, cursor, statement, parameters, context, many):
            if (
                statement.startswith("SELECT hub_producers.")
                and "WHERE hub_producers.id" in statement
            ):
                seen.append(
                    parameters[0]
                    if isinstance(parameters, tuple)
                    else parameters["id_1"]
                )

        low_id, high_id = sorted(str(uuid.uuid4()) for _ in range(2))
        high = self.event()
        high["producer_id"] = high_id
        low = self.event()
        low["producer_id"] = low_id
        event.listen(self.db.engine, "before_cursor_execute", capture)
        try:
            self.assertEqual(self.ingest([high, low]).status_code, 200)
        finally:
            event.remove(self.db.engine, "before_cursor_execute", capture)
        self.assertEqual(seen, sorted(set(seen)))
