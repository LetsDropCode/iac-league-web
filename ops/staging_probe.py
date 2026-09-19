"""Synthetic staging data and credential-free persistence evidence. Never use on live data."""
import argparse
from datetime import datetime, timezone
import io
import contextlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from storage import Storage, StorageError, atomic_write, checksum, get_storage
from storage_ops import encoded
from update_engine import process_league

RESULT = b'Name;Gender;Category;Distance;Time\nSynthetic Runner;Male;Test;10;00:40:00\n'
CORRECTED = RESULT.replace(b'00:40:00', b'00:50:00')
RULES = (b'Distance,Gender,Category,TimeFrom,TimeTo,Points\n'
         b'10,Male,Senior,00:00:00,00:45:00,20\n'
         b'10,Male,Senior,00:45:01,01:00:00,10\n')
MAPPING = b'FinishtimeCategory,PointsCategory\nTest,Senior\n'


def seed(root):
    if os.getenv('LEAGUE_DEPLOYMENT_STAGE') != 'staging':
        raise StorageError('Synthetic setup requires LEAGUE_DEPLOYMENT_STAGE=staging.')
    store = Storage(root)
    if store.root.exists() and any(store.root.iterdir()):
        raise StorageError('Synthetic setup requires a completely empty directory.')
    store.results.mkdir(parents=True)
    for name, data in [('points_rules.csv', RULES), ('points_rules_walk.csv', RULES), ('category_map.csv', MAPPING)]:
        store.publish(name, data)
    # Identity is explicit and isolated from the production volume.
    identity = os.environ.get('LEAGUE_VOLUME_ID', 'synthetic-local-only')
    atomic_write(store.path('.storage.json'), encoded({'volume_id': identity}))
    return store


def evidence(store):
    from unittest.mock import patch
    with store.lock(shared=True):
        inventory = store.inventory()
        with contextlib.redirect_stdout(io.StringIO()), patch('update_engine.get_storage', return_value=store):
            tables = process_league()
        totals = [table.to_json(orient='split', date_format='iso') for table in tables[:2]]
    repo = Path(__file__).resolve().parents[1]
    commit = os.getenv('RENDER_GIT_COMMIT') or subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo).decode().strip()
    if not re.fullmatch(r'[a-fA-F0-9]{40}', commit):
        raise StorageError('Cannot record a valid deployed/source commit identifier.')
    return {'observed_at': datetime.now(timezone.utc).isoformat(),
            'commit': commit,
            'file_count': len(inventory),
            'inventory_sha256': checksum(encoded(inventory)),
            'standings_sha256': checksum(encoded(totals)),
            'rules_sha256': {name: inventory[name]['sha256'] for name in ('points_rules.csv', 'points_rules_walk.csv', 'category_map.csv')},
            'data_device': store.root.stat().st_dev}


def verify(store, expected):
    actual = evidence(store)
    for field in ('file_count', 'inventory_sha256', 'standings_sha256', 'rules_sha256'):
        if actual[field] != expected[field]:
            raise StorageError(f'Staging evidence mismatch: {field}')
    return actual


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['seed', 'record', 'verify', 'correct', 'rollback'])
    parser.add_argument('--root', required=True)
    parser.add_argument('--checkpoint')
    args = parser.parse_args()
    if os.getenv('LEAGUE_DEPLOYMENT_STAGE') != 'staging':
        raise StorageError('Staging operations only.')
    store = Storage(args.root)
    if args.action == 'seed':
        seed(args.root)
        result = {'seeded': True, 'results': 0, 'next': 'Import synthetic.csv through the staging upload UI.'}
    elif args.action == 'correct':
        store.publish('results/synthetic.csv', CORRECTED, checksum(RESULT))
        result = evidence(store)
    elif args.action == 'rollback':
        store.publish('results/synthetic.csv', RESULT, checksum(CORRECTED))
        result = evidence(store)
    elif args.action == 'record':
        result = evidence(store)
        with Path(args.checkpoint).open('x') as stream:
            json.dump(result, stream, indent=2)
    else:
        result = verify(store, json.loads(Path(args.checkpoint).read_text()))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
