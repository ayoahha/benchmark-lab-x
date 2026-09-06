"""Commandes locales d'exploitation sans appel fournisseur."""
import argparse
from contextlib import closing
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sqlite3

from .storage import IntegrityError, Store, encode, initialize, private_path, sync_directory


def hashes(root):
    result = {}
    for path in sorted(root.rglob('*')):
        private_path(path, directory=path.is_dir() and not path.is_symlink())
        if path.is_file():
            result[path.relative_to(root).as_posix()] = sha256(path.read_bytes()).hexdigest()
    return result


def exclusive_json(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(encode(value) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    sync_directory(path.parent)


def backup(root, destination):
    """Le verrou SQLite bloque les écrivains de pièces pendant toute la copie."""
    destination = Path(destination).absolute()
    with closing(Store(root)) as store, store.transaction():
        status = store.status()
        if status['admission'] or status['operations'].get('SENDING', 0):
            raise IntegrityError('Maintenance et arrêt des appels requis')
        store.verify()
        destination.mkdir(mode=0o700)
        copied = destination / 'private'
        copied.mkdir(mode=0o700)
        shutil.copytree(store.root / 'pieces', copied / 'pieces')
        fd = os.open(copied / 'metadata.sqlite3', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        with closing(sqlite3.connect((store.root / 'metadata.sqlite3').as_uri() + '?mode=ro', uri=True)) as source:
            with closing(sqlite3.connect(copied / 'metadata.sqlite3')) as target:
                source.backup(target)
        with closing(Store(copied)) as check:
            proof = check.verify()
        for path in copied.rglob('*'):
            fd = os.open(path, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        sync_directory(copied)
        exclusive_json(destination / 'backup.json', {'schema_version': proof['schema_version'], 'files': hashes(copied), 'operations': status['operations']})
    return verify_backup(destination)


def verify_backup(destination):
    destination = Path(destination).absolute()
    private_path(destination, directory=True)
    private_path(destination / 'backup.json')
    manifest = json.loads((destination / 'backup.json').read_text())
    if hashes(destination / 'private') != manifest['files']:
        raise IntegrityError('Sauvegarde altérée')
    with closing(Store(destination / 'private')) as store:
        proof = store.verify()
    if manifest['schema_version'] != proof['schema_version']:
        raise IntegrityError('Schéma de sauvegarde divergent')
    return {**proof, 'state': 'BACKUP_VERIFIED'}


def restore(source, destination):
    source = Path(source).absolute()
    destination = Path(destination).absolute()
    verify_backup(source)
    manifest = json.loads((source / 'backup.json').read_text())
    # La cible neuve conserve toute base existante, y compris la source de secours
    shutil.copytree(source / 'private', destination)
    if hashes(destination) != manifest['files']:
        raise IntegrityError('Copie de restauration divergente')
    with closing(Store(destination)) as store:
        proof = store.verify()
        with store.transaction():
            store.db.execute('UPDATE runtime SET restore_pending=1,admission=0')
        store.stop('RESTORED_RECONCILIATION_REQUIRED', after_process_exit=True)
    for path in destination.rglob('*'):
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    sync_directory(destination)
    sync_directory(destination.parent)
    return {**proof, 'state': 'RESTORED_ADMISSION_BLOCKED'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('initialize', 'verify', 'status', 'maintenance', 'quiescence', 'backup', 'verify-backup', 'restore', 'web', 'executor'))
    parser.add_argument('--data', type=Path)
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--socket', type=Path)
    parser.add_argument('--public', type=Path)
    parser.add_argument('--listen', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args(argv)
    os.umask(0o077)
    try:
        if args.action in ('web', 'executor'):
            from .service import release_identity, serve_executor, serve_web
            if args.socket is None:
                raise ValueError('Socket requise')
            if args.action == 'web':
                if args.public is None or not 1024 <= args.port <= 65535:
                    raise ValueError('Projection et port requis')
                serve_web(args.listen, args.port, args.public, args.socket, release_identity())
            else:
                if args.data is None:
                    raise ValueError('Données requises')
                serve_executor(args.data, args.socket, release_identity())
            return 0
        if args.data is None:
            raise ValueError('Données requises')
        if args.action == 'initialize':
            initialize(args.data)
            result = {'state': 'INITIALIZED_ADMISSION_BLOCKED'}
        elif args.action == 'verify-backup':
            result = verify_backup(args.data)
        elif args.action in ('backup', 'restore'):
            if args.destination is None:
                raise ValueError('Destination requise')
            result = (backup if args.action == 'backup' else restore)(args.data, args.destination)
        else:
            with closing(Store(args.data)) as store:
                if args.action == 'verify':
                    result = store.verify()
                elif args.action == 'maintenance':
                    result = store.stop('MAINTENANCE')
                else:
                    result = store.status()
                    if args.action == 'quiescence' and (result['admission'] or result['operations'].get('SENDING', 0)):
                        raise IntegrityError('Travaux encore actifs ou admission ouverte')
        print(encode(result))
        return 0
    except (OSError, ValueError, sqlite3.Error):
        # Ne pas copier le contenu d'une saisie ou un chemin privé dans les journaux
        print(encode({'state': 'HOLD', 'reason': 'OPERATION_NOT_VERIFIED'}))
        return 78


if __name__ == '__main__':
    raise SystemExit(main())
