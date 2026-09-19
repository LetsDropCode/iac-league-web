"""Read-only, value-redacted runtime evidence. Run in the existing service shell."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path


def inspect():
    processes = []
    proc = Path('/proc')
    if proc.exists():
        for directory in proc.iterdir():
            if not directory.name.isdigit():
                continue
            try:
                command = (directory / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
                role = ('backup-supervisor' if 'backup_runner.py' in command else
                        'gunicorn' if 'gunicorn' in command else None)
                if role:
                    # Command text is intentionally never returned: it might contain secrets.
                    processes.append({'pid': int(directory.name), 'role': role})
            except (OSError, PermissionError):
                pass
    mounts = []
    try:
        for line in Path('/proc/self/mountinfo').read_text().splitlines():
            fields = line.split()
            if fields[4] in ('/', '/var/data') or fields[4].startswith('/opt/render/project'):
                mounts.append({'path': fields[4], 'filesystem': fields[fields.index('-') + 1],
                               'read_write': 'rw' in fields[5].split(',')})
    except OSError:
        pass
    cwd = Path.cwd()
    root = Path(os.environ.get('LEAGUE_DATA_DIR', str(cwd)))
    return {'observed_at': datetime.now(timezone.utc).isoformat(), 'cwd': str(cwd),
            'environment_names': sorted(os.environ), 'processes': processes, 'mounts': mounts,
            'data_directory_exists': root.is_dir(),
            'data_device': root.stat().st_dev if root.is_dir() else None,
            'notes': 'Read-only shell view; dashboard service/deploy/tier/start-command still require separate verification. No environment values or command arguments emitted.'}


if __name__ == '__main__':
    print(json.dumps(inspect(), indent=2))
