"""Acceptance-rule experiment: wrong-structure null + structural consistency rules.

usage:
  python eval/acceptance.py run       # receiver (top-20 hypotheses logged) → results/acceptance_rows.jsonl
  python eval/acceptance.py report    # calibrate on even-indexed files, report on odd-indexed files

Runs:
  null      data/nullset, every file, normal blind search
  wrongnull every coded data/nullset file with its TRUE interleaver removed from the candidates
            (nothing correct is left, so any DECODED is a false accept)
  bench-v1  data/sealed, data/train (development-contaminated; reported in full, not used to tune)

Rules (each walks the top-20 hypotheses in p-value order and accepts the first one that is
significant under the shipped Bonferroni threshold AND survives its filters):
  R0  shipped: sign test only
  MC  modulation consistency: drop QPSK hypotheses when BPSK presence is significant (p ≤ α),
      drop BPSK hypotheses when the BPSK-consistency count contradicts BPSK (p ≤ α). α = 0.01, untuned.
  BL  block-length consistency: drop hypotheses with covered symbols < active symbols − Δ,
      Δ = 99th percentile of (active − covered) over correct hypotheses in the calibration split.
  RM  runner-up margin: require log10 p of the best hypothesis with a different (code, interleaver)
      to be ≥ m above the accepted one; m chosen on the calibration split.
  PM  path-metric floor t = 99th percentile of top-1 path metric over calibration null files.
"""

import glob
import json
import os
import sys
from multiprocessing import Pool

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'src'))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding='utf-8')

from modem import load_iq                 # noqa: E402
from pipeline import analyze_iq, ALPHA    # noqa: E402

CODE_LABEL = {'conv_k7_r12_171_133': 'k7', 'conv_k5_r12_23_35': 'k5', 'conv_k3_r12_7_5': 'k3'}
CODED = ('k7', 'k5', 'k3')
NULL = ('noise', 'uncoded_bpsk', 'uncoded_qpsk', '8psk_k7')


def _ber(d, o):
    d, o = np.asarray(d), np.asarray(o)
    L = min(len(d), len(o))
    return 1.0 if L == 0 else float(min(np.mean(d[:L] != o[:L]), np.mean((1 - d[:L]) != o[:L])))


def run_one(job):
    kind, path = job
    gt = json.load(open(path + '.gt.json'))
    if 'class' in gt:
        cls, true_code = gt['class'], (gt['class'] if gt['class'] in CODED else None)
    else:                                   # bench-v1: always K7
        cls, true_code = 'k7', 'k7'
    oracle = {'exclude_interleaver': tuple(gt['interleaver'])} if kind == 'wrongnull' else None
    r = analyze_iq(load_iq(path), _oracle=oracle, _top_k=20, _keep_bits=True)
    tops = []
    for h in r['diagnostics']['top_hypotheses']:
        bits = h.pop('decoded_bits')
        h['correct'] = bool(kind != 'wrongnull' and true_code is not None
                            and CODE_LABEL[h['code']] == true_code
                            and list(h['interleaver']) == list(gt['interleaver'] or [])
                            and _ber(bits, gt['original_bits']) < 0.01)
        tops.append({k: h[k] for k in ('code', 'interleaver', 'modulation', 'sps', 'log10_p',
                                       'path_metric', 'covered_symbols', 'active_symbols',
                                       'bpsk_presence_log10p', 'bpsk_contradiction_log10p',
                                       'correct')})
    name = os.path.basename(path)[:-3]
    return {'kind': kind, 'dataset': os.path.basename(os.path.dirname(path)), 'file': name,
            'index': int(name.split('_')[-1]), 'class': cls,
            'coded_bits': gt.get('coded_bits', gt.get('n_interleaved_bits')),
            'log10_threshold': r['accept']['log10_threshold'], 'shipped_status': r['status'],
            'top': tops}


def run():
    jobs = [('null', p) for p in sorted(glob.glob('data/nullset/*.iq'))]
    jobs += [('wrongnull', p) for p in sorted(glob.glob('data/nullset/k[357]_*.iq'))]
    jobs += [('bench', p) for d in ('data/sealed', 'data/train') for p in sorted(glob.glob(d + '/*.iq'))]
    os.makedirs('results', exist_ok=True)
    with Pool(max(1, (os.cpu_count() or 2) - 1)) as pool, open('results/acceptance_rows.jsonl', 'w') as f:
        for i, row in enumerate(pool.imap_unordered(run_one, jobs, chunksize=4)):
            f.write(json.dumps(row) + '\n')
            if (i + 1) % 200 == 0:
                print(f'{i + 1}/{len(jobs)}', flush=True)


LOG_ALPHA = np.log10(ALPHA)


def decide(row, rule, params):
    """Accepted hypothesis dict or None."""
    top = row['top']
    for h in top:
        if h['log10_p'] > row['log10_threshold']:
            return None
        if 'MC' in rule:
            if h['modulation'] == 'QPSK' and h['bpsk_presence_log10p'] <= LOG_ALPHA:
                continue
            if h['modulation'] == 'BPSK' and h['bpsk_contradiction_log10p'] <= LOG_ALPHA:
                continue
        if 'BL' in rule and h['covered_symbols'] < h['active_symbols'] - params['delta']:
            continue
        if 'PM' in rule and h['path_metric'] < params['t']:
            continue
        if 'RM' in rule:
            others = [o['log10_p'] for o in top if (o['code'], o['interleaver']) != (h['code'], h['interleaver'])]
            if others and min(others) - h['log10_p'] < params['m']:
                continue
        return h
    return None


def wilson_hi(k, n, z=1.96):
    if n == 0:
        return 1.0
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    return min(1.0, c + z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n))


def metrics(rows, rule, params):
    null = [r for r in rows if r['kind'] == 'null' and r['class'] in NULL]
    coded = [r for r in rows if r['kind'] == 'null' and r['class'] in CODED]
    wrong = [r for r in rows if r['kind'] == 'wrongnull']
    acc = {id(r): decide(r, rule, params) for r in null + coded + wrong}
    tp = sum(1 for r in coded if acc[id(r)] is not None and acc[id(r)]['correct'])
    wh = sum(1 for r in coded if acc[id(r)] is not None and not acc[id(r)]['correct'])
    nf = sum(1 for r in null if acc[id(r)] is not None)
    wf = sum(1 for r in wrong if acc[id(r)] is not None)
    return {'recall': tp / max(len(coded), 1), 'wrong_hyp': wh, 'n_coded': len(coded),
            'null_fa': nf, 'n_null': len(null), 'wrongnull_fa': wf, 'n_wrong': len(wrong)}


def calibrate(calib):
    slack = [h['active_symbols'] - h['covered_symbols'] for r in calib
             if r['kind'] == 'null' and r['class'] in CODED for h in r['top'][:1] if h['correct']]
    delta = float(np.percentile(slack, 99)) if slack else 0.0
    pm_null = [r['top'][0]['path_metric'] for r in calib
               if r['kind'] == 'null' and r['class'] in NULL and r['top']]
    t = float(np.percentile(pm_null, 99)) if pm_null else 0.0
    base = metrics(calib, 'R0', {})
    best_m = 0.0
    for m in (0.0, 0.5, 1.0, 2.0, 3.0, 5.0):   # largest margin costing at most 2 recall points
        mm = metrics(calib, 'R0+RM', {'m': m})
        if base['recall'] - mm['recall'] <= 0.02:
            best_m = m
    return {'delta': delta, 't': t, 'm': best_m}


RULES = ['R0', 'R0+MC', 'R0+BL', 'R0+RM', 'R0+PM', 'R0+MC+BL', 'R0+MC+BL+RM', 'R0+MC+BL+PM']


def report():
    rows = [json.loads(line) for line in open('results/acceptance_rows.jsonl')]
    search = [r for r in rows if r['kind'] in ('null', 'wrongnull')]
    calib = [r for r in search if r['index'] % 2 == 0]
    evals = [r for r in search if r['index'] % 2 == 1]
    params = calibrate(calib)
    print('# Acceptance-rule experiment\n')
    print(f"Calibration split (even file index): {len(calib)} runs → Δ = {params['delta']:.1f} symbols, "
          f"path-metric floor t = {params['t']:.3f}, margin m = {params['m']:.1f} decades. "
          f"MC uses α = {ALPHA} with no tuning.\n")
    for split_name, split in (('Evaluation split (odd file index)', evals), ('Calibration split', calib)):
        print(f'## {split_name}\n')
        print('| rule | recall (coded) | wrong-hypothesis accepts | null false accepts | wrong-structure accepts |')
        print('|---|---|---|---|---|')
        for rule in RULES:
            m = metrics(split, rule, params)
            print(f"| {rule} | {m['recall']:.3f} ({round(m['recall'] * m['n_coded'])}/{m['n_coded']}) | "
                  f"{m['wrong_hyp']}/{m['n_coded']} ({100 * m['wrong_hyp'] / m['n_coded']:.1f}%, ≤{100 * wilson_hi(m['wrong_hyp'], m['n_coded']):.1f}%) | "
                  f"{m['null_fa']}/{m['n_null']} (≤{100 * wilson_hi(m['null_fa'], m['n_null']):.1f}%) | "
                  f"{m['wrongnull_fa']}/{m['n_wrong']} (≤{100 * wilson_hi(m['wrongnull_fa'], m['n_wrong']):.1f}%) |")
        print()
    bench = [r for r in rows if r['kind'] == 'bench']
    print('## bench-v1 (all files; development-contaminated, not used for calibration)\n')
    print('| rule | sealed pass | sealed false accept | train pass | train false accept |\n|---|---|---|---|---|')
    for rule in RULES:
        cells = []
        for ds in ('sealed', 'train'):
            rs = [r for r in bench if r['dataset'] == ds]
            dec = [decide(r, rule, params) for r in rs]
            cells += [f"{sum(1 for h in dec if h is not None and h['correct'])}/{len(rs)}",
                      str(sum(1 for h in dec if h is not None and not h['correct']))]
        print(f"| {rule} | " + ' | '.join(cells) + ' |')
    json.dump(params, open('results/acceptance_params.json', 'w'), indent=1)


if __name__ == '__main__':
    {'run': run, 'report': report}[sys.argv[1]]()
