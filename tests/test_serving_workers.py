"""Real local Gunicorn workers; not Render restart/redeploy evidence."""
import concurrent.futures
import http.client
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from ops.staging_probe import seed, RESULT, CORRECTED
from storage import checksum


class WorkersTests(unittest.TestCase):
    def test_two_serving_workers_correction_rollback_and_local_restart(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='iac-') as tmp:
            root = Path(tmp).resolve()
            with patch.dict(os.environ, {'LEAGUE_DEPLOYMENT_STAGE': 'staging'}):
                store = seed(root / 'data')
            store.publish('results/synthetic.csv', RESULT)
            sock = str(root / 'web.sock')
            env = dict(os.environ, LEAGUE_DATA_DIR=str(store.root), PYTHONDONTWRITEBYTECODE='1')
            for key in ('RENDER', 'LEAGUE_ENV', 'GUNICORN_CMD_ARGS', 'WEB_CONCURRENCY'):
                env.pop(key, None)
            class Connection(http.client.HTTPConnection):
                def connect(self):
                    self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    self.sock.settimeout(3)
                    self.sock.connect(sock)
            def request(_=None):
                connection = Connection('localhost')
                try:
                    connection.request('GET', '/', headers={'X-Forwarded-Proto': 'https'})
                    response = connection.getresponse()
                    body = response.read()
                    self.assertEqual(response.status, 200, body[:100])
                    self.assertIn(b'Synthetic Runner', body)
                    return response.getheader('X-Test-Worker-Pid'), int(response.getheader('X-Test-Points'))
                finally:
                    connection.close()
            def collect(expected):
                observed = set()
                for _ in range(10):
                    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                        replies = list(pool.map(request, range(8)))
                    for pid, points in replies:
                        self.assertEqual(points, expected)
                        observed.add(pid)
                    if len(observed) == 2:
                        return observed
                self.fail('Did not observe both serving workers')
            def launch():
                process = subprocess.Popen([sys.executable, '-m', 'gunicorn', '--workers', '2',
                                            '--bind', 'unix:' + sock, '--pythonpath', str(repo / 'tests'),
                                            'local_worker_app:application'], cwd=repo, env=env,
                                           stdout=log, stderr=log)
                for _ in range(100):
                    if process.poll() is not None:
                        self.fail('Gunicorn failed to start: ' + (root / 'workers.log').read_text()[-2500:])
                    try:
                        request()
                        return process
                    except (OSError, http.client.HTTPException):
                        time.sleep(0.05)
                process.terminate()
                process.wait(timeout=10)
                self.fail('Gunicorn start timeout')
            with (root / 'workers.log').open('wb') as log:
                process = launch()
                try:
                    pids = collect(20)
                    store.publish('results/synthetic.csv', CORRECTED, checksum(RESULT))
                    self.assertEqual(collect(10), pids)
                    store.publish('results/synthetic.csv', RESULT, checksum(CORRECTED))
                    self.assertEqual(collect(20), pids)
                finally:
                    process.terminate()
                    process.wait(timeout=10)
                process = launch()
                try:
                    self.assertTrue(collect(20).isdisjoint(pids))
                finally:
                    process.terminate()
                    process.wait(timeout=10)
