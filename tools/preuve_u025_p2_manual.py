from __future__ import annotations

import argparse
import ast
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import socket
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.validateur_pre_cadrage_v0 import (
    PaquetApprouveV0,
    valider_pre_cadrage_v0,
)


PACKAGE = ROOT / "tasks/dev/pre-cadrage-entretien-client"
PROOF = PACKAGE / "preuves-u025/p2-manual-v1"
P1 = PACKAGE / "preuves-u025/p1-local-v2"
PROCEDURE = PROOF / "procedure.md"
PROOF_ID = "U025-P2-MANUAL-V1"
VERSION = "u025-p2-manual/1"
GIT_BASE = "b47f86124c2c4dfd5faa10db71311fc13f1ef5bb"
PATH_ID = "METHODE_MANUELLE_CONTROLEE"
P1_PROOF_ID = "U025-P1-LOCAL-V2"
P1_ROOT_SHA256 = "e317647595665fd55a9a7850a90449e467956b0e2c231580a6b5225e83db55ad"
P1_CASE_INDEX_SHA256 = "e8091a2da43b3ac33f4faf93f7b21fd0042e14ca0ced9f04d1c06c3a9af9bfeb"
P1_CASE_FIXTURES_SHA256 = "72ed223d3a1cbb47eb8ca5052e30726d68a3c098928edb539a627b5fd6756453"
P1_ORACLE_SHA256 = "fb6df05fb033a3e4839fe140f4bc325e84ee68f09bff75771b2efad7e5b97124"
P1_BLIND_FIXTURES_SHA256 = "9d2c69e52d7e87ec9bfc8ac2da44913ebd1283ce7b10f31ec6c9e43464c42495"
P1_RUBRIC_SHA256 = "c0d17af852201cf3fa731260b6bbacd7aaa04a8894695e9fc345df45ce7d7c82"

PACKAGE_HASHES = {
    "manifeste-paquet.json": "8030128d159e4203483b19f0e37692a53f01baecc38fbccaa321541c23e71a10",
    "brief-proprietaire.md": "3e6e2b2edfa0e5b39f103a251707eb3f3f5f017f641aa53c55d64a6d4434eb11",
    "registre-verite.md": "6a8e957955460bfde90d88f05c2d5263f799d7ad7a9b98d78aa774ea1459d22c",
    "stimulus.md": "20f0be450640704b0c467eee57ca2ea58a4d629e63eba3efccbc6f68440e07e4",
    "temoins-qualification.md": "8a419c5950127c8187119545237f32b0ecb9b0062116afc3421e0c96a00bd011",
}

CASE_ORDER = (
    "WT-ACCEPTABLE",
    "WT-SCHEMA",
    "WT-ANCRE",
    "WT-VOCABULAIRE",
    "WT-HARNESS",
    "WT-FAIT-INVENTE",
    "WT-CONTRAINTE-OMISE",
    "WT-INCONNUE-RESOLUE",
    "WT-HYPOTHESE-INTERDITE",
    "WT-CONTRADICTION-MANQUEE",
    "WT-RISQUE-INADEQUAT",
    "WT-QUESTION-INADEQUATE",
    "WT-ACTION-INADEQUATE",
    "WT-CONFORMITE-AFFIRMEE",
    "WT-RECONSTRUCTION",
    "WT-HUMAIN-INDISPONIBLE",
)
AUTO_ONLY = frozenset(
    {"WT-SCHEMA", "WT-ANCRE", "WT-VOCABULAIRE", "WT-HARNESS"}
)
HUMAN_CASES = tuple(case_id for case_id in CASE_ORDER if case_id not in AUTO_ONLY)
PRESENTED_CASES = tuple(
    case_id for case_id in HUMAN_CASES if case_id != "WT-HUMAIN-INDISPONIBLE"
)
COMPONENTS = (
    "configuration",
    "integration",
    "execution",
    "revue_humaine",
    "verification",
    "maintenance",
    "production_rapport",
)
HUMAN_VERDICTS = frozenset(
    {"ACCEPTABLE", "NOT_ACCEPTABLE", "UNABLE_TO_JUDGE"}
)
REPORT_STATES = (
    "OFFICIALLY_ACCEPTABLE",
    "CANDIDATE_NOT_ACCEPTABLE",
    "PROVIDER_FAILURE",
    "HARNESS_ERROR",
    "UNABLE_TO_JUDGE",
)

ISSUE_DIGESTS = {
    "37": "470bde76e30f03c9740d4e5df33aa3a48495ef834228f9bcd56d2a5bf843bb04",
    "40": "37b044db2f377412c9e2f3d7ffbd236165202d7c81891f4f83798ee06395fb1f",
    "48": "63fb4a308f436a040c6ef019cf1a181a5ca03014ed9cd790c4d0cb96cff33ad0",
    "49": "2ce2a5a4c410afcc67f39fd5f175c04824258980bb6025382993237738e6ce2f",
    "53": "4befa11afe51d35d410a70e19a2ccb7f7b9f025d0166f80180c06ae16faa1030",
}
DOCUMENT_HASHES = {
    "docs/PRD.md": "0aaab457eaf3202025c33754b7fd87f41aea858c1108981fbd4c0ccee1dc0126",
    "docs/ARD.md": "f452dbfeeccbf8713be541a466066cc5ba1cd48be0da276181c09b6432f12db7",
    "docs/RULES.md": "f1edbdc9f8914aca41beef6221418704bff5db5f913688a5cc3281df71921938",
}
AUTHORITY_COMMENTS = {
    "D1": {
        "url": "https://github.com/ayoahha/benchmark-lab-x/issues/15#issuecomment-5301590597",
        "body_sha256": "ebea0d9f1587b02d44ed9317f309422dc09b20db5bd753cc3e5a4aa1f502dfa8",
    },
    "M2.1": {
        "url": "https://github.com/ayoahha/benchmark-lab-x/issues/34#issuecomment-5302877516",
        "body_sha256": "1de7e26c16b282ec2fb55a9ca5a97ab006fcf15b3e48fd527b533c6a312a0e3b",
    },
}

SECRET_PATTERNS = (
    re.compile(rb"gh[opusr]_[A-Za-z0-9]{20,}"),
    re.compile(rb"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"(?:API_KEY|TOKEN|PASSWORD)=[^\s<]{8,}"),
)
RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "proof_id",
        "level",
        "path",
        "case_id",
        "input_sha256",
        "output_sha256",
        "expected_identity",
        "observed_identity",
        "action",
        "expected",
        "observed",
        "state",
        "source_timestamp",
        "instrument_version",
        "previous_receipt_sha256",
        "unknowns",
        "candidate_calls",
        "provider_attempts",
        "supplier_spend",
        "receipt_sha256",
    }
)


class InvalidProof(RuntimeError):
    pass


class NetworkForbidden(RuntimeError):
    pass


def canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def object_digest(value: object) -> str:
    return digest(canonical(value))


def with_digest(value: dict[str, object], field: str) -> dict[str, object]:
    return {**value, field: object_digest(value)}


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_bytes())


def write_new(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def write_json_new(path: Path, value: object) -> None:
    write_new(path, canonical(value))


def runtime_identity() -> dict[str, str]:
    return {
        "implementation": platform.python_implementation(),
        "python": platform.python_version(),
        "executable": sys.executable,
        "platform": platform.platform(),
    }


def verify_static_inputs() -> None:
    observed_package = {
        name: digest((PACKAGE / name).read_bytes()) for name in PACKAGE_HASHES
    }
    if observed_package != PACKAGE_HASHES:
        raise InvalidProof(f"empreintes du paquet divergentes: {observed_package!r}")
    observed_documents = {
        path: digest((ROOT / path).read_bytes()) for path in DOCUMENT_HASHES
    }
    if observed_documents != DOCUMENT_HASHES:
        raise InvalidProof(f"documents canoniques divergents: {observed_documents!r}")
    checks = {
        P1 / "case-index.json": P1_CASE_INDEX_SHA256,
        P1 / "oracle.json": P1_ORACLE_SHA256,
        P1 / "artifacts" / P1_CASE_FIXTURES_SHA256: P1_CASE_FIXTURES_SHA256,
        P1 / "artifacts" / P1_BLIND_FIXTURES_SHA256: P1_BLIND_FIXTURES_SHA256,
    }
    for path, expected in checks.items():
        observed = digest(path.read_bytes())
        if observed != expected:
            raise InvalidProof(f"artefact P1 divergent: {path}: {observed}")
    root = read_json(P1 / "proof-root.json")
    if root.get("proof_id") != P1_PROOF_ID or root.get("root_sha256") != P1_ROOT_SHA256:
        raise InvalidProof("racine P1 v2 divergente")
    blind = read_json(P1 / "artifacts" / P1_BLIND_FIXTURES_SHA256)
    if blind.get("rubric_sha256") != P1_RUBRIC_SHA256:
        raise InvalidProof("rubrique P1 v2 divergente")


def verify_instrument_source() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_modules = {"ctypes", "cffi", "multiprocessing", "http", "urllib"}
    forbidden_calls = {"eval", "exec", "compile", "__import__"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots = {alias.name.split(".", 1)[0] for alias in node.names}
            if roots & forbidden_modules:
                raise InvalidProof(f"import instrument interdit: {sorted(roots)}")
        if isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".", 1)[0]
            if root in forbidden_modules:
                raise InvalidProof(f"import instrument interdit: {root}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in forbidden_calls:
                raise InvalidProof(f"appel dynamique interdit: {node.func.id}")


def install_network_guard(log_path: Path) -> None:
    denied = {
        "socket.__new__",
        "socket.bind",
        "socket.connect",
        "socket.getaddrinfo",
        "socket.gethostbyaddr",
        "socket.gethostbyname",
        "socket.gethostbyname_ex",
        "socket.sendmsg",
        "socket.sendto",
        "subprocess.Popen",
        "os.system",
        "os.posix_spawn",
        "os.posix_spawnp",
    }

    def hook(event: str, args: tuple[object, ...]) -> None:
        if event not in denied:
            return
        record = {
            "schema_version": "u025/network-audit/v1",
            "proof_id": PROOF_ID,
            "event": event,
            "argument_types": [type(value).__name__ for value in args],
            "state": "BLOCKED",
        }
        with log_path.open("ab") as handle:
            handle.write(canonical(record))
            handle.flush()
            os.fsync(handle.fileno())
        raise NetworkForbidden(event)

    sys.addaudithook(hook)


def network_guard_self_test() -> None:
    try:
        socket.socket()
    except NetworkForbidden:
        return
    raise InvalidProof("auto-test du contrôle réseau non bloqué")


def load_p1() -> tuple[list[dict[str, object]], dict[str, object], str]:
    fixtures = read_json(P1 / "artifacts" / P1_CASE_FIXTURES_SHA256)["cases"]
    oracle = read_json(P1 / "oracle.json")
    blind = read_json(P1 / "artifacts" / P1_BLIND_FIXTURES_SHA256)
    rubric = blind["rubric"]
    if tuple(value["case_id"] for value in fixtures) != CASE_ORDER:
        raise InvalidProof("ordre des fixtures P1 divergent")
    for fixture in fixtures:
        if digest(fixture["candidate"].encode()) != fixture["candidate_sha256"]:
            raise InvalidProof(f"fixture candidate divergente: {fixture['case_id']}")
        if digest(fixture["specification"].encode()) != fixture["specification_sha256"]:
            raise InvalidProof(f"spécification divergente: {fixture['case_id']}")
    if digest(rubric.encode()) != P1_RUBRIC_SHA256:
        raise InvalidProof("contenu de rubrique divergent")
    return fixtures, oracle, rubric


def case_index_value(fixtures: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_version": "u025/p2-manual-case-index/v1",
        "proof_id": PROOF_ID,
        "p1_proof_id": P1_PROOF_ID,
        "p1_case_index_sha256": P1_CASE_INDEX_SHA256,
        "p1_case_fixtures_sha256": P1_CASE_FIXTURES_SHA256,
        "cases": [
            {
                "ordinal": ordinal,
                "case_id": fixture["case_id"],
                "specification_sha256": fixture["specification_sha256"],
                "candidate_fixture_sha256": fixture["candidate_sha256"],
            }
            for ordinal, fixture in enumerate(fixtures, start=1)
        ],
    }


def lock_value(
    git_base: str,
    run_timestamp: str,
    case_index_sha256: str,
) -> dict[str, object]:
    runtime = runtime_identity()
    return {
        "schema_version": "u025/p2-manual-proof-lock/v1",
        "proof_id": PROOF_ID,
        "level": "P2",
        "path": PATH_ID,
        "policy": "HYBRID_PROOFS",
        "source_timestamp": run_timestamp,
        "git_base": {"expected": GIT_BASE, "observed": git_base},
        "package": {
            "name": "PRECADRAGE-ENTRETIEN-CLIENT-V0",
            "files": PACKAGE_HASHES,
            "approval": AUTHORITY_COMMENTS["D1"],
            "integrity": AUTHORITY_COMMENTS["M2.1"],
        },
        "authorities": {
            f"issue_{number}": {
                "url": f"https://github.com/ayoahha/benchmark-lab-x/issues/{number}",
                "snapshot_sha256": value,
            }
            for number, value in ISSUE_DIGESTS.items()
        },
        "documents": DOCUMENT_HASHES,
        "p1_v2": {
            "proof_id": P1_PROOF_ID,
            "root_sha256": P1_ROOT_SHA256,
            "case_index_sha256": P1_CASE_INDEX_SHA256,
            "case_fixtures_sha256": P1_CASE_FIXTURES_SHA256,
            "oracle_sha256": P1_ORACLE_SHA256,
            "blind_review_fixtures_sha256": P1_BLIND_FIXTURES_SHA256,
            "rubric_sha256": P1_RUBRIC_SHA256,
        },
        "case_index_sha256": case_index_sha256,
        "case_order": list(CASE_ORDER),
        "procedure": {
            "path": PROCEDURE.relative_to(ROOT).as_posix(),
            "sha256": digest(PROCEDURE.read_bytes()),
        },
        "instrument": {
            "path": Path(__file__).resolve().relative_to(ROOT).as_posix(),
            "sha256": digest(Path(__file__).read_bytes()),
            "version": VERSION,
            "automatic_scope": ["G-001", "G-002", "G-003", "G-004", "G-005"],
            "network_guard": "CPYTHON_AUDIT_HOOK_DENY_SOCKET_AND_SUBPROCESS",
        },
        "runtime": runtime,
        "roles": {
            "owner": "AYO",
            "procedure_and_proof_operator": "CURRENT_CODEX_SESSION",
            "automatic_instrument": "VERSIONED_LOCAL_G001_G005",
            "blind_dossier_preparer": "CURRENT_CODEX_SESSION",
            "manual_reviewer": "AYO",
            "verifier_and_report_author": "CURRENT_CODEX_SESSION",
            "manual_method_owner": "AYO",
            "final_verdict_combiner": "MECHANICAL_ONLY",
        },
        "manual_reviewer": "AYO",
        "manual_method_owner": "AYO",
        "authorizations": {
            "local_manual_p2": True,
            "network_acquisition": False,
            "installation": False,
            "candidate_call": False,
            "provider_access": False,
            "campaign": False,
            "spend": False,
            "github_during_case_window": False,
        },
        "write_scope": [
            "tools/preuve_u025_p2_manual.py",
            "tests/test_preuve_u025_p2_manual.py",
            "tasks/dev/pre-cadrage-entretien-client/preuves-u025/p2-manual-v1/",
        ],
        "stop_condition": "STOP_BEFORE_M3_12",
        "divergence_verdict": "HOLD_MANUAL_P2_EXECUTION",
    }


def validate_lock(lock: dict[str, object]) -> None:
    if lock.get("proof_id") != PROOF_ID:
        raise InvalidProof("proof_id du lock divergent")
    if lock.get("manual_reviewer") != "AYO":
        raise InvalidProof("manual_reviewer doit valoir AYO")
    if lock.get("manual_method_owner") != "AYO":
        raise InvalidProof("manual_method_owner doit valoir AYO")
    if lock.get("case_order") != list(CASE_ORDER):
        raise InvalidProof("ordre des cas divergent")
    if lock.get("policy") != "HYBRID_PROOFS":
        raise InvalidProof("politique de preuve divergente")
    if lock.get("git_base") != {"expected": GIT_BASE, "observed": GIT_BASE}:
        raise InvalidProof("base Git divergente")
    if lock["procedure"]["sha256"] != digest(PROCEDURE.read_bytes()):
        raise InvalidProof("procédure divergente")
    if lock["instrument"]["sha256"] != digest(Path(__file__).read_bytes()):
        raise InvalidProof("instrument divergent")
    if lock.get("runtime") != runtime_identity():
        raise InvalidProof("runtime divergent")
    if lock.get("p1_v2", {}).get("root_sha256") != P1_ROOT_SHA256:
        raise InvalidProof("liaison P1 divergente")
    roles = lock.get("roles", {})
    if roles.get("manual_reviewer") != "AYO" or roles.get("manual_method_owner") != "AYO":
        raise InvalidProof("attributions fonctionnelles divergentes")
    authorizations = lock.get("authorizations", {})
    forbidden = (
        "network_acquisition",
        "installation",
        "candidate_call",
        "provider_access",
        "campaign",
        "spend",
        "github_during_case_window",
    )
    if any(authorizations.get(name) is not False for name in forbidden):
        raise InvalidProof("interdiction du lock absente")


def register_entries() -> list[dict[str, object]]:
    path = PROOF / "evidence-register.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_bytes().splitlines()]


def verify_register(entries: list[dict[str, object]]) -> None:
    previous = None
    for sequence, entry in enumerate(entries, start=1):
        base = {key: value for key, value in entry.items() if key != "entry_sha256"}
        if entry.get("sequence") != sequence:
            raise InvalidProof("séquence du registre divergente")
        if entry.get("previous_entry_sha256") != previous:
            raise InvalidProof("chaîne du registre divergente")
        if object_digest(base) != entry.get("entry_sha256"):
            raise InvalidProof("empreinte d'entrée du registre divergente")
        artifact = PROOF / "artifacts" / entry["object_sha256"]
        if digest(artifact.read_bytes()) != entry["object_sha256"]:
            raise InvalidProof(f"objet de registre divergent: {entry['logical_name']}")
        previous = entry["entry_sha256"]


def append_register(logical_name: str, record_type: str, object_sha256: str) -> None:
    entries = register_entries()
    existing = next(
        (entry for entry in entries if entry["logical_name"] == logical_name), None
    )
    if existing:
        if existing["record_type"] != record_type or existing["object_sha256"] != object_sha256:
            raise InvalidProof(f"objet historique divergent: {logical_name}")
        return
    entry = {
        "schema_version": "u025/evidence-entry/v1",
        "proof_id": PROOF_ID,
        "sequence": len(entries) + 1,
        "record_type": record_type,
        "logical_name": logical_name,
        "object_sha256": object_sha256,
        "previous_entry_sha256": entries[-1]["entry_sha256"] if entries else None,
    }
    entry = with_digest(entry, "entry_sha256")
    path = PROOF / "evidence-register.jsonl"
    with path.open("ab") as handle:
        handle.write(canonical(entry))
        handle.flush()
        os.fsync(handle.fileno())


def store_object(logical_name: str, record_type: str, value: object) -> str:
    content = canonical(value)
    content_hash = digest(content)
    path = PROOF / "artifacts" / content_hash
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise InvalidProof(f"collision d'artefact: {content_hash}")
    else:
        write_new(path, content)
    append_register(logical_name, record_type, content_hash)
    return content_hash


def registered_object(logical_name: str) -> dict[str, object]:
    entry = next(
        (value for value in register_entries() if value["logical_name"] == logical_name),
        None,
    )
    if not entry:
        raise InvalidProof(f"objet absent du registre: {logical_name}")
    return read_json(PROOF / "artifacts" / entry["object_sha256"])


def make_receipt(
    lock: dict[str, object],
    case_id: str,
    action: str,
    input_sha256: object,
    output_sha256: object,
    expected: object,
    observed: object,
    state: str,
    previous_receipt_sha256: str | None,
    unknowns: list[str],
) -> dict[str, object]:
    identity = {
        "path": PATH_ID,
        "mode": "MANUAL_CONTROLLED_P2_LOCAL_FIXTURES",
        "manual_reviewer": "AYO",
        "manual_method_owner": "AYO",
        "runtime": lock["runtime"],
        "instrument_sha256": lock["instrument"]["sha256"],
    }
    receipt = {
        "schema_version": "u025/p2-manual-receipt/v1",
        "proof_id": PROOF_ID,
        "level": "P2",
        "path": PATH_ID,
        "case_id": case_id,
        "input_sha256": input_sha256,
        "output_sha256": output_sha256,
        "expected_identity": identity,
        "observed_identity": identity,
        "action": action,
        "expected": expected,
        "observed": observed,
        "state": state,
        "source_timestamp": lock["source_timestamp"],
        "instrument_version": VERSION,
        "previous_receipt_sha256": previous_receipt_sha256,
        "unknowns": unknowns,
        "candidate_calls": 0,
        "provider_attempts": [],
        "supplier_spend": "0",
    }
    return with_digest(receipt, "receipt_sha256")


def last_receipt_sha256() -> str | None:
    last = None
    for entry in register_entries():
        if entry["record_type"] != "receipt":
            continue
        receipt = read_json(PROOF / "artifacts" / entry["object_sha256"])
        last = receipt["receipt_sha256"]
    return last


def approved_package(case_id: str) -> PaquetApprouveV0:
    approved = PACKAGE_HASHES["manifeste-paquet.json"]
    if case_id == "WT-HARNESS":
        approved = "empreinte-illisible"
    return PaquetApprouveV0(
        manifeste=PACKAGE / "manifeste-paquet.json",
        empreinte_manifeste_approuvee=approved,
        approbateur="Ayo",
        verdict_approbation="APPROUVE",
    )


def automatic_observation(fixture: dict[str, object]) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as folder:
        candidate = Path(folder) / "SORTIE-A.md"
        candidate.write_text(fixture["candidate"], encoding="utf-8")
        result = valider_pre_cadrage_v0(
            approved_package(fixture["case_id"]), candidate
        )
    return {
        "automatic": result.statut,
        "origin": result.origine,
        "gates": [list(value) for value in result.gates],
        "proof": asdict(result)["preuve"],
    }


def automatic_expected(oracle: dict[str, object], case_id: str) -> dict[str, object]:
    value = oracle[case_id]
    return {
        "automatic": value["automatic"],
        "gates": value["gates"],
    }


def blind_mapping(lock_hash: str) -> dict[str, str]:
    ordered = sorted(
        PRESENTED_CASES,
        key=lambda case_id: digest(f"{lock_hash}:{case_id}".encode()),
    )
    return {
        f"D-{ordinal:03d}": case_id
        for ordinal, case_id in enumerate(ordered, start=1)
    }


def blind_dossier(stimulus: str, candidate: str, rubric: str) -> dict[str, str]:
    return {
        "stimulus": stimulus,
        "SORTIE-A": candidate,
        "rubrique HR-001": rubric,
    }


def assert_blind_dossier(value: dict[str, object]) -> None:
    if set(value) != {"stimulus", "SORTIE-A", "rubrique HR-001"}:
        raise InvalidProof("contenu du dossier aveugle divergent")
    content = canonical(value)
    forbidden = [
        *[case_id.encode() for case_id in CASE_ORDER],
        b'"case_id"',
        b'"expected"',
        b'"oracle"',
        b"PROMPTFOO",
        b"ORI_LOCAL",
        P1_PROOF_ID.encode(),
    ]
    if any(value in content for value in forbidden):
        raise InvalidProof("métadonnée révélatrice dans le dossier aveugle")


def render_dossier(value: dict[str, str]) -> bytes:
    text = (
        "## stimulus\n\n"
        + value["stimulus"].rstrip()
        + "\n\n## SORTIE-A\n\n"
        + value["SORTIE-A"].rstrip()
        + "\n\n## rubrique HR-001\n\n"
        + value["rubrique HR-001"].rstrip()
        + "\n"
    )
    return text.encode()


def hold_closure(first_divergence: str) -> None:
    if (PROOF / "closure.md").exists():
        return
    text = f"""---
style_gate: pass
---

# HOLD_MANUAL_P2_EXECUTION

Première divergence : `{first_divergence}`.

Les reçus déjà produits restent conservés et chaînés. Aucun cas supplémentaire, aucune publication et aucune action M3.12 ne sont autorisés.
"""
    write_new(PROOF / "closure.md", text.encode())


def prepare(git_base: str) -> dict[str, object]:
    verify_static_inputs()
    verify_instrument_source()
    if git_base != GIT_BASE:
        raise InvalidProof(f"base Git divergente: {git_base}")
    generated = (
        "proof-lock.json",
        "case-index.json",
        "evidence-register.jsonl",
        "pending-state.json",
        "prepare-root.json",
    )
    if any((PROOF / name).exists() for name in generated):
        raise InvalidProof("preuve P2 déjà préparée")
    fixtures, oracle, rubric = load_p1()
    case_index = case_index_value(fixtures)
    case_index_bytes = canonical(case_index)
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    lock = lock_value(git_base, timestamp, digest(case_index_bytes))
    write_new(PROOF / "case-index.json", case_index_bytes)
    write_json_new(PROOF / "proof-lock.json", lock)
    validate_lock(read_json(PROOF / "proof-lock.json"))

    log_path = PROOF / "network-audit.jsonl"
    write_new(log_path, b"")
    install_network_guard(log_path)
    network_guard_self_test()

    fixture_by_id = {value["case_id"]: value for value in fixtures}
    lock_hash = digest((PROOF / "proof-lock.json").read_bytes())
    previous_receipt = None
    automatic_results = {}
    for case_id in CASE_ORDER:
        fixture = fixture_by_id[case_id]
        opening = make_receipt(
            lock,
            case_id,
            "OPEN_CASE_RECEIPT",
            {
                "proof_lock": lock_hash,
                "case_specification": fixture["specification_sha256"],
                "candidate_fixture": fixture["candidate_sha256"],
            },
            object_digest({"case_id": case_id, "state": "OPENED"}),
            {"case_id": case_id, "ordinal": CASE_ORDER.index(case_id) + 1},
            {"case_id": case_id, "ordinal": CASE_ORDER.index(case_id) + 1},
            "PASS",
            previous_receipt,
            ["HUMAN_REVIEW_PENDING"] if case_id in HUMAN_CASES else [],
        )
        store_object(f"receipt/open/{case_id}", "receipt", opening)
        previous_receipt = opening["receipt_sha256"]

        observed = automatic_observation(fixture)
        expected = automatic_expected(oracle, case_id)
        comparable_observed = {
            "automatic": observed["automatic"],
            "gates": observed["gates"],
        }
        auto_state = "PASS" if comparable_observed == expected else "FAIL"
        evidence = {
            "schema_version": "u025/p2-manual-automatic-evidence/v1",
            "proof_id": PROOF_ID,
            "case_id": case_id,
            "specification_sha256": fixture["specification_sha256"],
            "candidate_fixture_sha256": fixture["candidate_sha256"],
            "expected": expected,
            "observed": observed,
            "state": auto_state,
            "instrument_version": VERSION,
            "candidate_calls": 0,
            "provider_attempts": [],
            "supplier_spend": "0",
        }
        evidence = with_digest(evidence, "automatic_evidence_sha256")
        evidence_hash = store_object(
            f"automatic/{case_id}", "automatic_evidence", evidence
        )
        receipt = make_receipt(
            lock,
            case_id,
            "EXECUTE_G005_THEN_G001_TO_G004",
            {
                "proof_lock": lock_hash,
                "case_specification": fixture["specification_sha256"],
                "candidate_fixture": fixture["candidate_sha256"],
            },
            evidence_hash,
            expected,
            comparable_observed,
            auto_state,
            previous_receipt,
            ["HUMAN_REVIEW_PENDING"] if observed["automatic"] == "PASS" else [],
        )
        store_object(f"receipt/automatic/{case_id}", "receipt", receipt)
        previous_receipt = receipt["receipt_sha256"]
        automatic_results[case_id] = {
            "evidence_sha256": evidence_hash,
            "automatic": observed["automatic"],
            "gates": observed["gates"],
            "state": auto_state,
        }
        if auto_state != "PASS":
            hold_closure(f"AUTOMATIC_ORACLE_DIVERGENCE:{case_id}")
            raise InvalidProof(f"oracle automatique divergent: {case_id}")

    mapping = blind_mapping(lock_hash)
    stimulus = (PACKAGE / "stimulus.md").read_text(encoding="utf-8")
    review_entries = []
    dossier_objects = {}
    for alias, case_id in mapping.items():
        dossier = blind_dossier(
            stimulus, fixture_by_id[case_id]["candidate"], rubric
        )
        assert_blind_dossier(dossier)
        dossier_hash = store_object(
            f"blind_dossier/{alias}", "blind_dossier", dossier
        )
        rendered = render_dossier(dossier)
        rendered_path = PROOF / "review" / f"{alias}.md"
        write_new(rendered_path, rendered)
        review_entries.append(
            {
                "dossier_id": alias,
                "dossier_sha256": dossier_hash,
                "rendered_path": rendered_path.relative_to(ROOT).as_posix(),
                "rendered_sha256": digest(rendered),
            }
        )
        dossier_objects[case_id] = dossier_hash
    unavailable = {
        "schema_version": "u025/p2-manual-blind-dossier-unavailable/v1",
        "available": False,
        "reason": "HUMAN_REVIEW_DOSSIER_UNAVAILABLE",
    }
    unavailable_hash = store_object(
        "blind_dossier/INDISPONIBLE", "blind_dossier_unavailable", unavailable
    )
    dossier_objects["WT-HUMAIN-INDISPONIBLE"] = unavailable_hash
    review_index = {
        "schema_version": "u025/p2-manual-review-index/v1",
        "proof_id": PROOF_ID,
        "manual_reviewer": "AYO",
        "rubric": "HR-001",
        "presentation_count": len(review_entries),
        "dossiers": review_entries,
        "unavailable_dossier_presented": False,
        "style_gate": "skipped:blind_dossier_exact_content",
    }
    write_json_new(PROOF / "review" / "index.json", review_index)

    entries = register_entries()
    pending = {
        "schema_version": "u025/p2-manual-pending-state/v1",
        "proof_id": PROOF_ID,
        "stage": "AWAITING_HUMAN_REVIEW",
        "lock_sha256": lock_hash,
        "automatic_results": automatic_results,
        "blind_mapping": mapping,
        "dossier_objects": dossier_objects,
        "review_index_sha256": digest(canonical(review_index)),
        "register_entry_count": len(entries),
        "register_tail_sha256": entries[-1]["entry_sha256"],
        "last_receipt_sha256": previous_receipt,
        "candidate_calls": 0,
        "provider_attempt_count": 0,
        "supplier_spend_total": "0",
    }
    write_json_new(PROOF / "pending-state.json", pending)
    os.chmod(PROOF / "pending-state.json", 0o600)
    prepare_root = {
        "schema_version": "u025/p2-manual-prepare-root/v1",
        "proof_id": PROOF_ID,
        "proof_lock_sha256": lock_hash,
        "case_index_sha256": digest(case_index_bytes),
        "pending_state_sha256": digest(canonical(pending)),
        "network_audit_sha256": digest(log_path.read_bytes()),
        "review_index_sha256": digest(canonical(review_index)),
        "register_entry_count": len(entries),
        "register_tail_sha256": entries[-1]["entry_sha256"],
        "p1_root_sha256": P1_ROOT_SHA256,
    }
    prepare_root = with_digest(prepare_root, "prepare_root_sha256")
    write_json_new(PROOF / "prepare-root.json", prepare_root)
    return {
        "proof_id": PROOF_ID,
        "stage": "AWAITING_HUMAN_REVIEW",
        "cases": len(CASE_ORDER),
        "presented_dossiers": len(review_entries),
        "unavailable_dossiers": 1,
        "prepare_root_sha256": prepare_root["prepare_root_sha256"],
        "candidate_calls": 0,
        "provider_attempt_count": 0,
        "supplier_spend_total": "0",
    }


def verify_prepare_prefix(allow_additional: bool) -> dict[str, object]:
    verify_static_inputs()
    verify_instrument_source()
    lock = read_json(PROOF / "proof-lock.json")
    validate_lock(lock)
    pending = read_json(PROOF / "pending-state.json")
    root = read_json(PROOF / "prepare-root.json")
    if root["pending_state_sha256"] != digest(canonical(pending)):
        raise InvalidProof("état de préparation divergent")
    base_root = {key: value for key, value in root.items() if key != "prepare_root_sha256"}
    if object_digest(base_root) != root["prepare_root_sha256"]:
        raise InvalidProof("racine de préparation divergente")
    entries = register_entries()
    verify_register(entries)
    count = pending["register_entry_count"]
    if len(entries) < count or (not allow_additional and len(entries) != count):
        raise InvalidProof("tail de préparation divergent")
    if entries[count - 1]["entry_sha256"] != pending["register_tail_sha256"]:
        raise InvalidProof("préfixe append-only divergent")
    review = read_json(PROOF / "review" / "index.json")
    if digest(canonical(review)) != pending["review_index_sha256"]:
        raise InvalidProof("index de revue divergent")
    if review["presentation_count"] != 11 or len(review["dossiers"]) != 11:
        raise InvalidProof("inventaire des dossiers présentés divergent")
    for item in review["dossiers"]:
        rendered = ROOT / item["rendered_path"]
        if digest(rendered.read_bytes()) != item["rendered_sha256"]:
            raise InvalidProof(f"rendu aveugle divergent: {item['dossier_id']}")
        assert_blind_dossier(read_json(PROOF / "artifacts" / item["dossier_sha256"]))
    return pending


def validate_human_input(value: dict[str, object], pending: dict[str, object]) -> dict[str, dict[str, str]]:
    if value.get("proof_id") != PROOF_ID:
        raise InvalidProof("proof_id humain divergent")
    if value.get("manual_reviewer") != "AYO" or value.get("rubric") != "HR-001":
        raise InvalidProof("autorité de revue humaine divergente")
    verdicts = value.get("verdicts")
    if not isinstance(verdicts, list):
        raise InvalidProof("verdicts humains absents")
    by_alias = {}
    for item in verdicts:
        if not isinstance(item, dict):
            raise InvalidProof("verdict humain invalide")
        alias = item.get("dossier_id")
        verdict = item.get("verdict")
        justification = item.get("justification")
        if alias in by_alias or alias not in pending["blind_mapping"]:
            raise InvalidProof(f"alias humain invalide: {alias}")
        if verdict not in HUMAN_VERDICTS:
            raise InvalidProof(f"verdict humain invalide: {alias}")
        if not isinstance(justification, str) or not justification.strip():
            raise InvalidProof(f"justification humaine absente: {alias}")
        if "\n" in justification or "\r" in justification:
            raise InvalidProof(f"justification non structurée: {alias}")
        encoded = justification.encode()
        if any(pattern.search(encoded) for pattern in SECRET_PATTERNS):
            raise InvalidProof(f"justification non publiable: {alias}")
        by_alias[alias] = {
            "verdict": verdict,
            "justification": justification.strip(),
        }
    if set(by_alias) != set(pending["blind_mapping"]):
        raise InvalidProof("gel humain incomplet")
    unavailable = value.get("unavailable")
    if not isinstance(unavailable, dict):
        raise InvalidProof("constat d'indisponibilité absent")
    if unavailable.get("verdict") != "UNABLE_TO_JUDGE":
        raise InvalidProof("dossier indisponible doit valoir UNABLE_TO_JUDGE")
    justification = unavailable.get("justification")
    if not isinstance(justification, str) or not justification.strip():
        raise InvalidProof("justification d'indisponibilité absente")
    if any(pattern.search(justification.encode()) for pattern in SECRET_PATTERNS):
        raise InvalidProof("justification d'indisponibilité non publiable")
    return by_alias


def combine(automatic: str, human: str | None) -> str:
    if automatic == "HARNESS_ERROR":
        return "HARNESS_ERROR"
    if automatic == "FAIL":
        return "CANDIDATE_NOT_ACCEPTABLE"
    if automatic == "PASS" and human == "ACCEPTABLE":
        return "OFFICIALLY_ACCEPTABLE"
    if automatic == "PASS" and human == "NOT_ACCEPTABLE":
        return "CANDIDATE_NOT_ACCEPTABLE"
    if automatic == "PASS" and human == "UNABLE_TO_JUDGE":
        return "UNABLE_TO_JUDGE"
    raise InvalidProof(f"combinaison non autorisée: {automatic}/{human}")


def derive_report(final_receipts: list[dict[str, object]], lock_hash: str) -> dict[str, object]:
    counts = {
        state: sum(receipt["observed"]["result"] == state for receipt in final_receipts)
        for state in REPORT_STATES
    }
    denominator = (
        counts["OFFICIALLY_ACCEPTABLE"]
        + counts["CANDIDATE_NOT_ACCEPTABLE"]
        + counts["PROVIDER_FAILURE"]
    )
    report = {
        "schema_version": "u025/p2-manual-report/v1",
        "proof_id": PROOF_ID,
        "level": "P2",
        "path": PATH_ID,
        "case_count": len(final_receipts),
        "counts": counts,
        "decidable_denominator": denominator,
        "coverage": f"{denominator}/{len(final_receipts)}",
        "official_acceptance_rate": (
            f"{counts['OFFICIALLY_ACCEPTABLE']}/{denominator}" if denominator else None
        ),
        "candidate_calls": sum(receipt["candidate_calls"] for receipt in final_receipts),
        "provider_attempt_count": sum(
            len(receipt["provider_attempts"]) for receipt in final_receipts
        ),
        "supplier_spend_total": "0",
        "automatic_results": {
            receipt["case_id"]: receipt["observed"]["automatic"]
            for receipt in final_receipts
        },
        "human_verdicts": {
            receipt["case_id"]: receipt["observed"]["human"]
            for receipt in final_receipts
            if receipt["observed"]["human"] is not None
        },
        "provenance": {
            "proof_lock_sha256": lock_hash,
            "p1_root_sha256": P1_ROOT_SHA256,
            "p1_oracle_sha256": P1_ORACLE_SHA256,
            "final_receipts_sha256": object_digest(final_receipts),
        },
        "conclusion": "INCONNU",
        "scope": "P2_MANUAL_LOCAL_FIXTURES_NOT_V0_EXECUTION",
        "unknowns": [
            "PROVIDER_BEHAVIOR_UNKNOWN",
            "REAL_CANDIDATE_QUALITY_UNKNOWN",
            "PROVIDER_COST_UNKNOWN",
            "PROVIDER_LATENCY_UNKNOWN",
            "U025_DOMINANCE_UNKNOWN",
        ],
    }
    return with_digest(report, "report_sha256")


def effort_plan(
    component: str,
    phase: str,
    final_receipts: list[dict[str, object]],
    human_receipts: list[dict[str, object]],
    report: dict[str, object],
) -> tuple[str, str, str, object, str]:
    plans = {
        ("configuration", "initial"): (
            "LOCK_MANUAL_P2_CONTRACT",
            "CURRENT_CODEX_SESSION",
            "GO_M3_11_EXECUTE_P2_MANUAL",
            {"proof_lock_sha256": digest((PROOF / "proof-lock.json").read_bytes())},
            "OBSERVE",
        ),
        ("configuration", "recurrent"): (
            "VERIFY_CASE_FIXTURE_AND_SPECIFICATION",
            "CURRENT_CODEX_SESSION",
            "EACH_FROZEN_CASE",
            {"case_count": len(final_receipts), "case_index_sha256": digest((PROOF / "case-index.json").read_bytes())},
            "OBSERVE",
        ),
        ("integration", "initial"): (
            "PREPARE_MANUAL_PATH",
            "CURRENT_CODEX_SESSION",
            "GO_M3_11_EXECUTE_P2_MANUAL",
            {"procedure_sha256": digest(PROCEDURE.read_bytes()), "instrument_sha256": digest(Path(__file__).read_bytes())},
            "OBSERVE",
        ),
        ("integration", "recurrent"): (
            "TRANSFER_FIXTURE_THROUGH_GATES",
            "CURRENT_CODEX_SESSION",
            "EACH_FROZEN_CASE",
            {"automatic_evidence_count": len(final_receipts)},
            "OBSERVE",
        ),
        ("execution", "initial"): (
            "OPEN_APPEND_ONLY_EXECUTION",
            "CURRENT_CODEX_SESSION",
            "VALIDATED_PROOF_LOCK",
            {"register_prefix_tail": read_json(PROOF / "prepare-root.json")["register_tail_sha256"]},
            "OBSERVE",
        ),
        ("execution", "recurrent"): (
            "EXECUTE_CASE_IN_FROZEN_ORDER",
            "CURRENT_CODEX_SESSION",
            "EACH_FROZEN_CASE",
            {"final_receipt_count": len(final_receipts)},
            "OBSERVE",
        ),
        ("revue_humaine", "initial"): (
            "FREEZE_HR001_ROLE_AND_BLINDING",
            "AYO",
            "VALIDATED_PROOF_LOCK",
            {"rubric_sha256": P1_RUBRIC_SHA256, "manual_reviewer": "AYO"},
            "OBSERVE",
        ),
        ("revue_humaine", "recurrent"): (
            "REVIEW_AND_FREEZE_HR001",
            "AYO",
            "EACH_AVAILABLE_BLIND_DOSSIER",
            {"human_receipt_count": len(human_receipts)},
            "OBSERVE",
        ),
        ("verification", "initial"): (
            "QUALIFY_G001_G005_AND_ORACLE_COMPARISON",
            "CURRENT_CODEX_SESSION",
            "VALIDATED_INSTRUMENT",
            {"p1_oracle_sha256": P1_ORACLE_SHA256, "instrument_version": VERSION},
            "OBSERVE",
        ),
        ("verification", "recurrent"): (
            "COMPARE_EXPECTED_AND_OBSERVED",
            "CURRENT_CODEX_SESSION",
            "EACH_CLOSED_CASE",
            {"final_receipts_sha256": object_digest(final_receipts)},
            "OBSERVE",
        ),
        ("maintenance", "initial"): (
            "ASSIGN_METHOD_OWNERSHIP_AND_VERSION",
            "AYO",
            "GO_M3_11_EXECUTE_P2_MANUAL",
            {"manual_method_owner": "AYO", "procedure_sha256": digest(PROCEDURE.read_bytes())},
            "OBSERVE",
        ),
        ("maintenance", "recurrent"): (
            "REQUALIFY_APPLICABLE_METHOD_CHANGE",
            "AYO",
            "APPLICABLE_METHOD_CHANGE",
            None,
            "INCONNU",
        ),
        ("production_rapport", "initial"): (
            "FREEZE_REPORT_FORMULAS",
            "CURRENT_CODEX_SESSION",
            "VALIDATED_PROOF_LOCK",
            {"oracle_sha256": P1_ORACLE_SHA256, "procedure_sha256": digest(PROCEDURE.read_bytes())},
            "OBSERVE",
        ),
        ("production_rapport", "recurrent"): (
            "RECOMPUTE_REPORT_FROM_RECEIPTS",
            "CURRENT_CODEX_SESSION",
            "CLOSED_RECEIPT_SET",
            {"report_sha256": report["report_sha256"]},
            "OBSERVE",
        ),
    }
    return plans[(component, phase)]


def build_effort(
    final_receipts: list[dict[str, object]],
    human_receipts: list[dict[str, object]],
    report: dict[str, object],
) -> dict[str, object]:
    facts = []
    for component in COMPONENTS:
        for phase in ("initial", "recurrent"):
            action, responsibility, trigger, artifact, state = effort_plan(
                component, phase, final_receipts, human_receipts, report
            )
            action_object = {
                "proof_id": PROOF_ID,
                "component": component,
                "phase": phase,
                "action": action,
                "responsibility": responsibility,
                "trigger": trigger,
            }
            action_hash = store_object(
                f"effort_action/{component}/{phase}", "effort_action", action_object
            )
            artifact_hash = None
            if artifact is not None:
                artifact_object = {
                    "proof_id": PROOF_ID,
                    "component": component,
                    "phase": phase,
                    "artifact": artifact,
                }
                artifact_hash = store_object(
                    f"effort_artifact/{component}/{phase}",
                    "effort_artifact",
                    artifact_object,
                )
                if action_hash == artifact_hash:
                    raise InvalidProof("action et artefact d'effort non distincts")
            fact = {
                "schema_version": "u025/p2-manual-effort-fact/v1",
                "proof_id": PROOF_ID,
                "path": PATH_ID,
                "component": component,
                "phase": phase,
                "action": action,
                "artifact": artifact_hash,
                "responsibility": responsibility,
                "trigger": trigger,
                "proof": {
                    "action_sha256": action_hash,
                    "artifact_sha256": artifact_hash,
                },
                "state": state,
            }
            facts.append(with_digest(fact, "fact_sha256"))
    return {
        "schema_version": "u025/p2-manual-effort-register/v1",
        "proof_id": PROOF_ID,
        "facts": facts,
    }


def artifact_index_value() -> dict[str, object]:
    entries = register_entries()
    return {
        "schema_version": "u025/p2-manual-artifact-index/v1",
        "proof_id": PROOF_ID,
        "artifacts": [
            {
                "logical_name": entry["logical_name"],
                "record_type": entry["record_type"],
                "sha256": entry["object_sha256"],
                "size_bytes": (PROOF / "artifacts" / entry["object_sha256"]).stat().st_size,
            }
            for entry in entries
        ],
    }


def write_or_match(path: Path, content: bytes) -> None:
    if path.exists():
        if path.read_bytes() != content:
            raise InvalidProof(f"objet final divergent: {path.name}")
        return
    write_new(path, content)


def finalize(human_input_path: Path) -> dict[str, object]:
    pending = verify_prepare_prefix(allow_additional=True)
    lock = read_json(PROOF / "proof-lock.json")
    human_input = read_json(human_input_path)
    by_alias = validate_human_input(human_input, pending)
    human_input_hash = store_object("human_input", "human_input", human_input)

    log_path = PROOF / "network-audit-finalize.jsonl"
    if not log_path.exists():
        write_new(log_path, b"")
    install_network_guard(log_path)
    network_guard_self_test()

    fixtures, oracle, _ = load_p1()
    fixture_by_id = {value["case_id"]: value for value in fixtures}
    case_to_alias = {case_id: alias for alias, case_id in pending["blind_mapping"].items()}
    actual_human = {}
    human_receipts = []
    previous_receipt = last_receipt_sha256()
    for case_id in HUMAN_CASES:
        if case_id == "WT-HUMAIN-INDISPONIBLE":
            human = {
                "verdict": "UNABLE_TO_JUDGE",
                "justification": human_input["unavailable"]["justification"].strip(),
                "dossier_available": False,
                "dossier_sha256": pending["dossier_objects"][case_id],
            }
        else:
            alias = case_to_alias[case_id]
            decision = by_alias[alias]
            human = {
                "verdict": decision["verdict"],
                "justification": decision["justification"],
                "dossier_available": True,
                "dossier_sha256": pending["dossier_objects"][case_id],
                "dossier_alias": alias,
            }
        actual_human[case_id] = human
        receipt = make_receipt(
            lock,
            case_id,
            "FREEZE_HUMAN_HR001_VERDICT",
            {
                "proof_lock": pending["lock_sha256"],
                "human_input": human_input_hash,
                "blind_dossier": human["dossier_sha256"],
            },
            object_digest(human),
            {"verdict_domain": sorted(HUMAN_VERDICTS)},
            human,
            "PASS",
            previous_receipt,
            [],
        )
        store_object(f"receipt/human/{case_id}", "receipt", receipt)
        previous_receipt = receipt["receipt_sha256"]
        human_receipts.append(receipt)

    human_divergences = [
        case_id
        for case_id in HUMAN_CASES
        if actual_human[case_id]["verdict"] != oracle[case_id]["human"]
    ]
    final_receipts = []
    for case_id in CASE_ORDER:
        automatic = pending["automatic_results"][case_id]["automatic"]
        human = actual_human.get(case_id, {}).get("verdict")
        result = combine(automatic, human)
        observed = {
            "automatic": automatic,
            "human": human,
            "result": result,
        }
        expected = {
            "automatic": oracle[case_id]["automatic"],
            "human": oracle[case_id]["human"],
            "result": oracle[case_id]["result"],
        }
        state = "PASS" if observed == expected else "FAIL"
        receipt = make_receipt(
            lock,
            case_id,
            "COMBINE_FROZEN_STATES_MECHANICALLY",
            {
                "automatic_evidence": pending["automatic_results"][case_id]["evidence_sha256"],
                "human_receipt": (
                    next(
                        value["receipt_sha256"]
                        for value in human_receipts
                        if value["case_id"] == case_id
                    )
                    if case_id in HUMAN_CASES
                    else None
                ),
            },
            object_digest(observed),
            expected,
            observed,
            state,
            previous_receipt,
            [
                "PROVIDER_BEHAVIOR_UNKNOWN",
                "REAL_CANDIDATE_QUALITY_UNKNOWN",
                "PROVIDER_COST_UNKNOWN",
                "PROVIDER_LATENCY_UNKNOWN",
                "U025_DOMINANCE_UNKNOWN",
            ],
        )
        store_object(f"receipt/final/{case_id}", "receipt", receipt)
        previous_receipt = receipt["receipt_sha256"]
        final_receipts.append(receipt)

    report = derive_report(final_receipts, pending["lock_sha256"])
    effort = build_effort(final_receipts, human_receipts, report)
    effort_hash = store_object("effort_register", "effort_register", effort)
    report_hash = store_object("report", "report", report)
    write_or_match(PROOF / "effort-register.json", canonical(effort))
    write_or_match(PROOF / "report.json", canonical(report))

    verdict = "PASS_M3_11_LOCAL_PROOF" if not human_divergences else "HOLD_MANUAL_P2_EXECUTION"
    divergence_text = (
        "aucune"
        if not human_divergences
        else ", ".join(f"HUMAN_ORACLE_DIVERGENCE:{value}" for value in human_divergences)
    )
    closure = f"""---
style_gate: pass
---

# {verdict}

Première divergence : {divergence_text}.

Les 16 fixtures P1 v2 ont traversé la procédure manuelle contrôlée. Les contrôles automatiques, les verdicts humains et les résultats finaux restent séparés. Appels candidats : 0. Tentatives fournisseur : 0. Dépense fournisseur : 0.

Conclusion P2 : `INCONNU`. Cette preuve ne démontre ni comportement fournisseur, ni qualité d'un candidat réel, ni coût ou latence fournisseur, ni dominance U-025. STOP avant M3.12.
"""
    write_or_match(PROOF / "closure.md", closure.encode())

    artifact_index = artifact_index_value()
    write_or_match(PROOF / "artifact-index.json", canonical(artifact_index))
    entries = register_entries()
    manifest = {
        "schema_version": "u025/p2-manual-evidence-manifest/v1",
        "proof_id": PROOF_ID,
        "top_level": {
            "proof_lock_sha256": digest((PROOF / "proof-lock.json").read_bytes()),
            "case_index_sha256": digest((PROOF / "case-index.json").read_bytes()),
            "prepare_root_sha256": digest((PROOF / "prepare-root.json").read_bytes()),
            "artifact_index_sha256": digest(canonical(artifact_index)),
            "evidence_register_sha256": digest((PROOF / "evidence-register.jsonl").read_bytes()),
            "effort_register_sha256": digest(canonical(effort)),
            "report_sha256": digest(canonical(report)),
            "closure_sha256": digest(closure.encode()),
            "review_index_sha256": digest((PROOF / "review" / "index.json").read_bytes()),
        },
        "register": {
            "entry_count": len(entries),
            "tail_entry_sha256": entries[-1]["entry_sha256"],
        },
        "objects": {
            "final_receipts": [value["receipt_sha256"] for value in final_receipts],
            "human_receipts": [value["receipt_sha256"] for value in human_receipts],
            "effort_register": effort_hash,
            "report": report_hash,
        },
        "human_divergences": human_divergences,
        "verdict": verdict,
    }
    write_or_match(PROOF / "evidence-manifest.json", canonical(manifest))
    proof_root = {
        "schema_version": "u025/p2-manual-proof-root/v1",
        "proof_id": PROOF_ID,
        "p1_v2": {
            "proof_id": P1_PROOF_ID,
            "root_sha256": P1_ROOT_SHA256,
        },
        "proof_lock_sha256": digest((PROOF / "proof-lock.json").read_bytes()),
        "case_index_sha256": digest((PROOF / "case-index.json").read_bytes()),
        "evidence_register_sha256": digest((PROOF / "evidence-register.jsonl").read_bytes()),
        "evidence_register_tail_sha256": entries[-1]["entry_sha256"],
        "evidence_manifest_sha256": digest(canonical(manifest)),
        "report_sha256": report["report_sha256"],
        "verdict": verdict,
    }
    proof_root = with_digest(proof_root, "root_sha256")
    write_or_match(PROOF / "proof-root.json", canonical(proof_root))
    final_state = {
        "schema_version": "u025/p2-manual-final-state/v1",
        "proof_id": PROOF_ID,
        "verdict": verdict,
        "root_sha256": proof_root["root_sha256"],
        "human_divergences": human_divergences,
        "register_entry_count": len(entries),
        "register_tail_sha256": entries[-1]["entry_sha256"],
        "last_receipt_sha256": previous_receipt,
    }
    write_or_match(PROOF / "final-state.json", canonical(final_state))
    return {
        "proof_id": PROOF_ID,
        "verdict": verdict,
        "root_sha256": proof_root["root_sha256"],
        "human_divergences": human_divergences,
        "report": report,
    }


def verify_receipts(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    previous = None
    final = []
    for entry in entries:
        if entry["record_type"] != "receipt":
            continue
        receipt = read_json(PROOF / "artifacts" / entry["object_sha256"])
        if set(receipt) != RECEIPT_FIELDS:
            raise InvalidProof(f"schéma de reçu divergent: {entry['logical_name']}")
        base = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
        if object_digest(base) != receipt["receipt_sha256"]:
            raise InvalidProof(f"empreinte de reçu divergente: {entry['logical_name']}")
        if receipt["previous_receipt_sha256"] != previous:
            raise InvalidProof(f"chaîne de reçus divergente: {entry['logical_name']}")
        if receipt["candidate_calls"] != 0 or receipt["provider_attempts"] != []:
            raise InvalidProof("appel candidat ou tentative fournisseur observé")
        if receipt["supplier_spend"] != "0":
            raise InvalidProof("dépense fournisseur non nulle")
        previous = receipt["receipt_sha256"]
        if entry["logical_name"].startswith("receipt/final/"):
            final.append(receipt)
    if len(final) != 16 or tuple(value["case_id"] for value in final) != CASE_ORDER:
        raise InvalidProof("inventaire des reçus finaux divergent")
    return final


def verify_effort(effort: dict[str, object]) -> None:
    facts = effort.get("facts", [])
    expected = [(component, phase) for component in COMPONENTS for phase in ("initial", "recurrent")]
    observed = [(value["component"], value["phase"]) for value in facts]
    if observed != expected:
        raise InvalidProof("inventaire des 14 faits d'effort divergent")
    for fact in facts:
        base = {key: value for key, value in fact.items() if key != "fact_sha256"}
        if object_digest(base) != fact["fact_sha256"]:
            raise InvalidProof("empreinte de fait d'effort divergente")
        if fact["component"] == "revue_humaine" and fact["responsibility"] != "AYO":
            raise InvalidProof("responsabilité humaine non attribuée à Ayo")
        if fact["component"] == "maintenance" and fact["responsibility"] != "AYO":
            raise InvalidProof("responsabilité de méthode non attribuée à Ayo")
        if fact["state"] == "OBSERVE":
            proof = fact["proof"]
            if not proof["action_sha256"] or not proof["artifact_sha256"]:
                raise InvalidProof("preuve OBSERVE incomplète")
            if proof["action_sha256"] == proof["artifact_sha256"]:
                raise InvalidProof("action et artefact OBSERVE non distincts")


def verify_secret_scan() -> None:
    for path in PROOF.rglob("*"):
        if not path.is_file():
            continue
        content = path.read_bytes()
        if any(pattern.search(content) for pattern in SECRET_PATTERNS):
            raise InvalidProof(f"secret potentiel détecté: {path.relative_to(ROOT)}")


def verify() -> dict[str, object]:
    pending = verify_prepare_prefix(allow_additional=True)
    final_state = read_json(PROOF / "final-state.json")
    entries = register_entries()
    verify_register(entries)
    if final_state["register_entry_count"] != len(entries):
        raise InvalidProof("compte final du registre divergent")
    if final_state["register_tail_sha256"] != entries[-1]["entry_sha256"]:
        raise InvalidProof("tail final divergent")
    final_receipts = verify_receipts(entries)
    human_receipts = [
        entry for entry in entries if entry["logical_name"].startswith("receipt/human/")
    ]
    if len(human_receipts) != 12:
        raise InvalidProof("inventaire des reçus humains divergent")
    report = read_json(PROOF / "report.json")
    expected_report = derive_report(
        final_receipts, digest((PROOF / "proof-lock.json").read_bytes())
    )
    if report != expected_report:
        raise InvalidProof("rapport non reproductible depuis les reçus")
    expected_counts = {
        "OFFICIALLY_ACCEPTABLE": 1,
        "CANDIDATE_NOT_ACCEPTABLE": 13,
        "PROVIDER_FAILURE": 0,
        "HARNESS_ERROR": 1,
        "UNABLE_TO_JUDGE": 1,
    }
    if report["counts"] != expected_counts:
        raise InvalidProof(f"compteurs du rapport divergents: {report['counts']!r}")
    if report["decidable_denominator"] != 14:
        raise InvalidProof("dénominateur décidable divergent")
    if report["coverage"] != "14/16" or report["official_acceptance_rate"] != "1/14":
        raise InvalidProof("couverture ou taux divergent")
    if report["candidate_calls"] != 0 or report["provider_attempt_count"] != 0:
        raise InvalidProof("compteurs externes non nuls")
    if report["supplier_spend_total"] != "0":
        raise InvalidProof("dépense fournisseur non nulle")
    effort = read_json(PROOF / "effort-register.json")
    verify_effort(effort)
    manifest = read_json(PROOF / "evidence-manifest.json")
    root = read_json(PROOF / "proof-root.json")
    root_base = {key: value for key, value in root.items() if key != "root_sha256"}
    if object_digest(root_base) != root["root_sha256"]:
        raise InvalidProof("racine P2 divergente")
    if root["evidence_manifest_sha256"] != digest(canonical(manifest)):
        raise InvalidProof("manifeste de preuve divergent")
    if root["p1_v2"]["root_sha256"] != P1_ROOT_SHA256:
        raise InvalidProof("liaison de racine P1 divergente")
    if root["verdict"] != "PASS_M3_11_LOCAL_PROOF":
        raise InvalidProof("fermeture locale non PASS")
    network_lines = (PROOF / "network-audit.jsonl").read_bytes().splitlines()
    finalize_lines = (PROOF / "network-audit-finalize.jsonl").read_bytes().splitlines()
    if len(network_lines) != 1 or len(finalize_lines) != 1:
        raise InvalidProof("journal réseau contient une tentative inattendue")
    for line in [*network_lines, *finalize_lines]:
        value = json.loads(line)
        if value.get("event") != "socket.__new__" or value.get("state") != "BLOCKED":
            raise InvalidProof("preuve du contrôle réseau divergente")
    verify_secret_scan()
    return {
        "proof_id": PROOF_ID,
        "verdict": "PASS",
        "root_sha256": root["root_sha256"],
        "case_count": 16,
        "human_receipts": 12,
        "effort_facts": 14,
        "register_entries": len(entries),
        "register_tail_sha256": entries[-1]["entry_sha256"],
        "candidate_calls": 0,
        "provider_attempt_count": 0,
        "supplier_spend_total": "0",
        "conclusion": "INCONNU",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--git-base", required=True)
    finalize_parser = subparsers.add_parser("finalize")
    finalize_parser.add_argument("--human-input", type=Path, required=True)
    subparsers.add_parser("verify-pending")
    subparsers.add_parser("verify")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args.git_base)
        elif args.command == "finalize":
            result = finalize(args.human_input)
        elif args.command == "verify-pending":
            pending = verify_prepare_prefix(allow_additional=False)
            result = {
                "proof_id": PROOF_ID,
                "stage": pending["stage"],
                "cases": len(pending["automatic_results"]),
                "presented_dossiers": len(pending["blind_mapping"]),
                "candidate_calls": pending["candidate_calls"],
                "provider_attempt_count": pending["provider_attempt_count"],
                "supplier_spend_total": pending["supplier_spend_total"],
            }
        else:
            result = verify()
    except (InvalidProof, OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"verdict": "HOLD_MANUAL_P2_EXECUTION", "error": str(error)}, ensure_ascii=False, sort_keys=True))
        raise SystemExit(1)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
