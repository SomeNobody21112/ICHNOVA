"""SPACE-PAYLOAD-GATE-01 — the payload gate must only ever withhold, never invent.

The gate is not integrated into src/. These tests pin the properties that would have to hold before
it ever could be: it withholds a payload while keeping the structure, it leaves families that publish
no payload-side statistic alone, it never upgrades a refusal into a claim, and the measured cost on
the populations that already work stays at zero.
"""
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, os.path.join(ROOT, 'eval'))

import payload_gate as pg                              # noqa: E402

CRITERIA = json.load(open(os.path.join(ROOT, 'eval', 'payload_gate_criteria.json'),
                          encoding='utf-8'))
ROWS = os.path.join(ROOT, 'results', 'payload_gate_rows.jsonl')


def _rows():
    with open(ROWS, encoding='utf-8') as f:
        return [json.loads(l) for l in f if l.strip()]


def test_the_gate_withholds_a_payload_and_keeps_the_structure():
    bar = 0.98
    assert pg.gated({'f2_supplied': True, 'consistency': 0.91, 'status': 'DECODED'}, bar) \
        == 'SIGNAL_NO_CODE'
    assert pg.gated({'f2_supplied': True, 'consistency': 0.999, 'status': 'DECODED'}, bar) \
        == 'DECODED'


def test_the_gate_never_upgrades_a_refusal():
    """A gate that could turn UNKNOWN into DECODED would be the opposite of this project."""
    for status in ('UNKNOWN', 'SIGNAL_NO_CODE'):
        for f2, cons in ((False, None), (True, 0.5), (True, 1.0)):
            assert pg.gated({'f2_supplied': f2, 'consistency': cons,
                             'status': status}, 0.98) == status


def test_families_without_a_payload_statistic_are_untouched():
    """F1 burst, F3 frame and F4 block-code publish no consistency; the gate must not guess one."""
    assert pg.gated({'f2_supplied': False, 'consistency': None, 'status': 'DECODED'}, 0.98) \
        == 'DECODED'
    assert pg.gated({'f2_supplied': True, 'consistency': None, 'status': 'DECODED'}, 0.98) \
        == 'DECODED'
    assert pg.gated({'f2_supplied': True, 'consistency': 0.1, 'status': 'DECODED'}, None) \
        == 'DECODED'                                   # no bar -> no change at all


def test_the_bar_is_set_from_correct_decodes_only_never_from_the_failures():
    """The committed rule. A bar fitted to the failures it catches would be threshold tuning."""
    synthetic = [
        {'population': 'bench2_sealed', 'f2_supplied': True, 'outcome': 'TP', 'consistency': 0.99},
        {'population': 'bench2_sealed', 'f2_supplied': True, 'outcome': 'TP', 'consistency': 0.97},
        # a failure with a much lower value must NOT drag the bar down
        {'population': 'bench2_sealed', 'f2_supplied': True, 'outcome': 'FALSE_ACCEPT',
         'consistency': 0.40},
        # another population must not contribute
        {'population': 'doppler', 'f2_supplied': True, 'outcome': 'DECODED_CORRECT',
         'consistency': 0.10},
    ]
    bar, n = pg.bar_from(synthetic)
    assert (bar, n) == (0.97, 2)
    rule = CRITERIA['bar_selection_rule_fixed_before_the_cost_measurement']['rule']
    assert 'never' in rule.lower()


def test_the_measured_cost_on_working_populations_is_still_zero():
    rows = _rows()
    bar, _ = pg.bar_from(rows)
    assert bar is not None
    for pop in ('bench1_sealed', 'bench2_sealed', 'nullset'):
        correct = [r for r in rows if r['population'] == pop and r.get('correct')]
        assert correct, f'{pop} should have correct decodes to protect'
        lost = [r for r in correct if pg.gated(r, bar) != r['status']]
        assert not lost, f'{pop} lost {len(lost)} working decodes: {[r["file"] for r in lost][:3]}'


def test_the_criteria_declare_the_peek_and_withhold_integration_approval():
    """Two honesty requirements that outlive the run."""
    assert 'NOT a blind estimate' in CRITERIA['declared_peek']
    assert 'integration_is_not_decided_here' in CRITERIA['decision_rules']
    assert 'changes REFUSAL BEHAVIOUR' in \
        CRITERIA['decision_rules']['integration_is_not_decided_here']
