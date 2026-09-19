"""Null / other-code evaluation set, calibration report and scoring comparison.

usage:
  python eval/nullset.py generate      # data/nullset/*.iq + .gt.json (seed0 500000)
  python eval/nullset.py run           # blind receiver on every file → results/nullset_rows.jsonl
  python eval/nullset.py report        # outcomes, false-accept rates, confusion, ROC → stdout
  python eval/nullset.py compare       # scoring-method comparison (oracle front-end) → stdout

Classes: noise, uncoded_bpsk, uncoded_qpsk, k7, k5, k3 (BPSK or QPSK), 8psk_k7 (out of family).
Transmitted coded-bit lengths: 30, 60, 120, 240, 384 (384 = largest block in the receiver's
interleaver domain). Parameters are drawn from ranges deliberately different from bench-v1:
sps ∈ {3,4,5,6,7,8,10,12}, β ~ U(0.2, 0.5), CFO ~ U(−0.01, 0.01), timing ~ U(−0.5, 0.5),
Es/N0 ∈ {3, 6, 9, 12} dB (set directly; see eval/snr.py for the definition).
"""

import glob
import json
import os
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'src'))
sys.stdout.reconfigure(encoding='utf-8')

from modem import modulate, pulse_shape, rrc_filter, channel, save_iq, load_iq   # noqa: E402
from fec import conv_encode, block_interleave                                   # noqa: E402
from pipeline import analyze_file, analyze_iq                                    # noqa: E402
from analyze import matched_filter_demod, symbol_snr_m2m4, psk_llrs              # noqa: E402
from blind_id import (CODE_CATALOGUE, interleaver_candidates, deinterleave_index,  # noqa: E402
                      syndrome_checks, sign_test_log10p, decode_hypothesis)

OUT = 'data/nullset'
LENGTHS = [30, 60, 120, 240, 384]
PER_LENGTH = {'noise': 100, 'uncoded_bpsk': 30, 'uncoded_qpsk': 30,
              'k7': 30, 'k5': 30, 'k3': 30, '8psk_k7': 20}
CODES = {'k7': CODE_CATALOGUE[0], 'k5': CODE_CATALOGUE[1], 'k3': CODE_CATALOGUE[2],
         '8psk_k7': CODE_CATALOGUE[0]}
NULL_CLASSES = ('noise', 'uncoded_bpsk', 'uncoded_qpsk', '8psk_k7')
CODE_LABEL = {CODE_CATALOGUE[0]['name']: 'k7', CODE_CATALOGUE[1]['name']: 'k5',
              CODE_CATALOGUE[2]['name']: 'k3'}


def modulate_8psk(bits):
    k = bits[0::3] * 4 + bits[1::3] * 2 + bits[2::3]
    return np.exp(2j * np.pi * k / 8)


def generate(seed0=500000):
    os.makedirs(OUT, exist_ok=True)
    seed = seed0
    for cls, per in PER_LENGTH.items():
        for L in LENGTHS:
            for i in range(per):
                seed += 1
                rng = np.random.RandomState(seed)
                sps = int(rng.choice([3, 4, 5, 6, 7, 8, 10, 12]))
                beta, cfo = float(rng.uniform(0.2, 0.5)), float(rng.uniform(-0.01, 0.01))
                tau, phase = float(rng.uniform(-0.5, 0.5)), float(rng.uniform(0, 2 * np.pi))
                esn0 = float(rng.choice([3, 6, 9, 12]))
                gt = {'class': cls, 'coded_bits': L, 'seed': seed, 'sps': sps, 'beta': beta,
                      'cfo': cfo, 'timing_offset': tau, 'phase_offset': phase, 'esn0_db': esn0}
                if cls == 'noise':
                    n = L * sps + 10 * sps
                    iq = (rng.standard_normal(n) + 1j * rng.standard_normal(n)) / np.sqrt(2)
                    gt.update(modulation=None, interleaver=None, original_bits=[])
                else:
                    if cls.startswith('uncoded'):
                        bits = rng.randint(0, 2, L).astype(np.uint8)
                        payload, dims = bits, None
                    else:
                        dims = _random_dims(L, rng)
                        info = rng.randint(0, 2, L).astype(np.uint8)
                        code = CODES[cls]
                        bits = block_interleave(conv_encode(info, code['generators'], code['K']), *dims)
                        payload = info[:L // 2]
                    mod = ('8PSK' if cls == '8psk_k7' else 'BPSK' if cls == 'uncoded_bpsk' else
                           'QPSK' if cls == 'uncoded_qpsk' else str(rng.choice(['BPSK', 'QPSK'])))
                    syms = modulate_8psk(bits) if mod == '8PSK' else modulate(bits, mod)
                    sig = pulse_shape(syms, sps, rrc_filter(beta, sps))
                    snr_per_sample = esn0 - 10 * np.log10(len(sig) / len(syms))
                    iq, _ = channel(sig, snr_per_sample, cfo, tau, phase, rng)
                    gt.update(modulation=mod, interleaver=dims, n_symbols=len(syms),
                              original_bits=payload.tolist())
                name = f'{cls}_{L:03d}_{i:03d}'
                save_iq(os.path.join(OUT, name + '.iq'), iq)
                json.dump(gt, open(os.path.join(OUT, name + '.iq.gt.json'), 'w'))
    print(f'generated {len(glob.glob(OUT + "/*.iq"))} files in {OUT}')


def _random_dims(L, rng):
    pairs = [(r, L // r) for r in range(2, 17) if L % r == 0 and 4 <= L // r <= 24]
    return pairs[rng.randint(len(pairs))]


def ber(decoded, original):
    d, o = np.asarray(decoded), np.asarray(original)
    L = min(len(d), len(o))
    return 1.0 if L == 0 else float(min(np.mean(d[:L] != o[:L]), np.mean((1 - d[:L]) != o[:L])))


def run_one(job):
    path, higher = job if isinstance(job, tuple) else (job, False)
    gt = json.load(open(path + '.gt.json'))
    r = analyze_iq(load_iq(path), search_higher_modulations=higher)
    top = r['diagnostics']['top_hypotheses'][:1]
    return {'file': os.path.basename(path)[:-3], 'class': gt['class'], 'coded_bits': gt['coded_bits'],
            'sps': gt['sps'], 'esn0_db': gt['esn0_db'], 'modulation': gt['modulation'],
            'interleaver': gt.get('interleaver'), 'status': r['status'], 'code': r['code'],
            'est_interleaver': r['interleaver'], 'est_mod': r['modulation'], 'est_sps': r['sps'],
            'ber': ber(r['payload_bits'], gt['original_bits']) if gt['original_bits'] else None,
            'log10_p': r['accept']['log10_p'], 'log10_threshold': r['accept']['log10_threshold'],
            'n_hypotheses': r['accept']['n_hypotheses'],
            'detection_log10_p': r['diagnostics']['detection_log10_p'],
            'runtime': r['runtime'], 'timers': r['diagnostics']['timers_s'],
            'top1': top[0] if top else None,
            **({'higher_modulations': True} if higher else {})}


def run(higher=False):
    """`higher` runs the EXPERIMENTAL 8PSK / 16-QAM search (pipeline.SEARCH_HIGHER_MODULATIONS is off
    by default). Its rows go to results/nullset_rows_higher.jsonl, so the two measurements can never
    be confused with each other."""
    paths = [(p, higher) for p in sorted(glob.glob(OUT + '/*.iq'))]
    os.makedirs('results', exist_ok=True)
    out_name = 'results/nullset_rows_higher.jsonl' if higher else 'results/nullset_rows.jsonl'
    # NULLSET_WORKERS caps the pool on a machine short of memory: the higher-modulation search holds
    # far more hypotheses per worker, and an over-subscribed run gets killed part way through.
    workers = int(os.environ.get('NULLSET_WORKERS') or max(1, (os.cpu_count() or 2) - 1))
    with Pool(workers) as pool, \
            open(out_name, 'w') as f:
        for i, row in enumerate(pool.imap_unordered(run_one, paths, chunksize=4)):
            f.write(json.dumps(row) + '\n')
            if (i + 1) % 100 == 0:
                print(f'{i + 1}/{len(paths)}', flush=True)


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, c - h), min(1.0, c + h))


def label(row):
    if row['status'] != 'DECODED':
        return row['status']
    return CODE_LABEL.get(row['code'], row['code'])


def correct_decode(row):
    return (row['class'] in ('k7', 'k5', 'k3') and label(row) == row['class']
            and list(row['est_interleaver'] or []) == list(row['interleaver'] or [])
            and row['ber'] is not None and row['ber'] < 0.01)


def _top_is_true(r):
    t = r['top1']
    return (t is not None and r['interleaver'] is not None and CODE_LABEL.get(t['code']) == r['class']
            and list(t['interleaver'] or []) == list(r['interleaver'] or []))


def report(higher=False):
    name = 'results/nullset_rows_higher.jsonl' if higher else 'results/nullset_rows.jsonl'
    rows = [json.loads(line) for line in open(name)]
    classes = list(PER_LENGTH)
    print(f'# Null / other-code calibration ({len(rows)} files)\n')

    print('## Outcomes by class\n\n| class | n | UNKNOWN | SIGNAL_NO_CODE | DECODED | of which correct |\n|---|---|---|---|---|---|')
    for c in classes:
        rs = [r for r in rows if r['class'] == c]
        st = Counter(r['status'] for r in rs)
        print(f"| {c} | {len(rs)} | {st['UNKNOWN']} | {st['SIGNAL_NO_CODE']} | {st['DECODED']} | "
              f"{sum(correct_decode(r) for r in rs) if c in ('k7', 'k5', 'k3') else '—'} |")

    print('\n## False accepts (DECODED on a file with no catalogue code / out of family), by length\n')
    print('| class | ' + ' | '.join(f'L={L}' for L in LENGTHS) + ' | all (95% upper bound) |\n|---|' + '---|' * (len(LENGTHS) + 1))
    for c in NULL_CLASSES:
        cells = []
        for L in LENGTHS:
            rs = [r for r in rows if r['class'] == c and r['coded_bits'] == L]
            cells.append(f"{sum(r['status'] == 'DECODED' for r in rs)}/{len(rs)}")
        rs = [r for r in rows if r['class'] == c]
        k = sum(r['status'] == 'DECODED' for r in rs)
        print(f"| {c} | {' | '.join(cells)} | {k}/{len(rs)} (≤ {100 * wilson(k, len(rs))[1]:.1f}%) |")
    nulls = [r for r in rows if r['class'] in NULL_CLASSES]
    k = sum(r['status'] == 'DECODED' for r in nulls)
    print(f"\nAll null files: {k}/{len(nulls)} false accepts, 95% Wilson upper bound "
          f"{100 * wilson(k, len(nulls))[1]:.2f}% (design target α = 1% per file).")

    print('\n## Coded files: correct decode rate (right code, right interleaver, BER < 0.01)\n')
    print('| class | ' + ' | '.join(f'L={L}' for L in LENGTHS) + ' |\n|---|' + '---|' * len(LENGTHS))
    for c in ('k7', 'k5', 'k3'):
        cells = [f"{sum(correct_decode(r) for r in rows if r['class'] == c and r['coded_bits'] == L)}/"
                 f"{sum(1 for r in rows if r['class'] == c and r['coded_bits'] == L)}" for L in LENGTHS]
        print(f"| {c} | {' | '.join(cells)} |")
    print('\n| class | ' + ' | '.join(f'Es/N0={e:g} dB' for e in (3, 6, 9, 12)) + ' |\n|---|---|---|---|---|')
    for c in ('k7', 'k5', 'k3'):
        cells = [f"{sum(correct_decode(r) for r in rows if r['class'] == c and r['esn0_db'] == e)}/"
                 f"{sum(1 for r in rows if r['class'] == c and r['esn0_db'] == e)}" for e in (3, 6, 9, 12)]
        print(f"| {c} | {' | '.join(cells)} |")
    wrong = [r for r in rows if r['class'] in ('k7', 'k5', 'k3') and r['status'] == 'DECODED' and not correct_decode(r)]
    print(f"\nCoded files DECODED but wrong (code, interleaver or payload): {len(wrong)}")
    for r in wrong[:12]:
        print(f"  {r['file']}: est {label(r)} {r['est_interleaver']} vs true {r['interleaver']}, BER {r['ber']}")

    print('\n## Confusion matrix (rows: truth, columns: receiver output)\n')
    cols = ['UNKNOWN', 'SIGNAL_NO_CODE', 'k7', 'k5', 'k3']
    print('| truth | ' + ' | '.join(cols) + ' |\n|---|' + '---|' * len(cols))
    for c in classes:
        cnt = Counter(label(r) for r in rows if r['class'] == c)
        print(f"| {c} | " + ' | '.join(str(cnt[x]) for x in cols) + ' |')

    print('\n## Acceptance threshold sweep (Bonferroni evidence e = log10 p + log10 M; accept if e ≤ τ)\n')
    print('Positives: coded files; a true positive needs the top hypothesis to be the true code and '
          'interleaver. Negatives: null classes. τ = −2 is the shipped rule (α = 0.01).\n')
    pos_all = [r for r in rows if r['class'] in ('k7', 'k5', 'k3')]
    print('| τ | TPR (recall) | FPR | FNR | precision | false accepts |\n|---|---|---|---|---|---|')
    for tau in (0, -1, -2, -3, -4, -6):
        def acc(r):
            return r['log10_p'] + np.log10(max(r['n_hypotheses'], 1)) <= tau
        tp = sum(acc(r) and _top_is_true(r) for r in pos_all)
        fp_pos = sum(acc(r) and not _top_is_true(r) for r in pos_all)
        fp = sum(acc(r) for r in nulls)
        prec = tp / max(tp + fp + fp_pos, 1)
        print(f"| {tau} | {tp / len(pos_all):.3f} | {fp / max(len(nulls), 1):.4f} | "
              f"{1 - tp / len(pos_all):.3f} | {prec:.3f} | {fp} null + {fp_pos} wrong-hypothesis |")
    e_null = np.array([r['log10_p'] + np.log10(max(r['n_hypotheses'], 1)) for r in nulls])
    print(f"\nNull evidence e: min {e_null.min():.2f}, 1% quantile {np.percentile(e_null, 1):.2f}, "
          f"median {np.median(e_null):.2f} (the shipped rule accepts at e ≤ −2).")

    print('\n## Runtime\n\n| class | mean s | max s | mean hypotheses |\n|---|---|---|---|')
    for c in classes:
        rs = [r for r in rows if r['class'] == c]
        print(f"| {c} | {np.mean([r['runtime'] for r in rs]):.2f} | {np.max([r['runtime'] for r in rs]):.2f} | "
              f"{np.mean([r['n_hypotheses'] for r in rs]):.0f} |")
    stage = defaultdict(float)
    for r in rows:
        for k2, v in r['timers'].items():
            stage[k2] += v
    tot = sum(stage.values())
    print('\nTime share by stage: ' + ', '.join(f'{k2} {100 * v / tot:.1f}%' for k2, v in stage.items()))
    print('Mean runtime by block length: ' + ', '.join(
        f"L={L}: {np.mean([r['runtime'] for r in rows if r['coded_bits'] == L]):.2f}s" for L in LENGTHS))


def compare_one(path):
    """All (code × interleaver) hypotheses at the true front-end, every scoring method."""
    gt = json.load(open(path + '.gt.json'))
    raw = load_iq(path)
    iq = raw * np.exp(-2j * np.pi * gt['cfo'] * np.arange(len(raw)))
    mod = gt['modulation'] or 'BPSK'
    y = matched_filter_demod(iq, rrc_filter(gt['beta'], gt['sps']), gt['sps'])
    y = y * np.exp(-1j * gt['phase_offset'])
    S, N = symbol_snr_m2m4(y)
    llrs = psk_llrs(y, mod, S, N)
    th = np.tanh(np.clip(llrs, -40, 40) / 2)
    hyps = []
    for dims in interleaver_candidates(len(llrs)):
        d = th[:dims[0] * dims[1]][deinterleave_index(*dims)]
        for code in CODE_CATALOGUE:
            chk = syndrome_checks(d, code)
            if len(chk) == 0:
                continue
            dec = decode_hypothesis(llrs, code, dims)
            hyps.append((code['name'], dims, len(chk), int((chk > 0).sum()),
                         float(chk.sum() / np.sqrt(max(np.dot(chk, chk), 1e-300))), dec,
                         dims[0] * dims[1] // 2))
    M = len(hyps)
    truth = (CODES[gt['class']]['name'], tuple(gt['interleaver'])) if gt['class'] in CODES else None
    scores = {}
    for name, fn in (('hard_consistency', lambda h: h[5]['consistency']),
                     ('soft_path_metric', lambda h: h[5]['path_metric']),
                     ('mdl_savings_bits', lambda h: h[6] - h[5]['soft_disagreement_nats'] / np.log(2) - np.log2(M)),
                     ('sign_test_evidence', lambda h: -(float(sign_test_log10p(h[3], h[2])) + np.log10(M))),
                     ('syndrome_z', lambda h: h[4])):
        vals = [fn(h) for h in hyps]
        i = int(np.argmax(vals))
        scores[name] = {'score': float(vals[i]), 'top_is_true': (hyps[i][0], tuple(hyps[i][1])) == truth}
    return {'class': gt['class'], 'coded_bits': gt['coded_bits'], 'n_hypotheses': M, 'scores': scores}


METHODS = ('hard_consistency', 'soft_path_metric', 'mdl_savings_bits', 'sign_test_evidence', 'syndrome_z')


def compare():
    paths = []
    for c in ('k7', 'k5', 'k3', 'noise', 'uncoded_bpsk', 'uncoded_qpsk'):
        for L in (60, 120, 240):
            paths += sorted(glob.glob(f'{OUT}/{c}_{L:03d}_*.iq'))[:20]
    with Pool(max(1, (os.cpu_count() or 2) - 1)) as pool:
        rows = pool.map(compare_one, paths)
    pos = [r for r in rows if r['class'] in ('k7', 'k5', 'k3')]
    neg = [r for r in rows if r['class'] not in ('k7', 'k5', 'k3')]
    print(f'# Scoring comparison at the true front-end ({len(pos)} coded, {len(neg)} null files; '
          f'L ∈ 60/120/240; mean {np.mean([r["n_hypotheses"] for r in rows]):.0f} hypotheses per file)\n')
    print('File score = max over hypotheses. AUC separates coded from null files. '
          '"TPR @ 0 FP" uses the largest null score as the threshold. '
          '"Identification" = top hypothesis is the true code and interleaver (coded files).\n')
    print('| method | AUC | TPR @ 0 null FP | identification accuracy | null score range |\n|---|---|---|---|---|')
    for m in METHODS:
        p = np.array([r['scores'][m]['score'] for r in pos])
        n = np.array([r['scores'][m]['score'] for r in neg])
        auc = float(np.mean(p[:, None] > n[None, :]) + 0.5 * np.mean(p[:, None] == n[None, :]))
        print(f"| {m} | {auc:.3f} | {np.mean(p > n.max()):.3f} | "
              f"{np.mean([r['scores'][m]['top_is_true'] for r in pos]):.3f} | [{n.min():.2f}, {n.max():.2f}] |")
    print('\nBy length (identification accuracy / TPR @ 0 FP):\n')
    print('| method | ' + ' | '.join(f'L={L}' for L in (60, 120, 240)) + ' |\n|---|---|---|---|')
    for m in METHODS:
        nmax = max(r['scores'][m]['score'] for r in neg)
        cells = []
        for L in (60, 120, 240):
            pl = [r for r in pos if r['coded_bits'] == L]
            cells.append(f"{np.mean([r['scores'][m]['top_is_true'] for r in pl]):.2f} / "
                         f"{np.mean([r['scores'][m]['score'] > nmax for r in pl]):.2f}")
        print(f"| {m} | {' | '.join(cells)} |")


if __name__ == '__main__':
    fn = {'generate': generate, 'run': run, 'report': report, 'compare': compare}[sys.argv[1]]
    kw = {'higher': True} if '--higher' in sys.argv[2:] and fn in (run, report) else {}
    fn(**kw)
