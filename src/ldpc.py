"""CCSDS TC LDPC (128,64) code (CCSDS 231.0-B-4 §4): parity-check matrix, systematic generator,
syndrome evidence and a normalised min-sum decoder.

H (64×128) is built from 16×16 circulants exactly as printed in §4.2.2 a). The generator G = [I | W]
uses W from Table 4-1 (rows 1, 17, 33, 49 from hex; every other row a right circular shift of each
16-bit circulant). Both come from references/ccsds_constants.json and are checked against each other
at import: H·Gᵀ = 0 over GF(2) and rank(H) = 64.

Syndrome evidence (Constitution v2.5 §13.1): the 64 rows of H are linearly independent, so for
uniformly random bits the syndrome is uniform on GF(2)⁶⁴. Each check is satisfied with probability
exactly ½, independently, so the number of satisfied checks over F complete codewords is exactly
Binomial(64F, ½) under the null. Every row has even weight (8), so the all-ones word is a codeword
and the statistic does not depend on polarity.

LLR convention: LLR > 0 favours bit 0 (as in the rest of the engine).
"""

import json
import os

import numpy as np

N, K, M_CIRC = 128, 64, 16
REF = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'references', 'ccsds_constants.json')


def _circulant(token):
    I = np.eye(M_CIRC, dtype=np.uint8)
    if token == '0M':
        return np.zeros((M_CIRC, M_CIRC), dtype=np.uint8)
    if token == 'I':
        return I
    if token.startswith('I+'):
        return I ^ np.roll(I, int(token[2:]), axis=1)
    return np.roll(I, int(token), axis=1)          # Φ^k: non-zero at column i + k mod M


def gf2_rank(A):
    A = (np.asarray(A) % 2).astype(np.uint8).copy()
    r = 0
    for c in range(A.shape[1]):
        piv = np.flatnonzero(A[r:, c])
        if not len(piv):
            continue
        p = r + piv[0]
        A[[r, p]] = A[[p, r]]
        rows = np.flatnonzero(A[:, c])
        rows = rows[rows != r]
        A[rows] ^= A[r]
        r += 1
        if r == A.shape[0]:
            break
    return r


def _build():
    ref = json.load(open(REF))['ldpc_tc_128_64']
    H = np.block([[_circulant(t) for t in row] for row in ref['H_blocks']]).astype(np.uint8)
    W = np.zeros((K, K), dtype=np.uint8)
    for b, h in enumerate(ref['W_row_hex_rows_1_17_33_49']):
        segs = np.array([int(c) for c in bin(int(h, 16))[2:].zfill(64)], dtype=np.uint8).reshape(4, M_CIRC)
        for s in range(M_CIRC):
            W[b * M_CIRC + s] = np.concatenate([np.roll(seg, s) for seg in segs])
    G = np.hstack([np.eye(K, dtype=np.uint8), W])
    if ((H.astype(np.int64) @ G.T.astype(np.int64)) % 2).any() or gf2_rank(H) != K:
        raise ValueError('CCSDS LDPC (128,64): H and G from the reference data are inconsistent')
    return H, G


H, G = _build()
ROW_IDX = np.array([np.flatnonzero(r) for r in H])     # (64, 8): every row has weight 8
assert ROW_IDX.shape == (K, 8)


def encode(msg_bits):
    """(F, 64) information bits → (F, 128) systematic codewords."""
    msg = np.atleast_2d(np.asarray(msg_bits, dtype=np.int64))
    return (msg @ G.astype(np.int64) % 2).astype(np.uint8)


def satisfied_checks(hard_bits):
    """(F, 128) hard bits → satisfied-check count per codeword."""
    b = np.atleast_2d(np.asarray(hard_bits, dtype=np.uint8))
    return K - (b.astype(np.int64) @ H.T.astype(np.int64) % 2).sum(axis=1)


def minsum_decode(llrs, max_iter=50, scale=0.75):
    """Normalised min-sum over a batch. llrs: (F, 128). Returns (bits (F,128), converged (F,), iterations)."""
    L = np.atleast_2d(np.asarray(llrs, dtype=np.float64))
    F = L.shape[0]
    flat = ROW_IDX.reshape(-1)                                   # edge → variable
    inc = np.zeros((flat.size, N))
    inc[np.arange(flat.size), flat] = 1.0                        # edge-to-variable incidence
    v2c = L[:, ROW_IDX]                                          # (F, 64, 8)
    total = L.copy()
    it = 0
    for it in range(1, max_iter + 1):
        mag = np.abs(v2c)
        sgn = np.where(v2c < 0, -1.0, 1.0)
        prod = np.prod(sgn, axis=2, keepdims=True)
        order = np.argsort(mag, axis=2)
        min1 = np.take_along_axis(mag, order[:, :, :1], axis=2)
        min2 = np.take_along_axis(mag, order[:, :, 1:2], axis=2)
        is_min = np.zeros_like(mag, dtype=bool)
        np.put_along_axis(is_min, order[:, :, :1], True, axis=2)
        c2v = scale * prod * sgn * np.where(is_min, min2, min1)
        total = L + c2v.reshape(F, -1) @ inc
        hard = (total < 0).astype(np.uint8)
        if (satisfied_checks(hard) == K).all():
            break
        v2c = total[:, ROW_IDX] - c2v
    hard = (total < 0).astype(np.uint8)
    return hard, satisfied_checks(hard) == K, it
