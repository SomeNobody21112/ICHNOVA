"""SPACE-OFFCARRIER-CENSUS-01 — does the SHIPPED engine already admit off-carrier front ends?

Criteria: `eval/offcarrier_census_criteria.json`, committed before this file existed. Read-only.

SPACE-FRONTEND-MECH-01 showed that a carrier pre-correction relocates the weakest of the six CFO
candidates off-carrier, that the de-rotated stream is then serially INDEPENDENT, and that the serial
gate admits it exactly as specified. `pipeline._cfo_candidates` produces its candidate list on every
capture, corrected or not. This harness asks the uncorrected question over the whole sealed evidence
base: how often does such a candidate exist, how often is one ADMITTED, how often does one reach a
structural family, pass F4, or produce a wrong claim?

Nothing is corrected, ablated or oracled: the engine runs exactly as shipped. The only instrumentation
is `_all_hypotheses=True`, which is existing evaluation-only logging (src/pipeline.py:113) read after
every acceptance decision is made — and the run VERIFIES it is verdict-neutral by comparing against
SPACE-F4-MARGIN-01's rows, which were recorded with the flag off.

    python eval/offcarrier_census.py run
    python eval/offcarrier_census.py report
"""

import hashlib
import json
import os
import sys
import time
from collections import Counter, defaultdict
from multiprocessing import Pool

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding='utf-8')

import f4_margin as f4m                                     # noqa: E402  (population + _correct)
import frontend_mechanism as fm                             # noqa: E402  (verified replication)
from modem import load_iq                                   # noqa: E402
from pipeline import CFO_MAX, analyze_iq                    # noqa: E402  (SHIPPED, unmodified)

CRITERIA = os.path.join(HERE, 'offcarrier_census_criteria.json')
ROWS = os.path.join('results', 'offcarrier_census_rows.jsonl')
ADMITTED = os.path.join('results', 'offcarrier_census_admitted.jsonl')
F4M_ROWS = os.path.join('results', 'f4_margin_rows.jsonl')

# Committed in the criteria file before any measurement. rot is in cycles per SYMBOL.
ON_CARRIER, OFF_CARRIER = 0.01, 0.10
SENSITIVITY_EDGES = (0.05, 0.10, 0.20)                      # the headline is reported at each
BAND_EDGE_FRAC = 0.9                                        # |cfo| > 0.9 * CFO_MAX  (MECH-01 signature)
WORKERS = min(max(1, (os.cpu_count() or 2) - 1), 8)


def _band(rot):
    if rot is None:
        return 'undefined'                                  # no meaningful carrier (noise captures)
    return 'on_carrier' if rot <= ON_CARRIER else ('near_carrier' if rot <= OFF_CARRIER
                                                   else 'off_carrier')


def _true_carrier(gt, n):
    """gt cfo in cycles/sample; for a drifting carrier the reference is the MEAN over the capture."""
    if 'cfo' not in gt:
        return None, False
    drift = float(gt.get('cfo_drift_per_sample') or 0.0)
    return float(gt['cfo']) + drift * (n - 1) / 2.0, bool(drift)


def _run_one(job):
    dataset, path, kind, gt = job
    t = time.perf_counter()
    iq = load_iq(path)
    r = analyze_iq(iq, _all_hypotheses=True)                 # SHIPPED ENGINE, no correction
    d = r['diagnostics']
    is_noise = (gt.get('class') == 'noise')
    ref, drifting = _true_carrier(gt, len(iq))
    sps = gt.get('sps')
    # ---- distinction 1 + 2 + 3: which candidates EXIST, and where they sit -------------------
    cands = []
    for c in d['cfo_candidates']:
        delta = None if (ref is None or is_noise) else abs(float(c['cfo']) - ref)
        rot = None if (delta is None or not sps) else delta * float(sps)
        cands.append({'cfo': float(c['cfo']), 'order': c.get('order'),
                      'ptf_db': c.get('peak_to_floor_db'), 'log10_p': c.get('log10_p'),
                      'delta': delta, 'rot': rot, 'band': _band(rot),
                      'band_edge': abs(float(c['cfo'])) > BAND_EDGE_FRAC * CFO_MAX})
    by_cfo = {round(c['cfo'], 12): c for c in cands}

    # ---- distinction 5: which cfos reach the F1 BURST-CODE hypothesis table ------------------
    # CORRECTION (post-measurement, recorded in the report): diagnostics.all_hypotheses is family
    # F1's table -- src/pipeline.py:428 passes this same M as F1_burst_code.tested_hypotheses. The
    # criteria file pre-registered it as F4's; that operationalisation was wrong. F4 publishes no
    # hypothesis -> front-end mapping (only a `stream` index, and the stream -> front map is
    # internal), so per-candidate F4 REACH is not measurable read-only. What IS published, and is
    # used for the F4 question instead, is the cfo of the front end that produced the CLAIM.
    ah = d.get('all_hypotheses') or {}
    reached, best_cfo, best_p = {}, None, None
    for cfo, lp in zip(ah.get('cfo', []), ah.get('log10_p', [])):
        k = round(float(cfo), 12)
        if k not in reached or lp < reached[k]:
            reached[k] = float(lp)
        if best_p is None or lp < best_p:
            best_p, best_cfo = float(lp), k
    f4 = r.get('block_code') or {}
    a4 = f4.get('accepted_hypothesis') or {}
    conv = a4.get('converged_codewords')

    # ---- distinction 4: which front ends are ADMITTED (verified replication) ------------------
    meta, fronts = fm._front_candidates(iq)
    rep_ok = (meta['replicated_fronts'] == d['n_front_ends']
              and meta['replicated_rejected'] == d['front_ends_rejected_serial_dependence'])
    adm = []
    for f in fronts:
        if not f['passed']:
            continue
        c = by_cfo.get(round(f['cfo'], 12), {})
        adm.append({'dataset': dataset, 'file': os.path.basename(path)[:-3], 'cls': gt.get('class'),
                    'cfo': f['cfo'], 'sps': f['sps'], 'mod': f['mod'], 'tracking': f['tracking'],
                    'band': c.get('band', 'undefined'), 'rot': c.get('rot'),
                    'delta': c.get('delta'), 'band_edge': c.get('band_edge'),
                    'ptf_db': c.get('ptf_db'),
                    'rot_own_sps': (None if c.get('delta') is None
                                    else c['delta'] * float(f['sps'])),
                    'agreement': f['agreement'], 'binom_log10': f['binom_log10'],
                    'symbol_snr_db': f['symbol_snr_db'], 'lag1_y4': f['lag1_y4'],
                    'reached_f1': round(f['cfo'], 12) in reached})
    ag = [a['agreement'] for a in adm if a['agreement'] is not None]
    off_adm = [a for a in adm if a['band'] == 'off_carrier']

    outcome, correct = f4m._correct(kind, gt, r)
    claim_d = (None if (ref is None or is_noise or r.get('cfo') is None)
               else abs(float(r['cfo']) - ref))
    claim_rot = None if (claim_d is None or not sps) else claim_d * float(sps)
    best, bar = f4.get('best_log10_p'), f4.get('log10_threshold')
    row = {
        'dataset': dataset, 'file': os.path.basename(path)[:-3], 'cls': gt.get('class'),
        'is_noise_class': is_noise, 'drifting': drifting, 'channel': gt.get('channel'),
        'esn0_db': gt.get('esn0_db', (gt.get('params') or {}).get('esn0', gt.get('snr_db'))),
        'true_cfo': ref, 'sps': sps, 'n_samples': len(iq),
        'n_cfo': len(cands), 'cands': cands,
        'n_off_carrier_cands': sum(1 for c in cands if c['band'] == 'off_carrier'),
        'n_band_edge_cands': sum(1 for c in cands if c['band_edge']),
        'detection_log10_p': d['detection_log10_p'],
        'sps_candidates': d['sps_candidates'],
        'n_front_ends': d['n_front_ends'],
        'rejected_serial': d['front_ends_rejected_serial_dependence'],
        'replication_ok': rep_ok,
        'n_admitted': len(adm), 'n_admitted_off_carrier': len(off_adm),
        'admitted_agreement_min': min(ag) if ag else None,
        'admitted_agreement_max': max(ag) if ag else None,
        'cfos_reaching_f1': sorted(reached), 'n_cfos_reaching_f1': len(reached),
        'off_carrier_reaches_f1': any(by_cfo.get(k, {}).get('band') == 'off_carrier'
                                      for k in reached),
        'best_f1_cfo': best_cfo,
        'best_f1_band': by_cfo.get(best_cfo, {}).get('band') if best_cfo is not None else None,
        'best_f1_rot': by_cfo.get(best_cfo, {}).get('rot') if best_cfo is not None else None,
        'f1_M': len(ah.get('cfo', [])), 'f4_best': best, 'f4_bar': bar,
        'f4_margin': None if (best is None or bar is None) else float(best - bar),
        'f4_accepted': bool(f4.get('accepted')), 'f4_code': a4.get('code'),
        'n_converged': None if conv is None else int(sum(conv)),
        'n_codewords': a4.get('n_codewords'),
        'status': r['status'], 'final_code': r['code'], 'outcome': outcome, 'correct': correct,
        # distinction 7: the front end that produced the PUBLISHED claim. result['cfo'] is set from
        # that front end (pipeline.py:385-407), and on an F4-supplied claim it IS F4's front end.
        'claim_cfo': r.get('cfo'), 'claim_sps': r.get('sps'), 'claim_band': _band(claim_rot),
        'claim_rot': claim_rot,
        'runtime': time.perf_counter() - t,
    }
    return row, adm


def _verdict_neutrality(rows):
    """The flag must not change what the engine decides: compare against F4-MARGIN-01 (flag OFF)."""
    if not os.path.exists(F4M_ROWS):
        return None, ['f4_margin rows missing']
    prev = {(r['dataset'], r['file']): r for r in
            (json.loads(l) for l in open(F4M_ROWS, encoding='utf-8'))}
    bad = []
    for r in rows:
        p = prev.get((r['dataset'], r['file']))
        if p is None:
            continue
        for k in ('status', 'final_code', 'f4_accepted', 'outcome'):
            if r[k] != p[k]:
                bad.append(f'{r["file"]}:{k} {p[k]!r}->{r[k]!r}')
        if (r['f4_best'] is not None and p['f4_best'] is not None
                and abs(r['f4_best'] - p['f4_best']) > 1e-9):
            bad.append(f'{r["file"]}:f4_best {p["f4_best"]}->{r["f4_best"]}')
    return len(prev), bad


def _j(o):
    return o.item() if hasattr(o, 'item') else str(o)


def run():
    jobs = f4m.jobs()
    print(f'SPACE-OFFCARRIER-CENSUS-01: {len(jobs)} sealed captures, {WORKERS} workers')
    t0 = time.perf_counter()
    rows, adm = [], []
    with Pool(WORKERS) as pool:
        for i, (row, a) in enumerate(pool.imap_unordered(_run_one, jobs, chunksize=8), 1):
            rows.append(row)
            adm.extend(a)
            if i % 200 == 0:
                print(f'  {i}/{len(jobs)}  {time.perf_counter() - t0:.0f}s')
    rows.sort(key=lambda r: (r['dataset'], r['file']))

    # noise-like reference: the MEDIAN peak_to_floor_db over candidates of the NO-SIGNAL captures,
    # per the criteria. Computed after the sweep because it is a property of that population.
    noise_ptf = [c['ptf_db'] for r in rows if r['is_noise_class'] for c in r['cands']
                 if c['ptf_db'] is not None]
    ref = float(np.median(noise_ptf)) if noise_ptf else None
    for r in rows:
        for c in r['cands']:
            c['noise_like'] = (None if (ref is None or c['ptf_db'] is None)
                               else bool(c['ptf_db'] <= ref))
        r['noise_like_ref_db'] = ref
        r['n_noise_like_cands'] = sum(1 for c in r['cands'] if c.get('noise_like'))
    for a in adm:
        a['noise_like_spectral'] = (None if (ref is None or a['ptf_db'] is None)
                                    else bool(a['ptf_db'] <= ref))
        a['noise_like_postdemod'] = bool(a['symbol_snr_db'] <= 0.0)

    n_prev, bad = _verdict_neutrality(rows)
    os.makedirs('results', exist_ok=True)
    with open(ROWS, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, default=_j) + '\n')
    with open(ADMITTED, 'w', encoding='utf-8') as f:
        for a in adm:
            f.write(json.dumps(a, default=_j) + '\n')
    print(f'\n{len(rows)} captures, {len(adm)} ADMITTED front ends -> {ROWS}, {ADMITTED}')
    print(f'wall {time.perf_counter() - t0:.0f}s; noise-like ptf reference {ref} dB '
          f'({len(noise_ptf)} candidates on no-signal captures)')
    print(f'replication matched the published counts on '
          f'{sum(1 for r in rows if r["replication_ok"])}/{len(rows)} captures')
    if bad:
        print(f'STOP: _all_hypotheses is NOT verdict-neutral, {len(bad)} differences vs '
              f'F4-MARGIN-01: {bad[:5]}')
    else:
        print(f'verdict-neutrality VERIFIED against F4-MARGIN-01 ({n_prev} captures, flag off)')


def _frac(n, d):
    return f'{n:5}/{d:<5} {100.0 * n / d if d else 0:6.2f}%'


def _wilson_upper(n):
    return 3.84 / (n + 3.84)


def report():
    rows = [json.loads(l) for l in open(ROWS, encoding='utf-8')]
    adm = [json.loads(l) for l in open(ADMITTED, encoding='utf-8')]
    sig = [r for r in rows if not r['is_noise_class']]       # carrier reference is meaningful
    noise = [r for r in rows if r['is_noise_class']]
    print(f'\nSPACE-OFFCARRIER-CENSUS-01 — {len(rows)} captures ({len(sig)} signal-bearing, '
          f'{len(noise)} no-signal), {len(adm)} admitted front ends')
    print(f'criteria sha256 {hashlib.sha256(open(CRITERIA, "rb").read()).hexdigest()[:16]}…')
    print(f'replication matched published counts: {sum(1 for r in rows if r["replication_ok"])}'
          f'/{len(rows)}\n')

    print('THE LADDER  (signal-bearing captures; each rung is a SEPARATE distinction)')
    print(f'  T1 candidate EXISTS off-carrier      {_frac(sum(1 for r in sig if r["n_off_carrier_cands"]), len(sig))}')
    print(f'  T2 off-carrier front end ADMITTED    {_frac(sum(1 for r in sig if r["n_admitted_off_carrier"]), len(sig))}')
    print(f'  T3 off-carrier REACHES F1 (see note) {_frac(sum(1 for r in sig if r["off_carrier_reaches_f1"]), len(sig))}')
    # T4 uses the PUBLISHED claim's front end: on an F4-supplied claim result['cfo'] is F4's own
    # front end. all_hypotheses could not be used here -- it is F1's table (see _run_one).
    t4 = [r for r in sig if r['f4_accepted'] and r['claim_band'] == 'off_carrier']
    print(f'  T4 off-carrier PASSES F4 (claim)     {_frac(len(t4), len(sig))}')
    t5 = [r for r in t4 if r['outcome'] == 'FALSE_ACCEPT']
    print(f'  T5 off-carrier -> WRONG CLAIM        {_frac(len(t5), len(sig))}')
    if not t4:
        print(f'     (T4 = 0 of {len(sig)}; Wilson 95% upper bound {_wilson_upper(len(sig)):.4f})')
    for e in SENSITIVITY_EDGES:
        ex = sum(1 for r in sig if any((c['rot'] or 0) > e for c in r['cands']))
        ad = sum(1 for r in sig if any(a['file'] == r['file'] and (a['rot'] or 0) > e for a in adm))
        print(f'  sensitivity rot>{e:<5}  exists {ex:5}  admitted-captures {ad:5}')

    print('\nADMITTED FRONT ENDS BY BAND  (the 4-way distinction, never assumed equal)')
    print('  band            n      agreement(min/med/max)   symbol SNR dB(med)  noise-like post')
    for b in ('on_carrier', 'near_carrier', 'off_carrier', 'undefined'):
        xs = [a for a in adm if a['band'] == b]
        if not xs:
            continue
        ag = np.array([a['agreement'] for a in xs])
        sn = np.array([a['symbol_snr_db'] for a in xs])
        nl = sum(1 for a in xs if a['noise_like_postdemod'])
        print(f'  {b:14}{len(xs):6}   {ag.min():.3f}/{np.median(ag):.3f}/{ag.max():.3f}'
              f'        {np.median(sn):7.2f}         {nl:6} ({100.0*nl/len(xs):.1f}%)')

    print('\nCROSS-TAB: serially independent (all admitted are, by construction) x noise-like')
    print(f'  admitted & noise-like (post-demod SNR<=0dB): '
          f'{_frac(sum(1 for a in adm if a["noise_like_postdemod"]), len(adm))}')
    print(f'  admitted & noise-like (spectral ptf):        '
          f'{_frac(sum(1 for a in adm if a.get("noise_like_spectral")), len(adm))}')
    reach = [a for a in adm if a['reached_f1']]
    print(f'  admitted that REACH F1 (burst table):        {_frac(len(reach), len(adm))}')
    if reach:
        print(f'    of those, off-carrier: {sum(1 for a in reach if a["band"] == "off_carrier")}'
              f'  noise-like: {sum(1 for a in reach if a["noise_like_postdemod"])}')

    print('\nBY CAPTURE CLASS  (concentration check; signal-bearing only)')
    byc = defaultdict(list)
    for r in sig:
        byc[(r['dataset'], r['cls'])].append(r)
    print('  dataset/class                    n   off-cand  off-admitted  off->F4  F4acc  FALSE_ACC')
    for k in sorted(byc, key=lambda k: (-sum(1 for r in byc[k] if r['n_admitted_off_carrier']),
                                        str(k))):
        xs = byc[k]
        oc = sum(1 for r in xs if r['n_off_carrier_cands'])
        oa = sum(1 for r in xs if r['n_admitted_off_carrier'])
        of = sum(1 for r in xs if r['off_carrier_reaches_f1'])
        fa = sum(1 for r in xs if r['f4_accepted'])
        fw = sum(1 for r in xs if r['outcome'] == 'FALSE_ACCEPT')
        if oa or of or fw or fa:
            print(f'  {k[0]}/{str(k[1]):22}{len(xs):5}{oc:9}{oa:14}{of:9}{fa:7}{fw:11}')

    print('\nNO-SIGNAL CAPTURES (no meaningful carrier exists; reported separately, never pooled)')
    na = [a for a in adm if a['band'] == 'undefined']
    print(f'  {len(noise)} captures, {sum(r["n_admitted"] for r in noise)} admitted front ends, '
          f'{sum(1 for r in noise if r["f4_accepted"])} F4 accepts, '
          f'{sum(1 for r in noise if r["outcome"] == "FALSE_ACCEPT")} FALSE_ACCEPT')
    if na:
        sn = np.array([a['symbol_snr_db'] for a in na])
        print(f'  their admitted front ends: symbol SNR median {np.median(sn):.2f} dB, '
              f'noise-like {sum(1 for a in na if a["noise_like_postdemod"])}/{len(na)}')

    print('\nPUBLISHED CLAIMS — which front end actually produced the engine output')
    dec = [r for r in rows if r['status'] == 'DECODED']
    print(f'  {len(dec)} DECODED captures; claim-producing front end by band: '
          f'{dict(Counter(r["claim_band"] for r in dec))}')
    for r in dec:
        if r['outcome'] == 'FALSE_ACCEPT':
            cr = r['claim_rot']
            print(f'    FALSE_ACCEPT {r["dataset"]}/{r["file"]:24} {str(r["final_code"]):34} '
                  f'claim band {r["claim_band"]:12} rot {cr if cr is None else round(cr, 4)}')

    print('\nF4-MARGIN LINKAGE  (accepts, and the closest approaches that did not accept)')
    acc = [r for r in rows if r['f4_accepted']]
    print(f'  F4 accepts: {len(acc)}  | claim off-carrier '
          f'{sum(1 for r in acc if r["claim_band"] == "off_carrier")}'
          f'  | claim on-carrier {sum(1 for r in acc if r["claim_band"] == "on_carrier")}'
          f'  | zero-convergence {sum(1 for r in acc if r["n_converged"] == 0)}'
          f'  | FALSE_ACCEPT {sum(1 for r in acc if r["outcome"] == "FALSE_ACCEPT")}')
    near = sorted((r for r in rows if not r['f4_accepted'] and r['f4_margin'] is not None),
                  key=lambda r: r['f4_margin'])[:10]
    print('  closest non-accepting approaches to the F4 bar (band = best F1 hypothesis, the only')
    print('  per-candidate table the engine publishes; F4 publishes no hypothesis->front map):')
    for r in near:
        rot = f'{r["best_f1_rot"]:.4f}' if r['best_f1_rot'] is not None else 'n/a'
        print(f'    {r["dataset"]}/{r["file"]:24} F4 margin {r["f4_margin"]:+.4f}  F1 M '
              f'{r["f1_M"]:6}  best F1-hyp {str(r["best_f1_band"]):12} rot {rot:8} {r["outcome"]}')


def demo():
    """Self-check: the committed band rule and the drifting-carrier reference."""
    assert _band(0.005) == 'on_carrier' and _band(0.05) == 'near_carrier'
    assert _band(0.5) == 'off_carrier' and _band(None) == 'undefined'
    assert _band(ON_CARRIER) == 'on_carrier' and _band(OFF_CARRIER) == 'near_carrier'
    # a static carrier is its own mean; a drifting one is referenced to the midpoint of the capture
    ref, d = _true_carrier({'cfo': 0.004}, 1001)
    assert ref == 0.004 and d is False
    ref, d = _true_carrier({'cfo': 0.004, 'cfo_drift_per_sample': 2e-6}, 1001)
    assert abs(ref - (0.004 + 2e-6 * 500)) < 1e-15 and d is True
    assert _true_carrier({}, 10) == (None, False)            # no carrier recorded -> no reference
    # the MECH-01 survivor: |cfo| 0.012377 at sps 18 sits far off-carrier and at the band edge
    rot = abs(-0.012377 - 0.00584) * 18
    assert _band(rot) == 'off_carrier' and abs(-0.012377) > BAND_EDGE_FRAC * CFO_MAX
    print('demo: band rule, drift reference and the MECH-01 signature self-checks pass')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'demo'
    os.chdir(ROOT)
    {'run': run, 'report': report, 'demo': demo}[cmd]()
