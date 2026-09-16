"""Oracle ladder (evaluation only): which blind estimate is each failure waiting on?

usage: python eval/ladder.py data/sealed 30 [data/train 100 ...]

Stages are cumulative; each replaces one more receiver estimate with ground truth:
  O0 blind · O1 +modulation · O2 +sps · O3 +CFO · O4 +β · O5 +fractional timing
  O6 +phase/rotation · O7 +interleaver
Acceptance is never oracled: a stage passes only if the receiver itself returns DECODED
with payload BER < 0.01. Oracles also shrink the hypothesis count, which lowers the
acceptance bar, so a first pass at stage k can reflect a better estimate *or* a smaller
search; the O0 columns (true value's rank among the blind candidates) separate the two.

Writes results/<dataset>_ladder.json and prints a markdown table.
"""

import json
import os
import sys
from collections import Counter
from multiprocessing import Pool

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'src'))
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, HERE)

from modem import load_iq                 # noqa: E402
from pipeline import analyze_iq           # noqa: E402
from snr import snr_from_gt               # noqa: E402

STAGES = [('O0', None), ('O1', 'modulation'), ('O2', 'sps'), ('O3', 'cfo'), ('O4', 'beta'),
          ('O5', 'timing_offset'), ('O6', 'phase'), ('O7', 'interleaver')]
REASON = {'O0': 'passes blind', 'O1': 'modulation identification', 'O2': 'sps estimation',
          'O3': 'CFO estimation', 'O4': 'roll-off mismatch', 'O5': 'fractional timing',
          'O6': 'phase / rotation', 'O7': 'interleaver identification'}


def ber(decoded, original):
    d, o = np.asarray(decoded), np.asarray(original)
    L = min(len(d), len(o))
    return 1.0 if L == 0 else float(min(np.mean(d[:L] != o[:L]), np.mean((1 - d[:L]) != o[:L])))


def ladder_one(args):
    data_dir, fname = args
    path = os.path.join(data_dir, fname + '.iq')
    gt = json.load(open(path + '.gt.json'))
    iq = load_iq(path)
    row = {'file': fname, 'modulation': gt['modulation'], 'sps': gt['sps'],
           'esn0_db': round(snr_from_gt(gt)['esn0_db'], 1), 'interleaver': gt['interleaver']}
    oracle, first = {}, None
    for stage, key in STAGES:
        if key == 'interleaver':
            oracle[key] = tuple(gt['interleaver'])
        elif key == 'phase':
            oracle[key] = gt['phase_offset']
        elif key is not None:
            oracle[key] = gt[key]
        r = analyze_iq(iq, _oracle=dict(oracle))
        b = ber(r['payload_bits'], gt['original_bits'])
        ok = r['status'] == 'DECODED' and b < 0.01
        row[stage] = ('PASS' if ok else 'WRONG' if r['status'] == 'DECODED' else r['status'])
        row[stage + '_log10p_margin'] = round(r['accept']['log10_p'] - r['accept']['log10_threshold'], 2)
        if stage == 'O0':
            d = r['diagnostics']
            ranked = [t['sps'] for t in sorted(d['sps_table'], key=lambda t: -t['q4'])]
            row['O0_true_sps_q4_rank'] = ranked.index(gt['sps']) + 1 if gt['sps'] in ranked else None
            row['O0_true_sps_in_candidates'] = gt['sps'] in d['sps_candidates']
            tol = 1 / (4 * len(iq))   # one x⁴ periodogram bin
            cfo_hits = [i + 1 for i, c in enumerate(d['cfo_candidates']) if abs(c['cfo'] - gt['cfo']) < tol]
            row['O0_true_cfo_rank'] = cfo_hits[0] if cfo_hits else None
            ms = [m for m in d['modulation_stats'] if m['sps'] == gt['sps']]
            row['O0_modstat_at_true_sps'] = ms[0]['decision'] if ms else None
            row['O0_n_hypotheses'] = r['accept']['n_hypotheses']
            row['O0_runtime_s'] = round(r['runtime'], 2)
        if ok and first is None:
            first = stage
        if stage == 'O7' and first is None:
            top = r['diagnostics']['top_hypotheses']
            best_possible = -top[0]['n_checks'] * np.log10(2) if top else 0.0
            if r['status'] == 'DECODED':
                row['failure_reason'] = 'accepted with all oracles but payload wrong (decoder / SNR limit)'
            elif best_possible > r['accept']['log10_threshold']:
                row['failure_reason'] = (f"unprovable: {top[0]['n_checks']} checks give at best "
                                         f"log10p={best_possible:.1f} > threshold "
                                         f"{r['accept']['log10_threshold']:.1f}")
            else:
                row['failure_reason'] = 'insufficient code evidence with all oracles (SNR)'
    row['first_pass_stage'] = first
    if first is not None:
        row['failure_reason'] = REASON[first]
    return row


def main(argv):
    pairs = list(zip(argv[0::2], map(int, argv[1::2])))
    os.makedirs('results', exist_ok=True)
    for data_dir, n in pairs:
        name = os.path.basename(os.path.normpath(data_dir))
        jobs = [(data_dir, f'test_{i:03d}') for i in range(n)]
        with Pool(max(1, (os.cpu_count() or 2) - 1)) as pool:
            rows = pool.map(ladder_one, jobs)
        json.dump(rows, open(os.path.join('results', f'{name}_ladder.json'), 'w'), indent=1)
        cols = ['file', 'modulation', 'sps', 'esn0_db'] + [s for s, _ in STAGES] + ['first_pass_stage', 'failure_reason']
        print(f'\n### Oracle ladder: {name} ({n} files)\n')
        print('| ' + ' | '.join(cols) + ' |')
        print('|' + '---|' * len(cols))
        for r in rows:
            print('| ' + ' | '.join(str(r.get(c)) for c in cols) + ' |')
        print('\n| stage | cumulative passes | first passes here |\n|---|---|---|')
        for s, _ in STAGES:
            print(f"| {s} | {sum(r[s] == 'PASS' for r in rows)} | "
                  f"{sum(r['first_pass_stage'] == s for r in rows)} |")
        never = [r for r in rows if r['first_pass_stage'] is None]
        print(f'| never | — | {len(never)} |')
        print('\nFailure reasons (never pass):', dict(Counter(r['failure_reason'].split(':')[0] for r in never)))
        blind_fail = [r for r in rows if r['O0'] != 'PASS']
        print(f"O0 diagnostics over {len(blind_fail)} blind failures: true sps in candidates "
              f"{sum(bool(r['O0_true_sps_in_candidates']) for r in blind_fail)}, true CFO among candidates "
              f"{sum(r['O0_true_cfo_rank'] is not None for r in blind_fail)}, modulation statistic correct at true sps "
              f"{sum(r['O0_modstat_at_true_sps'] == r['modulation'] for r in blind_fail)}")


if __name__ == '__main__':
    main(sys.argv[1:] or ['data/sealed', '30', 'data/train', '100'])
