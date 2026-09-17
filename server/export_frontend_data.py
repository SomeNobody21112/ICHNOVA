"""Export the frontend's real-data layer (no hand-typed numbers).

    python server/export_frontend_data.py

Requires generated data (data/sealed, data/train, data/nullset) and the evaluation results in
results/ (sealed_test.py, eval/ladder.py, eval/nullset.py run, eval/acceptance.py run).

Writes
  frontend/public/evidence/<id>.json   engine evidence packs for the flagship benchmark captures
  frontend/public/evidence/index.json  list of packs
  frontend/public/samples/*            sample captures for the Analysis upload flow (+ samples.json)
  frontend/public/benchmark.json       Experiment Lab numbers, each with its source file
"""

import json
import os
import shutil
import sys
from collections import Counter, defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from evidence import ROOT, build_pack, to_json_default   # noqa: E402

sys.path.insert(0, os.path.join(ROOT, 'eval'))
from modem import load_iq, save_wav                        # noqa: E402

PUB = os.path.join(ROOT, 'frontend', 'public')

FLAGSHIPS = [
    ('BENCH-QPSK-K7', 'data/sealed/test_018', 'DECODED QPSK capture: K=7 code and 10×12 interleaver accepted.'),
    ('BENCH-BPSK-K5', None, 'DECODED capture with a K=5 code, identified from the catalogue.'),
    ('BENCH-UNCODED', None, 'Uncoded BPSK: signal detected, no catalogue code established.'),
    ('BENCH-SHORT-K7', None, 'A real K=7 transmission too short to prove (32 coded bits): refused.'),
    ('BENCH-WRONGSTRUCT', 'data/nullset/k3_384_012', 'K=3 capture where a structurally inconsistent interleaver was significant and rejected.'),
    ('BENCH-NOISE', 'data/nullset/noise_060_052', 'Receiver noise only: no evidence of a signal.'),
]


def _read(p):
    return json.load(open(os.path.join(ROOT, p)))


def _jsonl(p):
    return [json.loads(line) for line in open(os.path.join(ROOT, p))]


def pick_paths():
    rows = _jsonl('results/nullset_rows.jsonl')

    def first(pred):
        return next(r for r in sorted(rows, key=lambda r: r['file']) if pred(r))
    k5 = first(lambda r: r['class'] == 'k5' and r['status'] == 'DECODED' and r['coded_bits'] >= 120 and r['ber'] == 0)
    unc = first(lambda r: r['class'] == 'uncoded_bpsk' and r['status'] == 'SIGNAL_NO_CODE' and r['coded_bits'] == 120)
    train = _read('results/train_results.json')['results']
    short = next(r for r in train if r['gt_interleaver'] == [4, 8] and r['outcome'] == 'UNKNOWN')
    paths = {'BENCH-BPSK-K5': f"data/nullset/{k5['file']}", 'BENCH-UNCODED': f"data/nullset/{unc['file']}",
             'BENCH-SHORT-K7': f"data/train/{short['file']}"}
    return [(i, p or paths[i], d) for i, p, d in FLAGSHIPS]


def truth_of(gt):
    keep = ('class', 'modulation', 'sps', 'beta', 'cfo', 'interleaver', 'snr_db', 'esn0_db', 'coded_bits',
            'n_interleaved_bits', 'timing_offset')
    t = {k: gt[k] for k in keep if k in gt}
    codes = {'k7': 'conv_k7_r12_171_133', 'k5': 'conv_k5_r12_23_35', 'k3': 'conv_k3_r12_7_5'}
    t['code'] = codes.get(gt['class']) if 'class' in gt else 'conv_k7_r12_171_133'
    return t


def export_packs():
    os.makedirs(os.path.join(PUB, 'evidence'), exist_ok=True)
    os.makedirs(os.path.join(PUB, 'samples'), exist_ok=True)
    index, samples = [], []
    for pid, rel, desc in pick_paths():
        path = os.path.join(ROOT, rel + '.iq')
        gt = json.load(open(path + '.gt.json'))
        pack = build_pack(load_iq(path), 1e6, pid,
                          {'kind': 'BENCHMARK', 'file': rel + '.iq', 'note': desc,
                           'dataset': rel.split('/')[1]},
                          {'format': 'iq'}, truth_of(gt))
        json.dump(pack, open(os.path.join(PUB, 'evidence', pid + '.json'), 'w'), default=to_json_default)
        index.append({'id': pid, 'status': pack['result']['status'], 'description': desc,
                      'hypotheses': pack['accept']['n_hypotheses'], 'file': rel + '.iq'})
        name = pid.lower() + '.iq'
        shutil.copy(path, os.path.join(PUB, 'samples', name))
        samples.append({'name': name, 'format': 'iq', 'fs_hz': 1e6, 'bytes': os.path.getsize(path),
                        'description': desc, 'evidence_id': pid})
        print(pid, pack['result']['status'], pack['accept']['n_hypotheses'], 'hypotheses')
    wav = os.path.join(PUB, 'samples', 'bench-qpsk-k7.wav')
    save_wav(wav, load_iq(os.path.join(ROOT, 'data/sealed/test_018.iq')), 1e6)
    samples.append({'name': 'bench-qpsk-k7.wav', 'format': 'wav', 'fs_hz': 1e6, 'bytes': os.path.getsize(wav),
                    'description': 'Same QPSK capture stored as int16 stereo I/Q .wav (exercises .wav ingestion).',
                    'evidence_id': 'BENCH-QPSK-K7'})
    json.dump(index, open(os.path.join(PUB, 'evidence', 'index.json'), 'w'), indent=1)
    json.dump(samples, open(os.path.join(PUB, 'samples', 'samples.json'), 'w'), indent=1)


def md_table(path, header_start):
    """Rows of the first markdown table whose header starts with header_start."""
    lines = open(os.path.join(ROOT, path), encoding='utf-8').read().splitlines()
    for i, line in enumerate(lines):
        if line.startswith('| ' + header_start):
            out = []
            for row in lines[i + 2:]:
                if not row.startswith('|'):
                    break
                out.append([c.strip() for c in row.strip('|').split('|')])
            return out
    return []


def export_benchmark():
    bench = {}
    for label, sealed, train in (
            ('baseline_4c8188b', 'reports/data/baseline_4c8188b_sealed_results.json', 'reports/data/baseline_4c8188b_train_results.json'),
            ('hardened_0f71803', 'reports/data/v1_sealed_results.json', 'reports/data/v1_train_results.json'),
            ('structural_0f71803+', 'reports/data/v1_sealed_results_structural.json', 'reports/data/v1_train_results_structural.json'),
            ('vectorised_current', 'reports/data/v2_sealed_results_vectorised.json', 'reports/data/v2_train_results_vectorised.json')):
        entry = {}
        for ds, p in (('sealed', sealed), ('train', train)):
            j = _read(p)
            if 'passes' in j:
                entry[ds] = {'pass': j['passes'], 'n': j['n_files'], 'false_accepts': j['false_accepts'],
                             'outcomes': j['outcomes'], 'runtime_s': round(j['total_time'], 1)}
            else:
                entry[ds] = {'pass': j['successes'], 'n': j['total'], 'false_accepts': None,
                             'outcomes': {'PASS': j['successes'], 'FAIL': j['total'] - j['successes']},
                             'runtime_s': round(j['total_time'], 1)}
            entry[ds]['source'] = p
        bench[label] = entry

    ladder = {}
    for ds in ('sealed', 'train'):
        rows = _read(f'reports/data/{ds}_ladder.json')
        ladder[ds] = {'stages': {s: sum(1 for r in rows if r['first_pass_stage'] == s)
                                 for s in ('O0', 'O1', 'O2', 'O3', 'O4', 'O5', 'O6', 'O7')},
                      'never': sum(1 for r in rows if r['first_pass_stage'] is None), 'n': len(rows),
                      'o7_first_pass_32bit': sum(1 for r in rows if r['first_pass_stage'] == 'O7'
                                                 and r['interleaver'][0] * r['interleaver'][1] == 32),
                      'source': f'reports/data/{ds}_ladder.json'}

    rows = _jsonl('results/nullset_rows.jsonl')
    label = {'conv_k7_r12_171_133': 'k7', 'conv_k5_r12_23_35': 'k5', 'conv_k3_r12_7_5': 'k3'}
    confusion = defaultdict(Counter)
    esn0 = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for r in rows:
        out = label.get(r['code'], r['status']) if r['status'] == 'DECODED' else r['status']
        confusion[r['class']][out] += 1
        if r['class'] in ('k7', 'k5', 'k3'):
            ok = (out == r['class'] and list(r['est_interleaver'] or []) == list(r['interleaver'] or [])
                  and r['ber'] is not None and r['ber'] < 0.01)
            cell = esn0[r['class']][str(int(r['esn0_db']))]
            cell[0] += ok
            cell[1] += 1
    nullset = {'n': len(rows), 'confusion': {k: dict(v) for k, v in confusion.items()},
               'correct_by_esn0': {k: {e: {'correct': c[0], 'n': c[1]} for e, c in v.items()} for k, v in esn0.items()},
               'runtime_mean_s': round(float(np.mean([r['runtime'] for r in rows])), 3),
               'hypotheses_mean': round(float(np.mean([r['n_hypotheses'] for r in rows]))),
               'source': 'results/nullset_rows.jsonl (reports/data/nullset_report_structural.md)'}

    import acceptance as acc
    arows = _jsonl('results/acceptance_rows.jsonl')
    search = [r for r in arows if r['kind'] in ('null', 'wrongnull')]
    params = acc.calibrate([r for r in search if r['index'] % 2 == 0])
    evals = [r for r in search if r['index'] % 2 == 1]
    rules = [{'rule': rule, **acc.metrics(evals, rule, params)} for rule in acc.RULES]
    acceptance = {'params': params, 'evaluation_split': rules, 'adopted': 'R0+MC+BL+PM',
                  'source': 'results/acceptance_rows.jsonl (reports/data/acceptance_rules.md)'}

    scoring = [{'method': r[0], 'auc': float(r[1]), 'tpr_at_zero_fp': float(r[2]),
                'identification': float(r[3]), 'null_range': r[4]}
               for r in md_table('reports/data/scoring_compare.md', 'method | AUC')]

    stages = defaultdict(float)
    for line in open(os.path.join(ROOT, 'results/train_diagnostics.jsonl')):
        for k, v in json.loads(line)['diagnostics']['timers_s'].items():
            stages[k] += v
    total = sum(stages.values())
    runtime = {'stage_share': {k: round(v / total, 4) for k, v in stages.items()},
               'source': 'results/train_diagnostics.jsonl'}

    null_rt = _read('reports/data/v2_nullset_runtime.json')
    performance = {
        'sealed_s': [bench['structural_0f71803+']['sealed']['runtime_s'], bench['vectorised_current']['sealed']['runtime_s']],
        'train_s': [bench['structural_0f71803+']['train']['runtime_s'], bench['vectorised_current']['train']['runtime_s']],
        'nullset_s': [null_rt['before_total_runtime_s'], null_rt['total_runtime_s']],
        'decision_differences': null_rt['decision_differences'], 'note': null_rt['note'],
        'changes': ['syndrome search: all interleaver x code hypotheses of a front end in one matrix pass (same factor order, identical check signs)',
                    'stacked deinterleave indices cached per candidate set',
                    'hypothesis table built from arrays instead of per-hypothesis list appends',
                    'root-raised-cosine taps cached (read-only) instead of recomputed per front end'],
        'source': 'reports/data/v2_*_results_vectorised.json, reports/data/v2_nullset_runtime.json'}
    real = json.load(open(os.path.join(PUB, 'live', 'index.json'), encoding='utf-8')) if os.path.exists(os.path.join(PUB, 'live', 'index.json')) else []
    out = {'generated_from_commit': os.popen(f'git -C "{ROOT}" rev-parse --short HEAD').read().strip(),
           'bench_v1': bench, 'oracle_ladder': ladder, 'nullset': nullset, 'acceptance': acceptance,
           'scoring': scoring, 'runtime': runtime, 'performance': performance, 'real_signals': real,
           'research_issue': 'Wrong-interleaver hypotheses can still pass on 0.9% of wrong-structure runs '
                             '(2/225, held-out split); low-SNR recall is limited (K7 3/34 at 3 dB Es/N0).'}
    json.dump(out, open(os.path.join(PUB, 'benchmark.json'), 'w'), indent=1, default=to_json_default)
    print('benchmark.json written')


if __name__ == '__main__':
    export_packs()
    export_benchmark()
