"""SPACE-CARRIER-EST-01 harness tests (eval/carrier_estimator.py) — additive, no engine calls.

The experiment's credibility rests on three structural properties, and these tests pin all three:
the grid is the pre-registered one; the candidate estimator is **the same object** as MECH-01 arm D's
(identity, not a copy, so it cannot have been quietly retuned); and the regression scorer is the
**corrected** null-set-aware one from SPACE-F4-MARGIN-01 rather than a fresh re-implementation.
"""
import os
import sys

import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, os.path.join(ROOT, 'server'))
sys.path.insert(0, os.path.join(ROOT, 'eval'))

import carrier_estimator as ce                     # noqa: E402
import f4_margin as f4m                            # noqa: E402
import space_doppler as sd                         # noqa: E402
import space_doppler_mech as mech                  # noqa: E402


def test_grid_is_the_pre_registered_one():
    js = ce.jobs()
    assert len(js) == 288                                   # 3 traj x 6 sev x 2 len x 2 esn0 x 4 reps
    assert len(js) * len(ce.ARMS) == 864
    assert len({i for i, _, _ in js}) == 288
    assert ce.SEED0 == 700000
    assert ce.REPS == 4
    assert ce.SEVERITY == (0.04, 0.1, 0.2, 0.4, 0.7, 1.0)
    assert ce.ESN0_DB == (12, 6)
    assert ce.LENGTH_SYMBOLS == {'short': 412, 'long': 1200}
    assert ce.ARMS == ('A_production', 'B_candidate', 'C_ideal')


def test_seed_namespace_is_disjoint_from_both_prior_experiments():
    assert ce.SEED0 == 700000 and mech.SEED0 == 600000 and sd.SEED0 == 500000
    ours = set(range(ce.SEED0, ce.SEED0 + len(ce.jobs())))
    assert not ours & set(range(mech.SEED0, mech.SEED0 + 144))
    assert not ours & set(range(sd.SEED0, sd.SEED0 + 192))
    assert ce.OUT != mech.OUT and mech.OUT != sd.OUT and ce.MANIFEST != mech.MANIFEST


def test_the_candidate_estimator_is_mech01_arm_d_by_identity():
    """Not 'an estimator with the same settings' — the same function object, so no knob can drift."""
    assert ce.mech.estimate_trajectory is mech.estimate_trajectory
    assert ce.KNOTS_EXPECTED == mech.D_BLOCKS == 8
    assert 'estimate_trajectory' not in ce.__dict__, 'the harness must not define its own estimator'
    # the generator is shared too, so the signal family is identical across the three experiments
    assert ce.mech._make is mech._make
    assert ce.LENGTHS is mech.LENGTHS and ce.SEVERITY is mech.SEVERITY


def test_regression_scoring_is_the_corrected_nullset_aware_scorer():
    assert ce.f4m._correct is f4m._correct
    # and it still distinguishes the null set's two sub-populations
    gt_null = {'class': 'noise'}
    gt_cat = {'class': 'k7', 'interleaver': [16, 24], 'original_bits': [0, 1, 1, 0] * 32}
    dec = {'status': 'DECODED', 'code': 'conv_k7_r12_171_133', 'modulation': 'BPSK',
           'interleaver': [16, 24], 'payload_bits': gt_cat['original_bits']}
    assert f4m._correct('nullset', gt_null, dec)[0] == 'FALSE_ACCEPT'
    assert f4m._correct('nullset', gt_cat, dec)[0] == 'TP'


def test_arm_A_is_a_pass_through():
    rng = np.random.RandomState(3)
    sig = rng.standard_normal(512) + 1j * rng.standard_normal(512)
    out, est = ce.apply_arm(sig, 'A_production')
    assert np.array_equal(out, sig)
    assert est == {'knots': None, 'rmse': None, 'estimator_degraded': None}


def test_arm_C_removes_exactly_the_injected_trajectory_and_needs_truth():
    gt = {'trajectory_class': 'pass', 'peak_shift_cyc_per_sample': 0.01, 'n_samples': 512}
    rng = np.random.RandomState(4)
    sig = rng.standard_normal(512) + 1j * rng.standard_normal(512)
    f = mech.true_trajectory(gt)
    out, est = ce.apply_arm(sd.apply_trajectory(sig, f), 'C_ideal', gt)
    assert np.allclose(out, sig, atol=1e-9)
    assert est['knots'] is None                              # the oracle is not an estimator
    try:
        ce.apply_arm(sig, 'C_ideal')                          # no ground truth -> must refuse
        raise AssertionError('arm C must not run without ground truth')
    except ValueError:
        pass


def test_arm_B_is_blind_and_reports_its_own_coverage():
    tone = np.exp(2j * np.pi * 0.004 * np.arange(4096))
    out, est = ce.apply_arm(tone, 'B_candidate')              # no gt passed: fully blind
    assert len(out) == len(tone)
    assert est['knots'] == ce.KNOTS_EXPECTED and est['estimator_degraded'] is False
    assert est['rmse'] is None                               # no truth available, so none invented
    # with ground truth present, RMSE is measured against it
    gt = {'trajectory_class': 'linear', 'peak_shift_cyc_per_sample': 0.004, 'n_samples': 4096}
    _, est2 = ce.apply_arm(sd.apply_trajectory(tone, mech.true_trajectory(gt)), 'B_candidate', gt)
    assert est2['rmse'] is not None and est2['rmse'] >= 0.0


def test_f4_and_family_extraction_use_the_repository_margin_convention():
    r = {'block_code': {'best_log10_p': -6.25, 'log10_threshold': -6.19, 'accepted': True,
                        'accepted_hypothesis': {'code': 'ccsds_tc_ldpc_128_64', 'family': 'ldpc',
                                                'n_codewords': 18,
                                                'converged_codewords': [False] * 18}},
         'accept': {'families': [
             {'name': 'F1_burst_code', 'tested_hypotheses': 420, 'log10_threshold': -4.92},
             {'name': 'F2_stream_code', 'tested_hypotheses': 176, 'log10_threshold': -5.25},
             {'name': 'F3_frame', 'tested_hypotheses': 12748780, 'log10_threshold': -9.8},
             {'name': 'F4_block_code', 'tested_hypotheses': 3072, 'log10_threshold': -6.19}]}}
    f4 = ce._f4(r)
    assert np.isclose(f4['f4_margin'], -6.25 - (-6.19))       # best - bar (eval/ladder.py:65)
    assert f4['f4_margin'] < 0 and f4['f4_accepted'] is True  # negative = cleared the bar
    assert f4['n_converged'] == 0 and f4['zero_convergence'] is True
    fam = ce._families(r)
    assert fam['M_F1'] == 420 and fam['M_F4'] == 3072        # the integration-cost metric
    assert fam['bar_F2'] == -5.25 and set(fam) == {
        'M_F1', 'M_F2', 'M_F3', 'M_F4', 'bar_F1', 'bar_F2', 'bar_F3', 'bar_F4'}


def test_no_f4_accepted_hypothesis_yields_no_invented_convergence():
    r = {'block_code': {'best_log10_p': -3.0, 'log10_threshold': -6.19, 'accepted': False},
         'accept': {'families': [{'name': 'F4_block_code', 'tested_hypotheses': 3072,
                                  'log10_threshold': -6.19}]}}
    f4 = ce._f4(r)
    assert f4['f4_margin'] > 0 and f4['f4_accepted'] is False
    assert f4['n_converged'] is None and f4['zero_convergence'] is None and f4['f4_code'] is None
