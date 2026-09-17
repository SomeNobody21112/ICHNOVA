"""Benchmark harness for SIH26147.

usage: python sealed_test.py [data_dir] [n_files] [--min-pass N] [--max-false-accept N]

A file PASSES when the receiver returns status DECODED and the payload BER < 0.01
(complement-tolerant: the catalogue codes cannot resolve a 180° phase flip).
A FALSE ACCEPT is DECODED with BER ≥ 0.01. UNKNOWN / SIGNAL_NO_CODE are refusals, not passes.

bench-v1 (data/sealed, seed0 99000) is a regression tripwire only: development-contaminated,
truncated payload (30–60 of 400 bits transmitted), not a genuine holdout.

Writes results/<dataset>_results.json and results/<dataset>_diagnostics.jsonl
(ground truth + full receiver diagnostics per file; evaluation artifacts only).
"""

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from collections import Counter

import numpy as np
import scipy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'src'))
sys.path.insert(0, os.path.join(HERE, 'eval'))
sys.stdout.reconfigure(encoding='utf-8')  # Windows consoles choke on 'β'

from pipeline import analyze_file   # noqa: E402
from snr import snr_from_gt         # noqa: E402


def complement_tolerant_ber(decoded, original):
    """BER with complement tolerance (handles 180° phase ambiguity)."""
    d = np.asarray(decoded, dtype=np.uint8)
    o = np.asarray(original, dtype=np.uint8)
    L = min(len(d), len(o))
    if L == 0:
        return 1.0
    return float(min(np.mean(d[:L] != o[:L]), np.mean((1 - d[:L]) != o[:L])))


def run_metadata():
    try:
        commit = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=HERE,
                                         text=True).strip()
        dirty = bool(subprocess.check_output(['git', 'status', '--porcelain', '--', 'src'],
                                             cwd=HERE, text=True).strip())
    except Exception:
        commit, dirty = 'unknown', None
    return {'commit': commit, 'src_dirty': dirty, 'python': platform.python_version(),
            'numpy': np.__version__, 'scipy': scipy.__version__, 'platform': platform.platform()}


def run_benchmark(data_dir='data/sealed', n_files=30, verbose=True):
    name = os.path.basename(os.path.normpath(data_dir))
    os.makedirs('results', exist_ok=True)
    rows, statuses = [], Counter()
    t_total = time.perf_counter()
    with open(os.path.join('results', f'{name}_diagnostics.jsonl'), 'w') as diag_file:
        for i in range(n_files):
            fname = f"test_{i:03d}"
            iq_path = os.path.join(data_dir, f"{fname}.iq")
            if not os.path.exists(iq_path):
                print(f"SKIP {fname}: file not found")
                continue
            with open(iq_path + '.gt.json') as f:
                gt = json.load(f)

            r = analyze_file(iq_path, fs=gt.get('fs'), fs_source='declared' if gt.get('fs') else None)
            ber = complement_tolerant_ber(r['payload_bits'], gt['original_bits'])
            decoded = r['status'] == 'DECODED'
            outcome = ('PASS' if decoded and ber < 0.01 else
                       'FALSE_ACCEPT' if decoded else r['status'])
            statuses[outcome] += 1
            snr = snr_from_gt(gt)
            row = {
                'file': fname, 'outcome': outcome, 'status': r['status'], 'ber': ber,
                'decoded_len': int(len(r['payload_bits'])),
                'payload_bits_transmitted': int(gt['n_interleaved_bits'] // 2),
                'gt_mod': gt['modulation'], 'gt_sps': gt['sps'], 'gt_beta': gt['beta'],
                'gt_interleaver': gt['interleaver'], **{f'gt_{k}': v for k, v in snr.items()},
                'est_mod': r['modulation'], 'est_sps': r['sps'], 'est_code': r['code'],
                'est_interleaver': r['interleaver'],
                'log10_p': r['accept']['log10_p'], 'log10_threshold': r['accept']['log10_threshold'],
                'n_hypotheses': r['accept']['n_hypotheses'], 'runtime': r['runtime'],
            }
            rows.append(row)
            diag = {'file': fname, 'ground_truth': {k: v for k, v in gt.items() if k != 'original_bits'},
                    'snr': snr, 'outcome': outcome, 'ber': ber,
                    **{k: v for k, v in r.items() if k != 'payload_bits'}}
            diag_file.write(json.dumps(diag, default=_json_default) + '\n')

            if verbose:
                print(f"{fname}: {outcome:14s} | {gt['modulation']} Es/N0={snr['esn0_db']:4.1f}dB "
                      f"(per-sample {gt['snr_db']:.0f}dB) sps={gt['sps']} β={gt['beta']:.2f} | "
                      f"est {r['modulation']} sps={r['sps']} {r['code']} {r['interleaver']} "
                      f"log10p={r['accept']['log10_p']:.1f}/{r['accept']['log10_threshold']:.1f} "
                      f"BER={ber:.3f} | {r['runtime']:.1f}s")

    total_time = time.perf_counter() - t_total
    passes = statuses['PASS']
    summary = {
        'dataset': name, 'metadata': run_metadata(), 'n_files': len(rows), 'passes': passes,
        'false_accepts': statuses['FALSE_ACCEPT'], 'outcomes': dict(statuses),
        'total_time': total_time, 'mean_time': total_time / max(len(rows), 1),
        'failures': [r['file'] for r in rows if r['outcome'] != 'PASS'], 'results': rows,
    }
    with open(os.path.join('results', f'{name}_results.json'), 'w') as f:
        json.dump(summary, f, indent=2, default=_json_default)

    print(f"\n{'=' * 60}")
    print(f"RESULT: {passes}/{len(rows)} decoded correctly | outcomes {dict(statuses)}")
    print(f"False accepts (DECODED, BER ≥ 0.01): {statuses['FALSE_ACCEPT']}")
    print(f"Total time: {total_time:.1f}s  Mean: {summary['mean_time']:.2f}s")
    print(f"{'=' * 60}")
    return summary


def _json_default(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('data_dir', nargs='?', default='data/sealed')
    ap.add_argument('n_files', nargs='?', type=int, default=30)
    ap.add_argument('--min-pass', type=int, default=None, help='fail (exit 1) below this many passes')
    ap.add_argument('--max-false-accept', type=int, default=None, help='fail above this many false accepts')
    args = ap.parse_args()
    s = run_benchmark(args.data_dir, args.n_files)
    ok = ((args.min_pass is None or s['passes'] >= args.min_pass) and
          (args.max_false_accept is None or s['false_accepts'] <= args.max_false_accept))
    sys.exit(0 if ok else 1)
