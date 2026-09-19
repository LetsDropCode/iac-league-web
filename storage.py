"""Single storage boundary. No seed copying, including on first production boot."""
from contextlib import contextmanager
from functools import lru_cache, wraps
from pathlib import Path
import fcntl
import hashlib
import io
import json
import os
import tempfile
import time
import uuid

RULE_FILES = ('points_rules.csv', 'points_rules_walk.csv', 'category_map.csv')
REPO = Path(__file__).resolve().parent


class StorageError(ValueError):
    pass


class ConflictError(StorageError):
    pass


def checksum(data):
    return hashlib.sha256(data).hexdigest()


def fsync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def durable_mkdir(path):
    path = Path(path)
    if not path.exists():
        durable_mkdir(path.parent)
        try:
            path.mkdir()
        except FileExistsError:
            pass
        fsync_dir(path.parent)


def atomic_write(path, data, mtime_ns=None):
    """Caller owns storage lock. Temp and target are on the same filesystem."""
    path = Path(path)
    durable_mkdir(path.parent)
    fd, name = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            if mtime_ns is not None:
                os.utime(name, ns=(mtime_ns, mtime_ns))
            os.fsync(stream.fileno())
        os.replace(name, path)
        fsync_dir(path.parent)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def validate_payload(name, data):
    import pandas as pd
    if name.startswith('results/'):
        from update_engine import read_result_file
        source = io.BytesIO(data)
        source.filename = name
        frame = read_result_file(source)
        if frame.empty or not any(c in frame.columns for c in ('Time', 'Finish')):
            raise StorageError('Result must contain rows and a Time/Finish column.')
        if frame['Name'].isna().any() or frame['Name'].astype(str).str.strip().eq('').any():
            raise StorageError('Result contains blank athlete names.')
    elif name in RULE_FILES:
        frame = pd.read_csv(io.BytesIO(data))
        required = ({'FinishtimeCategory', 'PointsCategory'} if name == 'category_map.csv'
                    else {'Distance', 'Gender', 'Category', 'TimeFrom', 'TimeTo', 'Points'})
        if frame.empty or not required.issubset(frame.columns):
            raise StorageError(f'Invalid rules/mapping schema: {name}')
    else:
        raise StorageError(f'Not a publishable file: {name}')


class Storage:
    def __init__(self, root):
        self.root = Path(root)
        if not self.root.is_absolute() or self.root.resolve() != self.root:
            raise StorageError('LEAGUE_DATA_DIR must be an absolute, canonical path without symlinks.')
        self.results = self.root / 'results'
        self.production = False

    @classmethod
    def from_env(cls):
        production = bool(os.getenv('RENDER')) or os.getenv('LEAGUE_ENV', '').lower() == 'production'
        configured = os.getenv('LEAGUE_DATA_DIR')
        if production and not configured:
            raise StorageError('Production requires LEAGUE_DATA_DIR; ephemeral fallback is forbidden.')
        store = cls(configured or REPO)
        store.production = production
        if production:
            store.verify_volume()
            for name in RULE_FILES:
                validate_payload(name, store.path(name).read_bytes())
        else:
            store.results.mkdir(parents=True, exist_ok=True)
        # A write probe is additional to (never a substitute for) the mount check.
        with store.lock():
            fd, probe = tempfile.mkstemp(prefix='.probe-', dir=store.root)
            os.close(fd)
            os.unlink(probe)
        return store

    def verify_volume(self):
        mount = Path(os.getenv('LEAGUE_DISK_MOUNT', '/invalid-unconfigured-mount'))
        if not mount.is_absolute() or mount.resolve() != mount or mount == Path('/'):
            raise StorageError('LEAGUE_DISK_MOUNT must name a dedicated canonical mount.')
        if not self.root.is_relative_to(mount) or self.root == mount:
            raise StorageError('LEAGUE_DATA_DIR must be a subdirectory of LEAGUE_DISK_MOUNT.')
        # Linux mount table proves this is an actual disk mount, not a writable folder.
        try:
            entries = Path('/proc/self/mountinfo').read_text().splitlines()
            matches = [line.split() for line in entries if line.split()[4] == str(mount)]
            valid = any(row[row.index('-') + 1] in {'ext4', 'xfs', 'btrfs'}
                        and 'rw' in row[5].split(',') for row in matches)
        except (OSError, ValueError):
            valid = False
        if not valid or not os.path.ismount(mount):
            raise StorageError('Durable disk mount missing/unsupported. Refusing production startup.')
        expected = os.getenv('LEAGUE_VOLUME_ID')
        marker = self.path('.storage.json')
        if not expected or not marker.exists() or json.loads(marker.read_text()).get('volume_id') != expected:
            raise StorageError('Storage identity missing/mismatched; migrate and initialize explicitly.')
        if not self.results.is_dir():
            raise StorageError('Migrated results directory is missing.')

    def path(self, relative):
        relative = Path(relative)
        if relative.is_absolute() or '..' in relative.parts or not relative.parts:
            raise StorageError('Unsafe storage path.')
        path = self.root / relative
        if path.resolve() != path:
            raise StorageError('Symlinks are forbidden in storage.')
        return path

    @contextmanager
    def lock(self, shared=False):
        if self.production:
            self.verify_volume()
        durable_mkdir(self.root)
        with self.path('.storage.lock').open('a+b') as handle:
            fcntl.flock(handle, fcntl.LOCK_SH if shared else fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def inventory(self):
        """Managed data only; exclude lock/temp/derived exports, reject links."""
        candidates = [self.path(name) for name in (*RULE_FILES, '.storage.json')]
        for directory in ('results', 'versions', 'publications', 'migrations'):
            parent = self.path(directory)
            if parent.exists():
                candidates.extend(parent.rglob('*'))
        result = {}
        for path in sorted(candidates):
            relative = str(path.relative_to(self.root))
            self.path(relative)
            if path.is_file() and not path.name.startswith('.pending-'):
                data = path.read_bytes()
                result[relative] = {'sha256': checksum(data), 'size': len(data),
                                    'mtime_ns': path.stat().st_mtime_ns}
        return result

    def publish(self, relative, data, expected=None):
        """New or identical imports only; replacement requires compare-and-swap hash."""
        path = self.path(relative)
        if relative.startswith('results/') and (len(Path(relative).parts) != 2 or path.suffix.lower() not in ('.csv', '.xlsx')):
            raise StorageError('Invalid result filename.')
        validate_payload(relative, data)  # before any publication side effects
        with self.lock():
            if self.path('.imports-paused').exists():
                raise StorageError('Imports are paused for storage maintenance.')
            old = path.read_bytes() if path.exists() else None
            if old == data:
                return False
            old_hash = checksum(old) if old is not None else None
            if old_hash != expected:
                raise ConflictError(f'{relative} already exists with different content. '
                                    'No changes made. An operator must review and supply its current SHA-256 to replace it.')
            event_id = f'{time.time_ns()}-{uuid.uuid4().hex}'
            # Immutable old AND proposed bytes plus intent survive interruption at any step.
            for payload in (old, data):
                if payload is not None:
                    version = self.path(f'versions/{checksum(payload)}')
                    if version.exists() and version.read_bytes() != payload:
                        raise StorageError('Version archive checksum mismatch.')
                    if not version.exists():
                        atomic_write(version, payload)
            event = {'id': event_id, 'path': relative, 'before': old_hash,
                     'after': checksum(data), 'state': 'prepared', 'time_ns': time.time_ns()}
            record = self.path(f'publications/{event_id}.json')
            atomic_write(record, json.dumps(event, sort_keys=True).encode())
            atomic_write(path, data)
            # Prepared records are intentionally sufficient for recovery if this write fails.
            event['state'] = 'committed'
            atomic_write(record, json.dumps(event, sort_keys=True).encode())
            return True


@lru_cache(maxsize=1)
def get_storage():
    return Storage.from_env()


def storage_read(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with get_storage().lock(shared=True):
            return function(*args, **kwargs)
    return wrapped
