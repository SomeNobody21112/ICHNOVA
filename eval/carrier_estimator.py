"""SPACE-CARRIER-EST-01 — does the blind carrier estimator survive contact with the rest of ICHNOVA?

Criteria: `eval/carrier_estimator_criteria.json`, committed before this file existed and before any
vector was generated. Arms: **A** the unmodified production engine, **B** the candidate estimator as a
pre-correction, **C** ideal ground-truth correction (a diagnostic ceiling that can never ship).

The estimator is **imported** from `eval/space_doppler_mech.py` (MECH-01 arm D), not reimplemented, so
its identity and every knob are structural and cannot drift. The generator is imported from the same
module, so the signal family is identical to both prior experiments.

Nothing under `src/`, `server/`, `frontend/` or `deploy/` is modified. The regression half reads
bench-v1, bench-v2, the null set and the real-signal recordings **read-only**; the single write outside
this experiment's own namespace is the one authorised append to bench-v2's access log.

    python eval/carrier_estimator.py generate      # 288 captures, seeds 700000-700287 (guarded)
    python eval/carrier_estimator.py run           # 864 analyses (arms A/B/C)
    python eval/carrier_estimator.py regress bench1|bench2|nullset|realsig     # arms A and B
    python eval/carrier_estimator.py report
    python eval/carrier_estimator.py verify
"""

import glob
import hashlib
import json
import os
import sys
import time
from collections import Counter
from multiprocessing import Pool

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, os.path.join(ROOT, 'server'))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding='utf-8')

import bench2                                              # noqa: E402  (scoring + access log, verbatim)
import f4_margin as f4m                                    # noqa: E402  (corrected regression scoring)
import space_doppler_mech as mech                          # noqa: E402  (estimator + generator, verbatim)
from bench2 import _ber                                    # noqa: E402
from modem import load_iq, save_iq                         # noqa: E402
from pipeline import analyze_iq                            # noqa: E402

CRITERIA = os.path.join(HERE, 'carrier_estimator_criteria.json')
MANIFEST = os.path.join(HERE, 'carrier_estimator_manifest.json')
OUT = os.path.join('data', 'space_bench', 'carrier_est')
ROWS = os.path.join('results', 'carrier_est_rows.jsonl')
REG_ROWS = os.path.join('results', 'carrier_est_regression_rows.jsonl')

SEED0 = 700000
ARMS = ('A_production', 'B_candidate', 'C_ideal')
TRAJECTORIES = mech.TRAJECTORIES                           # static, linear, pass
TREATED = mech.TREATED                                     # linear, pass
SEVERITY = mech.SEVERITY                                   # 0.04 .. 1.0 x CFO_MAX
LENGTHS = mech.LENGTHS                                     # n_info: short 200 -> 412 sym, long 594 -> 1200
LENGTH_SYMBOLS = mech.LENGTH_SYMBOLS
ESN0_DB = mech.ESN0_DB                                     # 12, 6
REPS = 4                                                   # the one grid difference from MECH-01
KNOTS_EXPECTED = mech.D_BLOCKS                             # 8
WORKERS = min(max(1, (os.cpu_count() or 2) - 1), 8)
REAL_DIR = os.path.join(ROOT, 'recordings', 'real')
REALSIG_RECORDINGS = ('jjy40-japan-2026-09-17', 'dcf77-france-2026-09-17', 'msf-uk-2026-09-17',
                      'wwv-10mhz-montana-2026-09-17', 'wwvb-montana-2026-09-17',
                      'ddh47-denmark-2026-09-17', 'air-chennai-720-bangalore-2026-09-17')
CATS = ('CORRECT_STRUCTURE_CORRECT_PAYLOAD', 'CORRECT_STRUCTURE_WRONG_PAYLOAD',
        'WRONG_STRUCTURE', 'REFUSED')
SHORT = {CATS[0]: 'correct', CATS[1]: 'WRONG', CATS[2]: 'struct', CATS[3]: 'refused'}


# ---------------------------------------------------------------- job list (pure function)
def jobs():
    out = []
    for cls in TRAJECTORIES:
        for sev in SEVERITY:
            for length in LENGTHS:
                for esn0 in ESN0_DB:
                    for rep in range(REPS):
                        out.append((cls, {'severity': sev, 'length': length, 'esn0': esn0,
                                          'rep': rep}))
    return [(i, cls, p) for i, (cls, p) in enumerate(out)]


def _paths(index, cls):
    base = os.path.join(OUT, f'{cls}_{index:04d}')
    return base + '.iq', base + '.iq.gt.json'


# ---------------------------------------------------------------- generation (mech._make, verbatim)
def _gen_one(job):
    index, cls, params = job
    iq, gt = mech._make(cls, params, np.random.RandomState(SEED0 + index))
    gt.update(index=index, seed=SEED0 + index, experiment='SPACE-CARRIER-EST-01')
    iq_path, gt_path = _paths(index, cls)
    save_iq(iq_path, iq)
    with open(gt_path, 'w', encoding='utf-8') as f:
        json.dump(gt, f)
    return os.path.basename(iq_path), len(iq)


def generate():
    if os.path.exists(MANIFEST) and '--force' not in sys.argv:
        sys.exit(f'refusing to regenerate: {MANIFEST} exists. A new experiment gets a new namespace; '
                 f'--force only to repair a lost dataset (`verify` then confirms it byte-identical).')
    os.makedirs(OUT, exist_ok=True)
    for old in glob.glob(os.path.join(OUT, '*')):
        os.remove(old)
    js = jobs()
    with Pool(WORKERS) as pool:
        made = pool.map(_gen_one, js, chunksize=4)
    print(f'generated {len(made)} captures in {OUT} '
          f'({sum(n for _, n in made) / 1e6:.1f} M samples, seeds {SEED0}–{SEED0 + len(js) - 1})')
    manifest()


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def manifest(write=True):
    files = sorted(glob.glob(os.path.join(OUT, '*.iq')))
    entries = {os.path.basename(p): _sha256_file(p) for p in files}
    lines = '\n'.join(f'{k} {v}' for k, v in sorted(entries.items()))
    m = {'experiment': 'SPACE-CARRIER-EST-01', 'n_files': len(entries), 'files': entries,
         'manifest_sha256': hashlib.sha256(lines.encode()).hexdigest(),
         'generator': 'eval/carrier_estimator.py (transmitter: space_doppler_mech._make)',
         'seed0': SEED0, 'criteria_sha256': _sha256_file(CRITERIA)}
    if write:
        with open(MANIFEST, 'w', encoding='utf-8') as f:
            json.dump(m, f, indent=1)
        print(f"wrote {MANIFEST}: {m['n_files']} files, manifest hash {m['manifest_sha256'][:16]}…")
    return m


def _regen_hash(job):
    index, cls, params = job
    iq, _ = mech._make(cls, params, np.random.RandomState(SEED0 + index))
    out = np.zeros(2 * len(iq), dtype=np.float32)
    out[0::2], out[1::2] = np.real(iq), np.imag(iq)
    return os.path.basename(_paths(index, cls)[0]), hashlib.sha256(out.tobytes()).hexdigest()


def verify():
    if not os.path.exists(MANIFEST):
        sys.exit('no manifest — generate first')
    committed = json.load(open(MANIFEST, encoding='utf-8'))['files']
    with Pool(WORKERS) as pool:
        regen = dict(pool.map(_regen_hash, jobs(), chunksize=4))
    differ = sorted(k for k in committed if regen.get(k) != committed[k])
    print(f'determinism: {len(committed) - len(differ)}/{len(committed)} files byte-identical'
          + (f' — DIFFER: {differ[:5]}' if differ else ''))
    return not differ


# ---------------------------------------------------------------- the arms
def apply_arm(iq, arm, gt=None):
    """(iq, estimator diagnostics). Arm A passes through; B pre-corrects blindly; C uses the oracle."""
    if arm == 'A_production':
        return iq, {'knots': None, 'rmse': None, 'estimator_degraded': None}
    if arm == 'C_ideal':
        if gt is None:
            raise ValueError('arm C needs ground truth')
        return (mech._derotate(iq, mech.true_trajectory(gt)),
                {'knots': None, 'rmse': None, 'estimator_degraded': None})
    f_hat, knots = mech.estimate_trajectory(iq)             # MECH-01 arm D, imported verbatim
    rmse = None
    if gt is not None:
        f_true = mech.true_trajectory(gt)
        n = min(len(f_hat), len(f_true))
        rmse = float(np.sqrt(np.mean((f_hat[:n] - f_true[:n]) ** 2)))
    return mech._derotate(iq, f_hat), {'knots': knots, 'rmse': rmse,
                                       'estimator_degraded': knots < KNOTS_EXPECTED}


def _families(r):
    """Per-family hypothesis multiplicity M and bar — the integration-cost metric (criteria)."""
    out = {}
    for fam in r['accept']['families']:
        key = fam['name'].split('_')[0]
        out[f'M_{key}'] = fam['tested_hypotheses']
        out[f'bar_{key}'] = fam['log10_threshold']
    return out


def _f4(r):
    f4 = r.get('block_code') or {}
    a4 = f4.get('accepted_hypothesis') or {}
    conv = a4.get('converged_codewords')
    best, bar = f4.get('best_log10_p'), f4.get('log10_threshold')
    return {'f4_best': best, 'f4_bar': bar,
            'f4_margin': None if (best is None or bar is None) else float(best - bar),
            'f4_accepted': bool(f4.get('accepted')), 'f4_code': a4.get('code'),
            'f4_family': a4.get('family'), 'n_codewords': a4.get('n_codewords'),
            'n_converged': None if conv is None else int(sum(conv)),
            'zero_convergence': None if conv is None else bool(sum(conv) == 0)}


# ---------------------------------------------------------------- new-vector run
def _run_one(job):
    path, arm = job
    gt = json.load(open(path + '.gt.json', encoding='utf-8'))
    iq, est = apply_arm(load_iq(path), arm, gt)
    t = time.perf_counter()
    r = analyze_iq(iq)
    runtime = time.perf_counter() - t
    outcome, note = mech.score(gt, r)                      # MECH-01 scoring, verbatim
    f2 = r.get('stream_code') or {}
    return {'file': os.path.basename(path)[:-3], 'arm': arm,
            'trajectory': gt['trajectory_class'], 'severity': gt['severity'],
            'peak': gt['peak_shift_cyc_per_sample'],
            'max_drift_rate': gt['max_drift_rate_cyc_per_sample2'],
            'length': gt['length'], 'n_symbols': gt['n_symbols'], 'esn0_db': gt['esn0_db'],
            'rep': gt['rep'], 'seed': gt['seed'],
            'outcome': outcome, 'note': note, 'status': r['status'],
            'ber': _ber(r['payload_bits'], gt['payload_bits']),
            'code_correct': bool((r['code'] or '').endswith('_continuous')),
            'modulation_correct': r['modulation'] == gt['modulation'],
            'true_sps': gt['sps'], 'est_sps': r['sps'],
            'est_code': r['code'], 'est_modulation': r['modulation'],
            'f2_accepted': bool(f2.get('accepted')),
            'n_front_ends': r['diagnostics']['n_front_ends'],
            'phase_tracked_front_ends': r['diagnostics']['phase_tracked_front_ends'],
            **_f4(r), **_families(r), **est, 'runtime': runtime}


def run():
    paths = sorted(glob.glob(os.path.join(OUT, '*.iq')))
    if not paths:
        sys.exit(f'no captures in {OUT} — generate first')
    js = [(p, arm) for p in paths for arm in ARMS]
    print(f'{len(paths)} captures x {len(ARMS)} arms = {len(js)} analyses; {WORKERS} workers')
    os.makedirs('results', exist_ok=True)
    t0 = time.perf_counter()
    rows = []
    with Pool(WORKERS) as pool, open(ROWS, 'w', encoding='utf-8') as f:
        for i, row in enumerate(pool.imap_unordered(_run_one, js, chunksize=2)):
            f.write(json.dumps(row) + '\n')
            rows.append(row)
            if (i + 1) % 150 == 0:
                print(f'{i + 1}/{len(js)}', flush=True)
    print(f'{len(rows)} analyses in {time.perf_counter() - t0:.0f}s -> {ROWS}')
    for arm in ARMS:
        print(f'  {arm:14} {dict(Counter(r["outcome"] for r in rows if r["arm"] == arm))}')


# ---------------------------------------------------------------- regression half (arms A and B)
REG_POPS = {'bench1': ('bench1_sealed', os.path.join('data', 'sealed'), 'bench1'),
            'bench2': ('bench2_sealed', os.path.join('data', 'bench2', 'sealed'), 'bench2'),
            'nullset': ('nullset', os.path.join('data', 'nullset'), 'nullset')}


def _reg_one(job):
    dataset, path, kind, arm = job
    gt = json.load(open(path + '.gt.json', encoding='utf-8'))
    iq, est = apply_arm(load_iq(path), arm)                # no ground-truth trajectory exists here
    t = time.perf_counter()
    r = analyze_iq(iq)
    runtime = time.perf_counter() - t
    outcome, correct = f4m._correct(kind, gt, r)           # the CORRECTED taxonomy, imported
    return {'population': dataset, 'file': os.path.basename(path)[:-3], 'arm': arm,
            'cls': gt.get('class'), 'family': gt.get('family'), 'expected': gt.get('expected'),
            'channel': gt.get('channel'),
            'esn0_db': gt.get('esn0_db', (gt.get('params') or {}).get('esn0', gt.get('snr_db'))),
            'outcome': outcome, 'correct': correct, 'status': r['status'],
            'est_code': r['code'], 'est_modulation': r['modulation'],
            'est_interleaver': list(r['interleaver'] or []) or None,
            **_f4(r), **_families(r), **est, 'runtime': runtime}


def regress(pop):
    if pop == 'realsig':
        return regress_realsig()
    if pop not in REG_POPS:
        sys.exit(f'unknown population {pop!r}; one of {list(REG_POPS) + ["realsig"]}')
    dataset, d, kind = REG_POPS[pop]
    paths = sorted(glob.glob(os.path.join(d, '*.iq')))
    if not paths:
        sys.exit(f'no captures in {d}')
    js = [(dataset, p, kind, arm) for p in paths for arm in ('A_production', 'B_candidate')]
    print(f'{dataset}: {len(paths)} captures x 2 arms = {len(js)} analyses (READ-ONLY)')
    os.makedirs('results', exist_ok=True)
    t0 = time.perf_counter()
    rows = []
    with Pool(WORKERS) as pool, open(REG_ROWS, 'a', encoding='utf-8') as f:
        for i, row in enumerate(pool.imap_unordered(_reg_one, js, chunksize=4)):
            f.write(json.dumps(row) + '\n')
            rows.append(row)
            if (i + 1) % 300 == 0:
                print(f'{i + 1}/{len(js)}', flush=True)
    elapsed = time.perf_counter() - t0
    print(f'{len(rows)} analyses in {elapsed:.0f}s -> {REG_ROWS}')
    for arm in ('A_production', 'B_candidate'):
        print(f'  {arm:14} {dict(Counter(r["outcome"] for r in rows if r["arm"] == arm))}')
    if pop == 'bench2':
        _bench2_criteria(rows)
        _log_bench2_access(rows, elapsed)


def _bench2_rows(rows, arm):
    """bench-v2's own row shape, in memory only, so its criterion evaluator can be reused verbatim."""
    return [{'class': r['cls'], 'family': r['family'], 'expected': r['expected'],
             'esn0_db': r['esn0_db'], 'outcome': r['outcome'], 'status': r['status']}
            for r in rows if r['arm'] == arm]


def _bench2_criteria(rows):
    criteria = json.load(open(os.path.join(HERE, 'bench2_criteria.json'), encoding='utf-8'))
    criteria = criteria.get('criteria', criteria)
    print('\nbench-v2 9 pre-registered criteria, evaluated in memory (bench2._evaluate_criterion):')
    summary = {}
    for arm in ('A_production', 'B_candidate'):
        br = _bench2_rows(rows, arm)
        verdicts = {}
        for name, c in criteria.items():
            detail, verdict = bench2._evaluate_criterion(c, br)
            verdicts[name] = verdict
            print(f'  {arm:14} {name:44} {verdict:4}  {detail}')
        summary[arm] = sum(1 for v in verdicts.values() if v == 'PASS')
        print(f'  {arm:14} -> {summary[arm]}/{len(verdicts)} PASS')
    return summary


def _log_bench2_access(rows, elapsed):
    """The ONE authorised access-log entry, written with bench-v2's own writer (exact format)."""
    committed = json.load(open(os.path.join(HERE, 'bench2_sealed_manifest.json'), encoding='utf-8'))
    entry = {'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
             'commit': bench2._commit(), 'split': 'sealed', 'n_files': len(rows) // 2,
             'manifest_sha256': committed['manifest_sha256'],
             'criteria_sha256': _sha256_file(CRITERIA),
             'higher_modulations': False,
             'outcomes': {arm: dict(Counter(r['outcome'] for r in rows if r['arm'] == arm))
                          for arm in ('A_production', 'B_candidate')},
             'runtime_s': round(elapsed, 1),
             'experiment': 'SPACE-CARRIER-EST-01',
             'purpose': 'read-only re-analysis of the sealed split under arm A (production engine) and '
                        'arm B (candidate blind carrier pre-correction) to measure the static-carrier '
                        'regression cost of the estimator. No bench-v2 vector, manifest, criteria file '
                        'or original result was modified; bench-v2 criteria were evaluated in memory.',
             'arms': ['A_production', 'B_candidate'], 'read_only': True}
    bench2._log_access(entry)
    print(f'\nappended ONE access entry to {bench2.ACCESS_LOG} (experiment SPACE-CARRIER-EST-01)')


def regress_realsig():
    """The real-signal regression: the same recordings and the same call tests/test_realsig.py makes."""
    import realsig
    from make_recording import load_recording
    out_rows = []
    for rec_id in REALSIG_RECORDINGS:
        if not os.path.exists(os.path.join(REAL_DIR, rec_id + '.wav')):
            print(f'  {rec_id}: recording absent — skipped')
            continue
        iq, meta = load_recording(rec_id)
        c = meta['capture']
        for arm in ('A_production', 'B_candidate'):
            x, est = apply_arm(np.asarray(iq), arm)
            t = time.perf_counter()
            out, _ = realsig.analyze_capture(x, c['fs_hz'], c['t0_unix'], c['timing'], 0.0)
            runtime = time.perf_counter() - t
            a = out['answer']
            runs = out['runs']
            fk, am = runs.get('fsk') or {}, runs.get('am') or {}
            row = {'population': 'realsig', 'file': rec_id, 'arm': arm,
                   'status': a['status'], 'protocol': a.get('protocol'),
                   'timing': (a.get('verification') or {}).get('timing'),
                   'arrival_minus_decoded_ms': (a.get('verification') or {}).get(
                       'arrival_minus_decoded_ms'),
                   'timecode_protocol': (runs.get('timecode') or {}).get('protocol'),
                   'fsk_status': fk.get('status'), 'fsk_baud': fk.get('baud'),
                   'fsk_code': fk.get('code'),
                   'fsk_text_has_callsign': bool(fk.get('text') and 'DE DDH47' in fk['text']),
                   'fsk_measured_shift_hz': fk.get('measured_shift_hz'),
                   'am_carrier_to_noise_db': am.get('carrier_to_noise_db'),
                   'am_carrier_offset_hz': am.get('carrier_offset_hz'),
                   **est, 'runtime': runtime}
            out_rows.append(row)
            print(f"  {rec_id:42} {arm:14} {str(row['status']):16} protocol "
                  f"{str(row['protocol']):6} knots {row['knots']}")
    with open(REG_ROWS, 'a', encoding='utf-8') as f:
        for r in out_rows:
            f.write(json.dumps(r) + '\n')
    print(f'{len(out_rows)} real-signal analyses -> {REG_ROWS}')


# ---------------------------------------------------------------- reporting
def _rows(path):
    if not os.path.exists(path):
        sys.exit(f'missing {path} — run the corresponding step first')
    return [json.loads(l) for l in open(path, encoding='utf-8')]


def _rate(rs, cat):
    return sum(1 for r in rs if r['outcome'] == cat) / len(rs) if rs else float('nan')


def _line(label, rs):
    c = Counter(r['outcome'] for r in rs)
    return (f'{label:30} n={len(rs):4}  ' + '  '.join(f'{SHORT[k]} {c[k]:4}' for k in CATS)
            + f'   correct {_rate(rs, CATS[0]):.3f}  WRONG-payload {_rate(rs, CATS[1]):.3f}'
              f'  refused {_rate(rs, CATS[3]):.3f}')


def report():
    rows = _rows(ROWS)
    reg = _rows(REG_ROWS) if os.path.exists(REG_ROWS) else []
    crit = json.load(open(CRITERIA, encoding='utf-8'))
    print(f'\nSPACE-CARRIER-EST-01 — {len(rows)} new-vector analyses, {len(reg)} regression analyses')
    print(f'criteria sha256 {_sha256_file(CRITERIA)[:16]}…  manifest '
          f'{json.load(open(MANIFEST, encoding="utf-8"))["manifest_sha256"][:16]}…')
    print('margin convention: F4 best_log10_p − bar (eval/ladder.py:65); negative = accepted\n')

    treated = [r for r in rows if r['trajectory'] in TREATED]
    static = [r for r in rows if r['trajectory'] == 'static']

    print('ARM COMPARISON — treated captures (linear + pass), n=192 per arm')
    for arm in ARMS:
        print('  ' + _line(arm, [r for r in treated if r['arm'] == arm]))
    print('\nARM COMPARISON — static captures, n=96 per arm')
    for arm in ARMS:
        print('  ' + _line(arm, [r for r in static if r['arm'] == arm]))

    for factor, values in (('trajectory', TREATED), ('severity', SEVERITY),
                           ('length', tuple(LENGTHS)), ('esn0_db', ESN0_DB)):
        print(f'\nTIME-VARYING BY {factor.upper()} (treated)')
        for v in values:
            for arm in ARMS:
                sel = [r for r in treated if r[factor] == v and r['arm'] == arm]
                print('  ' + _line(f'{factor}={v} / {arm}', sel))

    print('\nSTRUCTURAL SAFETY')
    for arm in ARMS:
        rs = [r for r in rows if r['arm'] == arm]
        m = [r['f4_margin'] for r in rs if r['f4_margin'] is not None]
        acc = [r for r in rs if r['f4_accepted']]
        zc = [r for r in rs if r['zero_convergence']]
        ws = [r for r in rs if r['outcome'] == 'WRONG_STRUCTURE']
        print(f'  {arm:14} wrong structures {len(ws):3}  F4 accepts {len(acc):3}  '
              f'zero-convergence accepts {len(zc):3}  min F4 margin {min(m):+.3f}  '
              f'median {np.median(m):+.3f}')
    print('\n  closest F4 margins per arm (smallest positive = nearest miss):')
    for arm in ARMS:
        rs = sorted((r for r in rows if r['arm'] == arm and r['f4_margin'] is not None
                     and not r['f4_accepted']), key=lambda r: r['f4_margin'])[:3]
        for r in rs:
            print(f"    {arm:14} {r['file']:18} margin {r['f4_margin']:+.3f}  "
                  f"traj {r['trajectory']} sev {r['severity']} {r['length']}")

    print('\nINTEGRATION COST — hypothesis multiplicity M and bars per arm (mean over captures)')
    keys = [k for k in rows[0] if k.startswith('M_') or k.startswith('bar_')]
    for arm in ARMS:
        rs = [r for r in rows if r['arm'] == arm]
        print(f'  {arm:14} ' + '  '.join(
            f'{k}={np.mean([x[k] for x in rs if x[k] is not None]):.4g}' for k in keys))
    for arm in ARMS:
        rs = [r for r in rows if r['arm'] == arm]
        print(f'  {arm:14} front ends mean {np.mean([r["n_front_ends"] for r in rs]):.1f}  '
              f'tracked mean {np.mean([r["phase_tracked_front_ends"] for r in rs]):.1f}')

    print('\nESTIMATOR (arm B, new vectors)')
    b = [r for r in rows if r['arm'] == 'B_candidate']
    cov = sum(1 for r in b if r['knots'] == KNOTS_EXPECTED) / len(b)
    rmse = [r['rmse'] for r in b if r['rmse'] is not None]
    print(f'  coverage (full {KNOTS_EXPECTED}-knot set): {cov:.3f}   knots distribution '
          f'{dict(Counter(r["knots"] for r in b))}')
    print(f'  RMSE vs true trajectory: min {min(rmse):.2e} median {np.median(rmse):.2e} '
          f'max {max(rmse):.2e} cyc/sample  (REPORTED, no bar)')
    for cls in TRAJECTORIES:
        rs = [r for r in b if r['trajectory'] == cls]
        print(f'    {cls:7} RMSE median {np.median([r["rmse"] for r in rs]):.2e}  '
              f'degraded {sum(1 for r in rs if r["estimator_degraded"])}/{len(rs)}')
    for sev in SEVERITY:
        rs = [r for r in b if r['severity'] == sev and r['trajectory'] in TREATED]
        print(f'    severity {sev:<5} RMSE median {np.median([r["rmse"] for r in rs]):.2e}  '
              f'wrong-payload {_rate(rs, CATS[1]):.3f}')
    deg = [r for r in b if r['estimator_degraded']]
    print(f'  estimator-degraded captures: {len(deg)}  '
          f'outcomes {dict(Counter(r["outcome"] for r in deg))}')

    print('\nRUNTIME')
    for arm in ARMS:
        rt = [r['runtime'] for r in rows if r['arm'] == arm]
        print(f'  {arm:14} mean {np.mean(rt):.3f}s  max {max(rt):.2f}s')
    ma = np.mean([r['runtime'] for r in rows if r['arm'] == 'A_production'])
    mb = np.mean([r['runtime'] for r in rows if r['arm'] == 'B_candidate'])
    print(f'  ratio B/A = {mb / ma:.2f}x  (bar <= 3x)')

    if reg:
        print('\nSTATIC REGRESSION (arms A and B, read-only populations)')
        for pop in ('bench1_sealed', 'bench2_sealed', 'nullset', 'realsig'):
            rs = [r for r in reg if r['population'] == pop]
            if not rs:
                continue
            for arm in ('A_production', 'B_candidate'):
                sel = [r for r in rs if r['arm'] == arm]
                if pop == 'realsig':
                    for r in sel:
                        print(f"  realsig {arm:14} {r['file']:42} {str(r['status']):16} "
                              f"protocol {str(r['protocol']):6} knots {r['knots']}")
                else:
                    print(f'  {pop:14} {arm:14} {dict(Counter(r["outcome"] for r in sel))}')
        ns = [r for r in reg if r['population'] == 'nullset']
        if ns:
            for arm in ('A_production', 'B_candidate'):
                tn = [r for r in ns if r['arm'] == arm
                      and r['cls'] in ('noise', 'uncoded_bpsk', 'uncoded_qpsk', '8psk_k7')]
                cat = [r for r in ns if r['arm'] == arm and r['cls'] in ('k7', 'k5', 'k3')]
                print(f'  nullset {arm:14} TRUE NULLS n={len(tn)} DECODED='
                      f'{sum(1 for r in tn if r["status"] == "DECODED")}  '
                      f'CATALOGUE n={len(cat)} correct={sum(1 for r in cat if r["correct"])}')
    print(f'\n({len(crit["acceptance_criteria"])} pre-registered criterion families; verdicts are '
          'computed in CARRIER_ESTIMATOR_RESULTS.md from these tables)')


def demo():
    """Self-checks on the arms and the grid. No engine calls."""
    js = jobs()
    assert len(js) == 288 and len(js) * len(ARMS) == 864
    assert len({i for i, _, _ in js}) == 288
    assert SEED0 == 700000 and SEED0 != mech.SEED0
    assert REPS == 4 and SEVERITY == (0.04, 0.1, 0.2, 0.4, 0.7, 1.0) and ESN0_DB == (12, 6)
    # the estimator is MECH-01's, by identity not by copy
    assert mech.estimate_trajectory.__module__ == 'space_doppler_mech'
    assert mech.D_BLOCKS == 8
    # arm A is a pass-through; arm C exactly removes the injected trajectory
    gt = {'trajectory_class': 'pass', 'peak_shift_cyc_per_sample': 0.01, 'n_samples': 256,
          'modulation': 'BPSK', 'payload_bits': [0, 1] * 32, 'sps': 4}
    rng = np.random.RandomState(0)
    sig = rng.standard_normal(256) + 1j * rng.standard_normal(256)
    assert np.array_equal(apply_arm(sig, 'A_production')[0], sig)
    f = mech.true_trajectory(gt)
    mixed = mech.sd.apply_trajectory(sig, f)               # space_doppler's definition, via mech
    assert np.allclose(apply_arm(mixed, 'C_ideal', gt)[0], sig, atol=1e-9)
    # arm B is blind: it needs no ground truth and reports its knots
    tone = np.exp(2j * np.pi * 0.004 * np.arange(4096))
    _, est = apply_arm(tone, 'B_candidate')
    assert est['knots'] == KNOTS_EXPECTED and est['estimator_degraded'] is False
    print('demo: grid, estimator identity and arm behaviour self-checks pass')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'demo'
    os.chdir(ROOT)
    if cmd == 'regress':
        regress(sys.argv[2] if len(sys.argv) > 2 else 'bench1')
    else:
        {'generate': generate, 'run': run, 'report': report, 'verify': verify,
         'manifest': manifest, 'demo': demo}[cmd]()
