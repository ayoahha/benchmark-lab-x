#!/usr/bin/env python3
"""Vérifie la fidélité de index.html aux sources versionnées.

Le script dérive chaque affirmation contractuelle attendue directement des
sources, indépendamment du générateur, puis la compare aux attributs
data-fait de la page. Toute divergence, tout fait inattendu ou toute
ressource externe fait échouer la vérification avec un code de sortie 1.
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

from generer_page import SOURCES, lire_sources, racine_canonique, repo_root  # noqa: E402

ETATS_NORMATIFS = ("INCONNU", "NON_DEFINI", "HARNESS_ERROR", "ABSTENTION")


def brut(valeur: Any) -> str:
    return valeur if isinstance(valeur, str) else json.dumps(valeur)


def attendus_depuis_sources(src: dict[str, Any]) -> dict[str, str]:
    """Dérive la carte complète des faits attendus, clé par clé, depuis les sources"""
    entrees = src["entrees_rapport"]
    faits_rapport = entrees["report_facts"]
    decision = faits_rapport["decision"]
    grok_r, kimi_r = faits_rapport["panel"]
    agrege = faits_rapport["aggregate"]
    table = src["table_metriques"]
    kimi_t = next(c for c in table["configurations"] if c["configuration_id"] == "kimi_k3_cursor_cli")
    panel = src["panel"]["panel"]
    grok_p, kimi_p = panel["configurations"]
    obs = src["recu_m8_2"]["direct_validation_observation"]
    portes = dict(obs["gates"])
    dossiers = src["manifeste_dossiers"]
    u025 = src["u025_racine"]
    matrice = src["u025_matrice"]
    liaisons_m7 = src["recu_m7_2"]["source_bindings"]
    budget = src["budget"]

    attendus: dict[str, Any] = {
        "conclusion": decision["conclusion"],
        "decision.recommandation": decision["recommendation"],
        "decision.gagnant": decision["winner"],
        "decision.score_global": decision["global_score"],
        "pareto.statut": faits_rapport["pareto"]["status"],
        "pareto.nombre_axes": len(faits_rapport["pareto"]["axes"]),
        "pareto.front_taille": len(faits_rapport["pareto"]["front"]),
        "abstention.nombre_raisons": len(decision["reasons"]),
        "grok.configuration": grok_r["configuration_id"],
        "grok.creneau": grok_r["planned_slot"],
        "grok.resultat": grok_r["official_outcome"],
        "grok.sortie": grok_r["candidate_output"],
        "grok.incident": grok_r["incident"],
        "grok.verdict_automatique": obs["status"],
        "grok.origine_echec": obs["origin"],
        "grok.porte.g005": portes["G-005"],
        "grok.porte.g001": portes["G-001"],
        "grok.acceptation": grok_r["official_acceptance_rate"]["exact_fraction"],
        "grok.couverture": grok_r["coverage"]["exact_fraction"],
        "grok.latence_ms": grok_r["latency_under_preregistered_rule_ms"],
        "grok.cout_total": grok_r["supplier_cost_total"],
        "grok.cout_par_acceptable": grok_r["supplier_cost_per_officially_acceptable_output"],
        "grok.identite_servie": grok_r["served_identity_and_provenance"],
        "grok.fraicheur": grok_r["freshness"],
        "grok.modele_demande": grok_p["model"]["value"],
        "grok.fournisseur": grok_p["provider"]["value"],
        "grok.route": grok_p["route"]["value"],
        "grok.raisonnement": grok_p["parameters"]["reasoning"]["value"],
        "kimi.configuration": kimi_r["configuration_id"],
        "kimi.creneau": kimi_r["planned_slot"],
        "kimi.resultat": kimi_r["official_outcome"],
        "kimi.sortie": kimi_r["candidate_output"],
        "kimi.incident": kimi_r["incident"],
        "kimi.acceptation": kimi_r["official_acceptance_rate"]["exact_fraction"],
        "kimi.couverture": kimi_r["coverage"]["exact_fraction"],
        "kimi.latence": kimi_r["latency_under_preregistered_rule_ms"],
        "kimi.duree_technique_ms": kimi_r["terminal_technical_elapsed_ms_excluded_from_pareto"],
        "kimi.duree_technique_exclue_pareto": kimi_t["latency"]["terminal_technical_elapsed_ms"]["excluded_from_pareto_axis"],
        "kimi.cout_total": kimi_r["supplier_cost_total"],
        "kimi.cout_par_acceptable": kimi_r["supplier_cost_per_officially_acceptable_output"],
        "kimi.identite_servie": kimi_r["served_identity_and_provenance"],
        "kimi.fraicheur": kimi_r["freshness"],
        "kimi.famille_demandee": kimi_p["model_family"]["value"],
        "kimi.slug_executable": kimi_p["executable_slug"]["value"],
        "kimi.fournisseur": kimi_p["provider"]["value"],
        "kimi.route": kimi_p["route"]["value"],
        "kimi.raisonnement": kimi_p["parameters"]["reasoning"]["value"],
        "agrege.acceptation": agrege["official_acceptance_rate"]["exact_fraction"],
        "agrege.couverture": agrege["coverage"]["exact_fraction"],
        "agrege.cout_total": agrege["supplier_cost_total"],
        "agrege.cout_par_acceptable": agrege["supplier_cost_per_officially_acceptable_output"],
        "agrege.effort_humain": agrege["human_effort"],
        "revue.dossiers_eligibles": dossiers["review_package"]["dossier_count"],
        "revue.exclusions": dossiers["review_package"]["exclusion_count"],
        "revue.decision_proprietaire": src["recu_m9_1"]["preparation_root"]["material"]["owner_decision"],
        "panel.id": panel["panel_id"],
        "panel.cardinalite": panel["cardinality"],
        "panel.ferme": panel["closed"],
        "panel.auto_router": src["panel"]["exclusions"]["auto_router"],
        "outillage.conclusion": u025["conclusion"],
        "outillage.dominance_effort": matrice["conclusions"]["effort_dominance"],
        "outillage.nombre_voies": len(u025["surviving_paths"]),
        "outillage.cas": matrice["common_inputs"]["case_count"],
        "outillage.projection_identique": matrice["p2_projection"]["equal_across_all_paths"],
        "budget.plafond_additionnel_usd": budget["requested"]["additional_spend_cap_usd"],
        "recu.grok": liaisons_m7["grok_receipt"]["content_address_sha256"],
        "recu.kimi": liaisons_m7["kimi_receipt"]["content_address_sha256"],
        "scope.base_git": entrees["scope"]["git_base"],
        "racine.m6_5": SOURCES["politique"]["sha256"],
        "racine.m6_6": SOURCES["manifeste_verrou"]["sha256"],
        "racine.m7_2": racine_canonique(src["recu_m7_2"]["reconciliation_root"]["material"], avec_lf=True),
        "racine.m8_2": racine_canonique(src["recu_m8_2"]["validation_root"]["material"], avec_lf=False),
        "racine.m9_1": racine_canonique(src["recu_m9_1"]["preparation_root"]["material"], avec_lf=False),
        "racine.m10_1": racine_canonique(src["recu_calcul"]["calculation_root"]["material"], avec_lf=False),
        "racine.m10_2": src["recu_reproduction"]["report_root"]["sha256"],
        "racine.u025": u025["root_sha256"],
    }
    for indice, axe in enumerate(faits_rapport["pareto"]["axes"], start=1):
        attendus[f"pareto.axe.{indice}"] = f"{axe['metric']}:{axe['direction']}"
    for indice, raison in enumerate(decision["reasons"], start=1):
        attendus[f"abstention.raison.{indice}"] = raison
    for indice, voie in enumerate(u025["surviving_paths"], start=1):
        attendus[f"outillage.voie.{indice}"] = voie
    return {cle: brut(valeur) for cle, valeur in attendus.items()}


def faits_de_la_page(page: str, erreurs: list[str]) -> dict[str, str]:
    observes: dict[str, str] = {}
    for cle, valeur in re.findall(r'data-fait="([^"]+)" data-valeur="([^"]*)"', page):
        cle, valeur = html.unescape(cle), html.unescape(valeur)
        if cle in observes and observes[cle] != valeur:
            erreurs.append(f"fait dupliqué avec valeurs contradictoires: {cle}")
        observes[cle] = valeur
    return observes


def verifier_structure(page: str, erreurs: list[str]) -> None:
    if '<html lang="fr">' not in page:
        erreurs.append("attribut lang=\"fr\" absent")
    for etat in ETATS_NORMATIFS:
        if etat not in page:
            erreurs.append(f"état normatif absent du texte: {etat}")
    for marqueur in ('id="futur" data-statut="PREVU_NON_EXISTANT"', 'id="historique" data-statut="NON_OFFICIEL"'):
        if marqueur not in page:
            erreurs.append(f"section marquée absente: {marqueur}")
    # page autonome : aucune ressource ni lien externe, aucune exécution de script
    for motif, libelle in (
        (r"<script\b", "balise script"),
        (r"<link\b", "balise link"),
        (r"<img\b", "balise img"),
        (r"\bsrc=", "attribut src"),
        (r'href="(?!#)', "lien non ancré"),
        (r"https?://", "URL externe"),
    ):
        if re.search(motif, page):
            erreurs.append(f"ressource ou lien externe interdit: {libelle}")


def main() -> None:
    script = Path(__file__).resolve()
    repo = repo_root(script.parent)
    chemin_page = script.parent / "index.html"
    if not chemin_page.is_file():
        raise SystemExit("FIDELITE_ECHEC: index.html absent, lancer generer_page.py d'abord")
    page = chemin_page.read_text(encoding="utf-8")

    erreurs: list[str] = []
    sources = lire_sources(repo)
    attendus = attendus_depuis_sources(sources)
    observes = faits_de_la_page(page, erreurs)

    for cle, valeur in attendus.items():
        if cle not in observes:
            erreurs.append(f"fait contractuel absent de la page: {cle}")
        elif observes[cle] != valeur:
            erreurs.append(f"divergence sur {cle}: page={observes[cle]!r} source={valeur!r}")
    for cle in observes:
        if cle not in attendus:
            erreurs.append(f"fait affiché sans source dérivée: {cle}")

    # les compteurs affichés bornent leurs listes : ni axe ni raison surnuméraire
    for prefixe, compteur in (("pareto.axe.", "pareto.nombre_axes"), ("abstention.raison.", "abstention.nombre_raisons"), ("outillage.voie.", "outillage.nombre_voies")):
        presents = sum(1 for cle in observes if cle.startswith(prefixe))
        if str(presents) != attendus[compteur]:
            erreurs.append(f"compte divergent pour {prefixe}*: page={presents} source={attendus[compteur]}")

    verifier_structure(page, erreurs)

    if erreurs:
        for erreur in erreurs:
            print(f"FIDELITE_ECHEC: {erreur}", file=sys.stderr)
        raise SystemExit(1)
    print(f"FIDELITE_OK {len(attendus)} faits contractuels conformes aux sources")


if __name__ == "__main__":
    main()
