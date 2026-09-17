"""Sample-rate provenance: a missing sample rate must never silently become a default (Constitution v2.5 §10)."""

import io
import json
import os
import sys
import threading
import urllib.request
import wave

import numpy as np
import pytest

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, os.path.join(ROOT, 'server'))

import pipeline                                       # noqa: E402
from evidence import build_pack, FS_NOT_ESTABLISHED   # noqa: E402
from test_core import _coded_signal                   # noqa: E402


def test_missing_fs_is_unavailable_not_a_default():
    iq, _ = _coded_signal(6, 'QPSK', seed=11)
    r = pipeline.analyze_iq(iq)
    assert r['fs_source'] == 'unavailable' and r['fs_hz'] is None
    assert r['status'] == 'DECODED'
    assert r['symbol_rate_est'] is None                # no absolute rate without an absolute fs
    assert r['symbol_rate_norm'] == pytest.approx(1 / 6)


def test_decision_does_not_depend_on_declared_fs():
    iq, _ = _coded_signal(8, 'BPSK', seed=12)
    a = pipeline.analyze_iq(iq)
    b = pipeline.analyze_iq(iq, fs=1e6)
    c = pipeline.analyze_iq(iq, fs=48000.0)
    for r in (b, c):
        assert r['status'] == a['status'] and r['sps'] == a['sps'] and r['code'] == a['code']
        assert np.array_equal(r['payload_bits'], a['payload_bits'])
        assert r['accept']['log10_p'] == pytest.approx(a['accept']['log10_p'])
    assert b['fs_source'] == 'declared' and b['symbol_rate_est'] == pytest.approx(1e6 / 8)
    assert c['symbol_rate_est'] == pytest.approx(48000 / 8)


@pytest.mark.parametrize('bad', [0.0, -1.0, float('nan'), float('inf')])
def test_invalid_fs_rejected(bad):
    with pytest.raises(ValueError):
        pipeline.analyze_iq(np.ones(100, complex), fs=bad)


def test_unknown_fs_source_rejected():
    with pytest.raises(ValueError):
        pipeline.analyze_iq(np.ones(100, complex), fs=1.0, fs_source='guessed')


def test_pack_without_fs_says_not_established():
    iq, _ = _coded_signal(4, 'BPSK', seed=13)
    pack = build_pack(iq, None, 'T-1', {'kind': 'UPLOAD'})
    cap = pack['capture']
    assert cap['fs_hz'] is None and cap['fs_source'] == 'unavailable'
    assert cap['duration_s'] is None and cap['fs_note'] == FS_NOT_ESTABLISHED
    assert pack['views']['units'] == 'normalised'
    assert pack['result']['symbol_rate_est'] is None
    json.dumps(pack, default=float)                    # serialisable with None values


@pytest.fixture(scope='module')
def server():
    import app
    httpd = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f'http://127.0.0.1:{httpd.server_address[1]}'
    httpd.shutdown()


def _post(base, query, body):
    req = urllib.request.Request(f'{base}/api/analyze?{query}', data=body, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _iq_bytes(iq):
    out = np.empty(2 * len(iq), dtype=np.float32)
    out[0::2], out[1::2] = iq.real, iq.imag
    return out.tobytes()


def test_api_iq_without_fs_is_unavailable(server):
    iq, _ = _coded_signal(6, 'BPSK', seed=14)
    status, pack = _post(server, 'format=iq&name=x.iq', _iq_bytes(iq))
    assert status == 200
    assert pack['capture']['fs_source'] == 'unavailable' and pack['capture']['fs_hz'] is None
    assert pack['result']['status'] == 'DECODED'


def test_api_iq_with_declared_fs(server):
    iq, _ = _coded_signal(6, 'BPSK', seed=14)
    status, pack = _post(server, 'format=iq&fs=250000&name=x.iq', _iq_bytes(iq))
    assert status == 200 and pack['capture']['fs_source'] == 'declared'
    assert pack['capture']['fs_hz'] == 250000.0


def test_api_rejects_malformed_fs(server):
    status, body = _post(server, 'format=iq&fs=fast', _iq_bytes(np.ones(200, complex)))
    assert status == 400 and 'fs' in body['error']


def test_api_wav_header_and_conflict(server):
    iq, _ = _coded_signal(6, 'QPSK', seed=15)
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(2), w.setsampwidth(2), w.setframerate(96000)
        pcm = np.empty(2 * len(iq), dtype=np.int16)
        scale = 30000 / np.max(np.abs(np.r_[iq.real, iq.imag]))
        pcm[0::2], pcm[1::2] = iq.real * scale, iq.imag * scale
        w.writeframes(pcm.tobytes())
    status, pack = _post(server, 'format=wav&name=x.wav', buf.getvalue())
    assert status == 200 and pack['capture']['fs_source'] == 'wav_header' and pack['capture']['fs_hz'] == 96000.0
    status, pack = _post(server, 'format=wav&fs=48000&name=x.wav', buf.getvalue())
    assert pack['capture']['fs_source'] == 'declared' and pack['capture']['fs_hz'] == 48000.0
    assert 'overrides WAV header 96000' in pack['capture']['fs_note']
