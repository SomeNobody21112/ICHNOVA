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

    # CFO estimation from raw IQ — x⁴ is data-free for both BPSK and QPSK.
    # Signal model: |CFO| ≤ 0.01 → |4·CFO| ≤ 0.04. Use 0.042 + fine refinement.
    _CFO_SEARCH_LIMIT = 0.042
    n_iq = len(iq)
    t_iq = np.arange(n_iq, dtype=float)
    fft4_iq = np.abs(np.fft.fft(iq ** 4))
    _bin_max = max(1, int(np.ceil(_CFO_SEARCH_LIMIT * n_iq)))
    fft4_iq[_bin_max: n_iq - _bin_max] = 0
    fft4_iq[0] = 0
    k_cfo = int(np.argmax(fft4_iq))
    cfo_raw = float(k_cfo) / n_iq
    if cfo_raw > 0.5:
        cfo_raw -= 1.0
    cfo_coarse = cfo_raw / 4.0

    # Fine-tune CFO: search ±0.006 around coarse estimate using M4 quality
    cfo_per_sample = _refine_cfo(iq, cfo_coarse, t_iq)
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
    if verbose:
        print(f"Modulation: {mod_est} (sps={_mod_sps})")
    beta_try = [0.25, 0.5, 0.35]

    result = search_rotations(iq_cfo, sps_try, mod_est, fs=fs, beta=beta_try,
                              snr_est_db=snr_est, n_info_bits=400)

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
        'runtime': elapsed,
    }


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


def _refine_cfo(iq, cfo_coarse, t_iq, sps=6, n_steps=41):
    """Fine-tune CFO by maximising M4-power lag-1 autocorrelation quality."""
    best_q = -1.0
    best_cfo = cfo_coarse
    for delta in np.linspace(-0.006, 0.006, n_steps):
        cfo_try = cfo_coarse + delta
        if abs(cfo_try) > 0.012:
            continue
        iq_try = iq * np.exp(-1j * 2 * np.pi * cfo_try * t_iq)
        syms = matched_filter_demod(iq_try, rrc_filter(0.35, sps), sps)
        if len(syms) < 10:
            continue
        s4 = syms ** 4
        q = float(np.abs(np.mean(s4[1:] * np.conj(s4[:-1]))) /
                  (np.mean(np.abs(s4) ** 2) + 1e-20))
        if q > best_q:
            best_q = q
            best_cfo = cfo_try
    return best_cfo


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
