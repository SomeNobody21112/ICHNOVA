"""SPACE-OFFCARRIER-CENSUS-01 harness tests (eval/offcarrier_census.py) — additive, no engine calls.

The census only means something if three things are structural rather than promised: the population
and the correctness rule are the ones the earlier sealed experiments already committed to (imported,
not copied), the band rule is the one the criteria file fixed before measurement, and the evaluation
-only `_all_hypotheses` flag is checked for verdict-neutrality rather than assumed to be neutral.
"""
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, os.path.join(ROOT, 'eval'))

import f4_margin as f4m                                # noqa: E402
import frontend_mechanism as fm                        # noqa: E402
import offcarrier_census as oc                         # noqa: E402
import pipeline                                        # noqa: E402

CRITERIA = json.load(open(os.path.join(ROOT, 'eval', 'offcarrier_census_criteria.json'),
                          encoding='utf-8'))


def test_population_and_correctness_are_imported_not_redefined():
    """'Broadest already-sealed evidence set' must be the same population F4-MARGIN-01 committed to."""
    assert 'DATASETS' not in oc.__dict__ and '_correct' not in oc.__dict__
    assert f4m.DATASETS == (('bench2_sealed', os.path.join('data', 'bench2', 'sealed'), 'bench2'),
                            ('bench1_sealed', os.path.join('data', 'sealed'), 'bench1'),
                            ('nullset', os.path.join('data', 'nullset'), 'nullset'))
    assert f4m.NULLSET_CATALOGUE_CLASSES == ('k7', 'k5', 'k3')      # mixed null set, still pinned
    assert oc.fm._front_candidates is fm._front_candidates          # the VERIFIED replication
    assert oc.CFO_MAX == pipeline.CFO_MAX


def test_band_rule_matches_the_committed_criteria():
    """The band edges are load-bearing, so they must equal what was committed before measurement."""
    assert (oc.ON_CARRIER, oc.OFF_CARRIER) == (0.01, 0.10)
    assert '0.01' in CRITERIA['definitions_committed_before_measurement']['bands']['on_carrier']
    assert '0.1' in CRITERIA['definitions_committed_before_measurement']['bands']['off_carrier']
    assert oc.SENSITIVITY_EDGES == (0.05, 0.10, 0.20)   # the headline is reported at each edge
    # boundaries are inclusive-below, so a candidate exactly at an edge takes the gentler band
    assert oc._band(0.0) == oc._band(0.01) == 'on_carrier'
    assert oc._band(0.0100001) == oc._band(0.10) == 'near_carrier'
    assert oc._band(0.1000001) == oc._band(99.0) == 'off_carrier'


def test_no_carrier_reference_is_never_invented():
    """A no-signal capture has no meaningful carrier; the harness must say so, not guess a number."""
    assert oc._true_carrier({}, 1000) == (None, False)
    assert oc._band(None) == 'undefined'


def test_a_drifting_carrier_is_referenced_to_its_mean():
    ref, drifting = oc._true_carrier({'cfo': 0.004, 'cfo_drift_per_sample': 1e-6}, 2001)
    assert drifting and abs(ref - 0.005) < 1e-12          # 0.004 + 1e-6 * 1000
    assert oc._true_carrier({'cfo': 0.004, 'cfo_drift_per_sample': 0.0}, 2001) == (0.004, False)


def test_the_mech01_survivor_is_classified_off_carrier():
    """The candidate that produced the canonical false accept must fall in the band it motivated."""
    rot = abs(-0.012377 - 0.00584) * 18                   # MECH-01 survivor, sps 18
    assert oc._band(rot) == 'off_carrier'
    assert abs(-0.012377) > oc.BAND_EDGE_FRAC * pipeline.CFO_MAX
    # ...while the six uncorrected candidates of that same capture are all on- or near-carrier
    for cfo in (0.00584, 0.00587, 0.00581, 0.00101, 0.00995, 0.00724):
        assert oc._band(abs(cfo - 0.00584) * 18) in ('on_carrier', 'near_carrier')


def test_verdict_neutrality_check_actually_detects_a_difference(tmp_path, monkeypatch):
    """If the eval-only flag ever changed a verdict, the run must STOP — so the check must bite."""
    prev = tmp_path / 'f4m.jsonl'
    prev.write_text(json.dumps({'dataset': 'nullset', 'file': 'x', 'status': 'UNKNOWN',
                                'final_code': None, 'f4_accepted': False, 'f4_best': -1.0,
                                'outcome': 'REFUSED_OK'}) + '\n', encoding='utf-8')
    monkeypatch.setattr(oc, 'F4M_ROWS', str(prev))
    same = {'dataset': 'nullset', 'file': 'x', 'status': 'UNKNOWN', 'final_code': None,
            'f4_accepted': False, 'f4_best': -1.0, 'outcome': 'REFUSED_OK'}
    n, bad = oc._verdict_neutrality([same])
    assert (n, bad) == (1, [])
    n, bad = oc._verdict_neutrality([{**same, 'status': 'DECODED', 'f4_accepted': True}])
    assert len(bad) == 2 and 'x:status' in bad[0]
    n, bad = oc._verdict_neutrality([{**same, 'f4_best': -1.5}])
    assert len(bad) == 1 and 'f4_best' in bad[0]


def test_criteria_commit_the_admission_vs_existence_distinction():
    """The question is about ADMISSION; 'a candidate exists' must not be reported as a threat."""
    d = CRITERIA['the_seven_distinctions_required']
    assert 'NOT evidence of a threat' in d['admission_vs_existence']
    assert set(CRITERIA['decision_rules']) >= {'T1_existence', 'T2_admission', 'T3_reaches_f4',
                                               'T4_passes_f4', 'T5_wrong_claim'}
    assert set(CRITERIA['decision_rules']['threat_verdict']) == {
        'MEANINGFUL_THREAT', 'LATENT_NOT_REALIZED', 'NOT_PRESENT'}
