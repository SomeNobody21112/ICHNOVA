"""Evidence pack: one JSON document per analysed capture, consumed by the frontend.

The pack is the receiver's real output plus the views an analyst needs (spectrogram, PSD,
constellation, time series). Nothing in it is simulated; `source.kind` says where the IQ came
from (BENCHMARK = synthetic benchmark capture, UPLOAD = operator upload).
"""

import datetime
import os
import subprocess
import sys

import numpy as np
from scipy.signal import spectrogram, welch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'src'))

import pipeline                                           # noqa: E402
import quality                                            # noqa: E402
import receipt as receipts                                # noqa: E402
import sufficiency                                        # noqa: E402
from pipeline import analyze_iq                           # noqa: E402
from modem import rrc_filter                              # noqa: E402
from analyze import matched_filter_demod, estimate_carrier_phase   # noqa: E402

ENGINE_VERSION = '0.3.0'


def _commit():
    try:
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT, text=True).strip()
    except Exception:
        return 'unknown'


def engine_info():
    return {
        'version': ENGINE_VERSION, 'commit': _commit(),
        'alpha': pipeline.ALPHA, 'accept_search': pipeline.ACCEPT_SEARCH,
        'bl_delta_symbols': pipeline.BL_DELTA_SYMBOLS, 'pm_floor': pipeline.PM_FLOOR,
        'sps_range': list(pipeline.SPS_RANGE), 'min_symbols': pipeline.MIN_SYMBOLS,
        'cfo_max': pipeline.CFO_MAX, 'rx_beta': pipeline.RX_BETA,
        'modulations': list(pipeline.MODULATIONS),
        'codes': [c['name'] for c in pipeline.CODE_CATALOGUE],
        'interleaver_domain': 'single block, rows 2-16, cols 4-24 (<=384 bits)',
    }


def _views(iq, fs, result):
    """Display views. With an unknown sample rate (fs None) frequency and time axes are normalised
    (cycles/sample, samples) and `units` says so."""
    n = len(iq)
    fs = 1.0 if fs is None else fs
    nper = int(min(128, max(16, 2 ** int(np.log2(max(n // 24, 16))))))
    f, t, S = spectrogram(iq, fs=fs, nperseg=nper, noverlap=nper // 2, return_onesided=False,
                          window='hann', mode='psd')
    S = np.fft.fftshift(S, axes=0)
    f = np.fft.fftshift(f)
    if S.shape[1] > 160:                      # keep the payload small
        idx = np.linspace(0, S.shape[1] - 1, 160).astype(int)
        S, t = S[:, idx], t[idx]
    db = 10 * np.log10(S + 1e-20)
    fw, pw = welch(iq, fs=fs, nperseg=min(256, n), return_onesided=False)
    order = np.argsort(fw)

    front = None
    if result['status'] in ('DECODED', 'SIGNAL_NO_CODE') and result['sps']:
        front = result
    elif result['diagnostics']['top_hypotheses']:
        front = result['diagnostics']['top_hypotheses'][0]
    const = []
    if front:
        sps = int(front['sps'])
        y = matched_filter_demod(iq * np.exp(-2j * np.pi * front['cfo'] * np.arange(n)),
                                 rrc_filter(result['beta'], sps), sps)
        phase = front.get('phase')
        if phase is None:
            phase = estimate_carrier_phase(y, front['modulation'])
        y = y * np.exp(-1j * (phase + (front.get('rotation') or 0.0)))
        active = front.get('active_symbols') or len(y)
        y = y[:max(int(active), 16)]
        y = y / (np.sqrt(np.mean(np.abs(y) ** 2)) + 1e-20)
        const = [[round(float(v.real), 4), round(float(v.imag), 4)] for v in y[:800]]
    k = min(n, 600)
    return {
        'units': 'hz' if fs != 1.0 else 'normalised',
        'spectrogram': {'f_hz': [round(float(v), 1) for v in f], 't_s': [round(float(v), 6) for v in t],
                        'db': [[round(float(v), 1) for v in row] for row in db]},
        'psd': {'f_hz': [round(float(v), 1) for v in fw[order]],
                'db': [round(float(v), 2) for v in 10 * np.log10(pw[order] + 1e-20)]},
        'constellation': const,
        'timeseries': {'i': [round(float(v), 4) for v in iq[:k].real],
                       'q': [round(float(v), 4) for v in iq[:k].imag]},
    }


FS_NOT_ESTABLISHED = 'Absolute sample rate not established'


LEDGER = os.path.join(ROOT, 'results', 'ledger.jsonl')


def build_pack(iq, fs, pack_id, source, capture_meta=None, truth=None, fs_source=None, fs_note=None,
               ledger_path=None):
    """fs: absolute sample rate in Hz or None; fs_source: pipeline.FS_SOURCES."""
    iq = np.asarray(iq, dtype=complex)
    r = analyze_iq(iq, fs=fs, _top_k=20, _all_hypotheses=True, fs_source=fs_source)
    payload = np.asarray(r['payload_bits']).astype(int).tolist()
    result = {k: r[k] for k in ('status', 'code', 'interleaver', 'modulation', 'sps', 'symbol_rate_est',
                                'symbol_rate_norm', 'cfo', 'beta', 'phase', 'rotation', 'runtime')}
    result['payload_bits'] = payload[:512]
    result['payload_len'] = len(payload)
    allh = r['diagnostics'].get('all_hypotheses')
    if allh:                                   # display precision; keeps packs small
        allh['log10_p'] = [round(v, 2) for v in allh['log10_p']]
        allh['cfo'] = [round(float(v), 6) for v in allh['cfo']]
        allh['code'] = [c.split('_')[1].upper() for c in allh['code']]
    pack = {
        'id': pack_id,
        'analysed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
        'source': source,
        'capture': {'samples': int(len(iq)),
                    'fs_hz': float(fs) if fs is not None else None,
                    'fs_source': r['fs_source'],
                    'fs_note': fs_note or (None if fs is not None else FS_NOT_ESTABLISHED),
                    'duration_s': float(len(iq) / fs) if fs is not None else None,
                    **(capture_meta or {})},
        'engine': engine_info(),
        'result': result,
        'accept': r['accept'],
        'diagnostics': r['diagnostics'],
        'views': _views(iq, fs, {**r, 'diagnostics': r['diagnostics']}),
    }
    # Capture quality: reported beside the verdict, never folded into it.
    pack['data_quality'] = quality.assess(iq, fs, declared_samples=(capture_meta or {}).get('declared_samples'))
    # Why a refusal happened and what capture would settle it, from the acceptance statistics.
    pack['sufficiency'] = sufficiency.assess(r, fs=fs)
    # Receipt: this decision, this capture, this engine, chained to the previous receipt.
    path = LEDGER if ledger_path is None else ledger_path
    decision, statistics = receipts.summarise(r, pack_id)

    def _receipt(prev_hash):
        return receipts.build(capture_sha256=receipts.sha256_array(iq), engine=pack['engine'],
                              decision=decision, statistics=statistics, source=source,
                              prev_hash=prev_hash,
                              capture={'samples': int(len(iq)), 'fs_hz': float(fs) if fs is not None else None,
                                       'fs_source': r['fs_source']})
    try:
        # Reading the head and appending must not be two steps: the server is threaded, and two
        # analyses finishing together would otherwise both claim the same predecessor and fork the
        # chain. See receipt.append_chained.
        rec = receipts.append_chained(path, _receipt)
    except OSError:
        # A read-only deployment still returns the receipt with the pack; it just is not stored, so
        # it cannot honestly claim a place in the chain either.
        rec = _receipt(receipts.GENESIS)
    pack['receipt'] = rec
    if truth is not None:
        pack['benchmark_truth'] = truth
    return pack


def to_json_default(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.bool_):
        return bool(o)
    raise TypeError(type(o))
