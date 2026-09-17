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

from functools import lru_cache

import numpy as np
from scipy.special import bdtrc
from fec import conv_encode, viterbi_decode
import interleavers
from interleavers import INTERLEAVER_ROWS, INTERLEAVER_COLS


# Generator convention (fec.conv_encode): bit j of g taps the input delayed by j samples
# (bit 0 = current input). This is the bit-reversal of the MATLAB poly2trellis / "MSB =
# current input" convention, so "171/133" here equals "117/155" in that convention.
CODE_CATALOGUE = [
    {'name': 'conv_k7_r12_171_133', 'generators': [0o171, 0o133], 'K': 7},
    {'name': 'conv_k5_r12_23_35', 'generators': [0o23, 0o35], 'K': 5},
    {'name': 'conv_k3_r12_7_5', 'generators': [0o7, 0o5], 'K': 3},
]

def interleaver_candidates(n_llrs):
    """Block interleavers r×c within the search domain with 0.5·n ≤ r·c ≤ n.

    The lower bound allows the matched-filter tail (extra near-zero symbols) to make up
    to half of the observed stream."""
    return [(r, c)
            for r in range(INTERLEAVER_ROWS[0], INTERLEAVER_ROWS[1] + 1)
            for c in range(INTERLEAVER_COLS[0], INTERLEAVER_COLS[1] + 1)
            if 0.5 * n_llrs <= r * c <= n_llrs]


def deinterleave_index(rows, cols):
    """Index array idx such that stream[idx] is the deinterleaved coded sequence (block r×c)."""
    return interleavers.deinterleave_index(('block', rows, cols))


def as_spec(interleaver):
    """Interleaver spec tuple (interleavers.py); a bare (rows, cols) pair means a block interleaver."""
    t = tuple(interleaver)
    return t if isinstance(t[0], str) else ('block', int(t[0]), int(t[1]))


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


@lru_cache(maxsize=64)
def _scan_index(specs, n_obs, n_conv=None):
    """Stacked deinterleave indices for a tuple of specs; padding (-1) points at a neutral 1.0."""
    rows = [interleavers.deinterleave_index(s, n_conv if (s[0] == 'conv' and n_conv) else n_obs)
            for s in specs]
    idx = np.full((len(specs), max(len(r) for r in rows)), -1, dtype=np.int64)
    for i, r in enumerate(rows):
        idx[i, :len(r)] = r
    idx.setflags(write=False)
    return idx, np.array([len(r) // 2 for r in rows])


def _fits(spec, n_obs):
    idx = interleavers.deinterleave_index(spec, n_obs)
    return len(idx) > 0 and int(idx.max()) < n_obs


def syndrome_scan(th, specs, codes=CODE_CATALOGUE, n_conv=None):
    """syndrome_checks() for every (interleaver, code) pair at once.

    `specs` are interleaver specs (interleavers.py) or bare (rows, cols) block pairs. All candidate
    deinterleavings of one front end are gathered into one padded matrix, and each code's parity
    products use the same factor order as syndrome_checks(), so every check sign (and therefore every
    sign-test p-value) is identical to the per-pair loop. Returns arrays spec (index into the returned
    'specs' tuple), code, n, pos, sum, sq in (spec, code) order, skipping pairs without checks and
    specs that do not fit in th."""
    n_obs = len(th)
    n_conv = n_obs if n_conv is None else min(int(n_conv), n_obs)
    specs = tuple(s for s in map(as_spec, specs) if _fits(s, n_conv if s[0] == 'conv' else n_obs))
    keys = ('spec', 'code', 'n', 'pos', 'sum', 'sq')
    empty = {k: np.zeros(0, dtype=float if k in ('sum', 'sq') else np.int64) for k in keys}
    empty['specs'] = specs
    if not specs:
        return empty
    idx, T = _scan_index(specs, n_obs, n_conv)
    D = np.append(th, 1.0)[idx]
    Tmax = idx.shape[1] // 2
    c1, c2 = D[:, 0:2 * Tmax:2], D[:, 1:2 * Tmax:2]
    cols = {k: [] for k in keys}
    for ci, code in enumerate(codes):
        g1, g2 = code['generators']
        K = code['K']
        n_max = Tmax - K + 1
        if n_max <= 0:
            continue
        prod = np.ones((len(specs), n_max))
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
        cols['code'].append(np.full(len(specs), ci))
        cols['spec'].append(np.arange(len(specs)))
    if not cols['n']:
        return empty
    # Stack as [code, spec] then reorder to (spec, code) - the order of the loop this replaces.
    out = {k: np.stack(v, axis=1).reshape(-1) for k, v in cols.items()}
    keep = out['n'] > 0
    out = {k: v[keep] for k, v in out.items()}
    out['specs'] = specs
    return out


def sign_test_log10p(n_positive, n_checks):
    """log10 P(Binomial(n_checks, 1/2) ≥ n_positive), vectorized."""
    n_positive = np.asarray(n_positive)
    p = bdtrc(n_positive - 1, n_checks, 0.5)
    return np.log10(np.where(n_positive > 0, np.maximum(p, 1e-300), 1.0))


def decode_hypothesis(llrs, code, interleaver, n_conv=None):
    """Viterbi-decode one hypothesis and compute the comparison scores for it.

    `interleaver` is a spec (interleavers.py) or a bare (rows, cols) block pair.
    Returns decoded bits plus: covered bits, hard re-encode consistency, soft path metric
    Σ L·(1-2c)/Σ|L|, and soft disagreement D = Σ_mismatch |L| (nats, for MDL). Covered bits are
    scored in stream order, so the sums add the same terms in the same order for every spec type."""
    stream = np.asarray(llrs, dtype=float)
    spec = as_spec(interleaver)
    n_obs = len(stream) if (spec[0] != 'conv' or not n_conv) else min(int(n_conv), len(stream))
    idx = interleavers.deinterleave_index(spec, n_obs)
    T = len(idx) // 2
    decoded = viterbi_decode(stream[idx[:2 * T]], code['generators'], code['K'], terminated=False)
    reenc = conv_encode(decoded, code['generators'], code['K'])[:2 * T]
    order = np.argsort(idx[:2 * T], kind='stable')
    L = stream[idx[:2 * T][order]]
    c = reenc[order]
    mismatch = (L < 0).astype(np.uint8) != c
    abs_sum = float(np.sum(np.abs(L))) + 1e-12
    return {
        'decoded_bits': decoded,
        'covered_bits': 2 * T,
        'consistency': float(1.0 - mismatch.mean()) if len(L) else 0.0,
        'path_metric': float(np.sum(L * (1 - 2.0 * c)) / abs_sum),
        'soft_disagreement_nats': float(np.sum(np.abs(L[mismatch]))),
    }
