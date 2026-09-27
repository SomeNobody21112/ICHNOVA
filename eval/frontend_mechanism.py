"""SPACE-FRONTEND-MECH-01 — why does a small IQ correction change the hypothesis search space?

Criteria: `eval/frontend_mechanism_criteria.json`. Read-only. This harness **calls** the production
functions and **recomputes the same scalars the production front-end loop computes**, using the
production constants. Nothing is added to `src/`, and no production behaviour changes — the
instrumentation is evaluation-side replication, and it is only trusted if it reproduces the engine's
own published `n_front_ends` and `front_ends_rejected_serial_dependence` exactly.

Two published gates were localised by SPACE-FRONTEND-SENSITIVITY-01. The code says what each one
branches on:

  * the serial gate branches on ONE scalar per candidate front end — the neighbouring hard-decision
    agreement rate `same/n_pairs` against `SERIAL_AGREEMENT_MAX = 0.60`;
  * the sps candidate list branches on the ORDERING of `q4 = lag1_correlation(y**4)`, computed on the
    IQ *as given* with no CFO removal.

This run measures both, plus the residual per-symbol rotation of the matched-filter output, so that
"one upstream effect or two" is answered with numbers rather than argument.

    python eval/frontend_mechanism.py run
    python eval/frontend_mechanism.py report
"""

import hashlib
import json
import os
import sys

import numpy as np
from scipy.special import bdtrc

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding='utf-8')

import carrier_est_diag as diag                            # noqa: E402  (grid + captures, imported)
import pipeline                                            # noqa: E402  (called, never modified)
import space_doppler_mech as mech                          # noqa: E402
from analyze import (estimate_carrier_phase, estimate_symbol_rate, lag1_correlation,  # noqa: E402
                     matched_filter_demod, psk_llrs, symbol_snr_m2m4)
from modem import load_iq, rrc_filter                      # noqa: E402
from pipeline import (ALPHA, MIN_SYMBOLS, MODULATIONS, RX_BETA, SERIAL_AGREEMENT_MAX,  # noqa: E402
                      SPS_RANGE, analyze_iq)

CRITERIA = os.path.join(HERE, 'frontend_mechanism_criteria.json')
ROWS = os.path.join('results', 'frontend_mechanism_rows.jsonl')
FRONTS = os.path.join('results', 'frontend_mechanism_fronts.jsonl')
BITS_PER_SYMBOL = {'BPSK': 1, 'QPSK': 2}

CAPTURES = {
    'idle_carrier_0411': (os.path.join('data', 'bench2', 'sealed', 'idle_carrier_0411.iq'),
                          'primary'),
    'k3_120_008': (os.path.join('data', 'nullset', 'k3_120_008.iq'), 'sps_flip'),
    'static_0000': (os.path.join('data', 'space_bench', 'carrier_est', 'static_0000.iq'), 'control'),
}
PRIMARY_CONDITIONS = (('A_original', None, None), ('B_zero', 'zero', 0.0),
                      ('C_estimator', 'estimator_exact', 1.0),
                      ('constant_m0.5', 'constant', 0.5), ('constant_m1.0', 'constant', 1.0),
                      ('varying_only_m0.5', 'varying_only', 0.5),
                      ('varying_only_m1.0', 'varying_only', 1.0),
                      ('pass_mean_m0.01', 'pass_mean', 0.01))
SECONDARY_CONDITIONS = PRIMARY_CONDITIONS[:3]


def _corrected(iq, f_hat, scale, shape, m):
    if shape is None:
        return iq
    if shape == 'zero':
        return mech._derotate(iq, np.zeros(len(iq)))
    if shape == 'estimator_exact':
        return mech._derotate(iq, f_hat)
    return mech._derotate(iq, diag.correction(shape, m, len(iq), f_hat, scale))


def _front_candidates(iq):
    """Replicate the production front-end loop's gate arithmetic, calling production functions."""
    cfo_cands, detection = pipeline._cfo_candidates(iq)
    cfo_list = [c['cfo'] for c in cfo_cands]
    table = pipeline._sps_table(iq)
    raw_rate, _ = estimate_symbol_rate(iq, 1.0, SPS_RANGE)
    raw_sps = 1.0 / raw_rate
    sps_list = pipeline._sps_candidates(table, raw_sps)
    n = np.arange(len(iq))
    out, passed, rejected = [], 0, 0
    for cfo in cfo_list:
        iq_c = iq * np.exp(-2j * np.pi * cfo * n)
        for s in sps_list:
            y = matched_filter_demod(iq_c, rrc_filter(RX_BETA, s), s)
            if len(y) < MIN_SYMBOLS:
                continue
            lag1 = complex(np.mean(y[1:] * np.conj(y[:-1]))) if len(y) > 1 else 0j
            rot_cps = float(np.angle(lag1) / (2 * np.pi))       # cycles per SYMBOL, residual
            stats = {'lag1_y': lag1_correlation(y), 'lag1_y2': lag1_correlation(y ** 2),
                     'lag1_y4': lag1_correlation(y ** 4), 'rot_cycles_per_symbol': rot_cps}
            for mod in MODULATIONS:
                phase = estimate_carrier_phase(y, mod)
                ys = y * np.exp(-1j * phase)
                S, N = symbol_snr_m2m4(ys)
                rots = [0.0] if mod == 'BPSK' else [0.0, np.pi / 2]
                variants = [('static', ys, S, N)]
                tracked = pipeline._track_phase(y, mod)
                if tracked is not None:
                    St, Nt = symbol_snr_m2m4(tracked)
                    variants.append(('block_tracked', tracked, St, Nt))
                for tracking, yv, Sv, Nv in variants:
                    for rot in rots:
                        llrs = psk_llrs(yv * np.exp(-1j * rot), mod, Sv, Nv)
                        step = BITS_PER_SYMBOL[mod]
                        same = int(np.count_nonzero((llrs[step:] < 0) == (llrs[:-step] < 0)))
                        n_pairs = len(llrs) - step
                        tail = (float(np.log10(max(bdtrc(same - 1, n_pairs, SERIAL_AGREEMENT_MAX),
                                                   1e-300))) if same > 0 else 0.0)
                        ok = tail > np.log10(ALPHA)
                        passed += ok
                        rejected += (not ok)
                        out.append({'cfo': float(cfo), 'sps': int(s), 'mod': mod,
                                    'rot': float(rot), 'tracking': tracking, **stats,
                                    'symbol_snr_db': float(10 * np.log10(Sv / Nv + 1e-30)),
                                    'agreement': same / n_pairs if n_pairs else None,
                                    'n_pairs': n_pairs, 'binom_log10': tail, 'passed': bool(ok)})
    meta = {'n_cfo': len(cfo_list), 'cfo_values': [round(c, 7) for c in cfo_list],
            'detection_log10_p': detection, 'sps_domain': [r['sps'] for r in table],
            'q4_by_sps': {str(r['sps']): round(r['q4'], 6) for r in table},
            'q2_by_sps': {str(r['sps']): round(r['q2'], 6) for r in table},
            'sps_candidates': sps_list, 'raw_sps': float(raw_sps),
            'replicated_fronts': passed, 'replicated_rejected': rejected}
    return meta, out


def run():
    rows, fronts = [], []
    for name, (path, role) in CAPTURES.items():
        iq = load_iq(path)
        gt = json.load(open(path + '.gt.json', encoding='utf-8'))
        f_hat, _ = mech.estimate_trajectory(iq)
        scale = float(np.mean(f_hat))
        conds = PRIMARY_CONDITIONS if role == 'primary' else SECONDARY_CONDITIONS
        print(f'\n{name} ({role})  true cfo {gt.get("cfo", float("nan")):.6f}  '
              f'estimator mean {scale:.6e}')
        for label, shape, m in conds:
            x = _corrected(iq, f_hat, scale, shape, m)
            r = analyze_iq(x)                                  # the engine's own published counts
            meta, cands = _front_candidates(x)                 # the replication
            pub_f = r['diagnostics']['n_front_ends']
            pub_r = r['diagnostics']['front_ends_rejected_serial_dependence']
            ok = (meta['replicated_fronts'] == pub_f and meta['replicated_rejected'] == pub_r)
            row = {'capture': name, 'role': role, 'condition': label, 'shape': shape, 'm': m,
                   **meta, 'published_fronts': pub_f, 'published_rejected': pub_r,
                   'replication_ok': ok, 'status': r['status'],
                   'f4_M': next(f['tested_hypotheses'] for f in r['accept']['families']
                                if f['name'].startswith('F4')),
                   'f4_accepted': bool((r.get('block_code') or {}).get('accepted')),
                   'final_code': r['code']}
            rows.append(row)
            for c in cands:
                fronts.append({'capture': name, 'condition': label, **c})
            print(f'  {label:18} cfo {meta["n_cfo"]}  sps_cands '
                  f'{str(meta["sps_candidates"])[:22]:22} | replicated '
                  f'{meta["replicated_fronts"]:3}/{meta["replicated_rejected"]:4} vs published '
                  f'{pub_f:3}/{pub_r:4}  match {ok}  | {r["status"]:15} F4 M {row["f4_M"]:5} '
                  f'{"ACCEPT" if row["f4_accepted"] else ""}')
    os.makedirs('results', exist_ok=True)
    # numpy scalars leak in from the production functions; .item() keeps the value exact
    def _j(o):
        return o.item() if hasattr(o, 'item') else str(o)

    os.makedirs('results', exist_ok=True)
    with open(ROWS, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, default=_j) + '\n')
    with open(FRONTS, 'w', encoding='utf-8') as f:
        for r in fronts:
            f.write(json.dumps(r, default=_j) + '\n')
    bad = [r['condition'] for r in rows if not r['replication_ok']]
    print(f'\n{len(rows)} conditions, {len(fronts)} candidate front ends -> {ROWS}, {FRONTS}')
    print('REPLICATION VERIFIED for every condition' if not bad
          else f'REPLICATION MISMATCH in {bad} — mechanism claims are UNVERIFIED')


def _sha256(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def report():
    rows = [json.loads(l) for l in open(ROWS, encoding='utf-8')]
    fronts = [json.loads(l) for l in open(FRONTS, encoding='utf-8')]
    print(f'\nSPACE-FRONTEND-MECH-01 — {len(rows)} conditions, {len(fronts)} candidate front ends; '
          f'criteria sha256 {_sha256(CRITERIA)[:16]}…')
    print(f'replication verified everywhere: {all(r["replication_ok"] for r in rows)}\n')

    for cap in CAPTURES:
        rs = [r for r in rows if r['capture'] == cap]
        if not rs:
            continue
        print(f'=== {cap} ===')
        for r in rs:
            print(f'  {r["condition"]:18} fronts {r["published_fronts"]:3} rejected '
                  f'{r["published_rejected"]:4}  sps_cands {str(r["sps_candidates"])[:24]:24} '
                  f'F4 M {r["f4_M"]:5}  {r["status"]:15} '
                  f'{"ACCEPT" if r["f4_accepted"] else ""}')
        dom = {tuple(r['sps_domain']) for r in rs}
        print(f'  sps DOMAIN identical across conditions: {len(dom) == 1}  '
              f'(size {len(next(iter(dom)))})')
        base = rs[0]
        for r in rs[1:]:
            moved = [s for s in base['q4_by_sps']
                     if abs(base['q4_by_sps'][s] - r['q4_by_sps'][s]) > 1e-6]
            top_b = sorted(base['q4_by_sps'], key=lambda s: -base['q4_by_sps'][s])[:3]
            top_r = sorted(r['q4_by_sps'], key=lambda s: -r['q4_by_sps'][s])[:3]
            print(f'  {r["condition"]:18} q4 changed at {len(moved):2}/{len(base["q4_by_sps"])} sps; '
                  f'top-3 by q4 {top_b} -> {top_r}  sps list same: '
                  f'{base["sps_candidates"] == r["sps_candidates"]}')

    print('\nSERIAL GATE — agreement rate distribution per condition (primary capture)')
    for r in [x for x in rows if x['capture'] == 'idle_carrier_0411']:
        fs_ = [f for f in fronts if f['capture'] == 'idle_carrier_0411'
               and f['condition'] == r['condition']]
        ag = np.array([f['agreement'] for f in fs_ if f['agreement'] is not None])
        pas = [f for f in fs_ if f['passed']]
        print(f'  {r["condition"]:18} n={len(ag):4} agreement min {ag.min():.3f} median '
              f'{np.median(ag):.3f} max {ag.max():.3f} | at or below 0.60: '
              f'{int((ag <= SERIAL_AGREEMENT_MAX).sum()):4} | passed {len(pas):3}')
        if pas:
            pa = np.array([f['agreement'] for f in pas])
            print(f'                     survivors: agreement min {pa.min():.3f} max {pa.max():.3f} '
                  f'| sps {sorted({f["sps"] for f in pas})} | mods '
                  f'{sorted({f["mod"] for f in pas})} | tracking '
                  f'{sorted({f["tracking"] for f in pas})}')

    print('\nRESIDUAL ROTATION vs THE TWO GATES (primary; BPSK static variant per (cfo, sps))')
    for r in [x for x in rows if x['capture'] == 'idle_carrier_0411']:
        fs_ = [f for f in fronts if f['capture'] == 'idle_carrier_0411'
               and f['condition'] == r['condition'] and f['mod'] == 'BPSK'
               and f['tracking'] == 'static']
        rot = np.array([abs(f['rot_cycles_per_symbol']) for f in fs_])
        ag = np.array([f['agreement'] for f in fs_])
        q4 = np.array([f['lag1_y4'] for f in fs_])
        print(f'  {r["condition"]:18} |rot| med {np.median(rot):.5f} cyc/sym  agreement med '
              f'{np.median(ag):.3f}  lag1(y^4) med {np.median(q4):.4f}  passed '
              f'{sum(1 for f in fs_ if f["passed"]):3}/{len(fs_)}')


def demo():
    """Self-check: the replication uses production constants and the production gate arithmetic."""
    assert SERIAL_AGREEMENT_MAX == 0.60 and ALPHA == 0.01 and RX_BETA == 0.3
    assert MODULATIONS == ('BPSK', 'QPSK') and SPS_RANGE == (2, 20)
    # the gate arithmetic: an oversampled stream (each symbol repeated 4x, so ~75% of neighbouring
    # pairs agree — the very case the 0.60 spec exists for) is rejected; a coin-flip stream is not
    rng0 = np.random.RandomState(1)
    rep = np.repeat(rng0.choice([-1.0, 1.0], 500), 4)
    same = int(np.count_nonzero((rep[1:] < 0) == (rep[:-1] < 0)))
    tail = float(np.log10(max(bdtrc(same - 1, len(rep) - 1, SERIAL_AGREEMENT_MAX), 1e-300)))
    assert tail <= np.log10(ALPHA), 'a 75%-agreeing stream must be rejected'
    rng = np.random.RandomState(0)
    coin = rng.standard_normal(2000)
    same = int(np.count_nonzero((coin[1:] < 0) == (coin[:-1] < 0)))
    tail = float(np.log10(max(bdtrc(same - 1, len(coin) - 1, SERIAL_AGREEMENT_MAX), 1e-300)))
    assert tail > np.log10(ALPHA), 'an independent stream must pass'
    print('demo: production constants and serial-gate arithmetic self-checks pass')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'demo'
    os.chdir(ROOT)
    {'run': run, 'report': report, 'demo': demo}[cmd]()
