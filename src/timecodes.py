"""Blind reception of standard-frequency time-code broadcasts (one symbol per second, 60-s frames).

Catalogue (operator; official format description):
  WWV/WWVH  NIST, USA      100-Hz subcarrier, pulse width 0.2/0.5/0.8 s; UTC of the current minute
  WWVB      NIST, USA      carrier reduced 17 dB, restored after 0.2/0.5/0.8 s; UTC, current minute
  DCF77     PTB, Germany   carrier reduced to 15 % for 0.1/0.2 s; CET/CEST of the next minute; even parity
  MSF       NPL, UK        carrier off for 0.1 s + bit A + bit B; UK time of the next minute; odd parity
  JJY       NICT, Japan    carrier high for 0.8/0.5/0.2 s; JST of the current minute; even parity

The receiver is not told which station it hears. For every catalogue entry it
  1. finds the carrier and demodulates the keying envelope (or the WWV 100-Hz subcarrier),
  2. estimates the second epoch from the capture (fold, then least-squares refinement),
  3. fits each second to the entry's symbol shapes (least squares, amplitude and offset free),
  4. aligns 60-s frames on the marker pattern,
  5. decodes each frame by maximum likelihood over *valid field values only*, with the parity bits as
     constraints (dynamic programming over parity state) — the time code's redundancy used as a code,
  6. re-generates the complete frames implied by the decoded minute and counts disagreements with the
     received symbols, jointly over all complete frames in the capture.
The decision is statistical: p = P(this few disagreements | symbols unrelated to any frame) multiplied by
the number of distinct frames the search could have produced (all minutes 2000-2099 x flags x 60
alignments) and by the number of catalogue entries. DECODED requires p <= ALPHA. The decoded time is then
compared with the capture timestamp (GPS when the receiver has it) as an independent verification.
"""

import datetime as dt
import math

import numpy as np
from scipy.signal import butter, hilbert, sosfiltfilt

ALPHA = 0.01
DIGIT_LOG10_ODDS = 2.0                # a time digit is established when the alternative is >= 100x less likely
ENV_RATE = 1000.0                     # Hz
SETTLE_S = 2.0                        # ignore the first seconds (receiver AGC settling)

# ------------------------------------------------------------------ layouts
# Per second: ('M',) position marker, ('H',) subcarrier hole, ('Z',) fixed 0, ('O',) fixed 1,
# ('X',) unused, ('F', field, weight) data bit, ('P', group) parity bit.


def _blank():
    return [('X',)] * 60


def _put(lay, secs, field, weights):
    for s, w in zip(secs, weights):
        lay[s] = ('F', field, w)


def _wwv():
    L = _blank()
    L[0] = ('H',)
    for s in (9, 19, 29, 39, 49, 59):
        L[s] = ('M',)
    for s in (8, 14, 18, 24, 27, 28, 34, 42, 43, 44, 45, 46, 47, 48):
        L[s] = ('Z',)
    L[2], L[3], L[55] = ('F', 'dst1', 1), ('F', 'leap_warning', 1), ('F', 'dst2', 1)
    _put(L, range(4, 8), 'year_u', (1, 2, 4, 8))
    _put(L, range(10, 14), 'min_u', (1, 2, 4, 8))
    _put(L, range(15, 18), 'min_t', (10, 20, 40))
    _put(L, range(20, 24), 'hour_u', (1, 2, 4, 8))
    _put(L, range(25, 27), 'hour_t', (10, 20))
    _put(L, range(30, 34), 'day_u', (1, 2, 4, 8))
    _put(L, range(35, 39), 'day_t', (10, 20, 40, 80))
    _put(L, range(40, 42), 'day_h', (100, 200))
    L[50] = ('F', 'dut1_sign', 1)
    _put(L, range(51, 55), 'year_t', (10, 20, 40, 80))
    _put(L, (56, 57, 58), 'dut1', (1, 2, 4))
    return L


def _wwvb():
    L = _blank()
    for s in (0, 9, 19, 29, 39, 49, 59):
        L[s] = ('M',)
    for s in (4, 10, 11, 14, 20, 21, 24, 34, 35, 44, 54):
        L[s] = ('Z',)
    _put(L, (1, 2, 3), 'min_t', (40, 20, 10))
    _put(L, (5, 6, 7, 8), 'min_u', (8, 4, 2, 1))
    _put(L, (12, 13), 'hour_t', (20, 10))
    _put(L, (15, 16, 17, 18), 'hour_u', (8, 4, 2, 1))
    _put(L, (22, 23), 'day_h', (200, 100))
    _put(L, (25, 26, 27, 28), 'day_t', (80, 40, 20, 10))
    _put(L, (30, 31, 32, 33), 'day_u', (8, 4, 2, 1))
    _put(L, (36, 37, 38), 'dut1_sign', (4, 2, 1))
    _put(L, (40, 41, 42, 43), 'dut1', (8, 4, 2, 1))
    _put(L, (45, 46, 47, 48), 'year_t', (80, 40, 20, 10))
    _put(L, (50, 51, 52, 53), 'year_u', (8, 4, 2, 1))
    L[55], L[56] = ('F', 'leap_year', 1), ('F', 'leap_warning', 1)
    _put(L, (57, 58), 'dst', (2, 1))
    return L


def _dcf77():
    L = _blank()
    L[59], L[0], L[20] = ('M',), ('Z',), ('O',)
    L[16], L[17], L[18], L[19] = ('F', 'dst_announce', 1), ('F', 'cest', 1), ('F', 'cet', 1), ('F', 'leap_announce', 1)
    _put(L, range(21, 25), 'min_u', (1, 2, 4, 8))
    _put(L, range(25, 28), 'min_t', (10, 20, 40))
    L[28] = ('P', 'min')
    _put(L, range(29, 33), 'hour_u', (1, 2, 4, 8))
    _put(L, (33, 34), 'hour_t', (10, 20))
    L[35] = ('P', 'hour')
    _put(L, range(36, 40), 'mday_u', (1, 2, 4, 8))
    _put(L, (40, 41), 'mday_t', (10, 20))
    _put(L, (42, 43, 44), 'dow', (1, 2, 4))
    _put(L, range(45, 49), 'month_u', (1, 2, 4, 8))
    L[49] = ('F', 'month_t', 10)
    _put(L, range(50, 54), 'year_u', (1, 2, 4, 8))
    _put(L, range(54, 58), 'year_t', (10, 20, 40, 80))
    L[58] = ('P', 'date')
    return L


def _jjy():
    L = _blank()
    for s in (0, 9, 19, 29, 39, 49, 59):
        L[s] = ('M',)
    for s in (4, 10, 11, 14, 20, 21, 24, 34, 35, 38, 40, 55, 56, 57, 58):
        L[s] = ('Z',)
    _put(L, (1, 2, 3), 'min_t', (40, 20, 10))
    _put(L, (5, 6, 7, 8), 'min_u', (8, 4, 2, 1))
    _put(L, (12, 13), 'hour_t', (20, 10))
    _put(L, (15, 16, 17, 18), 'hour_u', (8, 4, 2, 1))
    _put(L, (22, 23), 'day_h', (200, 100))
    _put(L, (25, 26, 27, 28), 'day_t', (80, 40, 20, 10))
    _put(L, (30, 31, 32, 33), 'day_u', (8, 4, 2, 1))
    L[36], L[37] = ('P', 'hour'), ('P', 'min')
    _put(L, (41, 42, 43, 44), 'year_t', (80, 40, 20, 10))
    _put(L, (45, 46, 47, 48), 'year_u', (8, 4, 2, 1))
    _put(L, (50, 51, 52), 'dow', (4, 2, 1))
    _put(L, (53, 54), 'leap', (2, 1))
    return L


def _msf():
    A, B = _blank(), _blank()
    A[0] = B[0] = ('M',)
    for s in range(1, 17):
        A[s] = ('Z',)
    _put(A, range(17, 25), 'year', (80, 40, 20, 10, 8, 4, 2, 1))
    _put(A, range(25, 30), 'month', (10, 8, 4, 2, 1))
    _put(A, range(30, 36), 'mday', (20, 10, 8, 4, 2, 1))
    _put(A, range(36, 39), 'dow', (4, 2, 1))
    _put(A, range(39, 45), 'hour', (20, 10, 8, 4, 2, 1))
    _put(A, range(45, 52), 'minute', (40, 20, 10, 8, 4, 2, 1))
    for s, v in zip(range(52, 60), (0, 1, 1, 1, 1, 1, 1, 0)):
        A[s] = ('O',) if v else ('Z',)
    _put(B, range(1, 9), 'dut1_pos', (1,) * 8)
    _put(B, range(9, 17), 'dut1_neg', (1,) * 8)
    for s in list(range(17, 53)) + [59]:
        B[s] = ('Z',)
    B[53], B[58] = ('F', 'bst_warning', 1), ('F', 'bst', 1)
    B[54], B[55], B[56], B[57] = ('P', 'year'), ('P', 'date'), ('P', 'dow'), ('P', 'time')
    return A, B


BCD = lambda top: tuple(v for v in range(top + 1) if v % 10 <= 9)        # noqa: E731
DIGITS, TENS = tuple(range(10)), lambda n: tuple(10 * k for k in range(n + 1))   # noqa: E731
BIT, TWO_BITS = (0, 1), (0, 1, 2, 3)

PROTOCOLS = {
    'WWV': {
        'operator': 'NIST (U.S. Department of Commerce)', 'demod': 'subcarrier', 'layout': _wwv(),
        'refers_to': 'current', 'zone': 'UTC', 'frequencies_khz': (2500, 5000, 10000, 15000, 20000, 25000),
        'site': (40.6781, -105.0471),
        'reference': 'https://www.nist.gov/pml/time-and-frequency-division/time-distribution/radio-station-wwv',
        'values': {'year_u': DIGITS, 'min_u': DIGITS, 'min_t': TENS(5), 'hour_u': DIGITS, 'hour_t': TENS(2),
                   'day_u': DIGITS, 'day_t': TENS(9), 'day_h': (0, 100, 200, 300), 'year_t': TENS(9),
                   'dut1': tuple(range(8)), 'dut1_sign': BIT, 'leap_warning': BIT, 'dst1': BIT, 'dst2': BIT},
    },
    'WWVB': {
        'operator': 'NIST (U.S. Department of Commerce)', 'demod': 'keyed', 'layout': _wwvb(),
        'refers_to': 'current', 'zone': 'UTC', 'frequencies_khz': (60,), 'site': (40.6776, -105.0471),
        'reference': 'https://www.nist.gov/pml/time-and-frequency-division/time-distribution/radio-station-wwvb',
        'values': {'min_t': TENS(5), 'min_u': DIGITS, 'hour_t': TENS(2), 'hour_u': DIGITS, 'day_h': (0, 100, 200, 300),
                   'day_t': TENS(9), 'day_u': DIGITS, 'year_t': TENS(9), 'year_u': DIGITS, 'dut1_sign': (2, 5),
                   'dut1': DIGITS, 'leap_year': BIT, 'leap_warning': BIT, 'dst': TWO_BITS},
    },
    'DCF77': {
        'operator': 'PTB (Physikalisch-Technische Bundesanstalt, Germany)', 'demod': 'keyed', 'layout': _dcf77(),
        'refers_to': 'next', 'zone': 'CET/CEST', 'frequencies_khz': (77.5,), 'site': (50.0156, 9.0106),
        'parity': {'min': ((21, 27), 0), 'hour': ((29, 34), 0), 'date': ((36, 57), 0)},
        'reference': 'https://www.ptb.de/cms/en/ptb/fachabteilungen/abt4/fb-44/ag-442/dissemination-of-legal-time/dcf77.html',
        'values': {'dst_announce': BIT, 'cest': BIT, 'cet': BIT, 'leap_announce': BIT, 'min_u': DIGITS,
                   'min_t': TENS(5), 'hour_u': DIGITS, 'hour_t': TENS(2), 'mday_u': DIGITS, 'mday_t': TENS(3),
                   'dow': tuple(range(1, 8)), 'month_u': DIGITS, 'month_t': TENS(1), 'year_u': DIGITS, 'year_t': TENS(9)},
    },
    'MSF': {
        'operator': 'NPL (National Physical Laboratory, UK)', 'demod': 'keyed', 'layout': _msf(),
        'refers_to': 'next', 'zone': 'UK', 'frequencies_khz': (60,), 'site': (54.9111, -3.2789),
        'parity': {'year': ((17, 24), 1), 'date': ((25, 35), 1), 'dow': ((36, 38), 1), 'time': ((39, 51), 1)},
        'reference': 'https://www.npl.co.uk/msf-signal',
        'values': {'year': BCD(99), 'month': tuple(v for v in BCD(12) if v >= 1), 'mday': tuple(v for v in BCD(31) if v >= 1),
                   'dow': tuple(range(7)), 'hour': BCD(23), 'minute': BCD(59), 'dut1_pos': tuple(range(9)),
                   'dut1_neg': tuple(range(9)), 'bst_warning': BIT, 'bst': BIT},
    },
    'JJY': {
        'operator': 'NICT (National Institute of Information and Communications Technology, Japan)',
        'demod': 'keyed', 'layout': _jjy(), 'refers_to': 'current', 'zone': 'JST', 'frequencies_khz': (40, 60),
        'site': (37.3725, 140.8489), 'parity': {'hour': ((12, 18), 0), 'min': ((1, 8), 0)},
        'reference': 'https://jjy.nict.go.jp/jjy/trans/index-e.html',
        'values': {'min_t': TENS(5), 'min_u': DIGITS, 'hour_t': TENS(2), 'hour_u': DIGITS, 'day_h': (0, 100, 200, 300),
                   'day_t': TENS(9), 'day_u': DIGITS, 'year_t': TENS(9), 'year_u': DIGITS, 'dow': tuple(range(7)),
                   'leap': TWO_BITS},
    },
}


def _channels(protocol):
    lay = PROTOCOLS[protocol]['layout']
    return (('A', lay[0]), ('B', lay[1])) if protocol == 'MSF' else ((None, lay),)


def _search_space_log10(protocol):
    """log10 of the number of distinct frames the decoder can output (fields x 60 alignments)."""
    return math.log10(60) + sum(math.log10(len(v)) for v in PROTOCOLS[protocol]['values'].values())


# ------------------------------------------------------------------ encoding (frame from time)

def _value_bits(entries, value):
    """Greedy (BCD / unary) assignment of `value` to [(pos, weight)] sorted by weight descending."""
    out = {}
    for pos, w in sorted(entries, key=lambda e: -e[1]):
        if value >= w:
            out[pos], value = 1, value - w
        else:
            out[pos] = 0
    return out


def fields_for(protocol, utc, flags=None):
    """Field values of the frame whose second 0 is the whole minute `utc`."""
    flags = dict(flags or {})
    ref = utc + dt.timedelta(minutes=1) if PROTOCOLS[protocol]['refers_to'] == 'next' else utc
    if protocol == 'JJY':
        t = ref + dt.timedelta(hours=9)
    elif protocol == 'DCF77':
        t = ref + dt.timedelta(hours=2 if flags.get('cest', 1) else 1)
        flags.setdefault('cest', 1)
        flags['cet'] = 1 - flags['cest']
    elif protocol == 'MSF':
        t = ref + dt.timedelta(hours=1 if flags.get('bst', 1) else 0)
        flags.setdefault('bst', 1)
    else:
        t = ref
    doy, y = t.timetuple().tm_yday, t.year % 100
    v = {'min_u': t.minute % 10, 'min_t': t.minute // 10 * 10, 'hour_u': t.hour % 10, 'hour_t': t.hour // 10 * 10,
         'day_u': doy % 10, 'day_t': doy // 10 % 10 * 10, 'day_h': doy // 100 * 100, 'year_u': y % 10,
         'year_t': y // 10 * 10, 'mday_u': t.day % 10, 'mday_t': t.day // 10 * 10, 'month_u': t.month % 10,
         'month_t': t.month // 10 * 10, 'year': y, 'month': t.month, 'mday': t.day, 'hour': t.hour,
         'minute': t.minute, 'dow': t.isoweekday() if protocol == 'DCF77' else t.isoweekday() % 7}
    if protocol == 'WWVB':
        v['dut1_sign'] = 5
    out = {k: v.get(k, 0) for k in PROTOCOLS[protocol]['values']}
    out.update({k: val for k, val in flags.items() if k in out})
    return out


def encode(protocol, values, predicted=False):
    """60 expected symbols ('0','1','M','H'; MSF: 'M' or 'ab' pairs) for field values.

    Seconds whose content is not determined by the time (DCF77 weather bits, unused seconds) are None
    unless `predicted` (synthesis transmits 0 there)."""
    chans = []
    for ch, lay in _channels(protocol):
        bits = [0] * 60
        for field in PROTOCOLS[protocol]['values']:
            entries = [(p, e[2]) for p, e in enumerate(lay) if e[0] == 'F' and e[1] == field]
            for p, b in _value_bits(entries, values.get(field, 0)).items():
                bits[p] = b
        for p, e in enumerate(lay):
            if e[0] == 'O':
                bits[p] = 1
        chans.append((lay, bits))
    parity = PROTOCOLS[protocol].get('parity', {})
    data_bits = chans[0][1]
    for ch_i, (lay, bits) in enumerate(chans):
        for p, e in enumerate(lay):
            if e[0] == 'P':
                (a, b), odd = parity[e[1]]
                bits[p] = (sum(data_bits[a:b + 1]) + odd) % 2
    lay0 = chans[0][0]
    out = []
    for p in range(60):
        if lay0[p][0] in ('M', 'H'):
            out.append(lay0[p][0])
        elif not predicted and all(lay[p][0] == 'X' for lay, _ in chans):
            out.append(None)
        elif protocol == 'MSF':
            out.append(f'{chans[0][1][p]}{chans[1][1][p]}')
        else:
            out.append(str(chans[0][1][p]))
    return out


def frame_time(protocol, v):
    """UTC of the frame's second 0 from decoded field values (ValueError if not a real date)."""
    try:
        if protocol in ('WWV', 'WWVB', 'JJY'):
            doy = v['day_h'] + v['day_t'] + v['day_u']
            year = 2000 + v['year_t'] + v['year_u']
            hour, minute = v['hour_t'] + v['hour_u'], v['min_t'] + v['min_u']
            days = 366 if year % 4 == 0 else 365
            if not (1 <= doy <= days and hour <= 23 and minute <= 59):
                raise ValueError('time fields out of range')
            t = dt.datetime(year, 1, 1, hour, minute, tzinfo=dt.timezone.utc) + dt.timedelta(days=doy - 1)
            if protocol == 'JJY':
                t -= dt.timedelta(hours=9)
            return t
        if protocol == 'DCF77':
            if v['cest'] + v['cet'] != 1:
                raise ValueError('CET/CEST flags inconsistent')
            t = dt.datetime(2000 + v['year_t'] + v['year_u'], v['month_t'] + v['month_u'], v['mday_t'] + v['mday_u'],
                            v['hour_t'] + v['hour_u'], v['min_t'] + v['min_u'], tzinfo=dt.timezone.utc)
            if t.isoweekday() != v['dow']:
                raise ValueError('day of week inconsistent with date')
            return t - dt.timedelta(hours=2 if v['cest'] else 1, minutes=1)
        if protocol == 'MSF':
            t = dt.datetime(2000 + v['year'], v['month'], v['mday'], v['hour'], v['minute'], tzinfo=dt.timezone.utc)
            if t.isoweekday() % 7 != v['dow']:
                raise ValueError('day of week inconsistent with date')
            return t - dt.timedelta(hours=1 if v['bst'] else 0, minutes=1)
    except (KeyError, TypeError) as e:
        raise ValueError(str(e))
    raise KeyError(protocol)


# ------------------------------------------------------------------ front end

def _filt(x, fs, cutoff, btype='low', order=4):
    return sosfiltfilt(butter(order, cutoff, btype=btype, fs=fs, output='sos'), x)


def find_carrier(iq, fs, max_offset_hz=None):
    """Strongest narrowband component: (frequency Hz, peak-to-median dB)."""
    n = len(iq)
    nfft = 1 << int(min(math.log2(max(n, 2)), 16))
    win = np.hanning(nfft)
    P = np.zeros(nfft)
    for k in range(max(1, n // nfft)):
        seg = iq[k * nfft:(k + 1) * nfft]
        if len(seg) == nfft:
            P += np.abs(np.fft.fft(seg * win)) ** 2
    f = np.fft.fftfreq(nfft, 1 / fs)
    if max_offset_hz is not None:
        P = np.where(np.abs(f) <= max_offset_hz, P, 0)
    i = int(np.argmax(P))
    a, b, c = P[i - 1], P[i], P[(i + 1) % nfft]
    den = a - 2 * b + c
    delta = 0.5 * (a - c) / den if den != 0 else 0.0
    return float(f[i] + delta * fs / nfft), float(10 * np.log10(P[i] / (np.median(P[P > 0]) + 1e-30)))


def envelopes(iq, fs, fc):
    """Carrier envelope, 100-Hz subcarrier envelope and 1-kHz tick envelope at ~ENV_RATE."""
    x = np.asarray(iq, dtype=complex) * np.exp(-2j * np.pi * fc * np.arange(len(iq)) / fs)
    dec = max(1, int(round(fs / ENV_RATE)))
    out = {'rate': fs / dec, 'carrier': np.abs(_filt(x, fs, min(45.0, 0.2 * fs)))[::dec], 'subcarrier': None, 'tick': None}
    if fs >= 2400:
        audio = np.abs(_filt(x, fs, min(1400.0, 0.45 * fs)))
        audio -= _filt(audio, fs, 20.0, order=2)
        out['subcarrier'] = _filt(np.abs(hilbert(_filt(audio, fs, (85.0, 115.0), 'band'))), fs, 25.0, order=2)[::dec]
        out['tick'] = _filt(np.abs(hilbert(_filt(audio, fs, (900.0, 1300.0), 'band'))), fs, 150.0, order=2)[::dec]
    return out


def _step_shape(intervals, n, rate, inside_level):
    t = np.arange(n) / rate
    inside = np.zeros(n, dtype=bool)
    for lo, hi in intervals:
        inside |= (t >= lo) & (t < hi)
    x = np.where(inside, inside_level, 1.0 - inside_level)
    k = max(1, int(round(0.008 * rate)))
    return np.convolve(x, np.ones(k) / k, mode='same')


def symbol_templates(protocol, rate):
    """{symbol: expected envelope over one second}, unit modulation depth."""
    n = int(round(rate))
    S = lambda iv, lvl: _step_shape(iv, n, rate, lvl)     # noqa: E731
    if protocol == 'WWV':
        return {'0': S([(0.03, 0.2)], 1.0), '1': S([(0.03, 0.5)], 1.0), 'M': S([(0.03, 0.8)], 1.0), 'H': np.zeros(n)}
    if protocol == 'WWVB':
        return {'0': S([(0, 0.2)], 0.0), '1': S([(0, 0.5)], 0.0), 'M': S([(0, 0.8)], 0.0)}
    if protocol == 'JJY':
        return {'0': S([(0, 0.8)], 1.0), '1': S([(0, 0.5)], 1.0), 'M': S([(0, 0.2)], 1.0)}
    if protocol == 'DCF77':
        return {'0': S([(0, 0.1)], 0.0), '1': S([(0, 0.2)], 0.0), 'M': np.ones(n)}
    return {'M': S([(0, 0.5)], 0.0), '00': S([(0, 0.1)], 0.0), '10': S([(0, 0.2)], 0.0),
            '01': S([(0, 0.1), (0.2, 0.3)], 0.0), '11': S([(0, 0.3)], 0.0)}


def _fit_seconds(env, rate, epoch_s, protocol):
    """Least-squares fit of every complete second to each symbol shape.

    Returns starts (s), residuals [n_sec, n_sym], amplitudes [n_sec, n_sym], symbol names."""
    temps = symbol_templates(protocol, rate)
    names = list(temps)
    n = len(next(iter(temps.values())))
    first = int(math.ceil((SETTLE_S - epoch_s)))
    ks = [k for k in range(max(first, 0), int(len(env) / rate) + 1)
          if int(round((epoch_s + k) * rate)) + n <= len(env)]
    if not ks:
        return [], np.zeros((0, len(names))), np.zeros((0, len(names))), names
    idx = np.array([int(round((epoch_s + k) * rate)) for k in ks])
    Y = env[idx[:, None] + np.arange(n)[None, :]]
    Y = Y - Y.mean(axis=1, keepdims=True)
    res, amp = [], []
    for name in names:
        x = temps[name] - temps[name].mean()
        vx = float(x @ x)
        a = (Y @ x) / vx if vx > 1e-12 else np.zeros(len(Y))
        a = np.maximum(a, 0.0)                               # shapes have a known polarity
        r = Y - a[:, None] * x[None, :]
        res.append(np.einsum('ij,ij->i', r, r))
        amp.append(a)
    return [epoch_s + k for k in ks], np.array(res).T, np.array(amp).T, names


def estimate_epoch(env, rate, protocol, tick=None):
    """Second epoch (capture-relative, 0..1 s): fold estimate, then +-40 ms least-squares refinement."""
    series = tick if tick is not None else env
    phase = (np.arange(len(series)) / rate) % 1.0
    bins = np.minimum((phase * 1000).astype(int), 999)
    prof = np.bincount(bins, series, 1000) / np.maximum(np.bincount(bins, None, 1000), 1)
    w = 5 if tick is not None else 20
    c = np.concatenate([prof[-w:], prof, prof[:w]])
    cs = np.cumsum(np.concatenate([[0.0], c]))
    step = (cs[2 * w:2 * w + 1000] - cs[w:w + 1000]) / w - (cs[w:w + 1000] - cs[0:1000]) / w
    if protocol == 'JJY':
        coarse = int(np.argmax(step))
    elif tick is not None:
        coarse = int(np.argmax(step))
    else:
        coarse = int(np.argmin(step))
    contrast = float(abs(step[coarse]) / (np.std(step) + 1e-12))
    best = None
    for d in range(-40, 41, 2):
        e = ((coarse + d) / 1000.0) % 1.0
        _, res, _, _ = _fit_seconds(env, rate, e, protocol)
        if len(res):
            score = float(np.sum(np.min(res, axis=1)))
            if best is None or score < best[1]:
                best = (e, score)
    epoch = best[0] if best else coarse / 1000.0
    for d in (-1, 1):                                        # 1-ms polish
        e = (epoch + d / 1000.0) % 1.0
        _, res, _, _ = _fit_seconds(env, rate, e, protocol)
        if len(res) and float(np.sum(np.min(res, axis=1))) < best[1]:
            epoch, best = e, (e, float(np.sum(np.min(res, axis=1))))
    return epoch, contrast


def classify(env, rate, epoch_s, protocol):
    """Per-second symbols: list of {start_s, symbol|None, confidence, amplitude}."""
    starts, res, amp, names = _fit_seconds(env, rate, epoch_s, protocol)
    if not starts:
        return []
    depth = amp.max(axis=1)
    typical = float(np.median(depth))
    out = []
    for i, s in enumerate(starts):
        order = np.argsort(res[i])
        b, r2 = order[0], order[1]
        sym = names[b]
        conf = float((res[i, r2] - res[i, b]) / (res[i, r2] + 1e-12))
        flat = (protocol == 'DCF77' and sym == 'M') or (protocol == 'WWV' and sym == 'H')
        if not flat and depth[i] < 0.3 * typical:
            sym, conf = None, 0.0                            # deep fade: erasure
        out.append({'start_s': round(s, 4), 'symbol': sym, 'confidence': round(max(conf, 0.0), 3),
                    'depth': round(float(depth[i] / (typical + 1e-12)), 2)})
    return out


# ------------------------------------------------------------------ decoding

def align(symbols, protocol):
    """Frame offset o (symbol k at frame position (k + o) % 60) with the best marker agreement."""
    marks = {p: e[0] for p, e in enumerate(_channels(protocol)[0][1]) if e[0] in ('M', 'H')}
    best = (0, -10 ** 9)
    for o in range(60):
        score = 0
        for k, s in enumerate(symbols):
            sym = s['symbol']
            if sym is None:
                continue
            pos = (k + o) % 60
            if pos in marks:
                score += 1 if sym == marks[pos] else -1
            elif sym in ('M', 'H'):
                score -= 1
        if score > best[1]:
            best = (o, score)
    return best


def _bit_cost(frame, weights, pos, channel, bit):
    sym = frame[pos]
    if sym is None:
        return 0.0
    if sym in ('M', 'H'):
        return weights[pos]
    obs = int(sym[1] if channel == 'B' else sym[0])
    return 0.0 if obs == bit else weights[pos]


def ml_fields(frame, weights, protocol):
    """Maximum-likelihood valid field values for one frame (parity bits as constraints)."""
    spec = PROTOCOLS[protocol]
    parity = spec.get('parity', {})
    chans = _channels(protocol)
    field_entries = {}
    for ch, lay in chans:
        for p, e in enumerate(lay):
            if e[0] == 'F':
                field_entries.setdefault(e[1], (ch, []))[1].append((p, e[2]))
    costs = {}
    for field, (ch, entries) in field_entries.items():
        table = []
        for v in spec['values'][field]:
            bits = _value_bits(entries, v)
            cost = sum(_bit_cost(frame, weights, p, ch, b) for p, b in bits.items())
            table.append((cost, v, sum(bits.values())))
        costs[field] = table
    chosen = {}
    grouped = set()
    for group, ((a, b), odd) in parity.items():
        members = [f for f, (ch, ent) in field_entries.items() if ch in (None, 'A') and all(a <= p <= b for p, _ in ent)]
        grouped.update(members)
        ppos = next(p for ch, lay in chans for p, e in enumerate(lay) if e[0] == 'P' and e[1] == group)
        pch = 'B' if protocol == 'MSF' else None
        # DP over parity of ones: state -> (cost, choices)
        states = {0: (0.0, {})}
        for f in members:
            nxt = {}
            for par, (c0, ch0) in states.items():
                for cost, v, ones in costs[f]:
                    s = (par + ones) % 2
                    cand = (c0 + cost, {**ch0, f: v})
                    if s not in nxt or cand[0] < nxt[s][0]:
                        nxt[s] = cand
            states = nxt
        best = None
        for par, (c0, ch0) in states.items():
            pbit = (par + odd) % 2
            total = c0 + _bit_cost(frame, weights, ppos, pch, pbit)
            if best is None or total < best[0]:
                best = (total, ch0)
        chosen.update(best[1])
    for f in field_entries:
        if f not in grouped:
            chosen[f] = min(costs[f])[1]
    return chosen


def _tail_log10(q_mismatch, k):
    """log10 P(at most k mismatches) for independent mismatch probabilities (Poisson-binomial, exact)."""
    dist = np.zeros(len(q_mismatch) + 1)
    dist[0] = 1.0
    for i, q in enumerate(q_mismatch):
        dist[1:i + 2] = dist[1:i + 2] * (1 - q) + dist[0:i + 1] * q
        dist[0] *= (1 - q)
    return float(np.log10(max(dist[:k + 1].sum(), 1e-300)))


def _digit_alternatives(protocol, t):
    """{digit name: [alternative whole-minute UTC datetimes differing only in that digit]}."""
    local_days = protocol in ('DCF77', 'MSF')
    out = {}

    def add(name, fn, values):
        alts = []
        for v in values:
            try:
                a = fn(v)
            except (ValueError, OverflowError):
                continue
            if a != t and dt.datetime(2000, 1, 1, tzinfo=dt.timezone.utc) <= a < dt.datetime(2100, 1, 1, tzinfo=dt.timezone.utc):
                alts.append(a)
        out[name] = alts

    y = t.year - 2000
    add('year_tens', lambda v: t.replace(year=2000 + 10 * v + y % 10), range(10))
    add('year_units', lambda v: t.replace(year=2000 + y // 10 * 10 + v), range(10))
    if local_days:
        add('month', lambda v: t.replace(month=v), range(1, 13))
        add('day_tens', lambda v: t.replace(day=10 * v + t.day % 10), range(4))
        add('day_units', lambda v: t.replace(day=t.day // 10 * 10 + v), range(10))
    else:
        doy = t.timetuple().tm_yday
        base = t - dt.timedelta(days=doy - 1)
        add('day_hundreds', lambda v: base + dt.timedelta(days=100 * v + doy % 100 - 1), range(4))
        add('day_tens', lambda v: base + dt.timedelta(days=doy // 100 * 100 + 10 * v + doy % 10 - 1), range(10))
        add('day_units', lambda v: base + dt.timedelta(days=doy // 10 * 10 + v - 1), range(10))
    add('hour_tens', lambda v: t.replace(hour=10 * v + t.hour % 10), range(3))
    add('hour_units', lambda v: t.replace(hour=t.hour // 10 * 10 + v), range(10))
    add('minute_tens', lambda v: t.replace(minute=10 * v + t.minute % 10), range(6))
    add('minute_units', lambda v: t.replace(minute=t.minute // 10 * 10 + v), range(10))
    return out


def _mismatches(protocol, symbols, starts, t_first, flags):
    total = 0
    syms = [s['symbol'] for s in symbols]
    for j, k in enumerate(starts):
        expected = encode(protocol, fields_for(protocol, t_first + dt.timedelta(minutes=j), flags))
        total += sum(1 for e, g in zip(expected, syms[k:k + 60]) if g is not None and e is not None and e != g)
    return total


def decode(symbols, protocol, t0_unix=None, timing=None):
    """Decode all complete frames jointly; statistical decision + optional timestamp verification."""
    offset, marker_score = align(symbols, protocol)
    starts = [k for k in range(len(symbols)) if (k + offset) % 60 == 0 and k + 60 <= len(symbols)]
    syms = [s['symbol'] for s in symbols]
    weights_all = [0.2 + s['confidence'] for s in symbols]
    observed = [s for s in syms if s is not None]
    freq = {s: observed.count(s) / len(observed) for s in set(observed)} if observed else {}
    candidates = []
    for j, k in enumerate(starts):
        frame, w = syms[k:k + 60], weights_all[k:k + 60]
        vals = ml_fields(frame, w, protocol)
        try:
            t = frame_time(protocol, vals)
        except ValueError:
            continue
        flags = {f: v for f, v in vals.items() if f in ('dst1', 'dst2', 'leap_warning', 'dut1', 'dut1_sign', 'cest', 'cet',
                                                       'dst_announce', 'leap_announce', 'bst', 'bst_warning', 'dut1_pos',
                                                       'dut1_neg', 'leap_year', 'dst', 'leap')}
        candidates.append((t - dt.timedelta(minutes=j), flags))
    best = None
    for t_first, flags in candidates:
        mism, n_obs, q = 0, 0, []
        frames = []
        for j, k in enumerate(starts):
            expected = encode(protocol, fields_for(protocol, t_first + dt.timedelta(minutes=j), flags))
            got = syms[k:k + 60]
            pairs = [(p, e, g) for p, (e, g) in enumerate(zip(expected, got)) if g is not None and e is not None]
            m = [x for x in pairs if x[1] != x[2]]
            n = len(pairs)
            mism += len(m)
            n_obs += n
            q += [1.0 - freq.get(e, 0.0) for _, e, _ in pairs]
            frames.append({'start_index': k, 'start_s': symbols[k]['start_s'],
                           'utc': (t_first + dt.timedelta(minutes=j)).isoformat(), 'expected': expected,
                           'mismatch_positions': [p for p, _, _ in m], 'observed_symbols': n})
        if best is None or mism < best['mismatches']:
            best = {'t_first': t_first, 'flags': flags, 'mismatches': mism, 'n_observed': n_obs, 'q': q, 'frames': frames}
    report = {'protocol': protocol, 'frame_offset': offset, 'marker_score': marker_score,
              'complete_frames': len(starts), 'search_space_log10': round(_search_space_log10(protocol), 2)}
    if best is None:
        return {**report, 'decoded': False, 'reason': 'no complete frame with a valid date' if starts else
                'capture shorter than one frame after alignment', 'log10_p': 0.0}
    tail = _tail_log10(best['q'], best['mismatches'])
    lp = tail + _search_space_log10(protocol)
    # Digit reliability: extra disagreements any other value of the digit would cause, converted to log10
    # odds with the capture's own symbol error rate (smoothed).
    eps = (best['mismatches'] + 1) / (best['n_observed'] + 2)
    per_symbol = math.log10((1 - eps) / eps)
    digits = {}
    for name, alts in _digit_alternatives(protocol, best['t_first']).items():
        margin = min((_mismatches(protocol, symbols, starts, a, best['flags']) - best['mismatches'] for a in alts),
                     default=None)
        odds = None if margin is None else round(margin * per_symbol, 2)
        digits[name] = {'margin_symbols': margin, 'log10_odds': odds,
                        'established': odds is not None and odds >= DIGIT_LOG10_ODDS}
    unresolved = [k for k, v in digits.items() if not v['established']]
    report.update({'decoded': True, 'utc_first_frame': best['t_first'].isoformat(), 'flags': best['flags'],
                   'digits': digits, 'unresolved_digits': unresolved, 'time_established': not unresolved,
                   'symbol_error_rate_smoothed': round(eps, 4), 'log10_odds_per_symbol': round(per_symbol, 3),
                   'mismatches': best['mismatches'], 'observed_symbols': best['n_observed'],
                   'symbol_error_rate': round(best['mismatches'] / max(best['n_observed'], 1), 4),
                   'log10_tail': round(tail, 2), 'log10_p': round(lp, 2), 'frames': best['frames']})
    if t0_unix is not None:
        f0 = best['frames'][0]
        arrival = t0_unix + f0['start_s']
        delta_ms = (arrival - best['t_first'].timestamp()) * 1e3
        report['verification'] = {'timing': timing, 'capture_t0_unix': t0_unix,
                                  'arrival_minus_decoded_ms': round(delta_ms, 2),
                                  'agrees': abs(delta_ms) < (100.0 if timing == 'gps' else 3000.0)}
    return report


def receive(iq, fs, t0_unix=None, timing=None, protocols=None, carrier_hz=None, carrier_search=None):
    """Blind reception over the catalogue. JSON-serialisable report.

    carrier_search=(center_hz, half_width_hz) restricts the carrier search when the tuning is known."""
    iq = np.asarray(iq, dtype=complex)
    if carrier_hz is not None:
        fc, peak_db = carrier_hz, None
    elif carrier_search is not None:
        c, w = carrier_search
        shifted = iq * np.exp(-2j * np.pi * c * np.arange(len(iq)) / fs)
        fc, peak_db = find_carrier(shifted, fs, w)
        fc += c
    else:
        fc, peak_db = find_carrier(iq, fs)
    env = envelopes(iq, fs, fc)
    names = [p for p in (protocols or PROTOCOLS) if not (PROTOCOLS[p]['demod'] == 'subcarrier' and env['subcarrier'] is None)]
    threshold = math.log10(ALPHA / max(len(names), 1))
    results = []
    for name in names:
        if PROTOCOLS[name]['demod'] == 'subcarrier':
            series, tick = env['subcarrier'], env['tick']
        else:
            series, tick = env['carrier'], None
        epoch, contrast = estimate_epoch(series, env['rate'], name, tick)
        syms = classify(series, env['rate'], epoch, name)
        r = decode(syms, name, t0_unix, timing)
        r.update({'operator': PROTOCOLS[name]['operator'], 'reference': PROTOCOLS[name]['reference'],
                  'epoch_s': round(epoch, 4), 'epoch_contrast': round(contrast, 2),
                  'symbols': [s['symbol'] for s in syms], 'confidence': [s['confidence'] for s in syms],
                  'symbol_starts_s': [s['start_s'] for s in syms]})
        r['detected'] = bool(r['decoded'] and r['log10_p'] <= threshold)
        r['accepted'] = bool(r['detected'] and r.get('time_established'))
        results.append(r)
    accepted = sorted([r for r in results if r['accepted']], key=lambda r: r['log10_p'])
    detected = sorted([r for r in results if r['detected']], key=lambda r: r['log10_p'])
    best = accepted[0] if accepted else None
    station = detected[0]['protocol'] if detected else None
    return {'kind': 'TIMECODE', 'carrier_offset_hz': round(fc, 3), 'carrier_peak_db': None if peak_db is None else round(peak_db, 1),
            'alpha': ALPHA, 'log10_threshold': round(threshold, 2), 'n_protocols': len(names),
            'status': 'DECODED' if best else ('SIGNAL_NO_CODE' if station else 'UNKNOWN'),
            'protocol': best['protocol'] if best else station,
            'utc': best['utc_first_frame'] if best else None,
            'reason': None if best else (f'{station} frame structure is significant but time digits are not established: '
                                         + ', '.join(detected[0]['unresolved_digits']) if station else
                                         'no catalogue time code is significant'),
            'results': results}


# ------------------------------------------------------------------ synthesis (tests)

def synthesize(protocol, start_utc, seconds, fs=12000.0, carrier_hz=-1000.0, snr_db=20.0, rng=None, lead_s=0.37,
               flags=None):
    """Complex baseband of a station; sample 0 is `lead_s` seconds before the whole second `start_utc`."""
    rng = rng or np.random.default_rng(0)
    n = int(seconds * fs)
    t = np.arange(n) / fs
    abs_t = start_utc.timestamp() - lead_s + t
    sec = np.floor(abs_t).astype(np.int64)
    frac = abs_t - sec
    amp = np.ones(n)
    cache = {}
    for s in np.unique(sec):
        m = sec == s
        f = frac[m]
        minute = int(s) - int(s) % 60
        if minute not in cache:
            cache[minute] = encode(protocol, fields_for(protocol, dt.datetime.fromtimestamp(minute, dt.timezone.utc), flags), True)
        sym = cache[minute][int(s) % 60]
        if protocol == 'MSF':
            off = (f < 0.5) if sym == 'M' else ((f < 0.1) | ((f < 0.2) & (sym[0] == '1')) | ((f >= 0.2) & (f < 0.3) & (sym[1] == '1')))
            amp[m] = np.where(off, 0.0, 1.0)
        elif protocol == 'DCF77':
            amp[m] = 1.0 if sym == 'M' else np.where(f < (0.2 if sym == '1' else 0.1), 0.15, 1.0)
        elif protocol == 'WWVB':
            amp[m] = np.where(f < {'0': 0.2, '1': 0.5, 'M': 0.8}[sym], 10 ** (-17 / 20), 1.0)
        elif protocol == 'JJY':
            amp[m] = np.where(f < {'0': 0.8, '1': 0.5, 'M': 0.2}[sym], 1.0, 0.1)
        else:
            width = {'0': 0.2, '1': 0.5, 'M': 0.8, 'H': 0.0}[sym]
            sub = np.where((f >= 0.03) & (f < width), 0.18 * np.sin(2 * np.pi * 100 * f), 0.0)
            tick = np.where(f < 0.005, 0.5 * np.sin(2 * np.pi * 1000 * f), 0.0)
            amp[m] = 1.0 + sub + tick
    sig = amp * np.exp(2j * np.pi * carrier_hz * t)
    sigma = math.sqrt(10 ** (-snr_db / 10) / 2 * fs / 1000.0)      # snr_db referenced to a 1-kHz bandwidth
    return sig + sigma * (rng.standard_normal(n) + 1j * rng.standard_normal(n))
