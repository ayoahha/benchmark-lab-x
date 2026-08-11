#!/usr/bin/env python3
"""Importer et vérifier le paquet R-016 préenregistré sans lancer le juge"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from protocole_v2 import PREDICATS_V4


PROVENANCE_SOURCE_SHA256 = "d4a52ae0501a080eff2a631dc7c8294427b97b7400557e9f14afb8d1a9a898a7"
PRODUCTION_SOURCE_SHA256 = "dce711f42718609e2e46cead6e8dc216e400f9d3dfce6c0f5bff3e05694e35b2"
PROVENANCE_HISTORIQUE_SHA256 = "0c0a04e13e6810c1143c8779b076f4f076373e43511b61a26977d3f82c6af2f9"
PROVENANCE_FORMELLE_V1_SHA256 = "7f8b27bb1a146ac054375ccd0970257d64e3cff5af6635168cd3216640f3cb9a"
SOURCE_DIR = Path("temoins/r016-source")
POSITIVE_SOURCE_DIR = Path("temoins/r016-positive-v3-source")
POSITIVE_WITNESS = "temoins/pos-03-solution.md"
POSITIVE_PACKAGE_SHA256SUMS_SHA256 = (
    "9baa7f012e8ad4e1b536f121ad85d91b87770146afda88f7bf5af93f64e6eef7"
)
POSITIVE_PACKAGE_HASHES = {
    "d110.json": "d4a2019aad213f79fc05d8f8005d1da50a4c5b230f3121105b370f6fabf3687f",
    "d80-events.tsv": "aae457a7400111f0924cf5c01c82f7d45fbcee6924cd931dd9ccd352be5ffa9b",
    "d80.json": "6fd7ba3edd9febe3c6b64f64ad7c2204517fcb7e43c81ddefe970437cf54cfb0",
    "events.tsv": "d189e44db66ec9140a681eac51f4070b958e025819dc7080023a69a4154aa777",
    "preregistration.json": "af94ffebf8d598816d17dbce60e785f49c20adae905549d23ef27cd55b8a1aa0",
    "production.json": "f0d4515966774ea1e943feeccc04b2125dca9577fe33cec074240052c42bea95",
    "reference.py": "845d6d38eb7a11d9d3722f18dda6ee27ccc0da044251249db4629726b6dde80a",
    "selfcheck.py": "1f4aeb7accf8a900254bb117efce63c91e3fed38613db41926acbcc674a2ab3c",
    POSITIVE_WITNESS: "1a5f82af054ff8cb93e142c1745736a8f1e437912ffb0387ed79b58f47d83ce5",
}
TASK_SOURCE_HASHES = {
    "task-v3.md": "7acfb34a2e4e68d5fe8b75d2972cc97bb949f99d36e92b12e80de1339e9a77bf",
    "donnees.md": "2f4dd0872b4377ea61df278396898f4cd7354d1bfa2a105ef6bfe1cdd3c77045",
}


class IntegrationR016Invalide(ValueError):
    """Le paquet ou son intégration ne respecte pas le préenregistrement"""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def lire_json(path: Path) -> dict[str, Any]:
    try:
        objet = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrationR016Invalide(f"JSON illisible: {path}") from exc
    if not isinstance(objet, dict):
        raise IntegrationR016Invalide(f"objet JSON attendu: {path}")
    return objet


def fichier_regulier(path: Path) -> bytes:
    if not path.is_file() or path.is_symlink():
        raise IntegrationR016Invalide(f"fichier absent, non régulier ou lié: {path}")
    return path.read_bytes()


def verifier_hash(path: Path, attendu: str) -> bytes:
    data = fichier_regulier(path)
    observe = sha256(data)
    if observe != attendu:
        raise IntegrationR016Invalide(
            f"empreinte différente pour {path}: {observe} au lieu de {attendu}"
        )
    return data


def ecrire_exact_si_absent(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or path.read_bytes() != data:
            raise IntegrationR016Invalide(f"refus d’écraser un actif différent: {path}")
        return
    path.write_bytes(data)


def chemin_destination_sur(racine: Path, relatif: str | Path) -> Path:
    chemin = Path(relatif)
    if chemin.is_absolute() or ".." in chemin.parts or "." in chemin.parts:
        raise IntegrationR016Invalide(f"chemin de destination non canonique: {relatif}")
    if not racine.is_dir() or racine.is_symlink():
        raise IntegrationR016Invalide(f"racine de destination absente ou liée: {racine}")
    courant = racine
    for partie in chemin.parts[:-1]:
        courant /= partie
        if courant.is_symlink():
            raise IntegrationR016Invalide(f"ancêtre symbolique interdit: {courant}")
        if courant.exists() and not courant.is_dir():
            raise IntegrationR016Invalide(f"ancêtre non répertoire: {courant}")
    cible = racine / chemin
    if cible.is_symlink():
        raise IntegrationR016Invalide(f"destination symbolique interdite: {cible}")
    return cible


def remplacer_atomiquement(path: Path, data: bytes, hashes_admis: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        actuel = fichier_regulier(path)
        if sha256(actuel) not in hashes_admis:
            raise IntegrationR016Invalide(f"provenance locale modifiée hors intégration: {path}")
        if actuel == data:
            return
    fd, nom = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(nom)
    try:
        with os.fdopen(fd, "wb") as flux:
            flux.write(data)
            flux.flush()
            os.fsync(flux.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def fichiers_declares(production: dict[str, Any]) -> dict[str, str]:
    declares = production.get("fichiers_livres")
    if not isinstance(declares, dict) or not declares:
        raise IntegrationR016Invalide("fichiers_livres absent de production.json")
    resultat: dict[str, str] = {}
    for nom, empreinte in declares.items():
        if not isinstance(nom, str) or not isinstance(empreinte, str):
            raise IntegrationR016Invalide("entrée invalide dans fichiers_livres")
        relatif = Path(nom)
        if relatif.is_absolute() or ".." in relatif.parts or "." in relatif.parts:
            raise IntegrationR016Invalide(f"chemin source non canonique: {nom}")
        resultat[nom] = empreinte
    return resultat


def verifier_paquet_positif_ferme(source: Path) -> dict[str, bytes]:
    if not source.is_dir() or source.is_symlink():
        raise IntegrationR016Invalide("dossier du paquet positif absent ou lié")
    attendus = {**POSITIVE_PACKAGE_HASHES, "SHA256SUMS": POSITIVE_PACKAGE_SHA256SUMS_SHA256}
    trouves: set[str] = set()
    dossiers: set[str] = set()
    for path in source.rglob("*"):
        if path.is_symlink():
            raise IntegrationR016Invalide(f"lien interdit dans le paquet positif: {path}")
        if path.is_file():
            trouves.add(path.relative_to(source).as_posix())
        elif path.is_dir():
            dossiers.add(path.relative_to(source).as_posix())
        else:
            raise IntegrationR016Invalide(f"entrée non régulière dans le paquet positif: {path}")
    if dossiers != {"temoins"}:
        raise IntegrationR016Invalide(f"arborescence positive non fermée: {sorted(dossiers)}")
    if trouves != set(attendus):
        raise IntegrationR016Invalide(
            f"paquet positif non fermé, ajoutés={sorted(trouves - set(attendus))}, "
            f"manquants={sorted(set(attendus) - trouves)}"
        )
    return {nom: verifier_hash(source / nom, empreinte) for nom, empreinte in attendus.items()}


def attentes_positives_preenregistrees(
    preregistration: dict[str, Any],
) -> dict[str, dict[str, bool]]:
    if preregistration.get("schema") != "r016-preregistration-v1":
        raise IntegrationR016Invalide("schéma du préenregistrement positif invalide")
    if preregistration.get("status") != "PRE_REGISTERED":
        raise IntegrationR016Invalide("statut du préenregistrement positif invalide")
    artefact = preregistration.get("witness_artifact")
    if artefact != {
        "path": POSITIVE_WITNESS,
        "sha256": POSITIVE_PACKAGE_HASHES[POSITIVE_WITNESS],
    }:
        raise IntegrationR016Invalide("témoin positif différent du préenregistrement")

    bloc = preregistration.get("expectations")
    if not isinstance(bloc, dict) or bloc.get("predicate_count") != 51:
        raise IntegrationR016Invalide("compte de prédicats préenregistrés invalide")
    if (
        bloc.get("fixed_before_judge") is not True
        or bloc.get("judge_observed_at_registration") is not False
    ):
        raise IntegrationR016Invalide("attentes positives non figées avant le juge")
    ordre = bloc.get("predicate_order")
    valeurs = bloc.get("expected_boolean_map")
    if not isinstance(ordre, list) or not isinstance(valeurs, dict):
        raise IntegrationR016Invalide("carte des attentes positives absente")

    ordre_attendu: list[tuple[str, str, str, int]] = []
    ordinal = 0
    niveau_precision = 0
    for carte, predicats in PREDICATS_V4.items():
        for predicat in predicats:
            ordinal += 1
            identifiant = predicat
            if carte == "pentagone-precision-24s":
                niveau_precision += 1
                identifiant = f"P24_{niveau_precision:02d}"
            ordre_attendu.append((carte, predicat, identifiant, ordinal))
    if len(ordre_attendu) != 51 or len(ordre) != 51:
        raise IntegrationR016Invalide("ordre préenregistré incomplet")

    resultat = {carte: {} for carte in PREDICATS_V4}
    identifiants: list[str] = []
    for entree, (carte, predicat, identifiant, position) in zip(ordre, ordre_attendu):
        if not isinstance(entree, dict) or (
            entree.get("id") != identifiant
            or entree.get("card") != carte
            or entree.get("ordinal") != position
        ):
            raise IntegrationR016Invalide(
                f"bijection de prédicat invalide à la position {position}"
            )
        identifiants.append(identifiant)
        resultat[carte][predicat] = True
    if set(valeurs) != set(identifiants) or any(valeurs[nom] is not True for nom in identifiants):
        raise IntegrationR016Invalide("valeurs positives préenregistrées incomplètes")
    return resultat


def donnees_paquet_positif(
    source: Path, task_dir: Path
) -> tuple[dict[str, Any], dict[str, Any], dict[str, bytes], dict[str, dict[str, bool]]]:
    fichiers = verifier_paquet_positif_ferme(source)
    for nom, empreinte in TASK_SOURCE_HASHES.items():
        verifier_hash(task_dir / nom, empreinte)
    try:
        preregistration = json.loads(fichiers["preregistration.json"].decode("utf-8"))
        production = json.loads(fichiers["production.json"].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IntegrationR016Invalide("métadonnées du paquet positif illisibles") from exc
    if not isinstance(preregistration, dict) or not isinstance(production, dict):
        raise IntegrationR016Invalide("métadonnées du paquet positif invalides")
    attentes = attentes_positives_preenregistrees(preregistration)

    lien = production.get("pre_registered_expectations")
    if (
        production.get("schema") != "r016-production-v3"
        or production.get("status") != "LIVRE"
        or production.get("witness") != "R-016-positive-v3"
        or not isinstance(lien, dict)
        or lien.get("preregistration_sha256")
        != POSITIVE_PACKAGE_HASHES["preregistration.json"]
        or lien.get("predicate_count") != 51
        or lien.get("fixed_before_judge") is not True
        or lien.get("judge_observed") is not False
        or lien.get("no_pass_claim") is not True
    ):
        raise IntegrationR016Invalide("production positive non liée au préenregistrement")
    sources = preregistration.get("source_read_declaration", {}).get("allowed_sources")
    if not isinstance(sources, list) or {
        Path(entree.get("path", "")).name: entree.get("sha256")
        for entree in sources if isinstance(entree, dict)
    } != TASK_SOURCE_HASHES:
        raise IntegrationR016Invalide("sources autorisées différentes du préenregistrement")
    declaration = production.get("source_read_declaration")
    derivation = declaration.get("derivation_sources") if isinstance(declaration, dict) else None
    if not isinstance(derivation, list) or {
        Path(entree.get("path", "")).name: entree.get("sha256")
        for entree in derivation if isinstance(entree, dict)
    } != TASK_SOURCE_HASHES:
        raise IntegrationR016Invalide("sources de dérivation différentes de la production")
    if declaration.get("forbidden_runtime_sources_consulted") != []:
        raise IntegrationR016Invalide("source runtime interdite déclarée dans la production")
    return preregistration, production, fichiers, attentes


def entree_provenance_positive(
    attentes: dict[str, dict[str, bool]],
) -> dict[str, Any]:
    return {
        "producteur": (
            "agent producteur indépendant local, sans accès au vérificateur ; "
            "dérivation physique et contractuelle limitée aux deux sources publiques hashées"
        ),
        "acces_au_verificateur": False,
        "consignes": (
            "task-v3.md sha256 " + TASK_SOURCE_HASHES["task-v3.md"]
            + ", donnees.md sha256 " + TASK_SOURCE_HASHES["donnees.md"]
            + ", préenregistrement sha256 "
            + POSITIVE_PACKAGE_HASHES["preregistration.json"]
            + " ; aucune observation du juge avant fixation des 51 attentes"
        ),
        "statut_octets": (
            "témoin positif préenregistré ; sha256 "
            + POSITIVE_PACKAGE_HASHES[POSITIVE_WITNESS]
            + " ; preuve numérique forte non certifiée par intervalles"
        ),
        "resultat_attendu": attentes,
    }


def verifier_matrice(provenance: dict[str, Any]) -> dict[str, int]:
    qualification = provenance.get("qualification_set")
    temoins = provenance.get("temoins")
    if (
        not isinstance(qualification, list)
        or len(qualification) != 13
        or len(set(qualification)) != len(qualification)
        or not isinstance(temoins, dict)
    ):
        raise IntegrationR016Invalide("qualification_set R-016 invalide")

    couverture_positive = 0
    couverture_negative = 0
    for carte, predicats in PREDICATS_V4.items():
        for predicat in predicats:
            valeurs = []
            for nom in qualification:
                source = temoins.get(nom)
                if not isinstance(source, dict):
                    raise IntegrationR016Invalide(f"provenance absente: {nom}")
                attendu = source.get("resultat_attendu")
                if not isinstance(attendu, dict):
                    raise IntegrationR016Invalide(f"résultat attendu absent: {nom}")
                valeur = (attendu.get(carte) or {}).get(predicat)
                if isinstance(valeur, bool):
                    valeurs.append(valeur)
            if True not in valeurs or False not in valeurs:
                raise IntegrationR016Invalide(f"couverture bilatérale absente: {carte}/{predicat}")
            couverture_positive += 1
            couverture_negative += 1

    for nom in qualification:
        source = temoins[nom]
        if source.get("acces_au_verificateur") is not False:
            raise IntegrationR016Invalide(f"producteur non aveugle déclaré: {nom}")
        if not isinstance(source.get("producteur"), str) or not source["producteur"].strip():
            raise IntegrationR016Invalide(f"producteur absent: {nom}")
        if not isinstance(source.get("consignes"), str) or not source["consignes"].strip():
            raise IntegrationR016Invalide(f"consignes absentes: {nom}")
        for carte, attendus in source["resultat_attendu"].items():
            if carte not in PREDICATS_V4 or not isinstance(attendus, dict):
                raise IntegrationR016Invalide(f"carte attendue inconnue: {nom}/{carte}")
            for predicat, valeur in attendus.items():
                if predicat not in PREDICATS_V4[carte] or not isinstance(valeur, bool):
                    raise IntegrationR016Invalide(f"attente invalide: {nom}/{carte}/{predicat}")
    return {
        "witnesses": len(qualification),
        "predicates": sum(len(v) for v in PREDICATS_V4.values()),
        "positive": couverture_positive,
        "negative": couverture_negative,
    }


def donnees_integration(source: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, bytes]]:
    provenance_data = verifier_hash(source / "provenance.json", PROVENANCE_SOURCE_SHA256)
    production_data = verifier_hash(source / "production.json", PRODUCTION_SOURCE_SHA256)
    provenance = json.loads(provenance_data.decode("utf-8"))
    production = json.loads(production_data.decode("utf-8"))
    declares = fichiers_declares(production)
    fichiers = {
        "provenance.json": provenance_data,
        "production.json": production_data,
    }
    for nom, attendu in declares.items():
        if nom == "provenance.json":
            if attendu != PROVENANCE_SOURCE_SHA256:
                raise IntegrationR016Invalide("hash de provenance incohérent dans production.json")
            continue
        fichiers[nom] = verifier_hash(source / nom, attendu)
    verifier_matrice(provenance)
    return provenance, production, fichiers


def donnees_legacy_destination(task_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    provenance_data = verifier_hash(
        task_dir / SOURCE_DIR / "provenance.json", PROVENANCE_SOURCE_SHA256
    )
    production_data = verifier_hash(
        task_dir / SOURCE_DIR / "production.json", PRODUCTION_SOURCE_SHA256
    )
    provenance = json.loads(provenance_data.decode("utf-8"))
    production = json.loads(production_data.decode("utf-8"))
    declares = fichiers_declares(production)
    qualification = provenance.get("qualification_set")
    if not isinstance(qualification, list):
        raise IntegrationR016Invalide("qualification_set legacy absente")
    for nom in qualification:
        attendu = declares.get(nom)
        if attendu is None:
            raise IntegrationR016Invalide(f"témoin legacy absent du manifeste: {nom}")
        verifier_hash(task_dir / nom, attendu)
    verifier_hash(
        task_dir / SOURCE_DIR / "outils/harnais-neg04.js",
        declares["outils/harnais-neg04.js"],
    )
    verifier_matrice(provenance)
    return provenance, production


def construire_provenance(task_dir: Path, source: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    historique_path = chemin_destination_sur(
        task_dir, "temoins/provenance-historique-v1.json"
    )
    formelle_path = chemin_destination_sur(task_dir, "temoins/provenance.json")
    provenance_legacy, production_legacy = donnees_legacy_destination(task_dir)
    _, production_positive, fichiers, attentes = donnees_paquet_positif(source, task_dir)
    if historique_path.exists():
        historique_data = verifier_hash(historique_path, PROVENANCE_HISTORIQUE_SHA256)
    else:
        historique_data = verifier_hash(formelle_path, PROVENANCE_HISTORIQUE_SHA256)
        ecrire_exact_si_absent(historique_path, historique_data)
    historique = json.loads(historique_data.decode("utf-8"))
    anciens = historique.get("temoins")
    temoins_legacy = provenance_legacy.get("temoins")
    qualification_legacy = provenance_legacy.get("qualification_set")
    if (
        not isinstance(anciens, dict)
        or not isinstance(temoins_legacy, dict)
        or not isinstance(qualification_legacy, list)
    ):
        raise IntegrationR016Invalide("table des témoins absente")
    negatifs = [nom for nom in qualification_legacy if "/neg-" in nom]
    if len(negatifs) != 12 or len(set(negatifs)) != 12:
        raise IntegrationR016Invalide("ensemble des douze témoins négatifs absent")
    collision = set(anciens) & (set(temoins_legacy) | {POSITIVE_WITNESS})
    if collision:
        raise IntegrationR016Invalide(f"collision de provenance: {sorted(collision)}")

    fusion = dict(historique)
    fusion["_etat"] = "préenregistré, en attente d’une nouvelle qualification Chromium"
    fusion["_r016_source"] = {
        "provenance_sha256": PROVENANCE_SOURCE_SHA256,
        "production_sha256": PRODUCTION_SOURCE_SHA256,
        "statut": production_legacy.get("statut"),
    }
    fusion["_r016_positive_v3_source"] = {
        "package_dir": POSITIVE_SOURCE_DIR.as_posix(),
        "sha256sums_sha256": POSITIVE_PACKAGE_SHA256SUMS_SHA256,
        "production_sha256": POSITIVE_PACKAGE_HASHES["production.json"],
        "preregistration_sha256": POSITIVE_PACKAGE_HASHES["preregistration.json"],
        "witness_sha256": POSITIVE_PACKAGE_HASHES[POSITIVE_WITNESS],
        "statut": production_positive.get("status"),
    }
    fusion["qualification_set"] = [*negatifs, POSITIVE_WITNESS]
    fusion["temoins"] = {
        **anciens,
        **temoins_legacy,
        POSITIVE_WITNESS: entree_provenance_positive(attentes),
    }
    verifier_matrice(fusion)
    return fusion, fichiers


def importer(source: Path, task_dir: Path) -> dict[str, Any]:
    fusion, fichiers = construire_provenance(task_dir, source)
    ecrire_exact_si_absent(
        chemin_destination_sur(task_dir, POSITIVE_WITNESS), fichiers[POSITIVE_WITNESS]
    )
    for nom, data in fichiers.items():
        ecrire_exact_si_absent(
            chemin_destination_sur(task_dir, POSITIVE_SOURCE_DIR / nom), data
        )
    data = (json.dumps(fusion, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    remplacer_atomiquement(
        chemin_destination_sur(task_dir, "temoins/provenance.json"),
        data,
        {PROVENANCE_FORMELLE_V1_SHA256, sha256(data)},
    )
    return verifier_destination(task_dir)


def verifier_destination(task_dir: Path) -> dict[str, Any]:
    historique_data = verifier_hash(
        task_dir / "temoins/provenance-historique-v1.json", PROVENANCE_HISTORIQUE_SHA256
    )
    historique = json.loads(historique_data.decode("utf-8"))
    provenance_source_data = verifier_hash(
        task_dir / SOURCE_DIR / "provenance.json", PROVENANCE_SOURCE_SHA256
    )
    provenance_source = json.loads(provenance_source_data.decode("utf-8"))
    production_data = verifier_hash(
        task_dir / SOURCE_DIR / "production.json", PRODUCTION_SOURCE_SHA256
    )
    production = json.loads(production_data.decode("utf-8"))
    _, production_positive, _, attentes_positives = donnees_paquet_positif(
        task_dir / POSITIVE_SOURCE_DIR, task_dir
    )
    formelle = lire_json(task_dir / "temoins/provenance.json")
    qualification_source = provenance_source.get("qualification_set")
    if not isinstance(qualification_source, list):
        raise IntegrationR016Invalide("qualification_set legacy absente")
    negatifs = [nom for nom in qualification_source if "/neg-" in nom]
    if formelle.get("qualification_set") != [*negatifs, POSITIVE_WITNESS]:
        raise IntegrationR016Invalide("qualification_set différente des deux sources figées")
    temoins_formels = formelle.get("temoins")
    temoins_source = provenance_source.get("temoins")
    temoins_historiques = historique.get("temoins")
    if not all(isinstance(table, dict) for table in (
        temoins_formels, temoins_source, temoins_historiques
    )):
        raise IntegrationR016Invalide("table de provenance absente")
    for nom in provenance_source["qualification_set"]:
        if temoins_formels.get(nom) != temoins_source.get(nom):
            raise IntegrationR016Invalide(f"provenance legacy modifiée: {nom}")
    for nom, entree in temoins_historiques.items():
        if temoins_formels.get(nom) != entree:
            raise IntegrationR016Invalide(f"provenance historique modifiée: {nom}")
    if formelle.get("_r016_source") != {
        "provenance_sha256": PROVENANCE_SOURCE_SHA256,
        "production_sha256": PRODUCTION_SOURCE_SHA256,
        "statut": production.get("statut"),
    }:
        raise IntegrationR016Invalide("liaison à la source R-016 modifiée")
    if formelle.get("_r016_positive_v3_source") != {
        "package_dir": POSITIVE_SOURCE_DIR.as_posix(),
        "sha256sums_sha256": POSITIVE_PACKAGE_SHA256SUMS_SHA256,
        "production_sha256": POSITIVE_PACKAGE_HASHES["production.json"],
        "preregistration_sha256": POSITIVE_PACKAGE_HASHES["preregistration.json"],
        "witness_sha256": POSITIVE_PACKAGE_HASHES[POSITIVE_WITNESS],
        "statut": production_positive.get("status"),
    }:
        raise IntegrationR016Invalide("liaison au témoin positif v3 modifiée")
    if temoins_formels.get(POSITIVE_WITNESS) != entree_provenance_positive(attentes_positives):
        raise IntegrationR016Invalide("provenance du témoin positif v3 modifiée")
    matrice = verifier_matrice(formelle)
    declares = fichiers_declares(production)
    for nom in negatifs:
        attendu = declares.get(nom)
        if attendu is None:
            raise IntegrationR016Invalide(f"témoin négatif absent du manifeste legacy: {nom}")
        verifier_hash(task_dir / nom, attendu)
    verifier_hash(
        task_dir / POSITIVE_WITNESS, POSITIVE_PACKAGE_HASHES[POSITIVE_WITNESS]
    )
    verifier_hash(
        task_dir / SOURCE_DIR / "outils/harnais-neg04.js",
        declares["outils/harnais-neg04.js"],
    )
    return {
        "status": "R016_PREREGISTERED_STATIC_PASS",
        **matrice,
        "dynamic_qualification": "HOLD_CHROMIUM",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--source", type=Path)
    mode.add_argument("--check", action="store_true")
    ap.add_argument(
        "--task-dir", type=Path, default=Path("tasks/dev/pentagone-rotatif")
    )
    args = ap.parse_args()
    try:
        resultat = importer(args.source, args.task_dir) if args.source else verifier_destination(args.task_dir)
    except (IntegrationR016Invalide, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"HOLD: {exc}")
        return 2
    print(json.dumps(resultat, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
