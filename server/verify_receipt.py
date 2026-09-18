"""Verify evidence receipts independently.

    python server/verify_receipt.py                       verify the whole ledger
    python server/verify_receipt.py --ledger PATH         verify a ledger elsewhere
    python server/verify_receipt.py --receipt R.json      verify one exported receipt
    python server/verify_receipt.py --receipt R.json --capture C.iq [--wav]
                                                          also check it belongs to that capture

Exit status is 0 when everything verifies and 1 otherwise, so this can gate a review.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'src'))

import receipt as receipts             # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description='Verify ICHNOVA evidence receipts')
    ap.add_argument('--ledger', default=os.path.join(ROOT, 'results', 'ledger.jsonl'))
    ap.add_argument('--receipt', help='a single exported receipt (JSON)')
    ap.add_argument('--capture', help='the capture the receipt should belong to')
    ap.add_argument('--wav', action='store_true', help='the capture is int16 stereo .wav, not float32 .iq')
    ap.add_argument('--json', action='store_true', help='machine-readable output')
    a = ap.parse_args(argv)

    report = {}
    ok = True

    if a.receipt:
        with open(a.receipt, encoding='utf-8') as f:
            rec = json.load(f)
        good, detail = receipts.verify_receipt(rec)
        report['receipt'] = {'ok': good, 'detail': detail, 'hash': rec.get('hash')}
        ok &= good
        if a.capture:
            from modem import load_iq, load_wav
            iq = load_wav(a.capture)[0] if a.wav else load_iq(a.capture)
            same, detail = receipts.verify_against_capture(rec, iq)
            report['capture'] = {'ok': same, **detail}
            ok &= same
    else:
        chain = receipts.verify_chain(receipts.read_ledger(a.ledger))
        report['ledger'] = {'path': a.ledger, **chain}
        ok &= chain['ok']

    if a.json:
        print(json.dumps(report, indent=1))
    else:
        for section, body in report.items():
            mark = 'OK  ' if body.get('ok') else 'FAIL'
            print(f'[{mark}] {section}')
            for k, v in body.items():
                if k != 'ok':
                    print(f'        {k}: {v}')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
