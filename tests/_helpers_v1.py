# /// script
# requires-python = ">=3.12"
# ///
"""Helpers de fixtures V1 partagés entre modules de tests.

Uniquement des ajustements de cohérence de fixtures de test : aucune
preuve versionnée du dépôt n'est modifiée et aucun comportement de
production n'est contourné."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
from typing import Callable


HISTORICAL_CONTRACT_COMMIT = "38e226a59020aad517cd0dbb16892ffb87d448ab"
HISTORICAL_CONTRACT_PATHS = (
    "docs/ARD.md",
    "docs/PRD.md",
    "docs/RULES.md",
)
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def historical_file_bytes(relative_path: str) -> bytes:
    """Lit un fichier historique depuis Git sans copie persistante."""
    return subprocess.check_output(
        [
            "git",
            "show",
            f"{HISTORICAL_CONTRACT_COMMIT}:{relative_path}",
        ],
        cwd=REPOSITORY_ROOT,
    )


def materialiser_contrats_historiques(root: Path) -> None:
    """Matérialise les trois contrats historiques dans une fixture jetable."""
    for relative_path in HISTORICAL_CONTRACT_PATHS:
        destination = root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(historical_file_bytes(relative_path))


def extraire_revision_historique(destination: Path) -> None:
    """Extrait la révision historique dans une fixture jetable."""
    archive = subprocess.check_output(
        ["git", "archive", HISTORICAL_CONTRACT_COMMIT],
        cwd=REPOSITORY_ROOT,
    )
    with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
        bundle.extractall(destination, filter="data")


def retirer_couverture_publiee(chemin_etat: "Path") -> None:
    """Aligne la copie bac à sable de l'état V1 sur le scénario testé :
    sans l'arbre de reçus et de verdicts officiels, aucune couverture
    annoncée ni exécution de complétion ne peut être redérivée. Les blocs
    hérités du dépôt sont retirés pour ne conserver que les projections
    effectivement prouvées par la fixture historique isolée."""
    contenu = json.loads(chemin_etat.read_text(encoding="utf-8"))
    contenu.pop("couverture", None)
    contenu.pop("execution_completion", None)
    chemin_etat.write_text(
        json.dumps(contenu, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def realigner_chaine_recus(
    module,
    racine: Path,
    campagne: Path,
    chemin_registre: Path,
    chemin_etat: Path,
    *,
    mutations: dict[str, Callable[[dict], None]] | None = None,
    configurations_retirees: set[str] | None = None,
) -> None:
    """Réaligne une chaîne de reçus mutée dans une fixture isolée."""
    mutations = mutations or {}
    configurations_retirees = configurations_retirees or set()
    repertoire = racine / campagne / "recus-v1"
    enveloppes = {
        chemin.name: json.loads(chemin.read_text(encoding="utf-8"))
        for chemin in repertoire.iterdir()
    }
    successeurs = {
        enveloppe["payload"]["predecesseur_adresse_contenu"]: nom
        for nom, enveloppe in enveloppes.items()
        if enveloppe["payload"]["predecesseur_adresse_contenu"] is not None
    }
    ordre = [
        next(
            nom
            for nom, enveloppe in enveloppes.items()
            if enveloppe["payload"]["predecesseur_adresse_contenu"] is None
        )
    ]
    while enveloppes[ordre[-1]]["content_address"]["sha256"] in successeurs:
        ordre.append(
            successeurs[enveloppes[ordre[-1]]["content_address"]["sha256"]]
        )
    reecritures: dict[str, tuple[str, str]] = {}
    suppressions: set[str] = set()
    nouveaux_fichiers: dict[str, bytes] = {}
    predecesseur: str | None = None
    prefixe = f"{campagne.as_posix()}/recus-v1/"
    for nom in ordre:
        enveloppe = enveloppes[nom]
        ancien_relatif = f"{prefixe}{nom}"
        identifiant = enveloppe["payload"]["configuration"]["identifiant"]
        if identifiant in configurations_retirees:
            suppressions.add(ancien_relatif)
            continue
        if nom in mutations:
            mutations[nom](enveloppe["payload"])
        enveloppe["payload"]["predecesseur_adresse_contenu"] = predecesseur
        adresse = module.adresse_canonique(enveloppe["payload"])
        enveloppe["content_address"]["sha256"] = adresse
        octets = module.octets_canoniques(enveloppe)
        nouveau_nom = f"{adresse}.json"
        nouveau_relatif = f"{prefixe}{nouveau_nom}"
        nouveaux_fichiers[nouveau_nom] = octets
        reecritures[ancien_relatif] = (
            nouveau_relatif,
            hashlib.sha256(octets).hexdigest(),
        )
        predecesseur = adresse

    for chemin in tuple(repertoire.iterdir()):
        chemin.unlink()
    for nom, octets in nouveaux_fichiers.items():
        (repertoire / nom).write_bytes(octets)

    registre_absolu = racine / chemin_registre
    registre = json.loads(registre_absolu.read_text(encoding="utf-8"))
    entrees = []
    for entree in registre["entrees"]:
        relatif = entree["recu"]
        if relatif in suppressions:
            continue
        if relatif in reecritures:
            entree["recu"], entree["recu_sha256"] = reecritures[relatif]
        entrees.append(entree)
    registre["entrees"] = entrees
    registre["couverture"]["acquisitions_officielles"] = len(entrees)
    registre["couverture"]["sorties_candidates"] = sum(
        entree["sortie_candidate"] == "PRESENTE" for entree in entrees
    )
    for statut in registre["couverture"]["verdicts"]:
        registre["couverture"]["verdicts"][statut] = sum(
            entree.get("verdict", {}).get("statut") == statut
            for entree in entrees
            if entree.get("verdict") is not None
        )
    octets_registre = module.octets_canoniques(registre)
    registre_absolu.write_bytes(octets_registre)
    sha_registre = hashlib.sha256(octets_registre).hexdigest()

    etat_absolu = racine / chemin_etat
    etat = json.loads(etat_absolu.read_text(encoding="utf-8"))
    registre_relatif = chemin_registre.as_posix()
    for creneau in etat.get("couverture", {}).get("creneaux", []):
        preuves = []
        for preuve in creneau["preuves"]:
            relatif = preuve["chemin"]
            if relatif in suppressions:
                continue
            if relatif in reecritures:
                preuve["chemin"], preuve["sha256"] = reecritures[relatif]
            elif relatif == registre_relatif:
                preuve["sha256"] = sha_registre
            preuves.append(preuve)
        creneau["preuves"] = preuves
    for creneau in etat.get("execution_completion", {}).get("creneaux", []):
        resultat = creneau["resultat_mesure"]
        if resultat in suppressions:
            creneau["resultat_mesure"] = "ABSENT"
        elif resultat in reecritures:
            creneau["resultat_mesure"] = reecritures[resultat][0]
    etat_absolu.write_bytes(module.octets_canoniques(etat))
