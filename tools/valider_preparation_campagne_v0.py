from __future__ import annotations

import argparse
import ast
from collections.abc import Mapping
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import sys

RACINE_IMPORT = Path(__file__).resolve().parents[1]
if str(RACINE_IMPORT) not in sys.path:
    sys.path.insert(0, str(RACINE_IMPORT))

from tools.campaign_v0_manual_harness import (
    ManualHarness,
    ManualHarnessError,
    prepare_command_descriptor,
)
from tools.campaign_v0_shared_core_adapter import (
    INCONNU,
    PreparationContractError,
    build_blind_decision_view,
    classify_incident,
    normalise_observations,
)


RACINE = Path(__file__).resolve().parents[1]
DOSSIER = (
    RACINE
    / "tasks/dev/pre-cadrage-entretien-client/campagne-v0/"
    "preparation-m7-1-v1"
)
CONTRATS_PAR_DEFAUT = DOSSIER / "contrats-preparation.json"
MANIFESTE_PAR_DEFAUT = DOSSIER / "manifeste-empreintes.json"
RECU_PAR_DEFAUT = DOSSIER / "recu-validation.json"
ADAPTER_PAR_DEFAUT = RACINE / "tools/campaign_v0_shared_core_adapter.py"
HARNESS_PAR_DEFAUT = RACINE / "tools/campaign_v0_manual_harness.py"

CHEMIN_CONTRATS = (
    "tasks/dev/pre-cadrage-entretien-client/campagne-v0/"
    "preparation-m7-1-v1/contrats-preparation.json"
)
CHEMIN_MANIFESTE = (
    "tasks/dev/pre-cadrage-entretien-client/campagne-v0/"
    "preparation-m7-1-v1/manifeste-empreintes.json"
)
CHEMIN_RECU = (
    "tasks/dev/pre-cadrage-entretien-client/campagne-v0/"
    "preparation-m7-1-v1/recu-validation.json"
)
CHEMIN_ADAPTER = "tools/campaign_v0_shared_core_adapter.py"
CHEMIN_HARNESS = "tools/campaign_v0_manual_harness.py"

PHASE_CONTRACT_SHA256 = "66cc12b780e6d972bc6ec4399a695bf44b4fd4db22d9b96d30573744e905712f"
LOCK_ROOT = "94f796d167915d8e1ce9fd471b415eff468e8afda685955c1e757d29567b3918"
CONTRACTS_SHA256 = "d96bb388fc3727f4b8a5de2401f0f05c91812044ed834a54b2d79ad2a6c0313e"
ADAPTER_SHA256 = "42b24fb7e8a36bf60c747b44807a2e0e017facc7b546fac7c20fd39cdc36e208"
HARNESS_SHA256 = "6191752a91a11be69a9074b92d6b14ecb6caef2e38ff78b3254259f851f0aee9"
PREPARATION_ROOT = "fdf63b7a7bbb6f578d9b7aa4e67dee7b13eee825500e3214b4b3fa27a1212b1d"

OUTPUT_IDENTITIES = [
    "campaign-v0-measurement-protocol/v1",
    "campaign-v0-acquisition-receipt/v1",
    "campaign-v0-decision-view/v1",
    "campaign-v0-manual-harness/v1",
    "campaign-v0-shared-core-adapter/v1",
]
AUTHORIZATIONS = {
    "account_inspection": "NOT_AUTHORIZED",
    "acquisition": "NOT_AUTHORIZED",
    "campaign_execution": "NOT_AUTHORIZED",
    "canary": "NOT_AUTHORIZED",
    "fallback": "NOT_AUTHORIZED",
    "human_review": "NOT_AUTHORIZED",
    "model_call": "NOT_AUTHORIZED",
    "provider_operation": "NOT_AUTHORIZED",
    "quota_consumption": "NOT_AUTHORIZED",
    "retry": "NOT_AUTHORIZED",
    "spend": "NOT_AUTHORIZED",
}
ZERO_EXECUTION = {
    "acquisitions_performed": 0,
    "campaign_runs": 0,
    "human_reviews_performed": 0,
    "model_calls": 0,
    "provider_contacted": False,
    "provider_operations": 0,
    "quota_consumed": False,
    "retries_performed": 0,
    "spend_incurred": False,
}
PREPARATION_ARTIFACTS = [
    {
        "identity": "campaign-v0-preparation-contract-package/v1",
        "path": CHEMIN_CONTRATS,
        "sha256": CONTRACTS_SHA256,
    },
    {
        "identity": "campaign-v0-shared-core-adapter/v1",
        "path": CHEMIN_ADAPTER,
        "sha256": ADAPTER_SHA256,
    },
    {
        "identity": "campaign-v0-manual-harness/v1",
        "path": CHEMIN_HARNESS,
        "sha256": HARNESS_SHA256,
    },
]
M6_6_ARTIFACTS = [
    {
        "path": "tasks/dev/pre-cadrage-entretien-client/campagne-v0/verrou-campagne-v1/verrou.json",
        "sha256": "b8ccf2ac10a7536700d3ab37f2989dcd8fa67b08592c387a57732199d4e0c102",
    },
    {
        "path": "tasks/dev/pre-cadrage-entretien-client/campagne-v0/verrou-campagne-v1/manifeste-empreintes.json",
        "sha256": LOCK_ROOT,
    },
    {
        "path": "tasks/dev/pre-cadrage-entretien-client/campagne-v0/verrou-campagne-v1/recu-validation.json",
        "sha256": "2ff5282d5f040d6ae01d25e6c1d089b0055fd6ce8e580c542baac97e62f5ed68",
    },
]
M6_PREDECESSORS = [
    {
        "milestone": "M6.1",
        "path": "tasks/dev/pre-cadrage-entretien-client/campagne-v0/autorites-v1/autorites.json",
        "sha256": "d551362f35a9e650d78330e79b757bb3e63c892b92fcaa08b48f86599d951d82",
    },
    {
        "milestone": "M6.2",
        "path": "tasks/dev/pre-cadrage-entretien-client/campagne-v0/contrats-versionnes-v1/contrats-versionnes.json",
        "sha256": "cf4c2784039edb5cb2be43911d7f3fbc52ff66612c4a4436094602a3dd8d1fcd",
    },
    {
        "milestone": "M6.3",
        "path": "tasks/dev/pre-cadrage-entretien-client/campagne-v0/panel-identites-v1/panel-identites.json",
        "sha256": "c6d31dbc7953f3c21d9f5e3b5ff42d38b8171eab2e5dee52ecfb10920cc849d0",
    },
    {
        "milestone": "M6.4",
        "path": "tasks/dev/pre-cadrage-entretien-client/campagne-v0/plan-acquisition-v1/plan-acquisition.json",
        "sha256": "7a6580a41e5e8f795f0ffe50ca0263050b78ba82ca1c052f8a140254ea403e2a",
    },
    {
        "milestone": "M6.5",
        "path": "tasks/dev/pre-cadrage-entretien-client/campagne-v0/politique-decision-v1/politique-decision.json",
        "sha256": "c378f180f93cb9f2ad481137618a8cd1fe2077f97389283ab13567fe6b857000",
    },
]
APPROVED_SOURCES = [
    {
        "role": "APPROVED_PACKAGE",
        "path": "tasks/dev/pre-cadrage-entretien-client/manifeste-paquet.json",
        "sha256": "8030128d159e4203483b19f0e37692a53f01baecc38fbccaa321541c23e71a10",
    },
    {
        "role": "APPROVED_STIMULUS",
        "path": "tasks/dev/pre-cadrage-entretien-client/stimulus.md",
        "sha256": "20f0be450640704b0c467eee57ca2ea58a4d629e63eba3efccbc6f68440e07e4",
    },
    {
        "role": "AUTOMATIC_CONTROLS",
        "path": "tools/validateur_pre_cadrage_v0.py",
        "sha256": "e631184b84270c4b3dbf931910436ad65b7d08c02016c94d2dfe53e27ead2056",
    },
]
AUTHORITIES = [
    {
        "role": "M6_6_PREPARATION_GO",
        "comment_id": 5357024090,
        "node_id": "IC_kwDOTswBxM8AAAABP02zWg",
        "created_at": "2026-08-20T14:08:14Z",
        "updated_at": "2026-08-20T14:08:14Z",
        "body_sha256": "bf1946739058fc0f34841dc4f3e26097b0b2528b908221bdabecb2d13420674f",
    },
    {
        "authority_value": "GO M7.1 PHASE 1",
        "author": "ayoahha",
        "author_association": "OWNER",
        "comment_id": 5357622173,
        "node_id": "IC_kwDOTswBxM8AAAABP1bTnQ",
        "created_at": "2026-08-20T14:55:35Z",
        "updated_at": "2026-08-20T14:55:35Z",
        "body_sha256": "422837581b97218a1ed8b925b64f684ddde609878f9d2fb0f3e722982141b8a4",
    },
]


class ErreurPreparationCampagne(ValueError):
    pass


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _canonical(document: object) -> bytes:
    try:
        return (
            json.dumps(
                document,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
            + b"\n"
        )
    except (TypeError, ValueError) as exc:
        raise ErreurPreparationCampagne("valeur JSON non canonique") from exc


def _load_canonical(path: Path, name: str) -> tuple[dict[str, object], bytes]:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise ErreurPreparationCampagne(f"clé JSON dupliquée: {name}")
            result[key] = value
        return result

    def forbidden_number(_: str) -> object:
        raise ErreurPreparationCampagne(f"float ou constante interdite: {name}")

    try:
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise ErreurPreparationCampagne(f"fichier régulier non-symlink requis: {name}")
        content = path.read_bytes()
        document = json.loads(
            content.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_float=forbidden_number,
            parse_constant=forbidden_number,
        )
    except ErreurPreparationCampagne:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ErreurPreparationCampagne(f"JSON inaccessible ou invalide: {name}") from exc
    if not isinstance(document, dict) or content != _canonical(document):
        raise ErreurPreparationCampagne(f"JSON non canonique ou non-objet: {name}")
    return document, content


def _closed(value: object, fields: set[str], name: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ErreurPreparationCampagne(f"schéma fermé divergent: {name}")
    return value


def _equal(observed: object, expected: object, name: str) -> None:
    if type(observed) is not type(expected):
        raise ErreurPreparationCampagne(f"type divergent: {name}")
    if isinstance(observed, dict):
        if set(observed) != set(expected):
            raise ErreurPreparationCampagne(f"schéma divergent: {name}")
        for key in observed:
            _equal(observed[key], expected[key], f"{name}.{key}")
        return
    if isinstance(observed, list):
        if len(observed) != len(expected):
            raise ErreurPreparationCampagne(f"cardinalité divergente: {name}")
        for index, (left, right) in enumerate(zip(observed, expected, strict=True)):
            _equal(left, right, f"{name}.{index}")
        return
    if observed != expected:
        raise ErreurPreparationCampagne(f"valeur divergente: {name}")


def _public_file(root: Path, raw_path: object, name: str) -> Path:
    if not isinstance(raw_path, str):
        raise ErreurPreparationCampagne(f"chemin non textuel: {name}")
    relative = PurePosixPath(raw_path)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ErreurPreparationCampagne(f"chemin non sûr: {name}")
    current = root
    try:
        for part in relative.parts:
            current = current / part
            if stat.S_ISLNK(current.lstat().st_mode):
                raise ErreurPreparationCampagne(f"lien symbolique interdit: {name}")
        if not stat.S_ISREG(current.lstat().st_mode):
            raise ErreurPreparationCampagne(f"fichier régulier requis: {name}")
    except OSError as exc:
        raise ErreurPreparationCampagne(f"chemin inaccessible: {name}") from exc
    return current


def _verify_references(
    observed: object,
    expected: list[dict[str, object]],
    root: Path,
    name: str,
) -> None:
    _equal(observed, expected, name)
    for index, reference in enumerate(expected):
        path = _public_file(root, reference["path"], f"{name}.{index}")
        if _sha256(path.read_bytes()) != reference["sha256"]:
            raise ErreurPreparationCampagne(f"empreinte divergente: {name}.{index}")


def assert_offline_module(path: Path, kind: str) -> None:
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        raise ErreurPreparationCampagne(f"module offline invalide: {kind}") from exc
    allowed_imports = {
        "adapter": {
            "__future__",
            "collections.abc",
            "hashlib",
            "json",
            "re",
            "types",
        },
        "harness": {
            "__future__",
            "collections.abc",
            "tools.campaign_v0_shared_core_adapter",
        },
    }[kind]
    forbidden_calls = {
        "__import__",
        "compile",
        "eval",
        "exec",
        "getattr",
        "open",
        "setattr",
    }
    forbidden_attributes = {
        "call",
        "connect",
        "exec",
        "open_connection",
        "popen",
        "request",
        "run",
        "send",
        "spawn",
        "system",
        "urlopen",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = {alias.name for alias in node.names}
            if not names.issubset(allowed_imports):
                raise ErreurPreparationCampagne(f"import interdit: {kind}")
        elif isinstance(node, ast.ImportFrom):
            if node.module not in allowed_imports:
                raise ErreurPreparationCampagne(f"import interdit: {kind}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in forbidden_calls:
                raise ErreurPreparationCampagne(f"appel dynamique interdit: {kind}")
            if isinstance(node.func, ast.Attribute) and node.func.attr in forbidden_attributes:
                raise ErreurPreparationCampagne(f"appel process/réseau interdit: {kind}")


def _validate_contract_package(document: dict[str, object], content: bytes) -> None:
    if _sha256(content) != CONTRACTS_SHA256:
        raise ErreurPreparationCampagne("empreinte du paquet de contrats divergente")
    _closed(
        document,
        {
            "authority_bindings",
            "authorizations",
            "contracts",
            "hash_conventions",
            "lock_binding",
            "output_identities",
            "schema_version",
            "scope",
            "value_state_contract",
        },
        "contrats",
    )
    if document["schema_version"] != "campaign-v0-preparation-contract-package/v1":
        raise ErreurPreparationCampagne("identité du paquet divergente")
    _equal(document["output_identities"], OUTPUT_IDENTITIES, "output_identities")
    _equal(document["authorizations"], AUTHORIZATIONS, "authorizations")
    lock = _closed(document["lock_binding"], {"root_sha256", "schema_version"}, "lock_binding")
    if lock != {"root_sha256": LOCK_ROOT, "schema_version": "campaign-v0-campaign-lock/v1"}:
        raise ErreurPreparationCampagne("liaison M6.6 divergente")
    contracts = _closed(
        document["contracts"],
        {
            "acquisition_receipt",
            "decision_view",
            "manual_harness",
            "measurement_protocol",
            "shared_core_adapter",
        },
        "contracts",
    )
    contract_identities = {
        "acquisition_receipt": "campaign-v0-acquisition-receipt/v1",
        "decision_view": "campaign-v0-decision-view/v1",
        "manual_harness": "campaign-v0-manual-harness/v1",
        "measurement_protocol": "campaign-v0-measurement-protocol/v1",
        "shared_core_adapter": "campaign-v0-shared-core-adapter/v1",
    }
    for key, identity in contract_identities.items():
        if not isinstance(contracts[key], dict) or contracts[key].get("identity") != identity:
            raise ErreurPreparationCampagne(f"identité de contrat divergente: {key}")
    protocol = contracts["measurement_protocol"]
    panel = protocol["panel"]
    if not isinstance(panel, list) or [item["configuration_id"] for item in panel] != [
        "grok46_xai_build_oauth",
        "kimi_k3_cursor_cli",
    ]:
        raise ErreurPreparationCampagne("panel fermé divergent")
    if [item["slot"] for item in panel] != [
        "ACQ-GROK46-PRIMARY-001",
        "ACQ-KIMIK3-PRIMARY-001",
    ]:
        raise ErreurPreparationCampagne("slots fermés divergents")
    for item in panel:
        descriptor = prepare_command_descriptor(item["configuration_id"])
        expected = {
            "argv": descriptor["argv"],
            "state": "REQUESTED",
            "workspace": descriptor["workspace"],
        }
        _equal(item["command_descriptor"], expected, f"descriptor.{item['configuration_id']}")
    plan = protocol["acquisition_plan"]
    _equal(
        plan,
        {
            "automatic_retries": 0,
            "fallbacks": "NONE",
            "manual_retries": 0,
            "planned_slots": 2,
            "replications": 0,
            "tools": "NONE",
            "web_search": False,
        },
        "acquisition_plan",
    )


def _validate_runtime_behavior() -> None:
    facts = {
        "identity_mismatch": False,
        "local_or_unattributable_failure": False,
        "missing_required_observation": False,
        "provider_attribution_proven": False,
        "provider_operation_failed": True,
    }
    if classify_incident(facts) != "HARNESS_ERROR":
        raise ErreurPreparationCampagne("incident non attribuable mal classé")
    missing = normalise_observations({})
    if (
        missing["served_model"] != {"state": "OBSERVED", "value": INCONNU}
        or missing["provider_cost"]["value_minor"] != INCONNU
    ):
        raise ErreurPreparationCampagne("observation absente imputée")
    harness = ManualHarness()
    first = harness.record_observation("grok46_xai_build_oauth", {})
    try:
        harness.record_observation("grok46_xai_build_oauth", {})
    except ManualHarnessError:
        pass
    else:
        raise ErreurPreparationCampagne("écrasement de reçu accepté")
    receipt = json.loads(first)
    controls = {f"G-{index:03d}": INCONNU for index in range(1, 6)}
    view = build_blind_decision_view(receipt, "ITEM-001", {"criterion": "SYNTHETIC"}, controls)
    forbidden = {
        "acquisition_id",
        "configuration_id",
        "cost",
        "latency",
        "model",
        "provider",
        "route",
        "usage",
    }
    if set(view).intersection(forbidden):
        raise ErreurPreparationCampagne("fuite dans la vue aveugle")


def _expected_receipt() -> dict[str, object]:
    return {
        "authorizations": AUTHORIZATIONS,
        "counts": {
            "approved_sources": 3,
            "m6_6_artifacts": 3,
            "m6_predecessor_artifacts": 5,
            "output_identities": 5,
            "provider_capability_imports": 0,
            "provider_invocation_paths": 0,
            "rooted_preparation_artifacts": 3,
        },
        "lock_binding": {
            "root_sha256": LOCK_ROOT,
            "schema_version": "campaign-v0-campaign-lock/v1",
        },
        "output_identities": OUTPUT_IDENTITIES,
        "phase_contract_sha256": PHASE_CONTRACT_SHA256,
        "preparation_root": {
            "algorithm": "SHA256",
            "manifest_path": CHEMIN_MANIFESTE,
            "sha256": PREPARATION_ROOT,
        },
        "rooted_artifacts": [
            *PREPARATION_ARTIFACTS,
            {
                "identity": "campaign-v0-preparation-manifest/v1",
                "path": CHEMIN_MANIFESTE,
                "sha256": PREPARATION_ROOT,
            },
        ],
        "schema_version": "campaign-v0-preparation-validation-receipt/v1",
        "status": "PREPARATION_CAMPAGNE_V0_OK",
        "zero_execution_proof": ZERO_EXECUTION,
    }


def valider_preparation_campagne_v0(
    contracts_path: Path = CONTRATS_PAR_DEFAUT,
    manifest_path: Path = MANIFESTE_PAR_DEFAUT,
    receipt_path: Path = RECU_PAR_DEFAUT,
    adapter_path: Path = ADAPTER_PAR_DEFAUT,
    harness_path: Path = HARNESS_PAR_DEFAUT,
    root: Path = RACINE,
) -> dict[str, object]:
    contracts, contracts_bytes = _load_canonical(contracts_path, "contrats")
    manifest, manifest_bytes = _load_canonical(manifest_path, "manifeste")
    receipt, receipt_bytes = _load_canonical(receipt_path, "recu")
    _validate_contract_package(contracts, contracts_bytes)
    if _sha256(adapter_path.read_bytes()) != ADAPTER_SHA256:
        raise ErreurPreparationCampagne("empreinte adapter divergente")
    if _sha256(harness_path.read_bytes()) != HARNESS_SHA256:
        raise ErreurPreparationCampagne("empreinte harness divergente")
    assert_offline_module(adapter_path, "adapter")
    assert_offline_module(harness_path, "harness")
    _closed(
        manifest,
        {
            "approved_sources",
            "authorities",
            "excluded_from_root",
            "hash_conventions",
            "m6_6_artifacts",
            "m6_predecessor_artifacts",
            "metadata",
            "output_identities",
            "preparation_artifacts",
            "schema_version",
            "zero_execution_claim",
        },
        "manifeste",
    )
    if manifest["schema_version"] != "campaign-v0-preparation-manifest/v1":
        raise ErreurPreparationCampagne("identité manifeste divergente")
    if _sha256(manifest_bytes) != PREPARATION_ROOT:
        raise ErreurPreparationCampagne("racine de préparation divergente")
    _equal(manifest["authorities"], AUTHORITIES, "authorities")
    _equal(manifest["output_identities"], OUTPUT_IDENTITIES, "manifest.output_identities")
    _equal(manifest["zero_execution_claim"], ZERO_EXECUTION, "zero_execution_claim")
    _equal(manifest["preparation_artifacts"], PREPARATION_ARTIFACTS, "preparation_artifacts")
    supplied_paths = {
        CHEMIN_CONTRATS: contracts_path,
        CHEMIN_ADAPTER: adapter_path,
        CHEMIN_HARNESS: harness_path,
    }
    for reference in PREPARATION_ARTIFACTS:
        if _sha256(supplied_paths[reference["path"]].read_bytes()) != reference["sha256"]:
            raise ErreurPreparationCampagne("empreinte de préparation divergente")
    _verify_references(manifest["m6_6_artifacts"], M6_6_ARTIFACTS, root, "m6_6_artifacts")
    _verify_references(
        manifest["m6_predecessor_artifacts"],
        M6_PREDECESSORS,
        root,
        "m6_predecessor_artifacts",
    )
    _verify_references(manifest["approved_sources"], APPROVED_SOURCES, root, "approved_sources")
    excluded = [CHEMIN_MANIFESTE, CHEMIN_RECU]
    _equal(manifest["excluded_from_root"], excluded, "excluded_from_root")
    rooted_paths = {item["path"] for item in PREPARATION_ARTIFACTS + M6_6_ARTIFACTS + M6_PREDECESSORS + APPROVED_SOURCES}
    if CHEMIN_MANIFESTE in rooted_paths or CHEMIN_RECU in rooted_paths:
        raise ErreurPreparationCampagne("cycle dans la racine de préparation")
    expected_receipt = _expected_receipt()
    if receipt_bytes != _canonical(expected_receipt) or receipt != expected_receipt:
        raise ErreurPreparationCampagne("reçu de validation non déterministe")
    _validate_runtime_behavior()
    return {
        "output_identities": OUTPUT_IDENTITIES,
        "preparation_root": PREPARATION_ROOT,
        "status": "PREPARATION_CAMPAGNE_V0_OK",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contracts", type=Path, default=CONTRATS_PAR_DEFAUT)
    parser.add_argument("--manifest", type=Path, default=MANIFESTE_PAR_DEFAUT)
    parser.add_argument("--receipt", type=Path, default=RECU_PAR_DEFAUT)
    parser.add_argument("--adapter", type=Path, default=ADAPTER_PAR_DEFAUT)
    parser.add_argument("--harness", type=Path, default=HARNESS_PAR_DEFAUT)
    args = parser.parse_args(argv)
    try:
        result = valider_preparation_campagne_v0(
            args.contracts,
            args.manifest,
            args.receipt,
            args.adapter,
            args.harness,
            RACINE,
        )
    except (ErreurPreparationCampagne, PreparationContractError, OSError) as exc:
        print(f"HOLD_M7_1_PREPARATION: {exc}", file=sys.stderr)
        return 1
    print(f"PREPARATION_CAMPAGNE_V0_OK root={result['preparation_root']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
