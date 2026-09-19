"""The single-writer guarantee that the in-process locks rest on.

`receipt.append_chained` and the outbox lock serialise the threads of one server. Two *processes*
on one results directory would each read the ledger head and each append against it, forking the
evidence chain — the same defect one level up, and one no in-process lock can reach. So the unsafe
configuration is made impossible instead: the second process refuses to start.

The cross-process tests really do start a second interpreter. An in-process test cannot prove this:
on POSIX a second flock from the same process succeeds, which is exactly the case that must not be
mistaken for a passing test.
"""

import json
import os
import subprocess
import sys
import textwrap

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'server'))

import store_lock                                   # noqa: E402


def _second_process(results_dir):
    """Try to take the lock from a genuinely separate interpreter."""
    code = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {os.path.join(ROOT, 'server')!r})
        import store_lock
        try:
            store_lock.acquire({str(results_dir)!r})
            print('ACQUIRED')
        except store_lock.AlreadyRunning as e:
            print('REFUSED:' + str(e))
    """)
    return subprocess.run([sys.executable, '-c', code], capture_output=True, text=True,
                          timeout=60).stdout.strip()


def test_the_lock_records_who_holds_it(tmp_path):
    handle = store_lock.acquire(str(tmp_path))
    try:
        held = json.loads((tmp_path / store_lock.RECORD_NAME).read_text(encoding='utf-8'))
        assert held['pid'] == os.getpid()
        assert held['since'].endswith('Z')
    finally:
        handle.close()


def test_a_second_process_is_refused_while_the_first_holds_it(tmp_path):
    handle = store_lock.acquire(str(tmp_path))
    try:
        out = _second_process(tmp_path)
    finally:
        handle.close()
    assert out.startswith('REFUSED:'), out
    assert 'forks the evidence chain' in out
    assert str(os.getpid()) in out, 'the refusal should name the process holding the directory'


def test_the_lock_is_released_when_the_holder_goes_away(tmp_path):
    """No stale-lock bookkeeping: the OS drops it when the process dies, crash included."""
    handle = store_lock.acquire(str(tmp_path))
    handle.close()
    assert _second_process(tmp_path) == 'ACQUIRED'


def test_separate_results_directories_do_not_collide(tmp_path):
    """Two instances are fine as long as each owns its own evidence."""
    a = store_lock.acquire(str(tmp_path / 'a'))
    try:
        assert _second_process(tmp_path / 'b') == 'ACQUIRED'
    finally:
        a.close()


def test_the_server_takes_the_lock_at_start_up():
    """The guard is only worth anything if it is actually wired into start-up."""
    src = open(os.path.join(ROOT, 'server', 'app.py'), encoding='utf-8').read()
    assert 'store_lock.acquire' in src and 'refusing to start' in src, \
        'server/app.py no longer takes the single-writer lock at start-up'


def test_an_os_level_lock_is_reachable_on_this_platform():
    """The module picks fcntl or msvcrt; at least one exists wherever this runs."""
    import importlib
    have = []
    for name in ('fcntl', 'msvcrt'):
        try:
            importlib.import_module(name)
            have.append(name)
        except ImportError:
            pass
    assert have, 'neither fcntl nor msvcrt is importable, so no OS lock is reachable'
