"""Opt-in real HTTP and database journey; provisions isolated synthetic data only."""
import json
import os
from pathlib import Path
import tempfile
import unittest
import urllib.error
import urllib.request
import uuid


@unittest.skipUnless(os.environ.get('AEK_INTEGRATION_URL') and os.environ.get('AEK_TEST_DATABASE_URL'), 'Live hub integration is not configured')
class LiveHubTests(unittest.TestCase):
    def test_thirty_two_producers_concurrently_preserve_latest_state(self):
        from concurrent.futures import ThreadPoolExecutor
        from datetime import datetime, timezone
        from aek_hub.database import Database
        db = Database(os.environ['AEK_TEST_DATABASE_URL'])
        self.addCleanup(db.close)
        db.initialize()
        org = db.create_organization('Synthetic concurrent ingestion ' + str(uuid.uuid4()), True)
        team = db.create_team(org, 'Synthetic fleet')
        tokens = [db.issue_key(org, team, 'ingest', f'Synthetic agent {index}') for index in range(32)]
        reader = db.issue_key(org, None, 'viewer', 'Synthetic observer')
        base = os.environ['AEK_INTEGRATION_URL']
        def send(token):
            producer = str(uuid.uuid4())
            def event(sequence, state):
                return {'id': str(uuid.uuid4()), 'producer_id': producer, 'sequence': sequence,
                    'run_id': 'synthetic-concurrent-run', 'kind': 'step_completed' if sequence == 2 else 'run_started',
                    'occurred_at': datetime.now(timezone.utc).isoformat(),
                    'payload': {'status': 'completed' if state == 'done' else 'pending', 'steps': [
                        {'id': 'check', 'state': state, 'attempts': 1 if state == 'done' else 0,
                         'approved': False, 'checks': {}, 'artifact_hashes': []}]}}
            req = urllib.request.Request(base + '/api/ingest', data=json.dumps({'events': [event(2, 'done'), event(1, 'pending')]}).encode(),
                headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=20) as response:
                return len(json.load(response)['accepted'])
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(send, tokens)), 64)
        request = urllib.request.Request(base + '/api/overview', headers={'Authorization': 'Bearer ' + reader})
        with urllib.request.urlopen(request, timeout=10) as response:
            overview = json.load(response)
        self.assertEqual(overview['agents']['total'], 32)
        self.assertEqual(overview['runs']['completed'], 32)
        self.assertEqual(overview['events_total'], 64)

    def test_core_outbox_http_postgres_and_human_review(self):
        from aek_hub.database import Database
        from agent_experience_kit.store import Store
        from agent_experience_kit.sync import sync_once
        db = Database(os.environ['AEK_TEST_DATABASE_URL'])
        self.addCleanup(db.close)
        db.initialize()
        org = db.create_organization('Synthetic integration ' + str(uuid.uuid4()), True)
        team = db.create_team(org, 'Integration team')
        ingest = db.issue_key(org, team, 'ingest', 'Integration agent')
        reviewer = db.issue_key(org, None, 'reviewer', 'Integration reviewer')
        other = db.create_organization('Synthetic isolated organization', True)
        foreign = db.issue_key(other, None, 'viewer', 'Foreign observer')
        base = os.environ['AEK_INTEGRATION_URL']

        def request(path, token, body=None):
            req = urllib.request.Request(base + path,
                data=None if body is None else json.dumps(body).encode(),
                headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.load(response)

        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / 'private-artifact.txt'
            artifact.write_text('Synthetic local evidence, never uploaded.')
            with Store(Path(directory) / 'state.db') as store:
                store.start({'id': 'integration-run', 'origin': 'private:conversation-label', 'steps': [
                    {'id': 'produce', 'required_checks': ['created']},
                    {'id': 'verify', 'depends_on': ['produce'], 'required_checks': ['accepted'], 'requires_approval': True}]})
                store.complete('integration-run', 'produce', 'private:conversation-label', {'created': True}, [str(artifact)])
                with self.assertRaises(ValueError):
                    store.complete('integration-run', 'verify', 'private:conversation-label', {'accepted': True}, [str(artifact)])
                bad = {'builder': 'producer', 'reviewer': 'reviewer', 'declared_pass': True,
                       'required_checks': ['alignment'], 'checks': {'alignment': False},
                       'defects': [{'severity': 'critical', 'description': 'Private description, not uploaded.'}]}
                self.assertFalse(store.record_review('integration-run', bad)['passed'])
                store.approve('integration-run', 'verify', 'private:conversation-label')
                store.complete('integration-run', 'verify', 'private:conversation-label', {'accepted': True}, [str(artifact)])
                wire = json.dumps(store.pending_events())
                for private in ['private:conversation-label', str(artifact), 'Private description', 'never uploaded']:
                    self.assertNotIn(private, wire)
                result = sync_once(store, base, ingest)
                self.assertGreaterEqual(result['accepted'], 6)
                self.assertEqual(result['pending'], 0)
                self.assertEqual(sync_once(store, base, ingest)['sent'], 0)
                listed = request('/api/runs', reviewer)
                self.assertEqual(listed['total'], 1)
                run = listed['items'][0]
                self.assertEqual(run['status'], 'completed')
                events = request('/api/runs/' + run['id'] + '/events', reviewer)
                self.assertIn('qa_reviewed', {e['kind'] for e in events['items']})
                self.assertIn('gate_rejected', {e['kind'] for e in events['items']})
                review = request('/api/runs/' + run['id'] + '/reviews', reviewer,
                                 {'outcome': 'needs_changes', 'note': 'Synthetic follow-up remains required.'})
                self.assertEqual(review['reviewer'], 'Integration reviewer')
                self.assertEqual(request('/api/reviews', reviewer)['total'], 1)
                self.assertEqual(request('/api/runs', foreign)['total'], 0)
                with self.assertRaises(urllib.error.HTTPError) as error:
                    request('/api/runs/' + run['id'], foreign)
                self.assertEqual(error.exception.code, 404)
                artifact.write_text('Changed after acceptance.')
                self.assertFalse(store.status('integration-run')['complete'])
                sync_once(store, base, ingest)
                self.assertNotEqual(request('/api/runs', reviewer)['items'][0]['status'], 'completed')


if __name__ == '__main__':
    unittest.main()
