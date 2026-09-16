"""Regression checks for the two bugs fixed in session 2. Run: python tests/test_core.py"""

import os
import sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from fec import conv_encode, viterbi_decode, block_interleave
from blind_id import try_decode, CODE_CATALOGUE
from pipeline import _cfo_candidates

K7 = CODE_CATALOGUE[0]


def _truncated_codeword(seed, rows, cols):
    """Same shape as generate.py: 400 info bits, interleaver keeps only rows*cols coded bits."""
    info = np.random.RandomState(seed).randint(0, 2, 400).astype(np.uint8)
    coded = conv_encode(info, K7['generators'], K7['K'])
    llrs = 1.0 - 2.0 * block_interleave(coded, rows, cols)   # noiseless, LLR>0 -> bit 0
    return info, llrs


def test_viterbi_terminated_roundtrip():
    info = np.random.RandomState(1).randint(0, 2, 100).astype(np.uint8)
    llrs = 1.0 - 2.0 * conv_encode(info, K7['generators'], K7['K'])
    assert np.array_equal(viterbi_decode(llrs, K7['generators'], K7['K']), info)


def test_truncated_codeword_decodes_fully():
    # Regression: tail trimming capped consistency at ~0.9 and lost the last 6 bits.
    for rows, cols in [(6, 10), (10, 12)]:
        info, llrs = _truncated_codeword(7, rows, cols)
        decoded, cons = try_decode(llrs, K7, (rows, cols))
        n = rows * cols // 2
        assert cons == 1.0, cons
        assert np.array_equal(decoded[:n], info[:n])


def test_wrong_interleaver_scores_below_accept():
    info, llrs = _truncated_codeword(7, 6, 10)
    _, cons = try_decode(llrs, K7, (4, 15))
    assert cons < 0.98, cons


def test_cfo_candidates_find_tone():
    cfo = -0.00576
    n = np.arange(420)
    qpsk = np.exp(1j * (np.pi / 4 + np.pi / 2 * np.random.RandomState(3).randint(0, 4, 420)))
    iq = qpsk * np.exp(2j * np.pi * cfo * n)
    assert abs(_cfo_candidates(iq, top_k=3)[0] - cfo) < 1e-4


if __name__ == '__main__':
    tests = [v for k, v in dict(globals()).items() if k.startswith('test_')]
    for t in tests:
        t()
        print('PASS', t.__name__)
    print(f'{len(tests)}/{len(tests)} passed')
