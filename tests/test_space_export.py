"""The Space page must never drift from the evidence it claims to show.

frontend/public/space.json is a committed artefact written by server/export_space_data.py. If a result
file changes and the export is not re-run, the console would keep showing the old numbers with a
straight face. These tests re-derive the headline figures from the row files and compare.
"""
import json
import os

ROOT = os.path.join(os.path.dirname(__file__), '..')
SPACE = os.path.join(ROOT, 'frontend', 'public', 'space.json')
TREATED = ('linear', 'pass')


def _rows(name):
    with open(os.path.join(ROOT, 'results', name), encoding='utf-8') as f:
        return [json.loads(l) for l in f if l.strip()]


def _space():
    with open(SPACE, encoding='utf-8') as f:
        return json.load(f)


def test_the_published_doppler_headline_matches_the_sealed_rows():
    d, rows = _space()['doppler'], _rows('space_doppler_rows.jsonl')
    tv = [r for r in rows if r['trajectory'] in TREATED]
    ct = [r for r in rows if r['trajectory'] not in TREATED]
    assert d['n'] == len(rows) and d['treated'] == len(tv) and d['controls'] == len(ct)
    assert d['wrong_payload'] == sum(1 for r in tv if r['outcome'] == 'FALSE_DECODE')
    assert d['controls_wrong_payload'] == sum(1 for r in ct if r['outcome'] == 'FALSE_DECODE')
    assert d['wrong_structure'] == sum(1 for r in rows if r['outcome'] == 'WRONG_STRUCTURE')


def test_the_measured_limitation_is_still_what_the_page_says_it_is():
    """The two numbers the whole Space story rests on. If either moves, the claim wording must too."""
    d = _space()['doppler']
    assert (d['wrong_payload'], d['treated']) == (54, 96)
    assert d['controls_wrong_payload'] == 0
    assert d['wrong_structure'] == 0, 'the structural half of the claim must still hold'


def test_the_page_never_shows_an_off_carrier_or_orbital_capability():
    """Guards the claim firewall at the data layer: no claim came from an off-carrier front end."""
    oc = _space()['offcarrier']
    assert oc['f4_passes_from_off_carrier'] == 0
    assert 'off_carrier' not in oc['claims_by_band'], 'a claim from an off-carrier front end is news'
    assert oc['admitted_off_carrier'] > 0, 'they are admitted routinely; that is the point'


def test_the_tracker_block_says_the_slip_is_not_the_whole_explanation():
    tr, rows = _space()['tracker'], _rows('track_readout_rows.jsonl')
    assert tr['failures_total'] == sum(1 for r in rows if r['outcome'] == 'FALSE_DECODE')
    assert tr['failures_from_untracked'] == sum(
        1 for r in rows if r['outcome'] == 'FALSE_DECODE' and r['claim_tracking'] == 'static')
    # the honest half: most of the failure is not the tracker's
    assert 0 < tr['failures_from_untracked'] < tr['failures_total']


def test_every_block_names_the_result_file_it_came_from():
    d = _space()
    for key in ('doppler', 'mechanism', 'estimator', 'f4', 'offcarrier', 'tracker', 'validity'):
        assert d[key]['source'].startswith('results/'), f'{key} must cite its evidence file'
    assert d['generated_from_commit']
