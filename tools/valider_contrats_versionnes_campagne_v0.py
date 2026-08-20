from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys


RACINE = Path(__file__).resolve().parents[1]
MATRICE_PAR_DEFAUT = (
    RACINE
    / "tasks/dev/pre-cadrage-entretien-client/campagne-v0/contrats-versionnes-v1/contrats-versionnes.json"
)
EMPREINTE_MATRICE_ATTENDUE = (
    "cf4c2784039edb5cb2be43911d7f3fbc52ff66612c4a4436094602a3dd8d1fcd"
)
PROTOCOLE_HISTORIQUE = "benchmark-lab-x/protocol/v2"

AUTORITES_ATTENDUES = {
    "recommended_bundle": {
        "author": "ayoahha",
        "comment_id": 5353285466,
        "node_id": "IC_kwDOTswBxM8AAAABPxSnWg",
        "url": "https://github.com/ayoahha/benchmark-lab-x/issues/65#issuecomment-5353285466",
        "created_at": "2026-08-20T08:19:01Z",
        "updated_at": "2026-08-20T08:19:01Z",
        "body_sha256": "f87fc2454f8950326d16d4b2cf8d299081b96cfac247358d1d2846d00b739fa3",
    },
    "acceptance": {
        "author": "ayoahha",
        "comment_id": 5353298745,
        "node_id": "IC_kwDOTswBxM8AAAABPxTbOQ",
        "url": "https://github.com/ayoahha/benchmark-lab-x/issues/65#issuecomment-5353298745",
        "created_at": "2026-08-20T08:20:14Z",
        "updated_at": "2026-08-20T08:20:14Z",
        "authority_value": "M6_2_OWNER_DECISION = ACCEPT_RECOMMENDED_BUNDLE",
        "body_sha256": "aae82c847b5ba7af13e4e22ed5a0931da3c9d1dea5239812491dffd32d4ab149",
    },
}

CONTRATS_ACTIFS_ATTENDUS = {
    "architecture": {
        "path": "docs/ARD.md",
        "sha256": "f452dbfeeccbf8713be541a466066cc5ba1cd48be0da276181c09b6432f12db7",
    },
    "product_requirements": {
        "path": "docs/PRD.md",
        "sha256": "0aaab457eaf3202025c33754b7fd87f41aea858c1108981fbd4c0ccee1dc0126",
    },
    "universal_rules": {
        "path": "docs/RULES.md",
        "sha256": "f1edbdc9f8914aca41beef6221418704bff5db5f913688a5cc3281df71921938",
    },
    "campaign_authorities": {
        "path": "tasks/dev/pre-cadrage-entretien-client/campagne-v0/autorites-v1/autorites.json",
        "sha256": "d551362f35a9e650d78330e79b757bb3e63c892b92fcaa08b48f86599d951d82",
    },
    "approved_manifest": {
        "path": "tasks/dev/pre-cadrage-entretien-client/manifeste-paquet.json",
        "sha256": "8030128d159e4203483b19f0e37692a53f01baecc38fbccaa321541c23e71a10",
    },
}

MATRICE_ATTENDUE = [
    {
        "category": "product",
        "dimension": "product_version",
        "value": "V0",
        "contract_source_ids": [
            "architecture",
            "campaign_authorities",
            "approved_manifest",
        ],
        "authority_source_ids": ["recommended_bundle", "acceptance"],
    },
    {
        "category": "artifact",
        "dimension": "artifact_schema",
        "value": "V0",
        "contract_source_ids": ["architecture", "approved_manifest"],
        "authority_source_ids": ["recommended_bundle", "acceptance"],
    },
    {
        "category": "protocol",
        "dimension": "protocol_version",
        "value": "campaign-v0-measurement-protocol/v1",
        "contract_source_ids": [
            "architecture",
            "product_requirements",
            "universal_rules",
        ],
        "authority_source_ids": ["recommended_bundle", "acceptance"],
    },
    {
        "category": "receipt",
        "dimension": "receipt_schema",
        "value": "campaign-v0-acquisition-receipt/v1",
        "contract_source_ids": [
            "architecture",
            "product_requirements",
            "universal_rules",
        ],
        "authority_source_ids": ["recommended_bundle", "acceptance"],
    },
    {
        "category": "decision_policy",
        "dimension": "decision_policy_version",
        "value": "campaign-v0-decision-policy/v1",
        "contract_source_ids": [
            "architecture",
            "product_requirements",
            "universal_rules",
            "campaign_authorities",
        ],
        "authority_source_ids": ["recommended_bundle", "acceptance"],
    },
    {
        "category": "view",
        "dimension": "view_schema",
        "value": "campaign-v0-decision-view/v1",
        "contract_source_ids": [
            "architecture",
            "product_requirements",
            "universal_rules",
        ],
        "authority_source_ids": ["recommended_bundle", "acceptance"],
    },
]


class ErreurContratsVersionnes(ValueError):
    pass


def _sha256(contenu: bytes) -> str:
    return hashlib.sha256(contenu).hexdigest()


def _exiger_champs(
    valeur: object, champs: tuple[str, ...], emplacement: str
) -> dict[str, object]:
    if not isinstance(valeur, dict) or set(valeur) != set(champs):
        raise ErreurContratsVersionnes(f"schéma fermé divergent: {emplacement}")
    return valeur


def _exiger_egal(observe: object, attendu: object, emplacement: str) -> None:
    if observe != attendu:
        raise ErreurContratsVersionnes(f"valeur divergente: {emplacement}")


def _valider_reference_fichier(reference: dict[str, object], racine: Path) -> None:
    chemin_brut = reference["path"]
    empreinte = reference["sha256"]
    if not isinstance(chemin_brut, str) or not isinstance(empreinte, str):
        raise ErreurContratsVersionnes("référence de contrat non textuelle")
    chemin_relatif = PurePosixPath(chemin_brut)
    if chemin_relatif.is_absolute() or ".." in chemin_relatif.parts:
        raise ErreurContratsVersionnes(
            f"référence de contrat non sûre: {chemin_brut}"
        )
    chemin = racine.joinpath(*chemin_relatif.parts)
    try:
        chemin.resolve(strict=True).relative_to(racine.resolve(strict=True))
        contenu = chemin.read_bytes()
    except (OSError, ValueError) as exc:
        raise ErreurContratsVersionnes(
            f"référence de contrat inaccessible: {chemin_brut}"
        ) from exc
    if _sha256(contenu) != empreinte:
        raise ErreurContratsVersionnes(
            f"empreinte de contrat divergente: {chemin_brut}"
        )


def valider_contrats_versionnes_campagne_v0(
    matrice: Path = MATRICE_PAR_DEFAUT, racine: Path = RACINE
) -> dict[str, object]:
    try:
        contenu = matrice.read_bytes()
        document = json.loads(contenu)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ErreurContratsVersionnes("matrice illisible ou JSON invalide") from exc

    racine_document = _exiger_champs(
        document,
        (
            "schema_version",
            "scope",
            "hash_conventions",
            "owner_authorities",
            "active_contracts",
            "historical_contract_exclusion",
            "version_matrix",
        ),
        "racine",
    )
    _exiger_egal(
        racine_document["schema_version"],
        "campaign-v0-version-contracts/v1",
        "schema_version",
    )
    _exiger_egal(
        _exiger_champs(
            racine_document["scope"],
            ("issue_number", "issue_url", "parent_issue_number", "parent_issue_url"),
            "scope",
        ),
        {
            "issue_number": 65,
            "issue_url": "https://github.com/ayoahha/benchmark-lab-x/issues/65",
            "parent_issue_number": 19,
            "parent_issue_url": "https://github.com/ayoahha/benchmark-lab-x/issues/19",
        },
        "scope",
    )
    _exiger_egal(
        _exiger_champs(
            racine_document["hash_conventions"],
            ("file_sha256", "github_body_sha256"),
            "hash_conventions",
        ),
        {
            "file_sha256": "sha256 of exact file bytes",
            "github_body_sha256": (
                "sha256 of the exact UTF-8 body returned by the GitHub API, "
                "without an added newline"
            ),
        },
        "hash_conventions",
    )

    autorites = _exiger_champs(
        racine_document["owner_authorities"],
        tuple(AUTORITES_ATTENDUES),
        "owner_authorities",
    )
    for identifiant, attendu in AUTORITES_ATTENDUES.items():
        citation = _exiger_champs(
            autorites[identifiant], tuple(attendu), f"owner_authorities.{identifiant}"
        )
        _exiger_egal(citation, attendu, f"owner_authorities.{identifiant}")

    contrats = _exiger_champs(
        racine_document["active_contracts"],
        tuple(CONTRATS_ACTIFS_ATTENDUS),
        "active_contracts",
    )
    for identifiant, attendu in CONTRATS_ACTIFS_ATTENDUS.items():
        reference = _exiger_champs(
            contrats[identifiant], ("path", "sha256"), f"active_contracts.{identifiant}"
        )
        _exiger_egal(reference, attendu, f"active_contracts.{identifiant}")
        _valider_reference_fichier(reference, racine)

    exclusion = _exiger_champs(
        racine_document["historical_contract_exclusion"],
        (
            "inheritance",
            "protocol_version",
            "protocol_implementation",
            "protocol_tests",
            "derived_schema_inheritance",
        ),
        "historical_contract_exclusion",
    )
    _exiger_egal(
        exclusion,
        {
            "inheritance": "FORBIDDEN",
            "protocol_version": PROTOCOLE_HISTORIQUE,
            "protocol_implementation": "tools/protocole_v2.py",
            "protocol_tests": "tests/test_protocol_v2.py",
            "derived_schema_inheritance": "FORBIDDEN",
        },
        "historical_contract_exclusion",
    )

    matrice_versions = racine_document["version_matrix"]
    if not isinstance(matrice_versions, list) or len(matrice_versions) != len(
        MATRICE_ATTENDUE
    ):
        raise ErreurContratsVersionnes("matrice de versions divergente")
    for index, attendu in enumerate(MATRICE_ATTENDUE):
        entree = _exiger_champs(
            matrice_versions[index], tuple(attendu), f"version_matrix[{index}]"
        )
        _exiger_egal(entree, attendu, f"version_matrix[{index}]")
        if entree["value"] == PROTOCOLE_HISTORIQUE:
            raise ErreurContratsVersionnes(
                f"protocole historique injecté: version_matrix[{index}]"
            )

    empreinte_matrice = _sha256(contenu)
    if empreinte_matrice != EMPREINTE_MATRICE_ATTENDUE:
        raise ErreurContratsVersionnes("matrice ou citations divergentes")
    return {
        "status": "CONTRATS_VERSIONNES_CAMPAGNE_V0_OK",
        "schema_version": racine_document["schema_version"],
        "matrix_sha256": empreinte_matrice,
        "dimension_count": len(matrice_versions),
        "active_contract_count": len(contrats),
        "historical_protocol_inheritance": exclusion["inheritance"],
    }


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser()
    analyseur.add_argument("matrice", nargs="?", type=Path, default=MATRICE_PAR_DEFAUT)
    arguments = analyseur.parse_args(argv)
    try:
        recu = valider_contrats_versionnes_campagne_v0(arguments.matrice)
    except ErreurContratsVersionnes as exc:
        print(f"HOLD_CAMPAIGN_LOCK: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(recu, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
