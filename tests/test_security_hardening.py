"""Deployment-grade hardening: the three defects the security pass found, each with its attack.

These are adversarial tests. Each one performs the attack and asserts the system fails safely, so
removing a guard makes the attack succeed and the test fail for the reason it was written.
"""

import io
import os
import sys
import threading

import pytest

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, os.path.join(ROOT, 'server'))

import auth                                        # noqa: E402
import kiwi                                        # noqa: E402
import live                                        # noqa: E402
from test_auth_api import call                     # noqa: E402


@pytest.fixture(scope='module')
def strict_server():
    """A server with a tight login limiter, which is what the forwarded-header attack targets."""
    os.environ['ICHNOVA_SECRET_KEY'] = 'test-signing-key'
    os.environ['ICHNOVA_DEMO_PASSWORD_ANALYST'] = 'demo-analyst-password'
    sys.modules.pop('app', None)
    import app
    app.LIMITER = auth.RateLimiter(limits={'auth': (3, 60), 'default': (2000, 60)})
    app.TRUSTED_PROXIES = set()
    httpd = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f'http://127.0.0.1:{httpd.server_address[1]}', app
    httpd.shutdown()


def _login_attempts(base, n, forwarded=None):
    out = []
    for i in range(n):
        headers = {'X-Forwarded-For': forwarded(i)} if forwarded else None
        out.append(call(base, '/api/auth/login', method='POST', headers=headers,
                        body={'username': 'demo.analyst', 'password': f'guess-{i}'})[0])
    return out


# ------------------------------------------------------------------ forwarded headers
def test_a_spoofed_forwarded_header_cannot_buy_a_fresh_rate_limit_bucket(strict_server):
    """The attack: one client, a new X-Forwarded-For per request, unlimited password guesses.

    Anyone can send this header. Believing it without knowing a proxy sent it turns the per-client
    limiter into no limiter at all, and it matters most on /api/auth/login, where it removes the
    only brute-force defence the server has.
    """
    base, app = strict_server
    app.LIMITER = auth.RateLimiter(limits={'auth': (3, 60), 'default': (2000, 60)})
    codes = _login_attempts(base, 8, forwarded=lambda i: f'203.0.113.{i}')
    assert 429 in codes, 'a spoofed X-Forwarded-For bought an unlimited number of guesses'
    assert codes.index(429) <= 4, codes


def test_a_trusted_proxy_may_still_name_the_client(strict_server):
    """The fix must not break the deployment it exists for: behind the proxy in deploy/, two real
    clients must still get one bucket each rather than sharing the proxy's."""
    base, app = strict_server
    app.LIMITER = auth.RateLimiter(limits={'auth': (3, 60), 'default': (2000, 60)})
    app.TRUSTED_PROXIES = {'127.0.0.1'}
    try:
        first = _login_attempts(base, 3, forwarded=lambda i: '198.51.100.7')
        second = _login_attempts(base, 3, forwarded=lambda i: '198.51.100.8')
        assert 429 not in first + second, (first, second)
        assert 429 in _login_attempts(base, 2, forwarded=lambda i: '198.51.100.7')
    finally:
        app.TRUSTED_PROXIES = set()


def test_the_rightmost_hop_wins_so_a_client_cannot_prepend_a_lie(strict_server):
    """The proxy appends the address it saw, so the last entry is the trustworthy one. Taking the
    first would let a client choose its own identity inside a header it is allowed to send."""
    base, app = strict_server
    app.LIMITER = auth.RateLimiter(limits={'auth': (3, 60), 'default': (2000, 60)})
    app.TRUSTED_PROXIES = {'127.0.0.1'}
    try:
        codes = _login_attempts(base, 8, forwarded=lambda i: f'203.0.113.{i}, 198.51.100.9')
        assert 429 in codes, 'a client-supplied leading hop was believed over the proxy entry'
    finally:
        app.TRUSTED_PROXIES = set()


# ------------------------------------------------------------------ token leakage
def test_a_session_token_never_reaches_the_log(strict_server):
    """EventSource cannot set an Authorization header, so /api/live/events carries the token in the
    query string. The access log must not then record live credentials."""
    base, app = strict_server
    app.LIMITER = auth.RateLimiter(limits={'auth': (200, 60), 'default': (2000, 60)})
    token = call(base, '/api/auth/demo', method='POST', body={'username': 'demo.viewer'})[1]['token']
    captured, real = io.StringIO(), sys.stderr
    sys.stderr = captured
    try:
        call(base, f'/api/live/events?session=NOPE&token={token}')
    finally:
        sys.stderr = real
    logged = captured.getvalue()
    assert 'token=<redacted>' in logged, logged
    assert token not in logged, 'the session token was written to the log verbatim'


# ------------------------------------------------------------------ server-side request forgery
DIRECTORY = [{'url': 'kiwi.example.org:8073', 'name': 'listed', 'loc': 'Chennai',
              'gps': '(13.08, 80.27)', 'users': 0, 'users_max': 4, 'bands': '0-30000'}]


@pytest.fixture
def offline_directory(monkeypatch):
    monkeypatch.setattr(live, 'directory_cached', lambda: DIRECTORY)
    monkeypatch.setattr(kiwi, 'rank_receivers',
                        lambda directory, *a, **k: [{'url': d['url'], 'name': d.get('name', ''),
                                                     'loc': d.get('loc', ''), 'gps': None,
                                                     'distance_km': 10.0, 'gps_timed': None,
                                                     'snr_db': None} for d in directory])
    return DIRECTORY


@pytest.mark.parametrize('hostile', [
    '127.0.0.1:8765',                       # the analysis server itself
    'localhost:22',                         # an internal service, used as a port oracle
    '169.254.169.254:80',                   # cloud instance metadata
    '10.0.0.5:8073',                        # a private network address
    'attacker.example.com:8073',            # an exfiltration target
])
def test_an_unlisted_receiver_is_never_contacted(offline_directory, hostile):
    """The attack: POST /api/live/start?receiver=<any host:port>.

    The operator-supplied receiver used to be dialled directly, and the per-receiver failure was
    streamed back over SSE, so the caller learned whether each host and port was open: a server-side
    request forgery with an oracle attached. Only a receiver the public directory lists may be named.
    """
    session = live.Session('JJY', 'iq', 1, receiver=hostile)
    with pytest.raises(kiwi.KiwiError) as e:
        session._receivers()
    assert 'public receiver directory' in str(e.value)


def test_a_listed_receiver_is_still_honoured_and_goes_first(offline_directory):
    session = live.Session('JJY', 'iq', 1, receiver='kiwi.example.org:8073')
    assert session._receivers()[0]['url'] == 'kiwi.example.org:8073'


def test_leaving_the_choice_to_the_server_still_works(offline_directory):
    assert live.Session('JJY', 'iq', 1)._receivers()[0]['url'] == 'kiwi.example.org:8073'
