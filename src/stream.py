"""Continuous convolutional stream code (family F2, Constitution v2.5 §12.1, §13.1).

A long capture need not be a zero-start burst: CCSDS TM transmits a continuous rate-½ K7 stream,
optionally with the second generator's output inverted (CCSDS 131.0-B-5 §3.3.1). The dual-code parity
check g2(D)·c1(D) + g1(D)·c2(D) = 0 holds for **any** encoder state and for a stream cut at both
ends, so the exact sign test of blind_id applies directly to the stream, with no deinterleaving.

Hypotheses per front end: pair offset o ∈ {0, 1} (which stream bit is the first c1) × G2 inversion.
Inverting every c2 bit multiplies each check by (−1)^weight(g1); g1 = 0o171 has weight 5, so the
inverted hypothesis is exactly the lower tail of the same positive count and costs no second pass.
Both are counted in M₂. For QPSK-like front ends the bit order inside a symbol is declared (I then Q),
so only the even offset is searched; a BPSK stream has no such anchor and both offsets are tested.

On acceptance the payload is decoded with a Viterbi that assumes no start state (`start='any'`), since
a continuous stream gives no reset point; polarity (a 180° phase flip) is resolved by path metric.
"""

import numpy as np

from blind_id import CODE_CATALOGUE, syndrome_checks, sign_test_log10p
from fec import conv_encode, viterbi_decode

CODE = CODE_CATALOGUE[0]                 # K7 (171,133); the only catalogue stream code
CODE_NAME = CODE['name'] + '_continuous'
PAIR_OFFSETS = (0, 1)
MIN_CHECKS = 16                          # below this no count can reach any family bar


def offsets(modulation):
    """Pair offsets searched for a front end (declared I-then-Q order anchors multi-bit symbols)."""
    return PAIR_OFFSETS if modulation == 'BPSK' else (0,)


def scan(th, modulation):
    """Every F2 hypothesis of one front end: exact sign test on the continuous stream.

    th = tanh(LLR/2) of the front end's bit stream. Returns one row per (offset, G2 inversion)."""
    rows = []
    for o in offsets(modulation):
        chk = syndrome_checks(np.asarray(th)[o:], CODE)
        if len(chk) < MIN_CHECKS:
            continue
        pos = int(np.count_nonzero(chk > 0))
        for inverted in (False, True):
            k = len(chk) - pos if inverted else pos
            rows.append({'offset': o, 'g2_inverted': inverted, 'n_checks': len(chk),
                         'n_positive': k, 'agreement': k / len(chk),
                         'log10_p': float(sign_test_log10p(k, len(chk)))})
    return rows


def rank(row):
    """Sort key over F2 hypotheses: p-value first, then the check-agreement ratio.

    On a long stream many hypotheses reach the 1e-300 floor of the p-value, so the tail probability
    alone cannot order them (F1 breaks the same tie with the syndrome z). The ratio does: a front end
    with residual carrier offset flips polarity in segments, which still satisfies the parity check
    inside each segment (the catalogue generators have odd weight, so a complemented codeword is a
    codeword) but fails it at every boundary. Such a front end decodes to a segment-wise complemented,
    useless payload, and it always has a lower agreement ratio than the coherent front end."""
    return (row['log10_p'], -row['agreement'])


def _g2_sign(n, offset):
    """+1 on c1 positions and −1 on c2 positions of a stream starting at `offset`."""
    s = np.ones(n)
    s[offset + 1::2] = -1.0
    return s


def decode(llrs, offset, g2_inverted):
    """Viterbi-decode an accepted F2 hypothesis (unknown start state, unknown polarity).

    Returns the information bits and the scores used to break polarity ties: the soft path metric
    Σ L·(1−2c)/Σ|L| and the hard re-encode consistency over the covered bits."""
    L = np.asarray(llrs, dtype=float)[offset:]
    if g2_inverted:
        L = L * _g2_sign(len(L), 0)
    T = len(L) // 2
    best = None
    for flip in (1.0, -1.0):
        x = flip * L[:2 * T]
        bits = viterbi_decode(x, CODE['generators'], CODE['K'], terminated=False, start='any')
        # Re-encoding from state 0 cannot reproduce a mid-stream start, so the first K-1 steps are
        # excluded from both scores.
        skip = 2 * (CODE['K'] - 1)
        reenc = conv_encode(bits, CODE['generators'], CODE['K'])[:2 * T]
        c = reenc[skip:]
        xs = x[skip:len(reenc)]
        mism = (xs < 0).astype(np.uint8) != c[:len(xs)]
        pm = float(np.sum(xs * (1 - 2.0 * c[:len(xs)])) / (float(np.sum(np.abs(xs))) + 1e-12))
        d = {'decoded_bits': bits, 'covered_bits': 2 * T, 'path_metric': pm,
             'consistency': float(1.0 - mism.mean()) if len(xs) else 0.0,
             'polarity_flipped': flip < 0}
        if best is None or d['path_metric'] > best['path_metric']:
            best = d
    return best
