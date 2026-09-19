"""Local analysis server (standard library only; suitable for an offline workstation).

    python server/app.py [--port 8765]

GET  /api/health                         engine version, commit, search-domain constants, live sessions
POST /api/analyze?format=iq|wav[&fs=HZ]&name=...  (no fs for .iq → fs_source 'unavailable', never a default)[&t0_unix=&timing=gps|arrival]
                                         → evidence pack (server/evidence.py); narrowband captures also get
                                           the real-signal receivers (src/realsig.py) under pack.real
GET  /api/ledger[?limit=N]               evidence receipts as stored, one raw JSON line each, so a
                                         client can recompute the hash chain without trusting us
GET  /api/sources[?network=0]            signal sources with provenance, licence, what they feed
                                         (ENGINE / REFERENCE ONLY / METADATA ONLY) and measured health
GET  /api/crm/status                     Salesforce configuration and the local outbox
POST /api/crm/queue                      {pack, summary, priority, station} -> queue a case locally
POST /api/crm/flush                      attempt delivery of queued cases; reports what happened
GET  /api/live/stations                  live-receivable government transmitters (server/stations.py)
POST /api/live/start?station=KEY[&mode=iq|band&seconds=S&receiver=URL]   → {session}
GET  /api/live/events?session=ID         Server-Sent Events: spectrum rows, symbols, decodes, result
POST /api/live/stop?session=ID
GET  /api/live/sessions                  active sessions and recorded live captures (results/live)
GET  /api/live/session/ID                recorded session (analysis + metadata)
GET  /api/live/file/ID/capture.wav|audio.wav
GET  /api/recordings/ID.wav|ID.json      committed real-signal recordings (recordings/real)
GET  /*                                  built frontend (frontend/dist) with SPA fallback
"""

import argparse
import json
import os
import queue
import sys
import tempfile
import traceback
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import auth                                                          # noqa: E402
from evidence import LEDGER, ROOT, build_pack, engine_info, to_json_default   # noqa: E402
from modem import load_wav                                            # noqa: E402
import live                                                           # noqa: E402
import realsig                                                        # noqa: E402
import crm                                                            # noqa: E402
import sources                                                        # noqa: E402
from stations import STATIONS                                         # noqa: E402

DIST = os.path.join(ROOT, 'frontend', 'dist')
MAX_UPLOAD = 64 * 1024 * 1024

USERS = auth.Users()
SESSIONS = auth.Sessions()
LIMITER = auth.RateLimiter()
# Authentication is on by default. ICHNOVA_OPEN_API=1 restores the old unauthenticated behaviour for
# an offline single-user workstation.
OPEN_API = os.environ.get('ICHNOVA_OPEN_API', '0') == '1'

# Endpoint -> permission. Everything under /api/ that is not listed needs 'read'.
ENDPOINT_PERMISSION = {
    '/api/analyze': 'analyse',
    '/api/live/start': 'live',
    '/api/live/stop': 'live',
    '/api/auth/users': 'admin',
    '/api/crm/queue': 'review',
    '/api/crm/flush': 'review',
}
PUBLIC_ENDPOINTS = ('/api/health', '/api/auth/login', '/api/auth/demo', '/api/auth/accounts')



def _parse_fs(value):
    """Operator-declared sample rate from the query string: None when absent or blank."""
    if value is None or str(value).strip() == '':
        return None
    try:
        fs = float(value)
    except ValueError:
        raise ValueError(f'fs must be a number of Hz, got {value!r}')
    if not (np.isfinite(fs) and fs > 0):
        raise ValueError(f'fs must be a positive number of Hz, got {value!r}')
    return fs

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIST, **kwargs)

    # A body already read, so a refusal knows not to drain it twice.
    body_consumed = False
    DRAIN_LIMIT = 1024 * 1024

    def _drain(self):
        """Read and discard an unread request body before answering.

        Answering a POST without reading what the client is still sending leaves unread data in the
        socket, and closing it then sends a reset: on Windows the client sees a dropped connection
        instead of the 401, 403 or 429 that explains the refusal. Anything larger than DRAIN_LIMIT is
        left unread on purpose — refusing an oversized upload must not mean receiving it first."""
        if self.body_consumed or self.command not in ('POST', 'PUT', 'PATCH'):
            return
        self.body_consumed = True
        try:
            length = int(self.headers.get('Content-Length', 0) or 0)
        except ValueError:
            return
        remaining = min(length, self.DRAIN_LIMIT)
        while remaining > 0:
            chunk = self.rfile.read(min(remaining, 65536))
            if not chunk:
                break
            remaining -= len(chunk)

    def _json(self, code, payload):
        body = json.dumps(payload, default=to_json_default).encode()
        if code >= 400:
            self._drain()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _query(self):
        return {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}

    def _client(self):
        fwd = self.headers.get('X-Forwarded-For', '')
        return (fwd.split(',')[0].strip() if fwd else self.client_address[0]) or 'unknown'

    def _token(self):
        head = self.headers.get('Authorization', '')
        if head.lower().startswith('bearer '):
            return head[7:].strip()
        return self._query().get('token')

    def _identity(self):
        return SESSIONS.verify(self._token())

    def _body(self, limit=64 * 1024):
        length = int(self.headers.get('Content-Length', 0) or 0)
        if length <= 0 or length > limit:
            return None
        self.body_consumed = True
        try:
            return json.loads(self.rfile.read(length))
        except Exception:
            return None

    def _guard(self, path, bucket='default'):
        """Rate limit, then authenticate and authorise. Returns the identity, or None when a
        response has already been sent."""
        ok, retry = LIMITER.check(self._client(), bucket)
        if not ok:
            body = json.dumps({'error': 'too many requests', 'retry_after_s': retry}).encode()
            self._drain()                      # or the client sees a reset instead of the 429
            self.send_response(429)
            self.send_header('Retry-After', str(retry))
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return None
        if path in PUBLIC_ENDPOINTS:
            return {'sub': None, 'role': None}
        permission = ENDPOINT_PERMISSION.get(path, 'read')
        if OPEN_API:
            return {'sub': 'local', 'role': 'ADMIN', 'name': 'Local workstation', 'open_api': True}
        who = self._identity()
        if not who:
            self._json(401, {'error': 'authentication required'})
            return None
        if not auth.allowed(who['role'], permission):
            self._json(403, {'error': f"role {who['role']} may not {permission}"})
            return None
        return who

    def _sse(self, session):
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('X-Accel-Buffering', 'no')
        self.end_headers()
        q = session.subscribe()
        try:
            while True:
                try:
                    ev = q.get(timeout=15)
                except queue.Empty:
                    self.wfile.write(b': keepalive' + b'\n\n')
                    self.wfile.flush()
                    continue
                self.wfile.write(b'data: ' + json.dumps(ev, default=to_json_default).encode() + b'\n\n')
                self.wfile.flush()
                if ev['type'] == 'status' and ev.get('phase') == 'closed':
                    break
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        finally:
            session.unsubscribe(q)

    def _file(self, path, ctype):
        if not os.path.isfile(path):
            return self._json(404, {'error': 'not found'})
        data = open(path, 'rb').read()
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def end_headers(self):
        """Evidence data and the app shell must never come from a stale browser cache.

        They carry no validators, so browsers apply heuristic caching: after re-exporting the
        evidence the console kept showing the previous run's numbers and commit. Hashed files under
        /assets/ change name whenever they change, so they stay cacheable."""
        p = urlparse(self.path).path
        if '/assets/' not in p and (p.endswith(('.json', '.jsonl', '.html')) or '.' not in os.path.basename(p)):
            self.send_header('Cache-Control', 'no-store, must-revalidate')
        # The console is self-contained: no third-party scripts, styles, fonts or frames, and
        # connections are same-origin only, so the browser cannot be steered to an external service.
        self.send_header('Content-Security-Policy',
                         "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; "
                         "style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; "
                         "font-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'self'")
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Permissions-Policy', 'geolocation=(), microphone=(), camera=()')
        super().end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith('/api/'):
            who = self._guard(path, 'auth' if path.startswith('/api/auth/') else 'default')
            if who is None:
                return
            self.identity = who
        if path == '/api/auth/accounts':
            # Demo accounts only: username, role and what that role may do. Never a password.
            demo = [{'username': u['username'], 'name': u['name'], 'role': u['role'],
                     'station': u['station'],
                     'permissions': [k for k, roles in auth.PERMISSIONS.items() if u['role'] in roles]}
                    for u in USERS.users.values() if u.get('demo')]
            return self._json(200, {'demo_accounts': demo, 'auth_required': not OPEN_API,
                                    'session_ttl_s': SESSIONS.ttl,
                                    'ephemeral_signing_key': SESSIONS.ephemeral_key})
        if path == '/api/auth/me':
            return self._json(200, {'user': {k: self.identity.get(k) for k in ('sub', 'name', 'role', 'station', 'demo', 'exp')}})
        if path == '/api/auth/users':
            return self._json(200, {'users': [USERS.public(u) for u in USERS.users.values()]})
        if path == '/api/health':
            active = [x.summary() for x in live.SESSIONS.values() if x.state in ('starting', 'receiving', 'analysing')]
            return self._json(200, {'status': 'ready', 'engine': engine_info(),
                                    'live': {'active': active, 'max_sessions': live.MAX_SESSIONS}})
        if path == '/api/ledger':
            # The receipt ledger as it is stored, line for line. The raw text is what each hash was
            # taken over, so a client can recompute every hash itself instead of trusting this reply.
            limit = max(1, min(2000, int(self._query().get('limit') or 500)))
            lines = []
            if os.path.exists(LEDGER):
                with open(LEDGER, encoding='utf-8') as f:
                    lines = [ln.strip() for ln in f if ln.strip()]
            return self._json(200, {'path': os.path.relpath(LEDGER, ROOT).replace('\\', '/'),
                                    'total': len(lines), 'lines': lines[-limit:],
                                    'truncated': len(lines) > limit})
        if path == '/api/crm/status':
            return self._json(200, crm.status())
        if path == '/api/sources':
            # Health is measured on request, against the live services, so this can take a few
            # seconds. `network=0` answers from what is known offline instead of waiting.
            net = self._query().get('network', '1') != '0'
            return self._json(200, {'sources': sources.status_all(timeout=8, include_network=net)})
        if path == '/api/live/stations':
            keys = ('name', 'operator', 'country', 'service', 'frequency_khz', 'site', 'analysis', 'capture_s', 'references')
            return self._json(200, {k: {kk: v[kk] for kk in keys} for k, v in STATIONS.items()})
        if path == '/api/live/events':
            session = live.SESSIONS.get(self._query().get('session', ''))
            if not session:
                return self._json(404, {'error': 'unknown session'})
            return self._sse(session)
        if path == '/api/live/sessions':
            return self._json(200, {'active': [x.summary() for x in live.SESSIONS.values()],
                                    'recorded': live.recorded_sessions()})
        if path.startswith('/api/live/session/'):
            sid = os.path.basename(path)
            if not sid.startswith('LIVE-'):
                return self._json(404, {'error': 'not found'})
            return self._file(os.path.join(live.LIVE_DIR, sid, 'session.json'), 'application/json')
        if path.startswith('/api/recordings/'):
            name = os.path.basename(path)
            stem, ext = os.path.splitext(name)
            if ext in ('.wav', '.json') and stem and all(ch.isalnum() or ch in '-_' for ch in stem):
                return self._file(os.path.join(ROOT, 'recordings', 'real', name),
                                  'audio/wav' if ext == '.wav' else 'application/json')
            return self._json(404, {'error': 'not found'})
        if path.startswith('/api/live/file/'):
            parts = path.split('/')
            if len(parts) == 6 and parts[5] in ('capture.wav', 'audio.wav') and parts[4].startswith('LIVE-') \
                    and os.path.basename(parts[4]) == parts[4]:
                return self._file(os.path.join(live.LIVE_DIR, parts[4], parts[5]), 'audio/wav')
            return self._json(404, {'error': 'not found'})
        if path.startswith('/api/'):
            return self._json(404, {'error': 'unknown endpoint'})
        if path == '/' or not os.path.exists(os.path.join(DIST, path.lstrip('/'))):
            self.path = '/index.html'
        return super().do_GET()

    def do_POST(self):
        url = urlparse(self.path)
        who = self._guard(url.path, 'auth' if url.path.startswith('/api/auth/') else
                          'analyse' if url.path == '/api/analyze' else
                          'live' if url.path.startswith('/api/live/') else 'default')
        if who is None:
            return
        self.identity = who
        if url.path == '/api/auth/login':
            data = self._body() or {}
            rec = USERS.check(str(data.get('username', '')), str(data.get('password', '')))
            if not rec:
                return self._json(401, {'error': 'invalid username or password'})
            token, payload = SESSIONS.issue(rec)
            return self._json(200, {'token': token, 'expires_at': payload['exp'], 'user': USERS.public(rec)})
        if url.path == '/api/auth/demo':
            # Signs in a demo account without revealing its password. Demo accounts only.
            data = self._body() or {}
            rec = USERS.users.get(str(data.get('username', '')))
            if not rec or not rec.get('demo'):
                return self._json(404, {'error': 'unknown demo account'})
            token, payload = SESSIONS.issue(rec)
            return self._json(200, {'token': token, 'expires_at': payload['exp'], 'user': USERS.public(rec)})
        if url.path == '/api/auth/logout':
            return self._json(200, {'revoked': SESSIONS.revoke(self._token())})
        if url.path == '/api/live/start':
            q = self._query()
            try:
                seconds = float(q['seconds']) if 'seconds' in q else None
                x = live.start_session(q.get('station', ''), q.get('mode', 'iq'), seconds, q.get('receiver'))
            except KeyError:
                return self._json(400, {'error': 'unknown station'})
            except (RuntimeError, ValueError) as e:
                return self._json(429, {'error': str(e)})
            return self._json(200, {'session': x.summary()})
        if url.path == '/api/crm/queue':
            # The case is built here, from a fixed field list, so what reaches the CRM never widens
            # to whatever a client chose to send.
            body = self._body(limit=512 * 1024) or {}
            pack = body.get('pack') or {}
            item_id = ((pack.get('receipt') or {}).get('hash'))
            if not item_id:
                return self._json(400, {'error': 'the evidence pack has no receipt: nothing to raise a case against'})
            try:
                payload = crm.case_payload(pack, summary=str(body.get('summary') or '')[:1000],
                                           raised_by=self.identity.get('sub'),
                                           priority=str(body.get('priority') or 'Medium')[:40],
                                           station=body.get('station'))
                item, created = crm.Outbox().add(item_id, 'case', payload)
            except crm.BulkDataRefused as e:
                return self._json(400, {'error': str(e)})
            return self._json(200, {'queued': created, 'item': {k: v for k, v in item.items() if k != 'payload'},
                                    'crm': crm.Salesforce().status(), 'outbox': crm.Outbox().counts()})
        if url.path == '/api/crm/flush':
            return self._json(200, crm.flush())
        if url.path == '/api/live/stop':
            x = live.SESSIONS.get(self._query().get('session', ''))
            if not x:
                return self._json(404, {'error': 'unknown session'})
            x.stop_flag.set()
            return self._json(200, {'session': x.summary()})
        if url.path != '/api/analyze':
            return self._json(404, {'error': 'unknown endpoint'})
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        length = int(self.headers.get('Content-Length', 0))
        if length <= 0 or length > MAX_UPLOAD:
            # Refused on the declared length alone: the point is not to receive it, so the body is
            # deliberately left unread and the connection may be reset rather than drained.
            self.body_consumed = True
            return self._json(413, {'error': f'upload must be 1 byte to {MAX_UPLOAD // 2**20} MB'})
        self.body_consumed = True
        body = self.rfile.read(length)
        fmt = q.get('format', 'iq').lower()
        try:
            try:
                declared = _parse_fs(q.get('fs'))
            except ValueError as e:
                return self._json(400, {'error': str(e)})
            fs_note = None
            if fmt == 'wav':
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                    f.write(body)
                try:
                    iq, header_fs = load_wav(f.name)
                finally:
                    os.unlink(f.name)
                fs, fs_source = float(header_fs), 'wav_header'
                if declared is not None and abs(declared - header_fs) > 1e-6 * header_fs:
                    # An operator value that contradicts the file header is used, and the conflict is kept.
                    fs, fs_source = declared, 'declared'
                    fs_note = f'Operator-declared {declared:g} Hz overrides WAV header {header_fs} Hz'
            else:
                if len(body) % 8:
                    return self._json(400, {'error': '.iq must be interleaved float32 I/Q (byte count divisible by 8)'})
                raw = np.frombuffer(body, dtype=np.float32)
                iq = raw[0::2].astype(float) + 1j * raw[1::2].astype(float)
                # A raw .iq file has no header: without a declared rate the absolute rate is unknown.
                fs = declared
                fs_source = 'declared' if declared is not None else 'unavailable'
            if len(iq) < 64:
                return self._json(400, {'error': 'capture too short (need at least 64 samples)'})
            meta = {k: q[k] for k in ('name', 'station', 'center_freq_hz', 'bandwidth_hz', 'antenna',
                                      'captured_at', 'notes') if k in q}
            meta['format'] = fmt
            pack = build_pack(iq, fs, f'CAP-{uuid.uuid4().hex[:8].upper()}',
                              {'kind': 'UPLOAD', 'file': q.get('name', 'upload'),
                               'note': 'Operator upload analysed by the local engine.'}, meta,
                              fs_source=fs_source, fs_note=fs_note)
            if fs is not None and fs <= 200e3:
                # Narrowband real-world capture: also run the real-signal receivers (time codes, FSK, AM).
                t0 = float(q['t0_unix']) if 't0_unix' in q else None
                real, _ = realsig.analyze_capture(iq, fs, t0, q.get('timing'), float(q.get('offset_hz', 0.0)))
                pack['real'] = live._clean(real)
            return self._json(200, pack)
        except Exception as e:           # report, never crash the server
            traceback.print_exc()
            return self._json(500, {'error': f'analysis failed: {e}'})

    def log_message(self, fmt, *args):
        sys.stderr.write('[server] ' + fmt % args + '\n')


if __name__ == '__main__':
    # Defaults stay localhost-only. A container or PaaS sets HOST/PORT (Constitution v2.5 §9.2:
    # the engine never depends on a network; a hosted instance is a convenience, not the deployment model).
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=int(os.environ.get('PORT', 8765)))
    ap.add_argument('--host', default=os.environ.get('HOST', '127.0.0.1'))
    a = ap.parse_args()
    print(f'Analysis server on http://{a.host}:{a.port}  (frontend: {DIST})')
    server = ThreadingHTTPServer((a.host, a.port), Handler)
    server.daemon_threads = True
    server.serve_forever()
