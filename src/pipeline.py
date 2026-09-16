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
from modem import load_iq, rrc_filter
from analyze import (estimate_symbol_rate, lag1_correlation, estimate_carrier_phase,
                     matched_filter_demod, symbol_snr_m2m4, psk_llrs)
from blind_id import (CODE_CATALOGUE, interleaver_candidates, deinterleave_index,
                      syndrome_checks, sign_test_log10p, decode_hypothesis)

# ---- Receiver search domain: a front-end specification, independent of any dataset ----
SPS_RANGE = (2, 20)     # integer samples/symbol → symbol rates fs/20 … fs/2
MIN_SYMBOLS = 16        # an sps candidate must yield at least this many symbols
CFO_MAX = 0.0125        # |carrier offset| ≤ 1.25 % of fs (assumed front-end tuning accuracy)
RX_BETA = 0.3           # one RRC matched filter, mid-range of the common 0.1–0.5 roll-offs
N_SPS_RANKED = 3        # compute budget: best sps by quality (their divisors are added)
N_CFO_PER_ORDER = 3     # compute budget: strongest x² and x⁴ spectral peaks
ALPHA = 0.01            # target false-accept probability per file under the null
MODULATIONS = ('BPSK', 'QPSK')


def analyze_file(filename, fs=1e6, verbose=False):
    """Blind analysis of an interleaved-float32 .iq file."""
    return analyze_iq(load_iq(filename), fs=fs)


def analyze_iq(iq, fs=1e6, _oracle=None):
    """Blind analysis of complex baseband samples.

    `_oracle` is evaluation-only (eval/ladder.py): ground-truth values that replace the
    corresponding estimates (keys: modulation, sps, cfo, beta, timing_offset, phase,
    interleaver). Normal inference never passes it; acceptance is never oracled."""
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

    fronts = []
    hyp = {k: [] for k in ('front', 'code', 'rows', 'cols', 'n', 'pos', 'sum', 'sq')}
    for cfo in cfo_list:
        iq_c = iq * np.exp(-2j * np.pi * cfo * n)
        for s in sps_list:
            t = time.perf_counter()
            y = matched_filter_demod(iq_c, rrc_filter(beta, s), s)
            timers['matched_filter'] += time.perf_counter() - t
            if len(y) < MIN_SYMBOLS:
                continue
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
                    th = np.tanh(np.clip(llrs, -40, 40) / 2)
                    fi = len(fronts)
                    fronts.append({'cfo': cfo, 'sps': s, 'modulation': mod, 'phase': phase,
                                   'rotation': rot, 'llrs': llrs,
                                   'symbol_snr_db': float(10 * np.log10(S / N + 1e-30))})
                    dims_list = ([tuple(o['interleaver'])] if 'interleaver' in o
                                 else interleaver_candidates(len(llrs)))
                    for rows, cols in dims_list:
                        if rows * cols > len(llrs):
                            continue
                        d = th[:rows * cols][deinterleave_index(rows, cols)]
                        for ci, code in enumerate(CODE_CATALOGUE):
                            chk = syndrome_checks(d, code)
                            if len(chk) == 0:
                                continue
                            for key, val in (('front', fi), ('code', ci), ('rows', rows),
                                             ('cols', cols), ('n', len(chk)),
                                             ('pos', int(np.count_nonzero(chk > 0))),
                                             ('sum', float(chk.sum())),
                                             ('sq', float(np.dot(chk, chk)))):
                                hyp[key].append(val)
                    timers['syndrome_search'] += time.perf_counter() - t

    t = time.perf_counter()
    M = len(hyp['n'])
    top, accepted, best_log10p, runner_margin = [], False, 0.0, None
    log10_threshold = float(np.log10(ALPHA / max(M, 1)))
    if M:
        log10p = sign_test_log10p(np.array(hyp['pos']), np.array(hyp['n']))
        z = np.array(hyp['sum']) / np.sqrt(np.maximum(np.array(hyp['sq']), 1e-300))
        order = np.lexsort((-z, log10p))
        best_log10p = float(log10p[order[0]])
        accepted = best_log10p <= log10_threshold
        best_key = (hyp['code'][order[0]], hyp['rows'][order[0]], hyp['cols'][order[0]])
        for k in order[1:]:
            if (hyp['code'][k], hyp['rows'][k], hyp['cols'][k]) != best_key:
                runner_margin = float(log10p[k] - best_log10p)
                break
    timers['scoring'] += time.perf_counter() - t
    if M:
        for k in order[:5]:
            fr = fronts[hyp['front'][k]]
            code = CODE_CATALOGUE[hyp['code'][k]]
            dims = (hyp['rows'][k], hyp['cols'][k])
            t = time.perf_counter()
            dec = _decode_both_polarities(fr['llrs'], code, dims)
            timers['viterbi'] += time.perf_counter() - t
            n_steps = dims[0] * dims[1] // 2
            top.append({
                'code': code['name'], 'interleaver': list(dims), 'sps': fr['sps'],
                'cfo': fr['cfo'], 'modulation': fr['modulation'],
                'rotation': fr['rotation'] + dec['flip'], 'phase': fr['phase'],
                'symbol_snr_db': fr['symbol_snr_db'],
                'n_checks': int(hyp['n'][k]), 'n_positive': int(hyp['pos'][k]),
                'log10_p': float(log10p[k]), 'syndrome_z': float(z[k]),
                'covered_bits': dec['covered_bits'], 'total_observed_bits': len(fr['llrs']),
                'coverage_ratio': dec['covered_bits'] / len(fr['llrs']),
                'consistency': dec['consistency'], 'path_metric': dec['path_metric'],
                # MDL: a rate-1/2 code needs n_steps free bits instead of 2·n_steps, pays
                # the soft disagreement, and pays log2(M) to name the hypothesis.
                'mdl_savings_bits': float(n_steps - dec['soft_disagreement_nats'] / np.log(2)
                                          - np.log2(M)),
                'uncoded_mdl_savings_bits': 0.0,
                '_decoded_bits': dec['decoded_bits'],
            })

    signal_front = _signal_front(cfo_cands, sps_table, o)
    result = {
        'status': 'UNKNOWN', 'payload_bits': np.array([], dtype=np.uint8), 'code': None,
        'interleaver': None, 'modulation': None, 'sps': None, 'symbol_rate_est': None,
        'cfo': None, 'beta': beta, 'phase': None, 'rotation': None,
    }
    if accepted:
        # Several front-ends can pass the accepted (code, interleaver) equally: a QPSK π/2
        # rotation, or any complement (π), is still a codeword of these codes, only with a
        # nonzero encoder start state. The syndrome test cannot separate them; Viterbi assumes
        # start state 0 (a reset encoder at the start of the capture), so the best zero-start
        # path metric over front-ends and both polarities breaks the tie. Without that
        # assumption the ambiguity needs frame synchronisation.
        b = top[0]
        best_key = (hyp['code'][order[0]], hyp['rows'][order[0]], hyp['cols'][order[0]])
        for k in order[1:]:
            if log10p[k] > log10_threshold:
                break
            if (hyp['code'][k], hyp['rows'][k], hyp['cols'][k]) != best_key:
                continue
            fr = fronts[hyp['front'][k]]
            t = time.perf_counter()
            dec = _decode_both_polarities(fr['llrs'], CODE_CATALOGUE[best_key[0]], best_key[1:])
            timers['viterbi'] += time.perf_counter() - t
            if dec['path_metric'] > b['path_metric']:
                b = dict(b, _decoded_bits=dec['decoded_bits'], path_metric=dec['path_metric'],
                         sps=fr['sps'], cfo=fr['cfo'], modulation=fr['modulation'],
                         phase=fr['phase'], rotation=fr['rotation'] + dec['flip'])
        result.update(status='DECODED', payload_bits=b['_decoded_bits'], code=b['code'],
                      interleaver=b['interleaver'], modulation=b['modulation'], sps=b['sps'],
                      symbol_rate_est=fs / b['sps'], cfo=b['cfo'], phase=b['phase'],
                      rotation=b['rotation'])
    elif detection_log10p <= np.log10(ALPHA) and signal_front:
        result.update(status='SIGNAL_NO_CODE', symbol_rate_est=fs / signal_front['sps'],
                      **signal_front)
        result['payload_bits'] = _hard_bits(iq, signal_front, beta)
    for h in top:
        h.pop('_decoded_bits')

    result['accept'] = {'log10_p': best_log10p, 'log10_threshold': log10_threshold,
                        'n_hypotheses': M, 'alpha': ALPHA}
    result['diagnostics'] = {
        'cfo_candidates': cfo_cands, 'detection_log10_p': float(detection_log10p),
        'raw_sps_estimate': float(raw_sps), 'sps_table': sps_table,
        'sps_candidates': [int(s) for s in sps_list],
        'modulation_stats': [_modulation_stat(r) for r in sps_table if r['sps'] in sps_list],
        'top_hypotheses': top, 'runner_up_margin_log10': runner_margin,
        'n_front_ends': len(fronts), 'timers_s': timers,
    }
    result['runtime'] = time.perf_counter() - t_start
    return result


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
