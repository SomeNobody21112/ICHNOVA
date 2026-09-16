"""Sealed benchmark harness for SIH26147."""

import sys
import os
import json
import time
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from pipeline import analyze_file


def complement_tolerant_ber(decoded, original):
    """BER with complement tolerance (handles 180° phase ambiguity)."""
    d = np.asarray(decoded, dtype=np.uint8)
    o = np.asarray(original, dtype=np.uint8)
    L = min(len(d), len(o))
    if L == 0:
        return 1.0
    ber_direct = np.mean(d[:L] != o[:L])
    ber_complement = np.mean((1 - d[:L]) != o[:L])
    return min(ber_direct, ber_complement)


def run_sealed_test(data_dir='data/sealed', n_files=30, verbose=True):
    """Run the sealed benchmark."""
    successes = 0
    failures = []
    results = []
    total_time = 0

    for i in range(n_files):
        fname = f"test_{i:03d}"
        iq_path = os.path.join(data_dir, f"{fname}.iq")
        gt_path = os.path.join(data_dir, f"{fname}.iq.gt.json")

        if not os.path.exists(iq_path):
            print(f"SKIP {fname}: file not found")
            continue

        with open(gt_path) as f:
            gt = json.load(f)

        t0 = time.time()
        result = analyze_file(iq_path, verbose=False)
        elapsed = time.time() - t0
        total_time += elapsed

        original_bits = np.array(gt['original_bits'], dtype=np.uint8)
        ber = complement_tolerant_ber(result['payload_bits'], original_bits)

        status = 'OK' if (ber < 0.01 and result['consistency'] >= 0.75) else 'FAIL'
        if status == 'OK':
            successes += 1
        else:
            failures.append(fname)

        result_entry = {
            'file': fname,
            'gt_mod': gt['modulation'],
            'gt_snr': gt['snr_db'],
            'gt_symbol_rate': gt['symbol_rate'],
            'gt_sps': gt['sps'],
            'gt_interleaver': gt['interleaver'],
            'gt_beta': gt['beta'],
            'est_symbol_rate': result['symbol_rate_est'],
            'est_mod': result['modulation'],
            'consistency': result['consistency'],
            'ber': float(ber),
            'status': status,
            'runtime': elapsed,
            'code': result['code'],
            'interleaver_est': result['interleaver'],
        }
        results.append(result_entry)

        if verbose:
            sym_err = abs(result['symbol_rate_est'] - gt['symbol_rate']) / gt['symbol_rate'] * 100
            print(f"{fname}: {status} | {gt['modulation']} {gt['snr_db']:.0f}dB "
                  f"sps={gt['sps']} β={gt['beta']:.2f} | "
                  f"cons={result['consistency']:.3f} BER={ber:.4f} "
                  f"sym_err={sym_err:.1f}% | {elapsed:.1f}s")

    print(f"\n{'='*60}")
    print(f"RESULT: {successes}/{n_files}")
    print(f"Total time: {total_time:.1f}s  Mean: {total_time/max(n_files,1):.1f}s")
    if failures:
        print(f"Failures: {', '.join(failures)}")
    print(f"{'='*60}")

    # Save results
    os.makedirs('results', exist_ok=True)
    with open('results/sealed_results.json', 'w') as f:
        json.dump({
            'successes': successes,
            'total': n_files,
            'failures': failures,
            'total_time': total_time,
            'results': results,
        }, f, indent=2)

    return successes, n_files, results


if __name__ == '__main__':
    successes, total, results = run_sealed_test()
    sys.exit(0 if successes >= 28 else 1)
