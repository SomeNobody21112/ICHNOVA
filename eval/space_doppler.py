"""SPACE-DOPPLER — controlled time-varying carrier frequency offset (pre-registered).

Criteria: `eval/space_doppler_criteria.json`, committed before this file generated a single vector.
Namespace: `data/space_bench/doppler`, `results/space_doppler_rows.jsonl`. bench-v2 data, seeds,
criteria and thresholds are never read or written here.

What this measures: the engine's published verdict on a continuous K7 BPSK stream carried by four
frequency trajectories — `zero`, `static`, `linear` (controls) and `pass` (the treatment, a bounded
S-curve, CONTROLLED SYNTHETIC and never to be called a satellite pass). Only the trajectory and the
declared severity/noise/length vary; nothing reads engine internals, so D1/D2/D8 of
DOPPLER_EXPERIMENT_DESIGN.md are out of scope here (see SPACE_IMPLEMENTATION_GATE.md §9.3).

    python eval/space_doppler.py generate
    python eval/space_doppler.py run
    python eval/space_doppler.py report
    python eval/space_doppler.py verify        # determinism: regenerate, compare hashes
"""

import glob
import hashlib
import json
import os
import sys
import time
from collections import Counter, defaultdict
from multiprocessing import Pool

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding='utf-8')

import bench2_gen as gen                                   # noqa: E402  (stream_bits / CODES only)
import modem                                               # noqa: E402
from bench2 import _ber                                    # noqa: E402  (FALSE_ACCEPT BER semantics, verbatim)
from modem import load_iq, save_iq                         # noqa: E402
from pipeline import CFO_MAX, TRACK_MIN_SYMBOLS, analyze_iq  # noqa: E402

SEED0 = 500000
OUT = os.path.join('data', 'space_bench', 'doppler')
CRITERIA = os.path.join(HERE, 'space_doppler_criteria.json')
MANIFEST = os.path.join(HERE, 'space_doppler_manifest.json')
ROWS = os.path.join('results', 'space_doppler_rows.jsonl')

CLASSES = ('zero', 'static', 'linear', 'pass')
CONTROL_CLASSES = ('zero', 'static')
SEVERITY = (0.25, 0.5, 1.0, 2.0)
ESN0_DB = (12, 9, 6)
LENGTHS = {'long': 1200, 'short': 200}          # n_info bits; straddles TRACK_MIN_SYMBOLS
REPS = 2
KAPPA = 4.0                                     # pass-curve sharpness, declared before any run
REFUSAL = ('UNKNOWN', 'SIGNAL_NO_CODE')
RUNTIME_MEAN_MAX = 7.14                         # 3x the bench-v2 sealed mean of 2.38 s
RUNTIME_MAX = 120.0


# ---------------------------------------------------------------- the trajectory (the one new thing)
def trajectory(cls, peak, n, kappa=KAPPA):
    """Instantaneous frequency offset in cycles/sample for each of `n` samples.

    zero   f(t) = 0                                        control
    static f(t) = peak                                     control — the validated static-CFO case
    linear f(t) = -peak + 2*peak*t/T                       control — bench-v2's cfo_drift shape
    pass   f(t) = peak*(2/pi)*arctan(kappa*(2t/T - 1))     treatment — bounded S-curve, SYNTHETIC
    """
    t = np.arange(n) / max(n - 1, 1)
    if cls == 'zero':
        return np.zeros(n)
    if cls == 'static':
        return np.full(n, float(peak))
    if cls == 'linear':
        return -peak + 2.0 * peak * t
    if cls == 'pass':
        return peak * (2.0 / np.pi) * np.arctan(kappa * (2.0 * t - 1.0))
    raise ValueError(cls)


def apply_trajectory(sig, f):
    """Mix by the trajectory: phase is the running integral of f, so a constant f is a pure CFO."""
    return sig * np.exp(2j * np.pi * np.cumsum(f))


# ---------------------------------------------------------------- the job list (pure function)
def jobs():
    out = []
    for cls in CLASSES:
        for sev in SEVERITY:
            for esn0 in ESN0_DB:
                for length in LENGTHS:
                    for rep in range(REPS):
                        out.append((cls, {'severity': sev, 'esn0': esn0, 'length': length,
                                          'rep': rep}))
    return [(i, cls, p) for i, (cls, p) in enumerate(out)]


def _paths(index, cls):
    base = os.path.join(OUT, f'{cls}_{index:04d}')
    return base + '.iq', base + '.iq.gt.json'


# ---------------------------------------------------------------- generation
def _make(cls, params, rng):
    """(iq, ground truth) for one vector. Known everything; the trajectory is the only variable."""
    peak = params['severity'] * CFO_MAX
    n_info = LENGTHS[params['length']]
    sps = int(rng.choice([4, 6, 8]))
    beta = float(rng.uniform(0.2, 0.5))
    bits, info = gen.stream_bits(rng, n_info)
    syms = modem.modulate(bits, 'BPSK')
    sig = modem.pulse_shape(syms, sps, modem.rrc_filter(beta, sps))

    f = trajectory(cls, peak, len(sig))
    sig = apply_trajectory(sig, f)
    # Es/N0 is per symbol at the matched-filter output, exactly as bench-v2 converts it.
    snr_per_sample = params['esn0'] - 10 * np.log10(len(sig) / max(len(syms), 1))
    iq, _ = modem.channel(sig, snr_per_sample, 0.0, 0.0, float(rng.uniform(0, 2 * np.pi)), rng)

    df = np.diff(f)
    return iq, {
        'class': cls, 'params': dict(params), 'trajectory_class': cls, 'kappa': KAPPA,
        'peak_shift_cyc_per_sample': float(peak), 'severity': params['severity'],
        'max_drift_rate_cyc_per_sample2': float(np.max(np.abs(df))) if len(df) else 0.0,
        'outside_search_bound': bool(peak > CFO_MAX),
        'modulation': 'BPSK', 'sps': sps, 'beta': beta, 'code': 'k7_continuous',
        'interleaver': 'none', 'payload_bits': info.tolist(),
        'sample_rate': 'normalised (no absolute fs)', 'esn0_db': params['esn0'],
        'n_symbols': int(len(syms)), 'n_info_bits': int(n_info),
        'tracking_expected': bool(len(syms) >= TRACK_MIN_SYMBOLS),
        'expected': 'DECODED_OR_REFUSAL_NEVER_WRONG',
    }


def _gen_one(job):
    index, cls, params = job
    iq, gt = _make(cls, params, np.random.RandomState(SEED0 + index))
    gt.update(index=index, seed=SEED0 + index)
    iq_path, gt_path = _paths(index, cls)
    save_iq(iq_path, iq)
    with open(gt_path, 'w', encoding='utf-8') as f:
        json.dump(gt, f)
    return os.path.basename(iq_path), len(iq)


def generate():
    # The sealed SPACE-DOPPLER dataset is historical evidence of a failed criterion: regenerating it in place
    # would destroy the artefact the failure analysis rests on. A future experiment gets a new namespace, new
    # criteria and a new experiment ID (reports/space/DOPPLER_REMEDIATION_EXPERIMENT.md), never this one.
    if os.path.exists(MANIFEST) and '--force' not in sys.argv:
        sys.exit(f'refusing to regenerate the sealed dataset: {MANIFEST} exists. Use a new namespace for a '
                 f'new experiment, or --force only to repair a lost dataset (`verify` then confirms it is '
                 f'byte-identical to the committed manifest).')
    os.makedirs(OUT, exist_ok=True)
    for old in glob.glob(os.path.join(OUT, '*')):
        os.remove(old)
    js = jobs()
    with Pool(max(1, (os.cpu_count() or 2) - 1)) as pool:
        made = pool.map(_gen_one, js, chunksize=4)
    print(f'generated {len(made)} files in {OUT} '
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
    m = {'experiment': 'space_doppler', 'n_files': len(entries), 'files': entries,
         'manifest_sha256': hashlib.sha256(lines.encode()).hexdigest(),
         'generator': 'eval/space_doppler.py', 'seed0': SEED0}
    if write:
        with open(MANIFEST, 'w', encoding='utf-8') as f:
            json.dump(m, f, indent=1)
        print(f"wrote {MANIFEST}: {m['n_files']} files, manifest hash {m['manifest_sha256'][:16]}…")
    return m


def _regen_hash(job):
    """sha256 of the bytes generation would write, without touching the dataset on disk."""
    index, cls, params = job
    iq, _ = _make(cls, params, np.random.RandomState(SEED0 + index))
    out = np.zeros(2 * len(iq), dtype=np.float32)          # save_iq's layout, verbatim
    out[0::2], out[1::2] = np.real(iq), np.imag(iq)
    return os.path.basename(_paths(index, cls)[0]), hashlib.sha256(out.tobytes()).hexdigest()


def verify():
    """Determinism criterion: regenerating from the same seeds is byte-identical."""
    if not os.path.exists(MANIFEST):
        sys.exit('no manifest — generate first')
    committed = json.load(open(MANIFEST, encoding='utf-8'))['files']
    with Pool(max(1, (os.cpu_count() or 2) - 1)) as pool:
        regen = dict(pool.map(_regen_hash, jobs(), chunksize=4))
    differ = sorted(k for k in committed if regen.get(k) != committed[k])
    missing = sorted(set(committed) - set(regen)) + sorted(set(regen) - set(committed))
    print(f'determinism: {len(committed) - len(differ)}/{len(committed)} files byte-identical'
          + (f' — DIFFER: {differ[:5]}' if differ else '')
          + (f' — SET MISMATCH: {missing[:5]}' if missing else ''))
    return not differ and not missing


# ---------------------------------------------------------------- running
def _score(gt, r):
    """(outcome, note). DECODED_CORRECT | FALSE_DECODE | REFUSED.

    FALSE_DECODE is bench-v2's FALSE_ACCEPT applied to this experiment: the engine says DECODED
    while the structure, the modulation or the payload is not the transmitted one."""
    if r['status'] != 'DECODED':
        return 'REFUSED', r['status']
    ber = _ber(r['payload_bits'], gt['payload_bits'])
    if not (r['code'] or '').endswith('_continuous'):
        return 'FALSE_DECODE', f"wrong structure: {r['code']}"
    if r['modulation'] != gt['modulation']:
        return 'FALSE_DECODE', f"wrong modulation: {r['modulation']}"
    if ber >= 0.01:
        return 'FALSE_DECODE', f'payload BER {ber:.3f} under a {r["code"]} claim'
    return 'DECODED_CORRECT', r['code']


def _run_one(path):
    gt = json.load(open(path + '.gt.json', encoding='utf-8'))
    t = time.perf_counter()
    r = analyze_iq(load_iq(path))
    runtime = time.perf_counter() - t
    outcome, note = _score(gt, r)
    cands = r['diagnostics']['sps_candidates']
    return {'file': os.path.basename(path)[:-3], 'trajectory': gt['trajectory_class'],
            'severity': gt['severity'], 'peak': gt['peak_shift_cyc_per_sample'],
            'outside_search_bound': gt['outside_search_bound'],
            'max_drift_rate': gt['max_drift_rate_cyc_per_sample2'],
            'esn0_db': gt['esn0_db'], 'length': gt['params']['length'], 'rep': gt['params']['rep'],
            'n_symbols': gt['n_symbols'], 'tracking_expected': gt['tracking_expected'],
            'outcome': outcome, 'note': note, 'status': r['status'],
            'ber': _ber(r['payload_bits'], gt['payload_bits']),
            'true_sps': gt['sps'], 'est_sps': r['sps'], 'sps_in_candidates': gt['sps'] in cands,
            'est_modulation': r['modulation'], 'est_code': r['code'],
            'phase_tracked_front_ends': r['diagnostics']['phase_tracked_front_ends'],
            'runtime': runtime}


def run():
    paths = sorted(glob.glob(os.path.join(OUT, '*.iq')))
    if not paths:
        sys.exit(f'no files in {OUT} — generate first')
    os.makedirs('results', exist_ok=True)
    t0 = time.perf_counter()
    with Pool(max(1, (os.cpu_count() or 2) - 1)) as pool, open(ROWS, 'w', encoding='utf-8') as f:
        rows = []
        for i, row in enumerate(pool.imap_unordered(_run_one, paths, chunksize=2)):
            f.write(json.dumps(row) + '\n')
            rows.append(row)
            if (i + 1) % 25 == 0:
                print(f'{i + 1}/{len(paths)}', flush=True)
    print(f'{len(rows)} files in {time.perf_counter() - t0:.0f}s — '
          f'{dict(Counter(r["outcome"] for r in rows))}')


# ---------------------------------------------------------------- reporting
def _rows():
    if not os.path.exists(ROWS):
        sys.exit(f'no rows at {ROWS} — run first')
    return [json.loads(l) for l in open(ROWS, encoding='utf-8')]


def _migration(rows):
    """Per (trajectory, length, rep) series ordered hardest-last: any DECODED→wrong transition, and
    any non-monotonic cell (a correct decode strictly harder than a refusal in the same series).
    No threshold — the criteria file declares this REPORTED, not PASS/FAIL."""
    series = defaultdict(list)
    for r in rows:
        series[(r['trajectory'], r['length'], r['rep'])].append(r)
    anomalies, wrong_after = [], []
    for key, rs in series.items():
        rs.sort(key=lambda r: (r['severity'], -r['esn0_db']))      # increasing difficulty
        refused_at = None
        for r in rs:
            if r['outcome'] == 'REFUSED' and refused_at is None:
                refused_at = (r['severity'], r['esn0_db'])
            elif r['outcome'] == 'DECODED_CORRECT' and refused_at is not None:
                anomalies.append({'series': key, 'refused_at': refused_at,
                                  'decoded_at': (r['severity'], r['esn0_db'])})
            elif r['outcome'] == 'FALSE_DECODE':
                wrong_after.append({'series': key, 'cell': (r['severity'], r['esn0_db']),
                                    'note': r['note']})
    return len(series), anomalies, wrong_after


def report():
    rows = _rows()
    criteria = json.load(open(CRITERIA, encoding='utf-8'))['criteria']
    n = len(rows)
    print(f'\nSPACE-DOPPLER — {n} vectors, criteria {os.path.basename(CRITERIA)} '
          f'(sha256 {_sha256_file(CRITERIA)[:16]}…)\n')

    # ---- cell table
    print(f'{"traj":7} {"sev":>5} {"Es/N0":>6} {"len":>5}  decoded  refused  FALSE  mean BER')
    cells = defaultdict(list)
    for r in rows:
        cells[(r['trajectory'], r['severity'], r['esn0_db'], r['length'])].append(r)
    for key in sorted(cells):
        rs = cells[key]
        c = Counter(r['outcome'] for r in rs)
        print(f'{key[0]:7} {key[1]:>5} {key[2]:>6} {key[3]:>5}  '
              f'{c["DECODED_CORRECT"]:>7}  {c["REFUSED"]:>7}  {c["FALSE_DECODE"]:>5}  '
              f'{np.mean([r["ber"] for r in rs]):.3f}')

    # ---- criteria, in the order they were pre-registered
    false_decodes = [r for r in rows if r['outcome'] == 'FALSE_DECODE']
    control = [r for r in rows if r['trajectory'] in CONTROL_CLASSES and r['severity'] <= 1.0
               and r['esn0_db'] >= 9 and r['length'] == 'long']
    control_ok = sum(1 for r in control if r['outcome'] == 'DECODED_CORRECT')
    n_series, anomalies, wrong_after = _migration(rows)
    decoded = [r for r in rows if r['status'] == 'DECODED']
    mod_wrong = [r for r in decoded if r['est_modulation'] != 'BPSK']
    runtimes = [r['runtime'] for r in rows]
    verdicts = {}

    def say(name, verdict, detail):
        verdicts[name] = verdict
        print(f'  [{verdict:>9}] {name}: {detail}')

    print('\npre-registered criteria')
    say('no_false_decode_under_trajectory', 'PASS' if not false_decodes else 'FAIL',
        f'{len(false_decodes)} false decodes (required 0)'
        + (f' — {[(r["file"], r["note"]) for r in false_decodes[:5]]}' if false_decodes else ''))
    say('payload_correctness_on_control_cells',
        'PASS' if control and control_ok / len(control) >= 0.80 else 'FAIL',
        f'{control_ok}/{len(control)} control cells decoded with BER < 0.01 (required >= 0.80)')
    say('refusal_migration_direction', 'REPORTED',
        f'{n_series} series; {len(wrong_after)} DECODED→wrong transitions; '
        f'{len(anomalies)} non-monotonic cells (no threshold — NOT ESTABLISHED)')
    say('modulation_consistency', 'PASS' if not mod_wrong else 'FAIL',
        f'{len(mod_wrong)} of {len(decoded)} DECODED carry a wrong modulation (required 0); '
        f'refusal-side modulations: '
        f'{dict(Counter(r["est_modulation"] for r in rows if r["outcome"] == "REFUSED"))}')
    in_cands = sum(1 for r in rows if r['sps_in_candidates'])
    sps_used = sum(1 for r in rows if r['est_sps'] == r['true_sps'])
    ctrl_cands = sum(1 for r in control if r['sps_in_candidates'])
    say('symbol_rate_consistency', 'REPORTED',
        f'true sps in candidates {in_cands}/{n}; accepted front end used true sps {sps_used}/{n}; '
        f'control reference {ctrl_cands}/{len(control)} (bar NOT ESTABLISHED)')
    code_ok = sum(1 for r in rows if (r['est_code'] or '').endswith('_continuous'))
    say('code_consistency', 'REPORTED',
        f'true code family accepted on {code_ok}/{n} vectors (bar NOT ESTABLISHED)')
    say('runtime_guard',
        'PASS' if np.mean(runtimes) <= RUNTIME_MEAN_MAX and max(runtimes) <= RUNTIME_MAX else 'FAIL',
        f'mean {np.mean(runtimes):.2f}s (<= {RUNTIME_MEAN_MAX}), '
        f'max {max(runtimes):.1f}s (<= {RUNTIME_MAX:.0f})')
    print('  [  SEPARATE] determinism: `verify`;  '
          'existing_regression_unchanged: pytest + sealed_test.py')

    # ---- Q8: does the existing tracking materially help? Behavioural, no internals.
    print('\nQ8 — tracking, measured behaviourally across TRACK_MIN_SYMBOLS '
          f'({TRACK_MIN_SYMBOLS} symbols)')
    for length in ('long', 'short'):
        for cls in CLASSES:
            rs = [r for r in rows if r['length'] == length and r['trajectory'] == cls]
            c = Counter(r['outcome'] for r in rs)
            tracked = sum(1 for r in rs if r['phase_tracked_front_ends'] > 0)
            print(f'  {length:5} {cls:7} n={len(rs):3}  decoded {c["DECODED_CORRECT"]:>3}  '
                  f'refused {c["REFUSED"]:>3}  false {c["FALSE_DECODE"]:>3}  '
                  f'tracked front ends present in {tracked}/{len(rs)}')

    for c in verdicts:
        assert criteria.get(c), f'{c} is not in the pre-registration'          # no invented criteria
    unmet = [k for k, v in verdicts.items() if v == 'FAIL']
    print(f'\n{len(unmet)} criterion failures' + (f': {unmet} — STOP rule applies' if unmet else ''))
    return verdicts


def demo():
    """Self-check on the one piece of non-trivial logic this file adds: the trajectory."""
    n, peak = 1000, 0.01
    assert np.all(trajectory('zero', peak, n) == 0.0)
    assert np.all(trajectory('static', peak, n) == peak)
    lin = trajectory('linear', peak, n)
    assert np.isclose(lin[0], -peak) and np.isclose(lin[-1], peak) and np.all(np.diff(lin) > 0)
    p = trajectory('pass', peak, n)
    assert np.all(np.diff(p) > 0), 'the pass curve is monotonic'
    assert np.max(np.abs(p)) < peak, 'arctan is bounded strictly inside the peak'
    assert np.isclose(p[0], -p[-1]) and abs(p[n // 2]) < 0.01 * peak, 'the curve is antisymmetric'
    assert np.max(np.abs(np.diff(p))) > np.max(np.abs(np.diff(lin))), 'the S-curve drifts faster'
    # a constant trajectory is exactly a static CFO
    sig = np.ones(64, dtype=complex)
    ref = sig * np.exp(2j * np.pi * peak * (np.arange(64) + 1))
    assert np.allclose(apply_trajectory(sig, trajectory('static', peak, 64)), ref)
    # generation is a pure function of the seed
    a = _make('pass', {'severity': 1.0, 'esn0': 9, 'length': 'short', 'rep': 0},
              np.random.RandomState(SEED0))[0]
    b = _make('pass', {'severity': 1.0, 'esn0': 9, 'length': 'short', 'rep': 0},
              np.random.RandomState(SEED0))[0]
    assert np.array_equal(a, b)
    assert len(jobs()) == len(CLASSES) * len(SEVERITY) * len(ESN0_DB) * len(LENGTHS) * REPS == 192
    print('demo: trajectory, mixing and generation self-checks pass')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'demo'
    os.chdir(ROOT)
    {'generate': generate, 'run': run, 'report': report, 'verify': verify, 'demo': demo}[cmd]()
