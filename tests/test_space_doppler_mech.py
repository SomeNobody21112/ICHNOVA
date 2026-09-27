"""SPACE-DOPPLER-MECH-01 harness tests (eval/space_doppler_mech.py) — additive.

They guard what the diagnostic's conclusions depend on: the ideal correction really removes the
injected carrier, the arm-A ablation really removes the tracked front end (and puts it back), the
blind estimator really follows a moving carrier without ground truth, the granularity quantiser is
piecewise-constant where it claims to be, and the four scoring categories are distinguished — a wrong
payload beneath a true structure must never be scored as a structural false accept.
"""
import os
import sys

import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, os.path.join(ROOT, 'eval'))

import pipeline                                    # noqa: E402
import space_doppler as sd                         # noqa: E402
import space_doppler_mech as m                     # noqa: E402
from pipeline import CFO_MAX                       # noqa: E402

LONG = {'severity': 1.0, 'length': 'long', 'esn0': 12, 'rep': 0}


def _capture(cls, params, seed=m.SEED0):
    return m._make(cls, params, np.random.RandomState(seed))


def test_the_grid_is_the_pre_registered_one():
    js = m.jobs()
    assert len(js) == 144                                   # 3 x 6 x 2 x 2 x 2
    assert len(js) * len(m.ARMS) == 576                     # the pre-registered analysis count
    assert len(m._e_jobs()) == 30                           # 5 granularities x 3 severities x 2 reps
    assert m.SEVERITY == (0.04, 0.1, 0.2, 0.4, 0.7, 1.0) and m.ESN0_DB == (12, 6)
    assert m.SEED0 == 600000 and m.SEED0 != sd.SEED0        # its own seed namespace


def test_declared_lengths_give_the_pre_registered_symbol_counts():
    for length, n_sym in m.LENGTH_SYMBOLS.items():
        _, gt = _capture('linear', {**LONG, 'length': length})
        assert gt['n_symbols'] == n_sym, (length, gt['n_symbols'])


def test_generation_is_seed_pure_and_static_matches_the_treated_peak():
    a, gta = _capture('pass', LONG)
    b, gtb = _capture('pass', LONG)
    assert np.array_equal(a, b) and gta == gtb
    _, gt_static = _capture('static', LONG)
    # DEV-3: the static control carries the same peak offset with zero drift
    assert gt_static['peak_shift_cyc_per_sample'] == gta['peak_shift_cyc_per_sample']
    assert gt_static['max_drift_rate_cyc_per_sample2'] == 0.0
    assert gta['max_drift_rate_cyc_per_sample2'] > 0.0


def test_every_cell_stays_inside_the_engines_declared_search_bound():
    """DEV-2: the severity ladder exists so that out-of-bound refusal is not a confound."""
    for cls in m.TRAJECTORIES:
        for sev in m.SEVERITY:
            _, gt = _capture(cls, {**LONG, 'severity': sev})
            assert gt['peak_shift_cyc_per_sample'] <= CFO_MAX
            assert not gt['outside_search_bound']


def test_ideal_correction_removes_exactly_what_the_generator_injected():
    _, gt = _capture('pass', LONG)
    f = m.true_trajectory(gt)
    assert len(f) == gt['n_samples']
    rng = np.random.RandomState(1)
    sig = rng.standard_normal(len(f)) + 1j * rng.standard_normal(len(f))
    assert np.allclose(m._derotate(sd.apply_trajectory(sig, f), f), sig, atol=1e-9)


def test_arm_A_ablates_the_tracked_front_end_and_restores_the_function():
    """The ablation must bite (no tracked front end) and must not leak out of the call."""
    iq, _ = _capture('linear', LONG)
    original = pipeline._track_phase
    r_b = m._analyse(iq, 'B_existing')
    r_a = m._analyse(iq, 'A_no_tracking')
    assert pipeline._track_phase is original, 'the ablation leaked'
    assert r_b['diagnostics']['phase_tracked_front_ends'] > 0, 'baseline should track a long capture'
    assert r_a['diagnostics']['phase_tracked_front_ends'] == 0, 'arm A should have no tracked front end'


def test_the_blind_estimator_follows_a_moving_carrier_without_ground_truth():
    iq, gt = _capture('linear', LONG)
    f_true = m.true_trajectory(gt)
    f_hat, knots = m.estimate_trajectory(iq)
    assert knots == m.D_BLOCKS and len(f_hat) == len(iq)
    # it is an estimate, not an oracle: require correlation with the truth, not equality
    assert np.corrcoef(f_hat, f_true[:len(f_hat)])[0, 1] > 0.9
    # and it is blind — on a static capture the same call returns a flatter estimate
    iq_s, _ = _capture('static', LONG)
    f_s, _ = m.estimate_trajectory(iq_s)
    assert np.ptp(f_s) < np.ptp(f_hat)


def test_granularity_quantiser_is_piecewise_constant_where_it_claims():
    _, gt = _capture('pass', LONG)
    f = m.true_trajectory(gt)
    sps = gt['sps']
    fc64 = m.quantise_trajectory(f, sps, 'const_64')
    fc8 = m.quantise_trajectory(f, sps, 'const_8')
    fl64 = m.quantise_trajectory(f, sps, 'linear_64')
    assert len(fc64) == len(fc8) == len(fl64) == len(f)
    # a coarser block holds fewer distinct values; linear interpolation holds more than constant
    assert len(np.unique(fc64)) < len(np.unique(fc8)) < len(np.unique(fl64))
    # each const block really is one value
    assert len(np.unique(fc64[:64 * sps])) == 1
    # and the finer the granularity, the closer to the truth
    assert np.max(np.abs(fc8 - f)) < np.max(np.abs(fc64 - f))


def test_scoring_never_calls_a_wrong_payload_a_structural_false_accept():
    gt = {'modulation': 'BPSK', 'payload_bits': [0, 1, 1, 0] * 64}
    good = {'status': 'DECODED', 'code': 'conv_k7_r12_171_133_continuous', 'modulation': 'BPSK',
            'payload_bits': gt['payload_bits']}
    assert m.score(gt, good)[0] == 'CORRECT_STRUCTURE_CORRECT_PAYLOAD'
    wrong_payload = m.score(gt, {**good, 'payload_bits': [1, 0, 0, 0] * 64})[0]
    assert wrong_payload == 'CORRECT_STRUCTURE_WRONG_PAYLOAD'
    assert wrong_payload != 'WRONG_STRUCTURE'
    assert m.score(gt, {**good, 'code': 'rs_255_223'})[0] == 'WRONG_STRUCTURE'
    assert m.score(gt, {**good, 'modulation': 'QPSK'})[0] == 'WRONG_STRUCTURE'
    for status in ('SIGNAL_NO_CODE', 'UNKNOWN'):
        assert m.score(gt, {**good, 'status': status})[0] == 'REFUSED'


def test_the_sealed_predecessor_is_a_different_namespace():
    assert m.OUT != sd.OUT and m.ROWS != sd.ROWS and m.MANIFEST != sd.MANIFEST
    assert os.path.basename(m.CRITERIA) == 'space_doppler_mech_criteria.json'
