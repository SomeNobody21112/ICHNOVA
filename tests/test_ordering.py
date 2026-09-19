"""Ordering and concurrency: the two append-only stores must not lose or fork what they are given.

Both stores are read-modify-write. The analysis server is a ThreadingHTTPServer, so two requests
really do run at once, and both of these races were reachable from the API before the locks:

- the receipt ledger read its head and appended as two separate steps, so two analyses finishing
  together claimed the same predecessor and the chain forked;
- the CRM outbox read every row, changed one and rewrote the file, so the later of two concurrent
  writers silently dropped the earlier one's row.

The first test in each pair reproduces the defect deterministically with the unserialised sequence,
so these tests keep failing for the right reason if the locks are removed.
"""

import os
import sys
import threading

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, os.path.join(ROOT, 'server'))

import receipt as receipts                 # noqa: E402
import crm                                 # noqa: E402

WORKERS = 24


def _receipt(prev_hash, i):
    return receipts.build(capture_sha256=f'{i:064x}', engine={'version': 'test'},
                          decision={'status': 'UNKNOWN', 'n': i}, statistics={}, prev_hash=prev_hash)


def _run(fn, n=WORKERS):
    """Start n threads that all wait on one barrier, so they collide instead of queueing politely."""
    barrier = threading.Barrier(n)
    errors = []

    def worker(i):
        barrier.wait()
        try:
            fn(i)
        except Exception as e:                       # noqa: BLE001 - reported, not swallowed
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert not errors, errors
    assert not any(t.is_alive() for t in threads), 'a worker did not finish'


# ----------------------------------------------------------------- receipt ledger


def test_reading_the_head_and_appending_separately_forks_the_chain(tmp_path):
    """The defect, stated as a test: two writers that read the head before either appends."""
    path = str(tmp_path / 'ledger.jsonl')
    head = receipts.last_hash(path)
    a, b = _receipt(head, 1), _receipt(head, 2)      # both built against the same predecessor
    receipts.append(a, path)
    receipts.append(b, path)
    report = receipts.verify_chain(receipts.read_ledger(path))
    assert not report['ok']
    assert 'broken link' in report['problems'][0]['problem']


def test_concurrent_receipts_do_not_fork_the_chain(tmp_path):
    path = str(tmp_path / 'ledger.jsonl')
    _run(lambda i: receipts.append_chained(path, lambda prev: _receipt(prev, i)))
    ledger = receipts.read_ledger(path)
    assert len(ledger) == WORKERS
    report = receipts.verify_chain(ledger)
    assert report['ok'], report['problems']
    assert report['checked'] == WORKERS
    # Every receipt appears exactly once and every predecessor is claimed exactly once.
    assert len({r['hash'] for r in ledger}) == WORKERS
    assert len({r['prev_hash'] for r in ledger}) == WORKERS


def test_a_forked_chain_is_still_detected_after_the_fix(tmp_path):
    """The lock removes the false alarm; it must not remove the true one."""
    path = str(tmp_path / 'ledger.jsonl')
    for i in range(4):
        receipts.append_chained(path, lambda prev, i=i: _receipt(prev, i))
    lines = open(path, encoding='utf-8').read().splitlines()
    open(path, 'w', encoding='utf-8').write('\n'.join([lines[0], lines[2], lines[1], lines[3]]) + '\n')
    assert not receipts.verify_chain(receipts.read_ledger(path))['ok']


# ----------------------------------------------------------------- CRM outbox


@pytest.fixture
def outbox(tmp_path):
    return crm.Outbox(path=str(tmp_path / 'outbox.jsonl'))


def test_rewriting_from_a_stale_snapshot_drops_a_case(outbox):
    """The defect, stated as a test: two writers that both read before either writes."""
    first, second = outbox._read(), outbox._read()
    first.append({'id': 'A', 'state': crm.PENDING})
    second.append({'id': 'B', 'state': crm.PENDING})
    outbox._write(first)
    outbox._write(second)                            # written from a snapshot taken before A existed
    assert [r['id'] for r in outbox._read()] == ['B']


def test_concurrent_queueing_keeps_every_case(outbox):
    _run(lambda i: outbox.add(f'RECEIPT-{i:02d}', 'case', {'pack_id': f'CAP-{i}'}))
    rows = outbox._read()
    assert len(rows) == WORKERS
    assert {r['id'] for r in rows} == {f'RECEIPT-{i:02d}' for i in range(WORKERS)}
    assert outbox.counts()['pending'] == WORKERS


def test_one_decision_queues_one_case_however_many_times_it_is_clicked(outbox):
    created = []
    _run(lambda i: created.append(outbox.add('RECEIPT-SAME', 'case', {'pack_id': 'CAP-1'})[1]))
    assert sum(created) == 1, 'the idempotency key must win exactly once'
    assert len(outbox._read()) == 1


def test_a_case_queued_during_delivery_is_not_lost(outbox):
    """flush() updates rows while the console may be queueing another case."""
    for i in range(6):
        outbox.add(f'OLD-{i}', 'case', {'pack_id': f'CAP-{i}'})

    def work(i):
        if i % 2:
            outbox.update(f'OLD-{i // 2}', state=crm.SENT, remote_id=f'500{i}')
        else:
            outbox.add(f'NEW-{i}', 'case', {'pack_id': f'CAP-new-{i}'})

    _run(work, n=12)
    rows = {r['id']: r for r in outbox._read()}
    assert len([k for k in rows if k.startswith('OLD-')]) == 6
    assert len([k for k in rows if k.startswith('NEW-')]) == 6
    assert all(rows[f'OLD-{i}']['state'] == crm.SENT for i in range(3))
