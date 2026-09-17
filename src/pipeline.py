"""Blind receiver.

raw IQ
  → CFO candidates: peaks of the x² and x⁴ spectra, each with a p-value against the
    exponential-periodogram null (also the signal-presence test)
  → sps candidates: lag-1 correlation of y⁴ for every sps in the search domain; the best
    few plus their integer divisors plus the raw spectral estimate (aliases at integer
    multiples are resolved by the code test: at k·sps most coded symbols are skipped)
  → front-ends (CFO × sps × modulation × rotation): matched filter, M-power phase,
    M2M4-calibrated LLRs
  → every (code × interleaver) hypothesis: dual-code syndrome sign test (blind_id.py)
  → rank by p-value; ACCEPT only if p × (number of hypotheses tested) ≤ ALPHA
  → DECODED (Viterbi on the accepted hypothesis) | SIGNAL_NO_CODE | UNKNOWN

Result keys: status, payload_bits, code, interleaver, modulation, sps, symbol_rate_est,
cfo, beta, phase, rotation, accept{log10_p, log10_threshold, n_hypotheses, alpha},
diagnostics{cfo_candidates, detection_log10_p, raw_sps_estimate, sps_table,
sps_candidates, modulation_stats, top_hypotheses, runner_up_margin_log10, timers_s}, runtime.
"""

import time
import numpy as np
import functools

from modem import load_iq, rrc_filter as _rrc_filter
from analyze import (estimate_symbol_rate, lag1_correlation, estimate_carrier_phase,
                     matched_filter_demod, symbol_snr_m2m4, psk_llrs)
from scipy.special import bdtr, bdtrc, ndtr
from blind_id import (CODE_CATALOGUE, interleaver_candidates, syndrome_scan, sign_test_log10p,
                      decode_hypothesis)

# ---- Receiver search domain: a front-end specification, independent of any dataset ----
SPS_RANGE = (2, 20)     # integer samples/symbol → symbol rates fs/20 … fs/2
MIN_SYMBOLS = 16        # an sps candidate must yield at least this many symbols
CFO_MAX = 0.0125        # |carrier offset| ≤ 1.25 % of fs (assumed front-end tuning accuracy)
RX_BETA = 0.3           # one RRC matched filter, mid-range of the common 0.1–0.5 roll-offs
N_SPS_RANKED = 3        # compute budget: best sps by quality (their divisors are added)
N_CFO_PER_ORDER = 3     # compute budget: strongest x² and x⁴ spectral peaks
ALPHA = 0.01            # target false-accept probability per file under the null
ACCEPT_SEARCH = 20      # significant hypotheses examined by the structural checks
# Structural checks (eval/acceptance.py, calibrated on the even-indexed null-set files, reported
# on the odd-indexed ones): wrong-structure accepts 39/225 -> 2/225, wrong-hypothesis 5 -> 0.
BL_DELTA_SYMBOLS = 1.7  # 99th pct shortfall of correct hypotheses' coverage vs transmission span
PM_FLOOR = 0.926        # 99th pct of top-1 soft path metric on calibration null files
MODULATIONS = ('BPSK', 'QPSK')


def analyze_file(filename, fs=1e6, verbose=False):
    """Blind analysis of an interleaved-float32 .iq file."""
    return analyze_iq(load_iq(filename), fs=fs)


@functools.lru_cache(maxsize=256)
def rrc_filter(beta, sps):
    """modem.rrc_filter is a per-tap Python loop; the receiver asks for the same few filters thousands
    of times. Cached copy is read-only so no caller can alter a shared filter."""
    h = _rrc_filter(beta, sps)
    h.setflags(write=False)
    return h


def analyze_iq(iq, fs=1e6, _oracle=None, _top_k=5, _keep_bits=False, _all_hypotheses=False):
    """Blind analysis of complex baseband samples.

    `_oracle` is evaluation-only (eval/ladder.py): ground-truth values that replace the
    corresponding estimates (keys: modulation, sps, cfo, beta, timing_offset, phase,
    interleaver, exclude_interleaver). Normal inference never passes it; acceptance is
    never oracled. `_top_k` / `_keep_bits` only widen the logged hypothesis list (eval)."""
    o = _oracle or {}
    timers = dict.fromkeys(['cfo', 'sps', 'matched_filter', 'syndrome_search',
                            'viterbi', 'scoring'], 0.0)
    t_start = time.perf_counter()
    iq = np.asarray(iq, dtype=complex)
    if 'timing_offset' in o:   # undo the generator's fractional delay exp(-j2πfτ)
        f = np.fft.fftfreq(len(iq))
        iq = np.fft.ifft(np.fft.fft(iq) * np.exp(2j * np.pi * f * o['timing_offset']))
    n = np.arange(len(iq))

    t = time.perf_counter()
    cfo_cands, detection_log10p = _cfo_candidates(iq)
    cfo_list = [float(o['cfo'])] if 'cfo' in o else [c['cfo'] for c in cfo_cands]
    timers['cfo'] += time.perf_counter() - t

    t = time.perf_counter()
    sps_table = _sps_table(iq)
    raw_rate, _ = estimate_symbol_rate(iq, fs, SPS_RANGE)
    raw_sps = fs / raw_rate
    sps_list = [int(o['sps'])] if 'sps' in o else _sps_candidates(sps_table, raw_sps)
    timers['sps'] += time.perf_counter() - t
    mods = [o['modulation']] if 'modulation' in o else list(MODULATIONS)
    beta = float(o.get('beta', RX_BETA))

    fronts, rejected_serial = [], 0
    hyp_parts = []
    for cfo in cfo_list:
        iq_c = iq * np.exp(-2j * np.pi * cfo * n)
        for s in sps_list:
            t = time.perf_counter()
            y = matched_filter_demod(iq_c, rrc_filter(beta, s), s)
            timers['matched_filter'] += time.perf_counter() - t
            if len(y) < MIN_SYMBOLS:
                continue
            span = _front_end_evidence(y)
            for mod in mods:
                phase = float(o['phase']) if 'phase' in o else estimate_carrier_phase(y, mod)
                ys = y * np.exp(-1j * phase)
                S, N = symbol_snr_m2m4(ys)
                # QPSK: rotations 0 and π/2; π and 3π/2 only complement all bits, which
                # every parity check of the catalogue codes (odd-weight generators) ignores.
                rots = [0.0] if (mod == 'BPSK' or 'phase' in o) else [0.0, np.pi / 2]
                for rot in rots:
                    t = time.perf_counter()
                    llrs = psk_llrs(ys * np.exp(-1j * rot), mod, S, N)
                    # The syndrome null needs serially independent hard decisions. Random,
                    # interleaved payload at the true symbol rate gives that; a front-end that
                    # oversamples the signal (sps too small) repeats each symbol, which biases
                    # short parity checks. Reject front-ends whose neighbouring decisions agree
                    # significantly more than half the time (exact one-sided sign test).
                    step = 1 if mod == 'BPSK' else 2
                    same = np.count_nonzero((llrs[step:] < 0) == (llrs[:-step] < 0))
                    if float(sign_test_log10p(same, len(llrs) - step)) <= np.log10(ALPHA):
                        rejected_serial += 1
                        timers['syndrome_search'] += time.perf_counter() - t
                        continue
                    th = np.tanh(np.clip(llrs, -40, 40) / 2)
                    fi = len(fronts)
                    fronts.append({'cfo': cfo, 'sps': s, 'modulation': mod, 'phase': phase,
                                   'rotation': rot, 'llrs': llrs,
                                   'symbol_snr_db': float(10 * np.log10(S / N + 1e-30)), **span})
                    dims_list = ([tuple(o['interleaver'])] if 'interleaver' in o
                                 else interleaver_candidates(len(llrs)))
                    if 'exclude_interleaver' in o:
                        dims_list = [d for d in dims_list if d != tuple(o['exclude_interleaver'])]
                    # All interleaver x code hypotheses of this front end in one vectorised pass
                    # (blind_id.syndrome_scan; identical check signs to the per-pair loop).
                    scan = syndrome_scan(th, dims_list)
                    scan['front'] = np.full(len(scan['n']), fi)
                    hyp_parts.append(scan)
                    timers['syndrome_search'] += time.perf_counter() - t

    t = time.perf_counter()
    hyp = {k: (np.concatenate([p[k] for p in hyp_parts]) if hyp_parts else np.zeros(0, dtype=int))
           for k in ('front', 'code', 'rows', 'cols', 'n', 'pos', 'sum', 'sq')}
    M = len(hyp['n'])
    top, best_log10p, runner_margin, rejected = [], 0.0, None, []
    log10_threshold = float(np.log10(ALPHA / max(M, 1)))
    described = {}

    def describe(k):
        """Decode hypothesis k and collect every score the UI and acceptance rules use."""
        if k in described:
            return described[k]
        fr = fronts[int(hyp['front'][k])]
        code = CODE_CATALOGUE[int(hyp['code'][k])]
        dims = (int(hyp['rows'][k]), int(hyp['cols'][k]))
        t0 = time.perf_counter()
        dec = _decode_both_polarities(fr['llrs'], code, dims)
        timers['viterbi'] += time.perf_counter() - t0
        n_steps = dims[0] * dims[1] // 2
        d = {
            'code': code['name'], 'interleaver': list(dims), 'sps': fr['sps'],
            'cfo': fr['cfo'], 'modulation': fr['modulation'],
            'rotation': fr['rotation'] + dec['flip'], 'phase': fr['phase'],
            'symbol_snr_db': fr['symbol_snr_db'],
            'n_checks': int(hyp['n'][k]), 'n_positive': int(hyp['pos'][k]),
            'log10_p': float(log10p[k]), 'syndrome_z': float(z[k]),
            'covered_bits': dec['covered_bits'], 'total_observed_bits': len(fr['llrs']),
            'coverage_ratio': dec['covered_bits'] / len(fr['llrs']),
            'consistency': dec['consistency'], 'path_metric': dec['path_metric'],
            # MDL: a rate-1/2 code needs n_steps free bits instead of 2·n_steps, pays the soft
            # disagreement, and pays log2(M) to name the hypothesis.
            'mdl_savings_bits': float(n_steps - dec['soft_disagreement_nats'] / np.log(2) - np.log2(M)),
            'uncoded_mdl_savings_bits': 0.0,
            'active_symbols': fr['active_symbols'],
            'covered_symbols': dec['covered_bits'] / (1 if fr['modulation'] == 'BPSK' else 2),
            'bpsk_presence_log10p': fr['bpsk_presence_log10p'],
            'bpsk_contradiction_log10p': fr['bpsk_contradiction_log10p'],
            '_decoded_bits': dec['decoded_bits'],
        }
        d['structural_rejection'] = _structural_rejection(d)
        described[k] = d
        return d

    accepted_k = None
    if M:
        log10p = sign_test_log10p(hyp['pos'], hyp['n'])
        z = hyp['sum'] / np.sqrt(np.maximum(hyp['sq'], 1e-300))
        order = np.lexsort((-z, log10p))
        best_log10p = float(log10p[order[0]])
        # Acceptance: walk significant hypotheses in p-value order; the first that also passes
        # the structural checks (modulation, block length, soft path metric) is accepted.
        for k in order[:ACCEPT_SEARCH]:
            if log10p[k] > log10_threshold:
                break
            d = describe(k)
            if d['structural_rejection'] is None:
                accepted_k = k
                break
            rejected.append({key: d[key] for key in ('code', 'interleaver', 'modulation', 'sps',
                                                     'log10_p', 'structural_rejection')})
        ref = order[0] if accepted_k is None else accepted_k
        ref_key = (hyp['code'][ref], hyp['rows'][ref], hyp['cols'][ref])
        for k in order:
            if (hyp['code'][k], hyp['rows'][k], hyp['cols'][k]) != ref_key:
                runner_margin = float(log10p[k] - log10p[ref])
                break
    timers['scoring'] += time.perf_counter() - t
    accepted = accepted_k is not None
    if M:
        top = [describe(k) for k in order[:_top_k]]

    signal_front = _signal_front(cfo_cands, sps_table, o)
    result = {
        'status': 'UNKNOWN', 'payload_bits': np.array([], dtype=np.uint8), 'code': None,
        'interleaver': None, 'modulation': None, 'sps': None, 'symbol_rate_est': None,
        'cfo': None, 'beta': beta, 'phase': None, 'rotation': None,
    }
    accepted_desc = None
    if accepted:
        # Several front-ends can pass the accepted (code, interleaver) equally: a QPSK π/2
        # rotation, or any complement (π), is still a codeword of these codes, only with a
        # nonzero encoder start state. The syndrome test cannot separate them; Viterbi assumes
        # start state 0 (a reset encoder at the start of the capture), so the best zero-start
        # path metric over front-ends and both polarities breaks the tie. Without that
        # assumption the ambiguity needs frame synchronisation.
        b = describe(accepted_k)
        acc_key = (hyp['code'][accepted_k], hyp['rows'][accepted_k], hyp['cols'][accepted_k])
        for k in order:
            if log10p[k] > log10_threshold:
                break
            if k == accepted_k or (hyp['code'][k], hyp['rows'][k], hyp['cols'][k]) != acc_key:
                continue
            d = describe(k)
            if d['structural_rejection'] is None and d['path_metric'] > b['path_metric']:
                b = d
        accepted_desc = {key: val for key, val in b.items() if key != '_decoded_bits'}
        result.update(status='DECODED', payload_bits=b['_decoded_bits'], code=b['code'],
                      interleaver=b['interleaver'], modulation=b['modulation'], sps=b['sps'],
                      symbol_rate_est=fs / b['sps'], cfo=b['cfo'], phase=b['phase'],
                      rotation=b['rotation'])
    elif detection_log10p <= np.log10(ALPHA) and signal_front:
        result.update(status='SIGNAL_NO_CODE', symbol_rate_est=fs / signal_front['sps'],
                      **signal_front)
        result['payload_bits'] = _hard_bits(iq, signal_front, beta)
    for h in top:
        bits = h.pop('_decoded_bits', None)
        if _keep_bits and bits is not None:
            h['decoded_bits'] = bits.tolist()

    result['accept'] = {'log10_p': best_log10p, 'log10_threshold': log10_threshold,
                        'n_hypotheses': M, 'alpha': ALPHA, 'accepted_hypothesis': accepted_desc,
                        'significant_but_rejected': rejected,
                        'rules': {'bl_delta_symbols': BL_DELTA_SYMBOLS, 'pm_floor': PM_FLOOR}}
    result['diagnostics'] = {
        'cfo_candidates': cfo_cands, 'detection_log10_p': float(detection_log10p),
        'raw_sps_estimate': float(raw_sps), 'sps_table': sps_table,
        'sps_candidates': [int(s) for s in sps_list],
        'modulation_stats': [_modulation_stat(r) for r in sps_table if r['sps'] in sps_list],
        'top_hypotheses': top, 'runner_up_margin_log10': runner_margin,
        'n_front_ends': len(fronts), 'front_ends_rejected_serial_dependence': rejected_serial,
        'timers_s': timers,
    }
    if _all_hypotheses and M:
        result['diagnostics']['all_hypotheses'] = {
            'code': [CODE_CATALOGUE[c]['name'] for c in hyp['code'].tolist()],
            'rows': hyp['rows'].tolist(), 'cols': hyp['cols'].tolist(),
            'sps': [fronts[f]['sps'] for f in hyp['front'].tolist()],
            'modulation': [fronts[f]['modulation'] for f in hyp['front'].tolist()],
            'cfo': [fronts[f]['cfo'] for f in hyp['front'].tolist()],
            'n_checks': hyp['n'].tolist(), 'n_positive': hyp['pos'].tolist(),
            'log10_p': [float(v) for v in log10p]}
    result['runtime'] = time.perf_counter() - t_start
    return result


def _structural_rejection(d):
    """Reason a significant hypothesis is structurally implausible, or None.

    MC  a QPSK hypothesis on a signal with a significant BPSK signature, or a BPSK hypothesis
        whose BPSK-consistency count is significantly too low (exact binomial tests at ALPHA);
    BL  it explains fewer symbols than the measured transmission span (minus BL_DELTA_SYMBOLS);
    PM  its soft Viterbi path metric is below PM_FLOOR."""
    log_alpha = np.log10(ALPHA)
    if d['modulation'] == 'QPSK' and d['bpsk_presence_log10p'] <= log_alpha:
        return 'modulation: BPSK signature present, QPSK hypothesis contradicted'
    if d['modulation'] == 'BPSK' and d['bpsk_contradiction_log10p'] <= log_alpha:
        return 'modulation: symbols inconsistent with BPSK'
    if d['covered_symbols'] < d['active_symbols'] - BL_DELTA_SYMBOLS:
        return (f"block length: covers {d['covered_symbols']:.0f} of ~{d['active_symbols']} "
                f"transmitted symbols")
    if d['path_metric'] < PM_FLOOR:
        return f"soft path metric {d['path_metric']:.3f} below floor {PM_FLOOR}"
    return None


def _front_end_evidence(y):
    """Per-front-end evidence logged for acceptance rules.

    active_symbols: end of the transmission, the split point minimising the squared error of a
      two-level fit to |y|² (assumes the burst starts at the capture start).
    bpsk_presence_log10p: with w = y², non-overlapping pairs v = w(2m+1)·conj(w(2m)) have
      Re(v) > 0 for BPSK (w keeps one phase up to slow drift) and a fair-coin sign for QPSK
      (w = ±j·a² flips with the data). Exact one-sided binomial p of the positive count;
      phase-frame free and insensitive to residual CFO.
    bpsk_contradiction_log10p: if the signal were BPSK with the M2M4-estimated S, N, each w has
      Re(w) > 0 with p1 ≈ Φ(√S/√(2N + N²/2S)), so Re(v) > 0 with q = p1² + (1−p1)²; lower-tail
      binomial p of the observed positive count."""
    e = np.abs(y) ** 2
    L = len(e)
    c1, c2 = np.cumsum(e), np.cumsum(e * e)
    k = np.arange(MIN_SYMBOLS, L + 1)
    head = c2[k - 1] - c1[k - 1] ** 2 / k
    tail_n = L - k
    tail = np.where(tail_n > 0, (c2[-1] - c2[k - 1]) - (c1[-1] - c1[k - 1]) ** 2 / np.maximum(tail_n, 1), 0.0)
    active = int(k[np.argmin(head + tail)]) if len(k) else L
    ya = y[:active]
    w = ya ** 2
    m = len(w) // 2
    v = w[1:2 * m:2] * np.conj(w[0:2 * m:2])
    pos = int(np.count_nonzero(np.real(v) > 0))
    presence = float(bdtrc(pos - 1, m, 0.5)) if pos > 0 else 1.0
    S, N = symbol_snr_m2m4(ya)
    p1 = float(ndtr(np.sqrt(S) / np.sqrt(2 * N + N * N / (2 * S + 1e-30)))) if S > 0 else 0.5
    q = max(p1 * p1 + (1 - p1) ** 2, 0.5)
    contradiction = float(bdtr(pos, m, q))
    return {'active_symbols': active,
            'bpsk_presence_log10p': float(np.log10(max(presence, 1e-300))),
            'bpsk_contradiction_log10p': float(np.log10(max(contradiction, 1e-300)))}


def _decode_both_polarities(llrs, code, dims):
    """Viterbi (zero start state) on the LLRs and on their complement; keep the better path."""
    a = decode_hypothesis(llrs, code, dims)
    b = decode_hypothesis(-np.asarray(llrs), code, dims)
    best = b if b['path_metric'] > a['path_metric'] else a
    return dict(best, flip=np.pi if best is b else 0.0)


def _cfo_candidates(iq, pad=16):
    """CFO candidates from spectral lines of x² (BPSK) and x⁴ (BPSK and QPSK).

    For noise, unpadded periodogram bins in the band are ~Exp(mean floor); floor is
    estimated as median/ln2. A peak of ratio γ over B band bins has
    p = P(max of B Exp(1) ≥ γ) = 1 − (1 − e^−γ)^B, Bonferroni-doubled for the two spectra.
    Returns (candidates sorted by p, detection log10 p of the strongest line)."""
    N = len(iq)
    cands = []
    for order in (2, 4):
        x = iq ** order
        band = order * CFO_MAX
        f = np.fft.fftfreq(N)
        inband = np.abs(f) <= band
        B = int(inband.sum())
        if B < 3:
            continue
        floor = np.median(np.abs(np.fft.fft(x)[inband]) ** 2) / np.log(2) + 1e-300
        fp = np.fft.fftfreq(pad * N)
        P = np.abs(np.fft.fft(x, pad * N)) ** 2
        P[np.abs(fp) > band] = 0
        peaks = np.flatnonzero((P > np.roll(P, 1)) & (P >= np.roll(P, -1)) & (P > 0))
        for k in peaks[np.argsort(-P[peaks])][:N_CFO_PER_ORDER]:
            ratio = P[k] / floor
            p = -np.expm1(B * np.log1p(-np.exp(-ratio)))
            cands.append({'cfo': float(fp[k] / order), 'order': order,
                          'peak_to_floor_db': float(10 * np.log10(ratio)),
                          'log10_p': float(min(np.log10(max(p, 1e-300)) + np.log10(2), 0.0))})
    cands.sort(key=lambda c: c['log10_p'])
    merged = []
    for c in cands:   # x² and x⁴ lines of one BPSK signal give the same CFO
        if all(abs(c['cfo'] - m['cfo']) > 1 / (8 * N) for m in merged):
            merged.append(c)
    return merged, (merged[0]['log10_p'] if merged else 0.0)


def _sps_table(iq):
    """Lag-1 correlation of y⁴ (both PSKs) and y² (BPSK only) at every sps in the domain."""
    rows = []
    for s in range(SPS_RANGE[0], SPS_RANGE[1] + 1):
        if len(iq) // s < MIN_SYMBOLS:
            break
        y = matched_filter_demod(iq, rrc_filter(RX_BETA, s), s)
        rows.append({'sps': s, 'n_symbols': len(iq) // s,
                     'q4': lag1_correlation(y ** 4), 'q2': lag1_correlation(y ** 2)})
    return rows


def _sps_candidates(sps_table, raw_sps):
    """Best N_SPS_RANKED sps by q4, each followed by its integer divisors, then the raw
    spectral estimate. The true sps's multiples also score high, so divisors are always
    tested; the code test decides between them."""
    valid = {r['sps'] for r in sps_table}
    out = []
    for r in sorted(sps_table, key=lambda r: -r['q4'])[:N_SPS_RANKED]:
        for d in [r['sps']] + [d for d in range(r['sps'] - 1, 1, -1) if r['sps'] % d == 0]:
            if d in valid and d not in out:
                out.append(d)
    raw = int(round(raw_sps))
    if raw in valid and raw not in out:
        out.append(raw)
    return out


def _modulation_stat(row):
    """BPSK evidence at one sps: y² is data-free for BPSK (q2 ≈ q4) and random for QPSK
    (q2 ≈ 0), so ratio = q2/q4 sits near 1 or 0; 0.5 is the midpoint decision."""
    ratio = row['q2'] / (row['q4'] + 1e-12)
    return {'sps': row['sps'], 'q2': row['q2'], 'q4': row['q4'], 'bpsk_ratio': float(ratio),
            'decision': 'BPSK' if ratio > 0.5 else 'QPSK', 'margin': float(abs(ratio - 0.5))}


def _signal_front(cfo_cands, sps_table, o):
    """Front-end used when a signal is detected but no code is accepted: strongest CFO line,
    smallest divisor sps whose quality is within 2σ (σ ≈ 1/√n_symbols) of the best,
    modulation from the q2/q4 ratio at that sps."""
    if not sps_table or (not cfo_cands and 'cfo' not in o):
        return None
    best = max(sps_table, key=lambda r: r['q4'])
    chosen = best
    for r in sps_table:
        if r['sps'] < best['sps'] and best['sps'] % r['sps'] == 0 \
                and r['q4'] >= best['q4'] - 2 / np.sqrt(r['n_symbols']):
            chosen = r
            break
    if 'sps' in o:
        chosen = next((r for r in sps_table if r['sps'] == int(o['sps'])), chosen)
    return {'cfo': float(o['cfo']) if 'cfo' in o else cfo_cands[0]['cfo'],
            'sps': chosen['sps'],
            'modulation': o.get('modulation', _modulation_stat(chosen)['decision'])}


def _hard_bits(iq, front, beta):
    """Uncoded hard decisions for the SIGNAL_NO_CODE front-end (polarity unresolved)."""
    y = matched_filter_demod(iq * np.exp(-2j * np.pi * front['cfo'] * np.arange(len(iq))),
                             rrc_filter(beta, front['sps']), front['sps'])
    y = y * np.exp(-1j * estimate_carrier_phase(y, front['modulation']))
    return (psk_llrs(y, front['modulation'], 1.0, 1.0) < 0).astype(np.uint8)
