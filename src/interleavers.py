"""Burst interleaver catalogue v1 (Constitution v2.5 §12.1): block, diagonal, convolutional, QPP.

An interleaver hypothesis is described by a hashable spec tuple:
    ('block', rows, cols)   write row-wise into rows x cols, read column-wise (bench-v1 convention)
    ('diag', rows, cols)    write row-wise into rows x cols, read along wrapped diagonals
                            d = (col - row) mod cols for d = 0, 1, ..., rows top-down within a diagonal
    ('conv', B, D)          Forney convolutional interleaver: coded bit i travels on branch i mod B
                            with delay (i mod B)·D commutator cycles, so it appears at output position
                            i + (i mod B)·D·B; output positions no bit reaches are fill
    ('qpp', K, f1, f2)      3GPP TS 36.212 quadratic permutation polynomial: out[i] = coded[pi(i)],
                            pi(i) = (f1·i + f2·i²) mod K (references/lte_qpp_table.json)

`deinterleave_index(spec, n_obs)` returns idx with coded[t] = stream[idx[t]] for the coded bits a
hypothesis can explain in an observed stream of n_obs bits (every idx < n_obs).
"""

import json
import os
from functools import lru_cache

import numpy as np

from fec import block_deinterleave

REF = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'references', 'lte_qpp_table.json')
CONV_BRANCHES = (2, 3, 4, 6, 8, 12)
CONV_DELAYS = (1, 2, 3, 4, 6, 8)
# Block and diagonal domain (a receiver spec, max 384 bits); blind_id re-exports these.
INTERLEAVER_ROWS = (2, 16)
INTERLEAVER_COLS = (4, 24)
QPP_MAX_K = 384
MIN_CODED = 32                      # a hypothesis must explain at least this many coded bits
TYPES = ('block', 'diag', 'conv', 'qpp')


@lru_cache(maxsize=None)
def qpp_table():
    return tuple((e['K'], e['f1'], e['f2']) for e in json.load(open(REF)) if e['K'] <= QPP_MAX_K)


@lru_cache(maxsize=4096)
def _index(spec, n_obs):
    kind = spec[0]
    if kind == 'block':
        idx = block_deinterleave(np.arange(spec[1] * spec[2]), spec[1], spec[2])
    elif kind == 'diag':
        r, c = spec[1], spec[2]
        idx = np.empty(r * c, dtype=np.int64)
        k = 0
        for d in range(c):
            for i in range(r):
                idx[i * c + (i + d) % c] = k
                k += 1
    elif kind == 'conv':
        B, D = spec[1], spec[2]
        m = n_obs - (B - 1) * D * B
        i = np.arange(max(m, 0))
        idx = i + (i % B) * D * B
    elif kind == 'qpp':
        K, f1, f2 = spec[1], spec[2], spec[3]
        i = np.arange(K, dtype=np.int64)
        pi = (f1 * i + f2 * i * i) % K
        idx = np.empty(K, dtype=np.int64)
        idx[pi] = i
    else:
        raise ValueError(f'unknown interleaver type {kind!r}')
    idx = np.asarray(idx, dtype=np.int64)
    idx.setflags(write=False)
    return idx


def deinterleave_index(spec, n_obs=None):
    """coded[t] = stream[idx[t]]. n_obs is required for convolutional interleavers."""
    return _index(tuple(spec), int(n_obs) if spec[0] == 'conv' else 0)


def interleave(coded, spec, fill=0):
    """Transmit-side interleaving (used by the benchmark generator and tests)."""
    coded = np.asarray(coded)
    kind = spec[0]
    if kind in ('block', 'diag'):
        n = spec[1] * spec[2]
        c = np.zeros(n, dtype=coded.dtype)
        c[:min(n, len(coded))] = coded[:n]
        out = np.empty(n, dtype=coded.dtype)
        out[deinterleave_index(spec)] = c
        return out
    if kind == 'conv':
        B, D = spec[1], spec[2]
        n_out = len(coded) + (B - 1) * D * B
        out = np.full(n_out, fill, dtype=coded.dtype)
        i = np.arange(len(coded))
        out[i + (i % B) * D * B] = coded
        return out
    if kind == 'qpp':
        K = spec[1]
        if len(coded) != K:
            raise ValueError('QPP interleaver needs exactly K bits')
        out = np.empty(K, dtype=coded.dtype)
        out[np.arange(K)] = coded[(spec[2] * np.arange(K) + spec[3] * np.arange(K) ** 2) % K]
        return out
    raise ValueError(kind)


def candidates(n_obs, types=TYPES):
    """Catalogue v1 burst hypotheses for an observed stream of n_obs bits."""
    out = []
    grid = [(r, c) for r in range(INTERLEAVER_ROWS[0], INTERLEAVER_ROWS[1] + 1)
            for c in range(INTERLEAVER_COLS[0], INTERLEAVER_COLS[1] + 1) if 0.5 * n_obs <= r * c <= n_obs]
    if 'block' in types:
        out += [('block', r, c) for r, c in grid]
    if 'diag' in types:
        out += [('diag', r, c) for r, c in grid]
    if 'conv' in types:
        for B in CONV_BRANCHES:
            for D in CONV_DELAYS:
                m = n_obs - (B - 1) * D * B
                if m >= max(MIN_CODED, 0.5 * n_obs) and m <= 384:
                    out.append(('conv', B, D))
    if 'qpp' in types:
        out += [('qpp', K, f1, f2) for K, f1, f2 in qpp_table() if 0.5 * n_obs <= K <= n_obs]
    return out


def n_coded(spec, n_obs):
    return len(deinterleave_index(spec, n_obs))


def describe(spec):
    kind = spec[0]
    if kind == 'block':
        return {'type': 'block', 'rows': spec[1], 'cols': spec[2], 'bits': spec[1] * spec[2]}
    if kind == 'diag':
        return {'type': 'diagonal', 'rows': spec[1], 'cols': spec[2], 'bits': spec[1] * spec[2]}
    if kind == 'conv':
        return {'type': 'convolutional', 'branches': spec[1], 'delay_unit': spec[2]}
    return {'type': 'pseudo_random_qpp', 'K': spec[1], 'f1': spec[2], 'f2': spec[3],
            'source': '3GPP TS 36.212 Table 5.1.3-3'}
