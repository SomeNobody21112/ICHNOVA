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
MIN_DISTINCT_BYTES = 4                   # degenerate-stream rule, as for RS (§13.1 note 5)

# Decoy codes: a within-file negative control, not hypotheses (they are never accepted and never
# enter M2). Each is a rate-1/2 constraint-length-7 generator pair that is NOT the catalogue code and
# has the same **even** total tap weight (10), so it is exactly as sensitive as the real code to a
# stream that is periodic or otherwise structured rather than K7-coded. A constant or periodic bit
# stream satisfies the parity checks of every such tap pattern — that is how an unmodulated carrier
# reached p = 10^-9 on the real code (bench-v2 calibration, idle_carrier) — while a genuine K7
# codeword satisfies only the real code's checks and leaves the decoys at chance.
# Each decoy generator has weight 5 like the catalogue's, and the pairs exclude (171,133), its swap
# and its bit-reversal (117,155), which are the same code in the other tap convention.
DECOYS = [{'name': 'decoy_127_135', 'generators': [0o127, 0o135], 'K': 7},
          {'name': 'decoy_147_153', 'generators': [0o147, 0o153], 'K': 7},
          {'name': 'decoy_163_165', 'generators': [0o163, 0o165], 'K': 7},
          {'name': 'decoy_117_127', 'generators': [0o117, 0o127], 'K': 7}]


def offsets(modulation):
    """Pair offsets searched for a front end (declared I-then-Q order anchors multi-bit symbols)."""
    return PAIR_OFFSETS if modulation == 'BPSK' else (0,)


def scan(th, modulation):
    """Every F2 hypothesis of one front end: exact sign test on the continuous stream.

    th = tanh(LLR/2) of the front end's bit stream. Returns one row per (offset, G2 inversion)."""
    rows = []
    for o in offsets(modulation):
        stream_th = np.asarray(th)[o:]
        chk = syndrome_checks(stream_th, CODE)
        if len(chk) < MIN_CHECKS:
            continue
        pos = int(np.count_nonzero(chk > 0))
        # Negative control: the same test with decoy tap patterns (never accepted, never in M2).
        decoy = []
        for d in DECOYS:
            dchk = syndrome_checks(stream_th, d)
            if not len(dchk):
                continue
            dpos = int(np.count_nonzero(dchk > 0))
            decoy.append({'name': d['name'], 'n_checks': len(dchk),
                          'log10_p': min(float(sign_test_log10p(dpos, len(dchk))),
                                         float(sign_test_log10p(len(dchk) - dpos, len(dchk))))})
        decoy_best = min((d['log10_p'] for d in decoy), default=0.0)
        for inverted in (False, True):
            k = len(chk) - pos if inverted else pos
            rows.append({'offset': o, 'g2_inverted': inverted, 'n_checks': len(chk),
                         'n_positive': k, 'agreement': k / len(chk),
                         'log10_p': float(sign_test_log10p(k, len(chk))),
                         'decoy_log10_p': decoy_best, 'decoys': decoy})
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


def degenerate(bits, min_distinct=MIN_DISTINCT_BYTES):
    """True when a bit stream carries no information, so a code claim on it is not evidence.

    The all-zero (and every constant) sequence is a codeword of every linear code, which is why the
    Reed-Solomon rule of §13.1 note 5 refuses codewords with fewer than four distinct symbols. An
    idle carrier reaches the F2 sign test the same way — every parity check of a constant stream is
    satisfied identically — so the same rule applies here, counted over whole bytes of the decoded
    information sequence."""
    b = np.asarray(bits, dtype=np.uint8)
    if len(b) < 8 * min_distinct:
        return True
    byte_vals = np.packbits(b[:len(b) // 8 * 8])
    return int(len(np.unique(byte_vals))) < min_distinct


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
