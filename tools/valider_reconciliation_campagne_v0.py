from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import sys


RACINE = Path(__file__).resolve().parents[1]
BASE = "tasks/dev/pre-cadrage-entretien-client/campagne-v0"
RECONCILIATION = f"{BASE}/reconciliation-m7-2-v1"
INVENTAIRE = f"{RECONCILIATION}/inventaire-acquisitions.json"
BUDGET = f"{RECONCILIATION}/registre-budgetaire.json"
RECU = f"{RECONCILIATION}/recu-validation.json"
SOURCES = {
    "acquisition_plan": {"path": f"{BASE}/plan-acquisition-v1/plan-acquisition.json", "sha256": "7a6580a41e5e8f795f0ffe50ca0263050b78ba82ca1c052f8a140254ea403e2a"},
    "lock_manifest": {"path": f"{BASE}/verrou-campagne-v1/manifeste-empreintes.json", "sha256": "94f796d167915d8e1ce9fd471b415eff468e8afda685955c1e757d29567b3918"},
    "preparation_manifest": {"path": f"{BASE}/preparation-m7-1-v1/manifeste-empreintes.json", "sha256": "fdf63b7a7bbb6f578d9b7aa4e67dee7b13eee825500e3214b4b3fa27a1212b1d"},
    "acquisition_manifest": {"path": f"{BASE}/acquisitions-m7-1-v1/manifeste-acquisitions.json", "sha256": "fea2d4e20b5d56b9b6bfeedd8e6bc200b1ff262b6d4c1ea7642fba4e8d25946c"},
    "grok_receipt": {"path": f"{BASE}/acquisitions-m7-1-v1/receipts/sha256/c129ad5902a3ab1d730b68ddc09be099aa4efe7ff4a274a59df178bb5d4f8da5.json", "sha256": "b3a33fd3ae0cb504099dee0cc9fd86c42a2cef6bde982d12c6375e2c2697d17a", "content_address_sha256": "c129ad5902a3ab1d730b68ddc09be099aa4efe7ff4a274a59df178bb5d4f8da5"},
    "kimi_receipt": {"path": f"{BASE}/acquisitions-m7-1-v1/receipts/sha256/cc1dd10670a079980cd432c7e6df4499f67f16ed4fdc61bd11958e56b18f820c.json", "sha256": "75e8ad1d75f5a0b339f3ddd4abf63df0e600a78bc50866019b4181f152694f64", "content_address_sha256": "cc1dd10670a079980cd432c7e6df4499f67f16ed4fdc61bd11958e56b18f820c"},
}
SLOT_IDS = ["ACQ-GROK46-PRIMARY-001", "ACQ-KIMIK3-PRIMARY-001"]


class ErreurReconciliation(ValueError):
    pass


def canonique(document: object) -> bytes:
    return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"


def empreinte(contenu: bytes) -> str:
    return hashlib.sha256(contenu).hexdigest()


def ferme(valeur: object, champs: tuple[str, ...], emplacement: str) -> dict[str, object]:
    if not isinstance(valeur, dict) or set(valeur) != set(champs):
        raise ErreurReconciliation(f"schéma fermé divergent: {emplacement}")
    return valeur


def egal(observe: object, attendu: object, emplacement: str) -> None:
    if observe != attendu:
        raise ErreurReconciliation(f"valeur divergente: {emplacement}")


def chemin(racine: Path, relatif: str, emplacement: str) -> Path:
    brut = PurePosixPath(relatif)
    if brut.is_absolute() or ".." in brut.parts:
        raise ErreurReconciliation(f"référence non sûre: {emplacement}")
    cible = racine.joinpath(*brut.parts)
    try:
        cible.resolve(strict=True).relative_to(racine.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise ErreurReconciliation(f"référence inaccessible: {emplacement}") from exc
    return cible


def lire_json(racine: Path, relatif: str, emplacement: str, canonique_requis: bool) -> tuple[dict[str, object], bytes]:
    try:
        contenu = chemin(racine, relatif, emplacement).read_bytes()
        document = json.loads(contenu)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ErreurReconciliation(f"JSON illisible: {emplacement}") from exc
    if not isinstance(document, dict):
        raise ErreurReconciliation(f"objet JSON requis: {emplacement}")
    if canonique_requis and contenu != canonique(document):
        raise ErreurReconciliation(f"octets JSON non canoniques: {emplacement}")
    return document, contenu


def verifier_sources(racine: Path) -> dict[str, dict[str, object]]:
    documents: dict[str, dict[str, object]] = {}
    for nom, binding in SOURCES.items():
        contenu = chemin(racine, str(binding["path"]), f"source.{nom}").read_bytes()
        if empreinte(contenu) != binding["sha256"]:
            raise ErreurReconciliation(f"empreinte source divergente: {nom}")
        document = json.loads(contenu)
        if not isinstance(document, dict):
            raise ErreurReconciliation(f"source objet requise: {nom}")
        documents[nom] = document
    for nom in ("grok_receipt", "kimi_receipt"):
        receipt = documents[nom]
        root = ferme(receipt, ("content_address", "payload", "schema_version"), f"source.{nom}")
        address = ferme(root["content_address"], ("algorithm", "sha256"), f"source.{nom}.content_address")
        egal(address, {"algorithm": "SHA256", "sha256": SOURCES[nom]["content_address_sha256"]}, f"source.{nom}.content_address")
        if empreinte(canonique(root["payload"])) != address["sha256"]:
            raise ErreurReconciliation(f"content address divergent: {nom}")
    return documents


def verifier_bindings(valeur: object, emplacement: str) -> None:
    egal(valeur, SOURCES, emplacement)


def verifier_inventaire(document: dict[str, object], sources: dict[str, dict[str, object]]) -> None:
    root = ferme(document, ("expected", "observed", "requested", "schema_version", "source_bindings"), "inventaire")
    egal(root["schema_version"], "campaign-v0-acquisition-reconciliation-inventory/v1", "inventaire.schema_version")
    verifier_bindings(root["source_bindings"], "inventaire.source_bindings")
    egal(root["expected"], {"slot_cardinality": 2, "slot_ids": SLOT_IDS}, "inventaire.expected")
    egal(root["requested"], {"automatic_retries": 0, "fallbacks": "NONE", "planned_cli_invocations": 2, "planned_receipts": 2}, "inventaire.requested")
    observed = ferme(root["observed"], ("candidate_outputs_observed", "cli_invocations_observed", "fallbacks_performed", "grok_provider_operations_observed", "kimi_model_call", "kimi_provider_contact", "model_calls_observed", "receipts", "retries_performed", "slots", "unobserved_identity_contact_usage"), "inventaire.observed")
    manifest = sources["acquisition_manifest"]
    egal(observed["cli_invocations_observed"], manifest["actual_counts"]["cli_invocations_observed"], "inventaire.cli_invocations")
    for cle in ("candidate_outputs_observed", "fallbacks_performed", "grok_provider_operations_observed", "kimi_model_call", "kimi_provider_contact", "model_calls_observed", "receipts", "retries_performed"):
        egal(observed[cle], manifest["actual_counts"][cle], f"inventaire.{cle}")
    egal(observed["unobserved_identity_contact_usage"], {"grok_identity": "INCONNU", "grok_usage": "INCONNU", "kimi_identity": "INCONNU", "kimi_usage": "INCONNU"}, "inventaire.inconnus")
    slots = observed["slots"]
    if not isinstance(slots, list) or len(slots) != 2:
        raise ErreurReconciliation("cardinalité slot divergente")
    expected_slots = [
        {"acquisition_id": "ACQ-GROK46-PRIMARY-001", "candidate_output": "OBSERVED", "configuration_id": "grok46_xai_build_oauth", "incident": "MISSING_OBSERVATION", "model_call": "OBSERVED", "predecessor_content_address_sha256": "INCONNU", "provider_contact": "INCONNU", "provider_operation": "OBSERVED", "receipt_content_address_sha256": SOURCES["grok_receipt"]["content_address_sha256"], "receipt_file_sha256": SOURCES["grok_receipt"]["sha256"]},
        {"acquisition_id": "ACQ-KIMIK3-PRIMARY-001", "candidate_output": "INCONNU", "configuration_id": "kimi_k3_cursor_cli", "incident": "HARNESS_ERROR", "model_call": "INCONNU", "predecessor_content_address_sha256": SOURCES["grok_receipt"]["content_address_sha256"], "provider_contact": "INCONNU", "provider_operation": "INCONNU", "receipt_content_address_sha256": SOURCES["kimi_receipt"]["content_address_sha256"], "receipt_file_sha256": SOURCES["kimi_receipt"]["sha256"]},
    ]
    egal(slots, expected_slots, "inventaire.slots")
    plan_slots = sources["acquisition_plan"]["acquisition_plan"]["slots"]
    egal([slot["acquisition_id"] for slot in plan_slots], SLOT_IDS, "inventaire.plan_slots")
    operations = sources["acquisition_manifest"]["operations"]
    egal([operation["acquisition_id"] for operation in operations], SLOT_IDS, "inventaire.operations")
    egal([operation["receipt"]["content_address_sha256"] for operation in operations], [item["receipt_content_address_sha256"] for item in slots], "inventaire.reçus")
    egal(operations[1]["receipt"]["predecessor_content_sha256"], operations[0]["receipt"]["content_address_sha256"], "inventaire.chaîne")


def verifier_budget(document: dict[str, object]) -> None:
    root = ferme(document, ("expected", "observed", "requested", "schema_version", "source_bindings"), "budget")
    egal(root["schema_version"], "campaign-v0-acquisition-reconciliation-budget-register/v1", "budget.schema_version")
    verifier_bindings(root["source_bindings"], "budget.source_bindings")
    egal(root["expected"], {"additional_spend_cap_usd": 0}, "budget.expected")
    egal(root["requested"], {"additional_spend_cap_usd": 0, "new_purchase": "FORBIDDEN", "subscription_allocation": "FORBIDDEN"}, "budget.requested")
    egal(root["observed"], {"grok": {"provider_cost_usd": "INCONNU", "quota_consumption": "INCONNU"}, "kimi": {"provider_cost_usd": "INCONNU", "quota_consumption": "INCONNU"}, "total_monetary_observed_usd": "INCONNU"}, "budget.observed")


def verifier_recu(document: dict[str, object], inventaire_sha256: str, budget_sha256: str) -> str:
    root = ferme(document, ("output_bindings", "reconciliation_root", "schema_version", "source_bindings", "status"), "reçu")
    egal(root["schema_version"], "campaign-v0-reconciliation-validation-receipt/v1", "reçu.schema_version")
    egal(root["status"], "RECONCILIATION_CAMPAGNE_V0_OK", "reçu.status")
    verifier_bindings(root["source_bindings"], "reçu.source_bindings")
    outputs = {"inventory": {"path": INVENTAIRE, "sha256": inventaire_sha256}, "budget": {"path": BUDGET, "sha256": budget_sha256}}
    egal(root["output_bindings"], outputs, "reçu.output_bindings")
    reconciliation_root = ferme(root["reconciliation_root"], ("algorithm", "material", "sha256"), "reçu.reconciliation_root")
    material = {"output_bindings": outputs, "schema_version": "campaign-v0-reconciliation-root/v1", "source_bindings": SOURCES}
    egal(reconciliation_root["algorithm"], "SHA256", "reçu.reconciliation_root.algorithm")
    egal(reconciliation_root["material"], material, "reçu.reconciliation_root.material")
    derived = empreinte(canonique(material))
    egal(reconciliation_root["sha256"], derived, "reçu.reconciliation_root.sha256")
    return derived


def valider_reconciliation_campagne_v0(racine: Path = RACINE) -> dict[str, object]:
    sources = verifier_sources(racine)
    inventaire, inventaire_bytes = lire_json(racine, INVENTAIRE, "inventaire", True)
    budget, budget_bytes = lire_json(racine, BUDGET, "budget", True)
    recu, _ = lire_json(racine, RECU, "reçu", True)
    verifier_inventaire(inventaire, sources)
    verifier_budget(budget)
    root = verifier_recu(recu, empreinte(inventaire_bytes), empreinte(budget_bytes))
    return {"inventory_sha256": empreinte(inventaire_bytes), "budget_sha256": empreinte(budget_bytes), "reconciliation_root_sha256": root, "status": "RECONCILIATION_CAMPAGNE_V0_OK"}


def main() -> int:
    try:
        print(json.dumps(valider_reconciliation_campagne_v0(), ensure_ascii=False, sort_keys=True))
    except (ErreurReconciliation, KeyError, TypeError) as exc:
        print(f"HOLD_M7_2_RECONCILIATION: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
