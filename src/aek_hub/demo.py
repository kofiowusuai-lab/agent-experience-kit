"""Invented demonstration data, provisioned only by explicit operator command."""
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import uuid
import urllib.request

from .database import Database
from .cli import write_private_json
from agent_experience_kit.sync import _NoRedirect


def seed_demo(database_url, hub_url, output):
    if Path(output).exists():
        raise ValueError("Demo credentials already exist; refusing to create another workspace")
    # Validate origin before creating data or sending newly issued credentials.
    from agent_experience_kit.sync import sync_once
    class EmptyOutbox:
        def pending_events(self, limit): return []
        def pending_count(self): return 0
    sync_once(EmptyOutbox(), hub_url, "validation-only")
    opener = urllib.request.build_opener(_NoRedirect())
    with opener.open(hub_url.rstrip("/") + "/health", timeout=10) as response:
        if not json.load(response).get("ready"):
            raise ValueError("Start the hub before seeding demonstration data")
    db = Database(database_url)
    try:
        db.initialize()
        org = db.create_organization("Aster Labs", demo=True)
        team_ids = [db.create_team(org, name) for name in ["Product engineering", "Content operations", "Revenue operations"]]
        viewer = db.issue_key(org, None, "viewer", "Demo observer")
        reviewer = db.issue_key(org, None, "reviewer", "Demo operations lead")
        credentials = {"organization_id": org, "team_ids": team_ids, "viewer_key": viewer, "reviewer_key": reviewer}
        # Preserve recovery access even if a later request fails. Never print keys to logs.
        write_private_json(output, credentials)
        titles = ["Checkout consent flow", "Release evidence bundle", "Caption timing review",
                  "Approved master handoff", "Prospect cohort audit", "Portuguese localization"]
        for agent_index in range(12):
            token = db.issue_key(org, team_ids[agent_index % 3], "ingest", f"{['build', 'content', 'research'][agent_index % 3]}-agent-{agent_index + 1:02}")
            producer = str(uuid.uuid4()); sequence = 0; batch = []
            for task in range(3):
                mode = (agent_index + task) % 6
                run = f"{titles[(agent_index + task) % len(titles)]} · {agent_index + 1:02}-{task + 1}"
                steps = [{"id": name, "state": "pending", "attempts": 0, "approved": False,
                          "checks": {}, "artifact_hashes": []} for name in ["prepare", "produce", "verify", "handoff"]]
                def event(kind, status, **extra):
                    nonlocal sequence
                    sequence += 1
                    batch.append({"id": str(uuid.uuid4()), "producer_id": producer, "sequence": sequence,
                        "run_id": run, "kind": kind,
                        "occurred_at": (datetime.now(timezone.utc) - timedelta(minutes=60 - task * 12)).isoformat(),
                        "payload": {"status": status, "steps": copy.deepcopy(steps), **extra}})
                event("run_started", "pending")
                completed = 4 if mode in (0, 1) else 2 if mode in (2, 3) else 0
                for index in range(completed):
                    steps[index].update(state="done", attempts=1, checks={"acceptance_passed": True},
                                        artifact_hashes=[hashlib.sha256(f"synthetic:{run}:{index}".encode()).hexdigest()])
                    event("step_completed", "completed" if index == 3 else "running")
                if mode == 2:
                    steps[2].update(state="failed", attempts=1)
                    event("qa_reviewed", "failed", failure_code="qa_failed",
                          qa={"passed": False, "checks": {"caption_timing": False}, "defect_counts": {"critical": 1, "major": 0, "minor": 0}})
                elif mode == 5:
                    steps[0].update(state="failed", attempts=2)
                    event("step_failed", "failed", failure_code="external_failure")
                elif mode == 3:
                    event("gate_rejected", "running", failure_code="approval_required")
            request = urllib.request.Request(hub_url.rstrip("/") + "/api/ingest",
                data=json.dumps({"events": batch}).encode(),
                headers={"Content-Type": "application/json", "Authorization": "Bearer " + token}, method="POST")
            with opener.open(request, timeout=15) as response:
                result = json.load(response)
                if len(result.get("accepted", [])) != len(batch):
                    raise ValueError("Demonstration batch was not fully accepted")
        return {"organization": "Aster Labs (synthetic demo)", "agents": 12, "runs": 36,
                "credentials_file": str(output), "dashboard": hub_url}
    finally:
        db.close()
