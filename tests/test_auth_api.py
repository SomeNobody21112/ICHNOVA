"""Authentication, authorisation, rate limiting and API hardening (Constitution v2.5 §25.8).

Every test drives the real HTTP server rather than calling handler functions, so the checks cover
what a client can actually reach.
"""

import io
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
import wave

import numpy as np
import pytest

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, os.path.join(ROOT, 'server'))

import auth                                        # noqa: E402


# ---------------------------------------------------------------- password and session units
def test_password_hash_is_scrypt_and_never_plaintext():
    h = auth.hash_password('a-long-enough-password')
    assert h.startswith('scrypt$') and 'a-long-enough-password' not in h
    assert auth.verify_password('a-long-enough-password', h)
    assert not auth.verify_password('a-long-enough-passworD', h)
    assert auth.hash_password('a-long-enough-password') != h          # per-password salt


def test_short_password_rejected():
    with pytest.raises(ValueError):
        auth.hash_password('short')


def test_session_token_expiry_forgery_and_revocation():
    s = auth.Sessions(secret=b'unit-test-key', ttl=1)
    user = {'username': 'u', 'role': 'ANALYST', 'name': 'U', 'station': None, 'demo': False}
    token, payload = s.issue(user)
    assert s.verify(token)['role'] == 'ANALYST'
    raw, sig = token.split('.')
    assert s.verify(raw + '.' + sig[:-2] + 'xy') is None               # tampered signature
    other = auth.Sessions(secret=b'another-key', ttl=60)
    assert other.verify(token) is None                                 # signed by a different key
    assert s.revoke(token) and s.verify(token) is None                 # logout
    token2, _ = s.issue(user)
    time.sleep(1.1)
    assert s.verify(token2) is None                                    # expired
    assert payload['exp'] > payload['iat']


def test_roles_map_to_real_permissions():
    assert auth.allowed('ANALYST', 'analyse') and not auth.allowed('VIEWER', 'analyse')
    assert auth.allowed('REVIEWER', 'review') and not auth.allowed('VIEWER', 'review')
    assert auth.allowed('ADMIN', 'admin') and not auth.allowed('ANALYST', 'admin')
    assert all(auth.allowed(r, 'read') for r in auth.ROLES)


def test_rate_limiter_window():
    rl = auth.RateLimiter(limits={'auth': (2, 60), 'default': (100, 60)})
    assert rl.check('1.2.3.4', 'auth')[0] and rl.check('1.2.3.4', 'auth')[0]
    ok, retry = rl.check('1.2.3.4', 'auth')
    assert not ok and 0 <= retry <= 60
    assert rl.check('5.6.7.8', 'auth')[0]                              # per client


# ---------------------------------------------------------------- live server
@pytest.fixture(scope='module')
def server():
    os.environ['ICHNOVA_SECRET_KEY'] = 'test-signing-key'
    os.environ['ICHNOVA_DEMO_PASSWORD_ANALYST'] = 'demo-analyst-password'
    sys.modules.pop('app', None)
    import app
    app.LIMITER = auth.RateLimiter(limits={'auth': (200, 60), 'analyse': (200, 60),
                                           'live': (200, 60), 'default': (2000, 60)})
    httpd = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f'http://127.0.0.1:{httpd.server_address[1]}', app
    httpd.shutdown()


def call(base, path, *, method='GET', token=None, body=None, raw=None, headers=None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(base + path, data=data, method=method)
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read() or b'{}'), dict(r.headers)
    except urllib.error.HTTPError as e:
        payload = e.read()
        try:
            payload = json.loads(payload or b'{}')
        except Exception:
            payload = {'raw': payload[:120].decode('utf-8', 'replace')}
        return e.code, payload, dict(e.headers)


def login(base, username='demo.analyst', password='demo-analyst-password'):
    status, body, _ = call(base, '/api/auth/login', method='POST',
                           body={'username': username, 'password': password})
    assert status == 200, body
    return body['token']


def iq_bytes(n=600):
    rng = np.random.default_rng(0)
    out = np.empty(2 * n, dtype=np.float32)
    out[0::2], out[1::2] = rng.standard_normal(n), rng.standard_normal(n)
    return out.tobytes()


def test_unauthenticated_api_is_refused(server):
    base, _ = server
    for path in ('/api/live/stations', '/api/live/sessions', '/api/auth/me'):
        status, body, _ = call(base, path)
        assert status == 401 and 'error' in body, (path, status)
    status, _, _ = call(base, '/api/analyze?format=iq', method='POST', raw=iq_bytes())
    assert status == 401


def test_health_and_demo_catalogue_are_public_but_leak_nothing(server):
    base, _ = server
    status, body, _ = call(base, '/api/health')
    assert status == 200 and body['status'] == 'ready'
    status, body, _ = call(base, '/api/auth/accounts')
    assert status == 200 and body['auth_required'] is True
    assert {a['role'] for a in body['demo_accounts']} == {'ANALYST', 'REVIEWER', 'VIEWER'}
    assert 'ADMIN' not in {a['role'] for a in body['demo_accounts']}   # demo accounts are not admins
    assert 'password' not in json.dumps(body).lower()


def test_login_rejects_bad_credentials_without_saying_which(server):
    base, _ = server
    s1, b1, _ = call(base, '/api/auth/login', method='POST',
                     body={'username': 'demo.analyst', 'password': 'wrong'})
    s2, b2, _ = call(base, '/api/auth/login', method='POST',
                     body={'username': 'nobody', 'password': 'wrong'})
    assert s1 == s2 == 401 and b1['error'] == b2['error']


def test_login_then_protected_call_then_logout(server):
    base, _ = server
    token = login(base)
    status, body, _ = call(base, '/api/auth/me', token=token)
    assert status == 200 and body['user']['role'] == 'ANALYST'
    assert call(base, '/api/live/stations', token=token)[0] == 200
    assert call(base, '/api/auth/logout', method='POST', token=token)[1]['revoked'] is True
    assert call(base, '/api/auth/me', token=token)[0] == 401           # revoked token is dead


def test_demo_signin_never_returns_a_password(server):
    base, _ = server
    status, body, _ = call(base, '/api/auth/demo', method='POST', body={'username': 'demo.viewer'})
    assert status == 200 and body['user']['demo'] is True and 'password' not in json.dumps(body)
    assert call(base, '/api/auth/demo', method='POST', body={'username': 'demo.analyst'})[0] == 200
    assert call(base, '/api/auth/demo', method='POST', body={'username': 'nobody'})[0] == 404


def test_role_separation_is_enforced_by_the_api(server):
    base, _ = server
    viewer = call(base, '/api/auth/demo', method='POST', body={'username': 'demo.viewer'})[1]['token']
    status, body, _ = call(base, '/api/analyze?format=iq', method='POST', token=viewer, raw=iq_bytes())
    assert status == 403 and 'VIEWER' in body['error']
    assert call(base, '/api/live/start?station=JJY', method='POST', token=viewer)[0] == 403
    assert call(base, '/api/auth/users', token=viewer)[0] == 403        # no privilege escalation
    assert call(base, '/api/live/stations', token=viewer)[0] == 200     # reading is allowed
    analyst = login(base)
    assert call(base, '/api/auth/users', token=analyst)[0] == 403       # analyst is not an admin


def test_forged_and_malformed_tokens_are_refused(server):
    base, _ = server
    good = login(base)
    raw, sig = good.split('.')
    flipped = raw + '.' + sig[:-1] + ('A' if sig[-1] != 'A' else 'B')
    for bad in ('', 'x', 'a.b', flipped, raw + '.'):
        assert call(base, '/api/auth/me', token=bad)[0] == 401, bad


def test_no_single_character_change_to_a_signature_verifies():
    """Exhaustive, because a near-miss is exactly what a forger produces. The last base64 character
    carries four bits that decoding discards, so a signature compared as bytes rather than as the
    text it was issued as would accept three variants of every token."""
    sessions = auth.Sessions(secret=b'fixed-key-for-this-test')
    token, _ = sessions.issue({'username': 'u', 'role': 'ANALYST', 'name': 'U'})
    raw, sig = token.split('.')
    alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'
    accepted = [f'{sig[:i]}{c}{sig[i + 1:]}' for i in range(len(sig)) for c in alphabet
                if c != sig[i] and sessions.verify(f'{raw}.{sig[:i]}{c}{sig[i + 1:]}') is not None]
    assert accepted == []
    assert sessions.verify(token) is not None                          # and the real one still works


def test_upload_limits_and_malformed_input(server):
    base, _ = server
    token = login(base)
    # a declared length beyond the cap is refused before the body is read
    req = urllib.request.Request(base + '/api/analyze?format=iq', data=b'x' * 16, method='POST')
    req.add_header('Authorization', f'Bearer {token}')
    req.add_header('Content-Length', str(200 * 1024 * 1024))
    try:
        urllib.request.urlopen(req, timeout=30)
        raise AssertionError('oversized upload should be refused')
    except urllib.error.HTTPError as e:
        assert e.code == 413
    except (urllib.error.URLError, ConnectionError, BrokenPipeError):
        pass                                                            # refused at the socket, also fine
    assert call(base, '/api/analyze?format=iq', method='POST', token=token, raw=b'12345')[0] == 400
    assert call(base, '/api/analyze?format=iq', method='POST', token=token, raw=iq_bytes(8))[0] == 400
    assert call(base, '/api/analyze?format=wav', method='POST', token=token,
                raw=b'RIFFxxxxWAVEjunk')[0] in (400, 500)
    for fs in ('fast', '-1', '0', 'NaN', 'Infinity'):
        assert call(base, f'/api/analyze?format=iq&fs={fs}', method='POST', token=token,
                    raw=iq_bytes())[0] == 400, fs


def test_path_traversal_is_refused(server):
    base, _ = server
    token = login(base)
    for path in ('/api/recordings/..%2f..%2fserver%2fapp.py', '/api/recordings/%2e%2e%2fapp.py',
                 '/api/live/file/..%2f..%2fetc/capture.wav', '/api/live/session/..%2f..%2fapp.py'):
        status, _, _ = call(base, path, token=token)
        assert status in (400, 404), (path, status)


def test_security_headers_present(server):
    base, _ = server
    _, _, headers = call(base, '/api/health')
    assert "default-src 'self'" in headers.get('Content-Security-Policy', '')
    assert headers.get('X-Content-Type-Options') == 'nosniff'
    assert headers.get('Referrer-Policy') == 'no-referrer'
    assert headers.get('X-Frame-Options') == 'DENY'


def test_errors_do_not_leak_stack_traces(server):
    base, _ = server
    token = login(base)
    status, body, _ = call(base, '/api/analyze?format=wav', method='POST', token=token,
                           raw=b'RIFFxxxxWAVEjunk')
    text = json.dumps(body)
    assert 'Traceback' not in text and 'File "' not in text and status in (400, 500)


def test_rate_limit_returns_429_with_retry_after(server):
    base, app = server
    app.LIMITER = auth.RateLimiter(limits={'auth': (3, 60), 'default': (2000, 60)})
    try:
        codes = [call(base, '/api/auth/login', method='POST',
                      body={'username': 'x', 'password': 'y'})[0] for _ in range(6)]
        assert 429 in codes
        status, body, headers = call(base, '/api/auth/login', method='POST',
                                     body={'username': 'x', 'password': 'y'})
        assert status == 429 and 'Retry-After' in headers and body['retry_after_s'] >= 0
    finally:
        app.LIMITER = auth.RateLimiter(limits={'auth': (200, 60), 'analyse': (200, 60),
                                               'live': (200, 60), 'default': (2000, 60)})


def test_authorised_analysis_still_works(server):
    base, _ = server
    token = login(base)
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(48000)
        rng = np.random.default_rng(1)
        pcm = (rng.standard_normal(2 * 400) * 3000).astype(np.int16)
        w.writeframes(pcm.tobytes())
    status, pack, _ = call(base, '/api/analyze?format=wav&name=t.wav', method='POST',
                           token=token, raw=buf.getvalue())
    assert status == 200 and pack['result']['status'] in ('DECODED', 'SIGNAL_NO_CODE', 'UNKNOWN')
    assert pack['capture']['fs_source'] == 'wav_header'
