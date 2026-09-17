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
symbol_rate_norm, fs_hz, fs_source, cfo, beta, phase, rotation,
accept{log10_p, log10_threshold, n_hypotheses, alpha},
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
from blind_id import CODE_CATALOGUE, syndrome_scan, sign_test_log10p, decode_hypothesis, as_spec
import rs
import interleavers
import stream
import framing
import blockcode
import constellations

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
MODULATIONS = ('BPSK', 'QPSK')          # always searched
GATED_MODULATIONS = ('8PSK', '16QAM')   # catalogue v1 §12.1, gated and OFF BY DEFAULT — see below
# EXPERIMENTAL (Constitution §24): searching 8PSK and 16-QAM is implemented and gated, but it is not
# in the default path. Measured cost of enabling it (reports/SIH_READINESS_EXECUTION.md, Phase 10
# step 5): on a weak or short burst the QPSK y⁴ signature is not significant because the capture is
# weak, so the gate opens on captures that carry no higher-modulation evidence, M₁ grows from ~25,000
# to ~245,000, and the tightened bar cost bench-v1 sealed 5 of 30 files, one null file was falsely
# accepted (1/900) and one K5 file was decoded wrongly. Putting it in the default path needs a
# Constitution amendment (an F1 sub-weight split and a gate with a power condition), so until then
# the default engine searches BPSK/QPSK only and every guarantee in §18–§19 refers to that path.
SEARCH_HIGHER_MODULATIONS = False
INTERLEAVER_TYPES = interleavers.TYPES   # block, diagonal, Forney convolutional, LTE QPP (§12.1)
# Pre-registered acceptance-family weights (Constitution v2.5 §13.1; amendment only, never fitted).
# A family's per-hypothesis bar is p <= ALPHA * weight / M_family, and the weights sum to 1, so the
# union bound still gives P(any false structural claim on a file) <= ALPHA.
FAMILY_WEIGHTS = {'F1_burst_code': 0.50, 'F2_stream_code': 0.10,
                  'F3_frame': 0.20, 'F4_block_code': 0.20}
F3_FRONT_ENDS = 3       # compute budget: (sps, modulation) classes by symbol SNR entering the frame search
F3_MAX_STREAMS = 12     # compute budget: bit streams the frame search may test in one analysis
# Front-end serial-dependence gate: the agreement rate of neighbouring hard decisions that a front
# end may not significantly exceed. 0.60 is a declared receiver spec with a physical basis, not a
# fitted value: a 2x oversampled front end repeats every symbol and so agrees on ~75% of pairs (~83%
# at 3x), while genuinely framed data biases the rate by only a few percent.
SERIAL_AGREEMENT_MAX = 0.60


FS_SOURCES = ('declared', 'wav_header', 'inferred', 'relative_only', 'unavailable')


def analyze_file(filename, fs=None, verbose=False, fs_source=None):
    """Blind analysis of an interleaved-float32 .iq file (a raw .iq file carries no sample rate)."""
    return analyze_iq(load_iq(filename), fs=fs, fs_source=fs_source)


@functools.lru_cache(maxsize=256)
def rrc_filter(beta, sps):
    """modem.rrc_filter is a per-tap Python loop; the receiver asks for the same few filters thousands
    of times. Cached copy is read-only so no caller can alter a shared filter."""
    h = _rrc_filter(beta, sps)
    h.setflags(write=False)
    return h


def analyze_iq(iq, fs=None, _oracle=None, _top_k=5, _keep_bits=False, _all_hypotheses=False,
               fs_source=None, search_higher_modulations=None):
    """Blind analysis of complex baseband samples.

    `fs` is the absolute sample rate in Hz, or None when it is not known. Every decision is made
    in normalised units (samples per symbol, cycles per sample), so a missing sample rate never
    changes the verdict; it only means no absolute rate (Hz) is reported. `fs_source` records
    where fs came from (FS_SOURCES); it defaults to 'declared' when fs is given, else 'unavailable'.

    `search_higher_modulations` turns the EXPERIMENTAL 8PSK / 16-QAM search on for this call
    (default: SEARCH_HIGHER_MODULATIONS, i.e. off). With it off, the gates are still measured and
    reported in diagnostics.modulation_gates, and no hypothesis of those modulations is tested.

    `_oracle` is evaluation-only (eval/ladder.py): ground-truth values that replace the
    corresponding estimates (keys: modulation, sps, cfo, beta, timing_offset, phase,
    interleaver, exclude_interleaver). Normal inference never passes it; acceptance is
    never oracled. `_top_k` / `_keep_bits` only widen the logged hypothesis list (eval)."""
    o = _oracle or {}
    if fs is not None and not (np.isfinite(fs) and fs > 0):
        raise ValueError(f'sample rate must be a positive number of Hz, got {fs!r}')
    fs_source = fs_source or ('declared' if fs is not None else 'unavailable')
    if fs_source not in FS_SOURCES:
        raise ValueError(f'fs_source must be one of {FS_SOURCES}')
    higher = (SEARCH_HIGHER_MODULATIONS if search_higher_modulations is None
              else bool(search_higher_modulations))
    timers = dict.fromkeys(['cfo', 'sps', 'matched_filter', 'syndrome_search',
                            'viterbi', 'scoring', 'stream_search', 'frame_search',
                            'block_code_search'], 0.0)
    t_start = time.perf_counter()
    iq = np.asarray(iq, dtype=complex)
    if 'timing_offset' in o:   # undo the generator's fractional delay exp(-j2πfτ)
        f = np.fft.fftfreq(len(iq))
        iq = np.fft.ifft(np.fft.fft(iq) * np.exp(2j * np.pi * f * o['timing_offset']))
    n = np.arange(len(iq))

    t = time.perf_counter()
    cfo_cands, detection_log10p = _cfo_candidates(iq, orders=(2, 4, 8) if higher else (2, 4))
    cfo_list = [float(o['cfo'])] if 'cfo' in o else [c['cfo'] for c in cfo_cands]
    timers['cfo'] += time.perf_counter() - t

    t = time.perf_counter()
    sps_table = _sps_table(iq, higher=higher)
    # Always in normalised units: welch's frequency grid in Hz rounds differently at the band edges
    # (e.g. the Nyquist bin), which made the candidate set depend on the declared rate.
    raw_rate, _ = estimate_symbol_rate(iq, 1.0, SPS_RANGE)
    raw_sps = 1.0 / raw_rate
    sps_list = [int(o['sps'])] if 'sps' in o else _sps_candidates(sps_table, raw_sps, higher=higher)
    timers['sps'] += time.perf_counter() - t
    mods = [o['modulation']] if 'modulation' in o else list(MODULATIONS)
    # The modulation gates are decided once per capture, on the symbol stream of the strongest
    # symbol-rate candidate (see _modulation_gates), not per front end.
    beta = float(o.get('beta', RX_BETA))
    gates = _modulation_gates(iq, sps_table, cfo_list, beta, higher)
    gated_mods = ([] if 'modulation' in o or not higher
                  else [m for m in GATED_MODULATIONS if gates[m]['searched']])

    fronts, rejected_serial = [], 0
    hyp_parts, spec_ids = [], {}
    for cfo in cfo_list:
        iq_c = iq * np.exp(-2j * np.pi * cfo * n)
        for s in sps_list:
            t = time.perf_counter()
            y = matched_filter_demod(iq_c, rrc_filter(beta, s), s)
            timers['matched_filter'] += time.perf_counter() - t
            if len(y) < MIN_SYMBOLS:
                continue
            span = _front_end_evidence(y)
            for mod in mods + gated_mods:
                higher = mod in GATED_MODULATIONS
                if higher:
                    phase = constellations.carrier_phase(y, mod)
                    ys = y * np.exp(-1j * phase)
                    S, N = constellations.symbol_snr(ys, mod)
                else:
                    phase = float(o['phase']) if 'phase' in o else estimate_carrier_phase(y, mod)
                    ys = y * np.exp(-1j * phase)
                    S, N = symbol_snr_m2m4(ys)
                # QPSK: rotations 0 and π/2; π and 3π/2 only complement all bits, which
                # every parity check of the catalogue codes (odd-weight generators) ignores.
                # 8PSK and 16-QAM have no such symmetry, so every rotation of the mapping is a
                # separate hypothesis (constellations.ROTATIONS).
                rots = (list(constellations.ROTATIONS[mod]) if higher else
                        [0.0] if (mod == 'BPSK' or 'phase' in o) else [0.0, np.pi / 2])
                for rot in rots:
                    t = time.perf_counter()
                    llrs = (constellations.llrs(ys * np.exp(-1j * rot), mod, S, N) if higher
                            else psk_llrs(ys * np.exp(-1j * rot), mod, S, N))
                    # The syndrome null needs serially independent hard decisions. A front end that
                    # oversamples the signal (sps too small) repeats each symbol, which biases short
                    # parity checks: at 2x oversampling every second neighbouring pair is the same
                    # symbol, so about 75% of pairs agree (83% at 3x). Reject a front end only when
                    # its neighbouring decisions agree significantly more often than
                    # SERIAL_AGREEMENT_MAX — a composite null, not "more than half the time".
                    # Real framed data (a sync marker repeating every frame) gives a small genuine
                    # dependence of a few percent; over a long stream that is highly significant
                    # against 1/2, and testing against 1/2 therefore discarded the *coherent* front
                    # end of a framed stream and kept an off-frequency one (whose polarity flips in
                    # segments). Measured in reports/SIH_READINESS_EXECUTION.md (Phase 10 step 3).
                    step = constellations.BITS_PER_SYMBOL[mod]
                    same = np.count_nonzero((llrs[step:] < 0) == (llrs[:-step] < 0))
                    n_pairs = len(llrs) - step
                    if float(np.log10(max(bdtrc(same - 1, n_pairs, SERIAL_AGREEMENT_MAX), 1e-300))
                             if same > 0 else 0.0) <= np.log10(ALPHA):
                        rejected_serial += 1
                        timers['syndrome_search'] += time.perf_counter() - t
                        continue
                    th = np.tanh(np.clip(llrs, -40, 40) / 2)
                    fi = len(fronts)
                    fronts.append({'cfo': cfo, 'sps': s, 'modulation': mod, 'phase': phase,
                                   'rotation': rot, 'llrs': llrs, 'th': th,
                                   'symbol_snr_db': float(10 * np.log10(S / N + 1e-30)), **span})
                    spec_list = ([as_spec(o['interleaver'])] if 'interleaver' in o
                                 else interleavers.candidates(len(llrs), INTERLEAVER_TYPES))
                    if 'exclude_interleaver' in o:
                        spec_list = [s for s in spec_list if s != as_spec(o['exclude_interleaver'])]
                    # All interleaver x code hypotheses of this front end in one vectorised pass
                    # (blind_id.syndrome_scan; identical check signs to the per-pair loop).
                    scan = syndrome_scan(th, spec_list)
                    scan['front'] = np.full(len(scan['n']), fi)
                    # Global spec ids, so one interleaver is the same key on every front end.
                    scan['spec'] = np.array([spec_ids.setdefault(scan['specs'][i], len(spec_ids))
                                             for i in scan['spec']], dtype=np.int64)
                    hyp_parts.append(scan)
                    timers['syndrome_search'] += time.perf_counter() - t

    t = time.perf_counter()
    hyp = {k: (np.concatenate([p[k] for p in hyp_parts]) if hyp_parts else np.zeros(0, dtype=int))
           for k in ('front', 'code', 'spec', 'n', 'pos', 'sum', 'sq')}
    specs = sorted(spec_ids, key=spec_ids.get)
    M = len(hyp['n'])
    top, best_log10p, runner_margin, rejected = [], 0.0, None, []
    log10_threshold = float(np.log10(ALPHA * FAMILY_WEIGHTS['F1_burst_code'] / max(M, 1)))
    described = {}

    def describe(k):
        """Decode hypothesis k and collect every score the UI and acceptance rules use."""
        if k in described:
            return described[k]
        fr = fronts[int(hyp['front'][k])]
        code = CODE_CATALOGUE[int(hyp['code'][k])]
        spec = specs[int(hyp['spec'][k])]
        t0 = time.perf_counter()
        dec = _decode_both_polarities(fr['llrs'], code, spec)
        timers['viterbi'] += time.perf_counter() - t0
        n_steps = interleavers.n_coded(spec, len(fr['llrs'])) // 2
        d = {
            'code': code['name'], 'interleaver': _interleaver_field(spec),
            'interleaver_spec': interleavers.describe(spec), 'sps': fr['sps'],
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
            'covered_symbols': dec['covered_bits'] / constellations.BITS_PER_SYMBOL[fr['modulation']],
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
        ref_key = (hyp['code'][ref], hyp['spec'][ref])
        for k in order:
            if (hyp['code'][k], hyp['spec'][k]) != ref_key:
                runner_margin = float(log10p[k] - log10p[ref])
                break
    timers['scoring'] += time.perf_counter() - t
    accepted = accepted_k is not None
    if M:
        top = [describe(k) for k in order[:_top_k]]

    t = time.perf_counter()
    f2 = _stream_family(fronts)
    timers['stream_search'] += time.perf_counter() - t

    t = time.perf_counter()
    f2_bits = None
    if f2['accepted']:
        b2 = f2['accepted_hypothesis']
        f2_decode = stream.decode(fronts[b2['front']]['llrs'], b2['offset'], b2['g2_inverted'])
        b2.update({k: f2_decode[k] for k in ('covered_bits', 'path_metric', 'consistency',
                                             'polarity_flipped')})
        f2_bits = f2_decode['decoded_bits']
    f3_streams = _frame_streams(fronts, f2_bits)
    f3 = _frame_family(f3_streams)
    timers['frame_search'] += time.perf_counter() - t

    t = time.perf_counter()
    f4 = _block_code_family(f3_streams, f3, fronts)
    timers['block_code_search'] += time.perf_counter() - t

    signal_front = _signal_front(cfo_cands, sps_table, o)
    result = {
        'status': 'UNKNOWN', 'payload_bits': np.array([], dtype=np.uint8), 'code': None,
        'interleaver': None, 'interleaver_spec': None, 'modulation': None, 'sps': None,
        'symbol_rate_est': None,
        'symbol_rate_norm': None, 'fs_hz': float(fs) if fs is not None else None, 'fs_source': fs_source,
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
        acc_key = (hyp['code'][accepted_k], hyp['spec'][accepted_k])
        for k in order:
            if log10p[k] > log10_threshold:
                break
            if k == accepted_k or (hyp['code'][k], hyp['spec'][k]) != acc_key:
                continue
            d = describe(k)
            if d['structural_rejection'] is None and d['path_metric'] > b['path_metric']:
                b = d
        accepted_desc = {key: val for key, val in b.items() if key != '_decoded_bits'}
        result.update(status='DECODED', payload_bits=b['_decoded_bits'], code=b['code'],
                      interleaver=b['interleaver'], interleaver_spec=b['interleaver_spec'],
                      modulation=b['modulation'], sps=b['sps'],
                      symbol_rate_est=_rate_hz(fs, b['sps']), symbol_rate_norm=1.0 / b['sps'],
                      cfo=b['cfo'], phase=b['phase'],
                      rotation=b['rotation'])
    elif f4['accepted']:
        # DECODED through an outer block code (13.1 note 6): F4 alone (LDPC on a stream), or
        # F3+F4, or F2+F3+F4. The chain with the most accepted layers is the one reported.
        a4 = f4['accepted_hypothesis']
        fi = f3_streams[a4['stream']]['front']
        fr = fronts[fi] if fi is not None else None
        result.update(status='DECODED', payload_bits=f4['payload_bits'], code=a4['code'])
        if fr is not None:
            result.update(modulation=fr['modulation'], sps=fr['sps'], cfo=fr['cfo'],
                          phase=fr['phase'], rotation=fr['rotation'],
                          symbol_rate_est=_rate_hz(fs, fr['sps']), symbol_rate_norm=1.0 / fr['sps'])
        elif f2['accepted']:
            fr2 = fronts[int(f2['accepted_hypothesis']['front'])]
            result.update(modulation=fr2['modulation'], sps=fr2['sps'], cfo=fr2['cfo'],
                          phase=fr2['phase'], rotation=fr2['rotation'],
                          symbol_rate_est=_rate_hz(fs, fr2['sps']), symbol_rate_norm=1.0 / fr2['sps'])
    elif f2['accepted']:
        b = f2['accepted_hypothesis']
        fr = fronts[int(b['front'])]
        result.update(status='DECODED', payload_bits=f2_bits, code=stream.CODE_NAME,
                      modulation=fr['modulation'], sps=fr['sps'],
                      symbol_rate_est=_rate_hz(fs, fr['sps']), symbol_rate_norm=1.0 / fr['sps'],
                      cfo=fr['cfo'], phase=fr['phase'],
                      rotation=fr['rotation'] + (np.pi if b['polarity_flipped'] else 0.0))
    elif f3['accepted']:
        # A proven frame structure with no accepted code: the frame map is the evidence (13.1 note 6).
        fi = f3['accepted_hypothesis']['front']
        fr = fronts[fi] if fi is not None else None
        result.update(status='SIGNAL_NO_CODE', payload_bits=f3['accepted_bits'])
        if fr is not None:
            result.update(modulation=fr['modulation'], sps=fr['sps'], cfo=fr['cfo'],
                          phase=fr['phase'], rotation=fr['rotation'],
                          symbol_rate_est=_rate_hz(fs, fr['sps']), symbol_rate_norm=1.0 / fr['sps'])
    elif detection_log10p <= np.log10(ALPHA) and signal_front:
        result.update(status='SIGNAL_NO_CODE', symbol_rate_est=_rate_hz(fs, signal_front['sps']),
                      symbol_rate_norm=1.0 / signal_front['sps'],
                      **signal_front)
        result['payload_bits'] = _hard_bits(iq, signal_front, beta)
    for h in top:
        bits = h.pop('_decoded_bits', None)
        if _keep_bits and bits is not None:
            h['decoded_bits'] = bits.tolist()

    result['accept'] = {'log10_p': best_log10p, 'log10_threshold': log10_threshold,
                        'n_hypotheses': M, 'alpha': ALPHA, 'accepted_hypothesis': accepted_desc,
                        'significant_but_rejected': rejected,
                        'rules': {'bl_delta_symbols': BL_DELTA_SYMBOLS, 'pm_floor': PM_FLOOR},
                        'families': [{'name': 'F1_burst_code',
                                      'weight': FAMILY_WEIGHTS['F1_burst_code'],
                                      'tested_hypotheses': M, 'log10_threshold': log10_threshold,
                                      'best_log10_p': best_log10p, 'accepted': accepted},
                                     {'name': 'F2_stream_code',
                                      'weight': FAMILY_WEIGHTS['F2_stream_code'],
                                      'tested_hypotheses': f2['tested_hypotheses'],
                                      'log10_threshold': f2['log10_threshold'],
                                      'best_log10_p': f2['best_log10_p'],
                                      'accepted': f2['accepted']},
                                     {'name': 'F3_frame',
                                      'weight': FAMILY_WEIGHTS['F3_frame'],
                                      'tested_hypotheses': f3['tested_hypotheses'],
                                      'log10_threshold': f3['log10_threshold'],
                                      'best_log10_p': f3['best_log10_p'],
                                      'accepted': f3['accepted']},
                                     {'name': 'F4_block_code',
                                      'weight': FAMILY_WEIGHTS['F4_block_code'],
                                      'tested_hypotheses': f4['tested_hypotheses'],
                                      'log10_threshold': f4['log10_threshold'],
                                      'best_log10_p': f4['best_log10_p'],
                                      'accepted': f4['accepted']}],
                        'interleaver_types': list(INTERLEAVER_TYPES)}
    result['stream_code'] = {k: v for k, v in f2.items() if k != 'rows'}
    result['frame'] = {k: v for k, v in f3.items() if k != 'accepted_bits'}
    result['block_code'] = {k: v for k, v in f4.items() if k != 'payload_bits'}
    result['structure'] = _structure(result, f2, f3, f4)
    result['diagnostics'] = {
        'cfo_candidates': cfo_cands, 'detection_log10_p': float(detection_log10p),
        'raw_sps_estimate': float(raw_sps), 'sps_table': sps_table,
        'sps_candidates': [int(s) for s in sps_list],
        'modulation_stats': [_modulation_stat(r) for r in sps_table if r['sps'] in sps_list],
        'top_hypotheses': top, 'runner_up_margin_log10': runner_margin,
        'n_front_ends': len(fronts), 'front_ends_rejected_serial_dependence': rejected_serial,
        'modulation_gates': gates,
        'timers_s': timers,
    }
    if _all_hypotheses and M:
        result['diagnostics']['all_hypotheses'] = {
            'code': [CODE_CATALOGUE[c]['name'] for c in hyp['code'].tolist()],
            # rows/cols: block and diagonal dimensions (0 for other types); interleaver: display label
            'rows': [int(specs[i][1]) if specs[i][0] in ('block', 'diag') else 0 for i in hyp['spec'].tolist()],
            'cols': [int(specs[i][2]) if specs[i][0] in ('block', 'diag') else 0 for i in hyp['spec'].tolist()],
            'interleaver': [_interleaver_label(specs[i]) for i in hyp['spec'].tolist()],
            'sps': [fronts[f]['sps'] for f in hyp['front'].tolist()],
            'modulation': [fronts[f]['modulation'] for f in hyp['front'].tolist()],
            'cfo': [fronts[f]['cfo'] for f in hyp['front'].tolist()],
            'n_checks': hyp['n'].tolist(), 'n_positive': hyp['pos'].tolist(),
            'log10_p': [float(v) for v in log10p]}
    result['runtime'] = time.perf_counter() - t_start
    return result


def _stream_family(fronts):
    """Family F2: the continuous-stream sign test over every front end (stream.py).

    M2 counts every (front end x pair offset x G2 inversion) hypothesis tested, and the bar is
    ALPHA * w(F2) / M2 (Constitution v2.5 Section 13.1). The best hypothesis is accepted on the sign
    test alone, as pre-registered; the front end it belongs to has already passed the serial-
    independence check that the null model needs."""
    rows = []
    for i, fr in enumerate(fronts):
        for row in stream.scan(fr['th'], fr['modulation']):
            rows.append({'front': i, 'sps': fr['sps'], 'cfo': fr['cfo'],
                         'modulation': fr['modulation'], **row})
    M2 = len(rows)
    bar = float(np.log10(ALPHA * FAMILY_WEIGHTS['F2_stream_code'] / max(M2, 1)))
    best = min(rows, key=stream.rank) if rows else None
    acc = best if best is not None and best['log10_p'] <= bar else None
    return {'code': stream.CODE_NAME, 'tested_hypotheses': M2, 'log10_threshold': bar,
            'best_log10_p': best['log10_p'] if best else 0.0, 'accepted': acc is not None,
            'accepted_hypothesis': acc,
            'top': sorted(rows, key=stream.rank)[:5], 'rows': rows}


def _frame_streams(fronts, f2_bits):
    """Bit streams the frame family is tested on (13.1 note 4, hierarchical front-end selection).

    The Viterbi output of an accepted F2 stream hypothesis (a CCSDS chain frames the decoded bits),
    plus the hard decisions of the front ends of the F3_FRONT_ENDS best (sps, modulation) classes by
    symbol SNR, capped at F3_MAX_STREAMS streams.

    Every CFO candidate of a kept class is tested, not just the best by SNR: the M2M4 symbol SNR of a
    front end whose carrier offset is slightly wrong is the same to two decimals as the coherent one
    (it measures power, not coherence), so SNR cannot order them, while a frame marker only survives
    on the coherent one. Selecting by SNR alone tested an off-carrier front end of a framed stream
    and missed an ASM that was present at p = 10^-115.6. Only streams actually tested enter M3."""
    streams = []
    if f2_bits is not None and len(f2_bits):
        streams.append({'source': 'f2_viterbi_output', 'front': None,
                        'bits': np.asarray(f2_bits, dtype=np.uint8)})
    order = sorted(range(len(fronts)), key=lambda i: -fronts[i]['symbol_snr_db'])
    classes = []
    for i in order:
        key = (fronts[i]['sps'], fronts[i]['modulation'])
        if key not in classes:
            classes.append(key)
    keep = classes[:F3_FRONT_ENDS]
    for i in order:
        if len(streams) >= F3_MAX_STREAMS:
            break
        fr = fronts[i]
        if (fr['sps'], fr['modulation']) in keep:
            streams.append({'source': 'front_end_hard_bits', 'front': i,
                            'bits': (fr['llrs'] < 0).astype(np.uint8)})
    return streams


def _block_code_family(streams, f3, fronts):
    """Family F4: CCSDS Reed-Solomon behind an accepted catalogue marker, and TC LDPC (128,64) by
    codeword offset on every stream the frame family tested (blockcode.py).

    M4 counts every RS (E, I, Q, randomizer) hypothesis the frame period admits plus every LDPC
    (offset, randomizer) hypothesis on every stream, and the bar is ALPHA * w(F4) / M4. An RS
    hypothesis with a degenerate codeword is refused however small its p-value, because constant fill
    and idle carriers are codewords (13.1 note 5)."""
    rs_rows, ldpc_rows = [], []
    frame = f3['accepted_hypothesis']
    if frame is not None and frame['kind'] == 'catalogue_marker':
        for row in blockcode.rs_scan(streams[frame['stream']]['bits'], frame):
            rs_rows.append({**row, 'family': 'rs', 'stream': frame['stream']})
    for si, st in enumerate(streams):
        for row in blockcode.ldpc_scan(st['bits']):
            ldpc_rows.append({**row, 'family': 'ldpc', 'stream': si})
    rows = rs_rows + ldpc_rows
    M4 = len(rows)
    bar = float(np.log10(ALPHA * FAMILY_WEIGHTS['F4_block_code'] / max(M4, 1)))
    rows.sort(key=blockcode.rank)
    acc, rejected, payload = None, [], np.array([], dtype=np.uint8)
    for r in rows:
        if r['log10_p'] > bar:
            break
        if r.get('degenerate'):
            rejected.append({'code': r['code'], 'log10_p': r['log10_p'],
                             'structural_rejection': 'degenerate codeword: fewer than four distinct '
                                                     'symbols (constant fill or idle carrier)'})
            continue
        acc = r
        break
    if acc is not None:
        if acc['family'] == 'rs':
            payload = rs.symbols_to_bits(np.concatenate(acc['_info'])) if acc['_info'] else payload
        else:
            st = streams[acc['stream']]
            fi = st['front']
            # Every row of H has even weight, so a complemented codeword is a codeword: the LDPC
            # statistic cannot resolve a 180° phase flip. An accepted catalogue marker on the same
            # stream does resolve it (its polarity is part of the hypothesis); without one the payload
            # is reported with polarity_resolved = False and may be the complement of the truth.
            anchored = frame is not None and frame['stream'] == acc['stream']
            polarity = frame['polarity'] if anchored else None
            bits = 1 - st['bits'] if polarity == 'inverted' else st['bits']
            llrs = fronts[fi]['llrs'] if fi is not None else None
            if polarity == 'inverted' and llrs is not None:
                llrs = -np.asarray(llrs)
            dec = blockcode.ldpc_decode(bits, llrs, acc['offset'], acc['randomizer'])
            acc = {**acc, 'polarity': polarity or 'unresolved', 'polarity_resolved': anchored}
            acc = {**acc, 'decode': {k: v for k, v in dec.items()
                                     if k not in ('info_bits', 'converged_codewords')},
                   'converged_codewords': dec['converged_codewords']}
            payload = dec['info_bits']
    return {'tested_hypotheses': M4, 'log10_threshold': bar,
            'best_log10_p': rows[0]['log10_p'] if rows else 0.0,
            'accepted': acc is not None,
            'accepted_hypothesis': {k: v for k, v in acc.items() if k != '_info'} if acc else None,
            'significant_but_rejected': rejected,
            'rs_hypotheses': len(rs_rows), 'ldpc_hypotheses': len(ldpc_rows),
            'top': [{k: v for k, v in r.items() if k != '_info'} for r in rows[:5]],
            'payload_bits': payload}


def _structure(result, f2, f3, f4):
    """The layered structure claimed for this capture, one entry per accepted layer."""
    layers = []
    if result['code'] and result['interleaver_spec']:
        layers.append({'layer': 'burst_code', 'code': result['code'],
                       'interleaver': result['interleaver_spec']})
    if f2['accepted']:
        a = f2['accepted_hypothesis']
        layers.append({'layer': 'stream_code', 'code': stream.CODE_NAME,
                       'g2_inverted': a['g2_inverted'], 'pair_offset': a['offset'],
                       'check_agreement': a['agreement']})
    if f3['accepted']:
        a = f3['accepted_hypothesis']
        layers.append({'layer': 'frame', 'kind': a['kind'], 'marker': a['marker'],
                       'period_bits': a['period_bits'], 'offset_bits': a['offset_bits'],
                       'polarity': a['polarity'], 'n_frames': a['n_frames'], 'map': f3['map']})
    if f4['accepted']:
        a = f4['accepted_hypothesis']
        layers.append({'layer': 'block_code', 'code': a['code'], 'randomizer': a['randomizer'],
                       **({'E': a['E'], 'I': a['I'], 'Q': a['Q'], 'n_codewords': a['n_codewords'],
                           'n_decoded': a['n_decoded'], 'symbol_errors': a['symbol_errors']}
                          if a['family'] == 'rs' else
                          {'offset': a['offset'], 'n_codewords': a['n_codewords'],
                           'satisfied_checks': a['satisfied_checks'],
                           'total_checks': a['total_checks']})})
    return {'modulation': result['modulation'], 'sps': result['sps'], 'layers': layers}


def _frame_family(streams):
    """Family F3: catalogue markers and blind constant fields over the declared frame domain.

    M3 sums framing.family_domain(n) over every stream tested, so the bar covers the whole declared
    domain (period x offset x marker/width x polarity), not only the hypotheses that were evaluated.
    Candidates are walked in p-value order and the first that also passes framing.structural_rejection
    is accepted."""
    M3 = sum(framing.family_domain(len(st['bits'])) for st in streams)
    bar = float(np.log10(ALPHA * FAMILY_WEIGHTS['F3_frame'] / max(M3, 1)))
    cands = []
    for si, st in enumerate(streams):
        found = [framing.marker_search(st['bits'], name) for name in framing.MARKERS]
        found.append(framing.blind_search(st['bits']))
        for c in found:
            if c is not None:
                cands.append({**c, 'stream': si, 'source': st['source'], 'front': st['front']})
    cands.sort(key=lambda c: (c['log10_p'], c['period_bits']))
    acc, rejected = None, []
    # Among candidates that clear the bar, a catalogue marker is preferred over a blind constant
    # field: it is the more specific claim (it names the standard and its polarity), and a blind
    # window overlapping the same marker can reach a smaller p-value simply by being wider.
    for c in sorted((c for c in cands if c['log10_p'] <= bar),
                    key=lambda c: (c['kind'] != 'catalogue_marker', c['log10_p'], c['period_bits'])):
        why = framing.structural_rejection(c, streams[c['stream']]['bits'])
        if why is None:
            acc = c
            break
        rejected.append({**{k: c[k] for k in ('kind', 'marker', 'period_bits', 'offset_bits',
                                              'n_frames', 'log10_p', 'source')},
                         'structural_rejection': why})
    out = {'tested_hypotheses': M3, 'log10_threshold': bar,
           'best_log10_p': cands[0]['log10_p'] if cands else 0.0,
           'accepted': acc is not None, 'accepted_hypothesis': acc,
           'significant_but_rejected': rejected,
           'candidates': [{k: c[k] for k in ('kind', 'marker', 'period_bits', 'offset_bits',
                                             'polarity', 'n_frames', 'log10_p', 'source')}
                          for c in cands[:5]],
           'streams_tested': [{'source': st['source'], 'front': st['front'], 'bits': len(st['bits']),
                               'domain': framing.family_domain(len(st['bits']))} for st in streams],
           'map': None, 'accepted_bits': np.array([], dtype=np.uint8)}
    if acc is not None:
        bits = streams[acc['stream']]['bits']
        out['map'] = framing.frame_map(bits, acc['period_bits'], acc['offset_bits'], acc['marker_bits'])
        out['accepted_bits'] = bits
    return out


def _rate_hz(fs, sps):
    """Symbol rate in Hz, or None when the absolute sample rate is not established."""
    return None if fs is None else float(fs) / sps


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


def _modulation_gates(iq, sps_table, cfo_list, beta, enabled=False):
    """Which catalogue modulations beyond BPSK/QPSK this capture may search (§12.1).

    8PSK is searched only when the QPSK y^4 signature is NOT significant (a significant signature
    says the symbols are BPSK or QPSK, so an 8PSK hypothesis is contradicted), and 16-QAM only when
    constant modulus IS contradicted. Both statistics are free of the carrier phase.

    The decision is made **once per capture**, on the symbol stream of the strongest symbol-rate
    candidate (largest y^4 lag-1 correlation) at the strongest CFO candidate. Gating per front end
    was measured to be wrong: at a wrong sps the matched-filter output is not the symbol stream, its
    y^4 signature is not significant and its amplitudes are spread by ISI, so both gates open on
    aliases of a plain QPSK capture. That multiplied M1 by about ten and cost bench-v1 sealed
    11 of 30 files (reports/SIH_READINESS_EXECUTION.md, Phase 10 step 5)."""
    log_alpha = float(np.log10(ALPHA))
    out = {m: {'searched': False, 'enabled': enabled} for m in GATED_MODULATIONS}
    if not sps_table or not cfo_list:
        return out
    best = max(sps_table, key=lambda r: r['q4'])
    y = matched_filter_demod(iq * np.exp(-2j * np.pi * cfo_list[0] * np.arange(len(iq))),
                             rrc_filter(beta, best['sps']), best['sps'])
    sig = constellations.qpsk_signature_log10p(y)
    cm = constellations.constant_modulus_contradiction_log10p(y)
    return {'8PSK': {'searched': bool(sig > log_alpha) and enabled, 'enabled': enabled,
                     'qpsk_signature_log10p': sig, 'sps': best['sps'],
                     'gate': 'searched unless the QPSK y^4 signature is significant'},
            '16QAM': {'searched': bool(cm <= log_alpha) and enabled, 'enabled': enabled,
                      'constant_modulus_contradiction_log10p': cm, 'sps': best['sps'],
                      'gate': 'searched only when constant modulus is contradicted'}}


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


def _interleaver_field(spec):
    """Legacy `interleaver` result field: [rows, cols] for block interleavers, None for other types
    (their parameters are in `interleaver_spec`)."""
    return [int(spec[1]), int(spec[2])] if spec[0] == 'block' else None


def _interleaver_label(spec):
    d = interleavers.describe(spec)
    if spec[0] == 'block':
        return f"{d['rows']}×{d['cols']}"
    if spec[0] == 'diag':
        return f"diag {d['rows']}×{d['cols']}"
    if spec[0] == 'conv':
        return f"conv B{d['branches']} D{d['delay_unit']}"
    return f"QPP K{d['K']}"


def _decode_both_polarities(llrs, code, spec):
    """Viterbi (zero start state) on the LLRs and on their complement; keep the better path."""
    a = decode_hypothesis(llrs, code, spec)
    b = decode_hypothesis(-np.asarray(llrs), code, spec)
    best = b if b['path_metric'] > a['path_metric'] else a
    return dict(best, flip=np.pi if best is b else 0.0)


def _cfo_candidates(iq, pad=16, orders=(2, 4)):
    """CFO candidates from spectral lines of x² (BPSK) and x⁴ (BPSK and QPSK).

    For noise, unpadded periodogram bins in the band are ~Exp(mean floor); floor is
    estimated as median/ln2. A peak of ratio γ over B band bins has
    p = P(max of B Exp(1) ≥ γ) = 1 − (1 − e^−γ)^B, Bonferroni-corrected over the spectra used.
    Returns (candidates sorted by p, detection log10 p of the strongest line).

    With the EXPERIMENTAL higher modulations enabled, x⁸ is added: for 8PSK the x² and x⁴ lines are
    data-dependent (s⁴ = ±1), so the carrier offset of an 8PSK capture is not among the candidates
    and no coherent front end is ever built. x⁸ is data-free for 8PSK."""
    N = len(iq)
    cands = []
    for order in orders:
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
                          'log10_p': float(min(np.log10(max(p, 1e-300))
                                              + np.log10(len(orders)), 0.0))})
    cands.sort(key=lambda c: c['log10_p'])
    merged = []
    for c in cands:   # x² and x⁴ lines of one BPSK signal give the same CFO
        if all(abs(c['cfo'] - m['cfo']) > 1 / (8 * N) for m in merged):
            merged.append(c)
    return merged, (merged[0]['log10_p'] if merged else 0.0)


def _sps_table(iq, higher=False):
    """Lag-1 correlation of y⁴ (both PSKs) and y² (BPSK only) at every sps in the domain.

    With the EXPERIMENTAL higher modulations enabled, q8 is added: for 8PSK, y⁴ = ±1 flips with the
    data, so the q4 ranking never proposes the true symbol rate of an 8PSK capture (measured: the
    correct hypothesis scores 10⁻²⁷ at the true front end, which the engine never builds). The 8th
    power is data-free for 8PSK, exactly as y⁴ is for QPSK."""
    rows = []
    for s in range(SPS_RANGE[0], SPS_RANGE[1] + 1):
        if len(iq) // s < MIN_SYMBOLS:
            break
        y = matched_filter_demod(iq, rrc_filter(RX_BETA, s), s)
        row = {'sps': s, 'n_symbols': len(iq) // s,
               'q4': lag1_correlation(y ** 4), 'q2': lag1_correlation(y ** 2)}
        if higher:
            row['q8'] = lag1_correlation(y ** 8)
        rows.append(row)
    return rows


def _sps_candidates(sps_table, raw_sps, higher=False):
    """Best N_SPS_RANKED sps by q4, each followed by its integer divisors, then the raw
    spectral estimate. The true sps's multiples also score high, so divisors are always
    tested; the code test decides between them.

    With the EXPERIMENTAL higher modulations enabled, the best candidates by q8 are added the same
    way, because q4 cannot rank an 8PSK capture (see _sps_table)."""
    valid = {r['sps'] for r in sps_table}
    out = []
    ranked = sorted(sps_table, key=lambda r: -r['q4'])[:N_SPS_RANKED]
    if higher:
        ranked = ranked + sorted(sps_table, key=lambda r: -r.get('q8', 0.0))[:N_SPS_RANKED]
    for r in ranked:
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
