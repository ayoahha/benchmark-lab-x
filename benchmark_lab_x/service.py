"""Processus Linux du produit, sans admission ni appel implicite au démarrage."""
from contextlib import closing
import fcntl
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import signal
import socket
import socketserver
import sqlite3
import stat

from .storage import Store, encode


def release_identity():
    manifest = json.loads((Path(__file__).resolve().parents[1] / 'release.json').read_text())
    source = manifest['source_sha']
    if not re.fullmatch('[0-9a-f]{40}', source):
        raise ValueError('Identité de release invalide')
    return source


def executor_health(path):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(2)
        connection.connect(str(path))
        connection.sendall(b'health\n')
        with connection.makefile('rb') as stream:
            raw = stream.readline(4097)
        if len(raw) > 4096 or not raw.endswith(b'\n'):
            raise ValueError('Réponse de santé invalide')
        result = json.loads(raw)
        if set(result) != {'source_sha', 'storage', 'admission', 'restore_pending', 'operations'}:
            raise ValueError('Réponse de santé invalide')
        return result


def serve_executor(data, socket_path, source):
    data, socket_path = Path(data), Path(socket_path)
    with closing(Store(data)) as store:
        lock_fd = os.open(data / 'executor.lock', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            store.verify()
            store.stop('PROCESS_STARTED_ADMISSION_BLOCKED', after_process_exit=True)
            if socket_path.exists() or socket_path.is_symlink():
                metadata = socket_path.lstat()
                if not stat.S_ISSOCK(metadata.st_mode) or metadata.st_uid != os.getuid():
                    raise ValueError('Socket non détenue par le service')
                socket_path.unlink()

            class Handler(socketserver.StreamRequestHandler):
                def handle(self):
                    self.connection.settimeout(2)
                    try:
                        if self.rfile.readline(8) != b'health\n':
                            return
                        store.verify()
                        result = {'source_sha': source, 'storage': 'ok', **store.status()}
                        self.wfile.write((encode(result) + '\n').encode())
                    except (OSError, ValueError, sqlite3.Error):
                        return

            with socketserver.UnixStreamServer(str(socket_path), Handler) as server:
                os.chmod(socket_path, 0o660)
                run(server)
            store.stop('PROCESS_STOPPED_ADMISSION_BLOCKED', after_process_exit=True)
        finally:
            os.close(lock_fd)


def run(server):
    stopping = False

    def stop(signum, frame):
        nonlocal stopping
        stopping = True

    previous = {number: signal.signal(number, stop) for number in (signal.SIGTERM, signal.SIGINT)}
    # Une requête de santé locale est bornée à deux secondes pour permettre l'arrêt
    server.timeout = 0.25
    try:
        while not stopping:
            server.handle_request()
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


def serve_web(address, port, public, socket_path, source):
    public = Path(public)

    class Handler(BaseHTTPRequestHandler):
        server_version = 'Benchmark'
        sys_version = ''

        def setup(self):
            self.request.settimeout(2)
            super().setup()

        def log_message(self, *args):
            # Les URL peuvent contenir une saisie privée ; ne pas les journaliser
            pass

        def respond(self, code, value, media_type='application/json'):
            raw = value if isinstance(value, bytes) else encode(value).encode()
            self.send_response(code)
            self.send_header('Content-Type', media_type)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'self'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header('Referrer-Policy', 'no-referrer')
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(raw)

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            if self.path == '/healthz':
                self.respond(200, {'web': 'ok', 'source_sha': source})
                return
            if self.path == '/readyz':
                try:
                    health = executor_health(socket_path)
                    ready = health['source_sha'] == source and health['storage'] == 'ok'
                    self.respond(200 if ready else 503, {'web': 'ok', 'executor': 'ok' if ready else 'unavailable', 'storage': 'ok' if ready else 'unavailable', 'source_sha': source})
                except (OSError, ValueError):
                    self.respond(503, {'web': 'ok', 'executor': 'unavailable', 'storage': 'unknown', 'source_sha': source})
                return
            # Seuls les fichiers d'une projection approuvée sont consultables
            name = 'index.html' if self.path == '/' else self.path.removeprefix('/')
            if not re.fullmatch(r'[a-zA-Z0-9_-]+\.(html|css|png|jpg|txt|json)', name):
                self.respond(404, {'error': 'NOT_FOUND'})
                return
            try:
                publication = json.loads((public / 'active.json').read_text())['directory']
                if not isinstance(publication, str) or not re.fullmatch('[0-9a-f]{64}', publication):
                    raise ValueError('Projection invalide')
                resolved = public / publication
                if resolved.is_symlink():
                    raise ValueError('Projection liée interdite')
                manifest_bytes = (resolved / 'publication.json').read_bytes()
                if sha256(manifest_bytes).hexdigest() != publication:
                    raise ValueError('Manifeste public altéré')
                manifest = json.loads(manifest_bytes)
                expected = manifest['files'][name]
                path = resolved / name
                if path.is_symlink() or not path.is_file():
                    raise ValueError('Pièce publique invalide')
                raw = path.read_bytes()
                if sha256(raw).hexdigest() != expected:
                    raise ValueError('Projection altérée')
                media_type = {'.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.txt': 'text/plain; charset=utf-8', '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg'}[path.suffix]
                self.respond(200, raw, media_type)
            except (OSError, ValueError, KeyError):
                self.respond(503 if self.path == '/' else 404, {'error': 'NO_VERIFIED_PUBLICATION'})

    # Le proxy termine TLS ; le pare-feu réserve ce port aux deux proxys
    with HTTPServer((address, port), Handler) as server:
        run(server)
