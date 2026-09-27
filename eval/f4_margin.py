"""SPACE-F4-MARGIN-01 — how close does the SHIPPED engine run to an F4 block-code acceptance?

Protocol: `eval/f4_margin_protocol.json`, committed before this file existed. Read-only: it analyses
the existing sealed datasets (bench-v2 sealed, bench-v1 sealed, the independent null set) with the
**unmodified** engine — no ablation, no pre-correction, no oracle — and records, per capture, the F4
family's best p-value, its bar, the margin between them, and the converged-codeword count of any
accepted hypothesis.

Margin convention is the repository's own (`eval/ladder.py:65`): **margin = best_log10_p − bar**, so a
**negative** margin means the bar was cleared (accepted) and a positive margin means it fell short.

Nothing is written to any dataset, manifest, criteria file or access log. The SPACE-DOPPLER and
SPACE-DOPPLER-MECH-01 datasets are not read at all.

    python eval/f4_margin.py run
    python eval/f4_margin.py report
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

from bench2 import _ber, _score as bench2_score              # noqa: E402  (both imported verbatim)
from modem import load_iq                                    # noqa: E402
from pipeline import analyze_iq                              # noqa: E402

PROTOCOL = os.path.join(HERE, 'f4_margin_protocol.json')
ROWS = os.path.join('results', 'f4_margin_rows.jsonl')

# The three read-only populations of the protocol. `kind` selects the correctness rule.
DATASETS = (('bench2_sealed', os.path.join('data', 'bench2', 'sealed'), 'bench2'),
            ('bench1_sealed', os.path.join('data', 'sealed'), 'bench1'),
            ('nullset', os.path.join('data', 'nullset'), 'nullset'))
NON_STATIC_CHANNELS = ('cfo_drift', 'phase_noise')           # protocol AMB-2
WORKERS = min(max(1, (os.cpu_count() or 2) - 1), 8)          # capped: this population is 1,810 files
# The null set is mixed (eval/nullset.py:39-42): these classes carry a catalogue code and a correct
# decode exists; the rest (noise, uncoded_bpsk, uncoded_qpsk, 8psk_k7) are true nulls.
NULLSET_CATALOGUE_CLASSES = ('k7', 'k5', 'k3')


def _code_label(code):
    """nullset.py's CODE_LABEL mapping, by name: a reported conv code -> its k-label."""
    for k in NULLSET_CATALOGUE_CLASSES:
        if code and f'conv_{k}_' in code:
            return k
    return code


def _correct(kind, gt, r):
    """(outcome, correct) under the rule each dataset already defines (protocol: correctness_scoring)."""
    if kind == 'bench2':
        outcome, _ = bench2_score(gt, r)
        return outcome, outcome in ('TP', 'TP_PARTIAL', 'REFUSED_OK')
    if kind == 'bench1':
        # sealed_test.py's rule: a conv K7 claim whose payload matches the recorded bits
        ok = (r['status'] == 'DECODED' and 'conv_k7' in (r['code'] or '')
              and _ber(r['payload_bits'], gt['original_bits']) < 0.01)
        return ('TP' if ok else ('FALSE_ACCEPT' if r['status'] == 'DECODED' else 'FN')), ok
    # nullset.py's rules. The null set is a MIXED population (eval/nullset.py:39-42): 900 true nulls
    # (noise, uncoded_bpsk, uncoded_qpsk, 8psk_k7 — any DECODED is a false accept) and 450
    # catalogue-coded files (k7/k5/k3 — a correct decode exists and is scored by nullset.correct_decode:
    # the code label, the interleaver and BER < 0.01 must all match).
    if gt['class'] in NULLSET_CATALOGUE_CLASSES:
        ok = (r['status'] == 'DECODED'
              and _code_label(r['code']) == gt['class']
              and list(r['interleaver'] or []) == list(gt.get('interleaver') or [])
              and _ber(r['payload_bits'], gt['original_bits']) < 0.01)
        if r['status'] == 'DECODED':
            return ('TP' if ok else 'FALSE_ACCEPT'), ok
        return 'FN', False
    ok = r['status'] != 'DECODED'
    return ('REFUSED_OK' if ok else 'FALSE_ACCEPT'), ok


def _row(job, r, runtime):
    dataset, path, kind, gt = job[0], job[1], job[2], job[3]
    f4 = r.get('block_code') or {}
    a4 = f4.get('accepted_hypothesis') or {}
    conv = a4.get('converged_codewords')
    f2 = r.get('stream_code') or {}
    best, bar = f4.get('best_log10_p'), f4.get('log10_threshold')
    channel = gt.get('channel')
    outcome, correct = _correct(kind, gt, r)
    return {
        'dataset': dataset, 'file': os.path.basename(path)[:-3],
        'cls': gt.get('class'), 'family': gt.get('family'), 'expected': gt.get('expected'),
        'channel': channel,
        'esn0_db': gt.get('esn0_db', (gt.get('params') or {}).get('esn0', gt.get('snr_db'))),
        'n_symbols': gt.get('n_symbols'),
        # protocol AMB-2: static unless the capture's channel class is one that moves the carrier
        'static': channel not in NON_STATIC_CHANNELS,
        'f4_best': best, 'f4_bar': bar,
        'f4_margin': None if (best is None or bar is None) else float(best - bar),
        'f4_accepted': bool(f4.get('accepted')),
        'f4_code': a4.get('code'), 'f4_family': a4.get('family'),
        'f4_offset': a4.get('offset'), 'f4_randomizer': a4.get('randomizer'),
        'n_codewords': a4.get('n_codewords'),
        'n_converged': None if conv is None else int(sum(conv)),
        'zero_convergence': None if conv is None else bool(sum(conv) == 0),
        'f4_rejected': [x.get('structural_rejection')
                        for x in (f4.get('significant_but_rejected') or [])],
        'f2_accepted': bool(f2.get('accepted')),
        'f2_code': f2.get('code') if f2.get('accepted') else None,
        'status': r['status'], 'final_code': r['code'], 'final_modulation': r['modulation'],
        'outcome': outcome, 'correct': correct, 'runtime': runtime,
    }


def _run_one(job):
    path = job[1]
    t = time.perf_counter()
    r = analyze_iq(load_iq(path))                            # SHIPPED ENGINE, unmodified
    return _row(job, r, time.perf_counter() - t)


def jobs():
    out = []
    for dataset, d, kind in DATASETS:
        for path in sorted(glob.glob(os.path.join(d, '*.iq'))):
            gt = json.load(open(path + '.gt.json', encoding='utf-8'))
            out.append((dataset, path, kind, gt))
    return out


def run():
    js = jobs()
    counts = Counter(j[0] for j in js)
    print(f'{len(js)} captures, read-only: ' + ', '.join(f'{k} {v}' for k, v in counts.items()))
    print(f'shipped engine only (no ablation, no correction); {WORKERS} workers')
    os.makedirs('results', exist_ok=True)
    t0 = time.perf_counter()
    rows = []
    with Pool(WORKERS) as pool, open(ROWS, 'w', encoding='utf-8') as f:
        for i, row in enumerate(pool.imap_unordered(_run_one, js, chunksize=4)):
            f.write(json.dumps(row) + '\n')
            rows.append(row)
            if (i + 1) % 200 == 0:
                print(f'{i + 1}/{len(js)}', flush=True)
    print(f'{len(rows)} analyses in {time.perf_counter() - t0:.0f}s -> {ROWS}')
    print(f'  F4 accepted: {sum(1 for r in rows if r["f4_accepted"])}')
    print(f'  zero-convergence accepts: {sum(1 for r in rows if r["zero_convergence"])}')


def _sha256(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def _rows():
    if not os.path.exists(ROWS):
        sys.exit(f'no rows at {ROWS} — run first')
    return [json.loads(l) for l in open(ROWS, encoding='utf-8')]


def _summarise(label, rs):
    m = np.array([r['f4_margin'] for r in rs if r['f4_margin'] is not None])
    acc = sum(1 for r in rs if r['f4_accepted'])
    if not len(m):
        print(f'  {label:36} n={len(rs):5}  (no F4 evaluation)')
        return
    print(f'  {label:36} n={len(rs):5}  F4 accepts {acc:3}  margin min {m.min():+7.3f}  '
          f'median {np.median(m):+7.3f}  within 0.5 {int(((m > 0) & (m < 0.5)).sum()):4}  '
          f'within 1.0 {int(((m > 0) & (m < 1.0)).sum()):4}')


def report():
    rows = _rows()
    print(f'\nSPACE-F4-MARGIN-01 — {len(rows)} captures; protocol sha256 {_sha256(PROTOCOL)[:16]}…')
    print('margin = F4 best_log10_p − bar (eval/ladder.py:65); NEGATIVE = accepted\n')

    print('BY POPULATION')
    for dataset, _, _ in DATASETS:
        _summarise(dataset, [r for r in rows if r['dataset'] == dataset])
    print('\nSTATIC vs NON-STATIC (protocol AMB-2)')
    _summarise('static (primary population)', [r for r in rows if r['static']])
    _summarise('non-static (cfo_drift/phase_noise)', [r for r in rows if not r['static']])
    print('\nbench-v2 sealed BY CHANNEL CLASS')
    for ch in sorted({r['channel'] for r in rows if r['dataset'] == 'bench2_sealed' and r['channel']}):
        _summarise(ch + ('  [NON-STATIC]' if ch in NON_STATIC_CHANNELS else ''),
                   [r for r in rows if r['dataset'] == 'bench2_sealed' and r['channel'] == ch])
    print('\nbench-v2 sealed BY GROUND-TRUTH CLASS (families of section 11.1.9 first)')
    for fam in sorted({r['cls'] for r in rows if r['dataset'] == 'bench2_sealed' and r['cls']}):
        _summarise(fam, [r for r in rows if r['dataset'] == 'bench2_sealed' and r['cls'] == fam])

    print('\nQ2/Q3 — EVERY F4 ACCEPTANCE')
    acc = [r for r in rows if r['f4_accepted']]
    if not acc:
        print('  none in this population')
    for r in sorted(acc, key=lambda r: r['f4_margin']):
        print(f"  {r['dataset']}/{r['file']}: {r['f4_code']} ({r['f4_family']}) margin "
              f"{r['f4_margin']:+.3f}  converged {r['n_converged']}/{r['n_codewords']}  "
              f"final {r['final_code']} / {r['final_modulation']}  gt {r['cls']}  "
              f"outcome {r['outcome']}  correct {r['correct']}")

    print('\nQ1 — CLOSEST REJECTED CASES (smallest positive margin; shipped engine)')
    near = sorted((r for r in rows if r['f4_margin'] is not None and not r['f4_accepted']),
                  key=lambda r: r['f4_margin'])[:10]
    for r in near:
        print(f"  {r['dataset']}/{r['file']}: margin {r['f4_margin']:+.3f}  gt {r['cls']}  "
              f"channel {r['channel']}  Es/N0 {r['esn0_db']}  status {r['status']}  "
              f"final {r['final_code']}  correct {r['correct']}")

    print('\nQ4 — DID AN F4 ACCEPT EVER SUPPLY A WRONG PUBLISHED STRUCTURE?')
    wrong = [r for r in acc if not r['correct']]
    print(f'  F4 accepts with an incorrect published structure: {len(wrong)}')
    for r in wrong:
        print(f"   {r['dataset']}/{r['file']}: final {r['final_code']} vs gt {r['cls']} — {r['outcome']}")
    nullacc = [r for r in rows if r['dataset'] == 'nullset' and r['f4_accepted']]
    print(f'  F4 accepts on null-set captures (any would be a false accept): {len(nullacc)}')

    print('\nCONTEXT — outcomes by population (the shipped engine on this run)')
    for dataset, _, _ in DATASETS:
        rs = [r for r in rows if r['dataset'] == dataset]
        print(f'  {dataset:14} {dict(Counter(r["outcome"] for r in rs))}')
    fa = [r for r in rows if r['outcome'] == 'FALSE_ACCEPT']
    print(f'  FALSE_ACCEPT total: {len(fa)}'
          + (f' -> {[(r["dataset"], r["file"]) for r in fa[:5]]}' if fa else ''))

    print('\nF4 STRUCTURAL REJECTIONS THAT DID FIRE')
    rej = defaultdict(int)
    for r in rows:
        for reason in r['f4_rejected']:
            rej[(reason or '')[:60]] += 1
    for k, v in sorted(rej.items(), key=lambda kv: -kv[1]):
        print(f'  {v:5}  {k}')
    if not rej:
        print('  none')

    rt = [r['runtime'] for r in rows]
    print(f'\nruntime mean {np.mean(rt):.2f}s max {max(rt):.2f}s')


def demo():
    """Self-check on the row extraction and the margin convention, on one existing capture."""
    path = sorted(glob.glob(os.path.join('data', 'sealed', '*.iq')))[0]
    gt = json.load(open(path + '.gt.json', encoding='utf-8'))
    r = analyze_iq(load_iq(path))
    row = _row(('bench1_sealed', path, 'bench1', gt), r, 0.0)
    assert row['f4_margin'] is None or np.isclose(row['f4_margin'], row['f4_best'] - row['f4_bar'])
    # the sign convention must agree with eval/ladder.py:65 — negative means accepted
    assert (row['f4_margin'] is None) or (row['f4_accepted'] == (row['f4_margin'] <= 0))
    assert row['static'] is True and row['dataset'] == 'bench1_sealed'
    assert row['outcome'] in ('TP', 'FALSE_ACCEPT', 'FN')
    print('demo: row extraction and margin convention self-checks pass on', os.path.basename(path))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'demo'
    os.chdir(ROOT)
    {'run': run, 'report': report, 'demo': demo}[cmd]()
