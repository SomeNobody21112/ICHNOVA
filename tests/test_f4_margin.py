"""SPACE-F4-MARGIN-01 harness tests (eval/f4_margin.py) — additive, pure-function, no engine calls.

They guard the two things the F4 characterisation depends on: the margin sign convention (the
repository's own, eval/ladder.py:65 — negative means the bar was cleared) and the per-dataset
correctness rules. The null-set rule in particular covers a MIXED population (eval/nullset.py:39-42):
900 true nulls where any decode is a false accept, and 450 catalogue-coded files where a correct
decode exists — scoring those 450 as nulls understates the engine, which is the bug these tests pin.
"""
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, os.path.join(ROOT, 'eval'))

import f4_margin as f4                               # noqa: E402

K7 = 'conv_k7_r12_171_133'
BITS = [0, 1, 1, 0] * 32


def _result(**kw):
    base = {'status': 'DECODED', 'code': K7, 'modulation': 'BPSK', 'interleaver': [16, 24],
            'payload_bits': BITS, 'block_code': {}, 'stream_code': {}}
    return {**base, **kw}


def test_code_label_matches_nullset_mapping():
    assert f4._code_label('conv_k7_r12_171_133') == 'k7'
    assert f4._code_label('conv_k5_r12_23_35') == 'k5'
    assert f4._code_label('conv_k3_r12_7_5') == 'k3'
    assert f4._code_label('ccsds_rs_255_223') == 'ccsds_rs_255_223'   # passes through
    assert f4._code_label(None) is None


def test_true_null_classes_score_any_decode_as_a_false_accept():
    for cls in ('noise', 'uncoded_bpsk', 'uncoded_qpsk', '8psk_k7'):
        gt = {'class': cls}
        assert f4._correct('nullset', gt, _result())[0] == 'FALSE_ACCEPT'
        assert f4._correct('nullset', gt, _result())[1] is False
        for status in ('SIGNAL_NO_CODE', 'UNKNOWN'):
            outcome, ok = f4._correct('nullset', gt, _result(status=status))
            assert outcome == 'REFUSED_OK' and ok is True


def test_nullset_catalogue_classes_score_a_correct_decode_as_correct():
    """The 450 k7/k5/k3 files are NOT nulls: a correct decode exists and must not read as a failure."""
    gt = {'class': 'k7', 'interleaver': [16, 24], 'original_bits': BITS}
    outcome, ok = f4._correct('nullset', gt, _result())
    assert outcome == 'TP' and ok is True
    # a wrong code label under a DECODED claim is a false accept
    assert f4._correct('nullset', gt, _result(code='conv_k3_r12_7_5'))[0] == 'FALSE_ACCEPT'
    # wrong interleaver, same code: also a false accept (nullset.correct_decode requires both)
    assert f4._correct('nullset', gt, _result(interleaver=[12, 16]))[0] == 'FALSE_ACCEPT'
    # a wrong payload under the right claim: a false accept
    assert f4._correct('nullset', gt, _result(payload_bits=[1, 1, 1, 1] * 32))[0] == 'FALSE_ACCEPT'
    # a refusal on a capture that had a correct answer is a miss, never a false accept
    assert f4._correct('nullset', gt, _result(status='UNKNOWN')) == ('FN', False)


def test_bench1_rule_is_the_tripwire_rule():
    gt = {'original_bits': BITS}
    assert f4._correct('bench1', gt, _result())[0] == 'TP'
    assert f4._correct('bench1', gt, _result(code='ccsds_rs_255_223'))[0] == 'FALSE_ACCEPT'
    # A genuinely different payload. NOT the bitwise complement: bench2._ber is polarity-insensitive
    # by design (these codes leave polarity unresolved), so a complemented payload scores as correct.
    assert f4._correct('bench1', gt, _result(payload_bits=[0, 0, 0, 1] * 32))[0] == 'FALSE_ACCEPT'
    assert f4._correct('bench1', gt, _result(status='SIGNAL_NO_CODE'))[0] == 'FN'


def test_the_ber_rule_treats_a_complemented_payload_as_correct():
    """Pinning the convention the previous test could have hidden: polarity is unresolved, so the
    complement of the transmitted bits is scored correct — by bench2._ber, imported verbatim."""
    gt = {'original_bits': BITS}
    complemented = [1 - b for b in BITS]
    assert f4._correct('bench1', gt, _result(payload_bits=complemented))[0] == 'TP'


def test_margin_sign_convention_and_static_flag():
    """margin = best - bar (eval/ladder.py:65): negative means accepted."""
    gt = {'class': 'k7', 'interleaver': [16, 24], 'original_bits': BITS, 'channel': 'awgn'}
    r = _result(block_code={'best_log10_p': -6.25, 'log10_threshold': -6.19, 'accepted': True,
                            'accepted_hypothesis': {'code': 'ccsds_tc_ldpc_128_64', 'family': 'ldpc',
                                                    'n_codewords': 18,
                                                    'converged_codewords': [False] * 18}})
    row = f4._row(('nullset', 'x/y.iq', 'nullset', gt), r, 0.5)
    assert row['f4_margin'] < 0 and row['f4_accepted'] is True
    assert row['n_converged'] == 0 and row['zero_convergence'] is True
    assert row['static'] is True

    r2 = _result(block_code={'best_log10_p': -3.0, 'log10_threshold': -6.19, 'accepted': False})
    row2 = f4._row(('nullset', 'x/y.iq', 'nullset', {**gt, 'channel': 'cfo_drift'}), r2, 0.5)
    assert row2['f4_margin'] > 0 and row2['f4_accepted'] is False
    assert row2['zero_convergence'] is None            # no accepted hypothesis, nothing to report
    assert row2['static'] is False                     # protocol AMB-2: cfo_drift is not static
