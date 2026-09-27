"""SPACE-FRONTEND-SENSITIVITY-01 harness tests (eval/frontend_sensitivity.py) — additive, no engine calls.

Two things must hold for this experiment's conclusions to mean anything: it reads **only** fields the
engine already publishes (no invented metric, no unexposed internal), and it reuses the previous
diagnostic's grid by import rather than by copy, so "no new correction magnitude" is structural.
"""
import os
import sys

import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, os.path.join(ROOT, 'eval'))

import carrier_est_diag as diag                    # noqa: E402
import frontend_sensitivity as fs                  # noqa: E402


def _result(**over):
    """A synthetic engine result carrying only the published fields the harness reads."""
    d = {'cfo_candidates': [{'cfo': 0.0058, 'order': 2, 'peak_to_floor_db': 31.2, 'log10_p': -141.5},
                            {'cfo': 0.0011, 'order': 4, 'peak_to_floor_db': 9.1, 'log10_p': -3.2}],
         'detection_log10_p': -141.5,
         'sps_table': [{'sps': 20, 'q2': 0.41, 'q4': 0.22, 'n_symbols': 1204},
                       {'sps': 10, 'q2': 0.33, 'q4': 0.11, 'n_symbols': 2408}],
         'sps_candidates': [20, 10, 5], 'raw_sps_estimate': 19.6,
         'modulation_gates': {'8PSK': {'searched': False}, '16QAM': {'searched': False}},
         'modulation_stats': [{'decision': 'BPSK'}, {'decision': 'BPSK'}],
         'n_front_ends': 18, 'phase_tracked_front_ends': 0,
         'front_ends_rejected_serial_dependence': 378, 'runner_up_margin_log10': 0.4}
    d.update(over.pop('diagnostics', {}))
    r = {'status': 'DECODED', 'code': 'ccsds_tc_ldpc_128_64', 'modulation': 'QPSK',
         'accept': {'n_hypotheses': 2048, 'families': [
             {'name': 'F1_burst_code', 'tested_hypotheses': 210, 'log10_threshold': -4.6},
             {'name': 'F4_block_code', 'tested_hypotheses': 2048, 'log10_threshold': -6.01}]},
         'block_code': {'best_log10_p': -6.12, 'log10_threshold': -6.01, 'accepted': True,
                        'accepted_hypothesis': {'code': 'ccsds_tc_ldpc_128_64', 'family': 'ldpc',
                                                'n_codewords': 18,
                                                'converged_codewords': [False] * 18}},
         'diagnostics': d}
    r.update(over)
    return r


def test_the_grid_is_imported_not_redefined():
    """'No new correction magnitude' must be structural, not a promise."""
    assert 'SHAPES' not in fs.__dict__ and 'MULTIPLIERS' not in fs.__dict__
    assert fs.diag.SHAPES == ('constant', 'linear_mean', 'pass_mean', 'estimator_scaled',
                              'varying_only')
    assert fs.diag.MULTIPLIERS == (0.01, 0.03, 0.1, 0.3, 0.5, 1.0, 2.0)
    assert fs.diag.correction is diag.correction
    assert fs.diag.PRIMARY.endswith(os.path.join('bench2', 'sealed', 'idle_carrier_0411.iq'))


def test_gate_extraction_reads_the_published_fields():
    g = fs._gates(_result())
    assert g['n_cfo_candidates'] == 2
    assert g['best_cfo_log10p'] == -141.5 and g['best_cfo'] == 0.0058   # most significant candidate
    assert g['detection_log10_p'] == -141.5
    assert g['n_sps_rows'] == 2 and g['sps_candidates'] == [20, 10, 5]
    assert g['best_q4_sps'] == 20 and g['best_q4'] == 0.22              # highest-q4 row
    assert g['mod_gate_8psk_searched'] is False and g['mod_decisions'] == ['BPSK', 'BPSK']
    assert g['n_front_ends'] == 18 and g['front_ends_rejected_serial_dependence'] == 378
    assert g['M_F4'] == 2048 and g['M_F1'] == 210
    assert np.isclose(g['f4_margin'], -6.12 - (-6.01)) and g['f4_accepted'] is True
    assert g['n_converged'] == 0 and g['n_codewords'] == 18


def test_the_candidate_pool_identity_the_report_relies_on():
    """rejected + surviving is the pool; the report's invariance claim is read off these two fields."""
    g = fs._gates(_result())
    assert g['front_ends_rejected_serial_dependence'] + g['n_front_ends'] == 396


def test_empty_diagnostics_yield_no_invented_values():
    g = fs._gates(_result(status='UNKNOWN', code=None,
                          block_code={'best_log10_p': 0.0, 'log10_threshold': -2.7,
                                      'accepted': False},
                          diagnostics={'cfo_candidates': [], 'sps_table': [], 'sps_candidates': [],
                                       'modulation_gates': {}, 'modulation_stats': [],
                                       'n_front_ends': 0,
                                       'front_ends_rejected_serial_dependence': 396}))
    assert g['n_cfo_candidates'] == 0 and g['best_cfo'] is None and g['best_q4'] is None
    assert g['mod_gate_8psk_searched'] is None and g['mod_decisions'] == []
    assert g['n_front_ends'] == 0 and g['f4_accepted'] is False
    assert g['n_converged'] is None                       # no accepted hypothesis -> nothing invented
    assert g['front_ends_rejected_serial_dependence'] + g['n_front_ends'] == 396
