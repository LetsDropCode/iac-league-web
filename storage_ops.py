"""Operator tooling; never invoked implicitly by application startup."""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import io
import json
import logging
import os
from pathlib import Path
import re
import sys
import uuid
import zipfile

from storage import Storage, StorageError, ConflictError, RULE_FILES, atomic_write, checksum, validate_payload


def encoded(value):
    return json.dumps(value, sort_keys=True, indent=2).encode()


def snapshot(store):
    with store.lock(shared=True):
        inventory = store.inventory()
        for name in RULE_FILES:
            if name not in inventory:
                raise StorageError(f'Missing required file: {name}')
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, info in inventory.items():
                data = store.path(name).read_bytes()
                if checksum(data) != info['sha256']:
                    raise StorageError(f'Source changed during backup: {name}')
                archive.writestr('data/' + name, data)
            if store.inventory() != inventory:
                raise StorageError('Source inventory changed during backup; freeze legacy writers.')
            archive.writestr('manifest.json', encoded({'format': 1, 'files': inventory}))
        return output.getvalue()


def unpack(data):
    """Verify every member before writing anything; no extractall or trusted archive paths."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise StorageError('Duplicate backup members.')
        manifest = json.loads(archive.read('manifest.json'))
        if manifest.get('format') != 1:
            raise StorageError('Unsupported backup format.')
        files = manifest['files']
        if set(names) != {'manifest.json', *('data/' + n for n in files)}:
            raise StorageError('Backup member inventory mismatch.')
        payloads = {}
        for name, info in files.items():
            path = Path(name)
            if (path.is_absolute() or '..' in path.parts or str(path) != name
                    or not (name in (*RULE_FILES, '.storage.json') or
                            len(path.parts) >= 2 and path.parts[0] in
                            ('results', 'versions', 'publications', 'migrations'))):
                raise StorageError('Unsafe backup path.')
            blob = archive.read('data/' + name)
            if len(blob) != info['size'] or checksum(blob) != info['sha256']:
                raise StorageError(f'Backup checksum mismatch: {name}')
            payloads[name] = blob
        if not set(RULE_FILES).issubset(files):
            raise StorageError('Incomplete backup: rules/mappings missing.')
        return files, payloads


def restore(data, destination):
    files, payloads = unpack(data)
    with destination.lock():
        # An interrupted restore can be resumed only if all existing bytes agree.
        existing = destination.inventory()
        if set(existing) - set(files):
            raise ConflictError('Destination has files absent from backup; use a fresh directory.')
        for name, info in existing.items():
            if info['sha256'] != files[name]['sha256']:
                raise ConflictError(f'Restore conflict: {name}')
        for name, blob in payloads.items():
            if name not in existing:
                atomic_write(destination.path(name), blob, files[name]['mtime_ns'])
        destination.results.mkdir(exist_ok=True)
        restored = destination.inventory()
        if {n: x['sha256'] for n, x in restored.items()} != {n: x['sha256'] for n, x in files.items()}:
            raise StorageError('Restore verification failed.')
    return restored


def migration_plan(source, destination):
    if (source.root.is_relative_to(destination.root) or destination.root.is_relative_to(source.root)):
        raise StorageError('Source and destination must be separate, non-nested directories.')
    before, after = source.inventory(), destination.inventory()
    for name in RULE_FILES:
        if name not in before:
            raise StorageError(f'Migration source lacks {name}.')
    conflicts = [name for name in before if name in after and before[name]['sha256'] != after[name]['sha256']]
    return {'format': 1, 'source': str(source.root), 'destination': str(destination.root),
            'source_files': before, 'destination_files': after, 'conflicts': conflicts,
            'copy': sorted(set(before) - set(after))}


def migrate(source, destination, plan, backup_data):
    backup_files, _ = unpack(backup_data)
    with ExitStack() as stack:
        for store in sorted((source, destination), key=lambda s: str(s.root)):
            stack.enter_context(store.lock())
        current = migration_plan(source, destination)
        if current != plan:
            raise ConflictError('Inventory changed since review. Generate and review a new plan.')
        if current['conflicts']:
            raise ConflictError('Conflicting destination files: ' + ', '.join(current['conflicts']))
        for name, info in current['source_files'].items():
            if backup_files.get(name, {}).get('sha256') != info['sha256']:
                raise StorageError(f'Independent backup does not cover current source: {name}')
        # Read and check all inputs before copying; preserve bytes and mtimes.
        payloads = {}
        for name, info in current['source_files'].items():
            blob = source.path(name).read_bytes()
            if checksum(blob) != info['sha256']:
                raise StorageError(f'Source changed: {name}')
            payloads[name] = blob
        for name in current['copy']:
            atomic_write(destination.path(name), payloads[name], current['source_files'][name]['mtime_ns'])
        destination.results.mkdir(exist_ok=True)
        after = destination.inventory()
        for name, info in current['source_files'].items():
            if after.get(name, {}).get('sha256') != info['sha256']:
                raise StorageError('Post-migration checksum verification failed.')
        report = {'plan': current, 'verified_destination': after}
        atomic_write(destination.path(f'migrations/{checksum(encoded(current))}.json'), encoded(report))
        return report


class S3Backups:
    """Independent object storage only. No local-directory backup destination."""
    def __init__(self, client=None):
        self.bucket = os.environ.get('LEAGUE_BACKUP_BUCKET')
        self.prefix = os.environ.get('LEAGUE_BACKUP_PREFIX', 'iac-league/').rstrip('/') + '/'
        if not self.bucket or self.prefix == '/' or '..' in self.prefix.split('/'):
            raise StorageError('Configure LEAGUE_BACKUP_BUCKET and a dedicated nonempty prefix.')
        if client is None:
            import boto3
            from botocore.config import Config
            client = boto3.client('s3', config=Config(connect_timeout=5, read_timeout=30,
                                                   retries={'max_attempts': 2}))
            # Standard AWS credential chain; never source credentials.
        self.client = client

    def download(self, key):
        if not key.startswith(self.prefix) or not re.fullmatch(r'\d{8}T\d{12}Z-[a-f0-9]{32}\.zip', key[len(self.prefix):]):
            raise StorageError('Not a managed backup key.')
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        body = response['Body'].read()
        if checksum(body) != response.get('Metadata', {}).get('sha256'):
            raise StorageError('Remote archive checksum mismatch.')
        unpack(body)
        return body

    def backup(self, store, retain=30):
        if retain < 2:
            raise StorageError('Retain at least two backups.')
        body = snapshot(store)
        key = self.prefix + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-' + uuid.uuid4().hex + '.zip'
        self.client.put_object(Bucket=self.bucket, Key=key, Body=body,
                               Metadata={'sha256': checksum(body)}, ServerSideEncryption='AES256')
        if self.download(key) != body:
            raise StorageError('Independent backup read-back failed; retention not run.')
        # Prune only our generated objects, only after successful full read-back.
        keys = []
        for page in self.client.get_paginator('list_objects_v2').paginate(Bucket=self.bucket, Prefix=self.prefix):
            keys.extend(o['Key'] for o in page.get('Contents', [])
                        if re.fullmatch(r'\d{8}T\d{12}Z-[a-f0-9]{32}\.zip', o['Key'][len(self.prefix):]))
        for old in sorted(keys, reverse=True)[retain:]:
            if old != key:
                self.client.delete_object(Bucket=self.bucket, Key=old)
        return {'key': key, 'sha256': checksum(body), 'files': len(unpack(body)[0]), 'verified': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('pause-imports', 'resume-imports'):
        pause = sub.add_parser(command); pause.add_argument('--source', required=True)
    inv = sub.add_parser('inventory'); inv.add_argument('--source', required=True)
    back = sub.add_parser('backup'); back.add_argument('--source', required=True); back.add_argument('--retain', type=int, default=30)
    rest = sub.add_parser('restore'); rest.add_argument('--key', required=True); rest.add_argument('--destination', required=True)
    mig = sub.add_parser('migrate')
    for flag in ('source', 'destination', 'plan'):
        mig.add_argument('--' + flag, required=True)
    mig.add_argument('--apply', action='store_true'); mig.add_argument('--backup-key')
    init = sub.add_parser('initialize'); init.add_argument('--destination', required=True); init.add_argument('--volume-id', required=True)
    pub = sub.add_parser('publish'); pub.add_argument('--source', required=True); pub.add_argument('--file', required=True); pub.add_argument('--name', required=True); pub.add_argument('--expected-sha256')
    args = parser.parse_args()
    try:
        if args.command in ('pause-imports', 'resume-imports'):
            store = Storage(args.source)
            with store.lock():
                marker = store.path('.imports-paused')
                if args.command == 'pause-imports':
                    atomic_write(marker, b'Imports paused for maintenance.\n')
                elif marker.exists():
                    marker.unlink()
                    from storage import fsync_dir
                    fsync_dir(store.root)
            result = {'imports_paused': marker.exists()}
        elif args.command == 'inventory':
            store = Storage(args.source)
            with store.lock(shared=True):
                result = store.inventory()
        elif args.command == 'backup':
            result = S3Backups().backup(Storage(args.source), args.retain)
        elif args.command == 'restore':
            result = restore(S3Backups().download(args.key), Storage(args.destination))
        elif args.command == 'migrate':
            source, destination = Storage(args.source), Storage(args.destination)
            if args.apply:
                if not args.backup_key:
                    raise StorageError('--apply requires a verified independent --backup-key.')
                result = migrate(source, destination, json.loads(Path(args.plan).read_text()), S3Backups().download(args.backup_key))
            else:
                with source.lock(shared=True), destination.lock(shared=True):
                    result = migration_plan(source, destination)
                with Path(args.plan).open('x') as output:
                    json.dump(result, output, indent=2, sort_keys=True)
        elif args.command == 'initialize':
            store = Storage(args.destination)
            with store.lock():
                for name in RULE_FILES:
                    validate_payload(name, store.path(name).read_bytes())
                if not store.results.is_dir():
                    raise StorageError('Migrate/restore results before initialization.')
                marker = store.path('.storage.json')
                result = {'volume_id': args.volume_id}
                if marker.exists() and json.loads(marker.read_text()) != result:
                    raise ConflictError('Storage identity already initialized; refusing overwrite.')
                atomic_write(marker, encoded(result))
        else:
            result = {'published': Storage(args.source).publish(args.name, Path(args.file).read_bytes(), args.expected_sha256)}
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        # Nonzero exit + stderr is the scheduler/operator failure signal. No credentials logged.
        print(f'STORAGE OPERATION FAILED ({type(exc).__name__}): {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
