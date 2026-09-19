"""Evidence receipts: a hash chain over decisions, verifiable by someone who does not trust us.

A receipt records what was analysed (capture hash), by what (engine version, commit, acceptance
configuration), what was decided (verdict and the statistics behind it) and when. Each receipt
carries the hash of the previous one, so a receipt cannot be altered, removed or reordered without
breaking every receipt after it.

What a receipt proves, and what it does not:

- It proves the recorded decision belongs to that exact capture and that engine configuration, and
  that the ledger has not been edited since.
- It does not prove the decision is correct, and it is not a signature: anyone holding the ledger can
  recompute the chain. Signing would need a key the prototype has nowhere safe to keep.

Verification is independent of this module's own bookkeeping: `verify_chain` recomputes every hash
from the receipt content, so a receipt altered anywhere fails.
"""

import datetime
import hashlib
import json
import os
import threading

LEDGER_VERSION = 1
GENESIS = '0' * 64


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_array(iq):
    """Hash of a capture as the engine saw it: interleaved float32 I/Q, little-endian."""
    import numpy as np
    a = np.asarray(iq)
    inter = np.empty(2 * a.size, dtype='<f4')
    inter[0::2] = np.real(a).astype('<f4')
    inter[1::2] = np.imag(a).astype('<f4')
    return sha256_bytes(inter.tobytes())


def canonical(obj):
    """Stable serialisation: sorted keys, no insignificant whitespace. The hash depends on content
    only, never on key order or formatting."""
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False, default=str)


def receipt_hash(body):
    return sha256_bytes(canonical(body).encode('utf-8'))


def build(*, capture_sha256, engine, decision, statistics, source=None, prev_hash=GENESIS,
          created_utc=None, capture=None):
    """Build a receipt. `engine` should carry version, commit and the acceptance configuration."""
    body = {
        'ledger_version': LEDGER_VERSION,
        'created_utc': created_utc or datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec='seconds').replace('+00:00', 'Z'),
        'capture': {'sha256': capture_sha256, **(capture or {})},
        'engine': engine,
        'decision': decision,
        'statistics': statistics,
        'source': source,
        'prev_hash': prev_hash,
    }
    return {**body, 'hash': receipt_hash(body)}


def append(receipt, path):
    """Append a receipt to the ledger. Returns the receipt."""
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'a', encoding='utf-8') as f:
        f.write(canonical(receipt) + '\n')
    return receipt


def last_hash(path):
    """Hash of the most recent receipt, or the genesis value when the ledger is empty."""
    if not os.path.exists(path):
        return GENESIS
    tail = GENESIS
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    tail = json.loads(line).get('hash', tail)
                except json.JSONDecodeError:
                    return tail
    return tail


_CHAIN_LOCKS = {}
_CHAIN_LOCKS_GUARD = threading.Lock()


def _chain_lock(path):
    key = os.path.abspath(path)
    with _CHAIN_LOCKS_GUARD:
        lock = _CHAIN_LOCKS.get(key)
        if lock is None:
            lock = _CHAIN_LOCKS[key] = threading.Lock()
    return lock


def append_chained(path, build):
    """Read the head, build a receipt against it and append it, as one indivisible step.

    The chain invariant is that entry N's `prev_hash` is entry N-1's `hash`. Reading the head and
    appending are two separate operations, and the server is threaded: two analyses finishing at the
    same moment both read the same head, both claim it, and the ledger forks. `verify_chain` then
    reports a broken link at an entry nobody touched — a false tamper alarm, which for this system is
    worse than a missed one, because the whole point of the receipt is that a break means something.

    `build` is called with the head hash and must return the receipt to append.
    """
    # ponytail: one lock per ledger path, so one process is serialised. Two *processes* writing the
    # same ledger can still fork it; an OS file lock (msvcrt.locking / fcntl.flock) is the upgrade
    # path if the deployment ever runs more than one writer.
    with _chain_lock(path):
        receipt = build(last_hash(path))
        append(receipt, path)
        return receipt


def read_ledger(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f'ledger line {i} is not valid JSON: {e}') from None
    return out


def verify_receipt(receipt):
    """Recompute one receipt's own hash. Returns (ok, detail)."""
    body = {k: v for k, v in receipt.items() if k != 'hash'}
    want = receipt_hash(body)
    if want != receipt.get('hash'):
        return False, (f'content does not match its hash (recomputed {want[:12]}..., '
                       f"stored {str(receipt.get('hash'))[:12]}...)")
    return True, 'hash matches content'


def verify_chain(receipts):
    """Verify a whole ledger: each receipt's hash, and each link to the one before.

    Returns a dict with ok, checked, and the problems found, naming each broken position."""
    problems = []
    prev = GENESIS
    for i, r in enumerate(receipts):
        ok, detail = verify_receipt(r)
        if not ok:
            problems.append({'index': i, 'receipt': r.get('hash'), 'problem': f'altered: {detail}'})
        if r.get('prev_hash') != prev:
            problems.append({'index': i, 'receipt': r.get('hash'),
                             'problem': (f"broken link: prev_hash {str(r.get('prev_hash'))[:12]}... "
                                         f'does not match the previous receipt {prev[:12]}...')})
        prev = r.get('hash', prev)
    return {'ok': not problems, 'checked': len(receipts), 'problems': problems,
            'head': receipts[-1]['hash'] if receipts else GENESIS}


def verify_against_capture(receipt, iq):
    """Check that a receipt belongs to this capture."""
    got = sha256_array(iq)
    want = (receipt.get('capture') or {}).get('sha256')
    return got == want, {'capture_sha256': got, 'receipt_capture_sha256': want}


def summarise(result, pack_id=None):
    """The decision and statistics a receipt records, taken from a pipeline result."""
    accept = result.get('accept') or {}
    decision = {'pack_id': pack_id, 'status': result.get('status'), 'code': result.get('code'),
                'modulation': result.get('modulation'), 'sps': result.get('sps'),
                'interleaver': result.get('interleaver'),
                'payload_bits': int(len(result.get('payload_bits', [])))}   # numpy array: len(), not truthiness
    statistics = {'log10_p': accept.get('log10_p'), 'log10_threshold': accept.get('log10_threshold'),
                  'n_hypotheses': accept.get('n_hypotheses'), 'alpha': accept.get('alpha'),
                  'families': [{k: f.get(k) for k in ('name', 'weight', 'M', 'log10_threshold',
                                                      'best_log10_p', 'accepted')}
                               for f in (accept.get('families') or [])]}
    return decision, statistics
