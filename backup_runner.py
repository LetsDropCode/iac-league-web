"""Render runtime supervisor: initial off-disk backup, then hourly backups on disk owner."""
from contextlib import contextmanager
import fcntl
import logging
import os
import signal
import subprocess
import sys
import threading
import time

from storage import get_storage, atomic_write, StorageError
from backup_monitor import monitor_loop, emit_health
from storage_ops import S3Backups, encoded


def run_backup(store, remote, retain):
    try:
        receipt = remote.backup(store, retain)
        receipt['last_success'] = time.time()
        atomic_write(store.path('.backup-status.json'), encoded(receipt))
        logging.info('BACKUP_VERIFIED key=%s', receipt['key'])
        return True
    except Exception as exc:
        logging.error('BACKUP_FAILED type=%s: independent backup not verified; operator action required', type(exc).__name__)
        try:
            atomic_write(store.path('.backup-status.json'), encoded({'failed_at': time.time(), 'verified': False}))
        except Exception:
            logging.error('BACKUP_STATUS_WRITE_FAILED: check disk capacity and mount')
        return False


@contextmanager
def scheduler_lock(store):
    """One runtime scheduler per disk, regardless of Gunicorn worker count."""
    with store.path('.backup-scheduler.lock').open('a+b') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise StorageError('Another backup scheduler owns this data directory.') from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def main():
    logging.basicConfig(level=logging.INFO)
    store = get_storage()
    with scheduler_lock(store):
        return supervise(store)


def supervise(store):
    remote = S3Backups()
    interval = int(os.getenv('LEAGUE_BACKUP_INTERVAL_SECONDS', '3600'))
    retain = int(os.getenv('LEAGUE_BACKUP_RETAIN', '168'))
    if not 60 <= interval <= 86400 or retain < 2:
        raise ValueError('Backup interval must be 60..86400 seconds and retention >= 2.')
    service = os.environ.get('LEAGUE_MONITOR_SERVICE')
    if not service:
        raise StorageError('LEAGUE_MONITOR_SERVICE is required; provision and test its CloudWatch alarm.')
    import boto3
    from botocore.config import Config
    monitor_client = boto3.client('cloudwatch', config=Config(connect_timeout=5, read_timeout=10,
                                                             retries={'max_attempts': 2}))
    workers = int(os.getenv('WEB_CONCURRENCY', '2'))
    if not 1 <= workers <= 8:
        raise StorageError('WEB_CONCURRENCY must be 1..8.')
    stopped = threading.Event()
    if not run_backup(store, remote, retain):
        return 1
    # Check monitoring credentials before opening the web listener.
    emit_health(store, monitor_client, service)
    monitor = threading.Thread(target=monitor_loop, args=(store, monitor_client, service, stopped), daemon=True)
    monitor.start()

    def loop():
        while not stopped.wait(interval):
            run_backup(store, remote, retain)

    worker = threading.Thread(target=loop, daemon=True)
    worker.start()
    child = subprocess.Popen([sys.executable, '-m', 'gunicorn', '--bind',
                              '0.0.0.0:' + os.getenv('PORT', '10000'), '--workers', str(workers), '--access-logfile', '-',
                              '--access-logformat', '%(p)s %(s)s', 'app:app'])

    def shutdown(signum, frame):
        stopped.set()
        child.send_signal(signum)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    try:
        return child.wait()
    finally:
        stopped.set()


if __name__ == '__main__':
    sys.exit(main())
