import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from storage import Storage, StorageError, ConflictError, checksum, get_storage
from storage_ops import snapshot, unpack, restore, migration_plan, migrate, S3Backups

RESULT = b'Name;Gender;Category;Distance;Time\nRunner;M;Senior;10;00:40:00\n'
OTHER = RESULT.replace(b'00:40:00', b'00:41:00')
RULES = b'Distance,Gender,Category,TimeFrom,TimeTo,Points\n10,M,Senior,00:00:00,01:00:00,10\n'
MAPPING = b'FinishtimeCategory,PointsCategory\nSenior,Senior\n'


def seed(root):
    store = Storage(root)
    store.results.mkdir(parents=True)
    for name, data in [('points_rules.csv', RULES), ('points_rules_walk.csv', RULES), ('category_map.csv', MAPPING)]:
        store.path(name).write_bytes(data)
    return store


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.store = seed(self.root / 'source')
        self.dest = Storage(self.root / 'destination')

    def tearDown(self):
        get_storage.cache_clear()
        self.temp.cleanup()

    def test_absolute_path_required(self):
        with self.assertRaises(StorageError):
            Storage('results')

    def test_configured_path_independent_of_cwd(self):
        with patch.dict(os.environ, {'LEAGUE_DATA_DIR': str(self.store.root)}, clear=True):
            self.assertEqual(Storage.from_env().results, self.store.results)

    def test_local_default_is_repository_absolute(self):
        from storage import REPO
        with patch.dict(os.environ, {}, clear=True), patch.object(Storage, 'lock'):
            self.assertEqual(Storage.from_env().root, REPO)

    def test_production_missing_config(self):
        for env in ({'RENDER': 'true'}, {'LEAGUE_ENV': 'production'}):
            with patch.dict(os.environ, env, clear=True), self.assertRaises(StorageError):
                Storage.from_env()

    def test_writable_directory_is_not_durable(self):
        env = {'RENDER': 'true', 'LEAGUE_DATA_DIR': str(self.store.root),
               'LEAGUE_DISK_MOUNT': str(self.root), 'LEAGUE_VOLUME_ID': 'test'}
        self.store.path('.storage.json').write_text('{"volume_id":"test"}')
        with patch.dict(os.environ, env, clear=True), self.assertRaises(StorageError):
            Storage.from_env()

    def test_missing_identity_on_real_mount_check(self):
        env = {'LEAGUE_DISK_MOUNT': str(self.root), 'LEAGUE_VOLUME_ID': 'test'}
        row = f'1 2 8:1 / {self.root} rw - ext4 /dev/disk rw\n'
        with patch.dict(os.environ, env, clear=True), patch('storage.os.path.ismount', return_value=True), patch('storage.Path.read_text', return_value=row):
            with self.assertRaisesRegex(StorageError, 'identity'):
                self.store.verify_volume()

    def test_no_startup_seed_overwrite(self):
        path = self.store.path('points_rules.csv')
        path.write_bytes(b'operator-owned-data')
        with patch.dict(os.environ, {'LEAGUE_DATA_DIR': str(self.store.root)}, clear=True):
            Storage.from_env()
        self.assertEqual(path.read_bytes(), b'operator-owned-data')

    def test_invalid_import_not_published(self):
        for data in (b'bad', RESULT.splitlines()[0] + b'\n'):
            with self.assertRaises(ValueError):
                self.store.publish('results/race.csv', data)
        self.assertFalse(self.store.path('results/race.csv').exists())

    def test_new_identical_conflict_and_explicit_replace(self):
        self.assertTrue(self.store.publish('results/race.csv', RESULT))
        self.assertFalse(self.store.publish('results/race.csv', RESULT))
        with self.assertRaises(ConflictError):
            self.store.publish('results/race.csv', OTHER)
        self.store.publish('results/race.csv', OTHER, checksum(RESULT))
        self.assertEqual(self.store.path('versions/' + checksum(RESULT)).read_bytes(), RESULT)
        self.assertEqual(self.store.path('results/race.csv').read_bytes(), OTHER)

    def test_interrupted_replace_keeps_prior_and_prepared_record(self):
        self.store.publish('results/race.csv', RESULT)
        original = os.replace
        def fail(source, target):
            if Path(target) == self.store.path('results/race.csv'):
                raise OSError('simulated power interruption')
            return original(source, target)
        with patch('storage.os.replace', side_effect=fail), self.assertRaises(OSError):
            self.store.publish('results/race.csv', OTHER, checksum(RESULT))
        self.assertEqual(self.store.path('results/race.csv').read_bytes(), RESULT)
        self.assertEqual(self.store.path('versions/' + checksum(OTHER)).read_bytes(), OTHER)
        records = [json.loads(p.read_text()) for p in self.store.path('publications').glob('*.json')]
        self.assertIn('prepared', [r['state'] for r in records])
        self.assertFalse(list(self.store.results.glob('.pending-*')))

    def test_interrupted_metadata_after_replace_is_recoverable(self):
        self.store.publish('results/race.csv', RESULT)
        from storage import atomic_write
        def fail(path, data, *args):
            if Path(path).parent.name == 'publications' and json.loads(data)['state'] == 'committed':
                raise OSError('metadata interruption')
            return atomic_write(path, data, *args)
        with patch('storage.atomic_write', side_effect=fail), self.assertRaises(OSError):
            self.store.publish('results/race.csv', OTHER, checksum(RESULT))
        self.assertEqual(self.store.path('results/race.csv').read_bytes(), OTHER)
        self.assertEqual(self.store.path('versions/' + checksum(RESULT)).read_bytes(), RESULT)
        self.assertFalse(self.store.publish('results/race.csv', OTHER))

    def test_concurrent_processes_conflict(self):
        script = ('import sys; from storage import Storage, ConflictError; '
                  's=Storage(sys.argv[1]); s.publish("results/race.csv",sys.argv[2].encode())')
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        workers = [subprocess.Popen([sys.executable, '-c', script, str(self.store.root), data.decode()],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
                   for data in (RESULT, OTHER)]
        codes = []
        for worker in workers:
            worker.communicate(timeout=30)
            codes.append(worker.returncode)
        self.assertEqual(sorted(codes), [0, 1])
        self.assertIn(self.store.path('results/race.csv').read_bytes(), (RESULT, OTHER))

    def test_paths_and_symlinks_rejected(self):
        for name in ('../escape', '/tmp/escape'):
            with self.assertRaises(StorageError):
                self.store.path(name)
        self.store.path('results/link.csv').symlink_to(self.store.path('points_rules.csv'))
        with self.assertRaises(StorageError):
            self.store.inventory()

    def test_migration_preserves_upload_and_mtime_repeatable(self):
        self.store.publish('results/race.csv', RESULT)
        backup = snapshot(self.store)
        plan = migration_plan(self.store, self.dest)
        migrate(self.store, self.dest, plan, backup)
        self.assertEqual(self.store.path('results/race.csv').stat().st_mtime_ns,
                         self.dest.path('results/race.csv').stat().st_mtime_ns)
        fresh_plan = migration_plan(self.store, self.dest)
        self.assertEqual(fresh_plan['copy'], [])
        migrate(self.store, self.dest, fresh_plan, backup)
        self.assertEqual(self.store.path('results/race.csv').read_bytes(), RESULT)

    def test_migration_conflicts_preflight_before_any_copy(self):
        self.dest.root.mkdir()
        self.dest.path('points_rules.csv').write_bytes(b'custom rules')
        plan = migration_plan(self.store, self.dest)
        with self.assertRaises(ConflictError):
            migrate(self.store, self.dest, plan, snapshot(self.store))
        self.assertFalse(self.dest.path('category_map.csv').exists())

    def test_migration_requires_current_inventory_and_backup(self):
        backup = snapshot(self.store)
        plan = migration_plan(self.store, self.dest)
        self.store.publish('results/race.csv', RESULT)
        with self.assertRaises(ConflictError):
            migrate(self.store, self.dest, plan, backup)
        with self.assertRaises(StorageError):
            migrate(self.store, self.dest, migration_plan(self.store, self.dest), backup)

    def test_interrupted_migration_resumes_after_new_plan(self):
        from storage import atomic_write
        plan = migration_plan(self.store, self.dest)
        def fail(path, data, *args):
            if Path(path).name == 'points_rules.csv':
                raise OSError('interrupted migration')
            atomic_write(path, data, *args)
        with patch('storage_ops.atomic_write', side_effect=fail), self.assertRaises(OSError):
            migrate(self.store, self.dest, plan, snapshot(self.store))
        migrate(self.store, self.dest, migration_plan(self.store, self.dest), snapshot(self.store))
        self.assertEqual(self.dest.path('points_rules.csv').read_bytes(), RULES)

    def test_backup_restore_all_managed_data(self):
        self.store.publish('results/race.csv', RESULT)
        self.store.publish('results/race.csv', OTHER, checksum(RESULT))
        self.store.path('.storage.json').write_text('{"volume_id":"test"}')
        restore(snapshot(self.store), self.dest)
        self.assertEqual(self.store.inventory(), self.dest.inventory())
        restore(snapshot(self.store), self.dest)

    def test_restore_rejects_corruption_before_writes(self):
        original = snapshot(self.store)
        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(original)) as source, zipfile.ZipFile(output, 'w') as target:
            for name in source.namelist():
                target.writestr(name, b'corrupt' if name.endswith('points_rules.csv') else source.read(name))
        with self.assertRaises(StorageError):
            restore(output.getvalue(), self.dest)
        self.assertFalse(self.dest.root.exists())

    def test_restore_rejects_populated_conflict(self):
        self.dest.root.mkdir()
        self.dest.path('points_rules.csv').write_bytes(b'custom')
        with self.assertRaises(ConflictError):
            restore(snapshot(self.store), self.dest)

    def test_engine_and_app_paths(self):
        self.store.publish('results/race.csv', RESULT)
        with patch.dict(os.environ, {'LEAGUE_DATA_DIR': str(self.store.root)}, clear=True):
            get_storage.cache_clear()
            import update_engine
            import app
            with patch.object(app, 'storage', self.store):
                self.assertEqual(app.latest_result_file(), self.store.path('results/race.csv'))
                self.assertEqual(update_engine.race_event_count(), 1)
                run, _, _, _ = update_engine.process_league()
                self.assertEqual(int(run.iloc[0]['Total Points']), 10)
                with app.app.test_request_context('/points'):
                    self.assertIn('10', app.points())

    def test_engine_scores_abnormal_distance_with_explicit_rule_distance(self):
        result = RESULT.replace(b'Distance;Time', b'Distance;ScoringDistance;Time').replace(
            b';10;00:40:00', b';33;10;00:40:00'
        )
        self.store.publish('results/33K_test_run.csv', result)
        with patch.dict(os.environ, {'LEAGUE_DATA_DIR': str(self.store.root)}, clear=True):
            get_storage.cache_clear()
            import update_engine
            run, _, _, _ = update_engine.process_league()
        self.assertEqual(int(run.iloc[0]['Total Points']), 10)
        self.assertTrue(any('33km' in column for column in run.columns))

    def test_upload_paste_and_finishtime_routes_use_configured_store(self):
        import pandas as pd
        with patch.dict(os.environ, {'LEAGUE_DATA_DIR': str(self.store.root)}, clear=True):
            get_storage.cache_clear()
            import app
            with patch.object(app, 'storage', self.store), patch.object(app.csrf, '_csrf_disable', True):
                client = app.app.test_client()
                with client.session_transaction() as session:
                    session['admin'] = True
                response = client.post('/upload', base_url='https://localhost',
                                       data={'file': (io.BytesIO(RESULT), 'upload.csv')})
                self.assertEqual(response.status_code, 302)
                self.assertEqual(self.store.path('results/upload.csv').read_bytes(), RESULT)
                client.post('/upload', base_url='https://localhost',
                            data={'file': (io.BytesIO(OTHER), 'upload.csv')})
                self.assertEqual(self.store.path('results/upload.csv').read_bytes(), RESULT)
                response = client.post('/paste-results', base_url='https://localhost',
                                       data={'race_name': 'Test Race', 'club': 'IRENE ATHLETICS CLUB',
                                             'discipline': 'run', 'distance': '10', 'action': 'import',
                                             'scoring_distance': '10',
                                             'confirm_unverified_club': 'yes',
                                             'results': RESULT.decode().replace(';M;', ';Male;').replace(';', '\t')})
                self.assertEqual(response.status_code, 302)
                pasted = app.pasted_results_filename('Test Race', 'run', 10)
                self.assertTrue(self.store.path('results/' + pasted).exists())
                frame = pd.read_csv(io.BytesIO(RESULT), sep=';')
                with patch.object(app.FinishTimeClient, 'results_for_club', return_value=frame):
                    response = client.post('/finishtime/import', base_url='https://localhost',
                                           data={'race_url': 'https://results.finishtime.co.za/results.aspx?CId=1&RId=2',
                                                 'club': 'Test', 'discipline': 'run', 'distance': '10',
                                                 'action': 'import'})
                self.assertEqual(response.status_code, 302)
                self.assertTrue(self.store.path('results/10K_FinishTime_2_run.csv').exists())
                self.assertEqual(len(app.load_result_details()), 3)

    def test_export_uses_configured_directory(self):
        self.store.publish('results/race.csv', RESULT)
        env = dict(os.environ, LEAGUE_DATA_DIR=str(self.store.root), PYTHONDONTWRITEBYTECODE='1')
        env.pop('RENDER', None)
        env.pop('LEAGUE_ENV', None)
        result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'update_league.py')],
                                cwd=self.root, env=env, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertTrue(self.store.path('exports/league_tables.xlsx').exists())
        self.assertFalse((self.root / 'league_tables.xlsx').exists())

    def test_restore_rejects_path_traversal(self):
        data = io.BytesIO()
        files = {'../escape': {'sha256': checksum(b'x'), 'size': 1, 'mtime_ns': 1}}
        with zipfile.ZipFile(data, 'w') as archive:
            archive.writestr('manifest.json', json.dumps({'format': 1, 'files': files}))
            archive.writestr('data/../escape', b'x')
        with self.assertRaises(StorageError):
            restore(data.getvalue(), self.dest)
        self.assertFalse((self.root / 'escape').exists())

    def test_production_accepts_matching_disk_and_rejects_wrong_identity(self):
        self.store.path('.storage.json').write_text('{"volume_id":"test"}')
        env = {'LEAGUE_ENV': 'production', 'LEAGUE_DATA_DIR': str(self.store.root),
               'LEAGUE_DISK_MOUNT': str(self.root), 'LEAGUE_VOLUME_ID': 'test'}
        real_read = Path.read_text
        def read(path, *args, **kwargs):
            if str(path) == '/proc/self/mountinfo':
                return f'1 2 8:1 / {self.root} rw - ext4 /dev/disk rw\n'
            return real_read(path, *args, **kwargs)
        with patch.dict(os.environ, env, clear=True), patch('storage.os.path.ismount', return_value=True), patch.object(Path, 'read_text', read):
            self.assertTrue(Storage.from_env().production)
            with patch.dict(os.environ, {'LEAGUE_VOLUME_ID': 'wrong'}), self.assertRaises(StorageError):
                Storage.from_env()



class FakeS3:
    def __init__(self):
        self.objects = {}
        self.fail = False
        self.deleted = []
    def put_object(self, **kwargs):
        self.objects[kwargs['Key']] = kwargs
    def get_object(self, **kwargs):
        item = self.objects[kwargs['Key']]
        return {'Body': io.BytesIO(b'corrupt' if self.fail else item['Body']), 'Metadata': item['Metadata']}
    def get_paginator(self, name):
        return self
    def paginate(self, **kwargs):
        return [{'Contents': [{'Key': key} for key in self.objects]}]
    def delete_object(self, **kwargs):
        self.deleted.append(kwargs['Key'])
        del self.objects[kwargs['Key']]


class BackupTests(unittest.TestCase):
    def test_remote_readback_retention_and_failure(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'LEAGUE_BACKUP_BUCKET': 'test'}):
            store = seed(Path(tmp).resolve() / 'source')
            client = FakeS3()
            remote = S3Backups(client)
            for _ in range(3):
                receipt = remote.backup(store, retain=2)
            self.assertTrue(receipt['verified'])
            self.assertEqual(len(client.objects), 2)
            self.assertEqual(len(client.deleted), 1)
            restore(remote.download(receipt['key']), Storage(Path(tmp).resolve() / 'restore'))
            client.fail = True
            with self.assertRaises(StorageError):
                remote.backup(store, retain=2)
            self.assertEqual(len(client.deleted), 1)

    def test_failure_is_reported_and_success_status_written(self):
        from backup_runner import run_backup
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'LEAGUE_BACKUP_BUCKET': 'test'}):
            store = seed(Path(tmp).resolve() / 'source')
            client = FakeS3()
            remote = S3Backups(client)
            self.assertTrue(run_backup(store, remote, 2))
            self.assertTrue(json.loads(store.path('.backup-status.json').read_text())['verified'])
            client.fail = True
            with self.assertLogs(level='ERROR') as logs:
                self.assertFalse(run_backup(store, remote, 2))
            self.assertIn('BACKUP_FAILED', logs.output[0])
            self.assertFalse(json.loads(store.path('.backup-status.json').read_text())['verified'])


    def test_missing_independent_destination(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(StorageError):
            S3Backups(FakeS3())


if __name__ == '__main__':
    unittest.main()
