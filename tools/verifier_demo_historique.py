# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Vérifie la vue historique reference-v2 sans exécuter l'instrument."""

import argparse
import hashlib
import json
import os
import sys
from html.parser import HTMLParser
from pathlib import Path

RACINE = Path(__file__).parent.parent
RAPPORT_ATTENDU = RACINE / "runs" / "2026-08-06-reference-v2" / "results-data.json"
ROUTES_ATTENDUES = RACINE / "runs" / "2026-08-06-reference-v2" / "routes.json"
PAGE_ATTENDUE = Path("/private/tmp/benchmark-lab-x-reference-v2.html")
SHA_RAPPORT = "4185a4ab9b4512f93bae0b998a939de0eff01151c00a9c01c789b757b62eedfd"
SHA_ROUTES = "5feae661b3050916973c40ca7212fe13443c1ca87e9e6471b3cc2eda7deae468"
SHA_ARBRE = "2214cd183c8da7aff12a745044c5542f3a846eaa9dd13312005d3c70dba8f923"


class LecteurPage(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.presentation: str | None = None
        self.ordre: list[str] = []
        self.lignes: dict[str, dict[str, str]] = {}
        self.textes: list[str] = []
        self.alias_courant: str | None = None

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = {cle: valeur or "" for cle, valeur in attrs_list}
        if tag == "main":
            self.presentation = attrs.get("data-presentation")
        if tag == "li" and attrs.get("data-alias"):
            alias = attrs["data-alias"]
            self.alias_courant = alias
            self.ordre.append(alias)
            self.lignes[alias] = attrs
        if tag == "span" and self.alias_courant:
            classes = attrs.get("class", "").split()
            if "nom" in classes:
                self.lignes[self.alias_courant]["infobulle"] = attrs.get("title", "")
            if "barre" in classes:
                self.lignes[self.alias_courant]["style_barre"] = attrs.get("style", "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "li":
            self.alias_courant = None

    def handle_data(self, data: str) -> None:
        self.textes.append(data)


def empreinte(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def empreinte_arbre(racine: Path) -> str:
    digest = hashlib.sha256()
    for chemin in sorted(
        racine.rglob("*"),
        key=lambda path: path.relative_to(RACINE).as_posix().encode(),
    ):
        relatif = chemin.relative_to(RACINE).as_posix()
        if chemin.is_symlink():
            entree = f"L {os.readlink(chemin)}  {relatif}\n"
        elif chemin.is_dir():
            entree = f"D  {relatif}\n"
        elif chemin.is_file():
            entree = f"F {empreinte(chemin)}  {relatif}\n"
        else:
            return f"entrée-spéciale-inattendue:{relatif}"
        digest.update(entree.encode())
    return digest.hexdigest()


def ajouter(erreurs: list[str], condition: bool, message: str) -> None:
    if not condition:
        erreurs.append(message)


def normaliser_texte(morceaux: list[str]) -> str:
    return " ".join(" ".join(morceaux).split())


def verifier_sources(
    rapport: Path, routes: Path, erreurs: list[str]
) -> tuple[dict, dict]:
    ajouter(erreurs, rapport.resolve() == RAPPORT_ATTENDU.resolve(), "chemin du rapport inattendu")
    ajouter(erreurs, routes.resolve() == ROUTES_ATTENDUES.resolve(), "chemin des routes inattendu")
    ajouter(erreurs, rapport.is_file(), "rapport introuvable")
    ajouter(erreurs, routes.is_file(), "routes introuvables")
    if not rapport.is_file() or not routes.is_file():
        return {}, {}
    ajouter(erreurs, empreinte(rapport) == SHA_RAPPORT, "empreinte du rapport inattendue")
    ajouter(erreurs, empreinte(routes) == SHA_ROUTES, "empreinte des routes inattendue")
    ajouter(
        erreurs,
        empreinte_arbre(RAPPORT_ATTENDU.parent) == SHA_ARBRE,
        "empreinte de l’archive historique inattendue",
    )
    return (
        json.loads(rapport.read_text(encoding="utf-8")),
        json.loads(routes.read_text(encoding="utf-8")),
    )


def verifier_donnees(data: dict, routes: dict, erreurs: list[str]) -> None:
    conf = data.get("conformite") or {}
    contexte = data.get("measurement_context") or {}
    runs = data.get("runs") or []
    retenus = [run for run in runs if run.get("tentative_retenue") is True]
    ajouter(erreurs, contexte.get("task_version") == "task-v2", "task_version différente de task-v2")
    ajouter(erreurs, contexte.get("verify_version") == "verify-v3", "verify_version différente de verify-v3")
    ajouter(
        erreurs,
        contexte.get("protocol_version") == "benchmark-lab-x/protocol/v1",
        "protocol_version différente de benchmark-lab-x/protocol/v1",
    )
    ajouter(erreurs, conf.get("instrument_qualifie") is False, "instrument marqué qualifié")
    ajouter(erreurs, conf.get("page_validee") is False, "page marquée validée")
    ajouter(
        erreurs,
        len((conf.get("blocages") or {}).get("R-016") or []) == 7,
        "blocage R-016 différent de sept témoins",
    )
    ajouter(erreurs, len(data.get("candidats") or []) == 19, "compteur candidats différent de 19")
    ajouter(erreurs, len(runs) == 84, "compteur tentatives différent de 84")
    ajouter(erreurs, len(retenus) == 76, "compteur retenues différent de 76")
    ajouter(
        erreurs,
        (data.get("cycle_de_vie") or {}).get("prompts_partis") == 83,
        "compteur prompts fournisseur différent de 83",
    )
    ajouter(
        erreurs,
        sum(run.get("motif") == "metadonnees_route_inatteignables" for run in runs) == 1,
        "nombre de tentatives arrêtées avant fournisseur différent de un",
    )

    recommandations = {
        entree.get("modele"): entree.get("recommande")
        for entree in routes.get("modeles") or []
    }
    kimi = [run for run in retenus if run.get("alias") == "kimi-k3-max"]
    ajouter(erreurs, len(kimi) == 4, "nombre de runs Kimi retenus différent de quatre")
    ajouter(
        erreurs,
        {run.get("provider_pinned") for run in kimi} == {"moonshotai"},
        "pin historique Kimi différent de moonshotai",
    )
    ajouter(
        erreurs,
        {run.get("provider_served") for run in kimi} == {"Moonshot AI"},
        "provider servi Kimi différent de Moonshot AI",
    )
    ajouter(
        erreurs,
        recommandations.get("moonshotai/kimi-k3") == "wafer",
        "route recommandée Kimi différente de wafer",
    )


def verifier_page(data: dict, page: Path, erreurs: list[str]) -> None:
    ajouter(
        erreurs,
        Path(os.path.abspath(page)) == PAGE_ATTENDUE
        and page.resolve() == PAGE_ATTENDUE,
        "page historique hors de la sortie temporaire attendue",
    )
    ajouter(erreurs, page.is_file(), "page HTML introuvable")
    ajouter(erreurs, not page.is_symlink(), "page HTML liée symboliquement")
    if page.exists() and page.is_file() and not page.is_symlink():
        ajouter(erreurs, page.stat().st_nlink == 1, "page HTML liée physiquement")
    if not page.is_file():
        return
    contenu = page.read_text(encoding="utf-8")
    lecteur = LecteurPage()
    lecteur.feed(contenu)
    texte = normaliser_texte(lecteur.textes)
    texte_minuscule = texte.casefold()

    ajouter(
        erreurs,
        lecteur.presentation == "historique-reference-v2",
        "mode historique absent du HTML",
    )
    obligations = (
        "Campagne historique diagnostique 2026-08-06-reference-v2",
        "Instrument non qualifié",
        "page non validée",
        "blocage R-016",
        "Présentation interne, provisoire et non décisionnelle",
        "19 candidats",
        "76 runs attendus et retenus",
        "84 tentatives enregistrées",
        "83 prompts ayant atteint un fournisseur",
        "niveau retenu sur 51, pas un pourcentage de capacité",
        "Le niveau 43 ne prouve aucune tenue à 35, 55 ou 75 secondes",
        "R-016 ouvert",
        "producteur non aveugle au vérificateur",
        "La couverture indépendante n’est pas démontrée",
        "aucun reçu de couverture figé n’est consommé par cette page",
    )
    for attendu in obligations:
        ajouter(erreurs, attendu in texte, f"mention obligatoire absente : {attendu}")

    interdits = (
        "classement v0",
        "meilleur modèle",
        "témoins indépendants qualifiés",
        "couverture complète",
        "podium calibré",
        "le 0 reste opposable",
    )
    for interdit in interdits:
        ajouter(
            erreurs,
            interdit.casefold() not in texte_minuscule,
            f"formulation interdite présente : {interdit}",
        )

    candidats = [c for c in data["candidats"] if c.get("classable")]
    ordre_plan = {
        alias: index
        for index, alias in enumerate(data["conformite"]["plan"]["alias"])
    }
    candidats.sort(
        key=lambda c: (
            -(c.get("niveau_retenu") or 0),
            ordre_plan.get(c["alias"], len(ordre_plan)),
        )
    )
    ordre_attendu = [c["alias"] for c in candidats]
    ajouter(erreurs, lecteur.ordre == ordre_attendu, "ordre des lignes différent du niveau puis du plan")
    ajouter(erreurs, len(lecteur.lignes) == 19, "nombre de lignes HTML différent de 19")

    runs = data["runs"]
    for candidat in candidats:
        alias = candidat["alias"]
        ligne = lecteur.lignes.get(alias) or {}
        niveau = candidat.get("niveau_retenu") or 0
        rang = 1 + sum(
            1 for autre in candidats
            if (autre.get("niveau_retenu") or 0) > niveau
        )
        pct = 100 * niveau / data["paliers_total"]
        ajouter(erreurs, ligne.get("data-rang") == str(rang), f"rang faux pour {alias}")
        ajouter(erreurs, ligne.get("data-niveau") == str(niveau), f"niveau faux pour {alias}")
        ajouter(erreurs, ligne.get("data-pct") == f"{pct:.1f}", f"barre fausse pour {alias}")
        ajouter(
            erreurs,
            ligne.get("style_barre") == f"width:{pct:.1f}%",
            f"largeur de barre fausse pour {alias}",
        )
        infobulle = ligne.get("infobulle", "")
        siens = sorted(
            (
                run for run in runs
                if run.get("alias") == alias and run.get("tentative_retenue") is True
            ),
            key=lambda run: int(run["run"]),
        )
        ajouter(erreurs, [run["run"] for run in siens] == [1, 2, 3, 4], f"runs retenus incomplets pour {alias}")
        for run in siens:
            attendu = f"r{run['run']} = {run.get('niveau')} | frontière {run.get('frontiere')}"
            ajouter(erreurs, attendu in infobulle, f"chronologie absente pour {alias} {attendu}")

    kimi = lecteur.lignes.get("kimi-k3-max") or {}
    ajouter(erreurs, kimi.get("data-route-recommandee") == "wafer", "badge Kimi sans route wafer")
    ajouter(erreurs, kimi.get("data-route-epinglee") == "moonshotai", "badge Kimi sans pin moonshotai")
    ajouter(
        erreurs,
        "mention documentaire, non réparatrice" in kimi.get("infobulle", ""),
        "réserve non réparatrice absente de Kimi",
    )
    ajouter(
        erreurs,
        "r2 = 0 | frontière A1_api_totale | cause historique : "
        "borne de vérification de 180 s dépassée" in kimi.get("infobulle", ""),
        "cause du timeout Kimi r2 incorrecte",
    )
    ajouter(
        erreurs,
        all(
            "data-route-recommandee" not in ligne
            for alias, ligne in lecteur.lignes.items()
            if alias != "kimi-k3-max"
        ),
        "écart de route affiché sur un candidat autre que Kimi",
    )

    deepseek = lecteur.lignes.get("deepseek-v4-flash", {}).get("infobulle", "")
    minimax = lecteur.lignes.get("minimax-m3", {}).get("infobulle", "")
    mimo = lecteur.lignes.get("mimo-v2-5", {}).get("infobulle", "")
    ajouter(erreurs, "borne de vérification de 180 s dépassée" in deepseek, "timeout DeepSeek r1 absent")
    ajouter(
        erreurs,
        "r3 = 1 | frontière A1_api_totale | cause historique : échec de l’API totale, sans dépassement de la borne" in deepseek,
        "cause DeepSeek r3 incorrecte",
    )
    ajouter(erreurs, "r1 = 0 | frontière A0_page | cause historique : aucune page scoreable" in minimax, "cause MiniMax r1 incorrecte")
    ajouter(erreurs, all(f"r{run} = 0" not in mimo for run in range(1, 5)), "Mimo présenté avec un niveau 0")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapport", type=Path, required=True)
    ap.add_argument("--routes", type=Path, required=True)
    ap.add_argument("--page", type=Path, required=True)
    args = ap.parse_args()

    erreurs: list[str] = []
    try:
        data, routes = verifier_sources(args.rapport, args.routes, erreurs)
        if data and routes:
            verifier_donnees(data, routes, erreurs)
            verifier_page(data, args.page, erreurs)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        erreurs.append(f"exception de vérification : {exc}")

    if erreurs:
        for erreur in erreurs:
            print(f"FAIL: {erreur}", file=sys.stderr)
        return 1
    print("PASS: archive et vue historique reference-v2 conformes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
