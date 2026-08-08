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


PROVENANCE_SOURCE_SHA256 = "dade38d6ff34e10266c0e0965b85427548fc5c89bd2dbc65c88e856ca0cf7208"
PRODUCTION_SOURCE_SHA256 = "fc000e827fe9ef171366caf7f65139d4ea52b619ea6e72bd97ff379f00869096"
PROVENANCE_HISTORIQUE_SHA256 = "0c0a04e13e6810c1143c8779b076f4f076373e43511b61a26977d3f82c6af2f9"
SOURCE_DIR = Path("temoins/r016-source")


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


def construire_provenance(task_dir: Path, source: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    provenance, production, fichiers = donnees_integration(source)
    historique_path = task_dir / "temoins/provenance-historique-v1.json"
    formelle_path = task_dir / "temoins/provenance.json"
    if historique_path.exists():
        historique_data = verifier_hash(historique_path, PROVENANCE_HISTORIQUE_SHA256)
    else:
        historique_data = verifier_hash(formelle_path, PROVENANCE_HISTORIQUE_SHA256)
        ecrire_exact_si_absent(historique_path, historique_data)
    historique = json.loads(historique_data.decode("utf-8"))
    anciens = historique.get("temoins")
    nouveaux = provenance.get("temoins")
    if not isinstance(anciens, dict) or not isinstance(nouveaux, dict):
        raise IntegrationR016Invalide("table des témoins absente")
    collision = set(anciens) & set(nouveaux)
    if collision:
        raise IntegrationR016Invalide(f"collision de provenance: {sorted(collision)}")

    fusion = dict(historique)
    fusion["_etat"] = "préenregistré, en attente de qualification Chromium"
    fusion["_r016_source"] = {
        "provenance_sha256": PROVENANCE_SOURCE_SHA256,
        "production_sha256": PRODUCTION_SOURCE_SHA256,
        "statut": production.get("statut"),
    }
    fusion["qualification_set"] = list(provenance["qualification_set"])
    fusion["temoins"] = {**anciens, **nouveaux}
    verifier_matrice(fusion)
    return fusion, fichiers


def importer(source: Path, task_dir: Path) -> dict[str, Any]:
    fusion, fichiers = construire_provenance(task_dir, source)
    for nom in fusion["qualification_set"]:
        ecrire_exact_si_absent(task_dir / nom, fichiers[nom])
    ecrire_exact_si_absent(
        task_dir / SOURCE_DIR / "provenance.json", fichiers["provenance.json"]
    )
    ecrire_exact_si_absent(
        task_dir / SOURCE_DIR / "production.json", fichiers["production.json"]
    )
    ecrire_exact_si_absent(
        task_dir / SOURCE_DIR / "outils/harnais-neg04.js",
        fichiers["outils/harnais-neg04.js"],
    )
    data = (json.dumps(fusion, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    remplacer_atomiquement(
        task_dir / "temoins/provenance.json",
        data,
        {PROVENANCE_HISTORIQUE_SHA256, sha256(data)},
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
    formelle = lire_json(task_dir / "temoins/provenance.json")
    if formelle.get("qualification_set") != provenance_source.get("qualification_set"):
        raise IntegrationR016Invalide("qualification_set différente de la source figée")
    temoins_formels = formelle.get("temoins")
    temoins_source = provenance_source.get("temoins")
    temoins_historiques = historique.get("temoins")
    if not all(isinstance(table, dict) for table in (
        temoins_formels, temoins_source, temoins_historiques
    )):
        raise IntegrationR016Invalide("table de provenance absente")
    for nom in provenance_source["qualification_set"]:
        if temoins_formels.get(nom) != temoins_source.get(nom):
            raise IntegrationR016Invalide(f"provenance qualifiante modifiée: {nom}")
    for nom, entree in temoins_historiques.items():
        if temoins_formels.get(nom) != entree:
            raise IntegrationR016Invalide(f"provenance historique modifiée: {nom}")
    if formelle.get("_r016_source") != {
        "provenance_sha256": PROVENANCE_SOURCE_SHA256,
        "production_sha256": PRODUCTION_SOURCE_SHA256,
        "statut": production.get("statut"),
    }:
        raise IntegrationR016Invalide("liaison à la source R-016 modifiée")
    matrice = verifier_matrice(formelle)
    declares = fichiers_declares(production)
    for nom in formelle["qualification_set"]:
        attendu = declares.get(nom)
        if attendu is None:
            raise IntegrationR016Invalide(f"témoin absent du manifeste livré: {nom}")
        verifier_hash(task_dir / nom, attendu)
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
