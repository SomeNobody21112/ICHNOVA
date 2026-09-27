"""SPACE-DOPPLER-MECH-01 — mechanism diagnostic for the sealed SPACE-DOPPLER payload failure.

Criteria: `eval/space_doppler_mech_criteria.json`, committed before this file existed.
Namespace: `data/space_bench/doppler_mech`, `results/space_doppler_mech_rows.jsonl`.
The sealed SPACE-DOPPLER dataset, bench-v1, bench-v2 and the null set are never read or written here;
the only thing shared with the sealed experiment is the trajectory definition it declared.

The question: WHY does a correct structural claim carry a wrong payload under a moving carrier? Four
arms analyse byte-identical captures — A no tracking, B today's engine, C ideal ground-truth carrier
correction, D a declared blind per-block estimator — plus E, ideal correction at declared
granularities. Every correction lives here, on the evaluation side. No production file is modified;
arm A ablates `pipeline._track_phase` inside the worker process only, and restores it.

    python eval/space_doppler_mech.py generate
    python eval/space_doppler_mech.py run
    python eval/space_doppler_mech.py report
    python eval/space_doppler_mech.py verify
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
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding='utf-8')

import bench2_gen as gen                                   # noqa: E402  (stream_bits only)
import modem                                               # noqa: E402
import pipeline                                            # noqa: E402  (arm A ablates one function)
import space_doppler as sd                                 # noqa: E402  (trajectory definition)
from bench2 import _ber                                    # noqa: E402  (BER semantics, verbatim)
from modem import load_iq, save_iq                         # noqa: E402
from pipeline import CFO_MAX, TRACK_MIN_SYMBOLS, analyze_iq  # noqa: E402

SEED0 = 600000
OUT = os.path.join('data', 'space_bench', 'doppler_mech')
CRITERIA = os.path.join(HERE, 'space_doppler_mech_criteria.json')
MANIFEST = os.path.join(HERE, 'space_doppler_mech_manifest.json')
ROWS = os.path.join('results', 'space_doppler_mech_rows.jsonl')

# ---- the pre-registered grid (eval/space_doppler_mech_criteria.json, "grid")
TRAJECTORIES = ('static', 'linear', 'pass')
TREATED = ('linear', 'pass')
SEVERITY = (0.04, 0.1, 0.2, 0.4, 0.7, 1.0)          # x CFO_MAX; criteria DEV-2
LENGTHS = {'short': 200, 'long': 594}               # n_info bits -> 412 and 1200 symbols; DEV-1
LENGTH_SYMBOLS = {'short': 412, 'long': 1200}
ESN0_DB = (12, 6)
REPS = 2
KAPPA = sd.KAPPA
ARMS = ('A_no_tracking', 'B_existing', 'C_ideal', 'D_estimated')
D_BLOCKS = 8                                        # arm D: declared estimator block count
E_GRANULARITIES = ('const_64', 'const_32', 'const_16', 'const_8', 'linear_64')
E_SEVERITY = (0.1, 0.4, 1.0)
TRUE_MOD = 'BPSK'


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


# ---------------------------------------------------------------- generation
def _make(cls, params, rng):
    """(iq, ground truth). The same transmitter as the sealed experiment; only the carrier differs.

    A `static` cell carries the same peak offset as its matched treated cell with no variation
    (criteria DEV-3), so peak magnitude is controlled and the drift rate is the varying factor."""
    peak = params['severity'] * CFO_MAX
    n_info = LENGTHS[params['length']]
    sps = int(rng.choice([4, 6, 8]))
    beta = float(rng.uniform(0.2, 0.5))
    bits, info = gen.stream_bits(rng, n_info)
    syms = modem.modulate(bits, TRUE_MOD)
    sig = modem.pulse_shape(syms, sps, modem.rrc_filter(beta, sps))

    f = sd.trajectory(cls, peak, len(sig))
    sig = sd.apply_trajectory(sig, f)
    snr_per_sample = params['esn0'] - 10 * np.log10(len(sig) / max(len(syms), 1))
    iq, _ = modem.channel(sig, snr_per_sample, 0.0, 0.0, float(rng.uniform(0, 2 * np.pi)), rng)

    df = np.diff(f)
    return iq, {
        'trajectory_class': cls, 'params': dict(params), 'severity': params['severity'],
        'peak_shift_cyc_per_sample': float(peak), 'kappa': KAPPA,
        'max_drift_rate_cyc_per_sample2': float(np.max(np.abs(df))) if len(df) else 0.0,
        'n_samples': int(len(sig)), 'outside_search_bound': bool(peak > CFO_MAX),
        'modulation': TRUE_MOD, 'sps': sps, 'beta': beta, 'code': 'k7_continuous',
        'payload_bits': info.tolist(), 'esn0_db': params['esn0'],
        'n_symbols': int(len(syms)), 'n_info_bits': int(n_info), 'length': params['length'],
        'rep': params['rep'], 'tracking_expected': bool(len(syms) >= TRACK_MIN_SYMBOLS),
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
    if os.path.exists(MANIFEST) and '--force' not in sys.argv:
        sys.exit(f'refusing to regenerate: {MANIFEST} exists. A new experiment gets a new namespace; '
                 f'--force only to repair a lost dataset (`verify` then confirms it byte-identical).')
    os.makedirs(OUT, exist_ok=True)
    for old in glob.glob(os.path.join(OUT, '*')):
        os.remove(old)
    js = jobs()
    with Pool(max(1, (os.cpu_count() or 2) - 1)) as pool:
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
    m = {'experiment': 'SPACE-DOPPLER-MECH-01', 'n_files': len(entries), 'files': entries,
         'manifest_sha256': hashlib.sha256(lines.encode()).hexdigest(),
         'generator': 'eval/space_doppler_mech.py', 'seed0': SEED0,
         'criteria_sha256': _sha256_file(CRITERIA)}
    if write:
        with open(MANIFEST, 'w', encoding='utf-8') as f:
            json.dump(m, f, indent=1)
        print(f"wrote {MANIFEST}: {m['n_files']} files, manifest hash {m['manifest_sha256'][:16]}…")
    return m


def _regen_hash(job):
    index, cls, params = job
    iq, _ = _make(cls, params, np.random.RandomState(SEED0 + index))
    out = np.zeros(2 * len(iq), dtype=np.float32)
    out[0::2], out[1::2] = np.real(iq), np.imag(iq)
    return os.path.basename(_paths(index, cls)[0]), hashlib.sha256(out.tobytes()).hexdigest()


def verify():
    if not os.path.exists(MANIFEST):
        sys.exit('no manifest — generate first')
    committed = json.load(open(MANIFEST, encoding='utf-8'))['files']
    with Pool(max(1, (os.cpu_count() or 2) - 1)) as pool:
        regen = dict(pool.map(_regen_hash, jobs(), chunksize=4))
    differ = sorted(k for k in committed if regen.get(k) != committed[k])
    print(f'determinism: {len(committed) - len(differ)}/{len(committed)} files byte-identical'
          + (f' — DIFFER: {differ[:5]}' if differ else ''))
    return not differ


# ---------------------------------------------------------------- the corrections (evaluation side)
def true_trajectory(gt):
    """The exact per-sample frequency trajectory that generated this capture (arms C and E)."""
    return sd.trajectory(gt['trajectory_class'], gt['peak_shift_cyc_per_sample'], gt['n_samples'])


def _derotate(iq, f):
    return iq * np.exp(-2j * np.pi * np.cumsum(f[:len(iq)]))


def estimate_trajectory(iq, n_blocks=D_BLOCKS):
    """Arm D's declared blind estimator: per-block CFO from the engine's own x²/x⁴ line test.

    One frequency per block from `pipeline._cfo_candidates` (most significant candidate), assigned to
    the block centre, linearly interpolated between centres and held constant outside them. No ground
    truth of any kind. Returns (per-sample estimate, number of knots)."""
    n = len(iq)
    edges = np.linspace(0, n, n_blocks + 1).astype(int)
    centres, freqs = [], []
    for a, b in zip(edges[:-1], edges[1:]):
        if b - a < 32:
            continue
        cands, _ = pipeline._cfo_candidates(iq[a:b])
        if not cands:
            continue
        centres.append(0.5 * (a + b - 1))
        freqs.append(cands[0]['cfo'])
    if not centres:
        return np.zeros(n), 0
    return np.interp(np.arange(n), centres, freqs), len(centres)


def quantise_trajectory(f, sps, granularity):
    """Arm E: the true trajectory sampled at a declared granularity instead of per sample.

    `const_<blk>` holds the block-centre value across each block of `blk` symbols — the same
    piecewise-constant form `pipeline._track_phase` applies to phase. `linear_<blk>` interpolates
    linearly between block centres."""
    kind, blk = granularity.split('_')
    step = int(blk) * sps
    n = len(f)
    edges = list(range(0, n, step)) + [n]
    centres = [min((a + min(b, n) - 1) // 2, n - 1) for a, b in zip(edges[:-1], edges[1:])]
    if kind == 'const':
        out = np.empty(n)
        for i, (a, b) in enumerate(zip(edges[:-1], edges[1:])):
            out[a:min(b, n)] = f[centres[i]]
        return out
    return np.interp(np.arange(n), centres, f[centres])


# ---------------------------------------------------------------- scoring (pre-registered)
def score(gt, r):
    """(outcome, note) in the four pre-registered categories. A wrong payload beneath a true
    structural claim is CORRECT_STRUCTURE_WRONG_PAYLOAD — never a structural false accept."""
    if r['status'] != 'DECODED':
        return 'REFUSED', r['status']
    code_ok = (r['code'] or '').endswith('_continuous')
    mod_ok = r['modulation'] == gt['modulation']
    if not code_ok or not mod_ok:
        return 'WRONG_STRUCTURE', f"code={r['code']} mod={r['modulation']}"
    ber = _ber(r['payload_bits'], gt['payload_bits'])
    if ber < 0.01:
        return 'CORRECT_STRUCTURE_CORRECT_PAYLOAD', r['code']
    return 'CORRECT_STRUCTURE_WRONG_PAYLOAD', f'payload BER {ber:.3f}'


def _analyse(iq, arm):
    """Run the engine under one arm. Arm A ablates the tracked front end in THIS PROCESS only."""
    if arm != 'A_no_tracking':
        return analyze_iq(iq)
    original = pipeline._track_phase
    try:
        # signature mirrors the real _track_phase, whose optional write-only `_trace` the front-end
        # loop now passes (SPACE-TRACK-VALIDITY-01). Ablation semantics are unchanged: no tracked
        # front end is ever produced.
        pipeline._track_phase = lambda y, mod, _trace=None: None
        return analyze_iq(iq)
    finally:
        pipeline._track_phase = original
        assert pipeline._track_phase is original


def _row(gt, r, arm, path, runtime, extra):
    outcome, note = score(gt, r)
    sc = r.get('stream_code') or {}
    a = sc.get('accepted_hypothesis') or {}
    return {'file': os.path.basename(path)[:-3], 'arm': arm,
            'trajectory': gt['trajectory_class'], 'severity': gt['severity'],
            'peak': gt['peak_shift_cyc_per_sample'],
            'max_drift_rate': gt['max_drift_rate_cyc_per_sample2'],
            'esn0_db': gt['esn0_db'], 'length': gt['length'], 'rep': gt['rep'],
            'n_symbols': gt['n_symbols'], 'tracking_expected': gt['tracking_expected'],
            'outcome': outcome, 'note': note, 'status': r['status'],
            'ber': _ber(r['payload_bits'], gt['payload_bits']),
            'true_sps': gt['sps'], 'est_sps': r['sps'],
            'sps_in_candidates': gt['sps'] in r['diagnostics']['sps_candidates'],
            'est_code': r['code'], 'est_modulation': r['modulation'],
            'phase_tracked_front_ends': r['diagnostics']['phase_tracked_front_ends'],
            'agreement': a.get('agreement'), 'path_metric': a.get('path_metric'),
            'consistency': a.get('consistency'), 'f2_log10p': a.get('log10_p'),
            'f2_bar': sc.get('log10_threshold'), 'runtime': runtime, **extra}


def _run_one(job):
    path, arm = job
    gt = json.load(open(path + '.gt.json', encoding='utf-8'))
    iq = load_iq(path)
    extra = {'granularity': None, 'estimator_knots': None}
    if arm == 'C_ideal':
        iq = _derotate(iq, true_trajectory(gt))
    elif arm == 'D_estimated':
        f_hat, knots = estimate_trajectory(iq)
        iq = _derotate(iq, f_hat)
        extra['estimator_knots'] = knots
    t = time.perf_counter()
    r = _analyse(iq, arm)
    return _row(gt, r, arm, path, time.perf_counter() - t, extra)


def _run_one_e(job):
    """Arm E: ideal correction at a declared granularity."""
    path, granularity = job
    gt = json.load(open(path + '.gt.json', encoding='utf-8'))
    iq = load_iq(path)
    f = quantise_trajectory(true_trajectory(gt), gt['sps'], granularity)
    t = time.perf_counter()
    r = _analyse(_derotate(iq, f), 'E_granularity')
    return _row(gt, r, 'E_granularity', path, time.perf_counter() - t,
                {'granularity': granularity, 'estimator_knots': None})


def _e_jobs():
    """The pre-registered sub-study: pass trajectory, long length, 12 dB, severities {0.1,0.4,1.0}."""
    out = []
    for index, cls, p in jobs():
        if (cls == 'pass' and p['length'] == 'long' and p['esn0'] == 12
                and p['severity'] in E_SEVERITY):
            path = _paths(index, cls)[0]
            out += [(path, g) for g in E_GRANULARITIES]
    return out


def run():
    paths = sorted(glob.glob(os.path.join(OUT, '*.iq')))
    if not paths:
        sys.exit(f'no captures in {OUT} — generate first')
    main_jobs = [(p, arm) for p in paths for arm in ARMS]
    e_jobs = _e_jobs()
    print(f'{len(paths)} captures x {len(ARMS)} arms = {len(main_jobs)} analyses, '
          f'plus {len(e_jobs)} arm-E analyses')
    os.makedirs('results', exist_ok=True)
    t0 = time.perf_counter()
    rows = []
    with Pool(max(1, (os.cpu_count() or 2) - 1)) as pool, open(ROWS, 'w', encoding='utf-8') as f:
        for i, row in enumerate(pool.imap_unordered(_run_one, main_jobs, chunksize=2)):
            f.write(json.dumps(row) + '\n')
            rows.append(row)
            if (i + 1) % 100 == 0:
                print(f'{i + 1}/{len(main_jobs)}', flush=True)
        for row in pool.imap_unordered(_run_one_e, e_jobs, chunksize=2):
            f.write(json.dumps(row) + '\n')
            rows.append(row)
    print(f'{len(rows)} analyses in {time.perf_counter() - t0:.0f}s')
    for arm in ARMS + ('E_granularity',):
        print(f'  {arm:14} {dict(Counter(r["outcome"] for r in rows if r["arm"] == arm))}')


# ---------------------------------------------------------------- reporting
CATS = ('CORRECT_STRUCTURE_CORRECT_PAYLOAD', 'CORRECT_STRUCTURE_WRONG_PAYLOAD',
        'WRONG_STRUCTURE', 'REFUSED')
SHORT = {'CORRECT_STRUCTURE_CORRECT_PAYLOAD': 'correct', 'CORRECT_STRUCTURE_WRONG_PAYLOAD': 'WRONG',
         'WRONG_STRUCTURE': 'struct', 'REFUSED': 'refused'}


def _rows():
    if not os.path.exists(ROWS):
        sys.exit(f'no rows at {ROWS} — run first')
    return [json.loads(l) for l in open(ROWS, encoding='utf-8')]


def _rate(rs, cat):
    return sum(1 for r in rs if r['outcome'] == cat) / len(rs) if rs else float('nan')


def _line(label, rs):
    c = Counter(r['outcome'] for r in rs)
    return (f'{label:26} n={len(rs):4}  ' + '  '.join(f'{SHORT[k]} {c[k]:4}' for k in CATS)
            + f'   wrong-payload {_rate(rs, CATS[1]):.3f}')


def report():
    rows = _rows()
    crit = json.load(open(CRITERIA, encoding='utf-8'))
    print(f'\nSPACE-DOPPLER-MECH-01 — {len(rows)} analyses; criteria sha256 '
          f'{_sha256_file(CRITERIA)[:16]}…\n')

    main = [r for r in rows if r['arm'] in ARMS]
    treated = [r for r in main if r['trajectory'] in TREATED]
    control = [r for r in main if r['trajectory'] == 'static']

    print('BY ARM — treated captures (linear + pass)')
    for arm in ARMS:
        print('  ' + _line(arm, [r for r in treated if r['arm'] == arm]))
    print('\nBY ARM — static controls (matched peak offset, zero drift)')
    for arm in ARMS:
        print('  ' + _line(arm, [r for r in control if r['arm'] == arm]))

    print('\nBY TRAJECTORY x ARM (treated)')
    for cls in TREATED:
        for arm in ARMS:
            print('  ' + _line(f'{cls}/{arm}',
                               [r for r in treated if r['trajectory'] == cls and r['arm'] == arm]))

    print('\nBY DRIFT SEVERITY x ARM (treated; achieved drift rate shown)')
    for sev in SEVERITY:
        rs_all = [r for r in treated if r['severity'] == sev]
        rates = [r['max_drift_rate'] for r in rs_all]
        print(f'  severity {sev:<5} peak {sev * CFO_MAX:.5f}  drift '
              f'{min(rates):.2e}–{max(rates):.2e} cyc/sample²')
        for arm in ARMS:
            print('    ' + _line(arm, [r for r in rs_all if r['arm'] == arm]))

    print('\nBY Es/N0 x ARM (treated)')
    for esn0 in ESN0_DB:
        for arm in ARMS:
            print('  ' + _line(f'{esn0}dB/{arm}',
                               [r for r in treated if r['esn0_db'] == esn0 and r['arm'] == arm]))

    print(f'\nBY LENGTH x ARM (treated; TRACK_MIN_SYMBOLS = {TRACK_MIN_SYMBOLS})')
    for length in ('short', 'long'):
        for arm in ARMS:
            print('  ' + _line(f'{length}({LENGTH_SYMBOLS[length]}sym)/{arm}',
                               [r for r in treated if r['length'] == length and r['arm'] == arm]))

    print('\nARM E — ideal correction at declared granularities (pass, long, 12 dB)')
    e_rows = [r for r in rows if r['arm'] == 'E_granularity']
    for g in E_GRANULARITIES:
        print('  ' + _line(g, [r for r in e_rows if r['granularity'] == g]))

    # ---- pre-registered decision bars
    print('\nPRE-REGISTERED DECISION BARS (criteria: decision_criteria)')
    w = {arm: _rate([r for r in treated if r['arm'] == arm], CATS[1]) for arm in ARMS}
    ok = {arm: _rate([r for r in treated if r['arm'] == arm], CATS[0]) for arm in ARMS}
    c, d, a, b = w['C_ideal'], w['D_estimated'], w['A_no_tracking'], w['B_existing']
    verdicts = {}

    def say(name, hit, detail):
        verdicts[name] = hit
        print(f'  [{"YES" if hit else "no ":>3}] {name}: {detail}')

    say('C_restores', c <= 0.05 and ok['C_ideal'] >= 0.90,
        f'arm C wrong-payload {c:.3f} (bar <= 0.05), correct {ok["C_ideal"]:.3f} (bar >= 0.90)')
    say('C_does_not_restore', c >= 0.25, f'arm C wrong-payload {c:.3f} (bar >= 0.25)')
    say('C_partial', 0.05 < c < 0.25, f'arm C wrong-payload {c:.3f} strictly within (0.05, 0.25)')
    say('D_approaches_C', abs(d - c) <= 0.10,
        f'|D {d:.3f} - C {c:.3f}| = {abs(d - c):.3f} (bar <= 0.10)')
    say('D_far_from_C', d - c >= 0.20, f'D {d:.3f} - C {c:.3f} = {d - c:.3f} (bar >= 0.20)')
    say('A_equals_B', abs(a - b) <= 0.10, f'|A {a:.3f} - B {b:.3f}| = {abs(a - b):.3f} (bar <= 0.10)')
    e_rate = {g: _rate([r for r in e_rows if r['granularity'] == g], CATS[1])
              for g in E_GRANULARITIES}
    const = [e_rate[g] for g in E_GRANULARITIES if g.startswith('const')]
    say('H2_confirmed', e_rate['linear_64'] <= 0.05 and min(const) >= 0.20,
        f'linear_64 {e_rate["linear_64"]:.3f} (bar <= 0.05), best const {min(const):.3f} '
        f'(bar >= 0.20)')
    say('H2_killed', max(e_rate.values()) - min(e_rate.values()) <= 0.10,
        f'granularity spread {max(e_rate.values()) - min(e_rate.values()):.3f} (bar <= 0.10)')
    n_ws = sum(1 for r in rows if r['outcome'] == 'WRONG_STRUCTURE')
    say('wrong_structure_stop', n_ws > 0, f'{n_ws} WRONG_STRUCTURE outcomes across all arms')

    for k in verdicts:
        assert k in crit['decision_criteria'], f'{k} is not a pre-registered bar'

    # ---- payload-side scores on NEW data (recorded; no threshold derived from them)
    print('\nPAYLOAD-SIDE SCORES ON NEW DATA (recorded per criteria; no threshold derived)')
    for arm in ARMS:
        rs = [r for r in main if r['arm'] == arm and r['status'] == 'DECODED'
              and r['path_metric'] is not None]
        good = [r['path_metric'] for r in rs if r['outcome'] == CATS[0]]
        bad = [r['path_metric'] for r in rs if r['outcome'] == CATS[1]]
        if good and bad:
            print(f'  {arm:14} path_metric  correct min {min(good):.4f} | wrong max {max(bad):.4f} '
                  f'| separated: {min(good) > max(bad)}')
        else:
            print(f'  {arm:14} path_metric  correct n={len(good)} wrong n={len(bad)} '
                  f'(a population is empty — no comparison)')
    return verdicts


def demo():
    """Self-checks on the logic this file adds: the corrections, the estimator and the scoring."""
    gt = {'trajectory_class': 'pass', 'peak_shift_cyc_per_sample': 0.01, 'n_samples': 512,
          'modulation': 'BPSK', 'payload_bits': [0, 1] * 64}
    f = true_trajectory(gt)
    assert len(f) == 512 and np.isclose(f[0], -f[-1])
    # ideal correction exactly undoes the generator's mixing
    rng = np.random.RandomState(0)
    sig = rng.standard_normal(512) + 1j * rng.standard_normal(512)
    assert np.allclose(_derotate(sd.apply_trajectory(sig, f), f), sig, atol=1e-9)
    # the blind estimator recovers a constant offset to within a fraction of a bin
    tone = np.exp(2j * np.pi * 0.004 * np.arange(4096))
    f_hat, knots = estimate_trajectory(tone)
    assert knots == D_BLOCKS and abs(np.median(f_hat) - 0.004) < 5e-4, (knots, np.median(f_hat))
    # granularity: const holds one value per block, linear varies within it
    fc = quantise_trajectory(f, 4, 'const_64')
    fl = quantise_trajectory(f, 4, 'linear_64')
    assert len(fc) == len(fl) == len(f)
    assert len(np.unique(fl)) > len(np.unique(fc))
    assert len(np.unique(quantise_trajectory(f, 4, 'const_8'))) > len(np.unique(fc))
    # scoring separates the four categories
    good = {'status': 'DECODED', 'code': 'conv_k7_r12_171_133_continuous', 'modulation': 'BPSK',
            'payload_bits': gt['payload_bits']}
    assert score(gt, good)[0] == 'CORRECT_STRUCTURE_CORRECT_PAYLOAD'
    assert score(gt, {**good, 'payload_bits': [1, 1] * 64})[0] == 'CORRECT_STRUCTURE_WRONG_PAYLOAD'
    assert score(gt, {**good, 'code': 'rs_255_223'})[0] == 'WRONG_STRUCTURE'
    assert score(gt, {**good, 'modulation': 'QPSK'})[0] == 'WRONG_STRUCTURE'
    assert score(gt, {**good, 'status': 'UNKNOWN'})[0] == 'REFUSED'
    # the grid is the pre-registered one
    assert len(jobs()) == 144 and len(jobs()) * len(ARMS) == 576 and len(_e_jobs()) == 30
    print('demo: corrections, estimator, granularity, scoring and grid self-checks pass')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'demo'
    os.chdir(ROOT)
    {'generate': generate, 'run': run, 'report': report, 'verify': verify, 'demo': demo}[cmd]()
