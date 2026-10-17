import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from agent_experience_kit.store import Store
try:
    from agent_experience_kit.sync import sync_once
except ImportError:
    sync_once = None


class Response:
    status = 200
    def __init__(self, value):
        self.value = value
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def read(self, size=-1):
        return self.value


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(sync_once, 'sync_once implementation required')
        self.store = Store(':memory:')
        self.addCleanup(self.store.close)
        self.store.start({'id': 'run', 'origin': 'private', 'steps': [{'id': 'build'}]})
        self.ids = [e['id'] for e in self.store.pending_events()]

    def test_ack_and_duplicate_retry(self):
        with patch('urllib.request.OpenerDirector.open', return_value=Response(json.dumps({'accepted': [], 'duplicates': self.ids}).encode())) as opened:
            result = sync_once(self.store, 'http://127.0.0.1:8787', 'secret')
        self.assertEqual(result, {'sent': 1, 'accepted': 0, 'duplicates': 1, 'pending': 0})
        request = opened.call_args.args[0]
        self.assertEqual(request.full_url, 'http://127.0.0.1:8787/api/ingest')
        self.assertEqual(request.get_header('Authorization'), 'Bearer secret')

    def test_bad_ack_and_transport_failures_preserve_queue(self):
        for value in [b'bad json', b'{"accepted":[],"duplicates":[]}',
                      b'{"accepted":["foreign"],"duplicates":[]}',
                      json.dumps({'accepted': self.ids, 'duplicates': self.ids}).encode()]:
            with patch('urllib.request.OpenerDirector.open', return_value=Response(value)):
                with self.assertRaises(ValueError):
                    sync_once(self.store, 'https://example.test', 'secret')
            self.assertEqual(len(self.store.pending_events()), 1)
        with patch('urllib.request.OpenerDirector.open', side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):
                sync_once(self.store, 'https://example.test', 'secret')
        self.assertEqual(len(self.store.pending_events()), 1)

    def test_reject_unsafe_urls_before_network(self):
        for url in ['http://example.com', 'https://user:pass@example.com', 'https://example.com?x=1',
                    'https://example.com#x', 'https://example.com/path', 'ftp://example.com', 'https://example.com:bad']:
            with patch('urllib.request.OpenerDirector.open') as opened:
                with self.assertRaises(ValueError):
                    sync_once(self.store, url, 'secret')
                opened.assert_not_called()

    def test_redirect_never_forwarded(self):
        from agent_experience_kit.sync import _NoRedirect
        handler = _NoRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 302, 'redirect', {}, 'https://other.test'))
