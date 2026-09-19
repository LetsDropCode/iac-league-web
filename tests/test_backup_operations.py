import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from backup_monitor import backup_healthy, emit_health, monitor_loop
from backup_runner import scheduler_lock
from storage import Storage, StorageError, checksum, atomic_write
from storage_ops import snapshot, unpack
from ops.staging_probe import seed, RESULT, CORRECTED, evidence


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'LEAGUE_DEPLOYMENT_STAGE': 'staging'})
        self.env.start()
        self.store = seed(Path(self.temp.name).resolve() / 'synthetic')
        self.store.publish('results/synthetic.csv', RESULT)

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_single_scheduler_across_processes(self):
        script = ('import sys; from storage import Storage; from backup_runner import scheduler_lock; '
                  's=Storage(sys.argv[1]); c=scheduler_lock(s); c.__enter__()')
        with scheduler_lock(self.store):
            result = subprocess.run([sys.executable, '-c', script, str(self.store.root)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'Another backup scheduler', result.stderr)
        result = subprocess.run([sys.executable, '-c', script, str(self.store.root)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_backup_snapshot_blocks_import_until_consistent(self):
        entered, release, wrote = threading.Event(), threading.Event(), threading.Event()
        original_inventory = self.store.inventory
        def inventory():
            entered.set()
            self.assertTrue(release.wait(5))
            return original_inventory()
        result = []
        def backup():
            result.append(snapshot(self.store))
        def publish():
            self.store.publish('results/synthetic.csv', CORRECTED, checksum(RESULT))
            wrote.set()
        with patch.object(self.store, 'inventory', side_effect=inventory):
            reader = threading.Thread(target=backup)
            reader.start()
            self.assertTrue(entered.wait(5))
            writer = threading.Thread(target=publish)
            writer.start()
            self.assertFalse(wrote.wait(0.1))
            release.set()
            reader.join(5)
            writer.join(5)
        self.assertTrue(wrote.is_set())
        _, payloads = unpack(result[0])
        self.assertEqual(payloads['results/synthetic.csv'], RESULT)
        self.assertEqual(self.store.path('results/synthetic.csv').read_bytes(), CORRECTED)

    def test_failed_missing_stale_future_and_healthy_monitor_status(self):
        now = 10000
        self.assertFalse(backup_healthy(self.store, now))
        for status, expected in [({'verified': True, 'last_success': now}, True),
                                 ({'verified': False, 'last_success': now}, False),
                                 ({'verified': True, 'last_success': now - 7200}, False),
                                 ({'verified': True, 'last_success': now + 1}, False)]:
            atomic_write(self.store.path('.backup-status.json'), json.dumps(status).encode())
            self.assertEqual(backup_healthy(self.store, now), expected)

    def test_metric_is_credential_free_and_reflects_failure(self):
        calls = []
        class CloudWatch:
            def put_metric_data(self, **kwargs):
                calls.append(kwargs)
        emit_health(self.store, CloudWatch(), 'iac-league-staging')
        self.assertEqual(calls[0]['MetricData'][0]['Value'], 0)
        atomic_write(self.store.path('.backup-status.json'), json.dumps({'verified': True, 'last_success': time.time()}).encode())
        emit_health(self.store, CloudWatch(), 'iac-league-staging')
        self.assertEqual(calls[1]['MetricData'][0]['Value'], 1)
        self.assertNotIn('Synthetic', json.dumps(calls))

    def test_monitor_outage_does_not_log_secret_exception(self):
        stopped = threading.Event()
        class FailedClient:
            def put_metric_data(self, **kwargs):
                stopped.set()
                raise OSError('SENSITIVE_TEST_SENTINEL')
        with self.assertLogs(level='ERROR') as log:
            monitor_loop(self.store, FailedClient(), 'iac-league-staging', stopped)
        self.assertIn('BACKUP_MONITOR_FAILED', log.output[0])
        self.assertNotIn('SENSITIVE_TEST_SENTINEL', log.output[0])

    def test_invalid_and_interrupted_replacement_and_rollback(self):
        before = evidence(self.store)['standings_sha256']
        with self.assertRaises(ValueError):
            self.store.publish('results/synthetic.csv', b'invalid', checksum(RESULT))
        original = os.replace
        def fail(source, target):
            if Path(target) == self.store.path('results/synthetic.csv'):
                raise OSError('interrupted')
            original(source, target)
        with patch('storage.os.replace', side_effect=fail), self.assertRaises(OSError):
            self.store.publish('results/synthetic.csv', CORRECTED, checksum(RESULT))
        self.assertEqual(evidence(self.store)['standings_sha256'], before)
        self.store.publish('results/synthetic.csv', CORRECTED, checksum(RESULT))
        self.assertNotEqual(evidence(self.store)['standings_sha256'], before)
        self.store.publish('results/synthetic.csv', RESULT, checksum(CORRECTED))
        self.assertEqual(evidence(self.store)['standings_sha256'], before)

    def test_pause_is_shared_by_all_publishers(self):
        atomic_write(self.store.path('.imports-paused'), b'maintenance')
        with self.assertRaisesRegex(StorageError, 'paused'):
            self.store.publish('results/synthetic.csv', CORRECTED, checksum(RESULT))
        self.assertEqual(self.store.path('results/synthetic.csv').read_bytes(), RESULT)

    def test_staging_seed_rejects_nonempty_and_production(self):
        with self.assertRaises(StorageError):
            seed(self.store.root)
        with patch.dict(os.environ, {'LEAGUE_DEPLOYMENT_STAGE': 'production'}), self.assertRaises(StorageError):
            seed(Path(self.temp.name).resolve() / 'production')


if __name__ == '__main__':
    unittest.main()
