"""CCSDS Reed-Solomon codes (CCSDS 131.0-B-5 §4, Annex F): GF(2⁸), encoder, errors-only decoder,
dual-basis symbols, interleaving depth I, virtual fill, and the null probability used for acceptance.

Field: F(x) = x⁸+x⁷+x²+x+1 (0x187), α = x. Code generator g(x) = Π_{j=128−E}^{127+E} (x − α^{11j}).
Writing β = α¹¹ (primitive, since gcd(11, 255) = 1), the roots are β^{fcr+i}, i = 0 … 2E−1, with
fcr = 128 − E. Every table below is therefore built in base β: log[v] = i ⇔ β^i = v.

Symbol order in arrays: index 0 is the highest-degree coefficient, i.e. the first transmitted symbol
(systematic: information symbols first, then 2E check symbols).

Acceptance statistic (Constitution v2.5 §13.1): a bounded-distance decoder with radius E succeeds on
a uniformly random word of length n′ with probability exactly V(n′, E) / 256^{2E}, where
V(n, t) = Σ_{i≤t} C(n, i)·255^i (decoding spheres of a code with minimum distance 2E+1 are disjoint).
Decoder success is converted to that probability; it is never accepted on its own.
"""

import json
import os
from functools import lru_cache
from math import comb, lgamma, log, log10

import numpy as np

PRIM_CCSDS = 0x187
REF = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'references', 'ccsds_constants.json')


class GF256:
    """GF(2⁸) arithmetic with log/antilog tables in base β = α^power (α = x modulo `prim`)."""

    def __init__(self, prim=PRIM_CCSDS, power=11):
        alpha = [1]
        for _ in range(254):
            v = alpha[-1] << 1
            if v & 0x100:
                v ^= prim
            alpha.append(v)
        if len(set(alpha)) != 255:
            raise ValueError('field polynomial is not primitive')
        self.exp = np.zeros(510, dtype=np.int64)
        self.log = np.full(256, -1, dtype=np.int64)
        for i in range(255):
            v = alpha[(power * i) % 255]
            self.exp[i] = self.exp[i + 255] = v
            self.log[v] = i
        if (self.log[1:] < 0).any():
            raise ValueError('β = α^power is not primitive')

    def mul(self, a, b):
        if a == 0 or b == 0:
            return 0
        return int(self.exp[self.log[a] + self.log[b]])

    def div(self, a, b):
        if b == 0:
            raise ZeroDivisionError
        if a == 0:
            return 0
        return int(self.exp[(self.log[a] - self.log[b]) % 255])

    def pow_beta(self, e):
        return int(self.exp[e % 255])


GF = GF256()


def _poly_mul(p, q):
    """Polynomials as lists, low degree first."""
    out = [0] * (len(p) + len(q) - 1)
    for i, a in enumerate(p):
        if a:
            for j, b in enumerate(q):
                if b:
                    out[i + j] ^= GF.mul(a, b)
    return out


def _poly_eval_low(p, x):
    """Evaluate p (low degree first) at x."""
    y = 0
    for c in reversed(p):
        y = GF.mul(y, x) ^ c
    return y


class ReedSolomon:
    """RS(255, 255−2E) over GF(2⁸) in the CCSDS convention (conventional basis inside)."""

    def __init__(self, E):
        if E not in (8, 16):
            raise ValueError('catalogue v1: E ∈ {8, 16}')
        self.E, self.nsym, self.fcr = E, 2 * E, 128 - E
        self.n, self.k = 255, 255 - 2 * E
        g = [1]
        for i in range(self.nsym):
            g = _poly_mul(g, [GF.pow_beta(self.fcr + i), 1])      # (x + β^{fcr+i}), low first
        self.gen_low = g                                           # monic, degree 2E
        self.gen_high = list(reversed(g))

    # ------------------------------------------------------------------ encoding
    def encode(self, msg):
        """Systematic encoding of conventional-basis symbols; len(msg) ≤ k (shortened when shorter)."""
        msg = [int(v) for v in msg]
        if len(msg) > self.k:
            raise ValueError('message too long')
        reg = [0] * self.nsym                     # remainder coefficients, highest degree first
        g = self.gen_high[1:]                     # drop the monic leading 1
        for m in msg:
            fb = m ^ reg[0]
            reg = reg[1:] + [0]
            if fb:
                lf = GF.log[fb]
                for j, gc in enumerate(g):
                    if gc:
                        reg[j] ^= int(GF.exp[lf + GF.log[gc]])
        return np.array(msg + reg, dtype=np.int64)

    # ------------------------------------------------------------------ decoding
    def syndromes(self, words):
        """(C, n′) conventional words → (C, 2E) syndromes S_i = r(β^{fcr+i})."""
        words = np.atleast_2d(np.asarray(words, dtype=np.int64))
        n = words.shape[1]
        p = np.arange(n - 1, -1, -1)                              # coefficient degree per index
        e = ((self.fcr + np.arange(self.nsym))[:, None] * p[None, :]) % 255   # (2E, n′)
        lw = GF.log[words]                                         # (C, n′), −1 for zero
        nz = lw >= 0
        terms = np.where(nz[:, None, :], GF.exp[(np.where(nz, lw, 0)[:, None, :] + e[None, :, :]) % 255], 0)
        return np.bitwise_xor.reduce(terms, axis=2)

    def decode(self, word):
        """Errors-only bounded-distance decoding of one conventional word of length n′ ≤ 255.

        Returns (corrected word, number of symbol errors corrected, success)."""
        r = np.asarray(word, dtype=np.int64).copy()
        n = len(r)
        S = [int(v) for v in self.syndromes(r[None, :])[0]]
        if not any(S):
            return r, 0, True
        # Berlekamp–Massey (connection polynomial, low degree first)
        C, B, L, m, b = [1], [1], 0, 1, 1
        for i in range(self.nsym):
            d = S[i]
            for j in range(1, L + 1):
                if j < len(C) and C[j]:
                    d ^= GF.mul(C[j], S[i - j])
            if d == 0:
                m += 1
                continue
            T = list(C)
            coef = GF.div(d, b)
            shifted = [0] * m + [GF.mul(coef, x) for x in B]
            C = [(C[j] if j < len(C) else 0) ^ (shifted[j] if j < len(shifted) else 0)
                 for j in range(max(len(C), len(shifted)))]
            if 2 * L <= i:
                L, B, b, m = i + 1 - L, T, d, 1
            else:
                m += 1
        while len(C) > 1 and C[-1] == 0:
            C.pop()
        if L > self.E or len(C) - 1 != L:
            return np.asarray(word, dtype=np.int64), 0, False
        # Chien search: error at degree p ⇔ Λ(β^{−p}) = 0
        positions = [p for p in range(n) if _poly_eval_low(C, GF.pow_beta(-p)) == 0]
        if len(positions) != L:
            return np.asarray(word, dtype=np.int64), 0, False
        # Forney: e_p = X^{1−fcr} · Ω(X⁻¹) / Λ′(X⁻¹), X = β^p, Ω = S·Λ mod x^{2E}
        omega = _poly_mul(S, C)[:self.nsym]
        dC = [C[j] if j % 2 == 1 else 0 for j in range(1, len(C))]       # formal derivative
        for p in positions:
            xinv = GF.pow_beta(-p)
            num = GF.mul(GF.pow_beta(p * (1 - self.fcr)), _poly_eval_low(omega, xinv))
            den = _poly_eval_low(dC, xinv)
            if den == 0:
                return np.asarray(word, dtype=np.int64), 0, False
            r[n - 1 - p] ^= GF.div(num, den)
        if self.syndromes(r[None, :]).any():
            return np.asarray(word, dtype=np.int64), 0, False
        return r, L, True

    # ------------------------------------------------------------------ null model
    @lru_cache(maxsize=None)
    def log10_random_decode_probability(self, n_prime):
        """log10 P(a uniformly random word of length n′ decodes within radius E)."""
        v = sum(comb(n_prime, i) * 255 ** i for i in range(self.E + 1))
        return log10(v) - self.nsym * log10(256)


@lru_cache(maxsize=None)
def code(E):
    return ReedSolomon(E)


# ---------------------------------------------------------------------- dual basis (Annex F)
def _dual_tables():
    ref = json.load(open(REF))['rs_dual_basis']
    T = np.array([[int(c) for c in row] for row in ref['T_l_rows_u7_to_u0']], dtype=np.int64)
    Tinv = np.array([[int(c) for c in row] for row in ref['T_l_inverse_rows_z0_to_z7']], dtype=np.int64)
    bits = np.array([[(v >> (7 - i)) & 1 for i in range(8)] for v in range(256)], dtype=np.int64)
    weights = 1 << np.arange(7, -1, -1)
    to_dual = (bits @ T % 2) @ weights           # [u7 … u0] · T = [z0 … z7], z0 = MSB
    from_dual = (bits @ Tinv % 2) @ weights      # [z0 … z7] · T⁻¹ = [u7 … u0]
    if not np.array_equal(from_dual[to_dual], np.arange(256)):
        raise ValueError('dual-basis matrices are not inverse')
    return to_dual.astype(np.int64), from_dual.astype(np.int64)


TO_DUAL, FROM_DUAL = _dual_tables()


# ---------------------------------------------------------------------- CCSDS codeblocks
def check_profile(E, I, Q):
    rs = code(E)
    if I not in (1, 2, 3, 4, 5, 8):
        raise ValueError('interleaving depth I ∈ {1,2,3,4,5,8}')
    if Q % I or not 0 <= Q < rs.k * I:
        raise ValueError('virtual fill Q must be a multiple of I and smaller than k·I')
    return rs


def codeblock_symbols(E, I, Q=0):
    """Transmitted codeblock length in symbols: 255·I − Q."""
    check_profile(E, I, Q)
    return 255 * I - Q


def encode_codeblock(info_dual, E, I, Q=0):
    """CCSDS interleaved codeblock in dual basis (§4.3.5–4.3.8).

    info_dual: the k·I − Q transmitted information symbols. Symbol m goes to codeword m mod I (with
    Q a multiple of I, the Q virtual-fill zeros put Q/I leading zeros in each codeword, which do not
    change the check symbols). Output: information symbols, then the 2E·I interleaved check symbols."""
    rs = check_profile(E, I, Q)
    info_dual = np.asarray(info_dual, dtype=np.int64)
    if len(info_dual) != rs.k * I - Q:
        raise ValueError(f'expected {rs.k * I - Q} information symbols')
    parities = [TO_DUAL[rs.encode(FROM_DUAL[info_dual[j::I]])[-rs.nsym:]] for j in range(I)]
    return np.concatenate([info_dual, np.stack(parities, axis=1).reshape(-1)])


def decode_codeblock(block_dual, E, I, Q=0):
    """Deinterleave and decode a received codeblock of dual-basis symbols.

    A decoded codeword with fewer than 4 distinct symbol values is flagged degenerate: constant or
    two-valued bit streams (idle carriers, alternating patterns) can be codewords, and they are not
    evidence of a Reed-Solomon code."""
    rs = check_profile(E, I, Q)
    block = np.asarray(block_dual, dtype=np.int64)
    n_info = rs.k * I - Q
    if len(block) != n_info + rs.nsym * I:
        raise ValueError('codeblock length does not match (E, I, Q)')
    info, parity = block[:n_info].copy(), block[n_info:]
    codewords, decoded, errors = [], 0, 0
    for j in range(I):
        word_dual = np.concatenate([info[j::I], parity[j::I]])
        corrected, n_err, ok = rs.decode(FROM_DUAL[word_dual])
        cw = TO_DUAL[corrected]
        distinct = int(len(np.unique(cw)))
        codewords.append({'decoded': bool(ok), 'symbol_errors': int(n_err) if ok else None,
                          'distinct_symbols': distinct, 'degenerate': bool(ok and distinct < 4)})
        if ok:
            decoded += 1
            errors += n_err
            info[j::I] = cw[:len(info[j::I])]
    return {'info_dual': info, 'codewords': codewords, 'n_decoded': decoded, 'n_codewords': I,
            'symbol_errors': errors, 'degenerate': any(c['degenerate'] for c in codewords),
            'log10_p_single': rs.log10_random_decode_probability(255 - Q // I)}


def log10_binom_tail(k, n, log10_p):
    """log10 P(X ≥ k), X ~ Binomial(n, p); stable for extremely small p (log-sum-exp over terms)."""
    if k <= 0:
        return 0.0
    if k > n:
        return float('-inf')
    ln_p = log10_p * log(10)
    ln_q = float(np.log1p(-10.0 ** log10_p)) if log10_p > -12 else -10.0 ** log10_p
    terms = np.array([lgamma(n + 1) - lgamma(d + 1) - lgamma(n - d + 1) + d * ln_p + (n - d) * ln_q
                      for d in range(k, n + 1)])
    mx = terms.max()
    return float((mx + np.log(np.exp(terms - mx).sum())) / log(10))


def symbols_to_bits(symbols):
    """Symbols (0–255) → bits, MSB first (dual-basis z0 is transmitted first)."""
    return np.unpackbits(np.asarray(symbols, dtype=np.uint8))


def bits_to_symbols(bits):
    bits = np.asarray(bits, dtype=np.uint8)
    return np.packbits(bits[:len(bits) // 8 * 8]).astype(np.int64)
