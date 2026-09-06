"""Preuves hors ligne de persistance et d'absence de double émission."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from benchmark_lab_x.storage import IntegrityError, Store, initialize
from benchmark_lab_x.runtime import backup, restore, verify_backup


class ServiceStorageTests(unittest.TestCase):
    def test_reopen_corruption_and_unknown_schema_preserve_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'private'
            root.mkdir(mode=0o700)
            initialize(root)
            with self.assertRaises(FileExistsError):
                initialize(root)
            store = Store(root)
            store.save_dossier('dossier', 1, {'request': 'Exemple inventé'})
            row = store.put_piece('dossier', 1, 'piece', name='exemple.txt', role='candidate_input', media_type='text/plain', content=b'fictif')
            store.close()
            code = "from benchmark_lab_x.storage import Store; import sys; s=Store(sys.argv[1]); assert s.get_dossier('dossier',1)['request']=='Exemple inventé'; assert s.read_piece('piece')==b'fictif'; s.verify(); s.close()"
            subprocess.run([sys.executable, '-c', code, str(root)], check=True)
            (root / row['relative_path']).write_bytes(b'altere')
            store = Store(root)
            with self.assertRaises(IntegrityError):
                store.read_piece('piece')
            with self.assertRaises(IntegrityError):
                store.verify()
            store.close()
            connection = sqlite3.connect(root / 'metadata.sqlite3')
            connection.execute('PRAGMA user_version=999')
            connection.close()
            before = sha256((root / 'metadata.sqlite3').read_bytes()).hexdigest()
            with self.assertRaises(IntegrityError):
                Store(root)
            self.assertEqual(before, sha256((root / 'metadata.sqlite3').read_bytes()).hexdigest())

    def test_concurrent_budget_and_interruption_never_replay_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'private'
            initialize(root)
            store = Store(root)
            store.save_dossier('dossier', 1, {})
            store.add_budget('test', phase='preparation', currency='USD', cap_units=10, units_per_currency=100, authority={'test_only': True})
            store.resume({'test_only': True})
            store.close()

            def reserve(index):
                other = Store(root)
                try:
                    other.reserve(str(index), budget_id='test', dossier_id='dossier', revision=1, reserved_units=6, intent={'transport': 'fake'})
                    return str(index)
                except IntegrityError:
                    return None
                finally:
                    other.close()

            with ThreadPoolExecutor(max_workers=2) as workers:
                results = list(workers.map(reserve, [1, 2]))
            self.assertEqual(1, sum(value is not None for value in results))
            operation = next(value for value in results if value is not None)
            emitted = []
            store = Store(root)
            store.mark_sending(operation)
            emitted.append(operation)
            store.close()
            store = Store(root)
            store.stop('Arrêt du processus démontré', after_process_exit=True)
            with self.assertRaises(IntegrityError):
                store.resume({'test_only': True})
            with self.assertRaises(IntegrityError):
                store.mark_sending(operation)
                emitted.append(operation)
            self.assertEqual([operation], emitted)
            self.assertEqual({'UNKNOWN': 1}, store.status()['operations'])
            store.close()

    def test_backup_restore_preserves_source_and_blocks_old_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'private'
            initialize(root)
            store = Store(root)
            store.save_dossier('dossier', 1, {'request': 'Exemple'})
            store.put_piece('dossier', 1, 'piece', name='a', role='candidate_input', media_type='text/plain', content=b'fictif')
            store.close()
            target = Path(directory) / 'backup'
            self.assertEqual('BACKUP_VERIFIED', backup(root, target)['state'])
            before = sha256((root / 'metadata.sqlite3').read_bytes()).hexdigest()
            restored = Path(directory) / 'restored'
            self.assertEqual('RESTORED_ADMISSION_BLOCKED', restore(target, restored)['state'])
            with self.assertRaises(FileExistsError):
                restore(target, root)
            self.assertEqual(before, sha256((root / 'metadata.sqlite3').read_bytes()).hexdigest())
            store = Store(restored)
            self.assertEqual(b'fictif', store.read_piece('piece'))
            store.stop('Autre maintenance')
            with self.assertRaises(IntegrityError):
                store.resume({'test_only': True})
            store.close()
            next((target / 'private/pieces').iterdir()).write_bytes(b'altere')
            with self.assertRaises(IntegrityError):
                verify_backup(target)

    def test_dangerous_reference_and_immutable_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'private'
            initialize(root)
            store = Store(root)
            store.save_dossier('dossier', 1, {'request': 'initial'})
            with self.assertRaises(sqlite3.IntegrityError):
                store.save_dossier('dossier', 1, {'request': 'replacement'})
            row = store.put_piece('dossier', 1, 'piece', name='a', role='candidate_input', media_type='text/plain', content=b'fictif')
            piece = root / row['relative_path']
            piece.rename(root / 'original')
            piece.symlink_to(root / 'original')
            with self.assertRaises(IntegrityError):
                store.read_piece('piece')
            store.db.execute("UPDATE pieces SET relative_path='../original' WHERE piece_id='piece'")
            with self.assertRaises(IntegrityError):
                store.read_piece('piece')
            self.assertEqual({'request': 'initial'}, store.get_dossier('dossier', 1))
            store.close()


if __name__ == '__main__':
    unittest.main()
