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


# ------------------------------------------------- memory limits (a 512 MB free-tier instance)
#
# `analyze_iq` needs ~674 bytes of transient memory per input sample, measured across 20k, 80k and
# 320k captures. On a 512 MB instance that number, not the byte count of the upload, is what decides
# whether a capture can be answered at all. Before these guards the only limit was a 64 MB byte cap:
# 64 MB of float32 I/Q is 8M samples, so the honest answer to a large upload was the platform killing
# the process. These tests assert the limits are consistent with each other and with the material the
# project actually ships.

ENGINE_BYTES_PER_SAMPLE = 674


def test_a_capture_too_large_for_the_instance_is_refused_and_never_truncated(strict_server):
    """The attack: an upload the instance cannot analyse, sent to make it die instead of answer.

    The refusal must also not be a silent truncation. Analysing a prefix would answer a different
    question from the one asked, which for an engine whose entire product is a defensible verdict is
    worse than refusing.
    """
    base, app = strict_server
    from test_auth_api import iq_bytes, login
    token = login(base)
    n = app.MAX_ANALYSIS_SAMPLES + 1
    status, body, _ = call(base, '/api/analyze?format=iq&fs=48000', method='POST',
                           token=token, raw=iq_bytes(n))
    assert status == 413, (status, body)
    assert str(n) in body['error'] and str(app.MAX_ANALYSIS_SAMPLES) in body['error']
    assert 'memory' in body['reason']
    # a refusal, not a quiet partial answer
    assert 'result' not in body and 'receipt' not in body


def test_the_byte_cap_can_never_be_what_rejects_an_analysable_capture(strict_server):
    """The two limits have to agree, or the error message lies about which one fired.

    Interleaved float32 I/Q is 8 bytes per sample and is the largest encoding accepted, so the byte
    cap must leave room for a full-size capture in it.
    """
    _, app = strict_server
    assert app.MAX_UPLOAD >= app.MAX_ANALYSIS_SAMPLES * 8, (
        'MAX_UPLOAD rejects captures the engine would otherwise accept, so the 413 would blame the '
        'wrong limit')
    # and the sample cap must fit the memory budget it was derived from, with headroom over the
    # ~100 MB the server is already resident before any analysis starts
    peak_mb = app.MAX_ANALYSIS_SAMPLES * ENGINE_BYTES_PER_SAMPLE / 2**20
    assert peak_mb + 100 < 512, f'a full-size analysis peaks at ~{peak_mb:.0f} MB and cannot fit 512 MB'


def test_every_recording_this_project_ships_still_fits_the_instance(strict_server):
    """A committed recording the deployed instance would refuse is a broken demo, not a safe limit.

    This fails if someone commits a longer recording without revisiting the budget, which is the
    mistake the cap could otherwise hide until a judge clicked it.
    """
    import wave
    _, app = strict_server
    real = os.path.join(ROOT, 'recordings', 'real')
    wavs = [f for f in os.listdir(real) if f.endswith('.wav')]
    assert wavs, 'no recordings found, so this test would pass by vacuum'
    for name in wavs:
        with wave.open(os.path.join(real, name)) as w:
            frames = w.getnframes()
        assert frames <= app.MAX_ANALYSIS_SAMPLES, (
            f'{name} has {frames} samples and the deployed instance would refuse it')


def test_the_compressed_static_cache_cannot_grow_without_bound(strict_server):
    """An unbounded cache in a long-lived process is a memory leak measured in uptime.

    dist/ holds ~14 MB of evidence JSON, so caching every compressed file forever would spend the
    instance's memory on whatever visitors happened to browse.
    """
    _, app = strict_server
    before = dict(app._GZ_CACHE)
    blob = b'x' * (1024 * 1024)
    try:
        for i in range(40):                                   # 40 MB offered into an 8 MB budget
            app._gz_remember((f'/synthetic/{i}', i, len(blob)), blob)
        assert app._GZ_CACHE_BYTES <= app.GZ_CACHE_MAX_BYTES, app._GZ_CACHE_BYTES
        assert sum(len(v) for v in app._GZ_CACHE.values()) <= app.GZ_CACHE_MAX_BYTES
        # it stops caching rather than failing: the budget is spent, not exceeded
        assert len(app._GZ_CACHE) > len(before), 'nothing was cached at all'
    finally:
        app._GZ_CACHE.clear()
        app._GZ_CACHE.update(before)
        app._GZ_CACHE_BYTES = sum(len(v) for v in before.values())
