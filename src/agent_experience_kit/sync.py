"""Explicit bounded outbox delivery; no retries or credential-bearing redirects."""
import ipaddress
import json
import math
import urllib.request
from urllib.parse import urlsplit


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def sync_once(store, url, token, limit=100, timeout=10):
    """Send one batch and acknowledge only a complete, exact server response."""
    if not isinstance(url, str):
        raise ValueError('hub URL must be a string')
    parsed = urlsplit(url)
    if (not parsed.hostname or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment or parsed.path not in ('', '/')):
        raise ValueError('hub URL must be a base origin without credentials, query or fragment')
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError('invalid hub port') from exc
    try:
        loopback = parsed.hostname == 'localhost' or ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        loopback = parsed.hostname == 'localhost'
    if parsed.scheme != 'https' and not (parsed.scheme == 'http' and loopback):
        raise ValueError('hub requires HTTPS or explicit loopback HTTP')
    if not isinstance(token, str) or not token.strip() or '\n' in token or '\r' in token:
        raise ValueError('token must be a nonempty single line')
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('timeout must be a positive finite number')
    events = store.pending_events(limit)
    if not events:
        return {'sent': 0, 'accepted': 0, 'duplicates': 0, 'pending': store.pending_count()}
    request = urllib.request.Request(url.rstrip('/') + '/api/ingest',
        data=json.dumps({'events': events}).encode('utf-8'),
        headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}, method='POST')
    opener = urllib.request.build_opener(_NoRedirect())
    with opener.open(request, timeout=timeout) as response:
        if not 200 <= response.status < 300:
            raise ValueError('hub did not accept batch')
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError('hub response too large')
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise ValueError('invalid hub JSON response') from exc
    if not isinstance(result, dict) or set(result) != {'accepted', 'duplicates'}:
        raise ValueError('invalid acknowledgement response')
    accepted, duplicates = result['accepted'], result['duplicates']
    if any(not isinstance(group, list) or any(not isinstance(v, str) for v in group)
           for group in (accepted, duplicates)):
        raise ValueError('acknowledgements must contain event ids')
    ids = accepted + duplicates
    if len(set(ids)) != len(ids) or set(ids) != {e['id'] for e in events}:
        raise ValueError('acknowledgements must match submitted ids exactly')
    store.ack_events(ids)
    return {'sent': len(events), 'accepted': len(accepted), 'duplicates': len(duplicates),
            'pending': store.pending_count()}
