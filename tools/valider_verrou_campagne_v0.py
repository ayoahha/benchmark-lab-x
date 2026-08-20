from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
from typing import Callable

RACINE_IMPORT = Path(__file__).resolve().parents[1]
if str(RACINE_IMPORT) not in sys.path:
    sys.path.insert(0, str(RACINE_IMPORT))

from tools.valider_autorites_campagne_v0 import valider_autorites_campagne_v0
from tools.valider_contrats_versionnes_campagne_v0 import (
    valider_contrats_versionnes_campagne_v0,
)
from tools.valider_panel_identites_campagne_v0 import (
    valider_panel_identites_campagne_v0,
)
from tools.valider_plan_acquisition_campagne_v0 import (
    valider_plan_acquisition_campagne_v0,
)
from tools.valider_politique_decision_campagne_v0 import (
    valider_politique_decision_campagne_v0,
)


RACINE = Path(__file__).resolve().parents[1]
DOSSIER_VERROU = (
    RACINE
    / "tasks/dev/pre-cadrage-entretien-client/campagne-v0/"
    "verrou-campagne-v1"
)
VERROU_PAR_DEFAUT = DOSSIER_VERROU / "verrou.json"
MANIFESTE_PAR_DEFAUT = DOSSIER_VERROU / "manifeste-empreintes.json"
RECU_PAR_DEFAUT = DOSSIER_VERROU / "recu-validation.json"
STORE_PRIVE_PAR_DEFAUT = Path(
    "/Users/ayo/Documents/benchmark-lab-x-private/"
    "campaign-v0-m6-6/raw/sha256"
)

CHEMIN_VERROU = (
    "tasks/dev/pre-cadrage-entretien-client/campagne-v0/"
    "verrou-campagne-v1/verrou.json"
)
CHEMIN_MANIFESTE = (
    "tasks/dev/pre-cadrage-entretien-client/campagne-v0/"
    "verrou-campagne-v1/manifeste-empreintes.json"
)
CHEMIN_RECU = (
    "tasks/dev/pre-cadrage-entretien-client/campagne-v0/"
    "verrou-campagne-v1/recu-validation.json"
)
CHEMIN_VALIDATOR = "tools/valider_verrou_campagne_v0.py"

PREDECESSEURS = [
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

VALIDATEURS_PREDECESSEURS = [
    {
        "milestone": "M6.1",
        "path": "tools/valider_autorites_campagne_v0.py",
        "sha256": "e84d31f5fdb7b1f8c5b1819b2d98efca330a0b1fc474b9ad53c6e5c939698f0f",
    },
    {
        "milestone": "M6.2",
        "path": "tools/valider_contrats_versionnes_campagne_v0.py",
        "sha256": "d9c79559be10e7e169dfe7e5eb721d3039e360f206e0197c3423214fd369cbad",
    },
    {
        "milestone": "M6.3",
        "path": "tools/valider_panel_identites_campagne_v0.py",
        "sha256": "65a3188b0ae680e4fababde93e16dc45c721f0492b0af5990aea2a8996540511",
    },
    {
        "milestone": "M6.4",
        "path": "tools/valider_plan_acquisition_campagne_v0.py",
        "sha256": "76e36658e454aa78c83e5a854d16267274e9a5fd9acc6cd6353025af13726a6d",
    },
    {
        "milestone": "M6.5",
        "path": "tools/valider_politique_decision_campagne_v0.py",
        "sha256": "0a6225ed82d7bb583d514320a8aad51ba223e295a9e5b57dcda26d8acaa77da1",
    },
]

FERMETURE_TRANSITIVE = [
    {"path": "docs/ARD.md", "sha256": "f452dbfeeccbf8713be541a466066cc5ba1cd48be0da276181c09b6432f12db7"},
    {"path": "docs/PRD.md", "sha256": "0aaab457eaf3202025c33754b7fd87f41aea858c1108981fbd4c0ccee1dc0126"},
    {"path": "docs/RULES.md", "sha256": "f1edbdc9f8914aca41beef6221418704bff5db5f913688a5cc3281df71921938"},
    {"path": "tasks/dev/pre-cadrage-entretien-client/brief-proprietaire.md", "sha256": "3e6e2b2edfa0e5b39f103a251707eb3f3f5f017f641aa53c55d64a6d4434eb11"},
    {"path": "tasks/dev/pre-cadrage-entretien-client/manifeste-paquet.json", "sha256": "8030128d159e4203483b19f0e37692a53f01baecc38fbccaa321541c23e71a10"},
    {"path": "tasks/dev/pre-cadrage-entretien-client/preuves-u025/p3-v1/adapters/manual-acquire.py", "sha256": "e8d67f5bf6aeff40eb4c3fac569209c589ff0a366e964914a50ab28ab25faefa"},
    {"path": "tasks/dev/pre-cadrage-entretien-client/preuves-u025/p3-v1/adapters/shared_acquisition.py", "sha256": "47fb1ca6a777215f0564c847cae9cbe7bb78313f83c806de3173d30439532da3"},
    {"path": "tasks/dev/pre-cadrage-entretien-client/preuves-u025/p3-v1/configs/manual/procedure.md", "sha256": "12c20bd794e16d7f3e15ed1e93db9571ffbeea6abac4eac8b073fc37001a1baa"},
    {"path": "tasks/dev/pre-cadrage-entretien-client/registre-verite.md", "sha256": "6a8e957955460bfde90d88f05c2d5263f799d7ad7a9b98d78aa774ea1459d22c"},
    {"path": "tasks/dev/pre-cadrage-entretien-client/stimulus.md", "sha256": "20f0be450640704b0c467eee57ca2ea58a4d629e63eba3efccbc6f68440e07e4"},
    {"path": "tasks/dev/pre-cadrage-entretien-client/temoins-qualification.md", "sha256": "8a419c5950127c8187119545237f32b0ecb9b0062116afc3421e0c96a00bd011"},
]

ENGAGEMENTS_PRIVES_REELS = [
    {
        "kind": "RANDOM_SALT_32_BYTES",
        "mode": "0600",
        "sha256": "8a064da1261943781538d288d4d838835c82e78b5101e1bca38d9d09f8a2077c",
        "size": 32,
    },
    {
        "kind": "BLIND_ORDER_MAPPING",
        "mode": "0600",
        "sha256": "19dd8e4371b216d7549b4f9622b9db72f13615b5b3a21c0e7bdb7bf57564e912",
        "size": 476,
    },
]

AUTORITES_M6_6 = {
    "continuation_v2": {
        "author": "ayoahha",
        "author_association": "OWNER",
        "authority_value": "M6_6_LOCK_V2_CONTINUATION_GO = GRANTED",
        "body_sha256": "35100c1a97e106c17b512bd051a740a8dee17a0d6bc3f38acd08270880663791",
        "body_sha256_with_one_lf": "45222302809dada1fb61457df66af91bbab502f1b68a07f7012c9148e68e2fbb",
        "comment_id": 5356663937,
        "created_at": "2026-08-20T13:38:23Z",
        "node_id": "IC_kwDOTswBxM8AAAABP0g0gQ",
        "updated_at": "2026-08-20T13:38:23Z",
        "url": "https://github.com/ayoahha/benchmark-lab-x/issues/69#issuecomment-5356663937",
    },
    "materialization_v1": {
        "author": "ayoahha",
        "author_association": "OWNER",
        "authority_value": "M6_6_LOCK_MATERIALIZATION_GO = GRANTED",
        "body_sha256": "e08958e24f8aed4d072a5b41895d6a161068e993fea99ce854bfeedbead51e7a",
        "body_sha256_with_one_lf": "01ca04b6c4c6d428d861a78a5b8ef204a3b054c84a7b0918daa85f5a29d57196",
        "comment_id": 5356397378,
        "created_at": "2026-08-20T13:15:26Z",
        "node_id": "IC_kwDOTswBxM8AAAABP0QjQg",
        "updated_at": "2026-08-20T13:15:26Z",
        "url": "https://github.com/ayoahha/benchmark-lab-x/issues/69#issuecomment-5356397378",
    },
}

METADATA_MANIFESTE = {
    "issue_number": 69,
    "private_store_uri": (
        "file:///Users/ayo/Documents/benchmark-lab-x-private/"
        "campaign-v0-m6-6/raw/sha256/"
    ),
    "root_definition": "SHA256_EXACT_CANONICAL_MANIFEST_BYTES",
}

AUTORISATIONS = {
    "acquisition": "NOT_GRANTED",
    "campaign_execution": "NOT_GRANTED",
    "canary": "NOT_GRANTED",
    "m6_7": "NOT_GRANTED",
    "preparation": "NOT_GRANTED_PENDING_EXACT_ROOT_OWNER_GO",
    "provider_operation": "NOT_GRANTED",
    "quota_consumption": "NOT_GRANTED",
    "retry": "NOT_GRANTED",
    "spend": "NOT_GRANTED",
}

ACQUISITIONS = {"ACQ-GROK46-PRIMARY-001", "ACQ-KIMIK3-PRIMARY-001"}

ETATS_VALEURS = {
    "DECIDED": "PRESERVED_AS_DECIDED_NEVER_PROMOTED_TO_OBSERVED",
    "EXPECTED": "PRESERVED_AS_EXPECTED_NEVER_PROMOTED_TO_OBSERVED",
    "INCONNU": "PRESERVED_WITHOUT_IMPUTATION",
    "OBSERVED": "ACTUALLY_SERVED_OR_MEASURED_ONLY",
    "REQUESTED": "PRESERVED_AS_REQUESTED_NEVER_PROMOTED_TO_OBSERVED",
    "promotion_to_observed_without_acquisition_evidence": "FORBIDDEN",
}


class ErreurVerrouCampagne(ValueError):
    pass


def _sha256(contenu: bytes) -> str:
    return hashlib.sha256(contenu).hexdigest()


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
        raise ErreurVerrouCampagne("valeur JSON non canonique") from exc


def _charger_json_canonique(chemin: Path, nom: str) -> tuple[object, bytes]:
    def paires(elements: list[tuple[str, object]]) -> dict[str, object]:
        resultat: dict[str, object] = {}
        for cle, valeur in elements:
            if cle in resultat:
                raise ErreurVerrouCampagne(f"clé JSON dupliquée: {nom}")
            resultat[cle] = valeur
        return resultat

    def interdit(_: str) -> object:
        raise ErreurVerrouCampagne(f"float ou constante interdit: {nom}")

    try:
        metadata = chemin.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise ErreurVerrouCampagne(f"fichier régulier non-symlink requis: {nom}")
        contenu = chemin.read_bytes()
        document = json.loads(
            contenu.decode("utf-8"),
            object_pairs_hook=paires,
            parse_float=interdit,
            parse_constant=interdit,
        )
    except ErreurVerrouCampagne:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ErreurVerrouCampagne(f"JSON inaccessible ou invalide: {nom}") from exc
    if contenu != _canonical(document):
        raise ErreurVerrouCampagne(f"JSON non canonique: {nom}")
    return document, contenu


def _ferme(valeur: object, champs: tuple[str, ...], nom: str) -> dict[str, object]:
    if not isinstance(valeur, dict) or set(valeur) != set(champs):
        raise ErreurVerrouCampagne(f"schéma fermé divergent: {nom}")
    return valeur


def _egal(observe: object, attendu: object, nom: str) -> None:
    def strictement_egal(gauche: object, droite: object) -> bool:
        if type(gauche) is not type(droite):
            return False
        if isinstance(gauche, dict) and isinstance(droite, dict):
            return set(gauche) == set(droite) and all(
                strictement_egal(gauche[cle], droite[cle]) for cle in gauche
            )
        if isinstance(gauche, list) and isinstance(droite, list):
            return len(gauche) == len(droite) and all(
                strictement_egal(element_gauche, element_droite)
                for element_gauche, element_droite in zip(
                    gauche, droite, strict=True
                )
            )
        return gauche == droite

    if not strictement_egal(observe, attendu):
        raise ErreurVerrouCampagne(f"valeur divergente: {nom}")


def _chemin_public(racine: Path, relatif_brut: object, nom: str) -> Path:
    if not isinstance(relatif_brut, str):
        raise ErreurVerrouCampagne(f"chemin non textuel: {nom}")
    relatif = PurePosixPath(relatif_brut)
    if relatif.is_absolute() or not relatif.parts or ".." in relatif.parts:
        raise ErreurVerrouCampagne(f"chemin non sûr: {nom}")
    chemin = racine.joinpath(*relatif.parts)
    courant = racine
    try:
        for partie in relatif.parts:
            courant = courant / partie
            if stat.S_ISLNK(courant.lstat().st_mode):
                raise ErreurVerrouCampagne(f"lien symbolique interdit: {nom}")
        if not stat.S_ISREG(chemin.lstat().st_mode):
            raise ErreurVerrouCampagne(f"fichier régulier requis: {nom}")
    except OSError as exc:
        raise ErreurVerrouCampagne(f"chemin inaccessible: {nom}") from exc
    return chemin


def _verifier_references(
    references: object, attendues: list[dict[str, object]], racine: Path, nom: str
) -> None:
    _egal(references, attendues, nom)
    for index, reference in enumerate(attendues):
        chemin = _chemin_public(racine, reference["path"], f"{nom}.{index}")
        if _sha256(chemin.read_bytes()) != reference["sha256"]:
            raise ErreurVerrouCampagne(f"empreinte divergente: {nom}.{index}")


def _verifier_engagements(engagements: object) -> list[dict[str, object]]:
    if not isinstance(engagements, list) or len(engagements) != 2:
        raise ErreurVerrouCampagne("deux engagements privés requis")
    resultat: list[dict[str, object]] = []
    for index, engagement in enumerate(engagements):
        item = _ferme(
            engagement,
            ("kind", "mode", "sha256", "size"),
            f"engagements privés.{index}",
        )
        if (
            item["kind"] not in {"RANDOM_SALT_32_BYTES", "BLIND_ORDER_MAPPING"}
            or item["mode"] != "0600"
            or not isinstance(item["sha256"], str)
            or len(item["sha256"]) != 64
            or any(caractere not in "0123456789abcdef" for caractere in item["sha256"])
            or type(item["size"]) is not int
            or item["size"] <= 0
        ):
            raise ErreurVerrouCampagne("engagement privé invalide")
        resultat.append(item)
    if {item["kind"] for item in resultat} != {
        "RANDOM_SALT_32_BYTES",
        "BLIND_ORDER_MAPPING",
    }:
        raise ErreurVerrouCampagne("types privés divergents")
    sel = next(item for item in resultat if item["kind"] == "RANDOM_SALT_32_BYTES")
    if sel["size"] != 32:
        raise ErreurVerrouCampagne("taille du sel privé divergente")
    if len({item["sha256"] for item in resultat}) != 2:
        raise ErreurVerrouCampagne("engagement privé dupliqué")
    return resultat


def _valider_ordre_prive(contenu: bytes, sel: bytes) -> None:
    def paires(elements: list[tuple[str, object]]) -> dict[str, object]:
        resultat: dict[str, object] = {}
        for cle, valeur in elements:
            if cle in resultat:
                raise ErreurVerrouCampagne("clé JSON dupliquée: manifeste privé")
            resultat[cle] = valeur
        return resultat

    def interdit(_: str) -> object:
        raise ErreurVerrouCampagne("float interdit: manifeste privé")

    try:
        document = json.loads(
            contenu.decode("utf-8"),
            object_pairs_hook=paires,
            parse_float=interdit,
            parse_constant=interdit,
        )
    except ErreurVerrouCampagne:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ErreurVerrouCampagne("manifeste privé JSON invalide") from exc
    if contenu != _canonical(document):
        raise ErreurVerrouCampagne("manifeste privé non canonique")
    ordre = _ferme(
        document,
        ("algorithm", "campaign_id", "cardinality", "entries", "schema_version"),
        "manifeste privé",
    )
    if not isinstance(ordre["algorithm"], str) or not ordre["algorithm"]:
        raise ErreurVerrouCampagne("algorithme privé invalide")
    if not isinstance(ordre["schema_version"], str) or not ordre["schema_version"]:
        raise ErreurVerrouCampagne("version privée invalide")
    campagne = ordre["campaign_id"]
    cardinalite = ordre["cardinality"]
    entrees = ordre["entries"]
    if not isinstance(campagne, str) or not campagne:
        raise ErreurVerrouCampagne("identité campagne privée invalide")
    if type(cardinalite) is not int or not isinstance(entrees, list):
        raise ErreurVerrouCampagne("cardinalité privée invalide")
    if cardinalite != len(entrees) or cardinalite != len(ACQUISITIONS):
        raise ErreurVerrouCampagne("cardinalité privée divergente")
    normalisees: list[dict[str, object]] = []
    for index, entree in enumerate(entrees):
        item = _ferme(
            entree,
            ("acquisition_id", "item_id", "position"),
            f"manifeste privé.entries.{index}",
        )
        if (
            not isinstance(item["acquisition_id"], str)
            or not isinstance(item["item_id"], str)
            or type(item["position"]) is not int
        ):
            raise ErreurVerrouCampagne("entrée privée mal typée")
        normalisees.append(item)
    if {item["acquisition_id"] for item in normalisees} != ACQUISITIONS:
        raise ErreurVerrouCampagne("mapping privé hors ensemble approuvé")
    positions = [item["position"] for item in normalisees]
    items = [item["item_id"] for item in normalisees]
    if positions != list(range(1, cardinalite + 1)):
        raise ErreurVerrouCampagne("positions privées non contiguës ou désordonnées")
    if len(set(items)) != cardinalite:
        raise ErreurVerrouCampagne("item_id privé dupliqué")
    for item in normalisees:
        if item["item_id"] != f"ITEM-{item['position']:03d}":
            raise ErreurVerrouCampagne("item_id privé incohérent")
    attendues = sorted(
        ACQUISITIONS,
        key=lambda acquisition: (
            hashlib.sha256(
                sel + campagne.encode("utf-8") + acquisition.encode("utf-8")
            ).digest(),
            acquisition.encode("utf-8"),
        ),
    )
    if [item["acquisition_id"] for item in normalisees] != attendues:
        raise ErreurVerrouCampagne("ordre privé divergent")


def _verifier_store_prive(
    store: Path, engagements: list[dict[str, object]]
) -> None:
    try:
        store_stat = store.lstat()
    except OSError as exc:
        raise ErreurVerrouCampagne("store privé inaccessible") from exc
    if stat.S_ISLNK(store_stat.st_mode) or not stat.S_ISDIR(store_stat.st_mode):
        raise ErreurVerrouCampagne("store privé non régulier")
    if stat.S_IMODE(store_stat.st_mode) != 0o700:
        raise ErreurVerrouCampagne("mode du store privé divergent")
    attendus = {engagement["sha256"] for engagement in engagements}
    try:
        observes = {entree.name for entree in os.scandir(store)}
    except OSError as exc:
        raise ErreurVerrouCampagne("store privé illisible") from exc
    if observes != attendus or len(engagements) != 2:
        raise ErreurVerrouCampagne("contenu du store privé divergent")
    contenus: dict[str, bytes] = {}
    for engagement in engagements:
        chemin = store / str(engagement["sha256"])
        try:
            metadata = chemin.lstat()
            contenu = chemin.read_bytes()
        except OSError as exc:
            raise ErreurVerrouCampagne("objet privé inaccessible") from exc
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise ErreurVerrouCampagne("objet privé non régulier")
        if stat.S_IMODE(metadata.st_mode) != int(str(engagement["mode"]), 8):
            raise ErreurVerrouCampagne("mode objet privé divergent")
        if len(contenu) != engagement["size"] or _sha256(contenu) != engagement["sha256"]:
            raise ErreurVerrouCampagne("engagement objet privé divergent")
        contenus[str(engagement["kind"])] = contenu
    sel = contenus.get("RANDOM_SALT_32_BYTES")
    ordre = contenus.get("BLIND_ORDER_MAPPING")
    if sel is None or ordre is None or len(sel) != 32:
        raise ErreurVerrouCampagne("types privés divergents")
    _valider_ordre_prive(ordre, sel)


def _resultats_validateurs(racine: Path) -> list[dict[str, str]]:
    appels: list[tuple[str, Callable[..., dict[str, object]], str, Path]] = [
        ("M6.1", valider_autorites_campagne_v0, "AUTORITES_CAMPAGNE_V0_OK", racine / PREDECESSEURS[0]["path"]),
        ("M6.2", valider_contrats_versionnes_campagne_v0, "CONTRATS_VERSIONNES_CAMPAGNE_V0_OK", racine / PREDECESSEURS[1]["path"]),
        ("M6.3", valider_panel_identites_campagne_v0, "PANEL_IDENTITES_CAMPAGNE_V0_OK", racine / PREDECESSEURS[2]["path"]),
        ("M6.4", valider_plan_acquisition_campagne_v0, "PLAN_ACQUISITION_CAMPAGNE_V0_OK", racine / PREDECESSEURS[3]["path"]),
        ("M6.5", valider_politique_decision_campagne_v0, "POLITIQUE_DECISION_CAMPAGNE_V0_OK", racine / PREDECESSEURS[4]["path"]),
    ]
    resultats: list[dict[str, str]] = []
    for (milestone, appel, statut, chemin), validateur in zip(
        appels, VALIDATEURS_PREDECESSEURS, strict=True
    ):
        recu = appel(chemin, racine)
        if recu.get("status") != statut:
            raise ErreurVerrouCampagne(f"validateur prédécesseur rouge: {milestone}")
        resultats.append(
            {
                "artifact_sha256": str(PREDECESSEURS[len(resultats)]["sha256"]),
                "milestone": milestone,
                "status": statut,
                "validator_sha256": str(validateur["sha256"]),
            }
        )
    return resultats


def _verifier_verrou(
    document: object, engagements: list[dict[str, object]]
) -> dict[str, object]:
    verrou = _ferme(
        document,
        (
            "authorizations",
            "blind_order_commitment",
            "execution_evidence",
            "hash_conventions",
            "lock_definition",
            "owner_authorities",
            "predecessor_artifacts",
            "preservation_invariants",
            "private_commitments",
            "schema_version",
            "scope",
            "value_state_contract",
        ),
        "verrou",
    )
    _egal(verrou["schema_version"], "campaign-v0-campaign-lock/v1", "verrou.schema_version")
    _egal(
        verrou["scope"],
        {
            "git_base": "b04d60549587442fcd739956d7dae7b551eeb54b",
            "issue_number": 69,
            "issue_url": "https://github.com/ayoahha/benchmark-lab-x/issues/69",
            "parent_issue_number": 19,
            "parent_issue_url": "https://github.com/ayoahha/benchmark-lab-x/issues/19",
            "product_version": "V0",
        },
        "verrou.scope",
    )
    _egal(
        verrou["hash_conventions"],
        {
            "file_sha256": "sha256 of exact file bytes",
            "manifest_root": "sha256 of exact canonical manifest bytes",
        },
        "verrou.hash_conventions",
    )
    _egal(
        verrou["owner_authorities"],
        AUTORITES_M6_6,
        "verrou.owner_authorities",
    )
    _egal(verrou["predecessor_artifacts"], PREDECESSEURS, "verrou.predecessor_artifacts")
    _egal(
        verrou["lock_definition"],
        {
            "artifact_set": "CLOSED_M6_1_THROUGH_M6_5_PLUS_M6_6_LOCK",
            "manifest_path": CHEMIN_MANIFESTE,
            "root_algorithm": "SHA256_EXACT_CANONICAL_MANIFEST_BYTES",
        },
        "verrou.lock_definition",
    )
    _egal(
        verrou["preservation_invariants"],
        {
            "m6_2_contract_ids": "DECLARED_IDS_ONLY_NOT_IMPLEMENTATIONS",
            "m6_3_manual_harness": "DECLARED_IDENTITY_ONLY",
            "m6_3_panel_configuration_count": 2,
            "m6_3_shared_core_adapter": "DECLARED_IDENTITY_ONLY",
            "m6_4_decision_contract_sha256": "ea07f5691249f648a939d1ca6bac26eaf38cea7bd2f7e3593add17a55184c704",
            "m6_4_literal_disposition": "APPROVED_OPAQUE_LITERAL_NOT_CONTENT_REFERENCE_NO_LOCAL_PREIMAGE_DECLARED",
            "m6_4_panel_slots": 2,
            "m6_4_retries_and_fallbacks": "ZERO_RETRY_ZERO_FALLBACK",
            "m6_5_owner_decision": "M6_5_OWNER_DECISION = ACCEPT_RECOMMENDED_BUNDLE",
        },
        "verrou.preservation_invariants",
    )
    _egal(
        verrou["blind_order_commitment"],
        {
            "cardinality": 2,
            "identifier_disclosure": "OPAQUE_ITEM_IDS_ONLY",
            "mapping_disclosure": "AFTER_ALL_HUMAN_VERDICTS_FROZEN",
            "method": "SHA256_SALT_CAMPAIGN_ID_ACQUISITION_ID_SORT",
            "private_material_in_public_lock": "FORBIDDEN",
        },
        "verrou.blind_order_commitment",
    )
    _egal(verrou["value_state_contract"], ETATS_VALEURS, "verrou.value_state_contract")
    _egal(verrou["private_commitments"], engagements, "verrou.private_commitments")
    _egal(verrou["authorizations"], AUTORISATIONS, "verrou.authorizations")
    _egal(
        verrou["execution_evidence"],
        {
            "acquisitions_performed": 0,
            "campaign_runs": 0,
            "canaries_performed": 0,
            "preparation_performed": False,
            "provider_contacted": False,
            "provider_operations": 0,
            "quota_consumed": False,
            "retries_performed": 0,
            "spend_incurred": False,
        },
        "verrou.execution_evidence",
    )
    if "manifest_root" in verrou["lock_definition"]:
        raise ErreurVerrouCampagne("racine interdite dans le verrou")
    return verrou


def _verifier_invariants_predecesseurs(racine: Path) -> None:
    contrats = json.loads((racine / PREDECESSEURS[1]["path"]).read_bytes())
    _egal(
        [entree["value"] for entree in contrats["version_matrix"]],
        [
            "V0",
            "V0",
            "campaign-v0-measurement-protocol/v1",
            "campaign-v0-acquisition-receipt/v1",
            "campaign-v0-decision-policy/v1",
            "campaign-v0-decision-view/v1",
        ],
        "M6.2.identifiants déclarés",
    )

    panel = json.loads((racine / PREDECESSEURS[2]["path"]).read_bytes())
    _egal(panel["panel"]["cardinality"], 2, "M6.3.cardinalité")
    _egal(len(panel["panel"]["configurations"]), 2, "M6.3.configurations")
    _egal(
        panel["shared_identity"]["manual_harness"]["implementation_state"],
        "DECLARED_IDENTITY_ONLY",
        "M6.3.manual_harness",
    )
    _egal(
        panel["shared_identity"]["shared_core_adapter"]["implementation_state"],
        "DECLARED_IDENTITY_ONLY",
        "M6.3.shared_core_adapter",
    )

    etats_autorises = {"DECIDED", "EXPECTED", "INCONNU", "OBSERVED", "REQUESTED"}

    def parcourir(valeur: object) -> None:
        if isinstance(valeur, dict):
            if "state" in valeur:
                if valeur["state"] not in etats_autorises:
                    raise ErreurVerrouCampagne("état de preuve M6.3 invalide")
                if valeur["state"] in {"INCONNU", "OBSERVED"} and valeur.get(
                    "value"
                ) != "INCONNU":
                    raise ErreurVerrouCampagne("observation M6.3 inventée")
            for enfant in valeur.values():
                parcourir(enfant)
        elif isinstance(valeur, list):
            for enfant in valeur:
                parcourir(enfant)

    parcourir(panel["panel"])

    plan = json.loads((racine / PREDECESSEURS[3]["path"]).read_bytes())
    _egal(
        plan["decision_contract_sha256"],
        "ea07f5691249f648a939d1ca6bac26eaf38cea7bd2f7e3593add17a55184c704",
        "M6.4.decision_contract_sha256",
    )
    _egal(plan["acquisition_plan"]["planned_acquisitions"], 2, "M6.4.slots")
    _egal(len(plan["acquisition_plan"]["slots"]), 2, "M6.4.slot_count")
    _egal(plan["acquisition_plan"]["automatic_retries"], 0, "M6.4.auto_retry")
    _egal(plan["acquisition_plan"]["manual_retries"], 0, "M6.4.manual_retry")
    _egal(plan["acquisition_plan"]["fallbacks"], "NONE", "M6.4.fallbacks")

    politique = json.loads((racine / PREDECESSEURS[4]["path"]).read_bytes())
    _egal(
        politique["owner_authorities"]["owner_acceptance"]["authority_value"],
        "M6_5_OWNER_DECISION = ACCEPT_RECOMMENDED_BUNDLE",
        "M6.5.owner_decision",
    )
    _egal(
        politique["authorizations"],
        {
            "acquisition": "NOT_GRANTED",
            "execution": "NOT_GRANTED",
            "m6_6": "NOT_GRANTED",
            "provider_operation": "NOT_GRANTED",
            "spend_or_quota": "NOT_GRANTED",
        },
        "M6.5.authorizations",
    )


def valider_verrou_campagne_v0(
    verrou: Path = VERROU_PAR_DEFAUT,
    manifeste: Path = MANIFESTE_PAR_DEFAUT,
    recu: Path = RECU_PAR_DEFAUT,
    store_prive: Path = STORE_PRIVE_PAR_DEFAUT,
    racine: Path = RACINE,
    engagements_prives_attendus: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    engagements = (
        ENGAGEMENTS_PRIVES_REELS
        if engagements_prives_attendus is None
        else engagements_prives_attendus
    )
    engagements = _verifier_engagements(engagements)
    verrou_document, verrou_octets = _charger_json_canonique(verrou, "verrou")
    _verifier_verrou(verrou_document, engagements)
    _verifier_references(PREDECESSEURS, PREDECESSEURS, racine, "prédécesseurs")

    _verifier_invariants_predecesseurs(racine)

    manifeste_document, manifeste_octets = _charger_json_canonique(
        manifeste, "manifeste"
    )
    manifeste_ferme = _ferme(
        manifeste_document,
        (
            "current_validator",
            "excluded_from_root",
            "hash_conventions",
            "lock_artifact",
            "metadata",
            "predecessor_artifacts",
            "predecessor_validators",
            "private_commitments",
            "schema_version",
            "transitive_local_references",
        ),
        "manifeste",
    )
    _egal(manifeste_ferme["schema_version"], "campaign-v0-lock-manifest/v1", "manifeste.schema_version")
    _egal(
        manifeste_ferme["hash_conventions"],
        {"canonical_json": "UTF-8_SORT_KEYS_COMPACT_ALLOW_NAN_FALSE_PLUS_LF", "file_sha256": "sha256 of exact file bytes"},
        "manifeste.hash_conventions",
    )
    _egal(manifeste_ferme["metadata"], METADATA_MANIFESTE, "manifeste.metadata")
    _egal(
        manifeste_ferme["lock_artifact"],
        {"path": CHEMIN_VERROU, "sha256": _sha256(verrou_octets)},
        "manifeste.lock_artifact",
    )
    _verifier_references(manifeste_ferme["predecessor_artifacts"], PREDECESSEURS, racine, "manifeste.predecessor_artifacts")
    _verifier_references(manifeste_ferme["predecessor_validators"], VALIDATEURS_PREDECESSEURS, racine, "manifeste.predecessor_validators")
    _verifier_references(manifeste_ferme["transitive_local_references"], FERMETURE_TRANSITIVE, racine, "manifeste.transitive_local_references")
    validateur = _chemin_public(racine, CHEMIN_VALIDATOR, "manifeste.current_validator")
    _egal(
        manifeste_ferme["current_validator"],
        {"path": CHEMIN_VALIDATOR, "sha256": _sha256(validateur.read_bytes())},
        "manifeste.current_validator",
    )
    _egal(manifeste_ferme["private_commitments"], engagements, "manifeste.private_commitments")
    _egal(
        manifeste_ferme["excluded_from_root"],
        [CHEMIN_MANIFESTE, CHEMIN_RECU, "tests/test_verrou_campagne_v0.py"],
        "manifeste.excluded_from_root",
    )
    racine_verrou = _sha256(manifeste_octets)

    _verifier_store_prive(store_prive, engagements)
    resultats = _resultats_validateurs(racine)

    recu_document, recu_octets = _charger_json_canonique(recu, "reçu")
    recu_attendu = {
        "authorizations": AUTORISATIONS,
        "counts": {
            "acquisitions_performed": 0,
            "campaign_runs": 0,
            "canaries_performed": 0,
            "predecessor_artifacts": 5,
            "predecessor_validators": 5,
            "private_commitments": 2,
            "provider_operations": 0,
            "retries_performed": 0,
            "transitive_local_references": 11,
        },
        "lock_root": {"algorithm": "SHA256", "manifest_path": CHEMIN_MANIFESTE, "sha256": racine_verrou},
        "private_commitments": engagements,
        "public_artifacts": {
            "lock_sha256": _sha256(verrou_octets),
            "manifest_sha256": racine_verrou,
            "validator_sha256": _sha256(validateur.read_bytes()),
        },
        "schema_version": "campaign-v0-lock-validation-receipt/v1",
        "validation_results": resultats
        + [
            {
                "lock_root": racine_verrou,
                "milestone": "M6.6",
                "status": "VERROU_CAMPAGNE_V0_OK",
                "validator_sha256": _sha256(validateur.read_bytes()),
            }
        ],
        "zero_execution_proof": {
            "acquisition_performed": False,
            "campaign_executed": False,
            "preparation_performed": False,
            "provider_contacted": False,
            "quota_consumed": False,
            "spend_incurred": False,
        },
    }
    _egal(recu_document, recu_attendu, "reçu")
    return {
        "lock_root": racine_verrou,
        "lock_sha256": _sha256(verrou_octets),
        "manifest_sha256": racine_verrou,
        "private_object_count": 2,
        "receipt_sha256": _sha256(recu_octets),
        "status": "VERROU_CAMPAGNE_V0_OK",
    }


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser()
    analyseur.add_argument("--lock", type=Path, default=VERROU_PAR_DEFAUT)
    analyseur.add_argument("--manifest", type=Path, default=MANIFESTE_PAR_DEFAUT)
    analyseur.add_argument("--receipt", type=Path, default=RECU_PAR_DEFAUT)
    analyseur.add_argument("--private-store", type=Path, default=STORE_PRIVE_PAR_DEFAUT)
    arguments = analyseur.parse_args(argv)
    try:
        resultat = valider_verrou_campagne_v0(
            arguments.lock,
            arguments.manifest,
            arguments.receipt,
            arguments.private_store,
        )
    except (ErreurVerrouCampagne, KeyError, OSError, TypeError, ValueError) as exc:
        print(f"HOLD_CAMPAIGN_LOCK: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(resultat, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
