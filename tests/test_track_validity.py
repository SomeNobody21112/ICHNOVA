"""SPACE-TRACK-VALIDITY-01 — regression tests for the published phase-tracking validity read-out.

`diagnostics.phase_tracking_validity` and `diagnostics.unwrap_margin_by_front_end` are write-only
evidence. These tests prove the three things that make that claim true: the numbers are exactly the
tracker's own unwrap arithmetic, nothing in the engine consults them, and a static carrier does not
acquire a spurious warning.
"""
import json
import os
import sys

import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, os.path.join(ROOT, 'eval'))

import pipeline                                        # noqa: E402
from modem import load_iq                              # noqa: E402

CRITERIA = json.load(open(os.path.join(ROOT, 'eval', 'track_validity_criteria.json'),
                          encoding='utf-8'))
DOPPLER = os.path.join(ROOT, 'data', 'space_bench', 'doppler')


def _stream(n=4096, drift=3e-4, seed=0):
    rng = np.random.RandomState(seed)
    bits = rng.choice([-1.0, 1.0], n)
    return bits * np.exp(1j * 2 * np.pi * np.cumsum(np.full(n, drift)))


def test_the_bound_is_the_unwrap_discriminant_not_a_chosen_threshold():
    t = {}
    pipeline._track_phase(_stream(), 'BPSK', _trace=t)
    assert t['unwrap_bound_rad'] == float(np.pi)
    assert 'not a chosen threshold' in CRITERIA[
        'the_condition_and_why_it_is_the_trackers_actual_assumption']['code']


def test_the_margin_is_exactly_the_trackers_own_arithmetic():
    """pi minus the largest wrapped block-to-block change of the angles the tracker computed."""
    t = {}
    pipeline._track_phase(_stream(), 'BPSK', _trace=t)
    ang = np.array(t['block_angles'])
    wrapped = (np.diff(ang) + np.pi) % (2 * np.pi) - np.pi
    assert np.isclose(t['max_wrapped_advance_rad'], np.max(np.abs(wrapped)))
    assert np.isclose(t['unwrap_margin_rad'], np.pi - np.max(np.abs(wrapped)))
    assert 0.0 <= t['unwrap_margin_rad'] <= np.pi


def test_a_slower_carrier_keeps_more_headroom():
    fast, slow = {}, {}
    pipeline._track_phase(_stream(drift=3e-4), 'BPSK', _trace=fast)
    pipeline._track_phase(_stream(drift=1e-6), 'BPSK', _trace=slow)
    assert slow['unwrap_margin_rad'] > fast['unwrap_margin_rad']


def test_indeterminate_is_reported_not_guessed():
    """No tracked front end -> None. That is the third state and it must not be faked as a number."""
    assert pipeline._tracking_validity([]) is None
    assert pipeline._tracking_validity([{'unwrap_margin_rad': None}]) is None
    v = pipeline._tracking_validity([{'unwrap_margin_rad': None}, {'unwrap_margin_rad': 0.5},
                                     {'unwrap_margin_rad': 2.0}])
    assert v['n_tracked_front_ends'] == 2                      # untracked front ends are excluded
    assert v['min_unwrap_margin_rad'] == 0.5 and v['max_unwrap_margin_rad'] == 2.0
    assert v['bound_rad'] == float(np.pi)


def test_the_diagnostic_is_never_consulted_by_any_decision(monkeypatch):
    """The safety claim: corrupt the read-out and the engine must decide exactly the same thing."""
    iq = load_iq(os.path.join(DOPPLER, 'linear_0098.iq'))
    good = pipeline.analyze_iq(iq)
    monkeypatch.setattr(pipeline, '_tracking_validity',
                        lambda fronts: {'bound_rad': -1.0, 'n_tracked_front_ends': -1,
                                        'min_unwrap_margin_rad': -99.0,
                                        'max_unwrap_margin_rad': -99.0})
    bad = pipeline.analyze_iq(iq)
    assert bad['status'] == good['status'] and bad['code'] == good['code']
    assert np.array_equal(bad['payload_bits'], good['payload_bits'])
    assert bad['accept']['n_hypotheses'] == good['accept']['n_hypotheses']
    assert bad['diagnostics']['n_front_ends'] == good['diagnostics']['n_front_ends']


def test_published_margins_align_with_the_front_end_index_the_engine_already_reports():
    """The claim's own validity is readable because the list shares the published front index."""
    r = pipeline.analyze_iq(load_iq(os.path.join(DOPPLER, 'linear_0098.iq')))
    by_fe = r['diagnostics']['unwrap_margin_by_front_end']
    assert len(by_fe) == r['diagnostics']['n_front_ends']
    ah = r['stream_code']['accepted_hypothesis']
    assert 0 <= ah['front'] < len(by_fe)
    v = r['diagnostics']['phase_tracking_validity']
    tracked = [m for m in by_fe if m is not None]
    assert v['n_tracked_front_ends'] == len(tracked) == r['diagnostics'][
        'phase_tracked_front_ends']
    assert np.isclose(v['min_unwrap_margin_rad'], min(tracked))


def test_a_static_control_does_not_acquire_a_spurious_warning():
    """A constant carrier must keep a large margin on the front end that produced its claim."""
    r = pipeline.analyze_iq(load_iq(os.path.join(DOPPLER, 'static_0049.iq')))
    v = r['diagnostics']['phase_tracking_validity']
    assert v is not None, 'this capture does have tracked front ends'
    assert v['max_unwrap_margin_rad'] > 1.0, 'a static carrier has ample unwrap headroom'
    # and the front end that produced its claim must itself be far from the ambiguity
    ah = (r.get('stream_code') or {}).get('accepted_hypothesis')
    if ah is not None:
        m = r['diagnostics']['unwrap_margin_by_front_end'][ah['front']]
        if m is not None:
            assert m > 1.0, 'no spurious warning on a constant carrier'


def test_the_diagnostic_is_deterministic():
    iq = load_iq(os.path.join(DOPPLER, 'linear_0098.iq'))
    a = pipeline.analyze_iq(iq)['diagnostics']
    b = pipeline.analyze_iq(iq)['diagnostics']
    assert a['phase_tracking_validity'] == b['phase_tracking_validity']
    assert a['unwrap_margin_by_front_end'] == b['unwrap_margin_by_front_end']
