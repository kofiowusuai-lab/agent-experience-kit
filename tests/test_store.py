import copy
import sqlite3
import tempfile
import unittest
from pathlib import Path

try:
    from agent_experience_kit.store import Store, validate_contract
except ImportError:
    Store = validate_contract = None


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(Store, 'Store implementation is required')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'state.db'
        self.file = Path(self.tmp.name) / 'proof.txt'
        self.file.write_text('proof')
        self.store = Store(self.path)
        self.addCleanup(self.store.close)
        self.contract = {'id': 'run', 'origin': 'local', 'steps': [
            {'id': 'build', 'required_checks': ['tested'], 'requires_approval': True},
            {'id': 'review', 'depends_on': ['build']}]}

    def start(self):
        return self.store.start(self.contract)

    def build(self):
        self.store.approve('run', 'build', 'local')
        return self.store.complete('run', 'build', 'local', {'tested': True}, [str(self.file)])

    def test_nested_database_parent_created(self):
        nested = Path(self.tmp.name) / 'nested' / 'state.db'
        with Store(nested) as store:
            self.assertEqual(store.start(self.contract)['id'], 'run')
        self.assertTrue(nested.is_file())
        with Store(':memory:') as store:
            self.assertEqual(store.start(self.contract)['id'], 'run')

    def test_large_artifact_hash(self):
        import hashlib
        content = b'evidence-block' * 200000
        self.file.write_bytes(content)
        self.start()
        status = self.build()
        self.assertEqual(status['steps'][0]['artifacts'][0]['sha256'], hashlib.sha256(content).hexdigest())

    def test_long_dependency_graph_without_recursion(self):
        contract = {'id': 'long', 'origin': 'local', 'steps': [
            {'id': str(index), 'depends_on': [str(index + 1)] if index < 1099 else []}
            for index in range(1100)]}
        self.assertEqual(len(validate_contract(contract)['steps']), 1100)
        contract['steps'][-1]['depends_on'] = ['0']
        with self.assertRaises(ValueError):
            validate_contract(contract)

    def test_validation(self):
        good = validate_contract(self.contract)
        self.assertEqual(good['steps'][0]['max_attempts'], 3)
        for value in [None, {}, {'id': 'x', 'origin': 'y', 'steps': []}]:
            with self.assertRaises(ValueError):
                validate_contract(value)
        for field, value in [('id', ''), ('required_checks', 'x'), ('required_checks', ['x', 'x']),
                             ('depends_on', [3]), ('min_artifacts', True), ('max_attempts', 0),
                             ('requires_approval', 1)]:
            bad = copy.deepcopy(self.contract)
            bad['steps'][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_contract(bad)
        for deps in [['unknown'], ['build'], ['review']]:
            bad = copy.deepcopy(self.contract)
            bad['steps'][0]['depends_on'] = deps
            with self.assertRaises(ValueError):
                validate_contract(bad)

    def test_gates_are_atomic_and_origin_isolated(self):
        before = self.start()
        for origin, checks in [('other', {'tested': True}), ('local', {'tested': 1}), ('local', {})]:
            with self.assertRaises(ValueError):
                self.store.complete('run', 'build', origin, checks, [str(self.file)])
        with self.assertRaises(ValueError):
            self.store.approve('run', 'build', 'other')
        with self.assertRaises(ValueError):
            self.store.fail('run', 'build', 'other', 'failure')
        self.assertEqual(before, self.store.status('run'))
        with self.assertRaises(ValueError):
            self.store.complete('run', 'review', 'local', {}, [str(self.file)])
        self.build()
        final = self.store.complete('run', 'review', 'local', {}, [str(self.file)])
        self.assertTrue(final['complete'])
        self.assertEqual(self.store.complete('run', 'review', 'local', {}, [str(self.file)]), final)
        self.assertEqual(final['steps'][1]['attempts'], 1)

    def test_two_connections_share_attempt_budget(self):
        self.start()
        with Store(self.path) as second:
            self.store.fail('run', 'build', 'local', 'first')
            second.fail('run', 'build', 'local', 'second')
            self.assertEqual(self.store.status('run')['steps'][0]['attempts'], 2)
            second.fail('run', 'build', 'local', 'third')
            with self.assertRaises(ValueError):
                self.store.fail('run', 'build', 'local', 'fourth')

    def test_approval_response_revalidates_evidence(self):
        self.start()
        self.build()
        self.store.complete('run', 'review', 'local', {}, [str(self.file)])
        self.file.write_text('changed')
        self.assertFalse(self.store.approve('run', 'review', 'local')['complete'])

    def test_missing_file_invalidates_completion(self):
        self.start()
        self.build()
        self.file.unlink()
        self.assertEqual(self.store.status('run')['steps'][0]['state'], 'pending')

    def test_unknown_run_and_duplicate_run(self):
        with self.assertRaises(ValueError):
            self.store.status('unknown')
        before = self.start()
        self.assertEqual(before, self.start())
        changed = copy.deepcopy(self.contract)
        changed['origin'] = 'different'
        with self.assertRaises(ValueError):
            self.store.start(changed)
        self.assertEqual(before, self.store.status('run'))

    def test_attempt_budget(self):
        self.start()
        for _ in range(3):
            status = self.store.fail('run', 'build', 'local', 'retry')
        self.assertEqual(status['steps'][0]['attempts'], 3)
        self.store.approve('run', 'build', 'local')
        with self.assertRaises(ValueError):
            self.build()
        with self.assertRaises(ValueError):
            self.store.fail('run', 'build', 'local', 'retry')

    def test_resume_and_evidence_invalidation(self):
        self.start()
        self.build()
        self.store.complete('run', 'review', 'local', {}, [str(self.file)])
        with Store(self.path) as reopened:
            self.assertTrue(reopened.status('run')['complete'])
            self.file.write_text('changed')
            result = reopened.status('run')
            self.assertFalse(result['complete'])
            self.assertEqual([s['state'] for s in result['steps']], ['pending', 'pending'])
        self.assertFalse(self.store.status('run')['complete'])

    def test_invalid_evidence_and_corrupt_state_fail_closed(self):
        self.start()
        self.store.approve('run', 'build', 'local')
        before = self.store.status('run')
        for files in [[], [self.tmp.name], ['missing'], [str(self.file), str(self.file)]]:
            with self.assertRaises(ValueError):
                self.store.complete('run', 'build', 'local', {'tested': True}, files)
        self.assertEqual(before, self.store.status('run'))
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE runs SET snapshot = '{}' WHERE id = 'run'")
        with self.assertRaises(ValueError):
            self.store.status('run')


if __name__ == '__main__':
    unittest.main()
