"""Frame synchronisation, bit-stream correlation and header/payload mapping (family F3,
Constitution v2.5 §12.1, §13.1), plus the catalogue pseudo-randomizers.

Two exact tests over a declared, finite domain. P is a byte-aligned frame period of 64–16,384 bits,
and a hypothesis exists only where at least MIN_FRAMES frames fit in the stream:

1. Catalogue marker (CCSDS ASM 1ACFFC1D, 64-bit marker 034776C7272895B0) at period P, offset o,
   polarity s. Under the null (independent fair bits) the number of marker-bit agreements summed over
   the F frames is exactly Binomial(L·F, 1/2).
2. Blind constant field: a window of W in {16,24,32,48,64} columns at offset o of period P. For
   independent fair bits, the XORs of the same column in consecutive frames are independent fair
   coins, so the agreement count is exactly Binomial(W·(F-1), 1/2). This finds sync words and fixed
   header fields of formats that are not in the catalogue.

Hypothesis counts (M) cover the whole declared domain for the stream length, whether or not a
hypothesis was evaluated. Marker evaluation is screened for speed (candidate periods come from
positions with at least 75% agreement); screening can only miss hypotheses, never add accepts, so the
family-wise bound still holds. Blind windows are evaluated for every declared period.

Header/payload map of an accepted frame: the header starts with the accepted anchor (the catalogue
marker, or the blind constant window). It extends over the following columns that are individually
proven constant or alternating across frames (exact binomial test per column, Bonferroni over the
period). Columns that cannot be decided with the frames available are reported as undetermined,
together with the number of frames a decision would need. The payload is everything after the
header.
"""

from functools import lru_cache
import json
import os

import numpy as np
from scipy.special import bdtrc

REF = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'references', 'ccsds_constants.json')
_R = json.load(open(REF))

MARKERS = {name: np.array([int(c) for c in m['bits']], dtype=np.uint8)
           for name, m in (('ASM_1ACFFC1D', _R['asm']['tm_32']), ('ASM_034776C7272895B0', _R['asm']['ldpc_64']))}
PERIOD_RANGE = (64, 16384)           # bits, byte aligned
PERIOD_STEP = 8
BLIND_WIDTHS = (16, 24, 32, 48, 64)
MIN_FRAMES = 2
MARKER_SCREEN = 0.75                 # candidate marker position: at least 75% agreement
FRAME_PRESENT = 0.75                 # structural check: marker visible in at least 75% of frames
COLUMN_ALPHA = 0.01                  # per-period family-wise level of the descriptive column tests

# ---------------------------------------------------------------- pseudo-randomizers
# s[n+deg] = XOR of s[n+e] for every term x^e of h(x) below the degree. The initial register is the
# printed seed; the 17-bit TM seed is printed from X16 down to X0 while X0 is output first, so it is
# read reversed. All three reproduce the first 40 bits printed in the standards (tests/test_catalogue.py).
RANDOMIZERS = {
    'tm_131071': {'degree': 17, 'terms': (14, 0), 'seed_reversed': True, 'period': 131071},
    'tm_255': {'degree': 8, 'terms': (7, 5, 3, 0), 'seed_reversed': False, 'period': 255},
    'tc_btg': {'degree': 8, 'terms': (6, 4, 3, 2, 1, 0), 'seed_reversed': False, 'period': 255},
}


@lru_cache(maxsize=None)
def _pn_period(name):
    spec = RANDOMIZERS[name]
    seed = [int(c) for c in _R['randomizers'][name]['seed']]
    s = seed[::-1] if spec['seed_reversed'] else seed
    deg, terms, n = spec['degree'], spec['terms'], spec['period']
    out = np.zeros(n + deg, dtype=np.uint8)
    out[:deg] = s
    for m in range(n):
        v = 0
        for e in terms:
            v ^= out[m + e]
        out[m + deg] = v
    seq = out[:n].copy()
    seq.setflags(write=False)
    return seq


def pn_sequence(name, n):
    """First n bits of a catalogue randomizer, starting from its preset state."""
    per = _pn_period(name)
    reps = -(-n // len(per))
    return np.tile(per, reps)[:n]


# ---------------------------------------------------------------- domain accounting
def _periods():
    return np.arange(PERIOD_RANGE[0], PERIOD_RANGE[1] + 1, PERIOD_STEP)


def marker_domain(n_bits):
    """Hypotheses (marker x polarity x period x offset) with at least MIN_FRAMES frames in n_bits."""
    P = _periods()
    return int(sum(2 * np.clip(n_bits - len(m) - (MIN_FRAMES - 1) * P + 1, 0, P).sum() for m in MARKERS.values()))


def blind_domain(n_bits):
    """Hypotheses (width x period x offset) with at least MIN_FRAMES frames in n_bits."""
    P = _periods()
    return int(sum(np.clip(n_bits - w - (MIN_FRAMES - 1) * P + 1, 0, P).sum() for w in BLIND_WIDTHS))


def family_domain(n_bits):
    return marker_domain(n_bits) + blind_domain(n_bits)


def log10_sign(k, n):
    """log10 P(Binomial(n, 1/2) >= k)."""
    if k <= 0:
        return 0.0
    return float(np.log10(max(bdtrc(k - 1, n, 0.5), 1e-300)))


# ---------------------------------------------------------------- catalogue markers
def _agreements(bits, marker):
    x = 1.0 - 2.0 * np.asarray(bits, dtype=np.float64)
    m = 1.0 - 2.0 * marker.astype(np.float64)
    corr = np.correlate(x, m, mode='valid')
    return np.rint((len(marker) + corr) / 2).astype(np.int64)


def marker_search(bits, name):
    """Best (period, offset, polarity) for one catalogue marker; None if nothing to evaluate."""
    marker = MARKERS[name]
    L, n = len(marker), len(bits)
    if n < L + PERIOD_RANGE[0]:
        return None
    a = _agreements(bits, marker)
    best = None
    for pol, agree in (('normal', a), ('inverted', L - a)):
        pos = np.flatnonzero(agree >= MARKER_SCREEN * L)
        if len(pos) < MIN_FRAMES:
            continue
        if len(pos) > 400:                                   # screen only: keep the strongest
            pos = np.sort(pos[np.argsort(-agree[pos])[:400]])
        cands = set()
        for i in range(len(pos)):
            d = pos[i + 1:] - pos[i]
            for P in d[(d >= PERIOD_RANGE[0]) & (d <= PERIOD_RANGE[1]) & (d % PERIOD_STEP == 0)]:
                cands.add((int(P), int(pos[i] % P)))
        for P, o in cands:
            idx = np.arange(o, len(agree), P)
            F = len(idx)
            if F < MIN_FRAMES:
                continue
            S = int(agree[idx].sum())
            lp = log10_sign(S, L * F)
            present = int((agree[idx] >= FRAME_PRESENT * L).sum())
            cand = {'kind': 'catalogue_marker', 'marker': name, 'marker_bits': L, 'period_bits': P,
                    'offset_bits': o, 'polarity': pol, 'n_frames': F, 'agreements': S, 'total': L * F,
                    'frames_with_marker': present, 'log10_p': lp}
            if best is None or (lp, P) < (best['log10_p'], best['period_bits']):
                best = cand
    return best


# ---------------------------------------------------------------- blind constant fields
def blind_search(bits):
    """Best blind constant-field window over every declared period, offset and width."""
    b = np.asarray(bits, dtype=np.uint8)
    n = len(b)
    best = None
    for P in _periods():
        P = int(P)
        F = n // P
        if F < MIN_FRAMES:
            break
        frames = b[:F * P].reshape(F, P)
        same = (frames[1:] == frames[:-1]).sum(axis=0)          # per column, F-1 comparisons
        csum = np.concatenate([[0], np.cumsum(np.concatenate([same, same[:BLIND_WIDTHS[-1]]]))])
        for W in BLIND_WIDTHS:
            if W > P:
                continue
            win = csum[W:W + P] - csum[:P]                     # cyclic window sums over columns
            o = int(np.argmax(win))
            S = int(win[o])
            T = W * (F - 1)
            if best is not None and T <= best['total'] and S * best['total'] <= best['agreements'] * T:
                continue    # no larger total and no higher agreement ratio: cannot have a smaller p-value
            lp = log10_sign(S, W * (F - 1))
            cand = {'kind': 'blind_constant_field', 'marker': None, 'marker_bits': W, 'period_bits': P,
                    'offset_bits': o, 'polarity': None, 'n_frames': F, 'agreements': S, 'total': W * (F - 1),
                    'log10_p': lp}
            if best is None or (lp, P) < (best['log10_p'], best['period_bits']):
                best = cand
    return best


# ---------------------------------------------------------------- structural checks and map
def frame_map(bits, period, offset, anchor_bits):
    """Header/payload map of frames aligned at `offset` (the frame starts with the anchor)."""
    b = np.asarray(bits, dtype=np.uint8)[offset:]
    F = len(b) // period
    if F < MIN_FRAMES:
        return None
    frames = b[:F * period].reshape(F, period)
    same = (frames[1:] == frames[:-1]).sum(axis=0)
    comps = F - 1
    bar = np.log10(COLUMN_ALPHA / period)
    const = np.array([log10_sign(int(c), comps) <= bar for c in same])
    alt = np.array([log10_sign(int(comps - c), comps) <= bar for c in same])
    header_end = int(anchor_bits)
    while header_end < period and (const[header_end] or alt[header_end]):
        header_end += 1
    frames_needed = int(np.ceil(np.log2(period / COLUMN_ALPHA))) + 1   # F-1 identical comparisons reach the bar
    # Counter fields are looked for over the header and the first bytes after it, because a frame
    # count often sits just past the anchor even when the columns around it cannot yet be proven.
    counters = counter_fields(bits, period, offset, min(header_end + 64, period))
    return {'counter_fields': counters,
            'n_frames': int(F), 'period_bits': int(period), 'offset_bits': int(offset),
            'anchor_bits': int(anchor_bits), 'header_bits': [0, header_end], 'payload_bits': [header_end, int(period)],
            'proven_constant_columns': int(const.sum()), 'proven_alternating_columns': int(alt.sum()),
            'undetermined_columns': int(period - const.sum() - alt.sum()),
            'frames_needed_per_column': frames_needed,
            'column_class': ''.join('C' if c else 'A' if a else '?' for c, a in zip(const, alt))}


COUNTER_WIDTHS = (8, 16)             # byte-aligned counter fields looked for in a frame header


def counter_fields(bits, period, offset, header_bits, widths=COUNTER_WIDTHS):
    """Byte-aligned fields in the header that increment by a constant step from frame to frame.

    A frame counter is the one header field whose *change* is predictable, so it is evidence of
    framing that a constant-field test cannot give. For a field of width w read MSB first, the
    values of F frames must satisfy v[i+1] = (v[i] + delta) mod 2^w for one delta ≠ 0. Under
    independent fair bits that happens with probability 2^{-w(F-1)} for a given field and delta, so
    the reported log10 p is −w(F−1)·log10 2 + log10(2^w − 1) (the union over the possible steps).
    Nothing is claimed about what the field means: a counter is a measurement, not an interpretation
    of a particular standard's header layout."""
    b = np.asarray(bits, dtype=np.uint8)[offset:]
    F = len(b) // period
    if F < 3:                        # two frames give one difference: any field would "match"
        return []
    frames = b[:F * period].reshape(F, period)
    out = []
    for w in widths:
        for start in range(0, max(header_bits - w + 1, 0), 8):
            vals = frames[:, start:start + w] @ (1 << np.arange(w - 1, -1, -1))
            steps = (np.diff(vals.astype(np.int64)) % (1 << w))
            if len(np.unique(steps)) == 1 and steps[0] != 0:
                out.append({'offset_bits': int(start), 'width_bits': int(w),
                            'step': int(steps[0]), 'first_value': int(vals[0]),
                            'n_frames': int(F),
                            'log10_p': float(-w * (F - 1) * np.log10(2) + np.log10((1 << w) - 1))})
    return out


def column_variability(bits, period, offset):
    """Share of columns whose consecutive-frame agreement is below 90% (used by the structural check)."""
    b = np.asarray(bits, dtype=np.uint8)[offset:]
    F = len(b) // period
    if F < MIN_FRAMES:
        return None
    frames = b[:F * period].reshape(F, period)
    same = (frames[1:] == frames[:-1]).mean(axis=0)
    return float((same < 0.9).mean())


def structural_rejection(cand, bits):
    """Reason an otherwise significant frame hypothesis is implausible, or None."""
    if cand['kind'] == 'catalogue_marker':
        if cand['frames_with_marker'] < FRAME_PRESENT * cand['n_frames']:
            return (f"marker visible in only {cand['frames_with_marker']}/{cand['n_frames']} frames "
                    f"(period is probably a multiple or divisor of the true period)")
        return None
    share = column_variability(bits, cand['period_bits'], 0)
    if share is None:
        return 'fewer than two whole frames'
    if share < 0.25:
        return (f"only {share:.0%} of the {cand['period_bits']} columns vary between frames: a periodic or "
                f"constant stream, not frames with a payload")
    return None
