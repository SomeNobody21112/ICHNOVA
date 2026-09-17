"""Blind binary FSK analysis: tone pair, shift, baud rate, polarity, character framing and text.

Nothing is assumed about the transmission. The analysis
  1. finds the two spectral lines that *alternate in time* (anti-correlated tone energy), which separates
     an FSK pair from a carrier plus an unrelated tone,
  2. demodulates non-coherently (two tone detectors) and estimates the baud rate from the phase coherence
     of symbol transitions on a fine grid,
  3. tests start-stop framing hypotheses (polarity x data bits x parity x stop bits) and keeps one only if
     its stop-bit agreement is significant against random bits, Bonferroni-corrected over the hypotheses,
  4. decodes characters (ITA2 5-bit with LTRS/FIGS shifts, or 7/8-bit ASCII).
Protocol recognisers (e.g. the CHU time code) then test redundancy that only the true protocol satisfies.
"""

import math

import numpy as np
from scipy.signal import butter, sosfiltfilt
from scipy.special import betainc

ALPHA = 0.01
STANDARD_BAUDS = (45.45, 50.0, 56.88, 75.0, 100.0, 110.0, 150.0, 200.0, 300.0, 600.0, 1200.0)

ITA2_LTRS = ['\0', 'E', '\n', 'A', ' ', 'S', 'I', 'U', '\r', 'D', 'R', 'J', 'N', 'F', 'C', 'K',
             'T', 'Z', 'L', 'W', 'H', 'Y', 'P', 'Q', 'O', 'B', 'G', None, 'M', 'X', 'V', None]
ITA2_FIGS = ['\0', '3', '\n', '-', ' ', "'", '8', '7', '\r', '$', '4', '\a', ',', '!', ':', '(',
             '5', '+', ')', '2', '#', '6', '0', '1', '9', '?', '&', None, '.', '/', '=', None]
FIGS, LTRS = 0x1B, 0x1F


def _lp(x, fs, fc, order=4):
    return sosfiltfilt(butter(order, min(fc, 0.45 * fs), fs=fs, output='sos'), x)


def spectrum(iq, fs, resolution_hz=2.0):
    nfft = 1 << int(math.ceil(math.log2(max(fs / resolution_hz, 64))))
    nfft = min(nfft, 1 << int(math.log2(len(iq))))
    win = np.hanning(nfft)
    P = np.zeros(nfft)
    hop = nfft // 2
    count = 0
    for k in range(0, len(iq) - nfft + 1, hop):
        P += np.abs(np.fft.fft(iq[k:k + nfft] * win)) ** 2
        count += 1
    f = np.fft.fftshift(np.fft.fftfreq(nfft, 1 / fs))
    return f, np.fft.fftshift(P / max(count, 1))


def _peaks(f, P, min_db=10.0, max_peaks=12, min_sep_hz=8.0):
    floor = np.median(P)
    db = 10 * np.log10(P / floor + 1e-30)
    order = np.argsort(db)[::-1]
    out = []
    for i in order:
        if db[i] < min_db or len(out) >= max_peaks:
            break
        if all(abs(f[i] - f[j]) > min_sep_hz for j in out):
            out.append(i)
    return [(float(f[i]), float(db[i])) for i in out]


def _tone_energy(iq, fs, f0, bw, rate):
    x = iq * np.exp(-2j * np.pi * f0 * np.arange(len(iq)) / fs)
    dec = max(1, int(fs // rate))
    return np.abs(_lp(x, fs, bw)[::dec]) ** 2, fs / dec


def stft_power(iq, fs, resolution_hz=6.0, hop_s=0.02, max_frames=6000):
    """|STFT|^2 [frames, bins] (fftshifted) and the bin frequencies. One pass, reused by every pair test."""
    nfft = 1 << int(math.ceil(math.log2(max(fs / resolution_hz, 16))))
    nfft = min(nfft, 1 << int(math.log2(max(len(iq), 16))))
    hop = max(1, int(hop_s * fs))
    count = max(1, min((len(iq) - nfft) // hop + 1, max_frames))
    hop = max(hop, (len(iq) - nfft) // count) if count == max_frames else hop
    idx = np.arange(count)[:, None] * hop + np.arange(nfft)[None, :]
    frames = iq[idx] * np.hanning(nfft)[None, :]
    S = np.abs(np.fft.fftshift(np.fft.fft(frames, axis=1), axes=1)) ** 2
    f = np.fft.fftshift(np.fft.fftfreq(nfft, 1 / fs))
    return f, S


def find_tone_pair(iq, fs, search=None, min_shift=20.0, max_shift=1200.0):
    """Best alternating tone pair: dict(f_low, f_high, shift_hz, center_hz, pair_db, anticorrelation) or None.

    Candidate lines come from the average spectrum; a pair is FSK only if the two lines' short-time energies
    are anti-correlated (one tone on while the other is off)."""
    iq = np.asarray(iq, dtype=complex)
    f, S = stft_power(iq, fs, resolution_hz=2.0, hop_s=0.5, max_frames=400)
    P = S.mean(axis=0)
    if search is not None:
        c, w = search
        P = np.where(np.abs(f - c) <= w, P, np.min(P))
    peaks = _peaks(f, P)
    pairs = [(i, j) for i in range(len(peaks)) for j in range(i + 1, len(peaks))
             if min_shift <= abs(peaks[i][0] - peaks[j][0]) <= max_shift]
    # Time resolution must follow the keying: analyse each pair with a resolution ~ shift/3 (one STFT per
    # power-of-two class, shared by all pairs in the class).
    classes = {}
    for i, j in pairs:
        res = float(2 ** round(math.log2(max(4.0, min(400.0, abs(peaks[i][0] - peaks[j][0]) / 3)))))
        classes.setdefault(res, []).append((i, j))
    best = None
    for res, members in classes.items():
        fr, Sr = stft_power(iq, fs, resolution_hz=res, hop_s=0.5 / res)
        dfr = fr[1] - fr[0]

        def energy(freq):
            k = int(round((freq - fr[0]) / dfr))
            return Sr[:, max(k, 0):k + 1].sum(axis=1)
        for i, j in members:
            (fa, da), (fb, db) = peaks[i], peaks[j]
            ea, eb = energy(fa), energy(fb)
            active = (ea + eb) > np.percentile(ea + eb, 60)
            if active.sum() < 10:
                continue
            r = np.corrcoef(ea[active], eb[active])[0, 1]
            # Keying sidebands also alternate; among clearly alternating pairs the tones carry the most power.
            score = min(da, db) - 3.0 * (r + 1.0)
            if r < -0.5 and (best is None or score > best['score']):
                lo, hi = sorted((fa, fb))
                best = {'f_low': lo, 'f_high': hi, 'shift_hz': abs(fa - fb), 'center_hz': (fa + fb) / 2,
                        'pair_db': round(min(da, db), 1), 'anticorrelation': round(float(-r), 3), 'score': score}
    return best


def refine_tones(iq, fs, pair, active_pct=60):
    """Tone frequencies from the two clusters of instantaneous frequency (spectral peaks of FSK are biased
    when the modulation index is not an integer)."""
    c, shift = pair['center_hz'], pair['shift_hz']
    rate = max(4 * shift, 200.0)
    dec = max(1, int(fs // rate))
    x = _lp(iq * np.exp(-2j * np.pi * c * np.arange(len(iq)) / fs), fs, 0.8 * shift)[::dec]
    r = fs / dec
    amp = np.abs(x)
    fi = np.angle(x[1:] * np.conj(x[:-1])) * r / (2 * np.pi)
    keep = amp[1:] > np.percentile(amp, active_pct)
    fi = fi[keep & (np.abs(fi) < shift)]
    if len(fi) < 50:
        return pair
    lo, hi = -shift / 2, shift / 2
    for _ in range(20):                                   # 1-D two-means
        thr = (lo + hi) / 2
        a, b = fi[fi < thr], fi[fi >= thr]
        if len(a) == 0 or len(b) == 0:
            break
        lo, hi = float(np.median(a)), float(np.median(b))
    return {**pair, 'f_low': c + lo, 'f_high': c + hi, 'shift_hz': hi - lo, 'center_hz': c + (lo + hi) / 2,
            'shift_from_spectrum_hz': round(shift, 2)}


def measure_shift(iq, fs, pair, baud):
    """Tone separation from coherent periodograms of the mark runs and of the space runs.

    Only the middle of runs of >= 2 identical bits is used; each run is phase-coherent on its own, so the
    periodogram is summed over runs. Unlike averaged phase increments, this is not biased by filtered noise."""
    c = pair['center_hz']
    width = pair['shift_hz'] + 2 * baud
    dec = max(1, int(fs // max(4 * width, 8 * baud)))
    x = _lp(iq * np.exp(-2j * np.pi * c * np.arange(len(iq)) / fs), fs, width / 2)[::dec]
    r = fs / dec
    fi = np.angle(x[1:] * np.conj(x[:-1])) * r / (2 * np.pi)
    k = max(1, int(r / baud))
    sign = np.sign(_lp(fi, r, baud / 2, order=2))
    same = np.convolve((sign > 0).astype(float), np.ones(2 * k) / (2 * k), mode='same')
    out = []
    for mask, lo_f, hi_f in (((same > 0.999), 0.0, width / 2), ((same < 0.001), -width / 2, 0.0)):
        idx = np.flatnonzero(mask)
        if len(idx) < 20:
            return None
        if len(idx) > 20000:
            idx = idx[:20000]
        run_id = np.cumsum(np.concatenate([[0], np.diff(idx) > 1]))
        n_runs = int(run_id[-1]) + 1
        best = None
        for grid in (np.linspace(lo_f, hi_f, 121), None):
            if grid is None:
                step = (hi_f - lo_f) / 120
                grid = np.linspace(best - step, best + step, 41)
            E = np.exp(-2j * np.pi * np.outer(idx / r, grid))            # [samples, grid]
            acc = np.zeros((n_runs, len(grid)), dtype=complex)
            np.add.at(acc, run_id, x[idx, None] * E)
            power = np.sum(np.abs(acc) ** 2, axis=0)
            best = float(grid[int(np.argmax(power))])
        out.append(best)
    return round(out[0] - out[1], 2)


def discriminate(iq, fs, f_low, f_high, bandwidth, out_rate):
    """d in [-1, 1] (+1 = high tone), total tone power, at ~out_rate."""
    el, rate = _tone_energy(iq, fs, f_low, bandwidth, out_rate)
    eh, _ = _tone_energy(iq, fs, f_high, bandwidth, out_rate)
    tot = el + eh
    return (eh - el) / (tot + 1e-30), tot, rate


def estimate_baud(d, rate, active, lo=10.0, hi=1500.0):
    """Baud from transition phase coherence. Returns (baud, coherence 0..1, n_transitions, min_run_s)."""
    s = np.sign(d)
    s[s == 0] = 1
    edges = np.flatnonzero((s[1:] != s[:-1]) & active[1:] & active[:-1])
    if len(edges) < 8:
        return None, 0.0, len(edges), None
    # sub-sample edge times by linear interpolation of d
    t = (edges + d[edges] / (d[edges] - d[edges + 1] + 1e-30)) / rate
    runs = np.diff(t)
    runs = runs[(runs > 1 / hi) & (runs < 1 / lo)]
    grid = np.unique(np.concatenate([np.geomspace(lo, min(hi, rate / 3), 1500), STANDARD_BAUDS]))
    grid = grid[grid < rate / 3]
    coh = np.abs(np.exp(2j * np.pi * np.outer(grid, t)).mean(axis=1))
    # Every harmonic k*B is as coherent as B (edges on the 1/B grid are also on the 1/(kB) grid), while
    # sub-harmonics are not (odd run lengths). The symbol rate is the lowest rate with near-maximal coherence.
    k = int(np.argmax(coh))
    good = np.flatnonzero(coh >= 0.85 * coh[k])
    k = int(good[np.argmin(grid[good])])
    fine = grid[k] * np.linspace(0.985, 1.015, 301)
    cf = np.abs(np.exp(2j * np.pi * np.outer(fine, t)).mean(axis=1))
    b = float(fine[int(np.argmax(cf))])
    min_run = float(np.percentile(runs, 2)) if len(runs) else None
    return b, float(cf.max()), len(edges), min_run


def snap_baud(b):
    std = min(STANDARD_BAUDS, key=lambda s: abs(s - b) / s)
    return std if abs(std - b) / std < 0.012 else b


def _binom_tail_log10(k, n, p):
    """log10 P(X >= k), X ~ Binomial(n, p)."""
    if k <= 0:
        return 0.0
    if k > n:
        return -300.0
    return float(np.log10(max(betainc(k, n - k + 1, p), 1e-300)))


FRAMINGS = [  # (data bits, parity, stop bits)
    (5, None, 1.5), (5, None, 1.0), (5, None, 2.0),
    (7, 'even', 1.0), (7, 'odd', 1.0), (7, None, 2.0), (8, None, 1.0), (8, None, 2.0),
]


def async_frames(d, active, rate, baud, data_bits, parity, stop_bits, polarity):
    """Start-stop character extraction. Returns list of dicts {t, value, stop_ok, parity_ok}.

    Bits are integrated over the middle half of each bit period (not a single sample)."""
    bit = rate / baud
    v = d * polarity                     # +1 = mark (idle), -1 = space
    n = len(v)
    cs = np.concatenate([[0.0], np.cumsum(v)])
    half = max(1, int(bit / 4))

    def level(center):
        a, b = int(center) - half, int(center) + half
        return (cs[min(max(b, 0), n)] - cs[min(max(a, 0), n)]) if 0 <= a < b <= n else -1.0

    n_bits = 1 + data_bits + (1 if parity else 0)
    total = (n_bits + stop_bits) * bit
    edges = np.flatnonzero((v[:-1] > 0) & (v[1:] <= 0) & active[1:]) + 1
    out = []
    next_free = 0
    for i in edges:
        if i < next_free or i + total >= n:
            continue
        c = i + 0.5 * bit
        if level(c) > 0:                 # glitch, not a start bit
            continue
        bits = [1 if level(c + (k + 1) * bit) > 0 else 0 for k in range(data_bits)]
        value = sum(b << k for k, b in enumerate(bits))
        pos = c + (data_bits + 1) * bit
        parity_ok = None
        if parity:
            parity_ok = (sum(bits) + (1 if level(pos) > 0 else 0)) % 2 == (0 if parity == 'even' else 1)
            pos += bit
        stop_ok = level(pos) > 0 and (stop_bits < 2 or level(pos + bit) > 0)
        out.append({'t': i / rate, 'value': value, 'stop_ok': bool(stop_ok), 'parity_ok': parity_ok})
        next_free = int(pos + (stop_bits - 0.5) * bit * 0.5) if stop_ok else int(i + bit)
    return out


def ita2_text(values):
    shift, out = 'L', []
    for v in values:
        if v == FIGS:
            shift = 'F'
        elif v == LTRS:
            shift = 'L'
        else:
            ch = (ITA2_FIGS if shift == 'F' else ITA2_LTRS)[v]
            if ch == ' ':
                shift = 'L' if shift == 'F' and False else shift
            if ch not in (None, '\0'):
                out.append(ch)
    return ''.join(out)


def analyze_fsk(iq, fs, search=None):
    """Blind FSK report (JSON-serialisable)."""
    iq = np.asarray(iq, dtype=complex)
    pair = find_tone_pair(iq, fs, search)
    if pair is None:
        return {'kind': 'FSK', 'status': 'UNKNOWN', 'reason': 'no alternating tone pair found'}
    # Work at a low rate around the pair: everything below is O(n) at ~16 x the widest plausible baud.
    span = pair['shift_hz'] + 2 * min(1500.0, 4 * pair['shift_hz'])
    dec = max(1, int(fs // max(2.5 * span, 400.0)))
    if dec > 1:
        base = pair['center_hz']
        x = _lp(iq * np.exp(-2j * np.pi * base * np.arange(len(iq)) / fs), fs, span / 2)[::dec]
        iq, fs = x, fs / dec
        pair = {**pair, 'f_low': pair['f_low'] - base, 'f_high': pair['f_high'] - base, 'center_hz': 0.0}
    else:
        base = 0.0
    pair = refine_tones(iq, fs, pair)
    shift = pair['shift_hz']
    bw0 = max(4.0, shift / 2.5)
    d, tot, rate = discriminate(iq, fs, pair['f_low'], pair['f_high'], bw0, min(fs / 2, max(8 * bw0, 400.0)))
    active = tot > 0.25 * np.percentile(tot, 90)
    baud, coherence, n_edges, min_run = estimate_baud(d, rate, active)
    shown = {k: (v + base if k in ('f_low', 'f_high', 'center_hz') else v) for k, v in pair.items() if k != 'score'}
    report = {'kind': 'FSK', **shown, 'transitions': n_edges,
              'active_fraction': round(float(active.mean()), 3)}
    if baud is None:
        return {**report, 'status': 'SIGNAL_NO_CODE', 'reason': 'too few symbol transitions'}
    # Fractional stop bits (ITA2 1.5) put transitions on a half-bit grid, so the coherent rate can be twice
    # the symbol rate. The shortest runs disambiguate; both candidates enter the framing test.
    candidates = [snap_baud(baud)]
    if min_run is not None and min_run * baud > 1.5:
        candidates.append(snap_baud(baud / 2))
    report.update({'baud_estimate': round(baud, 3), 'timing_coherence': round(coherence, 3),
                   'min_run_ms': None if min_run is None else round(min_run * 1e3, 2), 'baud_candidates': candidates})
    n_hyp = 2 * len(FRAMINGS) * len(candidates)
    threshold = math.log10(ALPHA / n_hyp)
    hyps = []
    for b_rate in candidates:
        bw = max(3.0, min(0.75 * b_rate, shift / 2))
        d, tot, rate = discriminate(iq, fs, pair['f_low'], pair['f_high'], bw, min(fs, max(16 * b_rate, 200.0)))
        active = tot > 0.25 * np.percentile(tot, 90)
        # Screen every framing on the first 20 s; only the most promising are run on the whole capture.
        screen = min(len(d), int(20 * rate))
        ranked = []
        for polarity in (1, -1):
            for data_bits, parity, stop in FRAMINGS:
                fr = async_frames(d[:screen], active[:screen], rate, b_rate, data_bits, parity, stop, polarity)
                ranked.append((-sum(f['stop_ok'] for f in fr) / max(len(fr), 1), polarity, data_bits, parity, stop))
        ranked.sort()
        for rank, (_, polarity, data_bits, parity, stop) in enumerate(ranked):
                full = rank < 4 or screen == len(d)
                fr = async_frames(d if full else d[:screen], active if full else active[:screen], rate, b_rate,
                                  data_bits, parity, stop, polarity)
                n = len(fr)
                ok = sum(f['stop_ok'] for f in fr)
                lp = _binom_tail_log10(ok, n, 0.5 if stop < 2 else 0.25)
                if parity:
                    pok = sum(1 for f in fr if f['stop_ok'] and f['parity_ok'])
                    lp = _binom_tail_log10(pok, n, 0.25)
                hyps.append({'baud': b_rate, 'polarity': 'high=mark' if polarity == 1 else 'low=mark', 'screened_only': not full,
                             'data_bits': data_bits, 'parity': parity, 'stop_bits': stop, 'characters': n,
                             'stop_ok': ok, 'stop_ok_fraction': round(ok / max(n, 1), 3), 'log10_p': round(lp, 2),
                             '_frames': fr})
    # Equal evidence: prefer the longer stop (it is the stricter hypothesis that still holds).
    hyps.sort(key=lambda h: (h['log10_p'], -h['stop_bits'], -h['characters']))
    best = hyps[0]
    report['baud'] = best['baud']
    report['framing_hypotheses'] = [{k: v for k, v in h.items() if k != '_frames'} for h in hyps]
    report['log10_threshold'] = round(threshold, 2)
    if best['log10_p'] > threshold:
        return {**report, 'status': 'SIGNAL_NO_CODE', 'reason': 'no character framing is significant'}
    report['measured_shift_hz'] = measure_shift(iq, fs, pair, best['baud'])
    frames = [f for f in best['_frames'] if f['stop_ok']]
    values = [f['value'] for f in frames]
    if best['data_bits'] == 5:
        text, code = ita2_text(values), 'ITA2'
    else:
        text = ''.join(chr(v & 0x7F) if 32 <= (v & 0x7F) < 127 or v in (10, 13) else '·' for v in values)
        code = 'ASCII'
    printable = sum(1 for ch in text if ch.isalnum() or ch in ' .,:-/+()\n\r') / max(len(text), 1)
    report.update({'status': 'DECODED', 'framing': {k: v for k, v in best.items() if k != '_frames'},
                   'code': code, 'text': text, 'printable_fraction': round(printable, 3),
                   'bytes': values, 'char_times_s': [round(f['t'], 4) for f in frames]})
    return report


# ------------------------------------------------------------------ CHU (NRC Canada) time code

def chu_packets(iq, fs, t0_unix=None, timing=None, tones=(2025.0, 2225.0), carrier_hz=None):
    """Decode CHU 300-Bd Bell-103 packets (10 bytes, 8N2) in seconds 31-39.

    Format A (32-39): 6d dd hh mm ss, repeated; format B (31): xd yy yy tt aa, then its one's complement.
    Nibbles within each byte are swapped for display (NRC). Tones are relative to the carrier."""
    iq = np.asarray(iq, dtype=complex)
    if carrier_hz is None:
        from timecodes import find_carrier
        carrier_hz, _ = find_carrier(iq, fs)
    f_space, f_mark = carrier_hz + tones[0], carrier_hz + tones[1]
    d, tot, rate = discriminate(iq, fs, f_space, f_mark, 220.0, 4800.0)
    active = tot > 0.25 * np.percentile(tot, 95)
    fr = async_frames(d, active, rate, 300.0, 8, None, 2.0, 1)
    packets = []
    i = 0
    while i + 10 <= len(fr):
        grp = fr[i:i + 10]
        span = grp[-1]['t'] - grp[0]['t']
        if not (0.30 < span < 0.34 and all(g['stop_ok'] for g in grp)):
            i += 1
            continue
        b = [g['value'] for g in grp]
        sw = [((x << 4) | (x >> 4)) & 0xFF for x in b]
        kind = 'A' if b[5:] == b[:5] else ('B' if all(x ^ y == 0xFF for x, y in zip(b[:5], b[5:])) else None)
        entry = {'t': round(grp[0]['t'], 4), 'bytes': b, 'format': kind, 'redundancy_ok': kind is not None,
                 'log10_p': round(40 * math.log10(0.5), 2) if kind else 0.0}
        digits = ''.join(f'{x:02x}' for x in sw[:5])
        if kind == 'A' and digits[0] == '6':
            entry.update({'day_of_year': int(digits[1:4]), 'hour': int(digits[4:6]), 'minute': int(digits[6:8]),
                          'second': int(digits[8:10])})
            if t0_unix is not None:
                import datetime as dt
                year = dt.datetime.fromtimestamp(t0_unix, dt.timezone.utc).year
                utc = dt.datetime(year, 1, 1, entry['hour'], entry['minute'], entry['second'], tzinfo=dt.timezone.utc) \
                    + dt.timedelta(days=entry['day_of_year'] - 1)
                # The last stop bit ends at .500 s; the first start bit begins 110/300 s earlier.
                start_utc = utc.timestamp() + 0.5 - 110 / 300
                entry['utc'] = utc.isoformat()
                entry['verification'] = {'timing': timing,
                                         'arrival_minus_decoded_ms': round((t0_unix + grp[0]['t'] - start_utc) * 1e3, 1)}
        elif kind == 'B':
            entry.update({'dut1_tenths': int(digits[1], 16) if digits[1] in '0123456789' else None,
                          'year': digits[2:6], 'tai_minus_utc': digits[6:8], 'dst_code': digits[8:10]})
        packets.append(entry)
        i += 10
    return {'kind': 'CHU', 'carrier_hz': round(carrier_hz, 2), 'packets': packets,
            'status': 'DECODED' if any(p['redundancy_ok'] for p in packets) else 'UNKNOWN'}


# ------------------------------------------------------------------ synthesis (tests)

def synthesize_async(values, fs, baud, f_low, f_high, data_bits=5, stop_bits=1.5, snr_db=20.0, lead_s=0.3,
                     rng=None, mark_high=True):
    rng = rng or np.random.default_rng(1)
    spb = fs / baud
    levels = [1] * int(lead_s * baud)
    for v in values:
        levels += [0] + [(v >> k) & 1 for k in range(data_bits)]
        levels += [1] * max(1, int(math.ceil(stop_bits)))           # 1.5 stop bits sent as 2 (receiver tolerant)
    samples = []
    for k, lv in enumerate(levels):
        samples.append(np.full(int(round((k + 1) * spb)) - int(round(k * spb)), lv))
    bits = np.concatenate(samples + [np.ones(int(lead_s * fs))])
    mark, space = (f_high, f_low) if mark_high else (f_low, f_high)
    freq = np.where(bits > 0, mark, space)
    phase = 2 * np.pi * np.cumsum(freq) / fs
    sig = np.exp(1j * phase)
    sigma = math.sqrt(10 ** (-snr_db / 10) / 2 * fs / 1000.0)
    return sig + sigma * (rng.standard_normal(len(sig)) + 1j * rng.standard_normal(len(sig)))


def ita2_encode(text):
    out, shift = [LTRS], 'L'
    for ch in text.upper():
        if ch in ITA2_LTRS and ch not in ('\0',):
            if shift != 'L' and ch not in (' ', '\n', '\r'):
                out.append(LTRS)
                shift = 'L'
            out.append(ITA2_LTRS.index(ch))
        elif ch in ITA2_FIGS:
            if shift != 'F':
                out.append(FIGS)
                shift = 'F'
            out.append(ITA2_FIGS.index(ch))
    return out


def chu_synthesize(utc_second, fs=12000.0, carrier_hz=-1500.0, snr_db=25.0, rng=None, fmt='A', lead_s=0.3):
    """One CHU packet for the whole second `utc_second` (datetime). Returns (iq, t0_unix of sample 0)."""
    import datetime as dt
    t = utc_second
    if fmt == 'A':
        digits = f"6{t.timetuple().tm_yday:03d}{t.hour:02d}{t.minute:02d}{t.second:02d}"
        data = [int(digits[i:i + 2], 16) for i in range(0, 10, 2)]
        data = data + data
    else:
        digits = f"0{t.year:04d}25"[:6] + "3700"
        data = [int(digits[i:i + 2], 16) for i in range(0, 10, 2)]
        data = data + [x ^ 0xFF for x in data]
    sent = [((x << 4) | (x >> 4)) & 0xFF for x in data]
    iq = synthesize_async(sent, fs, 300.0, carrier_hz + 2025.0, carrier_hz + 2225.0, data_bits=8, stop_bits=2,
                          snr_db=snr_db, lead_s=lead_s, rng=rng, mark_high=True)
    n = len(iq)
    iq = iq + 0.7 * np.exp(2j * np.pi * carrier_hz * np.arange(n) / fs)
    first_start = int(lead_s * 300.0) / 300.0
    t0 = t.replace(tzinfo=dt.timezone.utc).timestamp() + 0.5 - 110 / 300 - first_start
    return iq, t0
