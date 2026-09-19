"""One writer at a time for the results directory.

The receipt ledger and the CRM outbox are append-only files guarded by in-process locks
(`receipt.append_chained`, `crm._OUTBOX_LOCK`). Those make the stores safe against the threads of
one server. They do nothing whatever about a *second* server process pointed at the same directory:
two processes would each read the ledger head, each append against it, and the chain would fork --
the exact defect the in-process lock was added to prevent, one level up.

The cheap and wrong fix is to make every append cross-process safe: an OS lock on every write, on
two platforms, for a prototype that runs one process. The right fix is to make the unsafe
configuration impossible. Take an exclusive OS lock at start-up and hold it for the life of the
process; a second server on the same directory then refuses to start and says why, instead of
quietly forking the evidence chain.

The OS releases the lock when the process dies, so a crash leaves nothing to clean up and there is
no stale-lock guesswork.

Two files, deliberately. On Windows the lock is MANDATORY: while it is held, no other process may
read a byte of that file, not even to discover who holds it. So the lock file carries no information
at all, and the human-readable record lives beside it. The lock is the authority; the record is a
diagnostic that may be stale after a crash, which is why the refusal says "last recorded holder"
rather than asserting what is running now.

This is a single-writer guarantee, not a distributed one. Running ICHNOVA on two machines against
one shared filesystem is out of scope and is not made safe by this module; see deploy/README.md.
"""

import datetime as dt
import json
import os

LOCK_NAME = '.writer.lock'
RECORD_NAME = '.writer.json'


class AlreadyRunning(RuntimeError):
    """Another process already holds the results directory."""


def _lock_exclusive(handle):
    """Take a non-blocking exclusive lock. Raises OSError when another process holds it."""
    try:
        import fcntl                                  # POSIX: advisory, whole file
    except ImportError:
        import msvcrt                                 # Windows: mandatory
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def acquire(results_dir):
    """Become the single writer for `results_dir`, for the life of this process.

    Returns the open handle. **Keep it**: dropping it releases the lock. Raises AlreadyRunning when
    another process already has the directory.
    """
    os.makedirs(results_dir, exist_ok=True)
    lock_path = os.path.join(results_dir, LOCK_NAME)
    record_path = os.path.join(results_dir, RECORD_NAME)
    handle = open(lock_path, 'a+', encoding='utf-8')
    try:
        _lock_exclusive(handle)
    except OSError:
        handle.close()
        held = ''
        try:
            with open(record_path, encoding='utf-8') as f:
                rec = json.loads(f.read() or '{}')
            held = (f" (last recorded holder: pid {rec.get('pid', 'unknown')}, "
                    f"since {rec.get('since', 'unknown')})")
        except (ValueError, OSError):
            pass                                      # diagnostics only; the refusal stands either way
        raise AlreadyRunning(
            f'another ICHNOVA process is already writing {results_dir}{held}. The receipt ledger and '
            f'the CRM outbox are safe for one process only: a second writer forks the evidence chain. '
            f'Stop the other process, or give this one its own results directory.') from None
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
    with open(record_path, 'w', encoding='utf-8') as f:
        json.dump({'pid': os.getpid(), 'since': now}, f)
    return handle
