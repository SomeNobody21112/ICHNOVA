"""EXPERIMENTAL 8PSK / 16-QAM burst sweep (Constitution §12.1 catalogue, §24 EXPERIMENTAL row).

usage: python eval/higher_mod_sweep.py [n_seeds]

Measures what the off-by-default higher-modulation search actually achieves on bursts it is meant to
explain: modulation x burst interleaver type x Es/N0, decoded correctly (right modulation, right code,
right interleaver type and payload BER < 0.01) versus refused, plus any wrong decode. This is a
DEVELOPMENT measurement, not a benchmark: parameters are chosen here, nothing is held out, and the
default engine does not search these modulations at all (pipeline.SEARCH_HIGHER_MODULATIONS = False).
"""

import os
import sys
from collections import Counter
from multiprocessing import Pool

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'src'))
sys.stdout.reconfigure(encoding='utf-8')

import constellations as cs          # noqa: E402
import interleavers as il            # noqa: E402
import modem                         # noqa: E402
from fec import conv_encode          # noqa: E402
from pipeline import analyze_iq, CODE_CATALOGUE   # noqa: E402

K7 = CODE_CATALOGUE[0]
MODS = ('8PSK', '16QAM')
SPECS = (('block', 12, 16), ('diag', 12, 16), ('conv', 3, 2), ('qpp', 192, 23, 48))
ESN0_DB = (11, 14, 17, 20)


def _ber(d, o):
    d, o = np.asarray(d), np.asarray(o)
    L = min(len(d), len(o))
    return 1.0 if L == 0 else float(min(np.mean(d[:L] != o[:L]), np.mean(d[:L] != 1 - o[:L])))


def run_one(job):
    mod, spec, esn0, seed = job
    rng = np.random.RandomState(seed)
    sps, beta = int(rng.choice([4, 6, 8])), float(rng.uniform(0.2, 0.5))
    cfo, phase = float(rng.uniform(-0.01, 0.01)), float(rng.uniform(0, 2 * np.pi))
    n_coded = spec[1] if spec[0] == 'qpp' else spec[1] * spec[2]
    info = rng.randint(0, 2, n_coded // 2).astype(np.uint8)
    coded = conv_encode(info, K7['generators'], 7)[:n_coded]
    bits = il.interleave(coded, spec)
    syms = cs.modulate(bits, mod)
    sig = modem.pulse_shape(syms, sps, modem.rrc_filter(beta, sps))
    snr_per_sample = esn0 - 10 * np.log10(len(sig) / len(syms))
    iq, _ = modem.channel(sig, snr_per_sample, cfo, 0.0, phase, rng)
    r = analyze_iq(iq, search_higher_modulations=True)
    right = (r['status'] == 'DECODED' and r['modulation'] == mod and r['code'] == K7['name']
             and (r['interleaver_spec'] or {}).get('type') == il.describe(spec)['type']
             and _ber(r['payload_bits'], info) < 0.01)
    return {'mod': mod, 'type': spec[0], 'esn0': esn0, 'status': r['status'], 'correct': right,
            'wrong_decode': r['status'] == 'DECODED' and not right,
            'n_hypotheses': r['accept']['n_hypotheses'], 'runtime': r['runtime']}


def main(n_seeds=3):
    jobs = [(m, s, e, 7000 + 13 * i) for m in MODS for s in SPECS for e in ESN0_DB
            for i in range(n_seeds)]
    with Pool(max(1, (os.cpu_count() or 2) - 1)) as pool:
        rows = pool.map(run_one, jobs)
    print(f'# EXPERIMENTAL higher-modulation burst sweep ({len(rows)} runs, {n_seeds} seeds per cell)\n')
    print('DEVELOPMENT measurement. The default engine does not search these modulations.\n')
    print('| modulation | interleaver | ' + ' | '.join(f'Es/N0={e}' for e in ESN0_DB) + ' | wrong decodes |')
    print('|---|---|' + '---|' * (len(ESN0_DB) + 1))
    for m in MODS:
        for s in SPECS:
            cells = []
            for e in ESN0_DB:
                rs = [r for r in rows if r['mod'] == m and r['type'] == s[0] and r['esn0'] == e]
                cells.append(f"{sum(r['correct'] for r in rs)}/{len(rs)}")
            wrong = sum(r['wrong_decode'] for r in rows if r['mod'] == m and r['type'] == s[0])
            print(f"| {m} | {il.describe(s)['type']} | " + ' | '.join(cells) + f' | {wrong} |')
    print(f"\nTotals: {sum(r['correct'] for r in rows)}/{len(rows)} correct, "
          f"{sum(r['wrong_decode'] for r in rows)} wrong decodes, "
          f"{Counter(r['status'] for r in rows)}")
    print(f"Mean hypotheses M1 {np.mean([r['n_hypotheses'] for r in rows]):.0f}, "
          f"mean runtime {np.mean([r['runtime'] for r in rows]):.2f} s, "
          f"max {np.max([r['runtime'] for r in rows]):.2f} s")


if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 3)
