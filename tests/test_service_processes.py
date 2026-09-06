"""Preuve avec deux vrais processus et une socket locale, sans fournisseur."""
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from benchmark_lab_x.service import executor_health
from benchmark_lab_x.storage import Store, initialize


class ServiceProcessesTests(unittest.TestCase):
    def test_health_restart_and_private_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(Path(__file__).resolve().parents[1] / 'benchmark_lab_x', root / 'benchmark_lab_x')
            (root / 'release.json').write_text(json.dumps({'source_sha': 'a' * 40}))
            data, public = root / 'private', root / 'public'
            public.mkdir()
            initialize(data)
            with closing(Store(data)) as store:
                store.save_dossier('private', 1, {'secret': 'must never be public'})
                store.add_budget('test', phase='preparation', currency='USD', cap_units=1, units_per_currency=1, authority={'test': True})
                store.resume({'test': True})
                store.reserve('attempt', budget_id='test', dossier_id='private', revision=1, reserved_units=1, intent={'test': True})
                store.mark_sending('attempt')
            sock = root / 'executor.sock'
            command = [sys.executable, '-m', 'benchmark_lab_x.runtime']
            children = []
            try:
                executor = subprocess.Popen(command + ['executor', '--data', str(data), '--socket', str(sock)], cwd=root)
                children.append(executor)
                deadline = time.monotonic() + 5
                while True:
                    try:
                        health = executor_health(sock)
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise
                        time.sleep(0.02)
                self.assertFalse(health['admission'])
                self.assertEqual({'UNKNOWN': 1}, health['operations'])
                with socket.socket() as probe:
                    probe.bind(('127.0.0.1', 0))
                    port = probe.getsockname()[1]
                web = subprocess.Popen(command + ['web', '--public', str(public), '--socket', str(sock), '--port', str(port)], cwd=root)
                children.append(web)
                base = f'http://127.0.0.1:{port}'
                deadline = time.monotonic() + 5
                while True:
                    try:
                        with urlopen(base + '/readyz', timeout=2) as response:
                            self.assertEqual('ok', json.load(response)['storage'])
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise
                        time.sleep(0.02)
                for path, code in [('/private/metadata.sqlite3', 404), ('/../private/metadata.sqlite3', 404), ('/', 503)]:
                    with self.assertRaises(HTTPError) as rejected:
                        urlopen(base + path, timeout=2)
                    self.assertEqual(code, rejected.exception.code)
                    self.assertNotIn(b'must never be public', rejected.exception.read())
                    rejected.exception.close()
                page = b'<!doctype html><title>Approved fixture</title>'
                manifest = json.dumps({'files': {'index.html': sha256(page).hexdigest()}}).encode()
                publication = sha256(manifest).hexdigest()
                projection = public / publication
                projection.mkdir()
                (projection / 'publication.json').write_bytes(manifest)
                (projection / 'index.html').write_bytes(page)
                (public / 'active.json').write_text(json.dumps({'directory': publication}))
                with urlopen(base + '/', timeout=2) as response:
                    self.assertEqual(page, response.read())
                (projection / 'index.html').write_bytes(b'tampered')
                with self.assertRaises(HTTPError) as corrupt:
                    urlopen(base + '/', timeout=2)
                self.assertEqual(503, corrupt.exception.code)
                corrupt.exception.close()
                executor.terminate()
                self.assertEqual(0, executor.wait(timeout=5))
                with self.assertRaises(HTTPError) as unavailable:
                    urlopen(base + '/readyz', timeout=2)
                self.assertEqual(503, unavailable.exception.code)
                unavailable.exception.close()
                with urlopen(base + '/healthz', timeout=2) as response:
                    self.assertEqual('ok', json.load(response)['web'])
                restarted = subprocess.Popen(command + ['executor', '--data', str(data), '--socket', str(sock)], cwd=root)
                children.append(restarted)
                deadline = time.monotonic() + 5
                while True:
                    try:
                        health = executor_health(sock)
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise
                        time.sleep(0.02)
                self.assertEqual({'UNKNOWN': 1}, health['operations'])
                self.assertFalse(health['admission'])
            finally:
                for child in children:
                    if child.poll() is None:
                        child.terminate()
                        child.wait(timeout=5)
