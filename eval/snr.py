"""SNR definitions for SIH26147 benchmark files (evaluation only).

The generator (src/modem.channel) sets the *per-sample* SNR over the whole capture:
    snr_lin = mean(|s[n]|²) / σ²,  σ² = complex noise variance per sample,
where s = pulse_shape(symbols) uses a unit-energy RRC filter and unit-energy symbols.
With n_sym symbols and L = n_sym·sps + ntaps − 1 samples (ntaps = 10·sps + 1), the total
signal energy is n_sym·Es (Es = 1), so mean(|s|²) = n_sym/L and σ² = n_sym/(L·snr_lin).
A unit-energy matched filter leaves N0 = σ² per symbol sample, hence

    Es/N0 = 1/σ² = snr_lin · L / n_sym                            (≈ snr_lin·sps, plus the tail)
    Ec/N0 (per coded bit)  = Es/N0 / bits_per_symbol              (BPSK 1, QPSK 2)
    Eb/N0 (per info bit)   = Es/N0 / (bits_per_symbol · R)        (R = 1/2 for the K=7 code)

`measured_esn0_db` checks this independently: genie matched filter at the true CFO, β and
sps, a least-squares complex gain onto the true transmitted symbols, Es/N0 = |g|²/var(error).
"""

import os
import sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.stdout.reconfigure(encoding='utf-8')

from modem import rrc_filter, modulate                  # noqa: E402
from fec import conv_encode, block_interleave           # noqa: E402
from analyze import matched_filter_demod                # noqa: E402

BITS_PER_SYMBOL = {'BPSK': 1, 'QPSK': 2}


def snr_from_gt(gt, code_rate=0.5):
    """Per-sample SNR, Es/N0, Ec/N0 and Eb/N0 in dB from a ground-truth dict."""
    sps, n_sym = gt['sps'], gt['n_symbols']
    L = n_sym * sps + 10 * sps          # len(pulse_shape) = n_sym·sps + ntaps − 1
    esn0 = gt['snr_db'] + 10 * np.log10(L / n_sym)
    bps = BITS_PER_SYMBOL[gt['modulation']]
    return {'snr_per_sample_db': gt['snr_db'],
            'esn0_db': float(esn0),
            'ecn0_db': float(esn0 - 10 * np.log10(bps)),
            'ebn0_db': float(esn0 - 10 * np.log10(bps * code_rate))}


def measured_esn0_db(iq, gt):
    """Independent Es/N0 measurement from the samples (genie parameters)."""
    il = block_interleave(conv_encode(np.array(gt['original_bits'], dtype=np.uint8),
                                      [0o171, 0o133], 7), *gt['interleaver'])
    ref = modulate(il, gt['modulation'])
    iq = iq * np.exp(-2j * np.pi * gt['cfo'] * np.arange(len(iq)))
    rx = matched_filter_demod(iq, rrc_filter(gt['beta'], gt['sps']), gt['sps'])[:len(ref)]
    g = np.vdot(ref, rx) / np.vdot(ref, ref)
    err = rx - g * ref
    return float(10 * np.log10(np.abs(g) ** 2 * np.mean(np.abs(ref) ** 2) / np.mean(np.abs(err) ** 2)))


if __name__ == '__main__':
    import glob
    import json
    from modem import load_iq
    for ds in sys.argv[1:] or ['data/sealed', 'data/train']:
        diffs = []
        for p in sorted(glob.glob(os.path.join(ds, '*.iq'))):
            gt = json.load(open(p + '.gt.json'))
            diffs.append(measured_esn0_db(load_iq(p), gt) - snr_from_gt(gt)['esn0_db'])
        d = np.array(diffs)
        print(f'{ds}: measured − formula Es/N0 over {len(d)} files: '
              f'median {np.median(d):+.2f} dB, 5–95% [{np.percentile(d, 5):+.2f}, {np.percentile(d, 95):+.2f}] dB')
