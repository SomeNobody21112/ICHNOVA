"""Staged blind signal analysis pipeline."""

import numpy as np
import time
from modem import load_iq, rrc_filter
from analyze import (detect_signal, estimate_snr_m2m4, estimate_symbol_rate,
                     identify_modulation, matched_filter_demod)
from decode_search import search_rotations


def analyze_file(filename, fs=1e6, verbose=False):
    """Full blind analysis pipeline.
    Returns dict with all estimates and decoded payload.
    """
    t0 = time.time()

    iq = load_iq(filename)
    if verbose:
        print(f"Loaded {len(iq)} samples from {filename}")

    det = detect_signal(iq, fs)
    if not det['detected']:
        return _fail_result(iq, fs, "no_signal", time.time() - t0)

    snr_est = estimate_snr_m2m4(iq)
    if verbose:
        print(f"SNR estimate: {snr_est:.1f} dB")

    sym_rate, sym_confidence = estimate_symbol_rate(iq, fs)
    sps_est = fs / sym_rate
    if verbose:
        print(f"Symbol rate: {sym_rate:.0f} Hz (sps={sps_est:.2f}, confidence={sym_confidence:.1f})")

    # CFO candidates from raw IQ — x⁴ is data-free for both BPSK and QPSK.
    # At 2 dB on ~40 symbols the true tone is not always the top x⁴ peak, but it
    # is reliably in the top 3, so let decode consistency pick ("decoding as a sensor").
    t_iq = np.arange(len(iq), dtype=float)
    result = None
    for cfo_per_sample in _cfo_candidates(iq, top_k=3):
        iq_cfo = iq * np.exp(-1j * 2 * np.pi * cfo_per_sample * t_iq)

        # Rank sps candidates by M4-power quality (rotation- and CFO-invariant).
        # Always include sps=6 as fallback.
        all_sps = _sps_candidates(sps_est)
        sps_try = _rank_sps_by_quality(iq_cfo, all_sps, top_k=2, force_include=6)

        # Modulation classification: use the forced-fallback sps (6) if available,
        # else the top-1 quality sps.  The forced value is reliable; the quality ranking
        # can be misleading at low SNR.
        _mod_sps = 6 if 6 in sps_try else sps_try[0]
        syms_rough = matched_filter_demod(iq_cfo, rrc_filter(0.35, _mod_sps), _mod_sps)
        mod_est = identify_modulation(syms_rough, fs)
        beta_try = [0.25, 0.5, 0.35]

        r = search_rotations(iq_cfo, sps_try, mod_est, fs=fs, beta=beta_try,
                             snr_est_db=snr_est, n_info_bits=400)
        r['cfo'], r['modulation'] = cfo_per_sample, mod_est
        if verbose:
            print(f"CFO {cfo_per_sample:+.5f}: {mod_est} cons={r['consistency']:.3f}")
        if result is None or r['score'] > result['score']:
            result = r
        # Correct hypotheses re-encode at ~1.0, wrong ones top out near 0.94.
        if result['consistency'] >= _CONSISTENCY_ACCEPT:
            break
    mod_est = result['modulation']

    elapsed = time.time() - t0

    return {
        'payload_bits': result['decoded_bits'],
        'consistency': result['consistency'],
        'code': result['code']['name'] if isinstance(result['code'], dict) else str(result['code']),
        'interleaver': result['interleaver'],
        'modulation': mod_est,
        'symbol_rate_est': result.get('symbol_rate_est', sym_rate),
        'sps_used': result['sps_used'],
        'beta_used': result['beta_used'],
        'snr_est_db': snr_est,
        'phase': result['phase'],
        'cfo': result['cfo'],
        'runtime': elapsed,
    }


_CONSISTENCY_ACCEPT = 0.98
_CFO_SEARCH_LIMIT = 0.05   # |4·CFO| bound; signal model |CFO| ≤ 0.01 → 0.04, plus margin


def _cfo_candidates(iq, top_k=3, pad=16):
    """Top-k CFO estimates (cycles/sample) from local peaks of the zero-padded x⁴ spectrum."""
    n_fft = pad * len(iq)
    spec = np.abs(np.fft.fft(iq ** 4, n_fft))
    freqs = np.fft.fftfreq(n_fft)
    spec[np.abs(freqs) >= _CFO_SEARCH_LIMIT] = 0
    spec[0] = 0
    is_peak = (spec > np.roll(spec, 1)) & (spec >= np.roll(spec, -1))
    peaks = np.flatnonzero(is_peak)
    peaks = peaks[np.argsort(-spec[peaks])][:top_k]
    return [float(freqs[k]) / 4.0 for k in peaks] or [0.0]


def _sps_candidates(sps_est):
    """All sps candidates: estimated ±1 plus common fallbacks {4,6,8}."""
    sps_est = max(2, sps_est)
    rounded = int(round(sps_est))
    seen = set()
    candidates = []
    for v in [rounded, rounded - 1, rounded + 1, 4, 6, 8]:
        if 2 <= v <= 20 and v not in seen:
            seen.add(v)
            candidates.append(v)
    return candidates


def _m4_quality(iq, sps, beta=0.35):
    """M4-power lag-1 autocorrelation quality (rotation- and phase-invariant)."""
    sps = max(2, int(round(sps)))
    syms = matched_filter_demod(iq, rrc_filter(beta, sps), sps)
    if len(syms) < 10:
        return 0.0
    s4 = syms ** 4
    power = np.mean(np.abs(s4) ** 2) + 1e-20
    r1 = np.abs(np.mean(s4[1:] * np.conj(s4[:-1])))
    return float(r1 / power)


def _rank_sps_by_quality(iq, sps_list, top_k=2, force_include=6):
    """Return up to top_k sps values by M4 quality, always including force_include."""
    quals = sorted((((_m4_quality(iq, s)), s) for s in sps_list), reverse=True)
    selected = []
    for _, s in quals[:top_k]:
        if s not in selected:
            selected.append(s)
    if force_include not in selected and force_include in sps_list:
        selected.append(force_include)
    return selected


def _fail_result(iq, fs, reason, elapsed):
    return {
        'payload_bits': np.array([], dtype=np.uint8),
        'consistency': 0.0,
        'code': 'none',
        'interleaver': None,
        'modulation': 'UNKNOWN',
        'symbol_rate_est': 0,
        'sps_used': 0,
        'beta_used': 0,
        'snr_est_db': 0,
        'phase': 0,
        'runtime': elapsed,
        'failure': reason,
    }
