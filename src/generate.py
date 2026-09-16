"""Deterministic signal generator for SIH26147 benchmarks."""

import numpy as np
import json
import os
from modem import modulate, pulse_shape, channel, save_iq, rrc_filter
from fec import conv_encode, block_interleave


def generate_signal(seed, mod, snr_db, sps, interleaver_dims, beta=0.35,
                    n_info_bits=400, fs=1e6):
    """Generate one test signal with known parameters.
    Returns (iq_signal, ground_truth_dict).
    """
    rng = np.random.RandomState(seed)

    # Random info bits
    info_bits = rng.randint(0, 2, size=n_info_bits).astype(np.uint8)

    # FEC encode (K=7, rate-1/2, generators 171/133 octal = NASA/CCSDS)
    generators = [0o171, 0o133]
    K = 7
    coded_bits = conv_encode(info_bits, generators, K)

    # Block interleave
    rows, cols = interleaver_dims
    interleaved = block_interleave(coded_bits, rows, cols)

    # Modulate
    symbols = modulate(interleaved, mod)

    # Pulse shape (RRC)
    h = rrc_filter(beta, sps)
    sig = pulse_shape(symbols, sps, h)

    # Channel
    cfo = rng.uniform(-0.01, 0.01)
    timing_offset = rng.uniform(-0.5, 0.5)
    phase_offset = rng.uniform(0, 2 * np.pi)

    sig_ch, noise_var = channel(sig, snr_db, cfo, timing_offset, phase_offset, rng)

    gt = {
        'seed': int(seed),
        'modulation': mod,
        'snr_db': float(snr_db),
        'symbol_rate': float(fs / sps),
        'sps': int(sps),
        'interleaver': [int(rows), int(cols)],
        'beta': float(beta),
        'cfo': float(cfo),
        'timing_offset': float(timing_offset),
        'phase_offset': float(phase_offset),
        'n_info_bits': int(n_info_bits),
        'n_coded_bits': int(len(coded_bits)),
        'n_interleaved_bits': int(len(interleaved)),
        'n_symbols': int(len(symbols)),
        'original_bits': info_bits.tolist(),
        'fs': float(fs),
    }

    return sig_ch, gt


def generate_dataset(output_dir, seed0, n_files, param_set='train'):
    """Generate a full dataset.
    param_set: 'train' or 'sealed'
    """
    os.makedirs(output_dir, exist_ok=True)

    if param_set == 'train':
        snrs = [0, 3, 6, 10, 15]
        sps_vals = [4, 8]
        interleavers = [(4, 8), (8, 8), (8, 16)]
        betas = [0.35]
    elif param_set == 'sealed':
        snrs = [2, 5, 8, 12]
        sps_vals = [6]
        interleavers = [(6, 10), (10, 12)]
        betas = [0.25, 0.5]
    else:
        raise ValueError(f"Unknown param_set: {param_set}")

    mods = ['BPSK', 'QPSK']
    files_generated = []

    for i in range(n_files):
        seed = seed0 + i
        rng_params = np.random.RandomState(seed)

        mod = mods[rng_params.randint(0, len(mods))]
        snr = snrs[rng_params.randint(0, len(snrs))]
        sps = sps_vals[rng_params.randint(0, len(sps_vals))]
        il = interleavers[rng_params.randint(0, len(interleavers))]
        beta = betas[rng_params.randint(0, len(betas))]

        sig, gt = generate_signal(seed, mod, snr, sps, il, beta)

        fname = f"test_{i:03d}"
        iq_path = os.path.join(output_dir, f"{fname}.iq")
        gt_path = os.path.join(output_dir, f"{fname}.iq.gt.json")

        save_iq(iq_path, sig)
        with open(gt_path, 'w') as f:
            json.dump(gt, f, indent=2)

        files_generated.append(fname)
        if (i + 1) % 10 == 0:
            print(f"Generated {i+1}/{n_files}")

    return files_generated


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'sealed':
        print("Generating sealed test set (30 files)...")
        generate_dataset('data/sealed', seed0=99000, n_files=30, param_set='sealed')
        print("Done.")
    elif len(sys.argv) > 1 and sys.argv[1] == 'train':
        print("Generating train set (100 files)...")
        generate_dataset('data/train', seed0=1000, n_files=100, param_set='train')
        print("Done.")
    else:
        print("Generating sealed test set (30 files)...")
        generate_dataset('data/sealed', seed0=99000, n_files=30, param_set='sealed')
        print("Done.")
