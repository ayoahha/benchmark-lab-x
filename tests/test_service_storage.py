"""Preuves hors ligne de persistance et d'absence de double émission."""
from contextlib import closing
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from benchmark_lab_x.storage import BudgetError, ConflictError, IntegrityError, SchemaError, Store, initialize
from benchmark_lab_x.runtime import backup, restore, verify_backup, status, stop, verify
from tests.test_storage import PAYLOAD, operation, receipt, cost


class ServiceStorageTests(unittest.TestCase):
    def test_quiescence_refuses_active_qualification_and_preserves_data(self):
        from benchmark_lab_x import preparation, qualification as q
        from tests.test_s3_regressions import ACTOR, check, fixture, specification

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / 'private'
            _, view, reference = fixture(root)
            q.initialize(root)

            def cli(expected_code, expected_result):
                result = subprocess.run(
                    [sys.executable, '-B', '-m', 'benchmark_lab_x.runtime',
                     'quiescence', '--data', str(root)],
                    capture_output=True, text=True, timeout=10)
                self.assertEqual(expected_code, result.returncode, result.stderr)
                self.assertEqual(expected_result, json.loads(result.stdout))

            with closing(Store(root)) as store:
                preparation.close_admission(store)
                candidate = q.draft(store, 'fixture', view['revision'], specification(reference))
                idle = status(root, store)
                self.assertEqual({'admission', 'restore_pending', 'operations'}, set(idle))
                cli(0, idle)

                def during(contract, resources):
                    before = list(store._connection.iterdump())
                    pieces = {path: path.read_bytes() for path in (root / 'pieces').iterdir()}
                    cli(78, {'state': 'HOLD', 'reason': 'OPERATION_NOT_VERIFIED'})
                    self.assertEqual(before, list(store._connection.iterdump()))
                    self.assertEqual(pieces, {path: path.read_bytes() for path in (root / 'pieces').iterdir()})
                    return check(contract, resources)

                result = q.qualify(store, candidate['contract_sha256'], reviewer=ACTOR, check=during)
                self.assertEqual('QUALIFIED', result['status'])
                before = sha256((root / 'metadata.sqlite3').read_bytes()).hexdigest()
                cli(0, idle)
                self.assertEqual(before, sha256((root / 'metadata.sqlite3').read_bytes()).hexdigest())
                self.assertTrue(verify(store)['integrity_ok'])

    def test_reopen_corruption_and_unknown_schema_preserve_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / 'private'
            root.mkdir(mode=0o700)
            initialize(root)
            initialize(root)
            store = Store(root)
            store.save_dossier('d', 1, PAYLOAD)
            row = store.put_piece('d', 1, 'piece', name='exemple.txt', role='candidate', media_type='text/plain', content=b'fictif')
            store.close()
            code = "from benchmark_lab_x.storage import Store; import sys; s=Store(sys.argv[1]); assert s.get_dossier('d',1)['request']=='Suivi fictif Orme'; assert s.read_piece('piece')==b'fictif'; assert s.verify_storage()['integrity_ok']; s.close()"
            subprocess.run([sys.executable, '-c', code, str(root)], check=True)
            (root / row['relative_path']).write_bytes(b'altere')
            store = Store(root)
            with self.assertRaises(IntegrityError):
                store.read_piece('piece')
            with self.assertRaises(IntegrityError):
                verify(store)
            store.close()
            connection = sqlite3.connect(root / 'metadata.sqlite3')
            connection.execute('CREATE TABLE runtime (admission INTEGER)')
            connection.commit()
            connection.close()
            before = sha256((root / 'metadata.sqlite3').read_bytes()).hexdigest()
            with self.assertRaises(SchemaError):
                Store(root)
            for action in ('verify', 'status', 'initialize'):
                rejected = subprocess.run([sys.executable, '-m', 'benchmark_lab_x.runtime', action, '--data', str(root)], capture_output=True, text=True)
                self.assertEqual(78, rejected.returncode, rejected.stderr)
            self.assertEqual(before, sha256((root / 'metadata.sqlite3').read_bytes()).hexdigest())

    def test_concurrent_budget_and_interruption_never_replay_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / 'private'
            initialize(root)
            store = Store(root)
            store.save_dossier('d', 1, PAYLOAD)
            store.create_budget('test', '0.10', 'TEST')
            store.close()

            def reserve(index):
                other = Store(root)
                try:
                    other.reserve_intent(operation(str(index)), 'test', '0.06')
                    return str(index)
                except BudgetError:
                    return None
                finally:
                    other.close()

            with ThreadPoolExecutor(max_workers=2) as workers:
                results = list(workers.map(reserve, [1, 2]))
            self.assertEqual(1, sum(value is not None for value in results))
            attempt = next(value for value in results if value is not None)
            emitted = []
            store = Store(root)
            store.mark_emission_possible(attempt)
            emitted.append(attempt)
            store.close()
            store = Store(root)
            stop(root, store, 'Arrêt du processus démontré', after_process_exit=True)
            with self.assertRaises(BudgetError):
                store.reserve_intent(operation('new'), 'test', '0')
            with self.assertRaises(ConflictError):
                store.mark_emission_possible(attempt)
                emitted.append(attempt)
            self.assertEqual([attempt], emitted)
            self.assertEqual({'AMBIGUOUS': 1}, status(root, store)['operations'])
            store.close()

    def test_backup_restore_preserves_source_and_blocks_old_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / 'private'
            initialize(root)
            store = Store(root)
            store.save_dossier('d', 1, PAYLOAD)
            store.put_piece('d', 1, 'piece', name='a', role='candidate', media_type='text/plain', content=b'fictif')
            store.close()
            with closing(Store(root)) as store:
                store.create_budget('b', '100', 'TEST')
                for name in ('ambiguous', 'unknown', 'intent'):
                    store.reserve_intent(operation(name), 'b', '7')
                store.mark_emission_possible('ambiguous')
                with self.assertRaises(IntegrityError):
                    backup(root, Path(directory).resolve() / 'refused')
                self.assertFalse((Path(directory).resolve() / 'refused').exists())
                stop(root, store, 'Processus arrêté', after_process_exit=True)
                store.mark_emission_possible('unknown')
                store.record_receipt('unknown', receipt(), cost(None, 'UNKNOWN'))
                expected = store.inspect_operations()
                budget = store.inspect_budget('b')
            target = Path(directory).resolve() / 'backup'
            copytree = shutil.copytree
            def copy_under_lock(*args, **kwargs):
                with closing(sqlite3.connect(root / 'metadata.sqlite3', timeout=0)) as writer:
                    with self.assertRaisesRegex(sqlite3.OperationalError, 'locked'):
                        writer.execute('BEGIN IMMEDIATE')
                return copytree(*args, **kwargs)
            with patch('benchmark_lab_x.runtime.shutil.copytree', side_effect=copy_under_lock):
                self.assertEqual('BACKUP_VERIFIED', backup(root, target)['state'])
            before = sha256((root / 'metadata.sqlite3').read_bytes()).hexdigest()
            restored = Path(directory).resolve() / 'restored'
            self.assertEqual('RESTORED_ADMISSION_BLOCKED', restore(target, restored)['state'])
            with self.assertRaises(FileExistsError):
                restore(target, root)
            self.assertEqual(before, sha256((root / 'metadata.sqlite3').read_bytes()).hexdigest())
            store = Store(restored)
            self.assertEqual(b'fictif', store.read_piece('piece'))
            self.assertTrue(stop(restored, store, 'Autre maintenance')['restore_pending'])
            store.close()
            with closing(Store(restored)) as store:
                self.assertEqual(expected, store.inspect_operations())
                self.assertEqual(budget, store.inspect_budget('b'))
            second = Path(directory).resolve() / 'backup-restored'
            backup(restored, second)
            twice = Path(directory).resolve() / 'twice'
            restore(second, twice)
            with closing(Store(twice)) as store:
                self.assertTrue(status(twice, store)['restore_pending'])
                self.assertEqual(expected, store.inspect_operations())
            next((target / 'private/pieces').iterdir()).write_bytes(b'altere')
            with self.assertRaises(IntegrityError):
                verify_backup(target)

    def test_dangerous_reference_and_immutable_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / 'private'
            initialize(root)
            store = Store(root)
            store.save_dossier('d', 1, PAYLOAD)
            with self.assertRaises(ConflictError):
                store.save_dossier('d', 1, {**PAYLOAD, 'request': 'replacement'})
            row = store.put_piece('d', 1, 'piece', name='a', role='candidate', media_type='text/plain', content=b'fictif')
            piece = root / row['relative_path']
            piece.rename(root / 'original')
            piece.symlink_to(root / 'original')
            with self.assertRaises(IntegrityError):
                store.read_piece('piece')
            with sqlite3.connect(root / "metadata.sqlite3") as tamper:
                tamper.execute("UPDATE pieces SET relative_path='../original' WHERE piece_id='piece'")
            with self.assertRaises(IntegrityError):
                store.read_piece('piece')
            self.assertEqual(PAYLOAD, store.get_dossier('d', 1))
            store.close()


if __name__ == '__main__':
    unittest.main()
