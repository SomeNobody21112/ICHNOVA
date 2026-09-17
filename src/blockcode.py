"""Outer block codes on a synchronised stream (family F4, Constitution v2.5 §12.1, §13.1).

Two catalogue items, each with an **exact** null so nothing is ever accepted on decoder success alone
(§13.1 note 5):

1. **CCSDS Reed-Solomon** after a catalogue marker. The measured frame period fixes the codeblock:
   8·(255·I − Q) = P − (marker bits), with E ∈ {8, 16}, I ∈ {1,2,3,4,5,8} and virtual fill Q a
   multiple of I. Each hypothesis is (E, I, Q) × randomizer ∈ {none, TM 131071, TM 255}. Uniformly
   random bytes decode as a codeword with probability V(n′,E)/256^{2E} (rs.py), so over C codewords
   the statistic is the exact tail P(≥ D successes) — 2×10⁻⁵ per RS(255,239) codeword is why the
   count, not a single success, is the evidence. Degenerate codewords (fewer than four distinct
   symbols: idle carriers, constant fill) are rejected.

2. **CCSDS TC LDPC (128,64)** by codeword offset o ∈ [0,128) × randomizer ∈ {none, TC BTG preset per
   codeword}. The 64 rows of H are linearly independent, so under independent fair bits the satisfied
   checks of F complete codewords are exactly Binomial(64·F, ½); the statistic is that sign test, and
   min-sum decoding runs only afterwards. Every row of H has even weight 8, so the count is invariant
   to a 180° polarity flip.

The parity of a row over a derandomized codeword equals its parity over the raw codeword XOR the
row's parity over the 128-bit preset sequence — a constant per row — so the randomized hypotheses are
evaluated from the same single pass over the stream.
"""

import numpy as np

import framing
import ldpc
import rs

RS_E = (8, 16)
RS_DEPTHS = (1, 2, 3, 4, 5, 8)
RS_RANDOMIZERS = (None, 'tm_131071', 'tm_255')
LDPC_RANDOMIZERS = (None, 'tc_btg')
MIN_CODEWORDS = 2               # a block-code claim needs at least two codewords


def rank(row):
    """Sort key over F4 hypotheses: p-value first, then the fraction of evidence that agrees.

    Both statistics reach the 1e-300 floor on a long capture, so the tail alone cannot order
    hypotheses. `agreement` is the decoded-codeword fraction (RS) or the satisfied-check fraction
    (LDPC). It matters most for LDPC: every row of H has even weight, so a complemented codeword is
    a codeword, and a front end with residual carrier offset whose polarity flips between segments
    still satisfies almost every check while its payload is complemented in half the segments. The
    coherent front end has a strictly higher agreement, so ranking on it reports the usable payload."""
    return (row['log10_p'], -row['agreement'])


def rs_profiles(codeblock_bits):
    """(E, I, Q) profiles whose transmitted codeblock is exactly `codeblock_bits` bits long."""
    if codeblock_bits <= 0 or codeblock_bits % 8:
        return []
    symbols = codeblock_bits // 8
    out = []
    for E in RS_E:
        k = 255 - 2 * E
        for I in RS_DEPTHS:
            Q = 255 * I - symbols
            if Q < 0 or Q % I or Q >= k * I:
                continue
            out.append((E, I, Q))
    return out


def _frame_payloads(bits, period, offset, marker_bits, n_frames=None):
    """The bits of each whole frame after the marker (one row per frame)."""
    b = np.asarray(bits, dtype=np.uint8)
    F = (len(b) - offset) // period
    if n_frames is not None:
        F = min(F, n_frames)
    if F < 1:
        return np.zeros((0, 0), dtype=np.uint8)
    rows = b[offset:offset + F * period].reshape(F, period)
    return rows[:, marker_bits:]


def rs_scan(bits, frame):
    """Every RS hypothesis implied by an accepted frame; one row per (E, I, Q, randomizer).

    `frame` is a pipeline frame hypothesis (period_bits, offset_bits, marker_bits). Rows carry the
    exact tail probability, the decoded-codeword counts and the degenerate flag."""
    payloads = _frame_payloads(bits, frame['period_bits'], frame['offset_bits'], frame['marker_bits'])
    rows = []
    if payloads.size == 0 or payloads.shape[0] * 1 < 1:
        return rows
    n_bits = payloads.shape[1]
    for (E, I, Q) in rs_profiles(n_bits):
        for name in RS_RANDOMIZERS:
            pn = framing.pn_sequence(name, n_bits) if name else None
            C = I * payloads.shape[0]
            if C < MIN_CODEWORDS:
                continue
            decoded, errors, degenerate, info = 0, 0, False, []
            for row in payloads:
                block = rs.bits_to_symbols(row ^ pn if pn is not None else row)
                d = rs.decode_codeblock(block, E, I, Q)
                decoded += d['n_decoded']
                errors += d['symbol_errors']
                degenerate = degenerate or d['degenerate']
                info.append(d['info_dual'])
            log10_single = rs.code(E).log10_random_decode_probability(255 - Q // I)
            rows.append({'code': f'ccsds_rs_255_{255 - 2 * E}', 'E': E, 'I': I, 'Q': Q,
                         'randomizer': name, 'n_codewords': C, 'n_decoded': decoded,
                         'symbol_errors': errors, 'degenerate': degenerate,
                         'log10_p_single': log10_single, 'agreement': decoded / C,
                         'log10_p': rs.log10_binom_tail(decoded, C, log10_single),
                         '_info': info})
    return rows


def _row_parity_matrix(bits):
    """fail[r, t] = parity of H row r over the 128-bit codeword starting at bit t."""
    b = np.asarray(bits, dtype=np.uint8)
    T = len(b) - (ldpc.N - 1)
    if T <= 0:
        return np.zeros((ldpc.K, 0), dtype=np.uint8)
    fail = np.zeros((ldpc.K, T), dtype=np.uint8)
    for r, pos in enumerate(ldpc.ROW_IDX):
        acc = np.zeros(T, dtype=np.uint8)
        for p in pos:
            acc ^= b[p:p + T]
        fail[r] = acc
    return fail


def ldpc_scan(bits):
    """Every LDPC hypothesis on a stream: codeword offset x randomizer, with the exact sign test."""
    b = np.asarray(bits, dtype=np.uint8)
    fail = _row_parity_matrix(b)
    rows = []
    if fail.shape[1] == 0:
        return rows
    # Derandomizing with a preset sequence flips each row's parity by a constant (see module docstring).
    flip = {None: np.zeros(ldpc.K, dtype=np.uint8)}
    for name in LDPC_RANDOMIZERS:
        if name is None:
            continue
        pn = framing.pn_sequence(name, ldpc.N)
        flip[name] = np.array([pn[pos].sum() % 2 for pos in ldpc.ROW_IDX], dtype=np.uint8)
    for o in range(ldpc.N):
        starts = np.arange(o, len(b) - ldpc.N + 1, ldpc.N)
        F = len(starts)
        if F < MIN_CODEWORDS:
            continue
        sub = fail[:, starts]                                  # (64, F)
        for name in LDPC_RANDOMIZERS:
            bad = int(np.count_nonzero(sub ^ flip[name][:, None]))
            S = ldpc.K * F - bad
            rows.append({'code': 'ccsds_tc_ldpc_128_64', 'offset': o, 'randomizer': name,
                         'n_codewords': F, 'satisfied_checks': S, 'total_checks': ldpc.K * F,
                         'agreement': S / (ldpc.K * F),
                         'log10_p': framing.log10_sign(S, ldpc.K * F)})
    return rows


def ldpc_decode(bits, llrs, offset, randomizer):
    """Min-sum decode of the codewords of an accepted LDPC hypothesis.

    `llrs` are the front end's LLRs for the same bit positions (LLR > 0 favours bit 0) or None, in
    which case hard decisions are used with unit magnitude."""
    b = np.asarray(bits, dtype=np.uint8)
    starts = np.arange(offset, len(b) - ldpc.N + 1, ldpc.N)
    words = np.stack([b[s:s + ldpc.N] for s in starts])
    if llrs is None:
        L = 1.0 - 2.0 * words.astype(float)
    else:
        L = np.stack([np.asarray(llrs, dtype=float)[s:s + ldpc.N] for s in starts])
    if randomizer:
        pn = framing.pn_sequence(randomizer, ldpc.N)
        sign = 1.0 - 2.0 * pn.astype(float)
        L = L * sign
        words = words ^ pn
    hard, converged, iters = ldpc.minsum_decode(L)
    # Every codeword contributes its information bits, converged or not, so the payload stays aligned
    # with the transmission; `converged_codewords` says which blocks are proven consistent with H.
    return {'n_codewords': int(len(words)), 'n_converged': int(converged.sum()),
            'iterations': int(iters), 'info_bits': hard[:, :ldpc.K].reshape(-1).astype(np.uint8),
            'converged_codewords': converged.astype(bool).tolist(),
            'satisfied_checks': int(ldpc.satisfied_checks(hard).sum())}
