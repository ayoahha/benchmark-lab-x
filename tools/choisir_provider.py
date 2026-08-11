# /// script
# requires-python = ">=3.12"
# dependencies = ["requests"]
# ///
"""Choisir la meilleure route d'un modèle selon un critère déclaré et versionné.

Pourquoi cet outil existe. Le pin de `models.toml` était choisi à la main, et
un choix à la main s'oublie : Kimi K3 avait été épinglé sur Modal pour son
débit, alors que le débit ne compte pas dans une campagne qui n'est pas
chronométrée. Un critère écrit rend ce genre d'arbitrage visible et rejouable.

Ce que l'outil ne fait pas. Il ne bascule jamais de provider dans un lock.
R-003 sépare l'identité du modèle de celle de la route. Un provider secondaire
peut rejoindre la même série dans un nouveau lot lorsque le contrat de
compatibilité est prouvé et préenregistré. La sélection reste un acte préalable,
déclaré et consigné avant la collecte.

Le critère, dans cet ordre strict :

1. la route doit déclarer un budget de sortie positif (R-025) ;
2. classe de format. Quand la carte déclare `format_reference`, une route qui
   déclare exactement ce format passe d'abord. Une API éditeur qui ne divulgue
   pas sa quantification reste une classe de politique distincte, sans rang
   numérique supposé. Sans format de référence, cette classe éditeur passe
   avant les formats tiers déclarés au titre de l'identité de la route, pas
   d'une précision présumée. Entre formats déclarés, l'échelle absolue place
   `bf16` et au-dessus devant `fp8`, devant `fp4` ou `mxfp4` ;
3. endpoint de l'éditeur du modèle d'abord : à égalité de précision, la route
   de celui qui publie le modèle est l'implémentation de référence, et un
   revendeur peut différer par des réglages que les métadonnées n'exposent pas ;
4. paramètres du contrat de campagne acceptés, du plus complet au moins
   complet : une route qui refuse `seed` impose de l'omettre, et l'omission est
   déclarée dans `models.toml` puis consignée au reçu ;
5. étiquette d'endpoint par ordre alphabétique, faute de mieux.

L'ordre place la classe de format en tête : perdre `seed` coûte de la
répétabilité, servir des poids déclarés différents change le modèle. Le statut
`not_disclosed` ne fournit aucune information physique à comparer.

`format_reference` existe parce que l'échelle absolue s'est trompée. Elle
suppose qu'un modèle est publié en pleine précision et requantifié par ses
hébergeurs. Kimi K3 dément cette supposition : il est entraîné avec
quantification dans la boucle et publié en MXFP4, sans checkpoint BF16. Les
routes `fp8` n'y sont donc pas moins dégradées, elles sont requantifiées à
partir du format publié. Le critère avait, pour cette raison, écarté la route
de l'éditeur au profit de deux routes qui se sont révélées être les seules à
saturer. Voir le bloc `kimi-k3-max` de `models.toml`.

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
CRITERE_VERSION_HISTORIQUE = "benchmark-lab-x/selection-route/v2"
CRITERE_VERSION = "benchmark-lab-x/selection-route/v3"

# Correspondance fermée entre l'espace de noms, le slug et les noms d'éditeur
EDITEURS_CANONIQUES = {
    "anthropic": ("anthropic", frozenset({"anthropic"})),
    "deepseek": ("deepseek", frozenset({"deepseek"})),
    "meta": ("meta", frozenset({"meta"})),
    "minimax": ("minimax", frozenset({"minimax"})),
    "mistralai": ("mistral", frozenset({"mistral", "mistral-ai"})),
    "moonshotai": ("moonshotai", frozenset({"moonshot-ai", "moonshotai"})),
    "openai": ("openai", frozenset({"openai"})),
    "qwen": ("alibaba", frozenset({"alibaba"})),
    "tencent": ("tencent", frozenset({"tencent"})),
    "x-ai": ("xai", frozenset({"xai"})),
    "xiaomi": ("xiaomi", frozenset({"xiaomi"})),
}

# Fidélité numérique, du plus fidèle au plus dégradé
FIDELITE = {
    "fp32": 0, "float32": 0,
    "bf16": 1, "fp16": 1, "float16": 1, "bfloat16": 1,
    "fp8": 3, "float8": 3,
    "int8": 4,
    "fp6": 5,
    "fp4": 6, "mxfp4": 6, "nf4": 6, "int4": 6,
}
# Paramètres du contrat de campagne. Une route qui n'en accepte pas un impose
# de l'omettre, et un candidat mesuré sans `seed` n'est plus comparable aux
# autres sur le même pied
PARAMETRES_CONTRAT = ("temperature", "top_p", "seed", "max_tokens")

MARGE_PROMPT = 8192


def norm(v: Any) -> str:
    return re.sub(r"[\s_]+", "-", str(v or "").strip().lower())


def rang_fidelite(q: Any, reference: str | None = None) -> int | None:
    """Rang de fidélité d'une route, relatif au format de référence quand il est connu.

    L'échelle absolue de bits ci-dessus suppose que moins de bits vaut moins
    bien. C'est vrai d'un modèle publié en pleine précision et requantifié par
    des hébergeurs ; c'est faux d'un modèle entraîné avec quantification dans
    la boucle. Kimi K3 est publié en MXFP4, sans checkpoint BF16 : une route
    `fp8` n'y est pas moins dégradée, elle est requantifiée à partir du format
    publié, donc plus loin de la référence.

    Quand la carte déclare `format_reference`, avec sa source, c'est lui qui
    ordonne : la route qui sert ce format est fidèle, toute autre s'en écarte.
    Sans déclaration, l'échelle absolue s'applique et reste une hypothèse
    """
    cle = norm(q).replace("-", "")
    if cle in {"", "none", "unknown", "opaque", "notdisclosed"}:
        return None
    if reference:
        return 0 if cle == norm(reference).replace("-", "") else 4
    return FIDELITE.get(cle)


def politique_format(q: Any, editeur: bool, reference: str | None = None) -> tuple[str, int, int]:
    """Classer sans convertir `not_disclosed` en valeur de quantification"""
    cle = norm(q).replace("-", "")
    non_divulgue = cle in {"", "none", "unknown", "opaque", "notdisclosed"}
    if non_divulgue:
        if not editeur:
            return ("third_party_undisclosed", 3, 0)
        return ("publisher_not_disclosed", 1 if reference else 0, 0)
    rang = rang_fidelite(q, reference)
    if rang is None:
        return ("declared_unordered", 2, 0)
    if reference:
        if rang == 0:
            return ("declared_reference_exact", 0, 0)
        return ("declared_reference_mismatch", 2, 0)
    return ("declared_ranked", 1, rang)


def budget_de(ep: dict) -> int:
    """Budget de sortie réellement accordé, marge de prompt déduite"""
    mc, ctx = ep.get("max_completion_tokens"), ep.get("context_length")
    brut = mc if isinstance(mc, int) and mc > 0 else (ctx if isinstance(ctx, int) and ctx > 0 else 0)
    if isinstance(ctx, int) and ctx > 0:
        brut = min(brut, ctx - MARGE_PROMPT)
    return max(0, brut)


def editeur_canonique(model: str) -> str | None:
    """Résoudre l'éditeur depuis l'espace de noms public du modèle"""
    contrat = EDITEURS_CANONIQUES.get(norm(model.split("/")[0]))
    return contrat[0] if contrat else None


def est_editeur(ep: dict, model: str) -> bool:
    """L'endpoint est-il servi par celui qui publie le modèle ?

    L'identifiant OpenRouter porte l'éditeur en préfixe (`moonshotai/kimi-k3`),
    et l'étiquette d'endpoint reprend ce préfixe quand l'éditeur sert lui-même
    """
    contrat = EDITEURS_CANONIQUES.get(norm(model.split("/")[0]))
    if contrat is None:
        return False
    editeur, noms = contrat
    return (
        norm(ep.get("provider_name")) in noms
        and norm(str(ep.get("tag") or "").split("/")[0]) == editeur
    )


def contrat_quantification(ep: dict, model: str) -> dict[str, Any]:
    """Construire le contrat fermé de quantification de selection-route/v3"""
    brut = ep.get("quantization")
    if isinstance(brut, str) and brut.strip() and norm(brut) not in {"unknown", "opaque"}:
        return {"status": "declared", "value": brut.strip()}
    editeur = editeur_canonique(model)
    if est_editeur(ep, model) and editeur is not None:
        return {
            "status": "not_disclosed",
            "value": None,
            "basis": "publisher_managed_api",
            "publisher": editeur,
        }
    raise ValueError("quantification non déclarée sur une route tierce")


def evaluer(ep: dict, model: str, reference: str | None = None) -> dict:
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
    if budget < 1:
        exclusions.append("budget de sortie non positif ou absent")
    # Les réserves n'excluent pas, elles se signalent au moment de collecter
    reserves = []
    if norm(ep.get("status")) not in ("", "0", "none", "null"):
        reserves.append(f"statut {ep.get('status')}")
    if dispo is not None and dispo < 95:
        reserves.append(f"disponibilité {dispo:.1f}% sur 30 jours")
    editeur = est_editeur(ep, model)
    quantification_declaree = (
        isinstance(ep.get("quantization"), str)
        and bool(ep["quantization"].strip())
        and norm(ep["quantization"]) not in {"unknown", "opaque"}
    )
    if not editeur and not quantification_declaree:
        exclusions.append("quantification non déclarée sur une route tierce")
    classe_format, ordre_classe, ordre_format = politique_format(
        ep.get("quantization"), editeur, reference
    )
    fidelite = rang_fidelite(ep.get("quantization"), reference)
    return {
        "tag": ep.get("tag") or ep.get("provider_name"),
        "provider_name": ep.get("provider_name"),
        "quantization": ep.get("quantization") or ("not_disclosed" if editeur else "non déclarée"),
        "quantization_status": "declared" if quantification_declaree else "not_disclosed",
        "publisher": editeur_canonique(model),
        "format_policy_class": classe_format,
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
            ordre_classe,
            ordre_format,
            0 if editeur else 1,
            len(manquants),
            str(ep.get("tag") or ""),
        ),
    }


def classer(model: str, reference: str | None = None) -> dict:
    url = f"https://openrouter.ai/api/v1/models/{model}/endpoints"
    r = requests.get(url, headers={"Accept": "application/json"}, timeout=20)
    if r.status_code >= 400:
        return {"modele": model, "erreur": f"HTTP {r.status_code}", "routes": []}
    eps = (r.json().get("data") or {}).get("endpoints") or []
    routes = [evaluer(e, model, reference) for e in eps]
    eligibles = sorted((x for x in routes if not x["exclusions"]), key=lambda x: x["_cle"])
    for x in routes:
        x.pop("_cle")
    return {
        "modele": model,
        "critere_version": CRITERE_VERSION,
        "format_reference": reference,
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
    ap.add_argument("--json", action="store_true", help="sortie machine, à consigner avec la campagne")
    args = ap.parse_args()

    pins: dict[str, str] = {}
    references: dict[str, str] = {}
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
                if e.get("format_reference"):
                    references.setdefault(e["model"], e["format_reference"])

    resultats = [classer(m, references.get(m)) for m in cibles]

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
