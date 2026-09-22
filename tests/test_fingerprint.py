"""Phase 2 fingerprints: deterministic, finite, read-only on the engine result, leak-free scaling."""

import copy
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'src'))

from blind_id import CODE_CATALOGUE  # noqa: E402
from fec import block_interleave, conv_encode  # noqa: E402
from fingerprint import FEATURES, Library, fingerprint  # noqa: E402
from modem import channel, modulate, pulse_shape, rrc_filter  # noqa: E402
from pipeline import analyze_iq  # noqa: E402

K7 = next(c for c in CODE_CATALOGUE if c['K'] == 7)


def _result(seed=3):
    """A K=7 coded QPSK capture synthesised here (data/ is not in the repository), as in test_core."""
    rng = np.random.RandomState(seed)
    info = rng.randint(0, 2, 120).astype(np.uint8)
    syms = modulate(block_interleave(conv_encode(info, K7['generators'], 7), 8, 15), 'QPSK')
    sig = pulse_shape(syms, 8, rrc_filter(0.35, 8))
    iq, _ = channel(sig, 12.0 - 10 * np.log10(len(sig) / len(syms)), 0.004, 0.0, 1.0, rng)
    return analyze_iq(iq, _all_hypotheses=True)


def test_fingerprint_is_finite_deterministic_and_never_touches_the_result():
    r = _result()
    before = copy.deepcopy(r)
    a, b = fingerprint(r), fingerprint(r)
    assert a.shape == (len(FEATURES),) and np.all(np.isfinite(a))
    assert np.array_equal(a, b)
    # The fingerprint is read off a finished result: the verdict and evidence are unchanged by it.
    assert r['status'] == before['status'] and r['accept'] == before['accept']
    assert r['diagnostics']['top_hypotheses'] == before['diagnostics']['top_hypotheses']


def test_verdict_features_match_the_engine_verdict():
    r = _result()
    fp = dict(zip(FEATURES, fingerprint(r)))
    onehot = {'DECODED': 'v_decoded', 'SIGNAL_NO_CODE': 'v_signal_no_code', 'UNKNOWN': 'v_unknown'}
    assert fp[onehot[r['status']]] == 1.0
    assert sum(fp[v] for v in onehot.values()) == 1.0


def test_library_scaling_comes_from_the_reference_only():
    rng = np.random.default_rng(0)
    ref = rng.normal(size=(50, len(FEATURES)))
    lib = Library().fit(ref)
    mean, std = lib.mean.copy(), lib.std.copy()
    lib.query(rng.normal(loc=100.0, size=len(FEATURES)), k=3)   # a far-away query changes nothing
    assert np.array_equal(mean, lib.mean) and np.array_equal(std, lib.std)
    # Each reference fingerprint is its own nearest neighbour at distance 0.
    i, d = lib.query(ref[17], k=1)[0]
    assert i == 17 and d == 0.0
    # Exclusion removes it, so leave-one-out queries are possible.
    assert lib.query(ref[17], k=1, exclude=[17])[0][0] != 17
