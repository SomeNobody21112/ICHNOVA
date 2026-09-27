"""SPACE-CARRIER-EST-DIAG-01 harness tests (eval/carrier_est_diag.py) — additive, no engine calls.

The diagnostic's whole logic is the correction grid, so these tests pin it: each shape is what the
criteria file says it is, the zero correction through the real correction function is an exact
identity (the control that separates "the machinery perturbs it" from "the magnitude matters"), and
`varying_only` really carries no constant term while `constant` really carries no variation.
"""
import os
import sys

import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, os.path.join(ROOT, 'eval'))

import carrier_est_diag as diag                    # noqa: E402
import space_doppler_mech as mech                  # noqa: E402

N = 2048
SCALE = 5.838611e-03                               # M_est from the criteria file
F_HAT = SCALE + 8e-6 * np.sin(np.linspace(0, 7, N))


def test_the_grid_is_the_pre_registered_one():
    assert diag.SHAPES == ('constant', 'linear_mean', 'pass_mean', 'estimator_scaled',
                           'varying_only')
    assert diag.MULTIPLIERS == (0.01, 0.03, 0.1, 0.3, 0.5, 1.0, 2.0)
    assert diag.PRIMARY.endswith(os.path.join('bench2', 'sealed', 'idle_carrier_0411.iq'))


def test_zero_correction_through_the_real_path_is_an_exact_identity():
    """The control that makes the experiment interpretable: the machinery must be transparent."""
    rng = np.random.RandomState(7)
    iq = rng.standard_normal(N) + 1j * rng.standard_normal(N)
    assert np.array_equal(mech._derotate(iq, np.zeros(N)), iq)
    assert np.array_equal(mech._derotate(iq, diag.correction('constant', 0.0, N, F_HAT, SCALE)), iq)


def test_constant_shape_has_no_time_variation_and_the_declared_mean():
    for m in diag.MULTIPLIERS:
        f = diag.correction('constant', m, N, F_HAT, SCALE)
        assert np.ptp(f) == 0.0
        assert np.isclose(np.mean(f), m * SCALE)


def test_varying_only_has_no_constant_term_but_does_vary():
    for m in diag.MULTIPLIERS:
        f = diag.correction('varying_only', m, N, F_HAT, SCALE)
        assert abs(np.mean(f)) < 1e-15                      # no constant term at all
        assert np.ptp(f) > 0
    # its magnitude scales linearly with m
    a = np.ptp(diag.correction('varying_only', 0.1, N, F_HAT, SCALE))
    b = np.ptp(diag.correction('varying_only', 1.0, N, F_HAT, SCALE))
    assert np.isclose(b / a, 10.0, rtol=1e-6)


def test_time_varying_shapes_carry_the_declared_mean():
    for shape in ('linear_mean', 'pass_mean'):
        for m in (0.1, 1.0):
            f = diag.correction(shape, m, N, F_HAT, SCALE)
            assert np.isclose(np.mean(f), m * SCALE, rtol=2e-2), (shape, m)
            assert np.ptp(f) > 0


def test_estimator_scaled_at_one_is_the_estimator_itself():
    assert np.array_equal(diag.correction('estimator_scaled', 1.0, N, F_HAT, SCALE), F_HAT)
    half = diag.correction('estimator_scaled', 0.5, N, F_HAT, SCALE)
    assert np.isclose(np.mean(half), 0.5 * np.mean(F_HAT))


def test_unknown_shape_is_refused_rather_than_guessed():
    try:
        diag.correction('something_else', 1.0, N, F_HAT, SCALE)
        raise AssertionError('an unknown shape must raise')
    except ValueError:
        pass
