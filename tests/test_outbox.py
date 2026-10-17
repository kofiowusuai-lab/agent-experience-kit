import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from agent_experience_kit.store import Store


class OutboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'state.db'
        self.file = Path(self.tmp.name) / 'secret-proof.txt'
        self.file.write_text('private contents')
        self.store = Store(self.path)
        self.addCleanup(self.store.close)
        self.contract = {'id': 'run', 'origin': 'private chat', 'steps': [{'id': 'build', 'required_checks': ['tested']}]}

    def test_offline_durable_identity_sanitized_idempotent_events(self):
        with patch('urllib.request.urlopen', side_effect=AssertionError('network')):
            self.store.start(self.contract)
            self.store.start(self.contract)
            self.store.complete('run', 'build', 'private chat', {'tested': True}, [str(self.file)])
            self.store.complete('run', 'build', 'private chat', {'tested': True}, [str(self.file)])
        events = self.store.pending_events()
        self.assertEqual([e['kind'] for e in events], ['run_started', 'step_completed'])
        self.assertEqual([e['sequence'] for e in events], [1, 2])
        raw = json.dumps(events)
        for secret in ['private chat', 'secret-proof', 'private contents', str(self.file)]:
            self.assertNotIn(secret, raw)
        with Store(self.path) as reopened:
            self.assertEqual(reopened.pending_events(), events)
        self.store.ack_events([events[0]['id']])
        self.assertEqual(len(self.store.pending_events()), 1)
        with self.assertRaises(ValueError):
            self.store.ack_events(['foreign'])

    def test_event_failure_rolls_back_state(self):
        with patch.object(self.store, '_queue_event', side_effect=RuntimeError('disk')):
            with self.assertRaises(RuntimeError):
                self.store.start(self.contract)
        self.assertEqual(self.store.pending_events(), [])
        with self.assertRaises(ValueError):
            self.store.status('run')

    def test_refresh_emits_once_and_bootstrap_only_old_runs(self):
        self.store.start(self.contract)
        self.store.complete('run', 'build', 'private chat', {'tested': True}, [str(self.file)])
        self.file.write_text('changed')
        self.store.status('run')
        self.store.status('run')
        self.assertEqual([e['kind'] for e in self.store.pending_events()].count('evidence_invalidated'), 1)
        self.assertEqual(self.store.snapshot_existing(), 0)
        self.store.connection.execute('DELETE FROM outbox')
        self.assertEqual(self.store.snapshot_existing(), 1)
        self.assertEqual(self.store.snapshot_existing(), 0)
        self.assertEqual(self.store.pending_events()[0]['kind'], 'snapshot_imported')

    def test_approval_failure_and_review_allowlist(self):
        self.store.start(self.contract)
        self.store.approve('run', 'build', 'private chat')
        self.store.approve('run', 'build', 'private chat')
        self.store.fail('run', 'build', 'private chat', 'private failure')
        report = {'builder': 'private builder', 'reviewer': 'private reviewer', 'declared_pass': True,
                  'required_checks': ['tested'], 'checks': {'tested': True},
                  'defects': [{'severity': 'major', 'description': 'private description'}]}
        verdict = self.store.record_review('run', report)
        self.assertFalse(verdict['passed'])
        events = self.store.pending_events()
        self.assertEqual([e['kind'] for e in events], ['run_started', 'step_approved', 'step_failed', 'qa_reviewed'])
        self.assertEqual(events[-1]['payload']['qa']['defect_counts']['major'], 1)
        self.assertNotIn('private', json.dumps(events))

    def test_rejected_gate_records_category_after_state_rollback(self):
        self.store.start(self.contract)
        with self.assertRaises(ValueError):
            self.store.complete('run', 'build', 'private chat', {'tested': False}, [])
        event = self.store.pending_events()[-1]
        self.assertEqual(event['kind'], 'gate_rejected')
        self.assertEqual(event['payload']['failure_code'], 'checks_failed')
        self.assertEqual(self.store.status('run')['steps'][0]['attempts'], 0)
        count = self.store.pending_count()
        with self.assertRaises(ValueError):
            self.store.approve('run', 'build', 'foreign origin')
        self.assertEqual(self.store.pending_count(), count)

    def test_legacy_snapshot_rechecks_deleted_artifacts(self):
        self.store.start(self.contract)
        self.store.complete('run', 'build', 'private chat', {'tested': True}, [str(self.file)])
        self.store.connection.execute('DELETE FROM outbox')
        self.file.unlink()
        self.assertEqual(self.store.snapshot_existing(), 1)
        events = self.store.pending_events()
        self.assertEqual([event['kind'] for event in events], ['evidence_invalidated', 'snapshot_imported'])
        self.assertNotEqual(events[-1]['payload']['status'], 'completed')
        self.assertEqual(events[-1]['payload']['steps'][0]['artifact_hashes'], [])
        self.assertEqual(self.store.status('run')['steps'][0]['state'], 'pending')
        self.assertEqual(self.store.snapshot_existing(), 0)
