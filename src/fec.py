"""Convolutional FEC: encoder, vectorized soft Viterbi, block interleaver."""

import numpy as np


def conv_encode(bits, generators, K):
    """Convolutional encoder with zero-tail termination.
    generators: list of generator polynomials in octal (e.g., [0o171, 0o133]).
    K: constraint length.
    Returns encoded bits as uint8 array.
    """
    bits = np.asarray(bits, dtype=np.uint8)
    tail = np.zeros(K - 1, dtype=np.uint8)
    bits_term = np.concatenate([bits, tail])
    n_out = len(generators)
    n_in = len(bits_term)
    output = np.zeros(n_in * n_out, dtype=np.uint8)
    state = 0
    for i, b in enumerate(bits_term):
        state = ((state << 1) | int(b)) & ((1 << K) - 1)
        for j, g in enumerate(generators):
            output[i * n_out + j] = bin(state & g).count('1') % 2
    return output


def _build_trellis(generators, K):
    """Precompute trellis tables for fully-vectorized Viterbi.

    The encoder uses a left-shift register:
        state_new = ((state << 1) | b) & ((1<<K)-1)
    so the decoder state s (K-1 bits) must use the same left-shift:
        ns = ((s << 1) | b) & (n_states - 1)
    Input bit b is the LSB of ns; the two predecessors of ns are
    (ns >> 1) and (ns >> 1) | (n_states // 2).
    """
    n_out = len(generators)
    n_states = 1 << (K - 1)

    # Forward tables
    output_table = np.zeros((n_states, 2, n_out), dtype=np.int8)
    next_state_table = np.zeros((n_states, 2), dtype=np.int32)
    for s in range(n_states):
        for b in range(2):
            # full K-bit encoder state when decoder state is s and input is b
            full_state = ((s << 1) | b) & ((1 << K) - 1)
            for j, g in enumerate(generators):
                output_table[s, b, j] = bin(full_state & g).count('1') % 2
            # left-shift transition (matches encoder convention)
            next_state_table[s, b] = ((s << 1) | b) & (n_states - 1)

    # Reverse lookup: for each ns, its two predecessors and the input bit.
    # ns = (s<<1|b) & (n_states-1)  →  b = ns & 1,  s bits[K-3:0] = ns bits[K-2:1]
    # s ∈ { ns>>1, (ns>>1)|(n_states//2) }  (top bit of s free)
    ns_all = np.arange(n_states, dtype=np.int32)
    half = n_states // 2
    prev_a = ns_all >> 1                     # top bit of predecessor = 0
    prev_b = (ns_all >> 1) | half            # top bit of predecessor = 1
    b_for_ns = ns_all & 1                    # input bit that produced ns

    return output_table, next_state_table, prev_a, prev_b, b_for_ns


_TRELLIS_CACHE: dict = {}


def viterbi_decode(llrs, generators, K, terminated=True):
    """Fully-vectorized soft-decision Viterbi decoder.
    llrs: soft LLRs (LLR > 0 favors bit=0).
    terminated=False: stream was cut mid-codeword (no zero tail) — keep every step.
    Returns decoded bits (trimmed of tail if terminated) as uint8 array.
    """
    n_out = len(generators)
    n_states = 1 << (K - 1)
    n_steps = len(llrs) // n_out

    key = (tuple(generators), K)
    if key not in _TRELLIS_CACHE:
        _TRELLIS_CACHE[key] = _build_trellis(generators, K)
    output_table, _, prev_a, prev_b, b_for_ns = _TRELLIS_CACHE[key]

    # All branch metrics upfront: branch[t, s, b] = Σ_j llr[t,j]*(1-2*out[s,b,j])
    output_signs = (1.0 - 2.0 * output_table.astype(np.float32))
    llrs_f = llrs[:n_steps * n_out].astype(np.float32).reshape(n_steps, n_out)
    branch_metrics = np.einsum('tj,sbj->tsb', llrs_f, output_signs)  # [n_steps, n_states, 2]

    metrics = np.full(n_states, -1e30, dtype=np.float32)
    metrics[0] = 0.0
    paths = np.empty((n_steps, n_states), dtype=np.int16)

    for t in range(n_steps):
        bm = branch_metrics[t]                    # [n_states, 2]
        # For each next-state ns: two candidates arrive from prev_a[ns] and prev_b[ns]
        # using input bit b_for_ns[ns].
        cand_a = metrics[prev_a] + bm[prev_a, b_for_ns]   # [n_states]
        cand_b = metrics[prev_b] + bm[prev_b, b_for_ns]   # [n_states]
        use_a = cand_a >= cand_b
        metrics = np.where(use_a, cand_a, cand_b)
        paths[t] = np.where(use_a, prev_a, prev_b)

    # Traceback: input bit b = LSB of next-state (left-shift convention)
    state = int(np.argmax(metrics))
    decoded = np.empty(n_steps, dtype=np.uint8)
    for t in range(n_steps - 1, -1, -1):
        prev = int(paths[t, state])
        decoded[t] = state & 1   # b = ns & 1 in left-shift trellis
        state = prev

    info_len = max(0, n_steps - (K - 1)) if terminated else n_steps
    return decoded[:info_len]


def block_interleave(bits, rows, cols):
    """Block interleaver: write by rows, read by columns."""
    bits = np.asarray(bits, dtype=np.uint8)
    n = rows * cols
    if len(bits) < n:
        bits = np.concatenate([bits, np.zeros(n - len(bits), dtype=np.uint8)])
    else:
        bits = bits[:n]
    mat = bits.reshape(rows, cols)
    return mat.T.ravel()


def block_deinterleave(bits, rows, cols):
    """Block deinterleaver: write by columns, read by rows."""
    bits = np.asarray(bits)
    n = rows * cols
    if len(bits) < n:
        pad = np.zeros(n - len(bits), dtype=bits.dtype)
        bits = np.concatenate([bits, pad])
    else:
        bits = bits[:n]
    mat = bits.reshape(cols, rows)
    return mat.T.ravel()


def block_deinterleave_soft(llrs, rows, cols):
    """Block deinterleaver for soft values."""
    return block_deinterleave(llrs, rows, cols)
