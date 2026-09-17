"""Decision-identity check between two runs of the same evaluation (Constitution §32, performance/refactor gate).

usage:
  python eval/identity.py BEFORE.jsonl AFTER.jsonl

Rows are matched by `file` (order-free). A row differs when any key present in BEFORE has a different
value in AFTER (exact comparison, recursively; keys only in AFTER are new fields and are ignored). Timing
fields (runtime, timers, timers_s) are never compared. Works on results/nullset_rows.jsonl and on
results/<dataset>_diagnostics.jsonl from sealed_test.py.
"""

import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
SKIP = {'runtime', 'timers', 'timers_s', 'total_time', 'mean_time', 'analysed_at', 'metadata'}


def diff(a, b, path=''):
    if isinstance(a, dict):
        if not isinstance(b, dict):
            return [path]
        out = []
        for k, v in a.items():
            if k in SKIP:
                continue
            if k not in b:
                out.append(f'{path}.{k} (missing)')
            else:
                out += diff(v, b[k], f'{path}.{k}')
        return out
    if isinstance(a, list):
        if not isinstance(b, list) or len(a) != len(b):
            return [path]
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in diff(x, y, f'{path}[{i}]')]
    return [] if a == b else [path]


def main(before, after):
    A = {r['file']: r for r in map(json.loads, open(before, encoding='utf-8'))}
    B = {r['file']: r for r in map(json.loads, open(after, encoding='utf-8'))}
    missing = sorted(set(A) - set(B))
    changed = {f: d for f in sorted(set(A) & set(B)) if (d := diff(A[f], B[f]))}
    print(f'{len(A)} rows before, {len(B)} after, {len(missing)} missing, {len(changed)} with differences')
    for f, d in list(changed.items())[:20]:
        print(f'  {f}: {", ".join(d[:6])}{" ..." if len(d) > 6 else ""}')
    return 0 if not missing and not changed else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2]))
