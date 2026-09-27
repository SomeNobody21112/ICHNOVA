"""SPACE-TRACK-VALIDITY-01 — validating the published phase-tracking validity read-out.

Criteria: `eval/track_validity_criteria.json`.

`_track_phase` unwraps the per-block M-power angles, which is correct only while the true
block-to-block change stays below pi. The engine now publishes how close that unwrap actually ran to
its ambiguity, in `diagnostics.phase_tracking_validity`. pi is not a chosen threshold: it is the
exact discriminant of `np.unwrap`, the operation the shipped tracker performs.

This harness checks the field against the sealed Doppler evidence: does it separate static controls
from time-varying captures, does it sit nearest the bound exactly where SPACE-TRACK-READOUT-01
measured slips, and does it stay away from the bound on the controls?

    python eval/track_validity.py run
    python eval/track_validity.py report
"""

import hashlib
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding='utf-8')

from modem import load_iq                               # noqa: E402
from pipeline import analyze_iq                         # noqa: E402  (SHIPPED)

CRITERIA = os.path.join(HERE, 'track_validity_criteria.json')
ROWS = os.path.join('results', 'track_validity_rows.jsonl')
DOPPLER = os.path.join('data', 'space_bench', 'doppler')
SEALED = os.path.join('results', 'space_doppler_rows.jsonl')
READOUT = os.path.join('results', 'track_readout_rows.jsonl')
STATIC = ('zero', 'static')
TIME_VARYING = ('linear', 'pass')


def run():
    sealed = {json.loads(l)['file']: json.loads(l) for l in open(SEALED, encoding='utf-8')}
    readout = {json.loads(l)['file']: json.loads(l) for l in open(READOUT, encoding='utf-8')}
    rows = []
    files = sorted(f[:-3] for f in os.listdir(DOPPLER) if f.endswith('.iq'))
    for i, name in enumerate(files, 1):
        path = os.path.join(DOPPLER, name + '.iq')
        gt = json.load(open(path + '.gt.json', encoding='utf-8'))
        r = analyze_iq(load_iq(path))                   # no trace passed; the field is published
        v = r['diagnostics']['phase_tracking_validity']
        # the margin of the front end that produced the PUBLISHED claim, read by the index the
        # engine already publishes for the accepted stream hypothesis
        sc = r.get('stream_code') or {}
        ah = sc.get('accepted_hypothesis') if sc.get('accepted') else None
        by_fe = r['diagnostics']['unwrap_margin_by_front_end']
        claim_margin = (by_fe[ah['front']] if ah is not None and ah['front'] < len(by_fe)
                        else None)
        ro = readout.get(name, {})
        rows.append({
            'file': name, 'trajectory': gt['trajectory_class'], 'severity': gt['severity'],
            'length': (gt.get('params') or {}).get('length'), 'esn0_db': gt['esn0_db'],
            'outcome': sealed.get(name, {}).get('outcome'), 'status': r['status'],
            'final_code': r['code'],
            'n_tracked': None if v is None else v['n_tracked_front_ends'],
            'bound_rad': None if v is None else v['bound_rad'],
            'max_margin_rad': None if v is None else v['max_unwrap_margin_rad'],
            'min_margin_rad': None if v is None else v['min_unwrap_margin_rad'],
            'claim_front': None if ah is None else ah['front'],
            'claim_margin_rad': claim_margin,
            'state': ('INDETERMINATE' if claim_margin is None else 'MEASURED'),
            'aggregate_state': 'INDETERMINATE' if v is None else 'MEASURED',
            # cross-reference to what the read-out measured against the KNOWN trajectory
            'n_slips': ro.get('n_slips'), 'claim_tracking': ro.get('claim_tracking'),
            'tracker_ran_on_claim': ro.get('tracker_ran'),
        })
        if i % 48 == 0:
            print(f'  {i}/{len(files)}')

    os.makedirs('results', exist_ok=True)
    with open(ROWS, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r) + '\n')
    bad = [r['file'] for r in rows if sealed.get(r['file'], {}).get('status') != r['status']]
    print(f'\n{len(rows)} captures -> {ROWS}')
    print(f'field published on {sum(1 for r in rows if r["state"] == "MEASURED")}/{len(rows)}; '
          f'INDETERMINATE on {sum(1 for r in rows if r["state"] == "INDETERMINATE")}')
    print('VERDICTS UNCHANGED vs the sealed SPACE-DOPPLER run' if not bad
          else f'STOP: verdicts differ on {bad[:5]}')


def _rng(xs, key='max_margin_rad'):
    v = np.array([x[key] for x in xs if x[key] is not None])
    return (f'n={len(v):3} min {v.min():7.4f} med {np.median(v):7.4f} max {v.max():7.4f}'
            if len(v) else 'n=  0')


def report():
    rows = [json.loads(l) for l in open(ROWS, encoding='utf-8')]
    print(f'\nSPACE-TRACK-VALIDITY-01 — {len(rows)} sealed Doppler captures; criteria sha256 '
          f'{hashlib.sha256(open(CRITERIA, "rb").read()).hexdigest()[:16]}…')
    print(f'bound = pi = {np.pi:.6f} rad (the exact discriminant of np.unwrap, not a chosen '
          f'threshold)\n')

    meas = [r for r in rows if r['aggregate_state'] == 'MEASURED']
    ind = [r for r in rows if r['aggregate_state'] == 'INDETERMINATE']
    print(f'AGGREGATE FIELD COVERAGE: published {len(meas)}, null (no tracked front end at all, '
          f'i.e. INDETERMINATE) {len(ind)}')
    cm = [r for r in rows if r['claim_margin_rad'] is not None]
    print(f'CLAIM-LEVEL COVERAGE: {len(cm)} captures whose published claim came from a TRACKED '
          f'front end; {len(rows) - len(cm)} INDETERMINATE (claim untracked, or refused)')

    print('\nclaim_margin_rad — the margin of the front end that produced the PUBLISHED claim')
    print('  (read by the index the engine already publishes; this is the representation that')
    print('   answers the question — the whole-search aggregates below do NOT)')
    for cls in ('zero', 'static', 'linear', 'pass'):
        xs = [r for r in cm if r['trajectory'] == cls]
        if xs:
            print(f'  {cls:8} {_rng(xs, "claim_margin_rad")}')
    sc_ = [r for r in cm if r['trajectory'] in STATIC]
    tc_ = [r for r in cm if r['trajectory'] in TIME_VARYING]
    if sc_ and tc_:
        lo = min(r['claim_margin_rad'] for r in sc_)
        hi = max(r['claim_margin_rad'] for r in tc_)
        print(f'  SEPARATION: time-varying max {hi:.4f}  vs  static min {lo:.4f}  -> '
              f'{"NON-OVERLAPPING" if hi < lo else "OVERLAPPING"}')
    print('\n  against slips measured from the KNOWN trajectory:')
    for lbl, xs in (('no slip', [r for r in cm if r['n_slips'] == 0]),
                    ('slipped', [r for r in cm if (r['n_slips'] or 0) > 0])):
        if xs:
            print(f'    {lbl:8} {_rng(xs, "claim_margin_rad")}')
    for lbl, xs in (('claim correct', [r for r in cm if r['outcome'] == 'DECODED_CORRECT']),
                    ('claim wrong', [r for r in cm if r['outcome'] == 'FALSE_DECODE'])):
        if xs:
            print(f'    {lbl:14} {_rng(xs, "claim_margin_rad")}')

    print('\nmax_unwrap_margin_rad — the headroom the BEST tracked front end achieved')
    for cls in ('zero', 'static', 'linear', 'pass'):
        xs = [r for r in meas if r['trajectory'] == cls]
        if xs:
            print(f'  {cls:8} {_rng(xs)}')
    st = [r for r in meas if r['trajectory'] in STATIC]
    tv = [r for r in meas if r['trajectory'] in TIME_VARYING]
    if st and tv:
        lo = min(r['max_margin_rad'] for r in st)
        hi = max(r['max_margin_rad'] for r in tv)
        print(f'\n  SEPARATION: time-varying max {hi:.4f}  <  static min {lo:.4f}   '
              f'-> {"NON-OVERLAPPING" if hi < lo else "OVERLAPPING"}')

    print('\nmin_unwrap_margin_rad — the WORST tracked front end (NOT a warning signal)')
    for cls in ('zero', 'static', 'linear', 'pass'):
        xs = [r for r in meas if r['trajectory'] == cls]
        if xs:
            print(f'  {cls:8} {_rng(xs, "min_margin_rad")}')
    print('  the front-end search deliberately includes wrong-cfo / wrong-sps candidates, whose')
    print('  trackers SHOULD be beyond the bound — so a small minimum is expected, not a fault.')

    print('\nDOES IT FIND THE KNOWN SLIP REGIME?  (slips measured against the KNOWN trajectory)')
    for lbl, xs in (('no slip measured', [r for r in meas if r['n_slips'] == 0]),
                    ('slips measured', [r for r in meas if (r['n_slips'] or 0) > 0])):
        if xs:
            print(f'  {lbl:18} {_rng(xs)}')

    print('\nBY SEVERITY (time-varying)')
    for s in sorted({r['severity'] for r in tv}):
        xs = [r for r in tv if r['severity'] == s]
        print(f'  severity {s:<5} {_rng(xs)}')

    print('\nBY OUTCOME (time-varying)')
    for oc in ('DECODED_CORRECT', 'FALSE_DECODE', 'REFUSED'):
        xs = [r for r in tv if r['outcome'] == oc]
        if xs:
            print(f'  {oc:16} {_rng(xs)}')
    print('\n  NOTE: a small margin is EVIDENCE that the unwrap ran at its ambiguity. It is not a')
    print('  verdict: REFUSED captures sit there too, and the engine refused them on its own bars.')


def demo():
    """Self-check: the published margin is exactly pi - max|wrap(diff(block_angles))|."""
    import pipeline
    rng = np.random.RandomState(0)
    bits = rng.choice([-1.0, 1.0], 4096)
    y = bits * np.exp(1j * 2 * np.pi * np.cumsum(np.full(4096, 3e-4)))
    t = {}
    pipeline._track_phase(y, 'BPSK', _trace=t)
    ang = np.array(t['block_angles'])
    wrapped = (np.diff(ang) + np.pi) % (2 * np.pi) - np.pi
    assert np.isclose(t['max_wrapped_advance_rad'], np.max(np.abs(wrapped)))
    assert np.isclose(t['unwrap_margin_rad'], np.pi - np.max(np.abs(wrapped)))
    assert np.isclose(t['unwrap_bound_rad'], np.pi)
    # a nearly static carrier keeps a large margin; a fast one runs the unwrap to its ambiguity
    slow = bits * np.exp(1j * 2 * np.pi * np.cumsum(np.full(4096, 1e-6)))
    ts = {}
    pipeline._track_phase(slow, 'BPSK', _trace=ts)
    assert ts['unwrap_margin_rad'] > t['unwrap_margin_rad']
    print("demo: the published margin matches the tracker's own unwrap arithmetic")


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'demo'
    os.chdir(ROOT)
    {'run': run, 'report': report, 'demo': demo}[cmd]()
