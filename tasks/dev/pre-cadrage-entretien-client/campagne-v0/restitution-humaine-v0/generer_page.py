#!/usr/bin/env python3
"""Génère la restitution humaine V0 (index.html) depuis les preuves fusionnées.

La page restitue uniquement des faits déjà présents dans les sources
versionnées sous campagne-v0 et preuves-u025. Toute divergence entre une
source et une empreinte enregistrée arrête la génération.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

CV0 = "tasks/dev/pre-cadrage-entretien-client/campagne-v0"
U025 = "tasks/dev/pre-cadrage-entretien-client/preuves-u025"

# empreintes SHA-256 des octets exacts de chaque source lue
# recoupées avec les liaisons enregistrées dans les reçus fusionnés
SOURCES: dict[str, dict[str, str]] = {
    "politique": {"path": f"{CV0}/politique-decision-v1/politique-decision.json", "sha256": "c378f180f93cb9f2ad481137618a8cd1fe2077f97389283ab13567fe6b857000"},
    "panel": {"path": f"{CV0}/panel-identites-v1/panel-identites.json", "sha256": "c6d31dbc7953f3c21d9f5e3b5ff42d38b8171eab2e5dee52ecfb10920cc849d0"},
    "table_metriques": {"path": f"{CV0}/metriques-decision-m10-1-v1/table-metriques.json", "sha256": "3a8fd94da674a962619b08450a89381634aa5a5cdad5eeed742af5ea2566e6ab"},
    "recu_calcul": {"path": f"{CV0}/metriques-decision-m10-1-v1/recu-calcul.json", "sha256": "a3e12939dfb2b879c51220931fe58efb1354d2d89c5469c739fbfa8b68806fd0"},
    "entrees_rapport": {"path": f"{CV0}/rapport-decision-m10-2-v1/entrees-liees.json", "sha256": "72373a22dee6a40fe32ffcfcd203a87fb671c44adf75daaeae637555cd001dd6"},
    "rapport_interne": {"path": f"{CV0}/rapport-decision-m10-2-v1/rapport-interne.md", "sha256": "74ce0b9c67210fb5d1bdfe24d04a7db0c8abb861d54847eb96f737f112447c4e"},
    "recu_reproduction": {"path": f"{CV0}/rapport-decision-m10-2-v1/recu-reproduction.json", "sha256": "4557ac583b551c5e25a71e98db820f41555c2a2966a44f80223bb54ebb4f7c1a"},
    "recu_m7_2": {"path": f"{CV0}/reconciliation-m7-2-v1/recu-validation.json", "sha256": "463a6628d99452172a873ae545a55d1da545daf787675d553cb301230c960151"},
    "budget": {"path": f"{CV0}/reconciliation-m7-2-v1/registre-budgetaire.json", "sha256": "bd2192fc65888c4a7aa9a47b99025e162dd047e300274c09d95b43d77e16085a"},
    "inventaire": {"path": f"{CV0}/reconciliation-m7-2-v1/inventaire-acquisitions.json", "sha256": "49ca10966051c5dbbe11c4a7c55cbbd9d9d0cfecb1a5734689f36714c440ad9e"},
    "recu_m8_2": {"path": f"{CV0}/validation-automatique-m8-2-v1/recu-validation.json", "sha256": "f7e5f5f4218b2e5de6a71165f9ce18d7925c66cb0e18bc36b5c4683968d2799e"},
    "registre_couverture": {"path": f"{CV0}/validation-automatique-m8-2-v1/registre-couverture-verdicts.json", "sha256": "41829860e6a894d6e3a31a71fff5bc13604248d636a9e0c0d234b7012bebc362"},
    "recu_m9_1": {"path": f"{CV0}/preparation-revue-aveugle-m9-1-v1/recu-preparation.json", "sha256": "385f3959281cc66b792673bd7769a7bf98676edc98eb4c783b991a8075e036fb"},
    "manifeste_dossiers": {"path": f"{CV0}/preparation-revue-aveugle-m9-1-v1/manifeste-dossiers.json", "sha256": "9ca6fd591eb24cc5d0d23a7e0c270af73d4ab0e7398617605b66999a70e7e1d3"},
    "recu_m8_1": {"path": f"{CV0}/qualification-m8-1-v1/recu-qualification.json", "sha256": "dd23696a59cd390e8cddddeeb1065a036b460ebb9dcec03b2ed2931f64a98aa4"},
    "verrou": {"path": f"{CV0}/verrou-campagne-v1/verrou.json", "sha256": "b8ccf2ac10a7536700d3ab37f2989dcd8fa67b08592c387a57732199d4e0c102"},
    "manifeste_verrou": {"path": f"{CV0}/verrou-campagne-v1/manifeste-empreintes.json", "sha256": "94f796d167915d8e1ce9fd471b415eff468e8afda685955c1e757d29567b3918"},
    "u025_racine": {"path": f"{U025}/m3-12-consolidation-v1/proof-root.json", "sha256": "51b332acd2f449a721ab58fbc1269218c19ad41702936414602fc672fce29fb6"},
    "u025_matrice": {"path": f"{U025}/m3-12-consolidation-v1/matrix.json", "sha256": "00404881fcaff7b4ba1f42ec0275cc603cffd756f00731e880c9104db43c2926"},
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"HOLD_RESTITUTION: {message}")


def repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    raise SystemExit("HOLD_RESTITUTION: racine du dépôt introuvable")


def sha256_fichier(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def racine_canonique(objet: Any, avec_lf: bool) -> str:
    # forme canonique UTF-8, clés triées, séparateurs compacts (équivalent jq -cSj)
    blob = json.dumps(objet, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if avec_lf:
        blob += b"\n"
    return hashlib.sha256(blob).hexdigest()


def lire_sources(repo: Path) -> dict[str, Any]:
    charges: dict[str, Any] = {}
    for nom, binding in SOURCES.items():
        path = repo / binding["path"]
        require(path.is_file(), f"source absente: {binding['path']}")
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == binding["sha256"], f"empreinte divergente: {binding['path']}")
        if binding["path"].endswith(".md"):
            charges[nom] = raw.decode("utf-8")
        else:
            charges[nom] = json.loads(raw)
    return charges


def collecter_faits(repo: Path, src: dict[str, Any]) -> dict[str, Any]:
    politique, table, entrees = src["politique"], src["table_metriques"], src["entrees_rapport"]
    panel = src["panel"]["panel"]
    rapport = src["rapport_interne"]
    faits_rapport = entrees["report_facts"]
    decision = faits_rapport["decision"]

    # axes de Pareto identiques dans la politique M6.5, la table M10.1 et le rapport M10.2
    axes = politique["pareto"]["axes"]
    require(len(axes) == 3 and politique["pareto"]["axis_count"] == 3, "nombre d'axes inattendu")
    require(table["pareto"]["axes"] == axes and faits_rapport["pareto"]["axes"] == axes, "axes divergents entre M6.5, M10.1 et M10.2")
    require(table["pareto"]["status"] == faits_rapport["pareto"]["status"] == "FULL_THREE_AXIS_FRONT_NOT_COMPUTABLE", "statut Pareto divergent")
    require(table["pareto"]["front"] == [] and faits_rapport["pareto"]["front"] == [], "front de Pareto non vide")
    require(politique["pareto"]["global_score"] == "FORBIDDEN", "règle de score global divergente")

    # panel M6.3 et configurations M10.1 alignés
    configs_table = {c["configuration_id"]: c for c in table["configurations"]}
    ids_panel = [c["configuration_id"] for c in panel["configurations"]]
    require(sorted(configs_table) == sorted(ids_panel) == ["grok46_xai_build_oauth", "kimi_k3_cursor_cli"], "panel divergent")
    require(panel["closed"] is True and panel["cardinality"] == 2, "cardinalité du panel divergente")
    grok_panel, kimi_panel = panel["configurations"]
    grok_t, kimi_t = configs_table["grok46_xai_build_oauth"], configs_table["kimi_k3_cursor_cli"]
    grok_r, kimi_r = faits_rapport["panel"]

    # faits M10.2 et M10.1 alignés
    require(grok_r["official_outcome"] == grok_t["official_outcome"] == "CANDIDATE_NOT_ACCEPTABLE", "résultat Grok divergent")
    require(kimi_r["official_outcome"] == kimi_t["official_outcome"] == "HARNESS_ERROR", "résultat Kimi divergent")
    require(grok_r["official_acceptance_rate"]["exact_fraction"] == grok_t["official_acceptance_rate"]["exact_fraction"], "acceptation Grok divergente")
    require(kimi_r["official_acceptance_rate"]["state"] == kimi_t["official_acceptance_rate"]["state"] == "NON_DEFINI", "acceptation Kimi divergente")
    require(grok_r["latency_under_preregistered_rule_ms"] == grok_t["latency"]["pareto_axis"]["raw_singleton_ms"][0], "latence Grok divergente")
    require(kimi_t["latency"]["pareto_axis"]["state"] == "INCONNU", "latence Kimi divergente")
    require(kimi_t["latency"]["terminal_technical_elapsed_ms"]["value"] == kimi_r["terminal_technical_elapsed_ms_excluded_from_pareto"], "durée technique Kimi divergente")
    require(kimi_t["latency"]["terminal_technical_elapsed_ms"]["state"] == "OBSERVED", "état de la durée technique Kimi divergent")
    agrege_t, agrege_r = table["aggregate"], faits_rapport["aggregate"]
    require(agrege_t["official_acceptance_rate"]["exact_fraction"] == agrege_r["official_acceptance_rate"]["exact_fraction"], "acceptation agrégée divergente")
    require(agrege_t["coverage"]["exact_fraction"] == agrege_r["coverage"]["exact_fraction"], "couverture agrégée divergente")
    require(table["decision_outputs"] == {"global_score": decision["global_score"], "m10_2_recommendation": decision["recommendation"], "winner": decision["winner"]}, "sorties de décision divergentes")
    require(decision["conclusion"] == "ABSTENTION", "conclusion divergente")

    # le rapport interne publié porte la même conclusion et les mêmes raisons
    require("status: ABSTENTION" in rapport, "statut du rapport interne divergent")
    for raison in decision["reasons"]:
        require(f"`{raison}`" in rapport, f"raison absente du rapport interne: {raison}")

    # verdict automatique M8.2
    obs = src["recu_m8_2"]["direct_validation_observation"]
    require(src["recu_m8_2"]["verdict"] == "FAIL" and obs["status"] == "FAIL" and obs["origin"] == "CANDIDATE_ERROR", "verdict M8.2 divergent")
    portes = dict(obs["gates"])
    require(portes == {"G-005": True, "G-001": False}, "portes M8.2 divergentes")
    couverture = src["registre_couverture"]["coverage"]
    require(couverture["planned_output_coverage"] == agrege_t["coverage"]["exact_fraction"], "couverture M8.2 et M10.1 divergentes")

    # revue aveugle M9.1 sans dossier éligible
    dossiers = src["manifeste_dossiers"]
    require(dossiers["review_package"]["dossier_count"] == 0 and dossiers["review_package"]["exclusion_count"] == 2, "paquet de revue divergent")
    require(dossiers["aggregate_derivation"]["automatic_pass_eligible"]["count"] == 0, "éligibilité de revue divergente")
    decision_m9 = src["recu_m9_1"]["preparation_root"]["material"]["owner_decision"]

    # racines matérielles recomputées depuis les reçus
    racines = {
        "m6_5": SOURCES["politique"]["sha256"],
        "m6_6": SOURCES["manifeste_verrou"]["sha256"],
        "m7_2": racine_canonique(src["recu_m7_2"]["reconciliation_root"]["material"], avec_lf=True),
        "m8_2": racine_canonique(src["recu_m8_2"]["validation_root"]["material"], avec_lf=False),
        "m9_1": racine_canonique(src["recu_m9_1"]["preparation_root"]["material"], avec_lf=False),
        "m10_1": racine_canonique(src["recu_calcul"]["calculation_root"]["material"], avec_lf=False),
        "m10_2": src["recu_reproduction"]["report_root"]["sha256"],
    }
    require(racines["m7_2"] == src["recu_m7_2"]["reconciliation_root"]["sha256"], "racine M7.2 non reproduite")
    require(racines["m8_2"] == src["recu_m8_2"]["validation_root"]["sha256"], "racine M8.2 non reproduite")
    require(racines["m9_1"] == src["recu_m9_1"]["preparation_root"]["sha256"], "racine M9.1 non reproduite")
    require(racines["m10_1"] == src["recu_calcul"]["calculation_root"]["sha256"], "racine M10.1 non reproduite")
    require(table["authority_roots"]["M6.5"]["sha256"] == racines["m6_5"], "racine M6.5 divergente")
    require(table["authority_roots"]["M6.6"]["sha256"] == racines["m6_6"], "racine M6.6 divergente")
    require(table["authority_roots"]["M7.2"]["sha256"] == racines["m7_2"], "liaison M7.2 divergente")
    require(table["authority_roots"]["M8.2"]["sha256"] == racines["m8_2"], "liaison M8.2 divergente")
    require(table["authority_roots"]["M9.1"]["sha256"] == racines["m9_1"], "liaison M9.1 divergente")
    repro = src["recu_reproduction"]["report_root"]["material"]
    require(repro["reproducibility"]["two_run_byte_equality"] is True, "reproduction M10.2 non prouvée")
    require(repro["output_bindings"]["internal_report"]["sha256"] == SOURCES["rapport_interne"]["sha256"], "liaison du rapport interne divergente")

    # consolidation U-025 : racine recomputée sans le champ root_sha256
    u025 = src["u025_racine"]
    sans_racine = {k: v for k, v in u025.items() if k != "root_sha256"}
    require(racine_canonique(sans_racine, avec_lf=False) == u025["root_sha256"], "racine U-025 non reproduite")
    require(u025["matrix_sha256"] == SOURCES["u025_matrice"]["sha256"], "liaison matrice U-025 divergente")
    matrice = src["u025_matrice"]
    require(u025["conclusion"] == "INCONNU" and matrice["conclusions"]["INCONNU"]["established"] is True, "conclusion U-025 divergente")
    require(u025["surviving_paths"] == matrice["conclusions"]["surviving_paths"], "voies survivantes divergentes")
    require(len(u025["surviving_paths"]) == 3, "nombre de voies divergent")
    require(matrice["conclusions"]["effort_dominance"] == "INCONNU", "dominance d'effort divergente")
    require(matrice["p2_projection"]["equal_across_all_paths"] is True, "projection P2 divergente")

    # reçus d'acquisition M7.1 liés par M7.2, présents et conformes
    liaisons_m7 = src["recu_m7_2"]["source_bindings"]
    for cle in ("grok_receipt", "kimi_receipt"):
        chemin = repo / liaisons_m7[cle]["path"]
        require(chemin.is_file(), f"reçu d'acquisition absent: {liaisons_m7[cle]['path']}")
        require(sha256_fichier(chemin) == liaisons_m7[cle]["sha256"], f"reçu d'acquisition divergent: {liaisons_m7[cle]['path']}")

    # verrou M6.6 : prédécesseurs identiques aux sources épinglées
    predecesseurs = {p["milestone"]: p["sha256"] for p in src["verrou"]["predecessor_artifacts"]}
    require(predecesseurs["M6.5"] == racines["m6_5"] and predecesseurs["M6.3"] == SOURCES["panel"]["sha256"], "chaîne de prédécesseurs divergente")

    budget = src["budget"]
    require(budget["requested"]["additional_spend_cap_usd"] == 0, "plafond budgétaire divergent")
    require(budget["observed"]["total_monetary_observed_usd"] == "INCONNU", "coût observé divergent")

    faits: dict[str, Any] = {
        "conclusion": decision["conclusion"],
        "decision.recommandation": decision["recommendation"],
        "decision.gagnant": decision["winner"],
        "decision.score_global": decision["global_score"],
        "pareto.statut": faits_rapport["pareto"]["status"],
        "pareto.nombre_axes": len(axes),
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
        "grok.modele_demande": grok_panel["model"]["value"],
        "grok.fournisseur": grok_panel["provider"]["value"],
        "grok.route": grok_panel["route"]["value"],
        "grok.raisonnement": grok_panel["parameters"]["reasoning"]["value"],
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
        "kimi.famille_demandee": kimi_panel["model_family"]["value"],
        "kimi.slug_executable": kimi_panel["executable_slug"]["value"],
        "kimi.fournisseur": kimi_panel["provider"]["value"],
        "kimi.route": kimi_panel["route"]["value"],
        "kimi.raisonnement": kimi_panel["parameters"]["reasoning"]["value"],
        "agrege.acceptation": agrege_r["official_acceptance_rate"]["exact_fraction"],
        "agrege.couverture": agrege_r["coverage"]["exact_fraction"],
        "agrege.cout_total": agrege_r["supplier_cost_total"],
        "agrege.cout_par_acceptable": agrege_r["supplier_cost_per_officially_acceptable_output"],
        "agrege.effort_humain": agrege_r["human_effort"],
        "revue.dossiers_eligibles": dossiers["review_package"]["dossier_count"],
        "revue.exclusions": dossiers["review_package"]["exclusion_count"],
        "revue.decision_proprietaire": decision_m9,
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
        "racine.u025": u025["root_sha256"],
    }
    for indice, axe in enumerate(axes, start=1):
        faits[f"pareto.axe.{indice}"] = f"{axe['metric']}:{axe['direction']}"
    for indice, raison in enumerate(decision["reasons"], start=1):
        faits[f"abstention.raison.{indice}"] = raison
    for indice, voie in enumerate(u025["surviving_paths"], start=1):
        faits[f"outillage.voie.{indice}"] = voie
    for cle, valeur in racines.items():
        faits[f"racine.{cle}"] = valeur
    return faits


def brut(valeur: Any) -> str:
    return valeur if isinstance(valeur, str) else json.dumps(valeur)


def fait(cle: str, valeur: Any, affichage: str | None = None) -> str:
    texte = html.escape(affichage) if affichage is not None else html.escape(brut(valeur))
    return f'<span data-fait="{html.escape(cle)}" data-valeur="{html.escape(brut(valeur))}">{texte}</span>'


def ms_lisible(ms: int) -> str:
    minutes, secondes = divmod(round(ms / 1000), 60)
    if minutes:
        return f"{minutes} min {secondes} s"
    return f"{ms / 1000:.1f} s".replace(".", ",")


def nombre_fr(valeur: int) -> str:
    return f"{valeur:,}".replace(",", " ")


STYLE = """
:root { --encre: #1d1f24; --sourdine: #565b66; --papier: #faf9f6; --carte: #ffffff;
  --trait: #d9d6cf; --accent: #7a3e00; --accent-doux: #f6ead9; --neutre: #eceef1; }
* { box-sizing: border-box; }
body { margin: 0 auto; padding: 1.5rem 1.25rem 3rem; max-width: 62rem; color: var(--encre);
  background: var(--papier); font: 1rem/1.55 system-ui, -apple-system, "Segoe UI", sans-serif; }
h1 { font-size: 1.7rem; line-height: 1.25; margin: 0.25rem 0 0.5rem; }
h2 { font-size: 1.25rem; margin: 2.4rem 0 0.7rem; padding-bottom: 0.3rem; border-bottom: 1px solid var(--trait); }
h3 { font-size: 1.05rem; margin: 1.4rem 0 0.4rem; }
p, li, dd { max-width: 52rem; }
code { font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 0.86em;
  background: var(--neutre); padding: 0.08em 0.3em; border-radius: 4px; overflow-wrap: anywhere; }
a { color: var(--accent); }
.surtitre { color: var(--sourdine); font-size: 0.85rem; letter-spacing: 0.04em;
  text-transform: uppercase; margin: 0; }
.verdict { display: inline-block; margin: 0.6rem 0 0.2rem; padding: 0.5rem 0.9rem;
  border: 2px solid var(--accent); border-radius: 8px; background: var(--accent-doux);
  font-size: 1.15rem; }
.verdict strong { color: var(--accent); letter-spacing: 0.03em; }
nav.sommaire { margin: 1.2rem 0 0; font-size: 0.92rem; }
nav.sommaire ol { margin: 0.3rem 0 0; padding-left: 1.2rem; columns: 2; column-gap: 2.5rem; }
nav.sommaire li { margin: 0.15rem 0; }
.cartes { display: grid; grid-template-columns: repeat(auto-fit, minmax(11.5rem, 1fr));
  gap: 0.8rem; margin: 1.2rem 0; padding: 0; list-style: none; }
.cartes li { background: var(--carte); border: 1px solid var(--trait); border-radius: 8px;
  padding: 0.8rem 0.9rem; }
.cartes .valeur { display: block; font-size: 1.35rem; font-weight: 700; margin-bottom: 0.15rem; }
.cartes .legende { color: var(--sourdine); font-size: 0.86rem; }
.duo { display: grid; grid-template-columns: repeat(auto-fit, minmax(19rem, 1fr)); gap: 1rem; }
.bloc { background: var(--carte); border: 1px solid var(--trait); border-radius: 8px;
  padding: 0.9rem 1.1rem; }
.bloc h3 { margin-top: 0.2rem; }
.badge { display: inline-block; padding: 0.1em 0.55em; border-radius: 999px;
  font-size: 0.78rem; font-weight: 600; letter-spacing: 0.02em; vertical-align: middle; }
.badge-etat { background: var(--encre); color: var(--papier); }
.badge-inconnu { background: var(--neutre); color: var(--encre); border: 1px solid var(--trait); }
.badge-prevu { background: transparent; color: var(--accent); border: 2px dashed var(--accent); }
.badge-nonofficiel { background: var(--sourdine); color: var(--papier); }
table { width: 100%; border-collapse: collapse; margin: 0.8rem 0; font-size: 0.94rem; }
caption { text-align: left; color: var(--sourdine); font-size: 0.86rem; padding-bottom: 0.4rem; }
th, td { text-align: left; vertical-align: top; padding: 0.5rem 0.6rem; border-bottom: 1px solid var(--trait); }
thead th { border-bottom: 2px solid var(--encre); }
.table-roule { overflow-x: auto; }
dl.etats dt { font-weight: 700; margin-top: 0.9rem; }
dl.etats dd { margin: 0.15rem 0 0 0; color: var(--encre); }
ul.permis, ul.interdit { list-style: none; padding: 0; }
ul.permis li, ul.interdit li { margin: 0.45rem 0; padding: 0.45rem 0.7rem; border-left: 4px solid; border-radius: 4px; }
ul.permis li { border-color: #2e6e3e; background: #eef5ef; }
ul.interdit li { border-color: #96332b; background: #f8eeed; }
section[data-statut] { border: 2px dashed var(--trait); border-radius: 8px;
  padding: 0.2rem 1.1rem 0.9rem; margin-top: 2.4rem; }
section[data-statut] h2 { border-bottom: none; margin-top: 1rem; }
footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--trait);
  color: var(--sourdine); font-size: 0.88rem; }
footer code { font-size: 0.8rem; }
details { margin: 0.6rem 0; }
summary { cursor: pointer; color: var(--accent); }
.note { color: var(--sourdine); font-size: 0.88rem; }
"""


def rendre_html(f: dict[str, Any]) -> str:
    axes_libelles = {
        "OFFICIAL_ACCEPTANCE_RATE": "le taux de sorties officiellement acceptables",
        "SUPPLIER_COST_PER_OFFICIALLY_ACCEPTABLE_OUTPUT": "le coût fournisseur par sortie officiellement acceptable",
        "LATENCY_UNDER_PREREGISTERED_RULE": "la latence selon la règle préenregistrée",
    }
    directions = {"MAXIMIZE": "à maximiser", "MINIMIZE": "à minimiser"}
    axes_html = []
    for indice in range(1, f["pareto.nombre_axes"] + 1):
        metrique, direction = f[f"pareto.axe.{indice}"].split(":")
        axes_html.append(
            f"<li>{axes_libelles[metrique]}, {directions[direction]} "
            f"({fait(f'pareto.axe.{indice}', f[f'pareto.axe.{indice}'], metrique)})</li>"
        )

    raisons_explications = {
        "INCOMPLETE_COVERAGE": "la couverture est incomplète : un des deux créneaux prévus, celui de Kimi, n'a produit aucun résultat jugeable",
        "SERVED_IDENTITY_PROVENANCE_INCONNU": "le modèle réellement servi, sa route et ses paramètres effectifs n'ont été observés pour aucune des deux configurations",
        "FRESHNESS_INCONNU": "la fraîcheur des faits d'identité et de prix n'a pas pu être observée",
        "SUPPLIER_COST_TOTAL_INCONNU": "aucun coût fournisseur n'a été observé, et aucune valeur de remplacement n'est imputée",
        "SUPPLIER_COST_PER_OFFICIALLY_ACCEPTABLE_OUTPUT_NON_DEFINI": "avec zéro sortie acceptable, le coût par sortie acceptable est mathématiquement indéfini",
        "LATENCY_KIMI_INCONNU": "sans sortie complète de Kimi, sa latence sous la règle préenregistrée n'existe pas",
        "ABSENT_OR_NON_DECISIVE_OWNER_PREFERENCE": "aucune préférence propriétaire explicite n'a été fournie pour arbitrer entre plusieurs axes",
    }
    raisons_html = []
    for indice in range(1, f["abstention.nombre_raisons"] + 1):
        code = f[f"abstention.raison.{indice}"]
        explication = raisons_explications.get(code, "raison enregistrée dans le rapport M10.2")
        raisons_html.append(f"<li><code>{fait(f'abstention.raison.{indice}', code)}</code><br>{explication}</li>")

    voies_libelles = {
        "PROMPTFOO_0_122_0": "Promptfoo 0.122.0",
        "ORI_0_7_0_F411E1A": "Ori 0.7.0+f411e1a",
        "METHODE_MANUELLE_CONTROLEE": "Méthode manuelle contrôlée",
    }
    voies_html = "".join(
        f"<li>{voies_libelles[f[f'outillage.voie.{i}']]} "
        f"(<code>{fait(f'outillage.voie.{i}', f[f'outillage.voie.{i}'])}</code>)</li>"
        for i in range(1, f["outillage.nombre_voies"] + 1)
    )

    racines_lignes = [
        ("Politique de décision M6.5", f"{CV0}/politique-decision-v1/politique-decision.json", "racine.m6_5"),
        ("Verrou de campagne M6.6", f"{CV0}/verrou-campagne-v1/manifeste-empreintes.json", "racine.m6_6"),
        ("Réconciliation des acquisitions M7.2", f"{CV0}/reconciliation-m7-2-v1/recu-validation.json", "racine.m7_2"),
        ("Validation automatique M8.2", f"{CV0}/validation-automatique-m8-2-v1/recu-validation.json", "racine.m8_2"),
        ("Préparation de revue aveugle M9.1", f"{CV0}/preparation-revue-aveugle-m9-1-v1/recu-preparation.json", "racine.m9_1"),
        ("Table des métriques M10.1", f"{CV0}/metriques-decision-m10-1-v1/recu-calcul.json", "racine.m10_1"),
        ("Rapport de décision M10.2", f"{CV0}/rapport-decision-m10-2-v1/recu-reproduction.json", "racine.m10_2"),
        ("Consolidation outillage U-025", f"{U025}/m3-12-consolidation-v1/proof-root.json", "racine.u025"),
    ]
    racines_html = "".join(
        f"<tr><th scope=\"row\">{titre}</th><td><code>{chemin}</code></td>"
        f"<td><code>{fait(cle, f[cle])}</code></td></tr>"
        for titre, chemin, cle in racines_lignes
    )

    grok_latence = ms_lisible(f["grok.latence_ms"])
    kimi_duree = ms_lisible(f["kimi.duree_technique_ms"])

    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Restitution humaine V0 : campagne de pré-cadrage, conclusion ABSTENTION</title>
<!-- style_gate: pass -->
<!-- page générée par generer_page.py : ne pas éditer à la main -->
<style>{STYLE}</style>
</head>
<body>
<header>
  <p class="surtitre">Benchmark Lab-X · pilote V0 · page locale, hors ligne</p>
  <h1>Restitution humaine de la campagne V0</h1>
  <p class="verdict">Conclusion officielle : <strong>{fait("conclusion", f["conclusion"])}</strong></p>
  <p>La campagne V0 a été menée jusqu'au rapport de décision M10.2 et s'est conclue par une abstention.
  Les preuves disponibles ne permettent de désigner ni gagnant, ni score, ni recommandation.
  Cette page reprend uniquement des faits déjà enregistrés dans les sources versionnées du dépôt ;
  elle n'en crée aucun. Chaque valeur affichée est traçable vers sa source dans la
  <a href="#provenance">section provenance</a>.</p>
</header>

<nav class="sommaire" aria-label="Sommaire">
  <strong>Sommaire</strong>
  <ol>
    <li><a href="#essentiel">L'essentiel</a></li>
    <li><a href="#question">La question V0 et le workflow testé</a></li>
    <li><a href="#deux-etudes">Deux études distinctes</a></li>
    <li><a href="#panel">Le panel officiel</a></li>
    <li><a href="#resultats">Les résultats officiels</a></li>
    <li><a href="#etats">Ce que veulent dire les états</a></li>
    <li><a href="#pareto">Les trois axes de Pareto</a></li>
    <li><a href="#abstention">Pourquoi l'abstention</a></li>
    <li><a href="#conclusions">Conclusions permises et interdites</a></li>
    <li><a href="#provenance">Provenance et racines de preuve</a></li>
    <li><a href="#futur">Parcours prévu</a></li>
    <li><a href="#historique">Essais historiques</a></li>
  </ol>
</nav>

<main>
<section id="essentiel" aria-label="L'essentiel">
  <ul class="cartes">
    <li><span class="valeur">{fait("agrege.acceptation", f["agrege.acceptation"], "0 sur 1")}</span>
      <span class="legende">sortie officiellement acceptable observée sur le panel</span></li>
    <li><span class="valeur">{fait("agrege.couverture", f["agrege.couverture"], "1 sur 2")}</span>
      <span class="legende">créneaux de mesure couverts par le harnais</span></li>
    <li><span class="valeur">{fait("agrege.cout_total", f["agrege.cout_total"])}</span>
      <span class="legende">coût fournisseur total observé</span></li>
    <li><span class="valeur">{fait("revue.dossiers_eligibles", f["revue.dossiers_eligibles"], "0")}</span>
      <span class="legende">dossier éligible à la revue humaine aveugle</span></li>
  </ul>
</section>

<section id="question">
  <h2>La question V0 et le workflow testé</h2>
  <p>Benchmark Lab-X répond à une question pratique : sur le workflow exact du besoin,
  combien coûte en pratique une sortie acceptable, et quelle configuration choisir ?</p>
  <p>Le pilote V0 porte sur un seul workflow : préparer un pré-cadrage avant un entretien
  client, pour une activité de conseil en IA et cybersécurité auprès de PME. Le scénario est
  entièrement synthétique. Le candidat reçoit des notes brutes et doit produire un
  pré-cadrage structuré, soumis ensuite à la revue d'un consultant.</p>
  <p>Une sortie est <strong>officiellement acceptable</strong> quand deux conditions sont
  réunies : les contrôles automatiques rendent <code>PASS</code> sur les propriétés décidables
  par code, puis une revue humaine aveugle rend <code>ACCEPTABLE</code> sur la fidélité
  sémantique et l'utilité métier.</p>
</section>

<section id="deux-etudes">
  <h2>Deux études distinctes, à ne pas confondre</h2>
  <div class="duo">
    <div class="bloc">
      <h3>Étude d'outillage (U-025)</h3>
      <p>Elle compare des <strong>façons d'exécuter la mesure</strong>, jamais des modèles.
      {fait("outillage.nombre_voies", f["outillage.nombre_voies"], "Trois")} voies d'outillage
      ont été éprouvées sur 16 cas de fixtures :</p>
      <ul>{voies_html}</ul>
      <p>Ces trois voies ont produit une projection strictement identique
      ({fait("outillage.projection_identique", f["outillage.projection_identique"], "projection identique")}
      sur {fait("outillage.cas", f["outillage.cas"])} cas), ce qui prouve leur fidélité mutuelle
      sur fixtures. La conclusion d'outillage reste
      <code>{fait("outillage.conclusion", f["outillage.conclusion"])}</code> : aucune voie n'est
      éliminée, aucune n'est déclarée gagnante, et la dominance d'effort reste
      <code>{fait("outillage.dominance_effort", f["outillage.dominance_effort"])}</code>.</p>
      <p class="note">Promptfoo, Ori et la méthode manuelle sont des outils de mesure.
      Ils n'apparaissent dans aucun classement et ne sont pas des candidats évalués.</p>
    </div>
    <div class="bloc">
      <h3>Comparaison de configurations (campagne V0)</h3>
      <p>Elle compare des <strong>configurations candidates</strong> d'un panel figé, décrit
      ci-dessous. C'est cette comparaison qui devait produire la décision V0, et c'est elle
      qui se conclut par l'abstention.</p>
      <p>Les deux études sont indépendantes : l'étude d'outillage ne dit rien de la qualité
      des modèles, et la campagne ne dit rien de la supériorité d'un outil.</p>
    </div>
  </div>
</section>

<section id="panel">
  <h2>Le panel officiel</h2>
  <p>Le panel <code>{fait("panel.id", f["panel.id"])}</code> est
  {fait("panel.ferme", f["panel.ferme"], "fermé")} et compte exactement
  {fait("panel.cardinalite", f["panel.cardinalite"], "deux")} configurations. OpenRouter Auto
  Router est exclu du panel V0 ({fait("panel.auto_router", f["panel.auto_router"], "exclu")}),
  et aucun canari OpenRouter n'était donc applicable.</p>
  <div class="table-roule">
  <table>
    <caption>Identités demandées et décidées du panel. « Demandé » n'est jamais « servi » :
    l'identité réellement servie reste INCONNU pour les deux configurations.</caption>
    <thead>
      <tr><th scope="col">Configuration</th><th scope="col">Modèle demandé</th>
      <th scope="col">Fournisseur et route (décidés)</th><th scope="col">Raisonnement</th>
      <th scope="col">Identité servie (observée)</th></tr>
    </thead>
    <tbody>
      <tr>
        <th scope="row">Grok 4.6<br><code>{fait("grok.configuration", f["grok.configuration"])}</code></th>
        <td>{fait("grok.modele_demande", f["grok.modele_demande"])}</td>
        <td><code>{fait("grok.fournisseur", f["grok.fournisseur"])}</code><br><code>{fait("grok.route", f["grok.route"])}</code></td>
        <td><code>{fait("grok.raisonnement", f["grok.raisonnement"])}</code></td>
        <td><span class="badge badge-inconnu">{fait("grok.identite_servie", f["grok.identite_servie"])}</span></td>
      </tr>
      <tr>
        <th scope="row">Kimi K3<br><code>{fait("kimi.configuration", f["kimi.configuration"])}</code></th>
        <td>famille {fait("kimi.famille_demandee", f["kimi.famille_demandee"])}, slug exécutable <code>{fait("kimi.slug_executable", f["kimi.slug_executable"])}</code></td>
        <td><code>{fait("kimi.fournisseur", f["kimi.fournisseur"])}</code><br><code>{fait("kimi.route", f["kimi.route"])}</code></td>
        <td><code>{fait("kimi.raisonnement", f["kimi.raisonnement"])}</code></td>
        <td><span class="badge badge-inconnu">{fait("kimi.identite_servie", f["kimi.identite_servie"])}</span></td>
      </tr>
    </tbody>
  </table>
  </div>
</section>

<section id="resultats">
  <h2>Les résultats officiels</h2>

  <h3>Grok 4.6 : une sortie produite, rejetée par les contrôles automatiques</h3>
  <p>L'acquisition <code>{fait("grok.creneau", f["grok.creneau"])}</code> a produit une sortie
  candidate ({fait("grok.sortie", f["grok.sortie"], "disponible puis automatiquement rejetée")}).
  Le validateur automatique a rendu {fait("grok.verdict_automatique", f["grok.verdict_automatique"])} :
  le contrôle <code>G-005</code> est {fait("grok.porte.g005", f["grok.porte.g005"], "conforme")},
  le contrôle <code>G-001</code> est {fait("grok.porte.g001", f["grok.porte.g001"], "non conforme")},
  et l'origine de l'échec est la sortie candidate elle-même
  (<code>{fait("grok.origine_echec", f["grok.origine_echec"])}</code>). L'état officiel est donc
  <code>{fait("grok.resultat", f["grok.resultat"])}</code>. La latence mesurée sous la règle
  préenregistrée est de {fait("grok.latence_ms", f["grok.latence_ms"], nombre_fr(f["grok.latence_ms"]) + " ms")},
  soit environ {grok_latence}. L'incident consigné est
  <code>{fait("grok.incident", f["grok.incident"])}</code> : l'identité servie n'a pas été observée.</p>

  <h3>Kimi K3 : une panne du harnais, aucune sortie</h3>
  <p>L'acquisition <code>{fait("kimi.creneau", f["kimi.creneau"])}</code> s'est terminée en
  <code>{fait("kimi.resultat", f["kimi.resultat"])}</code> : le harnais de mesure est tombé en
  panne. La sortie candidate est {fait("kimi.sortie", f["kimi.sortie"], "absente et n'a pas été reconstruite")}.
  Les sources fusionnées consignent l'incident ({fait("kimi.incident", f["kimi.incident"], "HARNESS_ERROR")})
  sans en détailler la cause ; le contact fournisseur et l'appel modèle restent INCONNU.
  La durée technique terminale de
  {fait("kimi.duree_technique_ms", f["kimi.duree_technique_ms"], nombre_fr(f["kimi.duree_technique_ms"]) + " ms")}
  (environ {kimi_duree}) décrit la panne, pas une latence de service : elle est
  {fait("kimi.duree_technique_exclue_pareto", f["kimi.duree_technique_exclue_pareto"], "exclue")}
  de l'axe de latence. Cette panne est un défaut du harnais : elle compte comme couverture
  incomplète et n'est pas imputée à la configuration Kimi.</p>

  <h3>Métriques officielles</h3>
  <div class="table-roule">
  <table>
    <caption>Faits repris tels quels de la table M10.1 et du rapport M10.2. Aucune valeur
    absente n'est remplacée.</caption>
    <thead>
      <tr><th scope="col">Configuration</th><th scope="col">Acceptation officielle</th>
      <th scope="col">Couverture</th><th scope="col">Coût fournisseur total</th>
      <th scope="col">Coût par sortie acceptable</th><th scope="col">Latence préenregistrée</th></tr>
    </thead>
    <tbody>
      <tr>
        <th scope="row">Grok 4.6</th>
        <td>{fait("grok.acceptation", f["grok.acceptation"])}</td>
        <td>{fait("grok.couverture", f["grok.couverture"])}</td>
        <td><span class="badge badge-inconnu">{fait("grok.cout_total", f["grok.cout_total"])}</span></td>
        <td><span class="badge badge-inconnu">{fait("grok.cout_par_acceptable", f["grok.cout_par_acceptable"])}</span></td>
        <td>{nombre_fr(f["grok.latence_ms"])} ms</td>
      </tr>
      <tr>
        <th scope="row">Kimi K3</th>
        <td><span class="badge badge-inconnu">{fait("kimi.acceptation", f["kimi.acceptation"])}</span></td>
        <td>{fait("kimi.couverture", f["kimi.couverture"])}</td>
        <td><span class="badge badge-inconnu">{fait("kimi.cout_total", f["kimi.cout_total"])}</span></td>
        <td><span class="badge badge-inconnu">{fait("kimi.cout_par_acceptable", f["kimi.cout_par_acceptable"])}</span></td>
        <td><span class="badge badge-inconnu">{fait("kimi.latence", f["kimi.latence"])}</span></td>
      </tr>
      <tr>
        <th scope="row">Panel agrégé</th>
        <td>0/1</td>
        <td>1/2</td>
        <td><span class="badge badge-inconnu">INCONNU</span></td>
        <td><span class="badge badge-inconnu">{fait("agrege.cout_par_acceptable", f["agrege.cout_par_acceptable"])}</span></td>
        <td>non agrégée</td>
      </tr>
    </tbody>
  </table>
  </div>
  <p>La fraîcheur des faits d'identité et de prix reste
  <span class="badge badge-inconnu">{fait("grok.fraicheur", f["grok.fraicheur"])}</span> pour Grok
  comme pour Kimi (<span class="badge badge-inconnu">{fait("kimi.fraicheur", f["kimi.fraicheur"])}</span>).
  L'effort humain est consigné séparément du coût fournisseur et reste
  <span class="badge badge-inconnu">{fait("agrege.effort_humain", f["agrege.effort_humain"])}</span>
  sur ses sept composantes. Le plafond de dépense additionnelle de la campagne était de
  {fait("budget.plafond_additionnel_usd", f["budget.plafond_additionnel_usd"])}&nbsp;USD :
  aucun achat ni allocation d'abonnement n'était autorisé, et le coût réellement encouru
  sur les routes utilisées n'a pas pu être observé.</p>

  <h3>Revue humaine aveugle : zéro dossier éligible</h3>
  <p>Seules les sorties avec un <code>PASS</code> automatique sont éligibles à la revue
  humaine aveugle. La sortie Grok a échoué aux contrôles et la sortie Kimi n'existe pas :
  les {fait("revue.exclusions", f["revue.exclusions"], "deux")} créneaux ont été exclus et le
  paquet de revue compte zéro dossier. La décision propriétaire correspondante est
  <code>{fait("revue.decision_proprietaire", f["revue.decision_proprietaire"])}</code>.
  Aucun verdict humain n'a donc été rendu, et aucun n'a été simulé.</p>
</section>

<section id="etats">
  <h2>Ce que veulent dire les états affichés</h2>
  <p>Les quatre premiers états sont normatifs : ils restent littéraux dans tout le dossier
  V0 et ne sont jamais convertis en valeur de remplacement. Le dernier est un résultat
  officiel du contrat.</p>
  <dl class="etats">
    <dt><code>INCONNU</code></dt>
    <dd>La valeur n'a pas été observée. Ce n'est ni zéro, ni un échec, ni une estimation :
    c'est une absence d'observation, conservée telle quelle.</dd>
    <dt><code>NON_DEFINI</code></dt>
    <dd>La métrique n'existe pas mathématiquement dans cette situation. Exemple : un coût
    par sortie acceptable ne peut pas être calculé quand zéro sortie est acceptable.</dd>
    <dt><code>HARNESS_ERROR</code></dt>
    <dd>Le harnais de mesure est tombé en panne. La configuration testée n'est pas fautive :
    l'incident compte comme un trou de couverture, pas comme un échec du candidat.</dd>
    <dt><code>ABSTENTION</code></dt>
    <dd>Les preuves sont insuffisantes pour décider. Lab-X refuse alors de désigner un
    gagnant plutôt que de fabriquer une conclusion.</dd>
    <dt><code>CANDIDATE_NOT_ACCEPTABLE</code></dt>
    <dd>La sortie existe mais a échoué aux contrôles automatiques du contrat. C'est un
    résultat officiel, décidable, qui compte dans la couverture.</dd>
  </dl>
</section>

<section id="pareto">
  <h2>Les trois axes de Pareto</h2>
  <p>La politique de décision M6.5 verrouille exactement
  {fait("pareto.nombre_axes", f["pareto.nombre_axes"], "trois")} axes :</p>
  <ol>{"".join(axes_html)}</ol>
  <p>La couverture n'est pas un axe : elle conditionne l'éligibilité des configurations.
  Le budget n'est pas un axe non plus. Un score global est interdit
  (<code>{fait("decision.score_global", f["decision.score_global"])}</code>).</p>
  <p>Statut du front : <code>{fait("pareto.statut", f["pareto.statut"])}</code>.
  Le coût par sortie acceptable est NON_DEFINI pour les deux configurations et la latence
  Kimi est INCONNU : le front complet à trois axes ne peut pas être calculé, et le front
  publié est vide ({fait("pareto.front_taille", f["pareto.front_taille"], "0")} point).</p>
</section>

<section id="abstention">
  <h2>Pourquoi l'abstention</h2>
  <p>L'abstention est imposée par
  {fait("abstention.nombre_raisons", f["abstention.nombre_raisons"], "sept")} preuves manquantes
  ou insuffisantes, énumérées telles quelles dans le rapport M10.2 :</p>
  <ol>{"".join(raisons_html)}</ol>
  <p>Le rapport M10.2 nomme trois actions humaines possibles, sans valeur de remplacement :
  conserver l'abstention ; autoriser séparément une future collecte des preuves manquantes ;
  fournir séparément une préférence propriétaire explicite, seulement après obtention de
  trois axes complets et comparables.</p>
</section>

<section id="conclusions">
  <h2>Ce que ces preuves permettent, et interdisent, de conclure</h2>
  <h3>Conclusions permises par les preuves actuelles</h3>
  <ul class="permis">
    <li>La chaîne de mesure V0 a fonctionné de bout en bout sur une acquisition : sortie
    produite, contrôles automatiques exécutés, verdict rendu, reçus et racines de preuve
    enregistrés.</li>
    <li>Aucune sortie officiellement acceptable n'a été observée sur le panel (0 sur 1
    décidable).</li>
    <li>Le créneau Kimi n'est pas couvert : le harnais est tombé en panne avant toute sortie,
    et la couverture du panel s'établit à 1 sur 2.</li>
    <li>La revue humaine aveugle n'a reçu aucun dossier, car aucune sortie n'a passé les
    contrôles automatiques.</li>
    <li>Les trois voies d'outillage restent survivantes et fidèles entre elles sur fixtures ;
    aucune n'est éliminée.</li>
  </ul>
  <h3>Conclusions interdites, car sans preuve</h3>
  <ul class="interdit">
    <li>Désigner un gagnant ou un perdant : le rapport enregistre
    <code>{fait("decision.gagnant", f["decision.gagnant"])}</code>.</li>
    <li>Recommander une configuration : le rapport enregistre
    <code>{fait("decision.recommandation", f["decision.recommandation"])}</code>.</li>
    <li>Produire un score global ou un classement, explicitement interdits par la politique.</li>
    <li>Juger la qualité générale de Grok 4.6 ou de Kimi K3 : un seul essai par
    configuration ne prouve que la faisabilité, jamais une généralisation.</li>
    <li>Traiter le HARNESS_ERROR de Kimi comme un échec du modèle Kimi.</li>
    <li>Convertir INCONNU ou NON_DEFINI en zéro, en échec ou en estimation.</li>
    <li>Classer Promptfoo, Ori ou la méthode manuelle entre eux : leur comparaison
    d'effort reste INCONNU.</li>
  </ul>
</section>

<section id="provenance">
  <h2>Provenance et racines de preuve</h2>
  <p>Chaque fait de cette page provient d'un fichier versionné du dépôt, à la base git
  <code>{fait("scope.base_git", f["scope.base_git"])}</code> pour le rapport M10.2. Les racines
  SHA-256 ci-dessous scellent chaque jalon ; le script de génération de cette page les
  recompute depuis les reçus et refuse de produire la page si une seule diverge.</p>
  <div class="table-roule">
  <table>
    <caption>Jalons, fichiers de preuve et racines SHA-256.</caption>
    <thead>
      <tr><th scope="col">Jalon</th><th scope="col">Fichier de preuve</th><th scope="col">Racine SHA-256</th></tr>
    </thead>
    <tbody>{racines_html}</tbody>
  </table>
  </div>
  <details>
    <summary>Reçus d'acquisition adressés par contenu</summary>
    <p>Les deux tentatives d'acquisition M7.1 sont scellées par des reçus immuables sous
    <code>{CV0}/acquisitions-m7-1-v1/receipts/sha256/</code> :</p>
    <ul>
      <li>Grok : <code>{fait("recu.grok", f["recu.grok"])}</code></li>
      <li>Kimi : <code>{fait("recu.kimi", f["recu.kimi"])}</code></li>
    </ul>
  </details>
</section>

<section id="futur" data-statut="PREVU_NON_EXISTANT">
  <h2>Parcours prévu pour ajouter une configuration
    <span class="badge badge-prevu">PRÉVU, N'EXISTE PAS</span></h2>
  <p>Ce parcours est une déduction raisonnée à partir de la chaîne de jalons déjà exécutée.
  Aucune de ces étapes n'existe, n'est implémentée ni n'est autorisée aujourd'hui ; chacune
  exigerait ses propres autorisations propriétaires et ses propres preuves.</p>
  <ol>
    <li>Décision propriétaire amendant le panel figé (successeur de M6.3), avec l'identité
    complète de la nouvelle configuration.</li>
    <li>Nouveau verrou de campagne scellant les artefacts amendés (successeur de M6.6).</li>
    <li>Autorisations distinctes puis acquisition avec reçus immuables (M7).</li>
    <li>Validation automatique des sorties (M8), préparation de revue aveugle (M9).</li>
    <li>Recalcul des métriques (M10.1), régénération du rapport de décision (M10.2), puis
    régénération de cette page.</li>
  </ol>
</section>

<section id="historique" data-statut="NON_OFFICIEL">
  <h2>Essais historiques et exploratoires
    <span class="badge badge-nonofficiel">NON OFFICIELS</span></h2>
  <p>Ces artefacts existent dans le dépôt mais n'alimentent pas le résultat officiel V0.</p>
  <ul>
    <li>Preuve locale U-025 P1 V1 : remplacée par la V2, qui seule alimente la
    consolidation.</li>
    <li>Preuves manuelles U-025 P2 V1 et V2 : remplacées par la V3 ; la V2 prouvait la
    reprise aux frontières de reçus.</li>
    <li>Prototype <code>pentagone-rotatif</code> : pipeline historique et spécialisé,
    archivé hors du pilote V0 ; ses campagnes et reçus restent immuables et ne prouvent
    rien pour la V0.</li>
  </ul>
</section>
</main>

<footer>
  <p>Page générée hors ligne, sans script, sans ressource distante, depuis les seules
  sources versionnées. Le brouillon <code>pages/index.html</code> du dépôt reste un espace
  réservé non publié : la présente page n'est pas un site public.</p>
  <p>Régénérer : <code>PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/bin/python3.13 {CV0}/restitution-humaine-v0/generer_page.py</code></p>
  <p>Vérifier la fidélité : <code>PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/bin/python3.13 {CV0}/restitution-humaine-v0/verifier_fidelite.py</code></p>
  <p>Ouvrir localement : <code>open {CV0}/restitution-humaine-v0/index.html</code></p>
</footer>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Génère index.html depuis les preuves fusionnées")
    script = Path(__file__).resolve()
    parser.add_argument("--sortie", type=Path, default=script.parent / "index.html")
    args = parser.parse_args()
    repo = repo_root(script.parent)
    sources = lire_sources(repo)
    faits = collecter_faits(repo, sources)
    contenu = rendre_html(faits).encode("utf-8")
    args.sortie.write_bytes(contenu)
    print(f"GENERATION_OK {args.sortie} sha256={hashlib.sha256(contenu).hexdigest()}")


if __name__ == "__main__":
    main()
