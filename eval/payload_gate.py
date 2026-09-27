"""SPACE-PAYLOAD-GATE-01 — request B measured: can a wrong payload become a refusal for free?

Criteria: `eval/payload_gate_criteria.json`, committed before this file existed.

Request B has stood BLOCKED with one stated reason: a payload-reliability gate "may cost static-carrier
recall, which must be measured first". This measures it, and nothing else.

The gate is applied as POST-PROCESSING of the engine's own published result — `stream_code`'s accepted
hypothesis already carries `consistency`, the re-encode agreement of the payload it published. Today
that number is used only for polarity tie-breaking. Nothing in src/ is modified here, and the engine's
own verdict is recorded unchanged beside the gated one.

The bar is set by the no-regression constraint, never by the failures it is meant to catch:

    bar = min(consistency) over the bench-v2 F2 claims that are scored CORRECT today

so the cost is zero by construction on that population and the benefit is whatever falls out.

    python eval/payload_gate.py run
    python eval/payload_gate.py report
"""

import glob
import hashlib
import json
import os
import sys
from collections import Counter
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding='utf-8')

import f4_margin as f4m                                   # noqa: E402  (populations + _correct)
from modem import load_iq                                 # noqa: E402
from pipeline import analyze_iq                           # noqa: E402  (SHIPPED, unmodified)

CRITERIA = os.path.join(HERE, 'payload_gate_criteria.json')
ROWS = os.path.join('results', 'payload_gate_rows.jsonl')
DOPPLER = os.path.join('data', 'space_bench', 'doppler')
SEALED_DOPPLER = os.path.join('results', 'space_doppler_rows.jsonl')
WORKERS = min(max(1, (os.cpu_count() or 2) - 1), 8)


def _f2_stats(r):
    """The payload-side numbers the engine already publishes for an accepted F2 hypothesis."""
    sc = r.get('stream_code') or {}
    if not sc.get('accepted'):
        return None
    ah = sc.get('accepted_hypothesis') or {}
    return {'consistency': ah.get('consistency'), 'path_metric': ah.get('path_metric'),
            'agreement': ah.get('agreement'), 'front': ah.get('front')}


def _f2_supplied(r):
    """Did F2 supply the published claim? Verdict order is F1 -> F4 -> F2 (pipeline.py)."""
    sc = r.get('stream_code') or {}
    return bool(r['status'] == 'DECODED' and sc.get('accepted')
                and r['code'] == (sc.get('code') or ''))


def _one(job):
    population, path, kind, gt = job
    r = analyze_iq(load_iq(path))
    st = _f2_stats(r)
    row = {'population': population, 'file': os.path.basename(path)[:-3],
           'cls': gt.get('class'), 'trajectory': gt.get('trajectory_class'),
           'severity': gt.get('severity'),
           'status': r['status'], 'code': r['code'],
           'f2_accepted': bool((r.get('stream_code') or {}).get('accepted')),
           'f2_supplied': _f2_supplied(r),
           'consistency': (st or {}).get('consistency'),
           'path_metric': (st or {}).get('path_metric'),
           'agreement': (st or {}).get('agreement')}
    if kind == 'doppler':
        row['outcome'] = None           # filled from the sealed row file, never recomputed
    else:
        outcome, correct = f4m._correct(kind, gt, r)
        row.update(outcome=outcome, correct=correct)
    return row


def jobs():
    out = []
    for population, d, kind in f4m.DATASETS:            # bench2_sealed, bench1_sealed, nullset
        for path in sorted(glob.glob(os.path.join(d, '*.iq'))):
            out.append((population, path, kind,
                        json.load(open(path + '.gt.json', encoding='utf-8'))))
    for path in sorted(glob.glob(os.path.join(DOPPLER, '*.iq'))):
        out.append(('doppler', path, 'doppler',
                    json.load(open(path + '.gt.json', encoding='utf-8'))))
    return out


def run():
    js = jobs()
    print(f'SPACE-PAYLOAD-GATE-01: {len(js)} captures, {WORKERS} workers')
    rows = []
    with Pool(WORKERS) as pool:
        for i, row in enumerate(pool.imap_unordered(_one, js, chunksize=8), 1):
            rows.append(row)
            if i % 300 == 0:
                print(f'  {i}/{len(js)}')
    # the Doppler outcome is the sealed experiment's own scoring, read not recomputed
    sealed = {json.loads(l)['file']: json.loads(l)
              for l in open(SEALED_DOPPLER, encoding='utf-8')}
    for r in rows:
        if r['population'] == 'doppler':
            prev = sealed.get(r['file'], {})
            r['outcome'] = prev.get('outcome')
            r['correct'] = prev.get('outcome') == 'DECODED_CORRECT'
    rows.sort(key=lambda r: (r['population'], r['file']))
    os.makedirs('results', exist_ok=True)
    with open(ROWS, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r) + '\n')
    n_f2 = sum(1 for r in rows if r['f2_supplied'])
    print(f'\n{len(rows)} captures -> {ROWS}; F2-supplied claims: {n_f2}')


# ---------------------------------------------------------------- the committed bar rule
def bar_from(rows):
    """bar = min(consistency) over bench-v2 F2 claims scored CORRECT today. Never sees a failure."""
    ok = [r['consistency'] for r in rows
          if r['population'] == 'bench2_sealed' and r['f2_supplied']
          and r['outcome'] in ('TP', 'TP_PARTIAL') and r['consistency'] is not None]
    return (min(ok) if ok else None), len(ok)


def gated(r, bar):
    """Post-processing only: withhold the payload, keep the structure. Never upgrades a refusal.

    The `status == 'DECODED'` guard is load-bearing and is not redundant. Without it a refusal with a
    low consistency would be rewritten to SIGNAL_NO_CODE, i.e. UNKNOWN ("no evidence") would become
    "a signal is there" — the gate would be manufacturing a structural claim rather than withholding
    a payload. Real rows cannot reach that branch because `f2_supplied` already implies DECODED, but
    the function must be correct on its own terms before it could ever be integrated.
    """
    if bar is None or r['status'] != 'DECODED' or not r['f2_supplied']:
        return r['status']
    if r['consistency'] is None:
        return r['status']
    return 'SIGNAL_NO_CODE' if r['consistency'] < bar else r['status']


def report():
    rows = [json.loads(l) for l in open(ROWS, encoding='utf-8')]
    bar, n_cal = bar_from(rows)
    print(f'\nSPACE-PAYLOAD-GATE-01 — {len(rows)} captures; criteria sha256 '
          f'{hashlib.sha256(open(CRITERIA, "rb").read()).hexdigest()[:16]}…')
    print(f'BAR = {bar!r}  (min consistency over {n_cal} currently-correct bench-v2 F2 claims;\n'
          f'  set by the no-regression constraint, never by the failures it catches)\n')

    print('SCOPE — which populations carry an F2-supplied claim at all')
    for pop in sorted({r['population'] for r in rows}):
        xs = [r for r in rows if r['population'] == pop]
        f2 = [r for r in xs if r['f2_supplied']]
        tail = (dict(Counter(r['outcome'] for r in f2)) if f2
                else '(gate cannot touch this population)')
        print(f'  {pop:14} {len(xs):5} captures, {len(f2):4} F2-supplied  {tail}')

    print('\nCOST — currently-correct decodes lost to the gate')
    for pop in ('bench2_sealed', 'bench1_sealed', 'nullset'):
        xs = [r for r in rows if r['population'] == pop and r.get('correct')]
        lost = [r for r in xs if gated(r, bar) != r['status']]
        print(f'  {pop:14} correct today {len(xs):4}  lost to the gate {len(lost):3}'
              + (f'  -> {[r["file"] for r in lost][:4]}' if lost else ''))

    print('\nBENEFIT 1 — the 3 known structural false accepts (bench-v2 sealed)')
    fa = [r for r in rows if r['population'] == 'bench2_sealed' and r['outcome'] == 'FALSE_ACCEPT']
    for r in fa:
        g = gated(r, bar)
        c = r['consistency']
        print(f'  {r["file"]:26} consistency {c if c is None else round(c, 4)}  '
              f'{r["status"]} -> {g}'
              f'{"   CONVERTED TO REFUSAL" if g != r["status"] else "   still published"}')

    print('\nBENEFIT 2 — the sealed Doppler wrong payloads (NOT a blind estimate: see declared_peek)')
    dop = [r for r in rows if r['population'] == 'doppler']
    wrong = [r for r in dop if r['outcome'] == 'FALSE_DECODE']
    right = [r for r in dop if r['outcome'] == 'DECODED_CORRECT']
    conv = [r for r in wrong if gated(r, bar) != r['status']]
    lost = [r for r in right if gated(r, bar) != r['status']]
    print(f'  wrong payloads {len(wrong):3}  converted to refusal {len(conv):3} '
          f'({100.0 * len(conv) / max(len(wrong), 1):.1f}%)')
    print(f'  correct payloads {len(right):3}  lost {len(lost):3} '
          f'({100.0 * len(lost) / max(len(right), 1):.1f}%)')
    f2w = [r for r in wrong if r['f2_supplied']]
    print(f'  of the wrong payloads, {len(f2w)} are F2-supplied (in scope); '
          f'{len(wrong) - len(f2w)} are not and the gate cannot see them')

    print('\nSEPARATION on the statistics (F2-supplied claims only)')
    for key in ('consistency', 'path_metric', 'agreement'):
        for lbl, xs in (('correct', [r for r in rows if r['f2_supplied'] and r.get('correct')]),
                        ('wrong  ', [r for r in rows if r['f2_supplied'] and not r.get('correct')
                                     and r['outcome'] in ('FALSE_ACCEPT', 'FALSE_DECODE')])):
            v = sorted(r[key] for r in xs if r[key] is not None)
            if v:
                print(f'  {key:12} {lbl} n={len(v):3} min {v[0]:.4f} med {v[len(v) // 2]:.4f} '
                      f'max {v[-1]:.4f}')


def demo():
    """Self-check: the gate withholds a payload, never invents or upgrades one."""
    bar = 0.98
    keep = {'f2_supplied': True, 'consistency': 0.999, 'status': 'DECODED'}
    drop = {'f2_supplied': True, 'consistency': 0.91, 'status': 'DECODED'}
    other = {'f2_supplied': False, 'consistency': None, 'status': 'DECODED'}
    refused = {'f2_supplied': False, 'consistency': None, 'status': 'UNKNOWN'}
    assert gated(keep, bar) == 'DECODED'
    assert gated(drop, bar) == 'SIGNAL_NO_CODE'          # payload withheld, structure kept
    assert gated(other, bar) == 'DECODED'                # out of scope: F1/F3/F4 untouched
    assert gated(refused, bar) == 'UNKNOWN'              # never upgrades a refusal
    assert gated(drop, None) == 'DECODED'                # no bar -> no change
    print('demo: the gate withholds payloads, leaves other families alone, upgrades nothing')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'demo'
    os.chdir(ROOT)
    {'run': run, 'report': report, 'demo': demo}[cmd]()
