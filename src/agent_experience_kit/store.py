"""Transactional local checkpoints with explicit evidence gates."""
import hashlib
import json
import os
import stat
import sqlite3
import uuid
from datetime import datetime, timezone

from .qa import evaluate_review
from contextlib import contextmanager
from functools import wraps
from pathlib import Path


def _name(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{label} must be a nonempty string')
    return value


def _names(value, label):
    if not isinstance(value, list):
        raise ValueError(f'{label} must be a list')
    result = [_name(item, label) for item in value]
    if len(set(result)) != len(result):
        raise ValueError(f'{label} contains duplicates')
    return result


def validate_contract(contract):
    """Return a detached, normalized contract, rejecting invalid DAGs."""
    if not isinstance(contract, dict):
        raise ValueError('contract must be an object')
    result = {key: _name(contract.get(key), key) for key in ('id', 'origin')}
    steps = contract.get('steps')
    if not isinstance(steps, list) or not steps:
        raise ValueError('steps must be a nonempty list')
    normalized = []
    for step in steps:
        if not isinstance(step, dict):
            raise ValueError('step must be an object')
        item = {'id': _name(step.get('id'), 'step id')}
        for key in ('depends_on', 'required_checks'):
            item[key] = _names(step.get(key, []), key)
        for key, default, minimum in [('min_artifacts', 1, 0), ('max_attempts', 3, 1)]:
            value = step.get(key, default)
            if type(value) is not int or value < minimum:
                raise ValueError(f'{key} must be an integer >= {minimum}')
            item[key] = value
        approval = step.get('requires_approval', False)
        if type(approval) is not bool:
            raise ValueError('requires_approval must be boolean')
        item['requires_approval'] = approval
        normalized.append(item)
    by_id = {step['id']: step for step in normalized}
    if len(by_id) != len(normalized):
        raise ValueError('duplicate step id')
    dependents = {identifier: [] for identifier in by_id}
    remaining = {}
    for identifier, step in by_id.items():
        remaining[identifier] = len(step['depends_on'])
        for dependency in step['depends_on']:
            if dependency not in by_id:
                raise ValueError('unknown dependency')
            dependents[dependency].append(identifier)
    ready = [identifier for identifier, count in remaining.items() if count == 0]
    visited = 0
    while ready:
        identifier = ready.pop()
        visited += 1
        for dependent in dependents[identifier]:
            remaining[dependent] -= 1
            if remaining[dependent] == 0:
                ready.append(dependent)
    if visited != len(by_id):
        raise ValueError('dependency cycle')
    result['steps'] = normalized
    return result


def _evidence(paths):
    paths = _names(paths, 'artifacts')
    result = []
    try:
        for raw in paths:
            path = Path(raw).resolve(strict=True)
            descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_BINARY', 0))
            with os.fdopen(descriptor, 'rb') as source:
                if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                    raise ValueError('artifact must be a regular file')
                digest = hashlib.sha256()
                for chunk in iter(lambda: source.read(1024 * 1024), b''):
                    digest.update(chunk)
            result.append({'path': str(path), 'sha256': digest.hexdigest()})
    except (OSError, RuntimeError) as exc:
        raise ValueError(f'cannot read artifact: {exc}') from exc
    if len({item['path'] for item in result}) != len(result):
        raise ValueError('duplicate artifact')
    return result


def _audit_gate(operation):
    """Persist a normalized rejection only after the operation has rolled back."""
    @wraps(operation)
    def audited(self, run_id, step_id, origin, *args, **kwargs):
        try:
            return operation(self, run_id, step_id, origin, *args, **kwargs)
        except ValueError as error:
            codes = {
                'required checks must pass': 'checks_failed',
                'checks must map names to booleans': 'invalid_checks',
                'insufficient artifacts': 'insufficient_artifacts',
                'dependencies must be complete': 'dependencies_incomplete',
                'approval required': 'approval_required',
                'attempt budget exhausted': 'attempt_budget_exhausted',
                'completed evidence differs': 'evidence_conflict',
                'completed step cannot fail': 'completed_step',
            }
            # Do not publish operations attributed to another local origin.
            try:
                with self._transaction():
                    contract, steps = self._load(run_id)
                    if origin == contract['origin']:
                        self._queue_event(contract, steps, 'gate_rejected',
                                          failure_code=codes.get(str(error), 'gate_rejected'))
            except (ValueError, sqlite3.Error):
                # Rejection auditing must preserve the original business error.
                pass
            raise
    return audited


class Store:
    """SQLite-backed runs; each operation serializes writers before reading."""
    def __init__(self, path):
        if str(path) != ':memory:':
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, timeout=30, isolation_level=None)
        self.connection.execute('CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, contract TEXT NOT NULL, snapshot TEXT NOT NULL)')
        self.connection.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        self.connection.execute('CREATE TABLE IF NOT EXISTS outbox (sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, run_id TEXT NOT NULL, payload TEXT NOT NULL, delivered INTEGER NOT NULL DEFAULT 0)')
        with self._transaction():
            self.connection.execute("INSERT OR IGNORE INTO metadata VALUES ('producer_id', ?)", (str(uuid.uuid4()),))
            self.producer_id = self.connection.execute("SELECT value FROM metadata WHERE key = 'producer_id'").fetchone()[0]


    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @contextmanager
    def _transaction(self):
        self.connection.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.connection.execute('COMMIT')
        except BaseException:
            self.connection.execute('ROLLBACK')
            raise

    def _save(self, contract, steps):
        self.connection.execute('UPDATE runs SET snapshot = ? WHERE id = ?', (json.dumps(steps), contract['id']))

    def _load(self, run_id):
        _name(run_id, 'run id')
        row = self.connection.execute('SELECT contract, snapshot FROM runs WHERE id = ?', (run_id,)).fetchone()
        if row is None:
            raise ValueError('unknown run')
        try:
            contract = validate_contract(json.loads(row[0]))
            steps = json.loads(row[1])
            if contract['id'] != run_id or not isinstance(steps, list) or len(steps) != len(contract['steps']):
                raise ValueError('invalid checkpoint')
            for spec, step in zip(contract['steps'], steps):
                if not isinstance(step, dict) or step.get('id') != spec['id'] or step.get('state') not in ('pending', 'failed', 'done'):
                    raise ValueError('invalid checkpoint step')
                if type(step.get('attempts')) is not int or not 0 <= step['attempts'] <= spec['max_attempts'] or type(step.get('approved')) is not bool:
                    raise ValueError('invalid checkpoint counters')
                if not isinstance(step.get('artifacts'), list) or not isinstance(step.get('checks'), dict):
                    raise ValueError('invalid checkpoint evidence')
                if step['state'] == 'done':
                    if step['attempts'] < 1 or (spec['requires_approval'] and not step['approved']) or len(step['artifacts']) < spec['min_artifacts'] or any(step['checks'].get(key) is not True for key in spec['required_checks']):
                        raise ValueError('invalid completed checkpoint')
                    for evidence in step['artifacts']:
                        if not isinstance(evidence, dict) or not isinstance(evidence.get('path'), str) or not Path(evidence['path']).is_absolute() or not isinstance(evidence.get('sha256'), str) or len(evidence['sha256']) != 64:
                            raise ValueError('invalid checkpoint hash')
            by_id = {step['id']: step for step in steps}
            for spec, step in zip(contract['steps'], steps):
                if step['state'] == 'done' and any(by_id[dep]['state'] != 'done' for dep in spec['depends_on']):
                    raise ValueError('invalid completed dependency')
            return contract, steps
        except (TypeError, KeyError, json.JSONDecodeError) as exc:
            raise ValueError('corrupt checkpoint') from exc

    def _refresh(self, contract, steps):
        invalid = set()
        for step in steps:
            if step['state'] == 'done':
                try:
                    current = _evidence([item['path'] for item in step['artifacts']])
                    if current != step['artifacts']:
                        invalid.add(step['id'])
                except ValueError:
                    invalid.add(step['id'])
        for _ in steps:
            for spec in contract['steps']:
                if any(dep in invalid for dep in spec['depends_on']):
                    invalid.add(spec['id'])
        for step in steps:
            if step['id'] in invalid:
                step.update(state='pending', artifacts=[], checks={}, approved=False)
        self._save(contract, steps)
        if invalid:
            self._queue_event(contract, steps, 'evidence_invalidated')

    @staticmethod
    def _status(contract, steps):
        return {'id': contract['id'], 'origin': contract['origin'], 'complete': all(step['state'] == 'done' for step in steps), 'steps': steps}

    def start(self, contract):
        contract = validate_contract(contract)
        with self._transaction():
            row = self.connection.execute('SELECT contract FROM runs WHERE id = ?', (contract['id'],)).fetchone()
            if row:
                if json.loads(row[0]) != contract:
                    raise ValueError('run already exists with a different contract')
                contract, steps = self._load(contract['id'])
                self._refresh(contract, steps)
            else:
                steps = [{'id': spec['id'], 'state': 'pending', 'attempts': 0, 'approved': False, 'checks': {}, 'artifacts': [], 'reason': None} for spec in contract['steps']]
                self.connection.execute('INSERT INTO runs VALUES (?, ?, ?)', (contract['id'], json.dumps(contract), json.dumps(steps)))
                self._queue_event(contract, steps, 'run_started')
            return self._status(contract, steps)

    def status(self, run_id):
        with self._transaction():
            contract, steps = self._load(run_id)
            self._refresh(contract, steps)
            return self._status(contract, steps)

    def _target(self, run_id, step_id, origin):
        contract, steps = self._load(run_id)
        if origin != contract['origin']:
            raise ValueError('origin mismatch')
        _name(step_id, 'step id')
        for spec, step in zip(contract['steps'], steps):
            if step['id'] == step_id:
                return contract, steps, spec, step
        raise ValueError('unknown step')

    @_audit_gate
    def approve(self, run_id, step_id, origin):
        with self._transaction():
            contract, steps, spec, step = self._target(run_id, step_id, origin)
            self._refresh(contract, steps)
            if not step['approved']:
                step['approved'] = True
                self._save(contract, steps)
                self._queue_event(contract, steps, 'step_approved')
            return self._status(contract, steps)

    @_audit_gate
    def complete(self, run_id, step_id, origin, checks, artifacts):
        with self._transaction():
            contract, steps, spec, step = self._target(run_id, step_id, origin)
            self._refresh(contract, steps)
            if not isinstance(checks, dict) or any(not isinstance(key, str) or type(value) is not bool for key, value in checks.items()):
                raise ValueError('checks must map names to booleans')
            if any(checks.get(key) is not True for key in spec['required_checks']):
                raise ValueError('required checks must pass')
            evidence = _evidence(artifacts)
            if len(evidence) < spec['min_artifacts']:
                raise ValueError('insufficient artifacts')
            by_id = {item['id']: item for item in steps}
            if any(by_id[dep]['state'] != 'done' for dep in spec['depends_on']):
                raise ValueError('dependencies must be complete')
            if spec['requires_approval'] and not step['approved']:
                raise ValueError('approval required')
            if step['state'] == 'done':
                if step['artifacts'] != evidence or step['checks'] != checks:
                    raise ValueError('completed evidence differs')
            else:
                if step['attempts'] >= spec['max_attempts']:
                    raise ValueError('attempt budget exhausted')
                step.update(state='done', attempts=step['attempts'] + 1, checks=checks, artifacts=evidence, reason=None)
                self._save(contract, steps)
                self._queue_event(contract, steps, 'step_completed')
            return self._status(contract, steps)

    @_audit_gate
    def fail(self, run_id, step_id, origin, reason):
        _name(reason, 'reason')
        with self._transaction():
            contract, steps, spec, step = self._target(run_id, step_id, origin)
            self._refresh(contract, steps)
            if step['state'] == 'done':
                raise ValueError('completed step cannot fail')
            if step['attempts'] >= spec['max_attempts']:
                raise ValueError('attempt budget exhausted')
            step.update(state='failed', attempts=step['attempts'] + 1, reason=reason)
            self._save(contract, steps)
            self._queue_event(contract, steps, 'step_failed', failure_code='external_failure')
            return self._status(contract, steps)

    def _queue_event(self, contract, steps, kind, **extra):
        status = ('completed' if all(s['state'] == 'done' for s in steps) else
                  'failed' if any(s['state'] == 'failed' for s in steps) else
                  'running' if any(s['attempts'] for s in steps) else 'pending')
        payload = {'status': status, 'steps': [
            {'id': s['id'], 'state': s['state'], 'attempts': s['attempts'],
             'approved': s['approved'], 'checks': dict(s['checks']),
             'artifact_hashes': [a['sha256'] for a in s['artifacts']]}
            for s in steps]}
        payload.update(extra)
        event = {'id': str(uuid.uuid4()), 'producer_id': self.producer_id,
                 'run_id': contract['id'], 'kind': kind,
                 'occurred_at': datetime.now(timezone.utc).isoformat(), 'payload': payload}
        cursor = self.connection.execute('INSERT INTO outbox (id, run_id, payload) VALUES (?, ?, ?)',
                                         (event['id'], contract['id'], '{}'))
        event['sequence'] = cursor.lastrowid
        self.connection.execute('UPDATE outbox SET payload = ? WHERE id = ?', (json.dumps(event), event['id']))

    def pending_events(self, limit=100):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('limit must be between 1 and 100')
        return [json.loads(row[0]) for row in self.connection.execute(
            'SELECT payload FROM outbox WHERE delivered = 0 ORDER BY sequence LIMIT ?', (limit,))]

    def ack_events(self, ids):
        if not isinstance(ids, list) or any(not isinstance(v, str) for v in ids) or len(set(ids)) != len(ids):
            raise ValueError('acknowledgements must be unique event ids')
        with self._transaction():
            for identifier in ids:
                if self.connection.execute('SELECT 1 FROM outbox WHERE id = ?', (identifier,)).fetchone() is None:
                    raise ValueError('unknown local event id')
            self.connection.executemany('UPDATE outbox SET delivered = 1 WHERE id = ?', [(v,) for v in ids])

    def pending_count(self):
        return self.connection.execute('SELECT COUNT(*) FROM outbox WHERE delivered = 0').fetchone()[0]

    def snapshot_existing(self):
        with self._transaction():
            ids = [r[0] for r in self.connection.execute(
                'SELECT id FROM runs WHERE NOT EXISTS (SELECT 1 FROM outbox WHERE outbox.run_id = runs.id)')]
            for run_id in ids:
                contract, steps = self._load(run_id)
                self._refresh(contract, steps)
                self._queue_event(contract, steps, 'snapshot_imported')
            return len(ids)

    def record_review(self, run_id, report):
        verdict = evaluate_review(report)
        counts = {severity: sum(d['severity'] == severity for d in report['defects'])
                  for severity in ('critical', 'major', 'minor')}
        with self._transaction():
            contract, steps = self._load(run_id)
            self._refresh(contract, steps)
            extra = {'qa': {'passed': verdict['passed'], 'checks': dict(report['checks']), 'defect_counts': counts}}
            if not verdict['passed']:
                extra['failure_code'] = 'qa_failed'
            self._queue_event(contract, steps, 'qa_reviewed', **extra)
        return verdict
