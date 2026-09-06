"""Stockage privé du service, distinct des formats des campagnes historiques."""
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import uuid

SCHEMA_VERSION = 1


class IntegrityError(ValueError):
    pass


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def identity(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value):
        raise ValueError("Identité invalide")
    return value


def integer(value):
    if type(value) is not int or not 0 <= value <= 2**63 - 1:
        raise ValueError("Entier positif ou nul requis")
    return value


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def private_path(path, directory=False):
    metadata = path.lstat()
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    if not kind(metadata.st_mode) or metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != (0o700 if directory else 0o600):
        raise IntegrityError("Emplacement privé invalide")


def initialize(root):
    root = Path(root).absolute()
    # Ansible peut préparer le répertoire privé vide sous son compte de service
    if root.exists() or root.is_symlink():
        private_path(root, directory=True)
        if any(root.iterdir()):
            raise FileExistsError(root)
    else:
        root.mkdir(mode=0o700)
    (root / "pieces").mkdir(mode=0o700)
    db = root / "metadata.sqlite3"
    fd = os.open(db, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    connection = sqlite3.connect(db)
    try:
        connection.executescript("""
        PRAGMA foreign_keys=ON;
        PRAGMA synchronous=FULL;
        BEGIN IMMEDIATE;
        CREATE TABLE dossier_revisions (
            dossier_id TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>=0),
            payload_json TEXT NOT NULL, PRIMARY KEY(dossier_id, revision)
        );
        CREATE TABLE pieces (
            piece_id TEXT PRIMARY KEY, dossier_id TEXT NOT NULL, revision INTEGER NOT NULL,
            name TEXT NOT NULL, role TEXT NOT NULL, media_type TEXT NOT NULL,
            sha256 TEXT NOT NULL, relative_path TEXT NOT NULL UNIQUE,
            size_bytes INTEGER NOT NULL CHECK(size_bytes>=0),
            FOREIGN KEY(dossier_id,revision) REFERENCES dossier_revisions(dossier_id,revision)
        );
        CREATE TABLE budgets (
            budget_id TEXT PRIMARY KEY, phase TEXT NOT NULL
                CHECK(phase IN ('preparation','correction','judgment','acquisition')),
            currency TEXT NOT NULL, cap_units INTEGER NOT NULL CHECK(cap_units>=0),
            units_per_currency INTEGER NOT NULL CHECK(units_per_currency>0),
            authority_json TEXT NOT NULL
        );
        CREATE TABLE operations (
            operation_id TEXT PRIMARY KEY, budget_id TEXT NOT NULL REFERENCES budgets(budget_id),
            dossier_id TEXT NOT NULL, revision INTEGER NOT NULL,
            intent_json TEXT NOT NULL, reserved_units INTEGER NOT NULL CHECK(reserved_units>=0),
            state TEXT NOT NULL CHECK(state IN ('RESERVED','SENDING','UNKNOWN','DONE','CANCELLED')),
            observed_units INTEGER CHECK(observed_units>=0), receipt_json TEXT,
            FOREIGN KEY(dossier_id,revision) REFERENCES dossier_revisions(dossier_id,revision)
        );
        CREATE TABLE runtime (
            singleton INTEGER PRIMARY KEY CHECK(singleton=1),
            admission INTEGER NOT NULL CHECK(admission IN (0,1)),
            reason TEXT NOT NULL,
            restore_pending INTEGER NOT NULL CHECK(restore_pending IN (0,1))
        );
        INSERT INTO runtime VALUES(1,0,'INITIALIZED',0);
        PRAGMA user_version=1;
        COMMIT;
        """)
    finally:
        connection.close()
    sync_directory(root)
    sync_directory(root.parent)


class Store:
    def __init__(self, root):
        self.root = Path(root).absolute()
        private_path(self.root, directory=True)
        private_path(self.root / "pieces", directory=True)
        path = self.root / "metadata.sqlite3"
        private_path(path)
        # Vérifier sans droit d'écriture avant toute ouverture modifiable
        probe = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        try:
            if probe.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
                raise IntegrityError("Schéma inconnu")
            if probe.execute("PRAGMA quick_check").fetchall() != [("ok",)] or probe.execute("PRAGMA foreign_key_check").fetchall():
                raise IntegrityError("Base incohérente")
        finally:
            probe.close()
        self.db = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA synchronous=FULL")

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def save_dossier(self, dossier_id, revision, payload):
        if not isinstance(payload, dict):
            raise ValueError("Objet dossier requis")
        with self.transaction():
            self.db.execute("INSERT INTO dossier_revisions VALUES (?,?,?)", (identity(dossier_id), integer(revision), encode(payload)))

    def get_dossier(self, dossier_id, revision):
        row = self.db.execute("SELECT payload_json FROM dossier_revisions WHERE dossier_id=? AND revision=?", (identity(dossier_id), integer(revision))).fetchone()
        if row is None:
            raise KeyError("Dossier absent")
        return json.loads(row[0])

    def put_piece(self, dossier_id, revision, piece_id, *, name, role, media_type, content):
        identity(piece_id)
        identity(dossier_id)
        integer(revision)
        if not all(isinstance(value, str) and value and '\x00' not in value for value in (name, role, media_type)) or not isinstance(content, bytes):
            raise ValueError("Pièce invalide")
        relative = "pieces/" + uuid.uuid4().hex
        path = self.root / relative
        with self.transaction():
            self.get_dossier(dossier_id, revision)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            sync_directory(path.parent)
            # Un arrêt avant le commit laisse une pièce orpheline détectable, jamais une preuve
            self.db.execute("INSERT INTO pieces VALUES (?,?,?,?,?,?,?,?,?)", (piece_id, dossier_id, revision, name, role, media_type, sha256(content).hexdigest(), relative, len(content)))
        return self.get_piece(piece_id)

    def get_piece(self, piece_id):
        row = self.db.execute("SELECT * FROM pieces WHERE piece_id=?", (identity(piece_id),)).fetchone()
        if row is None:
            raise KeyError("Pièce absente")
        return dict(row)

    def read_piece(self, piece_id):
        row = self.get_piece(piece_id)
        if not re.fullmatch(r"pieces/[a-f0-9]{32}", row["relative_path"]):
            raise IntegrityError("Référence dangereuse")
        private_path(self.root / "pieces", directory=True)
        path = self.root / row["relative_path"]
        try:
            private_path(path)
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise IntegrityError("Pièce non régulière")
                content = stream.read()
        except OSError as exc:
            raise IntegrityError("Pièce inaccessible") from exc
        if len(content) != row["size_bytes"] or sha256(content).hexdigest() != row["sha256"]:
            raise IntegrityError("Pièce altérée ou incomplète")
        return content

    def verify(self):
        if self.db.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or self.db.execute("PRAGMA foreign_key_check").fetchall():
            raise IntegrityError("Références incohérentes")
        rows = self.db.execute("SELECT piece_id,relative_path FROM pieces").fetchall()
        for row in rows:
            self.read_piece(row["piece_id"])
        expected = {row["relative_path"] for row in rows}
        actual = {"pieces/" + path.name for path in (self.root / "pieces").iterdir()}
        if actual != expected:
            raise IntegrityError("Pièces orphelines ou manquantes")
        return {"schema_version": SCHEMA_VERSION, "pieces": len(rows)}

    def add_budget(self, budget_id, *, phase, currency, cap_units, units_per_currency, authority):
        identity(budget_id)
        if not isinstance(authority, dict) or not authority or not re.fullmatch(r"[A-Z]{3}", currency) or integer(units_per_currency) == 0:
            raise ValueError("Autorité et unité monétaire explicites requises")
        with self.transaction():
            self.db.execute("INSERT INTO budgets VALUES(?,?,?,?,?,?)", (budget_id, phase, currency, integer(cap_units), units_per_currency, encode(authority)))

    def resume(self, authority):
        if not isinstance(authority, dict) or not authority:
            raise ValueError("Autorité de reprise requise")
        with self.transaction():
            if self.db.execute("SELECT restore_pending FROM runtime").fetchone()[0]:
                raise IntegrityError("Historique postérieur à la sauvegarde à rapprocher")
            if self.db.execute("SELECT 1 FROM operations WHERE state IN ('SENDING','UNKNOWN') OR (state='DONE' AND observed_units IS NULL) LIMIT 1").fetchone():
                raise IntegrityError("Effets ou coûts à rapprocher avant reprise")
            for budget in self.db.execute("SELECT budget_id,cap_units FROM budgets"):
                used = self.db.execute("SELECT COALESCE(SUM(CASE WHEN state='CANCELLED' THEN 0 WHEN observed_units IS NULL THEN reserved_units ELSE MAX(reserved_units,observed_units) END),0) FROM operations WHERE budget_id=?", (budget[0],)).fetchone()[0]
                if used > budget[1]:
                    raise IntegrityError("Enveloppe dépassée")
            self.db.execute("UPDATE runtime SET admission=1,reason=?", (encode(authority),))

    def reserve(self, operation_id, *, budget_id, dossier_id, revision, reserved_units, intent):
        if not isinstance(intent, dict) or not intent:
            raise ValueError("Intention requise")
        with self.transaction():
            if not self.db.execute("SELECT admission FROM runtime").fetchone()[0]:
                raise IntegrityError("Admission suspendue")
            budget = self.db.execute("SELECT cap_units FROM budgets WHERE budget_id=?", (identity(budget_id),)).fetchone()
            if budget is None:
                raise KeyError("Budget absent")
            used = self.db.execute("SELECT COALESCE(SUM(CASE WHEN state='CANCELLED' THEN 0 WHEN observed_units IS NULL THEN reserved_units ELSE MAX(reserved_units,observed_units) END),0) FROM operations WHERE budget_id=?", (budget_id,)).fetchone()[0]
            if used + integer(reserved_units) > budget[0]:
                raise IntegrityError("Enveloppe épuisée")
            self.db.execute("INSERT INTO operations VALUES(?,?,?,?,?,?,'RESERVED',NULL,NULL)", (identity(operation_id), budget_id, identity(dossier_id), integer(revision), encode(intent), reserved_units))

    def mark_sending(self, operation_id):
        with self.transaction():
            if not self.db.execute("SELECT admission FROM runtime").fetchone()[0]:
                raise IntegrityError("Admission suspendue")
            changed = self.db.execute("UPDATE operations SET state='SENDING' WHERE operation_id=? AND state='RESERVED'", (identity(operation_id),)).rowcount
            if changed != 1:
                raise IntegrityError("Opération déjà émise ou absente")

    def finish(self, operation_id, *, receipt, observed_units=None):
        if not isinstance(receipt, dict) or not receipt:
            raise ValueError("Reçu requis")
        if observed_units is not None:
            integer(observed_units)
        with self.transaction():
            changed = self.db.execute("UPDATE operations SET state='DONE',receipt_json=?,observed_units=? WHERE operation_id=? AND state='SENDING'", (encode(receipt), observed_units, identity(operation_id))).rowcount
            if changed != 1:
                raise IntegrityError("État incompatible avec un reçu final")
            if observed_units is None:
                self.db.execute("UPDATE runtime SET admission=0,reason='UNKNOWN_COST'")
            elif self.db.execute("SELECT 1 FROM operations WHERE operation_id=? AND observed_units>reserved_units", (operation_id,)).fetchone():
                self.db.execute("UPDATE runtime SET admission=0,reason='RESERVATION_EXCEEDED'")

    def stop(self, reason, *, after_process_exit=False):
        if not isinstance(reason, str) or not reason:
            raise ValueError("Motif requis")
        with self.transaction():
            self.db.execute("UPDATE runtime SET admission=0,reason=?", (reason,))
            if after_process_exit:
                self.db.execute("UPDATE operations SET state='UNKNOWN' WHERE state='SENDING'")
        return self.status()

    def status(self):
        return {"admission": bool(self.db.execute("SELECT admission FROM runtime").fetchone()[0]), "restore_pending": bool(self.db.execute("SELECT restore_pending FROM runtime").fetchone()[0]), "operations": {row[0]: row[1] for row in self.db.execute("SELECT state,COUNT(*) FROM operations GROUP BY state")}}
