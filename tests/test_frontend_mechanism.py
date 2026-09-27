"""SPACE-FRONTEND-MECH-01 harness tests (eval/frontend_mechanism.py) — additive, no engine calls.

The mechanism claim rests on the eval-side replication branching on exactly what production branches
on. These tests pin that: the constants come from `pipeline` (not copies), and the gate arithmetic
rejects a serially dependent stream while admitting an independent one — which is the whole reason a
noise-like front end is admitted.
"""
import os
import sys

import numpy as np
from scipy.special import bdtrc

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, os.path.join(ROOT, 'eval'))

import frontend_mechanism as fm                    # noqa: E402
import pipeline                                    # noqa: E402


def _gate(signs):
    """The production rule, spelled out: reject when agreement is significantly above the spec."""
    same = int(np.count_nonzero((signs[1:] < 0) == (signs[:-1] < 0)))
    tail = (float(np.log10(max(bdtrc(same - 1, len(signs) - 1, fm.SERIAL_AGREEMENT_MAX), 1e-300)))
            if same > 0 else 0.0)
    return same / (len(signs) - 1), tail, bool(tail > np.log10(fm.ALPHA))


def test_constants_are_the_production_ones_not_copies():
    assert fm.SERIAL_AGREEMENT_MAX == pipeline.SERIAL_AGREEMENT_MAX == 0.60
    assert fm.ALPHA == pipeline.ALPHA and fm.RX_BETA == pipeline.RX_BETA
    assert fm.MODULATIONS is pipeline.MODULATIONS and fm.SPS_RANGE is pipeline.SPS_RANGE


def test_an_oversampled_stream_is_rejected():
    """4x oversampling agrees on ~75% of pairs — the case the 0.60 spec exists for."""
    rng = np.random.RandomState(1)
    rep = np.repeat(rng.choice([-1.0, 1.0], 500), 4)
    agreement, _, passed = _gate(rep)
    assert agreement > 0.70 and not passed


def test_a_noise_like_stream_is_admitted():
    """The finding: serial independence is necessary for the syndrome null, not sufficient for
    the front end to be meaningful. Pure noise agrees ~50% and therefore passes the gate."""
    rng = np.random.RandomState(2)
    noise = rng.standard_normal(3000)
    agreement, _, passed = _gate(noise)
    assert 0.45 < agreement < 0.55 and passed


def test_a_coherent_carrier_stream_is_rejected():
    """The uncorrected idle carrier: a slowly rotating phasor gives long runs of one sign."""
    k = np.arange(3000)
    coherent = np.cos(2 * np.pi * 0.002 * k)          # ~250-sample half-periods -> long runs
    agreement, _, passed = _gate(coherent)
    assert agreement > 0.60 and not passed


def test_the_harness_declares_the_captures_it_reads():
    assert set(fm.CAPTURES) == {'idle_carrier_0411', 'k3_120_008', 'static_0000'}
    assert fm.CAPTURES['idle_carrier_0411'][0].endswith(
        os.path.join('bench2', 'sealed', 'idle_carrier_0411.iq'))
    assert [c[0] for c in fm.PRIMARY_CONDITIONS][:3] == ['A_original', 'B_zero', 'C_estimator']
