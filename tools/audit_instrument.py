# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Audit humain de l'instrument, tirage à graine consignée (R-026).

Ce que l'audit demande, et rien d'autre : « le résultat noté du code, verdict
et niveau éventuel, décrit-il ce que je vois ? ». L'auditeur ne compare pas des
modèles, ne classe pas, ne discute pas d'un bon résultat. Il vérifie que le
code n'a pas noté autre chose que ce qui est écrit dans la réponse.

L'auditeur ne voit ni l'alias, ni le modèle, ni le fournisseur : un verdict qui
paraît juste parce qu'il vient du modèle attendu ne prouve rien. Le lien entre
le dossier présenté et le run réel n'existe que dans le fichier de correspondance,
écrit à part et à lire après.

Le tirage suit R-026 : les sorties sont ordonnées par leur clé de run, une
graine consignée départage les ex æquo, puis jusqu'à trois sorties hautes et
trois basses sont sélectionnées. Une strate incomplète est compensée par
l'autre ; sous six sorties, toutes sont auditées.

Un verdict ou un niveau faux invalide la page, incrémente `verify-vM` et impose
la renotation complète.

Usage :
    uv run tools/audit_instrument.py runs/<campagne>/results-data.json --graine 1789
    uv run tools/audit_instrument.py runs/<campagne>/results-data.json --graine 1789 --appliquer
"""

import argparse
import hashlib
import json
import random
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

TAILLE_STRATE = 3


def cle_de_run(r: dict) -> tuple:
    """Clé d'ordre définie en R-019 : niveau pour une carte à paliers"""
    return (-(r.get("niveau_opposable") if r.get("niveau_opposable") is not None else -1),)


def selectionner(runs: list[dict], graine: int) -> tuple[list[dict], str]:
    """Trois sorties hautes et trois basses, ex æquo départagés par la graine"""
    scores = [r for r in runs if r.get("etat") == "SCORED"
              and r.get("niveau_opposable") is not None]
    if not scores:
        return [], "aucune sortie scorée"
    alea = random.Random(graine)
    # La graine ne choisit pas les strates, elle ne départage que les ex æquo :
    # sans elle, l'ordre des ex æquo dépendrait du système de fichiers
    brouille = scores[:]
    alea.shuffle(brouille)
    ordonne = sorted(brouille, key=cle_de_run)
    if len(ordonne) <= 2 * TAILLE_STRATE:
        return ordonne, f"population de {len(ordonne)} sorties, toutes auditées"
    hautes = ordonne[:TAILLE_STRATE]
    basses = ordonne[-TAILLE_STRATE:]
    return hautes + basses, f"{TAILLE_STRATE} hautes et {TAILLE_STRATE} basses sur {len(ordonne)}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("rapport", type=Path, help="results-data.json d'une campagne")
    ap.add_argument("--graine", type=int, required=True,
                    help="graine consignée ; la même graine rend le même tirage")
    ap.add_argument("--sortie", type=Path, default=None,
                    help="dossier de l'audit (défaut : <campagne>/audit-<graine>)")
    ap.add_argument("--appliquer", action="store_true",
                    help="écrire réellement le dossier d'audit sur le disque")
    args = ap.parse_args()

    data = json.loads(args.rapport.read_text(encoding="utf-8"))
    runs = data.get("runs") or []
    tires, motif = selectionner(runs, args.graine)
    if not tires:
        print(f"rien à auditer : {motif}", file=sys.stderr)
        return 1

    racine_campagne = args.rapport.parent
    sortie = args.sortie or racine_campagne / f"audit-{args.graine}"

    print(f"carte          : {data.get('carte')}")
    print(f"verify         : {data.get('verify_version')} / {str(data.get('verify_hash'))[:16]}…")
    print(f"graine         : {args.graine}")
    print(f"tirage         : {motif}")
    print(f"dossier        : {sortie}{'' if args.appliquer else '  (simulation)'}\n")

    correspondance, presentes = [], []
    for i, r in enumerate(tires, start=1):
        piece = f"piece-{i:02d}"
        origine = None
        for d in (racine_campagne,):
            for cand in d.glob(f"{data.get('carte')}__{r['alias']}__r{r['run']}*"):
                if (cand / "response.md").is_file():
                    origine = cand
                    break
        presentes.append({
            "piece": piece,
            "niveau_note_par_le_code": r.get("niveau_opposable"),
            "verdict_note_par_le_code": r.get("verdict"),
            "paliers_total": r.get("paliers_total"),
            "frontiere": r.get("frontiere"),
            "ecart_reference": r.get("ecart_reference"),
            "question": "le résultat noté du code décrit-il ce que je vois ?",
            "reponse_auditeur": None,
        })
        correspondance.append({"piece": piece, "alias": r["alias"], "run": r["run"],
                               "dossier": str(origine) if origine else None})
        print(f"  {piece}  niveau {str(r.get('niveau_opposable')):>3}  "
              f"frontière {str(r.get('frontiere'))[:24]:24}  ← {origine.name if origine else 'introuvable'}")

    if not args.appliquer:
        print("\nSimulation. Relancer avec --appliquer pour écrire le dossier d'audit.")
        return 0

    sortie.mkdir(parents=True, exist_ok=True)
    for c, p in zip(correspondance, presentes):
        if not c["dossier"]:
            continue
        d = sortie / c["piece"]
        d.mkdir(exist_ok=True)
        shutil.copyfile(Path(c["dossier"]) / "response.md", d / "reponse.md")
        (d / "note-du-code.json").write_text(
            json.dumps(p, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    graine_empreinte = hashlib.sha256(str(args.graine).encode()).hexdigest()[:16]
    (sortie / "protocole.json").write_text(json.dumps({
        "regle": "R-026",
        "date": datetime.now(timezone.utc).isoformat(),
        "carte": data.get("carte"),
        "verify_version": data.get("verify_version"),
        "verify_hash": data.get("verify_hash"),
        "measurement_context_hash": data.get("measurement_context_hash"),
        "graine": args.graine,
        "graine_empreinte": graine_empreinte,
        "tirage": motif,
        "question_posee": "le résultat noté du code, verdict et niveau éventuel, "
                          "décrit-il ce que je vois ?",
        "consigne": "Répondre oui ou non par pièce dans note-du-code.json, champ "
                    "reponse_auditeur. Un seul non invalide la page, incrémente "
                    "verify-vM et impose la renotation complète.",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # La correspondance existe pour pouvoir remonter après l'audit, jamais
    # pendant : elle est écrite hors des pièces présentées
    (racine_campagne / f"audit-{args.graine}-correspondance.json").write_text(
        json.dumps({"graine": args.graine, "pieces": correspondance},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"\nDossier d'audit écrit. La correspondance pièce → candidat est dans "
          f"{racine_campagne / f'audit-{args.graine}-correspondance.json'}, "
          f"à ne lire qu'après avoir répondu.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
