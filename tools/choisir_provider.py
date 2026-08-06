# /// script
# requires-python = ">=3.12"
# dependencies = ["requests"]
# ///
"""Choisir la meilleure route d'un modèle selon un critère déclaré et versionné.

Pourquoi cet outil existe. Le pin de `models.toml` était choisi à la main, et
un choix à la main s'oublie : Kimi K3 a été épinglé sur Modal pour son débit,
sans que personne ne remarque que cette route sert le modèle en `mxfp4`, une
quantification sur quatre bits. Mesurer un modèle quantifié et publier le
résultat sous le nom du modèle est une erreur de mesure, pas une préférence.

Ce que l'outil ne fait pas. Il ne bascule jamais de provider en cours de
campagne. R-003 fait de la route une composante de l'identité du candidat :
changer de route ne réessaie pas le même candidat, il en mesure un autre sous
la même étiquette. La sélection est un acte préalable, déclaré, consigné, dont
le résultat est un pin écrit dans `models.toml` avant la collecte.

Le critère, dans cet ordre strict :

1. la route doit accorder au moins le plancher de budget (R-025) ;
2. fidélité numérique décroissante : une route qui quantifie sert des poids
   dégradés, et mesurer `mxfp4` puis publier sous le nom du modèle est une
   erreur de mesure. `bf16` et au-dessus valent mieux que `fp8`, qui vaut
   mieux que `fp4` ou `mxfp4` ;
3. endpoint de l'éditeur du modèle d'abord : à égalité de précision, la route
   de celui qui publie le modèle est l'implémentation de référence, et un
   revendeur peut différer par des réglages que les métadonnées n'exposent pas ;
4. paramètres du contrat de campagne acceptés, du plus complet au moins
   complet : une route qui refuse `seed` impose de l'omettre, et l'omission est
   déclarée dans `models.toml` puis consignée au reçu ;
5. étiquette d'endpoint par ordre alphabétique, faute de mieux.

L'ordre place la précision numérique en tête : perdre `seed` coûte de la
répétabilité, servir le modèle sur quatre bits change le modèle.

L'éditeur passe devant les paramètres depuis le 2026-08-06, sur objection de la
revue d'implémentation. La version précédente faisait l'inverse et recommandait
Azure plutôt qu'Anthropic pour Opus 5, au seul motif qu'Azure accepte
`temperature`. Le critère récompensait alors la route qui accepte le harnais,
et non celle qui sert le binaire de référence : mesurer Opus 5 chez Microsoft
parce que notre contrat d'échantillonnage y passe mieux, c'est laisser l'outil
choisir l'objet mesuré. Un paramètre refusé se déclare et se consigne ; une
route qui n'est pas celle de l'éditeur ne se rattrape pas.

Disponibilité, statut et débit ne départagent rien, volontairement. Ce sont
des observations d'un instant : le 2026-08-06, l'endpoint `anthropic` de
Claude Fable 5 portait un statut dégradé, celui-là même qui a servi sans
incident les douze runs Anthropic de la campagne de référence. Trier là-dessus
rendrait le verdict différent d'un jour à l'autre, ce qui ruinerait l'intérêt
d'un critère déclaré. Ces valeurs sont affichées, et signalées quand la route
retenue va mal, mais elles ne choisissent pas.

Usage :
    uv run tools/choisir_provider.py --tous
    uv run tools/choisir_provider.py moonshotai/kimi-k3
    uv run tools/choisir_provider.py --tous --json > runs/<campagne>/routes.json
"""

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

import requests

# Toute évolution de l'ordre ci-dessus change cette valeur : un pin consigné
# sous `critere/v1` ne se compare pas à un pin choisi sous une autre version
CRITERE_VERSION = "benchmark-lab-x/selection-route/v2"

# Fidélité numérique, du plus fidèle au plus dégradé
FIDELITE = {
    "fp32": 0, "float32": 0,
    "bf16": 1, "fp16": 1, "float16": 1, "bfloat16": 1,
    "unknown": 2, "": 2, "none": 2,
    "fp8": 3, "float8": 3,
    "int8": 4,
    "fp6": 5,
    "fp4": 6, "mxfp4": 6, "nf4": 6, "int4": 6,
}
# Une quantification non déclarée ne vaut pas la même chose selon qui sert.
# L'éditeur qui ne déclare rien sert presque toujours son modèle en précision
# native, et le supposer quantifié serait aussi faux que le supposer exact : il
# reste au rang 2. Un revendeur qui ne déclare rien, lui, ne nous apprend rien,
# et un `fp8` déclaré est une dégradation connue et bornée là où son silence ne
# l'est pas. Il passe donc DERRIÈRE les précisions déclarées, jamais devant.
# Distinction demandée par la revue du 2026-08-06
RANG_NON_DECLARE_REVENDEUR = 5
# Paramètres du contrat de campagne. Une route qui n'en accepte pas un impose
# de l'omettre, et un candidat mesuré sans `seed` n'est plus comparable aux
# autres sur le même pied
PARAMETRES_CONTRAT = ("temperature", "top_p", "seed", "max_tokens")

MARGE_PROMPT = 8192


def norm(v: Any) -> str:
    return re.sub(r"[\s_]+", "-", str(v or "").strip().lower())


def rang_fidelite(q: Any, editeur: bool) -> int:
    cle = norm(q).replace("-", "")
    rang = FIDELITE.get(cle, 2)
    if rang == 2 and not editeur:
        return RANG_NON_DECLARE_REVENDEUR
    return rang


def budget_de(ep: dict) -> int:
    """Budget de sortie réellement accordé, marge de prompt déduite"""
    mc, ctx = ep.get("max_completion_tokens"), ep.get("context_length")
    brut = mc if isinstance(mc, int) and mc > 0 else (ctx if isinstance(ctx, int) and ctx > 0 else 0)
    if isinstance(ctx, int) and ctx > 0:
        brut = min(brut, ctx - MARGE_PROMPT)
    return max(0, brut)


def est_editeur(ep: dict, model: str) -> bool:
    """L'endpoint est-il servi par celui qui publie le modèle ?

    L'identifiant OpenRouter porte l'éditeur en préfixe (`moonshotai/kimi-k3`),
    et l'étiquette d'endpoint reprend ce préfixe quand l'éditeur sert lui-même
    """
    editeur = norm(model.split("/")[0])
    return editeur in {norm(ep.get("provider_name")),
                       norm(str(ep.get("tag") or "").split("/")[0])}


def evaluer(ep: dict, plancher: int, model: str) -> dict:
    """Rendre la clé de tri d'un endpoint et les motifs qui l'écartent"""
    budget = budget_de(ep)
    supportes = {norm(p) for p in (ep.get("supported_parameters") or [])}
    # Une liste vide ou absente ne veut pas dire « accepte tout » : elle veut
    # dire que la route ne déclare rien. La version précédente en faisait un
    # endpoint parfait sur les paramètres, ce qui le hissait en tête du tri
    # sur une absence d'information (revue du 2026-08-06)
    if not supportes:
        manquants = list(PARAMETRES_CONTRAT)
        parametres_opaques = True
    else:
        manquants = [p for p in PARAMETRES_CONTRAT if norm(p) not in supportes]
        parametres_opaques = False
    dispo = ep.get("uptime_last_30m")
    # Seule une propriété structurelle exclut : elle sera encore vraie demain
    exclusions = []
    if budget < plancher:
        exclusions.append(f"budget {budget} sous le plancher {plancher}")
    # Les réserves n'excluent pas, elles se signalent au moment de collecter
    reserves = []
    if norm(ep.get("status")) not in ("", "0", "none", "null"):
        reserves.append(f"statut {ep.get('status')}")
    if dispo is not None and dispo < 95:
        reserves.append(f"disponibilité {dispo:.1f}% sur 30 jours")
    editeur = est_editeur(ep, model)
    fidelite = rang_fidelite(ep.get("quantization"), editeur)
    return {
        "tag": ep.get("tag") or ep.get("provider_name"),
        "provider_name": ep.get("provider_name"),
        "quantization": ep.get("quantization") or ("unknown" if editeur else "non déclarée"),
        "rang_fidelite": fidelite,
        "budget": budget,
        "uptime_30j": dispo,
        "debit": ep.get("throughput_last_30m"),
        "editeur": editeur,
        "parametres_manquants": manquants,
        "parametres_opaques": parametres_opaques,
        "exclusions": exclusions,
        "reserves": reserves,
        # Le tri suit exactement l'ordre documenté en tête de fichier, et ne
        # contient que des propriétés stables : deux exécutions à des jours
        # différents rendent le même verdict
        "_cle": (
            fidelite,
            0 if editeur else 1,
            len(manquants),
            str(ep.get("tag") or ""),
        ),
    }


def classer(model: str, plancher: int) -> dict:
    url = f"https://openrouter.ai/api/v1/models/{model}/endpoints"
    r = requests.get(url, headers={"Accept": "application/json"}, timeout=20)
    if r.status_code >= 400:
        return {"modele": model, "erreur": f"HTTP {r.status_code}", "routes": []}
    eps = (r.json().get("data") or {}).get("endpoints") or []
    routes = [evaluer(e, plancher, model) for e in eps]
    eligibles = sorted((x for x in routes if not x["exclusions"]), key=lambda x: x["_cle"])
    for x in routes:
        x.pop("_cle")
    return {
        "modele": model,
        "critere_version": CRITERE_VERSION,
        "plancher": plancher,
        "recommande": eligibles[0]["tag"] if eligibles else None,
        "routes": routes,
        "eligibles": [x["tag"] for x in eligibles],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("modeles", nargs="*", help="identifiants OpenRouter à classer")
    ap.add_argument("--tous", action="store_true", help="classer tous les alias de models.toml")
    ap.add_argument("--models-file", type=Path, default=Path("models.toml"))
    ap.add_argument("--plancher-tokens", type=int, default=65536)
    ap.add_argument("--json", action="store_true", help="sortie machine, à consigner avec la campagne")
    args = ap.parse_args()

    pins: dict[str, str] = {}
    cibles = list(args.modeles)
    if args.tous or not cibles:
        if not args.models_file.is_file():
            print(f"{args.models_file} introuvable", file=sys.stderr)
            return 2
        registre = tomllib.loads(args.models_file.read_text(encoding="utf-8"))
        for alias, e in registre.items():
            if isinstance(e, dict) and "model" in e and "provider" in e:
                if e["model"] not in cibles:
                    cibles.append(e["model"])
                pins.setdefault(e["model"], e["provider"])

    resultats = [classer(m, args.plancher_tokens) for m in cibles]

    if args.json:
        print(json.dumps({"critere_version": CRITERE_VERSION, "modeles": resultats},
                         ensure_ascii=False, indent=1))
        return 0

    a_changer = []
    for res in resultats:
        pin = pins.get(res["modele"])
        reco = res.get("recommande")
        print(f"\n{res['modele']}")
        if res.get("erreur"):
            print(f"  {res['erreur']}")
            continue
        for x in res["routes"]:
            marque = "→" if x["tag"] == reco else (" " if not x["exclusions"] else "×")
            actuel = "  [pin actuel]" if pin and norm(pin) in {norm(x["tag"]), norm(str(x["tag"]).split("/")[0]), norm(x["provider_name"])} else ""
            notes = list(x["exclusions"])
            if x["parametres_manquants"]:
                notes.append("sans " + ",".join(x["parametres_manquants"]))
            notes += x["reserves"]
            dispo = f"{x['uptime_30j']:5.1f}%" if x["uptime_30j"] is not None else "    ?"
            edit = "éditeur" if x["editeur"] else "       "
            print(f"  {marque} {str(x['tag']):28} {x['quantization']:8} {edit} "
                  f"budget {x['budget']:>7}  dispo {dispo}  {'; '.join(notes)}{actuel}")
        choisie = next((x for x in res["routes"] if x["tag"] == reco), None)
        if choisie and choisie["reserves"]:
            print(f"  ! la route retenue va mal en ce moment : {'; '.join(choisie['reserves'])}. "
                  f"Cela ne change pas le choix, mais peut faire échouer la collecte du jour")
        if pin and reco and norm(pin) not in {norm(reco), norm(str(reco).split("/")[0])}:
            a_changer.append((res["modele"], pin, reco))

    if a_changer:
        print("\nPins à revoir avant la prochaine campagne :")
        for m, pin, reco in a_changer:
            print(f"  {m}: {pin} → {reco}")
        print("\nChanger un pin crée un candidat différent : son `execution_manifest_hash` "
              "change, et ses runs antérieurs ne se comparent plus aux nouveaux (R-003, R-015).")
    else:
        print("\nTous les pins correspondent déjà au critère "
              f"{CRITERE_VERSION}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
