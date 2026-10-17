"""Real PostgreSQL contract checks; opt in with AEK_TEST_DATABASE_URL."""

import os
import unittest
import test_api
from aek_hub.app import create_app
from fastapi.testclient import TestClient


@unittest.skipUnless(
    os.environ.get("AEK_TEST_DATABASE_URL"), "PostgreSQL URL not configured"
)
class PostgreSQLTests(test_api.HubTests):
    def setUp(self):
        # Every test provisions a fresh organization; no existing data is read.
        import uuid

        self.app = create_app(os.environ["AEK_TEST_DATABASE_URL"], secure_cookie=False)
        self.db = self.app.state.database
        self.org = self.db.create_organization("Synthetic-" + str(uuid.uuid4()), True)
        self.team = self.db.create_team(self.org, "Engineering")
        self.writer = self.db.issue_key(self.org, self.team, "ingest", "Agent")
        self.reader = self.db.issue_key(self.org, None, "viewer", "Observer")
        self.reviewer = self.db.issue_key(self.org, None, "reviewer", "Reviewer")
        self.client = TestClient(self.app)
        self.producer = str(uuid.uuid4())
