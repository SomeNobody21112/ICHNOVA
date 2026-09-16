"""Blind FEC / interleaver identification: dual-code syndrome test over a code catalogue.

Every codeword of a rate-1/2 convolutional code (c1 = g1*u, c2 = g2*u over GF(2)) satisfies
    g2(D)·c1(D) + g1(D)·c2(D) = 0.
For each trellis step t ≥ K-1 this gives one parity check over the received coded bits,
valid for any encoder start state and for codewords truncated at any point. With soft
values th = tanh(LLR/2), a check's soft value is the product of th over its bits.

Null model: if the coded bits are independent and symmetric (noise, uncoded random data),
each check's sign is a fair coin, and consecutive checks are linearly independent over
GF(2) (check t is the first to involve c1(t), c2(t)), so the number of positive checks is
exactly Binomial(n_checks, 1/2). The p-value P(X >= n_positive) is therefore exact under
that null, needs no LLR calibration, and grows stronger with every covered bit, so a
hypothesis covering 36 bits can never look as certain as one covering 120.
Wrong-interleaver hypotheses on truly coded data are not guaranteed to follow this null;
their behaviour is measured empirically (eval/nullset.py).
"""

import numpy as np
from scipy.special import bdtrc
from fec import conv_encode, viterbi_decode, block_interleave, block_deinterleave


# Generator convention (fec.conv_encode): bit j of g taps the input delayed by j samples
# (bit 0 = current input). This is the bit-reversal of the MATLAB poly2trellis / "MSB =
# current input" convention, so "171/133" here equals "117/155" in that convention.
CODE_CATALOGUE = [
    {'name': 'conv_k7_r12_171_133', 'generators': [0o171, 0o133], 'K': 7},
    {'name': 'conv_k5_r12_23_35', 'generators': [0o23, 0o35], 'K': 5},
    {'name': 'conv_k3_r12_7_5', 'generators': [0o7, 0o5], 'K': 3},
]

# Receiver search domain for single-block interleavers (a receiver spec, max 384 bits).
INTERLEAVER_ROWS = (2, 16)
INTERLEAVER_COLS = (4, 24)


def interleaver_candidates(n_llrs):
    """Block interleavers r×c within the search domain with 0.5·n ≤ r·c ≤ n.

    The lower bound allows the matched-filter tail (extra near-zero symbols) to make up
    to half of the observed stream."""
    return [(r, c)
            for r in range(INTERLEAVER_ROWS[0], INTERLEAVER_ROWS[1] + 1)
            for c in range(INTERLEAVER_COLS[0], INTERLEAVER_COLS[1] + 1)
            if 0.5 * n_llrs <= r * c <= n_llrs]


_DEINTERLEAVE_INDEX = {}


def deinterleave_index(rows, cols):
    """Index array idx such that stream[idx] is the deinterleaved coded sequence."""
    key = (rows, cols)
    if key not in _DEINTERLEAVE_INDEX:
        _DEINTERLEAVE_INDEX[key] = block_deinterleave(np.arange(rows * cols), rows, cols)
    return _DEINTERLEAVE_INDEX[key]


def syndrome_checks(th, code):
    """Soft parity-check values of g2(D)·c1(D) + g1(D)·c2(D) for steps t = K-1 … T-1.

    th: tanh(LLR/2) of the deinterleaved stream, c1/c2 alternating (LLR > 0 means bit 0)."""
    g1, g2 = code['generators']
    K = code['K']
    T = len(th) // 2
    n = T - K + 1
    if n <= 0:
        return np.empty(0)
    c1, c2 = th[0:2 * T:2], th[1:2 * T:2]
    prod = np.ones(n)
    for j in range(K):
        if (g2 >> j) & 1:
            prod *= c1[K - 1 - j:K - 1 - j + n]
        if (g1 >> j) & 1:
            prod *= c2[K - 1 - j:K - 1 - j + n]
    return prod


def sign_test_log10p(n_positive, n_checks):
    """log10 P(Binomial(n_checks, 1/2) ≥ n_positive), vectorized."""
    n_positive = np.asarray(n_positive)
    p = bdtrc(n_positive - 1, n_checks, 0.5)
    return np.log10(np.where(n_positive > 0, np.maximum(p, 1e-300), 1.0))


def decode_hypothesis(llrs, code, dims):
    """Viterbi-decode one hypothesis and compute the comparison scores for it.

    Returns decoded bits plus: covered bits, hard re-encode consistency, soft path metric
    Σ L·(1-2c)/Σ|L|, and soft disagreement D = Σ_mismatch |L| (nats, for MDL)."""
    rows, cols = dims
    n = rows * cols
    stream = np.asarray(llrs[:n], dtype=float)
    deint = stream[deinterleave_index(rows, cols)]
    T = n // 2
    decoded = viterbi_decode(deint[:2 * T], code['generators'], code['K'], terminated=False)
    reenc = conv_encode(decoded, code['generators'], code['K'])[:2 * T]
    full = np.zeros(n, dtype=np.uint8)
    full[:2 * T] = reenc
    reint = block_interleave(full, rows, cols)
    covered = np.zeros(n, dtype=np.uint8)
    covered[:2 * T] = 1
    covered = block_interleave(covered, rows, cols).astype(bool)
    L = stream[covered]
    c = reint[covered]
    mismatch = (L < 0).astype(np.uint8) != c
    abs_sum = float(np.sum(np.abs(L))) + 1e-12
    return {
        'decoded_bits': decoded,
        'covered_bits': int(covered.sum()),
        'consistency': float(1.0 - mismatch.mean()) if len(L) else 0.0,
        'path_metric': float(np.sum(L * (1 - 2.0 * c)) / abs_sum),
        'soft_disagreement_nats': float(np.sum(np.abs(L[mismatch]))),
    }
