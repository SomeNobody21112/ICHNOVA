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


_SCAN_INDEX = {}


def _scan_index(dims):
    """Stacked deinterleave indices for a tuple of (rows, cols); padding points at a neutral 1.0."""
    if dims not in _SCAN_INDEX:
        L = max(r * c for r, c in dims)
        idx = np.full((len(dims), L), -1, dtype=np.int64)
        for i, (r, c) in enumerate(dims):
            idx[i, :r * c] = deinterleave_index(r, c)
        _SCAN_INDEX[dims] = (idx, np.array([r * c // 2 for r, c in dims]))
    return _SCAN_INDEX[dims]


def syndrome_scan(th, dims_list, codes=CODE_CATALOGUE):
    """syndrome_checks() for every (interleaver, code) pair at once.

    All candidate deinterleavings of one front end are gathered into one padded matrix, and each
    code's parity products use the same factor order as syndrome_checks(), so every check sign (and
    therefore every sign-test p-value) is identical to the per-pair loop. Returns a dict of arrays
    rows, cols, code, n, pos, sum, sq in (dims, code) order, skipping pairs without checks."""
    dims = tuple((r, c) for r, c in dims_list if r * c <= len(th))
    empty = {k: np.zeros(0, dtype=float if k in ('sum', 'sq') else np.int64) for k in ('rows', 'cols', 'code', 'n', 'pos', 'sum', 'sq')}
    if not dims:
        return empty
    idx, T = _scan_index(dims)
    D = np.append(th, 1.0)[idx]
    Tmax = idx.shape[1] // 2
    c1, c2 = D[:, 0:2 * Tmax:2], D[:, 1:2 * Tmax:2]
    cols = {k: [] for k in empty}
    for ci, code in enumerate(codes):
        g1, g2 = code['generators']
        K = code['K']
        n_max = Tmax - K + 1
        if n_max <= 0:
            continue
        prod = np.ones((len(dims), n_max))
        for j in range(K):
            if (g2 >> j) & 1:
                prod *= c1[:, K - 1 - j:K - 1 - j + n_max]
            if (g1 >> j) & 1:
                prod *= c2[:, K - 1 - j:K - 1 - j + n_max]
        n_checks = T - K + 1
        masked = np.where(np.arange(n_max)[None, :] < n_checks[:, None], prod, 0.0)
        cols['n'].append(n_checks)
        cols['pos'].append(np.count_nonzero(masked > 0, axis=1))
        cols['sum'].append(masked.sum(axis=1))
        cols['sq'].append(np.einsum('ij,ij->i', masked, masked))
        cols['code'].append(np.full(len(dims), ci))
        cols['rows'].append(np.array([d[0] for d in dims]))
        cols['cols'].append(np.array([d[1] for d in dims]))
    if not cols['n']:
        return empty
    # Stack as [code, dims] then reorder to (dims, code) - the order of the loop this replaces.
    out = {k: np.stack(v, axis=1).reshape(-1) for k, v in cols.items()}
    keep = out['n'] > 0
    return {k: v[keep] for k, v in out.items()}


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
