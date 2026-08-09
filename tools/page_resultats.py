# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Écrit la page de résultats d'une campagne, en HTML statique autonome.

Les données sont incorporées dans la page : elle s'ouvre hors ligne, sans
requête réseau, et la regénérer après une campagne est une commande. Rien
n'est calculé ici que le rapport n'ait déjà décidé : la page affiche, elle ne
note pas.

Ce qu'elle montre, et pourquoi pas davantage. Le titre parle de configurations
et non de modèles, parce que c'est ce que le classement compare : le candidat
est le triplet modèle, route, effort (R-003). Les caractéristiques de mesure
vivent dans une infobulle par ligne plutôt que dans des colonnes, qui
rendraient le tableau illisible pour quelqu'un qui découvre le projet.

Usage :
    uv run tools/page_resultats.py runs/<campagne>/results-data.json
    uv run tools/page_resultats.py runs/<campagne>/results-data.json --sortie docs/index.html
"""

import argparse
import hashlib
import html
import json
import os
import sys
import tomllib
from pathlib import Path

RACINE = Path(__file__).parent.parent
MODE_HISTORIQUE = "historique-reference-v2"
RAPPORT_HISTORIQUE = RACINE / "runs" / "2026-08-06-reference-v2" / "results-data.json"
ROUTES_HISTORIQUES = RACINE / "runs" / "2026-08-06-reference-v2" / "routes.json"
SORTIE_HISTORIQUE = Path("/private/tmp/benchmark-lab-x-reference-v2.html")
SHA_RAPPORT_HISTORIQUE = "4185a4ab9b4512f93bae0b998a939de0eff01151c00a9c01c789b757b62eedfd"
SHA_ROUTES_HISTORIQUES = "5feae661b3050916973c40ca7212fe13443c1ca87e9e6471b3cc2eda7deae468"
SHA_ARBRE_HISTORIQUE = "2214cd183c8da7aff12a745044c5542f3a846eaa9dd13312005d3c70dba8f923"

# Libellé lisible de chaque état terminal R-013, plus les deux mises à l'écart
# décidées par l'agrégateur. Un état sans libellé apparaîtrait brut sur la page
ETATS = {
    "INELIGIBLE": "route non conforme, refusée avant tout appel",
    "RETIRE": "retiré du panel, motif consigné",
    "UNKNOWN": "preuve ambiguë, non imputable au candidat",
    "INFRA_ERROR": "tentatives épuisées sans sortie notable",
    "MISSING": "run planifié jamais tenté",
    "absent du plan de campagne": "collecté hors du plan gelé",
    "runs non scorés": "tous les runs attendus ne sont pas notés",
}


def registre() -> dict:
    try:
        return tomllib.loads((RACINE / "models.toml").read_text(encoding="utf-8"))
    except OSError:
        return {}


def libelle(alias: str, effort: str | None, reg: dict) -> str:
    """Nom de ligne : le candidat entier, pas l'alias interne.

    Repli sur l'alias brut quand le rapport porte un candidat absent du
    registre ; cela arrive dès qu'un alias est retiré après une campagne
    """
    e = reg.get(alias)
    nom = e.get("nom_public") if isinstance(e, dict) else None
    if not nom:
        return alias
    return f"{nom} · {effort}" if effort else nom


def empreinte(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def empreinte_arbre_historique(racine: Path) -> str:
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
            raise ValueError(f"entrée spéciale inattendue dans l’archive : {relatif}")
        digest.update(entree.encode())
    return digest.hexdigest()


def charger_archive_historique(rapport: Path, routes: Path) -> tuple[dict, dict]:
    """Charge uniquement les deux artefacts figés de reference-v2."""
    attendus = (
        (rapport, RAPPORT_HISTORIQUE, SHA_RAPPORT_HISTORIQUE, "rapport"),
        (routes, ROUTES_HISTORIQUES, SHA_ROUTES_HISTORIQUES, "routes"),
    )
    for chemin, canonique, attendu, nom in attendus:
        if not chemin.is_file():
            raise ValueError(f"{nom} historique introuvable : {chemin}")
        if chemin.resolve() != canonique.resolve():
            raise ValueError(f"{nom} historique hors archive attendue : {chemin}")
        observe = empreinte(chemin)
        if observe != attendu:
            raise ValueError(
                f"empreinte {nom} inattendue : {observe}, attendu {attendu}"
            )

    arbre_observe = empreinte_arbre_historique(RAPPORT_HISTORIQUE.parent)
    if arbre_observe != SHA_ARBRE_HISTORIQUE:
        raise ValueError(
            "empreinte de l’archive inattendue : "
            f"{arbre_observe}, attendu {SHA_ARBRE_HISTORIQUE}"
        )

    data = json.loads(rapport.read_text(encoding="utf-8"))
    routes_data = json.loads(routes.read_text(encoding="utf-8"))
    valider_archive_historique(data, routes_data)
    return data, routes_data


def valider_archive_historique(data: dict, routes: dict) -> None:
    """Refuse une archive dont les faits structurants ne sont plus ceux audités."""
    conf = data.get("conformite") or {}
    contexte = data.get("measurement_context") or {}
    runs = data.get("runs") or []
    candidats = data.get("candidats") or []
    retenus = [r for r in runs if r.get("tentative_retenue") is True]
    controles = {
        "task-v2": contexte.get("task_version") == "task-v2",
        "verify-v3": contexte.get("verify_version") == "verify-v3",
        "protocole v1": contexte.get("protocol_version") == "benchmark-lab-x/protocol/v1",
        "instrument non qualifié": conf.get("instrument_qualifie") is False,
        "page non validée": conf.get("page_validee") is False,
        "blocage R-016": len((conf.get("blocages") or {}).get("R-016") or []) == 7,
        "19 candidats": len(candidats) == 19,
        "84 tentatives": len(runs) == 84,
        "76 tentatives retenues": len(retenus) == 76,
        "83 prompts fournisseur": (data.get("cycle_de_vie") or {}).get("prompts_partis") == 83,
        "51 paliers": data.get("paliers_total") == 51,
    }
    invalides = [nom for nom, passe in controles.items() if not passe]
    if invalides:
        raise ValueError("archive historique non conforme : " + ", ".join(invalides))

    recommandations = {
        entree.get("modele"): entree.get("recommande")
        for entree in routes.get("modeles") or []
    }
    kimi = [
        r for r in retenus
        if r.get("alias") == "kimi-k3-max"
    ]
    if len(kimi) != 4:
        raise ValueError("archive historique non conforme : quatre runs Kimi retenus attendus")
    modeles = {r.get("model_requested") for r in kimi}
    pins = {r.get("provider_pinned") for r in kimi}
    servis = {r.get("provider_served") for r in kimi}
    if modeles != {"moonshotai/kimi-k3"} or pins != {"moonshotai"} or servis != {"Moonshot AI"}:
        raise ValueError("archive historique non conforme : identité de route Kimi inattendue")
    if recommandations.get("moonshotai/kimi-k3") != "wafer":
        raise ValueError("archive historique non conforme : recommandation Kimi inattendue")


def infobulle(c: dict, runs: list[dict], reg: dict) -> str:
    """Caractéristiques de mesure de ce candidat, une ligne par fait."""
    siens = [r for r in runs if r["alias"] == c["alias"]]
    prem = next((r for r in siens if r.get("provider_served")), {})
    budget = next((r.get("max_tokens") for r in siens if r.get("max_tokens")), None)
    quant = next((r.get("quantization_servie") for r in siens if r.get("quantization_servie")), None)

    # Un champ absent du rapport et un champ vide ne disent pas la même chose.
    # Les rapports antérieurs au 2026-08-06 ne portent pas `params_omitted` :
    # écrire « tous les paramètres envoyés » y serait faux, GPT 5.6-sol omettant
    # `temperature` et `top_p`. Une absence se déclare, elle ne se comble pas
    connu = any("params_omitted" in r for r in siens)
    omis = next((r.get("params_omitted") for r in siens if r.get("params_omitted")), None)
    if not connu:
        ligne_params = "paramètres omis : non consignés dans ce rapport"
    elif omis:
        ligne_params = f"paramètres omis : {', '.join(omis)}"
    else:
        ligne_params = "tous les paramètres du contrat envoyés"

    faits = [
        f"route servie : {prem.get('provider_served') or '-'}",
        f"quantification : {quant}" if quant else None,
        f"budget de sortie : {budget} jetons" if budget else None,
        ligne_params,
        f"niveaux des runs : {', '.join(str(n) for n in c['niveaux'])}" if c.get("niveaux") else None,
        f"coût moyen : {c['cout_moyen_usd']:.3f} $" if c.get("cout_moyen_usd") else None,
    ]
    return "\n".join(f for f in faits if f)


def page(data: dict, reg: dict, source: Path) -> str:
    conf = data.get("conformite") or {}
    total = data.get("paliers_total") or 51
    runs = data.get("runs") or []
    classables = [c for c in data.get("candidats", []) if c.get("classable")]
    ecartes = [c for c in data.get("candidats", []) if not c.get("classable")]
    maxi = max((c["niveau_retenu"] or 0) for c in classables) if classables else 1

    blocages = conf.get("blocages") or {}
    lignes_blocage = []
    for cle, valeurs in blocages.items():
        n = len(valeurs) if isinstance(valeurs, list) else 1
        lignes_blocage.append(f"{html.escape(str(cle))} ({n})")

    # Une campagne peut avoir été collectée sous des routes que le registre n'a
    # plus. Le signaler est automatique et vaut pour n'importe quel rapport :
    # sans cela, la page présente comme courant un candidat qui n'existe plus
    def norme(v: str | None) -> str:
        return "".join(ch for ch in str(v or "").lower() if ch.isalnum())

    perimes = []
    for c in data.get("candidats", []):
        e = reg.get(c["alias"])
        servi = next((r.get("provider_served") for r in runs
                      if r["alias"] == c["alias"] and r.get("provider_served")), None)
        if isinstance(e, dict) and servi and norme(e.get("provider")) != norme(servi):
            perimes.append(f"{libelle(c['alias'], c.get('reasoning_effort'), reg)} ({servi})")

    barres = []
    for rang, c in enumerate(classables, start=1):
        niveau = c["niveau_retenu"] or 0
        pct = 100 * niveau / max(maxi, 1)
        barres.append(f"""      <li>
        <span class="rang">{rang}</span>
        <span class="nom" title="{html.escape(infobulle(c, runs, reg))}">{html.escape(libelle(c['alias'], c.get('reasoning_effort'), reg))}</span>
        <span class="piste"><span class="barre" style="width:{pct:.1f}%"></span></span>
        <span class="niveau">{niveau}<span class="sur">/{total}</span></span>
      </li>""")

    hors = []
    for c in ecartes:
        motif = c.get("hors_classement") or "non classable"
        hors.append(f"""      <li>
        <span class="nom" title="{html.escape(infobulle(c, runs, reg))}">{html.escape(libelle(c['alias'], c.get('reasoning_effort'), reg))}</span>
        <span class="motif">{html.escape(ETATS.get(motif, motif))}</span>
      </li>""")

    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Classement des configurations mesurées</title>
<style>
  :root {{
    --encre: #1a1a1a; --papier: #fbfaf8; --trait: #d8d4cd;
    --barre: #33566b; --attenue: #6b665e; --alerte: #8a4b2a;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --encre: #e8e5e0; --papier: #17181a; --trait: #33353a;
      --barre: #6fa3c0; --attenue: #94908a; --alerte: #d08a5e;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 2.5rem 1.25rem 4rem;
    background: var(--papier); color: var(--encre);
    font: 16px/1.55 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  }}
  main {{ max-width: 54rem; margin: 0 auto; }}
  h1 {{ font-size: 1.6rem; font-weight: 600; margin: 0 0 .35rem; text-wrap: balance; }}
  .sous {{ color: var(--attenue); margin: 0 0 1.75rem; font-size: .94rem; }}
  .bandeau {{
    border-left: 3px solid var(--alerte); padding: .7rem .9rem;
    margin: 0 0 2rem; font-size: .9rem; color: var(--attenue);
  }}
  .bandeau strong {{ color: var(--encre); font-weight: 600; }}
  ol, ul {{ list-style: none; margin: 0; padding: 0; }}
  ol li {{
    display: grid; grid-template-columns: 1.6rem minmax(8rem, 13rem) 1fr 4.2rem;
    gap: .7rem; align-items: center; padding: .3rem 0;
  }}
  .rang {{ color: var(--attenue); font-size: .82rem; text-align: right;
           font-variant-numeric: tabular-nums; }}
  .nom {{ font-size: .93rem; cursor: help; }}
  .piste {{ background: var(--trait); height: .62rem; border-radius: .31rem; overflow: hidden; }}
  .barre {{ display: block; height: 100%; background: var(--barre); border-radius: .31rem; }}
  .niveau {{ font-variant-numeric: tabular-nums; font-size: .93rem; text-align: right; }}
  .sur {{ color: var(--attenue); font-size: .78rem; }}
  h2 {{ font-size: .95rem; font-weight: 600; margin: 2.5rem 0 .6rem; }}
  ul li {{ display: flex; flex-wrap: wrap; gap: .5rem .9rem; padding: .28rem 0;
           font-size: .9rem; border-top: 1px solid var(--trait); }}
  ul li:first-child {{ border-top: none; }}
  .motif {{ color: var(--attenue); }}
  footer {{ margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--trait);
            color: var(--attenue); font-size: .8rem; }}
  code {{ font-size: .85em; }}
</style>
</head>
<body>
<main>
  <h1>Classement des configurations mesurées</h1>
  <p class="sous">Carte <code>{html.escape(str(data.get('carte')))}</code>, échelle <code>{html.escape(str(data.get('verify_version')))}</code>, {total} paliers. Le niveau retenu est le troisième meilleur des quatre runs.</p>

  <div class="bandeau">
    <strong>Page provisoire.</strong>
    {"Conditions non remplies : " + ", ".join(lignes_blocage) + ". " if lignes_blocage else ""}
    Un candidat est un triplet modèle, route et effort de raisonnement : ce tableau
    compare des configurations, pas des modèles nus. Survolez un nom pour voir
    comment il a été mesuré.
    {"<br><br>Mesuré sous une route que le registre n'épingle plus : " + html.escape(", ".join(perimes)) + ". Ces lignes ne se comparent pas aux mesures courantes." if perimes else ""}
  </div>

  <ol>
{chr(10).join(barres) if barres else '      <li><span class="nom">aucun candidat classable</span></li>'}
  </ol>

  {"<h2>Hors classement</h2><ul>" + chr(10).join(hors) + "</ul>" if hors else ""}

  <footer>
    Données : <code>{html.escape(str(source))}</code>.
    Contexte de mesure <code>{html.escape(str(data.get('measurement_context_hash', ''))[:16])}…</code>,
    instrument <code>{html.escape(str(data.get('verify_hash', ''))[:16])}…</code>.
    Notation par code seul, sans juge humain ni juge modèle.
  </footer>
</main>
</body>
</html>
"""


def page_v3(data: dict, reg: dict, source: Path) -> str:
    """Rendre les axes valides et provisoires sans statut global trompeur"""
    blocs = []
    for axe in data.get("axes") or []:
        lignes = []
        candidats = sorted(
            axe.get("candidats") or [],
            key=lambda candidat: (
                candidat.get("rang_provisoire") is None,
                candidat.get("rang_provisoire") or 0,
                candidat.get("alias") or "",
            ),
        )
        for candidat in candidats:
            agregat = candidat.get("agregat") or {}
            valeur = agregat.get("verdict_retenu")
            if valeur is None:
                valeur = agregat.get("niveau_retenu")
            if valeur is None:
                valeur = "hors classement"
            distribution = ", ".join(
                str(item) if item is not None else "?"
                for item in agregat.get("distribution") or []
            )
            rang = candidat.get("rang_provisoire")
            nom = libelle(candidat.get("alias", ""), None, reg)
            if candidat.get("panel_state") == "RETIRE":
                nom += " (retirée du panel)"
            lignes.append(
                "<tr>"
                f"<td>{html.escape(str(rang) if rang is not None else '–')}</td>"
                f"<td>{html.escape(nom)}</td>"
                f"<td>{html.escape(str(valeur))}</td>"
                f"<td>{html.escape(distribution)}</td>"
                "</tr>"
            )
        blocages = html.escape(json.dumps(axe.get("blocages") or [], ensure_ascii=False))
        blocs.append(f"""
  <section>
    <h2>{html.escape(str(axe.get('id')))}</h2>
    <p class="statut {html.escape(str(axe.get('statut')))}">Statut : {html.escape(str(axe.get('statut')))}</p>
    <table>
      <thead><tr><th>Rang</th><th>Configuration</th><th>Résultat retenu</th><th>Six runs</th></tr></thead>
      <tbody>{''.join(lignes)}</tbody>
    </table>
    {f'<details><summary>Pourquoi cet axe reste provisoire</summary><code>{blocages}</code></details>' if axe.get('statut') != 'valide' else ''}
  </section>""")

    statut_campagne = data.get("campaign_status") or "incomplete"
    hold = data.get("operator_status") == "HOLD"
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Résultats Benchmark Lab-X</title>
<style>
  :root {{ color-scheme: light dark; --trait: #7775; --alerte: #a54b2a; }}
  body {{ margin: 0; padding: 2rem 1rem 4rem; font: 16px/1.5 system-ui, sans-serif; }}
  main {{ max-width: 72rem; margin: auto; }}
  h1 {{ margin-bottom: .4rem; }}
  .mission {{ max-width: 62rem; }}
  .bandeau {{ border-left: .25rem solid var(--alerte); padding: .75rem 1rem; margin: 1.5rem 0; }}
  section {{ margin-top: 2.5rem; }}
  h2 {{ margin-bottom: .25rem; }}
  .statut {{ margin-top: 0; font-weight: 600; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ padding: .45rem .5rem; text-align: left; border-bottom: 1px solid var(--trait); }}
  th:first-child, td:first-child {{ width: 4rem; text-align: right; }}
  details {{ margin-top: .8rem; }}
  details code {{ white-space: pre-wrap; }}
  footer {{ margin-top: 3rem; font-size: .85rem; opacity: .75; }}
</style>
</head>
<body>
<main>
  <h1>Résultats Benchmark Lab-X</h1>
  <p class="mission">Benchmark Lab-X détermine quel modèle, quelle configuration ou quel agent réussit un travail réel, avec quelle fiabilité, à quel coût et en combien de temps, puis vérifie si cette recommandation reste valable lorsque les systèmes évoluent.</p>
  <div class="bandeau">
    Campagne <strong>{html.escape(str(statut_campagne))}</strong>.
    {'Contrôle opérateur : HOLD. Aucun nouvel appel ne doit partir sous ce lock.' if hold else 'Chaque axe porte son propre statut.'}
  </div>
  {''.join(blocs)}
  <footer>Données : <code>{html.escape(str(source))}</code>. Lock <code>{html.escape(str(data.get('campaign_lock_hash', ''))[:16])}…</code>.</footer>
</main>
</body>
</html>
"""


def cause_historique(run: dict) -> str | None:
    if run.get("cause") == "budget de temps dépassé":
        return (
            "cause historique : borne de vérification de 180 s dépassée; "
            "borne absente des consignes visibles, effet sur le score non réparé"
        )
    if run.get("frontiere") == "A0_page":
        return "cause historique : aucune page scoreable"
    if run.get("frontiere") == "A1_api_totale":
        return "cause historique : échec de l’API totale, sans dépassement de la borne"
    if run.get("cause"):
        return f"cause historique : {run['cause']}"
    return None


def resume_run_historique(run: dict) -> str:
    morceaux = [
        f"r{run['run']} = {run.get('niveau')}",
        f"frontière {run.get('frontiere') or 'non consignée'}",
    ]
    cause = cause_historique(run)
    if cause:
        morceaux.append(cause)
    return " | ".join(morceaux)


def runs_retenus_historique(alias: str, runs: list[dict]) -> list[dict]:
    return sorted(
        (
            run for run in runs
            if run.get("alias") == alias and run.get("tentative_retenue") is True
        ),
        key=lambda run: int(run["run"]),
    )


def ecart_route_historique(
    alias: str, runs: list[dict], routes: dict
) -> tuple[str, str, str] | None:
    siens = runs_retenus_historique(alias, runs)
    if not siens:
        return None
    premier = siens[0]
    recommandations = {
        entree.get("modele"): entree.get("recommande")
        for entree in routes.get("modeles") or []
    }
    recommandee = recommandations.get(premier.get("model_requested"))
    provider_recommande = str(recommandee or "").split("/", 1)[0]
    provider_epingle = str(premier.get("provider_pinned") or "")
    if not recommandee or provider_recommande == provider_epingle:
        return None
    return recommandee, provider_epingle, str(premier.get("provider_served") or "-")


def infobulle_historique(c: dict, runs: list[dict], routes: dict) -> str:
    siens = runs_retenus_historique(c["alias"], runs)
    premier = siens[0] if siens else {}
    faits = [
        f"route épinglée : {premier.get('provider_pinned') or '-'}",
        f"provider servi : {premier.get('provider_served') or '-'}",
        "chronologie des runs retenus :",
        *(resume_run_historique(run) for run in siens),
    ]
    ecart = ecart_route_historique(c["alias"], runs, routes)
    if ecart:
        recommandee, epingle, servi = ecart
        faits.append(
            "écart au critère figé : "
            f"route recommandée {recommandee}, pin {epingle}, provider servi {servi}; "
            "mention documentaire, non réparatrice"
        )
    return "\n".join(faits)


def page_historique(data: dict, routes: dict, source: Path) -> str:
    conf = data["conformite"]
    contexte = data["measurement_context"]
    total = data["paliers_total"]
    runs = data["runs"]
    candidats = [c for c in data["candidats"] if c.get("classable")]
    ordre_plan = {
        alias: index
        for index, alias in enumerate(conf["plan"]["alias"])
    }
    candidats.sort(
        key=lambda c: (
            -(c.get("niveau_retenu") or 0),
            ordre_plan.get(c["alias"], len(ordre_plan)),
        )
    )

    barres = []
    for c in candidats:
        niveau = c.get("niveau_retenu") or 0
        rang = 1 + sum(
            1 for autre in candidats
            if (autre.get("niveau_retenu") or 0) > niveau
        )
        pct = 100 * niveau / total
        ecart = ecart_route_historique(c["alias"], runs, routes)
        badge = ""
        attribut_ecart = ""
        if ecart:
            recommandee, epingle, _ = ecart
            badge = (
                '<span class="badge-route" '
                'title="Mention documentaire, cet écart historique n’est pas réparé">'
                "écart de route</span>"
            )
            attribut_ecart = (
                f' data-route-recommandee="{html.escape(recommandee)}"'
                f' data-route-epinglee="{html.escape(epingle)}"'
            )
        alias = html.escape(c["alias"])
        info = html.escape(infobulle_historique(c, runs, routes))
        barres.append(f"""      <li data-alias="{alias}" data-rang="{rang}" data-niveau="{niveau}" data-pct="{pct:.1f}"{attribut_ecart}>
        <span class="rang">{rang}</span>
        <span class="nom" title="{info}">{alias} {badge}</span>
        <span class="piste" aria-label="niveau historique {niveau} sur {total}"><span class="barre" style="width:{pct:.1f}%"></span></span>
        <span class="niveau">{niveau}<span class="sur">/{total}</span></span>
      </li>""")

    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Archive diagnostique des configurations mesurées</title>
<style>
  :root {{
    --encre: #1a1a1a; --papier: #fbfaf8; --trait: #d8d4cd;
    --barre: #33566b; --attenue: #6b665e; --alerte: #8a4b2a;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --encre: #e8e5e0; --papier: #17181a; --trait: #33353a;
      --barre: #6fa3c0; --attenue: #94908a; --alerte: #d08a5e;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 2.5rem 1.25rem 4rem;
    background: var(--papier); color: var(--encre);
    font: 16px/1.55 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  }}
  main {{ max-width: 62rem; margin: 0 auto; }}
  h1 {{ font-size: 1.6rem; font-weight: 600; margin: 0 0 .35rem; text-wrap: balance; }}
  .sous {{ color: var(--attenue); margin: 0 0 1.75rem; font-size: .94rem; }}
  .bandeau {{
    border-left: 3px solid var(--alerte); padding: .7rem .9rem;
    margin: 0 0 2rem; font-size: .9rem; color: var(--attenue);
  }}
  .bandeau strong {{ color: var(--encre); font-weight: 600; }}
  .bandeau p {{ margin: 0 0 .65rem; }}
  .bandeau p:last-child {{ margin-bottom: 0; }}
  ol {{ list-style: none; margin: 0; padding: 0; }}
  ol li {{
    display: grid; grid-template-columns: 1.6rem minmax(11rem, 17rem) 1fr 4.2rem;
    gap: .7rem; align-items: center; padding: .3rem 0;
  }}
  .rang {{ color: var(--attenue); font-size: .82rem; text-align: right;
           font-variant-numeric: tabular-nums; }}
  .nom {{ font-size: .93rem; cursor: help; }}
  .badge-route {{
    display: inline-block; margin-left: .3rem; padding: .05rem .3rem;
    border: 1px solid var(--alerte); border-radius: .2rem;
    color: var(--alerte); font-size: .68rem; vertical-align: .08rem;
  }}
  .piste {{ background: var(--trait); height: .62rem; border-radius: .31rem; overflow: hidden; }}
  .barre {{ display: block; height: 100%; background: var(--barre); border-radius: .31rem; }}
  .niveau {{ font-variant-numeric: tabular-nums; font-size: .93rem; text-align: right; }}
  .sur {{ color: var(--attenue); font-size: .78rem; }}
  footer {{ margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--trait);
            color: var(--attenue); font-size: .8rem; }}
  code {{ font-size: .85em; }}
</style>
</head>
<body>
<main data-presentation="{MODE_HISTORIQUE}">
  <h1>Archive diagnostique des configurations mesurées</h1>
  <p class="sous">Campagne <code>2026-08-06-reference-v2</code>, <code>{html.escape(contexte['task_version'])}</code>, <code>{html.escape(contexte['verify_version'])}</code>, <code>{html.escape(contexte['protocol_version'])}</code>.</p>

  <div class="bandeau">
    <p><strong>Campagne historique diagnostique 2026-08-06-reference-v2.</strong>
    Résultats immuables de task-v2 et verify-v3. Instrument non qualifié,
    page non validée, blocage R-016. Présentation interne, provisoire et non
    décisionnelle. Aucun rejeu, aucune renotation, aucune correction des scores.</p>

    <p><strong>Comptage historique :</strong> 19 candidats; 76 runs attendus et
    retenus; 84 tentatives enregistrées; 83 prompts ayant atteint un fournisseur.
    Huit tentatives n’ont pas été retenues, dont une arrêtée avant fournisseur.</p>

    <p><strong>Échelle nominale historique :</strong> les barres représentent le
    niveau retenu sur 51, pas un pourcentage de capacité. Le plateau observé au
    niveau 43 porte la frontière P3e-17_precision_ref. Les deux paliers de précision
    extrême suivants ne discriminent pas l’interface numérique historique. Les six
    paliers d’horizon long placés ensuite n’ont pas été atteints. Le niveau 43 ne
    prouve aucune tenue à 35, 55 ou 75 secondes.</p>

    <p><strong>Limites connues :</strong> la borne de vérification de 180 s n’était
    pas annoncée dans les consignes visibles et son effet historique sur le score
    demeure. Les causes basses sont hétérogènes. La ligne Kimi documente un pin
    non conforme au critère de route figé, sans réparer l’écart.</p>

    <p><strong>R-016 ouvert :</strong> les sept témoins historiques déclarent un
    producteur non aveugle au vérificateur. La couverture indépendante n’est pas
    démontrée et aucun reçu de couverture figé n’est consommé par cette page.</p>
  </div>

  <ol>
{chr(10).join(barres)}
  </ol>

  <footer>
    Vue dérivée de <code>{html.escape(str(source))}</code>. Rangs de compétition
    calculés sur <code>niveau_retenu</code> seul; ordre du plan au sein des ex aequo.
    Contexte <code>{html.escape(data['measurement_context_hash'][:16])}…</code>,
    instrument <code>{html.escape(data['verify_hash'][:16])}…</code>.
  </footer>
</main>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("rapport", type=Path, help="results-data.json d'une campagne")
    ap.add_argument("--sortie", type=Path)
    ap.add_argument(
        "--mode",
        choices=("standard", MODE_HISTORIQUE),
        default="standard",
    )
    ap.add_argument("--routes", type=Path, help="routes.json figé de la campagne")
    args = ap.parse_args()

    if not args.rapport.is_file():
        print(f"rapport introuvable : {args.rapport}", file=sys.stderr)
        return 2

    if args.mode == MODE_HISTORIQUE:
        if args.routes is None:
            print("--routes est requis en mode historique", file=sys.stderr)
            return 2
        sortie = args.sortie or SORTIE_HISTORIQUE
        racine_temporaire = Path("/private/tmp").resolve()
        try:
            sortie.resolve().relative_to(racine_temporaire)
        except ValueError:
            print("la sortie historique doit rester sous /private/tmp", file=sys.stderr)
            return 2
        if sortie.exists() and (
            not sortie.is_file()
            or sortie.is_symlink()
            or sortie.stat().st_nlink != 1
        ):
            print("la sortie historique existante n’est pas un fichier régulier isolé", file=sys.stderr)
            return 2
        try:
            data, routes = charger_archive_historique(args.rapport, args.routes)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"archive historique refusée : {exc}", file=sys.stderr)
            return 2
        contenu = page_historique(data, routes, args.rapport)
    else:
        sortie = args.sortie or RACINE / "docs" / "index.html"
        data = json.loads(args.rapport.read_text(encoding="utf-8"))
        contenu = (
            page_v3(data, registre(), args.rapport)
            if data.get("schema_version") == "benchmark-lab-x/results-data/v3"
            else page(data, registre(), args.rapport)
        )

    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(contenu, encoding="utf-8")

    conf = data.get("conformite") or {}
    if data.get("schema_version") == "benchmark-lab-x/results-data/v3":
        print(f"{sortie}  {len(data.get('axes') or [])} axes, "
              f"page_validee={conf.get('page_validee')}")
    else:
        print(f"{sortie}  "
              f"{len([c for c in data.get('candidats', []) if c.get('classable')])} classés, "
              f"{len([c for c in data.get('candidats', []) if not c.get('classable')])} hors classement, "
              f"page_validee={conf.get('page_validee')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
