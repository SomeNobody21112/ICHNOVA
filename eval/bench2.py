"""bench-v2: catalogue v1 families, non-catalogue nulls and channel impairments (Constitution §18.1).

usage:
  python eval/bench2.py generate calibration|train|sealed
  python eval/bench2.py manifest sealed                  # write the committed SHA-256 manifest
  python eval/bench2.py run calibration|train [--higher]
  python eval/bench2.py run sealed --final-evaluation [--higher]
  python eval/bench2.py report calibration|train|sealed

Protocol (all of it is policy from §18.1, not a convenience):
  * three splits from **disjoint seed ranges**; constants may only ever be fitted on CALIBRATION;
  * `eval/bench2_criteria.json` is committed **before** SEALED is ever run, and `report` checks the
    measurement against it;
  * `eval/bench2_sealed_manifest.json` (per-file SHA-256 + a manifest hash) is committed when SEALED
    is first generated, so a later regeneration cannot silently differ;
  * the SEALED runner refuses to run without `--final-evaluation` and appends every run to the
    committed access log `eval/bench2_access_log.jsonl`;
  * a SEALED result obtained after an engine change made in response to it is contaminated, and the
    access log is what makes that visible.

Scoring is decided by the class, not by the receiver: catalogue classes have a correct structure and
payload, the blind framed class is correct only as SIGNAL_NO_CODE with the right period, and the null
classes are correct only as a refusal. Any DECODED on a null class or any wrong structure/payload on
a catalogue class is a false accept.
"""

import glob
import hashlib
import json
import os
import subprocess
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

import bench2_gen as gen                                   # noqa: E402
import interleavers as il                                  # noqa: E402
import ldpc                                                # noqa: E402
import rs                                                  # noqa: E402
from fec import conv_encode                                # noqa: E402
from modem import load_iq, save_iq                         # noqa: E402
from pipeline import analyze_iq                            # noqa: E402

SPLITS = {'calibration': 200000, 'train': 300000, 'sealed': 400000}
OUT = os.path.join('data', 'bench2')
CRITERIA = os.path.join(HERE, 'bench2_criteria.json')
MANIFEST = os.path.join(HERE, 'bench2_sealed_manifest.json')
ACCESS_LOG = os.path.join(HERE, 'bench2_access_log.jsonl')
ROWS = os.path.join('results', 'bench2_{split}_rows.jsonl')

NULL_CLASSES = ('noise', 'uncoded_BPSK', 'uncoded_QPSK', 'uncoded_8PSK', 'uncoded_16QAM',
                'mod_64qam', 'conv_k9', 'rs_dvb_204_188', 'linear_128_64', 'asm_random',
                'idle_carrier', 'perm_random')
REFUSAL = ('UNKNOWN', 'SIGNAL_NO_CODE')


# ---------------------------------------------------------------- the job list (deterministic)
def jobs(split):
    """Every file of a split, as (index, class, params). The list is a pure function of the split."""
    out = []
    for mod in gen.MODS:
        for code in gen.CODES:
            for name, spec in gen.SPECS.items():
                for esn0 in gen.ESN0_DB:
                    out.append((f'burst_{mod}_{code}_{name}', {'mod': mod, 'code': code, 'spec': name,
                                                               'esn0': esn0}))
    for inv in (False, True):
        for esn0 in gen.ESN0_DB:
            for k in range(2):
                out.append(('stream_k7', {'g2_inverted': inv, 'esn0': esn0, 'rep': k}))
    for (E, I, Q) in ((16, 1, 0), (16, 4, 0), (8, 1, 0), (8, 5, 0)):
        for esn0 in gen.ESN0_DB:
            out.append(('ccsds_concat', {'E': E, 'I': I, 'Q': Q, 'esn0': esn0}))
    for (E, I, Q) in ((16, 1, 0), (8, 2, 0)):
        for esn0 in gen.ESN0_DB:
            out.append(('rs_framed', {'E': E, 'I': I, 'Q': Q, 'esn0': esn0}))
    for randomizer in ('tc_btg', None):
        for esn0 in gen.ESN0_DB:
            out.append(('tc_ldpc_cltu', {'randomizer': randomizer, 'esn0': esn0}))
    for period in (512, 1024):
        for esn0 in gen.ESN0_DB:
            out.append(('blind_framed', {'period': period, 'esn0': esn0}))
    for cls in NULL_CLASSES:
        for esn0 in gen.ESN0_DB:
            for k in range(2):
                out.append((cls, {'esn0': esn0, 'rep': k}))
    return [(i, cls, p) for i, (cls, p) in enumerate(out)]


def _name(split, index, cls):
    return f'{cls}_{index:04d}'


def _paths(split, index, cls):
    d = os.path.join(OUT, split)
    base = os.path.join(d, _name(split, index, cls))
    return base + '.iq', base + '.iq.gt.json'


# ---------------------------------------------------------------- generation
def _make(cls, params, rng):
    """(iq, ground truth) for one file."""
    esn0 = params.get('esn0', 9)
    sps = int(rng.choice([4, 6, 8]))
    beta = float(rng.uniform(0.2, 0.5))
    channel = gen.CHANNELS[rng.randint(len(gen.CHANNELS))]
    gt = {'class': cls, 'params': dict(params)}

    if cls.startswith('burst_'):
        mod, code, spec_name = params['mod'], params['code'], params['spec']
        spec = gen.SPECS[spec_name]
        bits, info = gen.burst_bits(rng, code, spec, mod)
        syms = gen.modulate(bits, mod)
        gt.update(family='F1', modulation=mod, code=code, interleaver_type=il.describe(spec)['type'],
                  expected='DECODED', payload_bits=info.tolist())
    elif cls == 'stream_k7':
        bits, info = gen.stream_bits(rng, 1200, params['g2_inverted'])
        mod = 'BPSK'
        syms = gen.modulate(bits, mod)
        gt.update(family='F2', modulation=mod, code='k7_continuous', expected='DECODED',
                  g2_inverted=params['g2_inverted'], payload_bits=info.tolist())
    elif cls == 'ccsds_concat':
        frames, info = gen.rs_frames(rng, 4, params['E'], params['I'], params['Q'])
        bits = conv_encode(frames, *gen.CODES['k7']).copy()
        bits[1::2] ^= 1                                    # CCSDS G2 inversion (131.0-B-5 §3.3.1)
        mod = 'BPSK'
        syms = gen.modulate(bits, mod)
        gt.update(family='F2+F3+F4', modulation=mod, code=f"ccsds_rs_255_{255 - 2 * params['E']}",
                  expected='DECODED', payload_symbols=info.tolist(),
                  inner_payload_bits=frames.tolist(), inner_code='k7_continuous')
    elif cls == 'rs_framed':
        bits, info = gen.rs_frames(rng, 4, params['E'], params['I'], params['Q'])
        mod = 'BPSK'
        syms = gen.modulate(bits, mod)
        gt.update(family='F3+F4', modulation=mod, code=f"ccsds_rs_255_{255 - 2 * params['E']}",
                  expected='DECODED', payload_symbols=info.tolist())
    elif cls == 'tc_ldpc_cltu':
        bits, info = gen.cltu_bits(rng, 24, params['randomizer'])
        mod = 'BPSK'
        syms = gen.modulate(bits, mod)
        gt.update(family='F4', modulation=mod, code='ccsds_tc_ldpc_128_64', expected='DECODED',
                  payload_bits=info.tolist())
    elif cls == 'blind_framed':
        bits, _ = gen.blind_framed_bits(rng, 8, params['period'])
        mod = 'BPSK'
        syms = gen.modulate(bits, mod)
        gt.update(family='F3', modulation=mod, expected='SIGNAL_NO_CODE', period_bits=params['period'])
    elif cls == 'noise':
        n = int(rng.choice([2000, 6000, 20000]))
        iq = (rng.standard_normal(n) + 1j * rng.standard_normal(n)) / np.sqrt(2)
        gt.update(family='null', expected='REFUSAL', channel='none', modulation=None)
        return iq, gt
    elif cls == 'idle_carrier':
        bits = np.zeros(3000, dtype=np.uint8)
        mod = 'BPSK'
        syms = gen.modulate(bits, mod)
        gt.update(family='null', expected='REFUSAL', modulation=mod)
    elif cls.startswith('uncoded_'):
        mod = cls.split('_')[1]
        bits = rng.randint(0, 2, 2400).astype(np.uint8)
        syms = gen.modulate(bits, mod)
        gt.update(family='null', expected='REFUSAL', modulation=mod)
    elif cls == 'mod_64qam':
        bits = rng.randint(0, 2, 3600).astype(np.uint8)
        syms = gen.modulate_64qam(bits)
        gt.update(family='null', expected='REFUSAL', modulation='64QAM')
    elif cls == 'conv_k9':
        info = rng.randint(0, 2, 400).astype(np.uint8)
        coded = conv_encode(info, *gen.CODE_K9)
        syms = gen.modulate(coded, 'BPSK')
        gt.update(family='null', expected='REFUSAL', modulation='BPSK', code='k9')
    elif cls == 'rs_dvb_204_188':
        words = [gen.rs_dvb_encode(rng.randint(0, 256, 188).astype(np.int64)) for _ in range(3)]
        bits = rs.symbols_to_bits(np.concatenate(words))
        syms = gen.modulate(bits, 'BPSK')
        gt.update(family='null', expected='REFUSAL', modulation='BPSK', code='rs_dvb_204_188')
    elif cls == 'linear_128_64':
        _, words = gen.random_linear_128_64(rng, 24)
        syms = gen.modulate(words.reshape(-1), 'BPSK')
        gt.update(family='null', expected='REFUSAL', modulation='BPSK', code='random_linear_128_64')
    elif cls == 'asm_random':
        bits = gen.asm_random_bits(rng, 6, 2072)
        syms = gen.modulate(bits, 'BPSK')
        gt.update(family='null', expected='REFUSAL', modulation='BPSK',
                  note='catalogue marker with random data: a frame, no code')
    elif cls == 'perm_random':
        info = rng.randint(0, 2, 96).astype(np.uint8)
        coded = conv_encode(info, *gen.CODES['k7'])[:192]
        perm = rng.permutation(192)
        bits = np.zeros(192, dtype=np.uint8)
        bits[perm] = coded
        syms = gen.modulate(bits, 'BPSK')
        gt.update(family='null', expected='REFUSAL', modulation='BPSK',
                  note='non-catalogue random permutation interleaver')
    else:
        raise ValueError(cls)

    iq, meta = gen.apply_channel(syms, sps, beta, esn0, channel, rng)
    gt.update(meta)
    return iq, gt


def _gen_one(job):
    split, index, cls, params = job
    rng = np.random.RandomState(SPLITS[split] + index)
    iq, gt = _make(cls, params, rng)
    gt.update(split=split, index=index, seed=SPLITS[split] + index)
    iq_path, gt_path = _paths(split, index, cls)
    save_iq(iq_path, iq)
    with open(gt_path, 'w', encoding='utf-8') as f:
        json.dump(gt, f)
    return os.path.basename(iq_path), len(iq)


def generate(split):
    assert split in SPLITS, split
    d = os.path.join(OUT, split)
    os.makedirs(d, exist_ok=True)
    for old in glob.glob(os.path.join(d, '*')):
        os.remove(old)
    js = [(split, i, cls, p) for i, cls, p in jobs(split)]
    with Pool(max(1, (os.cpu_count() or 2) - 1)) as pool:
        made = pool.map(_gen_one, js, chunksize=4)
    total = sum(n for _, n in made)
    print(f'generated {len(made)} files in {d} ({total / 1e6:.1f} M samples, seeds '
          f'{SPLITS[split]}–{SPLITS[split] + len(js) - 1})')


# ---------------------------------------------------------------- manifest and access log
def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def manifest(split='sealed', write=True):
    files = sorted(glob.glob(os.path.join(OUT, split, '*.iq')))
    entries = {os.path.basename(p): _sha256(p) for p in files}
    lines = '\n'.join(f'{k} {v}' for k, v in sorted(entries.items()))
    m = {'split': split, 'n_files': len(entries), 'files': entries,
         'manifest_sha256': hashlib.sha256(lines.encode()).hexdigest(),
         'generator': 'eval/bench2.py + eval/bench2_gen.py', 'seed0': SPLITS[split]}
    if write:
        with open(MANIFEST, 'w', encoding='utf-8') as f:
            json.dump(m, f, indent=1)
        print(f"wrote {MANIFEST}: {m['n_files']} files, manifest hash {m['manifest_sha256'][:16]}…")
    return m


def _check_manifest():
    """The sealed split must match the committed manifest exactly."""
    if not os.path.exists(MANIFEST):
        return None, 'no committed manifest'
    committed = json.load(open(MANIFEST, encoding='utf-8'))
    current = manifest('sealed', write=False)
    if current['manifest_sha256'] != committed['manifest_sha256']:
        differing = [k for k, v in committed['files'].items() if current['files'].get(k) != v]
        return committed, (f"sealed data does not match the committed manifest "
                           f"({len(differing)} of {len(committed['files'])} files differ)")
    return committed, None


def _commit():
    try:
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT,
                                       text=True).strip()
    except Exception:
        return 'unknown'


def _log_access(entry):
    with open(ACCESS_LOG, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry) + '\n')


# ---------------------------------------------------------------- running
def _ber(decoded, truth):
    d, o = np.asarray(decoded), np.asarray(truth)
    L = min(len(d), len(o))
    return 1.0 if L == 0 else float(min(np.mean(d[:L] != o[:L]), np.mean(d[:L] != 1 - o[:L])))


def _score(gt, r):
    """(outcome, note) for one file.

    Outcomes: TP (the claim and its payload are right), TP_PARTIAL (the claim is true but covers
    fewer layers than the transmission, or a block code decoded only some of its codewords — an
    honest, incomplete answer), FALSE_ACCEPT (a structure that is not there, or a payload that is
    wrong where the engine says it decoded one), FN (a refusal although a correct answer existed),
    REFUSED_OK (a refusal on a null class)."""
    cls, status = gt['class'], r['status']
    if gt['expected'] == 'REFUSAL':
        return ('FALSE_ACCEPT', f'DECODED as {r["code"]}') if status == 'DECODED' else ('REFUSED_OK', '')
    if gt['expected'] == 'SIGNAL_NO_CODE':
        if status == 'DECODED':
            return 'FALSE_ACCEPT', f'DECODED as {r["code"]}'
        acc = (r.get('frame') or {}).get('accepted_hypothesis')
        if status == 'SIGNAL_NO_CODE' and acc and acc['period_bits'] == gt['period_bits']:
            return 'TP', f"frame P={acc['period_bits']}"
        return 'FN', f"no frame at P={gt['period_bits']}"
    # DECODED expected: the claim must match the transmitted structure and the payload
    if status != 'DECODED':
        return 'FN', status
    if cls.startswith('burst_'):
        ok = (r['modulation'] == gt['modulation']
              and (r['code'] or '').startswith('conv_' + gt['code'])
              and (r['interleaver_spec'] or {}).get('type') == gt['interleaver_type']
              and _ber(r['payload_bits'], gt['payload_bits']) < 0.01)
    elif cls == 'stream_k7':
        ok = ((r['code'] or '').endswith('_continuous')
              and _ber(r['payload_bits'], gt['payload_bits']) < 0.01)
    elif cls in ('ccsds_concat', 'rs_framed'):
        truth = rs.symbols_to_bits(np.array(gt['payload_symbols']))
        if r['code'] == gt['code']:
            if _ber(r['payload_bits'], truth) < 0.01:
                return 'TP', r['code']
            a4 = (r.get('block_code') or {}).get('accepted_hypothesis') or {}
            if 0 < a4.get('n_decoded', 0) < a4.get('n_codewords', 0):
                return 'TP_PARTIAL', f"RS accepted, {a4['n_decoded']}/{a4['n_codewords']} codewords decoded"
            return 'FALSE_ACCEPT', f"payload wrong under an {r['code']} claim"
        if cls == 'ccsds_concat' and (r['code'] or '').endswith('_continuous'):
            # The inner convolutional layer on its own is a true statement about this capture.
            if _ber(r['payload_bits'], np.array(gt['inner_payload_bits'])) < 0.01:
                return 'TP_PARTIAL', 'inner stream code identified; outer RS layer not accepted'
            return 'FALSE_ACCEPT', 'inner-code claim with a wrong payload'
        return 'FALSE_ACCEPT', f"wrong structure: {r['code']}"
    elif cls == 'tc_ldpc_cltu':
        if r['code'] != gt['code']:
            return 'FALSE_ACCEPT', f"wrong structure: {r['code']}"
        if _ber(r['payload_bits'], gt['payload_bits']) < 0.01:
            return 'TP', r['code']
        conv = ((r.get('block_code') or {}).get('accepted_hypothesis') or {}).get('converged_codewords')
        if conv is not None and not all(conv):
            return 'TP_PARTIAL', f'LDPC accepted, {sum(conv)}/{len(conv)} codewords converged'
        return 'FALSE_ACCEPT', 'payload wrong under an LDPC claim'
    else:
        raise ValueError(cls)
    return ('TP', r['code']) if ok else ('FALSE_ACCEPT', f'wrong structure or payload: {r["code"]}')


def _run_one(job):
    split, path, higher = job
    gt = json.load(open(path + '.gt.json', encoding='utf-8'))
    t = time.perf_counter()
    r = analyze_iq(load_iq(path), search_higher_modulations=higher)
    outcome, note = _score(gt, r)
    fam = {f['name']: {'M': f['tested_hypotheses'], 'p': f['best_log10_p'],
                       'bar': f['log10_threshold'], 'accepted': f['accepted']}
           for f in r['accept']['families']}
    return {'file': os.path.basename(path)[:-3], 'class': gt['class'], 'family': gt['family'],
            'expected': gt['expected'], 'status': r['status'], 'outcome': outcome, 'note': note,
            'esn0_db': gt['params'].get('esn0'), 'channel': gt.get('channel'),
            'sps': gt.get('sps'), 'modulation': gt.get('modulation'),
            'est_code': r['code'], 'est_modulation': r['modulation'],
            'est_interleaver': (r['interleaver_spec'] or {}).get('type'),
            'families': fam, 'runtime': time.perf_counter() - t}


def run(split, final=False, higher=False):
    assert split in SPLITS, split
    if split == 'sealed':
        if not final:
            sys.exit('refusing to run the SEALED split without --final-evaluation (Constitution §18.1)')
        committed, problem = _check_manifest()
        if problem:
            sys.exit(f'SEALED refused: {problem}')
    paths = sorted(glob.glob(os.path.join(OUT, split, '*.iq')))
    if not paths:
        sys.exit(f'no files in {os.path.join(OUT, split)} — generate the split first')
    os.makedirs('results', exist_ok=True)
    t0 = time.perf_counter()
    with Pool(max(1, (os.cpu_count() or 2) - 1)) as pool, \
            open(ROWS.format(split=split), 'w', encoding='utf-8') as f:
        rows = []
        for i, row in enumerate(pool.imap_unordered(_run_one, [(split, p, higher) for p in paths],
                                                    chunksize=2)):
            f.write(json.dumps(row) + '\n')
            rows.append(row)
            if (i + 1) % 50 == 0:
                print(f'{i + 1}/{len(paths)}', flush=True)
    elapsed = time.perf_counter() - t0
    counts = Counter(r['outcome'] for r in rows)
    print(f'{split}: {len(rows)} files in {elapsed:.0f}s — {dict(counts)}')
    if split == 'sealed':
        _log_access({'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                     'commit': _commit(), 'split': 'sealed', 'n_files': len(rows),
                     'manifest_sha256': json.load(open(MANIFEST, encoding='utf-8'))['manifest_sha256'],
                     'criteria_sha256': _sha256(CRITERIA) if os.path.exists(CRITERIA) else None,
                     'higher_modulations': higher, 'outcomes': dict(counts),
                     'runtime_s': round(elapsed, 1)})
        print(f'appended the run to {ACCESS_LOG}')


# ---------------------------------------------------------------- reporting
def wilson_hi(k, n, z=1.96):
    if n == 0:
        return 1.0
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    return min(1.0, c + z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n))


def _cell(rows):
    n = len(rows)
    tp = sum(r['outcome'] == 'TP' for r in rows)
    partial = sum(r['outcome'] == 'TP_PARTIAL' for r in rows)
    fa = sum(r['outcome'] == 'FALSE_ACCEPT' for r in rows)
    fn = sum(r['outcome'] in ('FN',) for r in rows)
    ok = sum(r['outcome'] == 'REFUSED_OK' for r in rows)
    return {'n': n, 'tp': tp, 'partial': partial, 'fa': fa, 'fn': fn, 'refused_ok': ok,
            'recall': tp / n if n and rows[0]['expected'] != 'REFUSAL' else None,
            'fa_rate': fa / n if n else 0.0, 'fa_hi': wilson_hi(fa, n)}


def report(split):
    path = ROWS.format(split=split)
    if not os.path.exists(path):
        sys.exit(f'no results for {split} — run it first')
    rows = [json.loads(line) for line in open(path, encoding='utf-8')]
    crit = json.load(open(CRITERIA, encoding='utf-8')) if os.path.exists(CRITERIA) else None
    print(f'# bench-v2 — {split} split ({len(rows)} files)\n')
    print(f"Dataset: `{OUT}/{split}`, seeds {SPLITS[split]}–{SPLITS[split] + len(rows) - 1}, generator "
          f"`eval/bench2_gen.py`. Engine commit `{_commit()}`. "
          f"Criteria: {'`eval/bench2_criteria.json` (committed before any sealed run)' if crit else 'none committed'}.\n")
    if split == 'sealed':
        print('**SEALED split — final evaluation only.** Every run is recorded in '
              '`eval/bench2_access_log.jsonl`.\n')

    groups = [('Catalogue families (a correct structure exists)',
               [c for c in sorted({r['class'] for r in rows}) if c not in NULL_CLASSES]),
              ('Non-catalogue nulls (any DECODED is a false accept)',
               [c for c in sorted({r['class'] for r in rows}) if c in NULL_CLASSES])]
    for title, classes in groups:
        print(f'## {title}\n')
        print('| class | N | TP | partial | false accepts (95% upper) | FN | recall |')
        print('|---|---|---|---|---|---|---|')
        for c in classes:
            m = _cell([r for r in rows if r['class'] == c])
            rec = '—' if m['recall'] is None else f"{m['recall']:.2f}"
            print(f"| {c} | {m['n']} | {m['tp']} | {m['partial']} | {m['fa']} ({100 * m['fa_hi']:.1f}%) | "
                  f"{m['fn']} | {rec} |")
        print()

    print('## By Es/N0 (catalogue classes, recall)\n')
    fams = sorted({r['family'] for r in rows if r['expected'] != 'REFUSAL'})
    print('| family | ' + ' | '.join(f'{e} dB' for e in gen.ESN0_DB) + ' |')
    print('|---|' + '---|' * len(gen.ESN0_DB))
    for fam in fams:
        cells = []
        for e in gen.ESN0_DB:
            rs_ = [r for r in rows if r['family'] == fam and r['esn0_db'] == e]
            m = _cell(rs_)
            cells.append(f"{m['tp']}/{m['n']}" if rs_ else '—')
        print(f'| {fam} | ' + ' | '.join(cells) + ' |')

    print('\n## By channel (all classes)\n')
    print('| channel | N | TP | false accepts | recall (catalogue only) |')
    print('|---|---|---|---|---|')
    for ch in ('none',) + gen.CHANNELS:
        rs_ = [r for r in rows if (r['channel'] or 'none') == ch]
        if not rs_:
            continue
        cat = [r for r in rs_ if r['expected'] != 'REFUSAL']
        m, mc = _cell(rs_), _cell(cat)
        recall = f"{mc['tp']}/{mc['n']}" if cat else '—'
        print(f"| {ch} | {m['n']} | {m['tp']} | {m['fa']} | {recall} |")

    nulls = [r for r in rows if r['expected'] == 'REFUSAL']
    cat = [r for r in rows if r['expected'] != 'REFUSAL']
    nm, cm = _cell(nulls), _cell(cat)
    print(f"\n**Totals.** Null classes: {nm['fa']}/{nm['n']} false accepts "
          f"(95% Wilson upper bound {100 * nm['fa_hi']:.2f}%). Catalogue classes: {cm['tp']}/{cm['n']} "
          f"fully correct, {cm['partial']} partially correct (true but fewer layers), "
          f"{cm['fa']} wrong structure or payload "
          f"(95% upper bound {100 * cm['fa_hi']:.2f}%), {cm['fn']} refusals.")
    print(f"Mean runtime {np.mean([r['runtime'] for r in rows]):.2f} s, "
          f"max {np.max([r['runtime'] for r in rows]):.1f} s.")

    if crit:
        print('\n## Pre-registered criteria\n')
        print('| criterion | required | measured | verdict |')
        print('|---|---|---|---|')
        for name, c in crit['criteria'].items():
            value, verdict = _evaluate_criterion(c, rows)
            print(f"| {name} | {c['requirement']} | {value} | {verdict} |")


def _evaluate_criterion(c, rows):
    kind = c['kind']
    if kind == 'null_false_accept_rate':
        sel = [r for r in rows if r['expected'] == 'REFUSAL']
        m = _cell(sel)
        ok = m['fa_rate'] <= c['max_rate'] and m['fa_hi'] <= c['max_wilson_hi']
        return (f"{m['fa']}/{m['n']} = {100 * m['fa_rate']:.2f}% (≤{100 * m['fa_hi']:.2f}%)",
                'PASS' if ok else 'FAIL')
    if kind == 'catalogue_wrong_rate':
        sel = [r for r in rows if r['expected'] != 'REFUSAL']
        m = _cell(sel)
        ok = m['fa_rate'] <= c['max_rate']
        return f"{m['fa']}/{m['n']} = {100 * m['fa_rate']:.2f}%", 'PASS' if ok else 'FAIL'
    if kind == 'recall_including_partial':
        sel = [r for r in rows if (c.get('classes') is None or r['class'] in c['classes'])
               and (c.get('min_esn0') is None or (r['esn0_db'] or 0) >= c['min_esn0'])]
        m = _cell(sel)
        good = m['tp'] + m['partial']
        ok = m['n'] > 0 and good / m['n'] >= c['min_rate']
        return (f"{good}/{m['n']} = {0 if not m['n'] else 100 * good / m['n']:.0f}%",
                'PASS' if ok else 'FAIL')
    if kind == 'recall':
        sel = [r for r in rows if (c.get('class_prefix') is None or r['class'].startswith(c['class_prefix']))
               and (c.get('classes') is None or r['class'] in c['classes'])
               and (c.get('min_esn0') is None or (r['esn0_db'] or 0) >= c['min_esn0'])]
        m = _cell(sel)
        ok = m['n'] > 0 and (m['recall'] or 0) >= c['min_recall']
        return f"{m['tp']}/{m['n']} = {0 if not m['n'] else 100 * (m['recall'] or 0):.0f}%", 'PASS' if ok else 'FAIL'
    return 'unknown criterion kind', 'FAIL'


if __name__ == '__main__':
    cmd = sys.argv[1]
    arg = sys.argv[2] if len(sys.argv) > 2 else 'calibration'
    flags = sys.argv[2:]
    if cmd == 'generate':
        generate(arg)
    elif cmd == 'manifest':
        manifest(arg)
    elif cmd == 'run':
        run(arg, final='--final-evaluation' in flags, higher='--higher' in flags)
    elif cmd == 'report':
        report(arg)
    else:
        sys.exit(__doc__)
