from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
from typing import Iterator


RACINE = Path(__file__).resolve().parents[1]
FRAGMENT_PAR_DEFAUT = (
    RACINE
    / "tasks/dev/pre-cadrage-entretien-client/campagne-v0/autorites-v1/autorites.json"
)
EMPREINTE_FRAGMENT_ATTENDUE = (
    "d551362f35a9e650d78330e79b757bb3e63c892b92fcaa08b48f86599d951d82"
)
CHAMPS_RACINE = ("schema_version", "scope", "hash_conventions", "authorities")
CHAMPS_AUTORITES = (
    "need",
    "card_issue",
    "approved_package",
    "evaluation_route",
    "specific_platform",
    "auto_router",
    "measurement_profile",
    "official_acceptability",
    "pareto",
    "abstention",
)


class ErreurAutorites(ValueError):
    pass


def _sha256(contenu: bytes) -> str:
    return hashlib.sha256(contenu).hexdigest()


def _exiger_champs(
    valeur: object, champs: tuple[str, ...], emplacement: str
) -> dict[str, object]:
    if not isinstance(valeur, dict) or set(valeur) != set(champs):
        raise ErreurAutorites(f"schéma fermé divergent: {emplacement}")
    return valeur


def _exiger_egal(observe: object, attendu: object, emplacement: str) -> None:
    if observe != attendu:
        raise ErreurAutorites(f"valeur d’autorité divergente: {emplacement}")


def _references_fichiers(valeur: object) -> Iterator[dict[str, object]]:
    if isinstance(valeur, dict):
        if set(valeur) == {"path", "sha256"}:
            yield valeur
        else:
            for enfant in valeur.values():
                yield from _references_fichiers(enfant)
    elif isinstance(valeur, list):
        for enfant in valeur:
            yield from _references_fichiers(enfant)


def _valider_reference_fichier(
    reference: dict[str, object], racine: Path
) -> None:
    chemin_brut = reference["path"]
    empreinte = reference["sha256"]
    if not isinstance(chemin_brut, str) or not isinstance(empreinte, str):
        raise ErreurAutorites("référence de fichier non textuelle")
    chemin_relatif = PurePosixPath(chemin_brut)
    if chemin_relatif.is_absolute() or ".." in chemin_relatif.parts:
        raise ErreurAutorites(f"référence de fichier non sûre: {chemin_brut}")
    chemin = racine.joinpath(*chemin_relatif.parts)
    try:
        chemin.resolve(strict=True).relative_to(racine.resolve(strict=True))
        contenu = chemin.read_bytes()
    except (OSError, ValueError) as exc:
        raise ErreurAutorites(
            f"référence de fichier inaccessible: {chemin_brut}"
        ) from exc
    if _sha256(contenu) != empreinte:
        raise ErreurAutorites(f"empreinte de fichier divergente: {chemin_brut}")


def valider_autorites_campagne_v0(
    fragment: Path = FRAGMENT_PAR_DEFAUT, racine: Path = RACINE
) -> dict[str, object]:
    try:
        contenu = fragment.read_bytes()
        document = json.loads(contenu)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ErreurAutorites("fragment illisible ou JSON invalide") from exc

    racine_document = _exiger_champs(document, CHAMPS_RACINE, "racine")
    _exiger_egal(
        racine_document["schema_version"],
        "campaign-v0-authorities/v1",
        "schema_version",
    )
    _exiger_egal(
        racine_document["scope"],
        {
            "issue_number": 64,
            "issue_url": "https://github.com/ayoahha/benchmark-lab-x/issues/64",
            "parent_issue_number": 19,
            "parent_issue_url": "https://github.com/ayoahha/benchmark-lab-x/issues/19",
            "product_version": "V0",
        },
        "scope",
    )
    autorites = _exiger_champs(
        racine_document["authorities"], CHAMPS_AUTORITES, "authorities"
    )
    _exiger_egal(
        autorites["evaluation_route"]["value"],
        "USE_MANUAL",
        "evaluation_route.value",
    )
    _exiger_egal(
        autorites["specific_platform"]["value"],
        "STOP_SPECIFIC_PLATFORM",
        "specific_platform.value",
    )
    _exiger_egal(
        autorites["auto_router"]["value"],
        "EXCLUDED",
        "auto_router.value",
    )
    _exiger_egal(
        autorites["measurement_profile"]["value"],
        "api",
        "measurement_profile.value",
    )
    _exiger_egal(
        {
            cle: autorites["official_acceptability"][cle]
            for cle in ("automatic_verdict", "human_blind_verdict", "operator")
        },
        {
            "automatic_verdict": "PASS",
            "human_blind_verdict": "ACCEPTABLE",
            "operator": "AND",
        },
        "official_acceptability",
    )
    _exiger_egal(
        autorites["pareto"]["axes"],
        [
            {"metric": "official_acceptance_rate", "direction": "MAXIMIZE"},
            {
                "metric": "supplier_cost_per_officially_acceptable_output",
                "direction": "MINIMIZE",
            },
            {
                "metric": "latency_under_preregistered_rule",
                "direction": "MINIMIZE",
            },
        ],
        "pareto.axes",
    )
    _exiger_egal(
        autorites["pareto"]["coverage"],
        "ELIGIBILITY_AND_INTERPRETATION_NOT_AXIS",
        "pareto.coverage",
    )
    _exiger_egal(
        {
            cle: autorites["abstention"][cle]
            for cle in (
                "triggers",
                "result",
                "replacement_value",
                "unique_winner_without_sufficient_explicit_preference",
            )
        },
        {
            "triggers": [
                "NO_CONFIGURATION_SATISFIES_NEED_CONSTRAINTS",
                "EVIDENCE_NOT_COMPARABLE_OR_FRESH_ENOUGH",
                "INSUFFICIENT_COVERAGE",
                "AMBIGUOUS_IDENTITY_OR_PROVENANCE",
                "MISSING_PREFERENCE_REQUIRED_FOR_UNIQUE_RECOMMENDATION",
            ],
            "result": "NAME_MISSING_EVIDENCE_AND_POSSIBLE_HUMAN_ACTION",
            "replacement_value": "FORBIDDEN",
            "unique_winner_without_sufficient_explicit_preference": "FORBIDDEN",
        },
        "abstention",
    )

    references = list(_references_fichiers(document))
    for reference in references:
        _valider_reference_fichier(reference, racine)

    empreinte_fragment = _sha256(contenu)
    if empreinte_fragment != EMPREINTE_FRAGMENT_ATTENDUE:
        raise ErreurAutorites("fragment ou référence d’autorité divergent")
    return {
        "status": "AUTORITES_CAMPAGNE_V0_OK",
        "schema_version": racine_document["schema_version"],
        "fragment_sha256": empreinte_fragment,
        "file_reference_count": len(references),
    }


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser()
    analyseur.add_argument("fragment", nargs="?", type=Path, default=FRAGMENT_PAR_DEFAUT)
    arguments = analyseur.parse_args(argv)
    try:
        recu = valider_autorites_campagne_v0(arguments.fragment)
    except ErreurAutorites as exc:
        print(f"HOLD_M6_AUTHORITIES: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(recu, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
