"""Core regression tests. Run: python tests/test_core.py  (or pytest tests/)"""

import inspect
import itertools
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from fec import conv_encode, viterbi_decode, block_interleave            # noqa: E402
from modem import modulate, pulse_shape, rrc_filter, channel             # noqa: E402
from blind_id import (CODE_CATALOGUE, decode_hypothesis, syndrome_checks,  # noqa: E402
                      deinterleave_index, sign_test_log10p)
import pipeline                                                           # noqa: E402
from pipeline import analyze_iq, _cfo_candidates                          # noqa: E402

K7 = CODE_CATALOGUE[0]


# ---------------- Viterbi: independent reference ----------------

def reference_encode(u, generators, K, terminate):
    """Textbook encoder, independent of fec.conv_encode's state machine:
    c_j(t) = Σ_i g_j[i]·u(t−i) mod 2, where g_j[i] is bit i of the octal constant
    (i = 0 is the current input — the convention documented in blind_id.py)."""
    u = np.concatenate([u, np.zeros(K - 1, dtype=int)]) if terminate else np.asarray(u)
    streams = [np.convolve(u, [(g >> i) & 1 for i in range(K)])[:len(u)] % 2 for g in generators]
    return np.column_stack(streams).ravel().astype(np.uint8)


def ml_bruteforce(llrs, generators, K, k, terminate):
    """Exhaustive maximum-likelihood decision over all 2^k inputs (correlation metric)."""
    best, best_u = -np.inf, None
    for bits in itertools.product((0, 1), repeat=k):
        u = np.array(bits)
        c = reference_encode(u, generators, K, terminate)[:len(llrs)]
        m = np.dot(llrs, 1 - 2.0 * c)
        if m > best:
            best, best_u = m, u
    return best_u


def test_encoder_matches_reference_convention():
    rng = np.random.RandomState(0)
    for code in CODE_CATALOGUE:
        for _ in range(20):
            u = rng.randint(0, 2, 50)
            assert np.array_equal(conv_encode(u, code['generators'], code['K']),
                                  reference_encode(u, code['generators'], code['K'], True))
    # impulse response documents the bit order: output j at delay i is bit i of g_j (LSB first)
    imp = conv_encode([1], [0o171, 0o133], 7)
    assert list(imp[0::2]) == [1, 0, 0, 1, 1, 1, 1]      # 0o171 = 0b1111001, read LSB first
    assert list(imp[1::2]) == [1, 1, 0, 1, 1, 0, 1]      # 0o133 = 0b1011011, read LSB first


def test_viterbi_equals_bruteforce_ml():
    rng = np.random.RandomState(1)
    k = 9
    for code in CODE_CATALOGUE:
        g, K = code['generators'], code['K']
        for terminate in (True, False):
            for _ in range(25):
                u = rng.randint(0, 2, k)
                c = reference_encode(u, g, K, terminate)
                llrs = 2.0 * (1 - 2.0 * c) + rng.standard_normal(len(c)) * 1.5   # noisy
                ml = ml_bruteforce(llrs, g, K, k, terminate)
                vit = viterbi_decode(llrs, g, K, terminated=terminate)
                assert np.array_equal(vit, ml), (code['name'], terminate)


def test_truncated_codeword_decodes_fully():
    for rows, cols in [(6, 10), (10, 12)]:
        info = np.random.RandomState(7).randint(0, 2, 400).astype(np.uint8)
        llrs = 1.0 - 2.0 * block_interleave(conv_encode(info, K7['generators'], 7), rows, cols)
        d = decode_hypothesis(llrs, K7, (rows, cols))
        assert d['consistency'] == 1.0
        assert np.array_equal(d['decoded_bits'], info[:rows * cols // 2])


# ---------------- syndrome test ----------------

def test_syndrome_checks_true_vs_wrong_interleaver():
    rng = np.random.RandomState(2)
    for code in CODE_CATALOGUE:
        info = rng.randint(0, 2, 200).astype(np.uint8)
        stream = block_interleave(conv_encode(info, code['generators'], code['K']), 8, 15)
        th = 1.0 - 2.0 * stream                      # noiseless: tanh(±∞/2) = ±1
        chk = syndrome_checks(th[deinterleave_index(8, 15)], code)
        assert np.all(chk > 0)
        wrong = syndrome_checks(th[:112][deinterleave_index(7, 16)], code)
        assert float(sign_test_log10p(int((wrong > 0).sum()), len(wrong))) > -3


def test_sign_test_null_is_calibrated():
    rng = np.random.RandomState(3)
    hits = 0
    for _ in range(2000):
        th = np.tanh(rng.standard_normal(120))
        chk = syndrome_checks(th, K7)
        hits += float(sign_test_log10p(int((chk > 0).sum()), len(chk))) <= np.log10(0.05)
    assert hits / 2000 <= 0.05 + 0.015       # exact binomial test is conservative


# ---------------- front-end ----------------

def test_cfo_candidates_find_tone():
    cfo = -0.00576
    n = np.arange(420)
    qpsk = np.exp(1j * (np.pi / 4 + np.pi / 2 * np.random.RandomState(3).randint(0, 4, 420)))
    cands, detection = _cfo_candidates(qpsk * np.exp(2j * np.pi * cfo * n))
    assert abs(cands[0]['cfo'] - cfo) < 1e-4
    assert detection < -10


def _coded_signal(sps, mod, seed, esn0_db=12.0, bits=120, dims=(8, 15)):
    rng = np.random.RandomState(seed)
    info = rng.randint(0, 2, bits).astype(np.uint8)
    syms = modulate(block_interleave(conv_encode(info, K7['generators'], 7), *dims), mod)
    sig = pulse_shape(syms, sps, rrc_filter(0.35, sps))
    snr = esn0_db - 10 * np.log10(len(sig) / len(syms))
    iq, _ = channel(sig, snr, rng.uniform(-0.008, 0.008), 0.0, rng.uniform(0, 2 * np.pi), rng)
    return iq, info[:dims[0] * dims[1] // 2]


def test_sps_domain_and_aliases():
    """True sps 4, 6, 8, 10, 12 (multiples of each other) must decode at the true sps."""
    for sps, mod in [(4, 'BPSK'), (6, 'QPSK'), (8, 'BPSK'), (10, 'QPSK'), (12, 'BPSK')]:
        iq, payload = _coded_signal(sps, mod, seed=sps)
        r = analyze_iq(iq)
        assert r['status'] == 'DECODED', (sps, mod, r['accept'])
        assert r['sps'] == sps and r['modulation'] == mod, (sps, r['sps'], r['modulation'])
        d = np.asarray(r['payload_bits'])[:len(payload)]
        assert min(np.mean(d != payload), np.mean((1 - d) != payload)) == 0.0


def test_noise_and_uncoded_are_not_decoded():
    rng = np.random.RandomState(4)
    for n in (280, 600):
        x = (rng.standard_normal(n) + 1j * rng.standard_normal(n)) / np.sqrt(2)
        assert analyze_iq(x)['status'] == 'UNKNOWN'
    bits = rng.randint(0, 2, 200).astype(np.uint8)
    sig = pulse_shape(modulate(bits, 'BPSK'), 5, rrc_filter(0.3, 5))
    iq, _ = channel(sig, 5.0, 0.004, 0.0, 1.0, rng)
    assert analyze_iq(iq)['status'] == 'SIGNAL_NO_CODE'


def test_no_dataset_constants_in_inference():
    src = inspect.getsource(pipeline)
    for leaked in ('force_include', '[4, 6, 8]', '_mod_sps', '0.25, 0.5, 0.35', 'CODED_BONUS'):
        assert leaked not in src, leaked
    assert '_oracle' not in inspect.signature(pipeline.analyze_file).parameters


if __name__ == '__main__':
    tests = [v for k, v in dict(globals()).items() if k.startswith('test_')]
    for t in tests:
        t()
        print('PASS', t.__name__)
    print(f'{len(tests)}/{len(tests)} passed')
