import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class CLITest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / 'state.db'

    def write(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value), encoding='utf-8')
        return str(path)

    def invoke(self, *args):
        env = dict(os.environ)
        env['PYTHONPATH'] = str(Path(__file__).resolve().parents[1] / 'src')
        return subprocess.run([sys.executable, '-m', 'agent_experience_kit', *map(str, args)],
                              cwd=self.root, env=env, text=True, capture_output=True)

    def test_restart_dependency_and_artifact_mutation_journey(self):
        contract = self.write('task.json', {'id': 'demo', 'origin': 'local:demo', 'steps': [
            {'id': 'build', 'required_checks': ['rendered']},
            {'id': 'verify', 'depends_on': ['build'], 'required_checks': ['reviewed']} ]})
        artifact = self.root / 'result.txt'
        artifact.write_text('ready')
        checks = self.write('checks.json', {'rendered': True, 'reviewed': True})
        self.assertEqual(self.invoke('start', contract, '--db', self.db).returncode, 0)
        before = self.invoke('complete', 'demo', 'verify', '--origin', 'local:demo',
                             '--checks', checks, '--artifact', artifact, '--db', self.db)
        self.assertEqual(before.returncode, 2, before.stderr)
        for step in ['build', 'verify']:
            result = self.invoke('complete', 'demo', step, '--origin', 'local:demo',
                                 '--checks', checks, '--artifact', artifact, '--db', self.db)
            self.assertEqual(result.returncode, 0, result.stderr)
        status = self.invoke('status', 'demo', '--db', self.db)
        self.assertTrue(json.loads(status.stdout)['complete'])
        artifact.write_text('changed after approval')
        status = self.invoke('status', 'demo', '--db', self.db)
        self.assertFalse(json.loads(status.stdout)['complete'])

    def test_failed_review_exits_one_and_emits_reasons(self):
        report = self.write('review.json', {'builder': 'producer', 'reviewer': 'reviewer',
            'declared_pass': True, 'required_checks': ['captions'], 'checks': {'captions': True},
            'defects': [{'severity': 'critical', 'description': 'Speech has no matching mouth movement'}]})
        result = self.invoke('review', report)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse(json.loads(result.stdout)['passed'])

    def test_malformed_input_has_concise_error(self):
        result = self.invoke('review', self.write('bad.json', []))
        self.assertEqual(result.returncode, 2)
        self.assertNotIn('Traceback', result.stderr)

    def test_export_refuses_private_lesson_without_creating_output(self):
        lesson = {'id': 'example', 'category': 'qa', 'failure': 'A check was skipped',
                  'correction': 'Require the check', 'acceptance_criteria': ['Check passes'],
                  'evidence_level': 'synthetic', 'provenance': 'synthetic_example',
                  'visibility': 'private', 'reviewed_for_public': False}
        output = self.root / 'public.json'
        result = self.invoke('lessons', 'export', self.write('lessons.json', [lesson]), '--output', output)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(output.exists())

    def test_export_does_not_overwrite_existing_file(self):
        output = self.root / 'public.json'
        output.write_text('keep')
        result = self.invoke('lessons', 'export', self.write('lessons.json', []), '--output', output)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(output.read_text(), 'keep')

    def test_unknown_run_does_not_print_traceback(self):
        result = self.invoke('status', 'missing', '--db', self.db)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
