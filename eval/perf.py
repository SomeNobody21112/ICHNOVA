"""Performance as the hypothesis space grows (Constitution §23, §32; execution-log Phase 19).

usage: python eval/perf.py [--higher]

Measures, single-process so memory is attributable: runtime per file, peak RSS of the process, and
the hypothesis counts and survivors per family. Datasets: bench-v1 sealed and train, a sample of the
null set, and two long synthetic captures (a CCSDS concatenated chain and a TC LDPC CLTU) which are
where the frame and block-code families do real work. The demo machine has little memory, so peak RSS
is reported as well as the delta over the interpreter baseline.
"""

import glob
import json
import os
import sys
import time

import numpy as np
import psutil

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'src'))
sys.stdout.reconfigure(encoding='utf-8')

import framing                                    # noqa: E402
import ldpc                                       # noqa: E402
import modem                                      # noqa: E402
import rs                                         # noqa: E402
import stream                                     # noqa: E402
from fec import conv_encode                       # noqa: E402
from modem import load_iq                         # noqa: E402
from pipeline import analyze_iq                   # noqa: E402

PROC = psutil.Process()
MB = 1024 * 1024


def _rss():
    return PROC.memory_info().rss / MB


def _long_ccsds(rng, n_frames=4):
    asm = framing.MARKERS['ASM_1ACFFC1D']
    frames = []
    for _ in range(n_frames):
        info = rng.randint(0, 256, rs.code(16).k).astype(np.int64)
        bits = rs.symbols_to_bits(rs.encode_codeblock(info, 16, 1, 0))
        frames.append(np.concatenate([asm, bits ^ framing.pn_sequence('tm_131071', len(bits))]))
    coded = conv_encode(np.concatenate(frames).astype(np.uint8), stream.CODE['generators'], 7)
    sig = modem.pulse_shape(modem.modulate(coded, 'BPSK'), 4, modem.rrc_filter(0.35, 4))
    return modem.channel(sig, 8.0, 0.004, 0.0, 0.6, rng)[0]


def _long_cltu(rng, n_codewords=24):
    pn = framing.pn_sequence('tc_btg', ldpc.N)
    cw = ldpc.encode(rng.randint(0, 2, (n_codewords, 64)).astype(np.uint8))
    cltu = np.concatenate([framing.MARKERS['ASM_034776C7272895B0']] + [c ^ pn for c in cw])
    sig = modem.pulse_shape(modem.modulate(cltu.astype(np.uint8), 'BPSK'), 4, modem.rrc_filter(0.35, 4))
    return modem.channel(sig, 9.0, 0.003, 0.0, 0.4, rng)[0]


def measure(name, captures, higher):
    rows, t0, rss0 = [], time.perf_counter(), _rss()
    peak = rss0
    for iq, fs in captures:
        r = analyze_iq(iq, fs=fs, search_higher_modulations=higher)
        peak = max(peak, _rss())
        fam = {f['name']: f['tested_hypotheses'] for f in r['accept']['families']}
        rows.append({'samples': len(iq), 'runtime': r['runtime'], 'status': r['status'],
                     'M': fam, 'fronts': r['diagnostics']['n_front_ends'],
                     'timers': r['diagnostics']['timers_s']})
    total = time.perf_counter() - t0
    return {'dataset': name, 'n': len(rows), 'total_s': total,
            'mean_s': total / max(len(rows), 1),
            'max_s': max((r['runtime'] for r in rows), default=0.0),
            'peak_rss_mb': peak, 'rss_growth_mb': peak - rss0,
            'mean_samples': float(np.mean([r['samples'] for r in rows])) if rows else 0.0,
            'mean_M': {k: float(np.mean([r['M'].get(k, 0) for r in rows])) for k in
                       ('F1_burst_code', 'F2_stream_code', 'F3_frame', 'F4_block_code')} if rows else {},
            'mean_fronts': float(np.mean([r['fronts'] for r in rows])) if rows else 0.0,
            'timers': {k: float(np.sum([r['timers'][k] for r in rows])) for k in rows[0]['timers']} if rows else {}}


def _bench(dirname, n):
    out = []
    for i in range(n):
        path = os.path.join(dirname, f'test_{i:03d}.iq')
        if os.path.exists(path):
            gt = json.load(open(path + '.gt.json'))
            out.append((load_iq(path), gt.get('fs')))
    return out


def main(higher=False):
    rng = np.random.RandomState(99)
    sets = [('bench-v1 sealed', _bench('data/sealed', 30)),
            ('bench-v1 train', _bench('data/train', 100)),
            ('null set (200-file sample)',
             [(load_iq(p), None) for p in sorted(glob.glob('data/nullset/*.iq'))[::7][:200]]),
            ('long CCSDS chain (4 frames, 66 k samples)', [(_long_ccsds(rng), None)]),
            ('long TC LDPC CLTU (24 codewords)', [(_long_cltu(rng), None)])]
    print(f"# Performance report ({'EXPERIMENTAL higher modulations ON' if higher else 'default path'})\n")
    print(f'Single process, Python {sys.version.split()[0]}, numpy {np.__version__}. '
          f'Interpreter baseline RSS {_rss():.0f} MB.\n')
    print('| dataset | files | mean samples | mean s | max s | peak RSS MB | ΔRSS MB | mean front ends | '
          'mean M₁ | M₂ | M₃ | M₄ |')
    print('|---|---|---|---|---|---|---|---|---|---|---|---|')
    results = []
    for name, captures in sets:
        if not captures:
            continue
        m = measure(name, captures, higher)
        results.append(m)
        print(f"| {name} | {m['n']} | {m['mean_samples']:.0f} | {m['mean_s']:.2f} | {m['max_s']:.2f} | "
              f"{m['peak_rss_mb']:.0f} | {m['rss_growth_mb']:.0f} | {m['mean_fronts']:.1f} | "
              + ' | '.join(f"{m['mean_M'][k]:.0f}" for k in
                           ('F1_burst_code', 'F2_stream_code', 'F3_frame', 'F4_block_code')) + ' |')
    print('\n## Time by stage (share of the summed per-file timers)\n')
    print('| dataset | ' + ' | '.join(results[0]['timers']) + ' |')
    print('|---|' + '---|' * len(results[0]['timers']))
    for m in results:
        tot = sum(m['timers'].values()) or 1.0
        print(f"| {m['dataset']} | " + ' | '.join(f'{100 * v / tot:.0f}%' for v in m['timers'].values()) + ' |')
    os.makedirs('results', exist_ok=True)
    with open('results/perf_higher.json' if higher else 'results/perf.json', 'w') as f:
        json.dump(results, f, indent=1)


if __name__ == '__main__':
    main('--higher' in sys.argv[1:])
