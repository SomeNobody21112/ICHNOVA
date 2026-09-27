"""SPACE-TRACK-READOUT-01 — regression tests for the one production instrumentation change.

`src/pipeline.py::_track_phase` gained an optional write-only `_trace` dict. These tests exist to
prove that the change is observational only: the returned stream is identical with and without it,
the read-out is faithful to what the function actually applied, the trace is deterministic, and the
engine's verdicts on sealed captures are unchanged.
"""
import json
import os
import sys

import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, os.path.join(ROOT, 'eval'))

import pipeline                                        # noqa: E402
import track_readout as tr                             # noqa: E402
from modem import load_iq                              # noqa: E402


def _stream(n=4096, drift=2e-4, seed=0):
    """A BPSK symbol stream with a drifting carrier — the case the tracker exists for."""
    rng = np.random.RandomState(seed)
    bits = rng.choice([-1.0, 1.0], n)
    phase = 2 * np.pi * np.cumsum(np.full(n, drift))
    return bits * np.exp(1j * phase) + 0.05 * (rng.standard_normal(n) + 1j * rng.standard_normal(n))


def test_the_trace_does_not_change_what_the_tracker_returns():
    """The whole safety argument: passing a trace must not alter the output by even one sample."""
    y = _stream()
    without = pipeline._track_phase(y, 'BPSK')
    trace = {}
    with_trace = pipeline._track_phase(y, 'BPSK', _trace=trace)
    assert without is not None and np.array_equal(without, with_trace)
    assert trace, 'the trace should have been filled'


def test_the_trace_is_a_faithful_readout_not_a_recomputation():
    """The reported phase must be exactly what the function applied to the stream."""
    y = _stream()
    trace = {}
    out = pipeline._track_phase(y, 'BPSK', _trace=trace)
    phi = np.array(trace['phase'])
    per_symbol = np.repeat(phi, trace['block'])
    if len(per_symbol) < len(y):
        per_symbol = np.concatenate([per_symbol, np.full(len(y) - len(per_symbol), phi[-1])])
    assert np.allclose(out, y * np.exp(-1j * per_symbol[:len(y)]))
    # the pre-unwrap angles are what make a slip visible, so they must be present and consistent
    ang = np.array(trace['block_angles'])
    assert len(ang) == len(phi) == trace['n_blocks']
    assert np.allclose(np.unwrap(ang) / trace['m_power'], phi)


def test_the_trace_is_deterministic():
    y = _stream()
    a, b = {}, {}
    pipeline._track_phase(y, 'BPSK', _trace=a)
    pipeline._track_phase(y, 'BPSK', _trace=b)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_the_tracker_still_declines_short_captures_and_keeps_its_signature():
    """Positional calls must keep working: the engine calls _track_phase(y, mod) with two args."""
    short = _stream(n=pipeline.TRACK_MIN_SYMBOLS - 1)
    assert pipeline._track_phase(short, 'BPSK') is None
    trace = {}
    assert pipeline._track_phase(short, 'BPSK', _trace=trace) is None
    assert trace == {}, 'nothing is reported when the tracker declines to run'


def test_verdicts_on_a_sealed_capture_are_unchanged():
    """The engine never passes a trace; its published verdict must match the sealed record."""
    rows = {json.loads(l)['file']: json.loads(l)
            for l in open(os.path.join(ROOT, 'results', 'space_doppler_rows.jsonl'),
                          encoding='utf-8')}
    name = 'linear_0098'
    r = pipeline.analyze_iq(load_iq(os.path.join(ROOT, 'data', 'space_bench', 'doppler',
                                                 name + '.iq')))
    assert r['status'] == rows[name]['status'] == 'DECODED'
    assert r['code'] == rows[name]['est_code']


def test_the_slip_rule_is_the_committed_one():
    """A slip is an increment off by a non-zero multiple of 2*pi/M, within a quarter of a step."""
    assert tr.SLIP_TOL == 0.25
    true = np.array([0.0, 0.5, 1.0, 1.5])
    assert not tr._slips(true + 0.02, true, 2)[0].any()          # small error is not a slip
    slipped = true + np.array([0.0, 0.0, np.pi, np.pi])          # 2*pi/2 step that persists
    is_slip, k = tr._slips(slipped, true, 2)
    assert is_slip.sum() == 1 and int(k[is_slip][0]) == 1
    # the truth-side predictor: unwrap must slip once the M-power advance exceeds pi
    assert tr._predicted_slip(np.array([0.0, np.pi / 2 + 0.01]), 2)[0]
    assert not tr._predicted_slip(np.array([0.0, np.pi / 2 - 0.01]), 2)[0]
