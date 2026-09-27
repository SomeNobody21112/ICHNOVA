"""SPACE-CARRIER-EST-DIAG-01 — why does carrier pre-correction help under drift and hurt when static?

Criteria: `eval/carrier_est_diag_criteria.json`, committed before any synthetic correction was applied.
Read-only over existing sealed captures. No dataset is generated, the estimator is imported and never
modified, and nothing under `src/`, `server/`, `frontend/` or `deploy/` is touched.

The design separates two things the previous experiment could not:

  * **estimation error** — the estimator's output differing from the truth, and
  * **correction-transformation effect** — what de-rotating the samples does to the structural
    evidence, regardless of whether the correction was warranted.

Every correction, including the explicit **zero** control, goes through the same function
(`space_doppler_mech._derotate`), so "the machinery perturbs it" and "the magnitude matters" are
distinguishable rather than confounded.

    python eval/carrier_est_diag.py primary      # the idle-carrier case: 37 analyses
    python eval/carrier_est_diag.py secondary    # 5 pre-declared groups x 2 captures x 5 conditions
    python eval/carrier_est_diag.py report
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

import f4_margin as f4m                                    # noqa: E402  (correctness rules, imported)
import space_doppler as sd                                 # noqa: E402  (trajectory shapes)
import space_doppler_mech as mech                          # noqa: E402  (estimator + _derotate)
from modem import load_iq                                  # noqa: E402
from pipeline import analyze_iq                            # noqa: E402

CRITERIA = os.path.join(HERE, 'carrier_est_diag_criteria.json')
ROWS = os.path.join('results', 'carrier_est_diag_rows.jsonl')
PRIMARY = os.path.join('data', 'bench2', 'sealed', 'idle_carrier_0411.iq')
CE_ROWS = os.path.join('results', 'carrier_est_rows.jsonl')
CE_REG_ROWS = os.path.join('results', 'carrier_est_regression_rows.jsonl')

SHAPES = ('constant', 'linear_mean', 'pass_mean', 'estimator_scaled', 'varying_only')
MULTIPLIERS = (0.01, 0.03, 0.1, 0.3, 0.5, 1.0, 2.0)        # m = 0 is arm C, analysed once
DATASET_KIND = {'bench2_sealed': 'bench2', 'bench1_sealed': 'bench1', 'nullset': 'nullset'}
POP_DIR = {'bench1_sealed': os.path.join('data', 'sealed'),
           'bench2_sealed': os.path.join('data', 'bench2', 'sealed'),
           'nullset': os.path.join('data', 'nullset'),
           'carrier_est': os.path.join('data', 'space_bench', 'carrier_est')}


def correction(shape, m, n, f_hat, scale):
    """The correction trajectory for one grid cell. `scale` is this capture's own estimator mean."""
    if shape == 'constant':
        return np.full(n, m * scale)
    if shape == 'linear_mean':
        return np.linspace(0.0, 2.0 * m * scale, n)         # mean = m*scale, time-varying
    if shape == 'pass_mean':
        return m * scale + sd.trajectory('pass', m * scale, n)
    if shape == 'estimator_scaled':
        return f_hat * m                                    # m=1 reproduces the estimator exactly
    if shape == 'varying_only':
        return (f_hat - float(np.mean(f_hat))) * m          # no constant term at all
    raise ValueError(shape)


def _mag(f):
    f = np.asarray(f, dtype=float)
    return {'corr_mean': float(np.mean(f)), 'corr_rms': float(np.sqrt(np.mean(f ** 2))),
            'corr_peak': float(np.max(np.abs(f))), 'corr_ptp': float(np.ptp(f)),
            'corr_varying_rms': float(np.sqrt(np.mean((f - np.mean(f)) ** 2)))}


def _measure(case, group, path, gt, kind, arm, shape, m, iq, f_corr, est):
    """Analyse one condition and record everything the criteria list."""
    x = iq if f_corr is None else mech._derotate(iq, f_corr)
    t = time.perf_counter()
    r = analyze_iq(x)
    runtime = time.perf_counter() - t
    f4 = r.get('block_code') or {}
    a4 = f4.get('accepted_hypothesis') or {}
    conv = a4.get('converged_codewords')
    best, bar = f4.get('best_log10_p'), f4.get('log10_threshold')
    if kind == 'carrier_est':
        outcome, _ = mech.score(gt, r)
        structure_correct = outcome != 'WRONG_STRUCTURE'
        payload_correct = outcome == 'CORRECT_STRUCTURE_CORRECT_PAYLOAD'
    else:
        outcome, ok = f4m._correct(kind, gt, r)
        structure_correct = outcome != 'FALSE_ACCEPT'
        payload_correct = ok
    row = {'case': case, 'group': group, 'file': os.path.basename(path)[:-3],
           'arm': arm, 'shape': shape, 'm': m,
           **(_mag(f_corr) if f_corr is not None else
              {'corr_mean': None, 'corr_rms': None, 'corr_peak': None, 'corr_ptp': None,
               'corr_varying_rms': None}),
           'f4_best': best, 'f4_bar': bar,
           'f4_margin': None if (best is None or bar is None) else float(best - bar),
           'f4_accepted': bool(f4.get('accepted')), 'f4_code': a4.get('code'),
           'f4_family': a4.get('family'), 'f4_offset': a4.get('offset'),
           'f4_randomizer': a4.get('randomizer'), 'n_codewords': a4.get('n_codewords'),
           'n_converged': None if conv is None else int(sum(conv)),
           'zero_convergence': None if conv is None else bool(sum(conv) == 0),
           'status': r['status'], 'final_code': r['code'], 'final_modulation': r['modulation'],
           'structure_correct': structure_correct, 'payload_correct': payload_correct,
           'outcome': outcome,
           'f2_accepted': bool((r.get('stream_code') or {}).get('accepted')),
           'n_front_ends': r['diagnostics']['n_front_ends'],
           'phase_tracked_front_ends': r['diagnostics']['phase_tracked_front_ends'],
           'runtime': runtime, **est}
    for fam in r['accept']['families']:
        row[f"M_{fam['name'].split('_')[0]}"] = fam['tested_hypotheses']
        row[f"bar_{fam['name'].split('_')[0]}"] = fam['log10_threshold']
    return row


def _load(path):
    gt = json.load(open(path + '.gt.json', encoding='utf-8'))
    iq = load_iq(path)
    f_hat, knots = mech.estimate_trajectory(iq)
    est = {'knots': knots, 'est_mean': float(np.mean(f_hat)),
           'est_rms': float(np.sqrt(np.mean(f_hat ** 2))),
           'est_varying_rms': float(np.sqrt(np.mean((f_hat - np.mean(f_hat)) ** 2)))}
    return gt, iq, f_hat, est


def _conditions_primary(iq, f_hat, scale):
    """Arm A, arm C (zero through the same path), arm B, then the pre-registered shape x m grid."""
    n = len(iq)
    yield ('A_original', None, None, None)
    yield ('C_zero_correction', 'zero', 0.0, np.zeros(n))
    yield ('B_estimator_exact', 'estimator_exact', 1.0, f_hat)
    for shape in SHAPES:
        for m in MULTIPLIERS:
            yield ('D_E_F_controlled', shape, m, correction(shape, m, n, f_hat, scale))


def primary():
    gt, iq, f_hat, est = _load(PRIMARY)
    scale = est['est_mean']
    print(f'primary: {os.path.basename(PRIMARY)}  n={len(iq)}  gt {gt["class"]} expected '
          f'{gt["expected"]}  true cfo {gt["cfo"]:.6f}')
    print(f'estimator: knots {est["knots"]}  mean {est["est_mean"]:.6e}  '
          f'varying rms {est["est_varying_rms"]:.6e}  (M_est = scale)')
    rows = []
    for arm, shape, m, f_corr in _conditions_primary(iq, f_hat, scale):
        row = _measure('primary', 'idle_carrier', PRIMARY, gt, 'bench2', arm, shape, m, iq, f_corr,
                       est)
        rows.append(row)
        print(f'  {arm:20} {str(shape):17} m={str(m):5}  margin '
              f'{row["f4_margin"]:+8.3f}  accepted {str(row["f4_accepted"]):5}  '
              f'{row["status"]:15} {str(row["final_code"])[:28]:28} conv '
              f'{row["n_converged"]}/{row["n_codewords"]}')
    os.makedirs('results', exist_ok=True)
    with open(ROWS, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r) + '\n')
    print(f'{len(rows)} analyses -> {ROWS}')


# ---------------------------------------------------------------- secondary cases
def _ce_rows():
    return ([json.loads(l) for l in open(CE_ROWS, encoding='utf-8')],
            [json.loads(l) for l in open(CE_REG_ROWS, encoding='utf-8')])


def secondary_selection():
    """The pre-declared deterministic selection: first two by filename per group (criteria)."""
    new, reg = _ce_rows()

    def pick(rows, pred_a, pred_b):
        a = {r['file']: r for r in rows if r['arm'] == 'A_production'}
        b = {r['file']: r for r in rows if r['arm'] == 'B_candidate'}
        return sorted(f for f in a if f in b and pred_a(a[f]) and pred_b(b[f]))[:2]

    groups = {}
    for gname, pop in (('G1_bench1_failures', 'bench1_sealed'),
                       ('G2_bench2_failures', 'bench2_sealed')):
        rs = [r for r in reg if r['population'] == pop]
        groups[gname] = (pop, pick(rs, lambda r: r['outcome'] == 'TP',
                                   lambda r: r['outcome'] != 'TP'))
    rs = [r for r in reg if r['population'] == 'nullset' and r['cls'] in ('k7', 'k5', 'k3')]
    groups['G3_catalogue_control_failures'] = ('nullset', pick(rs, lambda r: r['correct'],
                                                               lambda r: not r['correct']))
    ok = 'CORRECT_STRUCTURE_CORRECT_PAYLOAD'
    st = [r for r in new if r['trajectory'] == 'static']
    groups['G4_static_unaffected'] = ('carrier_est', pick(st, lambda r: r['outcome'] == ok,
                                                          lambda r: r['outcome'] == ok))
    tv = [r for r in new if r['trajectory'] in ('linear', 'pass')]
    groups['G5_time_varying_success'] = ('carrier_est', pick(
        tv, lambda r: r['outcome'] == 'CORRECT_STRUCTURE_WRONG_PAYLOAD',
        lambda r: r['outcome'] == ok))
    return groups


def secondary():
    groups = secondary_selection()
    print('pre-declared selection (first two by filename per group):')
    for g, (pop, files) in groups.items():
        print(f'  {g:32} {pop:14} {files}')
    rows = []
    for g, (pop, files) in groups.items():
        kind = DATASET_KIND.get(pop, 'carrier_est')
        for fname in files:
            path = os.path.join(POP_DIR[pop], fname + '.iq')
            gt, iq, f_hat, est = _load(path)
            conds = [('A_original', None, None, None),
                     ('C_zero_correction', 'zero', 0.0, np.zeros(len(iq))),
                     ('B_estimator_exact', 'estimator_exact', 1.0, f_hat),
                     ('D_E_F_controlled', 'estimator_scaled', 0.1,
                      correction('estimator_scaled', 0.1, len(iq), f_hat, est['est_mean'])),
                     ('D_E_F_controlled', 'estimator_scaled', 1.0,
                      correction('estimator_scaled', 1.0, len(iq), f_hat, est['est_mean']))]
            for arm, shape, m, f_corr in conds:
                row = _measure('secondary', g, path, gt, kind, arm, shape, m, iq, f_corr, est)
                rows.append(row)
                print(f'  {g:30} {fname:22} {arm:20} m={str(m):5} {row["status"]:15} '
                      f'margin {row["f4_margin"]:+8.3f} outcome {row["outcome"]}')
    with open(ROWS, 'a', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r) + '\n')
    print(f'{len(rows)} secondary analyses appended -> {ROWS}')


# ---------------------------------------------------------------- report
def _sha256(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def report():
    rows = [json.loads(l) for l in open(ROWS, encoding='utf-8')]
    print(f'\nSPACE-CARRIER-EST-DIAG-01 — {len(rows)} analyses; criteria sha256 '
          f'{_sha256(CRITERIA)[:16]}…')
    print('margin = F4 best_log10_p − bar (eval/ladder.py:65); NEGATIVE = accepted\n')

    prim = [r for r in rows if r['case'] == 'primary']
    a = next(r for r in prim if r['arm'] == 'A_original')
    c = next(r for r in prim if r['arm'] == 'C_zero_correction')
    b = next(r for r in prim if r['arm'] == 'B_estimator_exact')

    print('PRIMARY — idle_carrier_0411 (ground truth: REFUSAL, so any DECODED is a false accept)')
    for label, r in (('A original', a), ('C zero via the same path', c), ('B estimator exact', b)):
        print(f'  {label:26} margin {r["f4_margin"]:+8.3f}  accepted {str(r["f4_accepted"]):5}  '
              f'{r["status"]:15} {str(r["final_code"])} conv {r["n_converged"]}/{r["n_codewords"]}')
    same = all(a[k] == c[k] for k in ('f4_best', 'f4_bar', 'f4_accepted', 'status', 'final_code',
                                      'n_front_ends', 'M_F1', 'M_F4'))
    print(f'  ZERO CONTROL identical to arm A on every compared field: {same}')

    print('\nF4 MARGIN vs CORRECTION MAGNITUDE (primary; * = accepted)')
    print('  shape            ' + ''.join(f'{"m=" + str(m):>12}' for m in MULTIPLIERS))
    for shape in SHAPES:
        cells = []
        for m in MULTIPLIERS:
            r = next((x for x in prim if x['shape'] == shape and x['m'] == m), None)
            cells.append('—' if r is None else
                         f'{r["f4_margin"]:+.3f}{"*" if r["f4_accepted"] else ""}')
        print(f'  {shape:17}' + ''.join(f'{v:>12}' for v in cells))

    print('\nACCEPTANCE TRANSITION (smallest m at which F4 accepts, per shape)')
    for shape in SHAPES:
        acc = sorted(x['m'] for x in prim if x['shape'] == shape and x['f4_accepted'])
        print(f'  {shape:17} {"none" if not acc else acc[0]}   accepted at m in '
              f'{sorted(set(acc)) if acc else "[]"}')

    print('\nCODEWORD CONVERGENCE among accepting cells (primary)')
    acc_rows = [x for x in prim if x['f4_accepted']]
    for r in acc_rows:
        print(f'  {str(r["shape"]):17} m={str(r["m"]):5} {r["f4_code"]} ({r["f4_family"]}) '
              f'converged {r["n_converged"]}/{r["n_codewords"]}  margin {r["f4_margin"]:+.3f}  '
              f'published {r["final_code"]} / {r["final_modulation"]}')
    if not acc_rows:
        print('  none')

    sec = [r for r in rows if r['case'] == 'secondary']
    if sec:
        print('\nSECONDARY CASES')
        for g in sorted({r['group'] for r in sec}):
            print(f'  {g}')
            for fname in sorted({r['file'] for r in sec if r['group'] == g}):
                for r in [x for x in sec if x['group'] == g and x['file'] == fname]:
                    tag = r['arm'] + (f'/{r["shape"]} m={r["m"]}'
                                      if r['arm'] == 'D_E_F_controlled' else '')
                    print(f'    {fname:22} {tag:34} {r["status"]:15} '
                          f'margin {r["f4_margin"]:+8.3f} outcome {r["outcome"]:14} '
                          f'payload_ok {r["payload_correct"]}')
    print(f'\nstructural false accepts across all analyses: '
          f'{sum(1 for r in rows if not r["structure_correct"])}')


def demo():
    """Self-checks on the correction shapes. No engine calls."""
    n, scale = 1000, 5.838611e-03
    f_hat = scale + 1e-5 * np.sin(np.linspace(0, 6, n))
    assert np.allclose(correction('constant', 1.0, n, f_hat, scale), scale)
    lin = correction('linear_mean', 1.0, n, f_hat, scale)
    assert np.isclose(np.mean(lin), scale, rtol=1e-3) and np.ptp(lin) > 0
    ps = correction('pass_mean', 1.0, n, f_hat, scale)
    assert np.isclose(np.mean(ps), scale, rtol=1e-2) and np.ptp(ps) > 0
    # estimator_scaled at m=1 IS the estimator's own trajectory
    assert np.array_equal(correction('estimator_scaled', 1.0, n, f_hat, scale), f_hat)
    vo = correction('varying_only', 1.0, n, f_hat, scale)
    assert abs(np.mean(vo)) < 1e-12 and np.ptp(vo) > 0      # no constant term
    # zero correction through the real path is an exact identity
    rng = np.random.RandomState(0)
    iq = rng.standard_normal(n) + 1j * rng.standard_normal(n)
    assert np.array_equal(mech._derotate(iq, np.zeros(n)), iq)
    assert len(SHAPES) == 5 and len(MULTIPLIERS) == 7
    print('demo: correction shapes and the zero-correction identity self-checks pass')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'demo'
    os.chdir(ROOT)
    {'primary': primary, 'secondary': secondary, 'report': report, 'demo': demo}[cmd]()
