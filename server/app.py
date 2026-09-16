"""Local analysis server (standard library only; suitable for an offline workstation).

    python server/app.py [--port 8765]

GET  /api/health                         engine version, commit, search-domain constants
POST /api/analyze?format=iq|wav&fs=HZ&name=...   raw .iq (interleaved float32) or .wav body
                                         → evidence pack (server/evidence.py)
GET  /*                                  built frontend (frontend/dist) with SPA fallback
"""

import argparse
import json
import os
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

DIST = os.path.join(ROOT, 'frontend', 'dist')
MAX_UPLOAD = 64 * 1024 * 1024


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

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/api/health':
            return self._json(200, {'status': 'ready', 'engine': engine_info()})
        if path.startswith('/api/'):
            return self._json(404, {'error': 'unknown endpoint'})
        if path == '/' or not os.path.exists(os.path.join(DIST, path.lstrip('/'))):
            self.path = '/index.html'
        return super().do_GET()

    def do_POST(self):
        url = urlparse(self.path)
        if url.path != '/api/analyze':
            return self._json(404, {'error': 'unknown endpoint'})
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        length = int(self.headers.get('Content-Length', 0))
        if length <= 0 or length > MAX_UPLOAD:
            return self._json(413, {'error': f'upload must be 1 byte to {MAX_UPLOAD // 2**20} MB'})
        body = self.rfile.read(length)
        fmt = q.get('format', 'iq').lower()
        try:
            if fmt == 'wav':
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                    f.write(body)
                try:
                    iq, fs = load_wav(f.name)
                finally:
                    os.unlink(f.name)
                fs = float(q.get('fs', fs))
            else:
                if len(body) % 8:
                    return self._json(400, {'error': '.iq must be interleaved float32 I/Q (byte count divisible by 8)'})
                raw = np.frombuffer(body, dtype=np.float32)
                iq = raw[0::2].astype(float) + 1j * raw[1::2].astype(float)
                fs = float(q.get('fs', 1e6))
            if len(iq) < 64:
                return self._json(400, {'error': 'capture too short (need at least 64 samples)'})
            meta = {k: q[k] for k in ('name', 'station', 'center_freq_hz', 'bandwidth_hz', 'antenna',
                                      'captured_at', 'notes') if k in q}
            meta['format'] = fmt
            pack = build_pack(iq, fs, f'CAP-{uuid.uuid4().hex[:8].upper()}',
                              {'kind': 'UPLOAD', 'file': q.get('name', 'upload'),
                               'note': 'Operator upload analysed by the local engine.'}, meta)
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
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()
