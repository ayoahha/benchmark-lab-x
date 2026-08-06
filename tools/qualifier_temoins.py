# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Qualifier la matrice de témoins d'une carte (R-016).

Un prédicat n'est qualifié que s'il possède au moins un témoin positif et un
témoin négatif, et que la provenance de ces témoins est consignée. La partie
mécanique se vérifie : passer chaque témoin dans le vérificateur et comparer le
niveau obtenu au niveau attendu. La partie qui compte ne se vérifie pas par du
code : **le producteur du témoin a-t-il eu accès au vérificateur ?**

Un témoin écrit par l'auteur du vérificateur ne prouve rien. Il montre que le
code fait ce que son auteur croit qu'il fait, ce qui est vrai par construction.
C'est pourquoi cet outil refuse de qualifier une carte dont la provenance n'est
pas déclarée, et refuse également de la qualifier quand la provenance déclare
que le producteur voyait le vérificateur. Il ne peut pas être plus indulgent :
un contre-exemple conforme à la tâche mais rejeté par le vérificateur casse la
carte, pas la réponse, et c'est précisément ce qu'un témoin indépendant trouve.

La provenance se déclare dans `tasks/<jeu>/<carte>/temoins/provenance.json` :

    {
      "temoins": {
        "anchor-T5-reference.md": {
          "producteur": "nom ou identifiant du générateur",
          "acces_au_verificateur": false,
          "consignes": "ce qui a été demandé au producteur",
          "resultat_attendu": {"niveau_min": 45, "niveau_max": 51},
          "predicats_couverts": ["P24_precision_ref_1e-15"],
          "polarite": "positif"
        }
      }
    }

Usage :
    uv run tools/qualifier_temoins.py pentagone-rotatif
    uv run tools/qualifier_temoins.py pentagone-rotatif --json
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).parent.parent
NOM_NEUTRE = "reponse.md"


def noter_aveugle(temoin: Path, verificateur: Path, delai: int = 180) -> dict | None:
    """Même présentation neutre que la notation de campagne (R-010)"""
    with tempfile.TemporaryDirectory(prefix="temoin-") as tmp:
        neutre = Path(tmp) / NOM_NEUTRE
        shutil.copyfile(temoin, neutre)
        try:
            out = subprocess.run(["uv", "run", str(verificateur), str(neutre)],
                                 capture_output=True, text=True, timeout=delai)
        except subprocess.TimeoutExpired:
            return {"niveau_atteint": 0, "verdict": "FAIL", "cause": "délai dépassé"}
    if out.returncode != 0:
        return None
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("carte")
    ap.add_argument("--jeu", default="dev")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    dossier = RACINE / "tasks" / args.jeu / args.carte
    verificateur = RACINE / "tools" / f"verifier_{args.carte.split('-')[0]}.py"
    if not dossier.is_dir() or not verificateur.is_file():
        print(f"carte ou vérificateur introuvable : {dossier}, {verificateur}", file=sys.stderr)
        return 2

    provenance_f = dossier / "temoins" / "provenance.json"
    provenance = {}
    if provenance_f.is_file():
        provenance = (json.loads(provenance_f.read_text(encoding="utf-8")) or {}).get("temoins", {})

    temoins = sorted(dossier.glob("anchor-*.md")) + sorted((dossier / "temoins").glob("*.md"))
    lignes, bloquants = [], []
    for t in temoins:
        note = noter_aveugle(t, verificateur)
        p = provenance.get(t.name, {})
        attendu = p.get("resultat_attendu") or {}
        niveau = (note or {}).get("niveau_atteint")
        conforme = None
        if note is not None and attendu:
            lo, hi = attendu.get("niveau_min"), attendu.get("niveau_max")
            conforme = ((lo is None or (niveau is not None and niveau >= lo))
                        and (hi is None or (niveau is not None and niveau <= hi)))
        motifs = []
        if not p:
            motifs.append("provenance non déclarée")
        else:
            if p.get("acces_au_verificateur") is not False:
                motifs.append("le producteur voyait le vérificateur")
            if not p.get("predicats_couverts"):
                motifs.append("aucun prédicat couvert déclaré")
            if not attendu:
                motifs.append("résultat attendu non déclaré")
            if conforme is False:
                motifs.append(f"niveau observé {niveau} hors de l'intervalle attendu")
        if note is None:
            motifs.append("le vérificateur n'a rien rendu")
        lignes.append({
            "temoin": t.name,
            "polarite": p.get("polarite"),
            "niveau_observe": niveau,
            "resultat_attendu": attendu or None,
            "producteur": p.get("producteur"),
            "acces_au_verificateur": p.get("acces_au_verificateur"),
            "predicats_couverts": p.get("predicats_couverts") or [],
            "qualifie": not motifs,
            "motifs": motifs,
        })
        if motifs:
            bloquants.append(t.name)

    couverts_pos, couverts_neg = set(), set()
    for l in lignes:
        if not l["qualifie"]:
            continue
        cible = couverts_pos if l["polarite"] == "positif" else couverts_neg
        cible.update(l["predicats_couverts"])
    predicats_complets = sorted(couverts_pos & couverts_neg)

    rapport = {
        "carte": args.carte,
        "regle": "R-016",
        "temoins": lignes,
        "predicats_avec_temoin_positif_et_negatif": predicats_complets,
        "matrice_complete": bool(predicats_complets) and not bloquants,
        "bloquants": bloquants,
    }

    if args.json:
        print(json.dumps(rapport, ensure_ascii=False, indent=1))
        return 0 if rapport["matrice_complete"] else 1

    print(f"carte : {args.carte}   règle R-016\n")
    for l in lignes:
        etat = "qualifié" if l["qualifie"] else "NON QUALIFIÉ"
        print(f"  {l['temoin']:34} niveau {str(l['niveau_observe']):>4}  {etat}")
        for m in l["motifs"]:
            print(f"      - {m}")
    print()
    if rapport["matrice_complete"]:
        print(f"Matrice complète sur {len(predicats_complets)} prédicats.")
        return 0
    print(f"Matrice incomplète : {len(bloquants)} témoins sur {len(lignes)} ne qualifient rien.")
    print("Tant que la matrice est incomplète, la carte reste hors classement publiable\n"
          "(R-016, R-027). Un témoin écrit par l'auteur du vérificateur ne prouve\n"
          "que la cohérence du code avec lui-même.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
