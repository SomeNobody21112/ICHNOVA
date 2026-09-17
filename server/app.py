"""Local analysis server (standard library only; suitable for an offline workstation).

    python server/app.py [--port 8765]

GET  /api/health                         engine version, commit, search-domain constants, live sessions
POST /api/analyze?format=iq|wav[&fs=HZ]&name=...  (no fs for .iq → fs_source 'unavailable', never a default)[&t0_unix=&timing=gps|arrival]
                                         → evidence pack (server/evidence.py); narrowband captures also get
                                           the real-signal receivers (src/realsig.py) under pack.real
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

from evidence import ROOT, build_pack, engine_info, to_json_default   # noqa: E402
from modem import load_wav                                            # noqa: E402
import live                                                           # noqa: E402
import realsig                                                        # noqa: E402
from stations import STATIONS                                         # noqa: E402

DIST = os.path.join(ROOT, 'frontend', 'dist')
MAX_UPLOAD = 64 * 1024 * 1024



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

    def _json(self, code, payload):
        body = json.dumps(payload, default=to_json_default).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _query(self):
        return {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}

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

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/api/health':
            active = [x.summary() for x in live.SESSIONS.values() if x.state in ('starting', 'receiving', 'analysing')]
            return self._json(200, {'status': 'ready', 'engine': engine_info(),
                                    'live': {'active': active, 'max_sessions': live.MAX_SESSIONS}})
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
            return self._json(413, {'error': f'upload must be 1 byte to {MAX_UPLOAD // 2**20} MB'})
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
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--host', default='127.0.0.1')
    a = ap.parse_args()
    print(f'Analysis server on http://{a.host}:{a.port}  (frontend: {DIST})')
    server = ThreadingHTTPServer((a.host, a.port), Handler)
    server.daemon_threads = True
    server.serve_forever()
