"""SPACE-FRONTEND-SENSITIVITY-01 — which published front-end gate moves when the carrier correction changes?

Criteria: `eval/frontend_sensitivity_criteria.json`. Read-only characterisation using **only** diagnostics
the engine already publishes. No production file is modified; if the published fields cannot separate the
conditions, the experiment reports INSUFFICIENT PUBLISHED DIAGNOSTICS and names the missing value rather
than exposing new internals.

The correction grid, the primary capture and the secondary selection are **imported** from
`eval/carrier_est_diag.py`, so no new magnitude, shape or capture is introduced and the two runs are
directly comparable. SPACE-CARRIER-EST-DIAG-01 recorded front-end *counts*; this run records the upstream
gate values for the identical conditions.

    python eval/frontend_sensitivity.py primary      # 38 conditions on idle_carrier_0411
    python eval/frontend_sensitivity.py secondary    # the same 5 groups x 2 captures x 5 conditions
    python eval/frontend_sensitivity.py report
"""

import hashlib
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding='utf-8')

import carrier_est_diag as diag                            # noqa: E402  (grid + captures, imported)
import f4_margin as f4m                                    # noqa: E402
import space_doppler_mech as mech                          # noqa: E402
from pipeline import analyze_iq                            # noqa: E402

CRITERIA = os.path.join(HERE, 'frontend_sensitivity_criteria.json')
ROWS = os.path.join('results', 'frontend_sensitivity_rows.jsonl')


def _gates(r):
    """Every field this experiment records comes from the engine's PUBLISHED diagnostics."""
    d = r['diagnostics']
    cands = d['cfo_candidates'] or []
    best = min(cands, key=lambda c: c['log10_p']) if cands else {}
    table = d['sps_table'] or []
    best_q4 = max(table, key=lambda x: x['q4']) if table else {}
    gates = d.get('modulation_gates') or {}
    f4 = r.get('block_code') or {}
    a4 = f4.get('accepted_hypothesis') or {}
    conv = a4.get('converged_codewords')
    fb, fbar = f4.get('best_log10_p'), f4.get('log10_threshold')
    row = {
        # ---- CFO / detection
        'n_cfo_candidates': len(cands),
        'best_cfo': best.get('cfo'), 'best_cfo_log10p': best.get('log10_p'),
        'best_cfo_order': best.get('order'), 'best_cfo_peak_db': best.get('peak_to_floor_db'),
        'detection_log10_p': d['detection_log10_p'],
        # ---- symbol rate
        'n_sps_rows': len(table), 'sps_candidates': d['sps_candidates'],
        'raw_sps_estimate': d['raw_sps_estimate'],
        'best_q4_sps': best_q4.get('sps'), 'best_q4': best_q4.get('q4'), 'best_q2': best_q4.get('q2'),
        # ---- modulation
        'mod_gate_8psk_searched': (gates.get('8PSK') or {}).get('searched'),
        'mod_gate_16qam_searched': (gates.get('16QAM') or {}).get('searched'),
        'mod_decisions': [s.get('decision') for s in (d.get('modulation_stats') or [])],
        # ---- front-end construction
        'n_front_ends': d['n_front_ends'],
        'phase_tracked_front_ends': d['phase_tracked_front_ends'],
        'front_ends_rejected_serial_dependence': d.get('front_ends_rejected_serial_dependence'),
        # ---- downstream
        'f4_best': fb, 'f4_bar': fbar,
        'f4_margin': None if (fb is None or fbar is None) else float(fb - fbar),
        'f4_accepted': bool(f4.get('accepted')), 'f4_code': a4.get('code'),
        'f4_family': a4.get('family'), 'n_codewords': a4.get('n_codewords'),
        'n_converged': None if conv is None else int(sum(conv)),
        'status': r['status'], 'final_code': r['code'], 'final_modulation': r['modulation'],
        'runner_up_margin_log10': d.get('runner_up_margin_log10'),
        'n_hypotheses_total': r['accept']['n_hypotheses'],
    }
    for fam in r['accept']['families']:
        key = fam['name'].split('_')[0]
        row[f'M_{key}'] = fam['tested_hypotheses']
        row[f'bar_{key}'] = fam['log10_threshold']
    return row


def _measure(case, group, path, gt, kind, label, shape, m, iq, f_corr):
    x = iq if f_corr is None else mech._derotate(iq, f_corr)
    t = time.perf_counter()
    r = analyze_iq(x)
    runtime = time.perf_counter() - t
    if kind == 'carrier_est':
        outcome, _ = mech.score(gt, r)
    else:
        outcome, _ = f4m._correct(kind, gt, r)
    corr = {'corr_mean': None, 'corr_ptp': None, 'corr_varying_rms': None}
    if f_corr is not None:
        f = np.asarray(f_corr, dtype=float)
        corr = {'corr_mean': float(np.mean(f)), 'corr_ptp': float(np.ptp(f)),
                'corr_varying_rms': float(np.sqrt(np.mean((f - np.mean(f)) ** 2)))}
    return {'case': case, 'group': group, 'file': os.path.basename(path)[:-3],
            'condition': label, 'shape': shape, 'm': m, **corr, **_gates(r),
            'outcome': outcome, 'runtime': runtime}


def primary():
    gt, iq, f_hat, est = diag._load(diag.PRIMARY)
    scale = est['est_mean']
    print(f'primary: {os.path.basename(diag.PRIMARY)}  gt {gt["class"]} expected {gt["expected"]}  '
          f'true cfo {gt["cfo"]:.6f}   estimator mean {scale:.6e}')
    conds = [('A_original', None, None, None),
             ('B_zero_correction', 'zero', 0.0, np.zeros(len(iq))),
             ('C_estimator_exact', 'estimator_exact', 1.0, f_hat)]
    for shape in diag.SHAPES:
        for m in diag.MULTIPLIERS:
            conds.append(('D_E_F_controlled', shape, m,
                          diag.correction(shape, m, len(iq), f_hat, scale)))
    rows = []
    for label, shape, m, f_corr in conds:
        row = _measure('primary', 'idle_carrier', diag.PRIMARY, gt, 'bench2', label, shape, m, iq,
                       f_corr)
        rows.append(row)
        print(f'  {label:20} {str(shape):17} m={str(m):5} | cfo cands {row["n_cfo_candidates"]:2} '
              f'det {row["detection_log10_p"]:8.2f} | sps rows {row["n_sps_rows"]:2} cands '
              f'{str(row["sps_candidates"])[:18]:18} | fronts {row["n_front_ends"]:3} | M_F4 '
              f'{row["M_F4"]:5} | margin {row["f4_margin"]:+8.3f} '
              f'{"ACCEPT" if row["f4_accepted"] else ""}')
    os.makedirs('results', exist_ok=True)
    with open(ROWS, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r) + '\n')
    print(f'{len(rows)} analyses -> {ROWS}')


def secondary():
    groups = diag.secondary_selection()
    rows = []
    for g, (pop, files) in groups.items():
        kind = diag.DATASET_KIND.get(pop, 'carrier_est')
        for fname in files:
            path = os.path.join(diag.POP_DIR[pop], fname + '.iq')
            gt, iq, f_hat, est = diag._load(path)
            conds = [('A_original', None, None, None),
                     ('B_zero_correction', 'zero', 0.0, np.zeros(len(iq))),
                     ('C_estimator_exact', 'estimator_exact', 1.0, f_hat),
                     ('D_E_F_controlled', 'estimator_scaled', 0.1,
                      diag.correction('estimator_scaled', 0.1, len(iq), f_hat, est['est_mean'])),
                     ('D_E_F_controlled', 'estimator_scaled', 1.0,
                      diag.correction('estimator_scaled', 1.0, len(iq), f_hat, est['est_mean']))]
            for label, shape, m, f_corr in conds:
                row = _measure('secondary', g, path, gt, kind, label, shape, m, iq, f_corr)
                rows.append(row)
                print(f'  {g:30} {fname:22} {label:20} m={str(m):5} cfo '
                      f'{row["n_cfo_candidates"]:2} sps {str(row["sps_candidates"])[:16]:16} '
                      f'fronts {row["n_front_ends"]:3} {row["status"]:15} {row["outcome"]}')
    with open(ROWS, 'a', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r) + '\n')
    print(f'{len(rows)} secondary analyses appended -> {ROWS}')


def _sha256(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def report():
    rows = [json.loads(l) for l in open(ROWS, encoding='utf-8')]
    prim = [r for r in rows if r['case'] == 'primary']
    print(f'\nSPACE-FRONTEND-SENSITIVITY-01 — {len(rows)} analyses; criteria sha256 '
          f'{_sha256(CRITERIA)[:16]}…\n')

    a = next(r for r in prim if r['condition'] == 'A_original')
    b = next(r for r in prim if r['condition'] == 'B_zero_correction')
    keys = [k for k in a if k not in ('condition', 'shape', 'm', 'runtime', 'corr_mean', 'corr_ptp',
                                      'corr_varying_rms')]
    print('TRANSPARENCY CONTROL: zero correction identical to the original on every recorded field: '
          f'{all(a[k] == b[k] for k in keys)}')

    print('\nTHE DESCRIPTIVE CHAIN (primary capture, every imported grid cell)')
    print('  condition                          cfo  det_log10p  sps_rows  sps_cands          '
          'fronts  M_F4   F4 margin  acc')
    for r in prim:
        tag = (r['condition'] if r['condition'] != 'D_E_F_controlled'
               else f'{r["shape"]}/m={r["m"]}')
        print(f'  {tag:34} {r["n_cfo_candidates"]:3}  {r["detection_log10_p"]:10.2f}  '
              f'{r["n_sps_rows"]:8}  {str(r["sps_candidates"])[:18]:18}  {r["n_front_ends"]:6}  '
              f'{r["M_F4"]:5}  {r["f4_margin"]:+9.3f}  {"YES" if r["f4_accepted"] else ""}')

    print('\nWHICH PUBLISHED GATE MOVES WITH front-end construction (primary)')
    zero = [r for r in prim if r['n_front_ends'] == 0]
    nz = [r for r in prim if r['n_front_ends'] > 0]
    for field in ('n_cfo_candidates', 'detection_log10_p', 'n_sps_rows', 'raw_sps_estimate',
                  'best_q4', 'best_q4_sps', 'mod_gate_8psk_searched', 'mod_gate_16qam_searched'):
        zv = sorted({r[field] for r in zero if not isinstance(r[field], list)},
                    key=lambda v: (v is None, v))
        nv = sorted({r[field] for r in nz if not isinstance(r[field], list)},
                    key=lambda v: (v is None, v))
        sep = set(zv).isdisjoint(nv)
        print(f'  {field:28} 0-front-end: {str(zv)[:42]:42} | >0: {str(nv)[:38]:38} | '
              f'separates: {sep}')
    print(f'  sps_candidates (0 fronts)   {sorted({tuple(r["sps_candidates"]) for r in zero})}')
    print(f'  sps_candidates (>0 fronts)  '
          f'{sorted({tuple(r["sps_candidates"]) for r in nz})[:4]}')

    print('\nCELLS THAT BUILT FRONT ENDS — accepting vs not')
    for r in [x for x in prim if x['n_front_ends'] > 0]:
        tag = (r['condition'] if r['condition'] != 'D_E_F_controlled'
               else f'{r["shape"]}/m={r["m"]}')
        print(f'  {tag:34} fronts {r["n_front_ends"]:3} M_F4 {r["M_F4"]:5} '
              f'margin {r["f4_margin"]:+8.3f} '
              f'{"ACCEPT " + str(r["f4_code"]) if r["f4_accepted"] else ""}')

    sec = [r for r in rows if r['case'] == 'secondary']
    if sec:
        print('\nSECONDARY CAPTURES — the same chain')
        for g in sorted({r['group'] for r in sec}):
            for fname in sorted({r['file'] for r in sec if r['group'] == g}):
                print(f'  {g} / {fname}')
                for r in [x for x in sec if x['group'] == g and x['file'] == fname]:
                    tag = (r['condition'] if r['condition'] != 'D_E_F_controlled'
                           else f'estimator_scaled/m={r["m"]}')
                    print(f'    {tag:30} cfo {r["n_cfo_candidates"]:2} det '
                          f'{r["detection_log10_p"]:8.2f} sps {str(r["sps_candidates"])[:16]:16} '
                          f'fronts {r["n_front_ends"]:3} M_F4 {r["M_F4"]:5} '
                          f'{r["status"]:15} {r["outcome"]}')


def demo():
    """Self-check: the gate extractor reads only published fields and tolerates an empty diagnostic."""
    r = {'status': 'UNKNOWN', 'code': None, 'modulation': 'BPSK',
         'accept': {'n_hypotheses': 0, 'families': [
             {'name': 'F1_burst_code', 'tested_hypotheses': 0, 'log10_threshold': -2.7},
             {'name': 'F4_block_code', 'tested_hypotheses': 0, 'log10_threshold': -2.7}]},
         'block_code': {'best_log10_p': 0.0, 'log10_threshold': -2.7, 'accepted': False},
         'diagnostics': {'cfo_candidates': [], 'detection_log10_p': 0.0, 'sps_table': [],
                         'sps_candidates': [], 'raw_sps_estimate': 3.0, 'modulation_gates': {},
                         'modulation_stats': [], 'n_front_ends': 0,
                         'phase_tracked_front_ends': 0,
                         'front_ends_rejected_serial_dependence': 0,
                         'runner_up_margin_log10': None}}
    g = _gates(r)
    assert g['n_cfo_candidates'] == 0 and g['best_cfo'] is None and g['n_front_ends'] == 0
    assert g['M_F4'] == 0 and np.isclose(g['f4_margin'], 2.7)
    assert diag.SHAPES == ('constant', 'linear_mean', 'pass_mean', 'estimator_scaled',
                           'varying_only')
    assert diag.MULTIPLIERS == (0.01, 0.03, 0.1, 0.3, 0.5, 1.0, 2.0)
    print('demo: gate extraction and imported-grid self-checks pass')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'demo'
    os.chdir(ROOT)
    {'primary': primary, 'secondary': secondary, 'report': report, 'demo': demo}[cmd]()
