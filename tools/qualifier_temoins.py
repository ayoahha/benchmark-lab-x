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
      "qualification_set": [
        "temoins/positif.md",
        "temoins/negatif.md"
      ],
      "temoins": {
        "temoins/positif.md": {
          "producteur": "nom ou identifiant du générateur",
          "acces_au_verificateur": false,
          "consignes": "ce qui a été demandé au producteur",
          "resultat_attendu": {
            "pentagone-api": {
              "P0_PAGE": true,
              "P1_API_NUMERIC_TOTAL": true
            }
          }
        }
      }
    }

En mode v2, chaque clé de témoin est son chemin relatif canonique dans la
tâche. Seuls les prédicats déclarés dans `resultat_attendu` avant qualification
et confirmés par l'observation contribuent à la couverture positive ou négative

Usage :
    uv run tools/qualifier_temoins.py pentagone-rotatif
    uv run tools/qualifier_temoins.py pentagone-rotatif --json
"""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).parent.parent
NOM_NEUTRE = "reponse.md"

sys.path.insert(0, str(Path(__file__).parent))
from empreintes import empreinte  # noqa: E402
from moteur_rendu import descripteur  # noqa: E402
from protocole_v2 import (  # noqa: E402
    SCHEMA_COVERAGE,
    ContratV2Invalide,
    charger_json,
    construire_process_diagnostic,
    ecrire_json_immuable,
    empreinte_lock,
    chemin_relatif_sur,
    resoudre_sous,
    sha256_fichier,
    valider_environnement_observe,
    valider_lock,
    valider_resultat_carte,
)


def charger_qualification_set(dossier: Path, objet: dict) -> tuple[dict, list[Path]]:
    provenance = objet.get("temoins")
    qualification_set = objet.get("qualification_set")
    if not isinstance(provenance, dict) or not provenance:
        raise ContratV2Invalide("table des témoins absente de la provenance R-016")
    if (
        not isinstance(qualification_set, list)
        or not qualification_set
        or not all(isinstance(nom, str) and nom for nom in qualification_set)
        or len(qualification_set) != len(set(qualification_set))
    ):
        raise ContratV2Invalide("qualification_set R-016 absente ou invalide")
    sans_provenance = set(qualification_set) - set(provenance)
    if sans_provenance:
        raise ContratV2Invalide(
            f"témoin qualifiant sans provenance R-016: {sorted(sans_provenance)}"
        )

    chemins = []
    for nom in qualification_set:
        relatif = chemin_relatif_sur(nom, f"qualification_set.{nom}")
        parties = Path(relatif).parts
        if not parties or parties[0] != "temoins" or Path(relatif).suffix != ".md":
            raise ContratV2Invalide(f"témoin qualifiant hors de temoins/: {relatif}")
        path = resoudre_sous(dossier, relatif)
        if not path.is_file() or path.is_symlink():
            raise ContratV2Invalide(f"témoin qualifiant absent ou lié: {relatif}")
        chemins.append(path)
    return provenance, chemins


def noter_aveugle(temoin: Path, verificateur: Path, delai: int = 180) -> dict | None:
    """Même présentation neutre que la notation de campagne (R-010)"""
    with tempfile.TemporaryDirectory(prefix="temoin-") as tmp:
        neutre = Path(tmp) / NOM_NEUTRE
        shutil.copyfile(temoin, neutre)
        # Groupe de processus : au dépassement, le Chromium lancé par le
        # vérificateur doit mourir avec lui. Voir `executer_borne` dans
        # `rapport_campagne.py` pour ce que coûtait l'oubli
        proc = subprocess.Popen(["uv", "run", str(verificateur), str(neutre)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, start_new_session=True)
        try:
            sortie, _ = proc.communicate(timeout=delai)
            out = subprocess.CompletedProcess([], proc.returncode, sortie, "")
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                proc.kill()
            proc.communicate()
            return {"niveau_atteint": 0, "verdict": "FAIL", "cause": "délai dépassé"}
    if out.returncode != 0:
        return None
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        return None


def _resultat_processus_inobservable(
    cause_code: str,
    failure_stage: str,
    verifier_exit_code: int | None,
    stderr: str,
) -> dict:
    return {
        "etat": "UNKNOWN",
        "cause_code": cause_code,
        "predicates": {},
        "process_diagnostic": construire_process_diagnostic(
            failure_stage, verifier_exit_code, stderr
        ),
    }


def noter_v5(temoin: Path, verificateur: Path, card_id: str, delai: int = 180) -> dict:
    """Noter une seule carte v5 sous le même chemin neutre que la campagne"""
    with tempfile.TemporaryDirectory(prefix="temoin-v5-") as tmp:
        neutre = Path(tmp) / "response.md"
        shutil.copyfile(temoin, neutre)
        try:
            proc = subprocess.Popen(
                ["uv", "run", str(verificateur), "--card", card_id, str(neutre)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                start_new_session=True,
            )
        except OSError as exc:
            return _resultat_processus_inobservable(
                "VERIFY_PROCESS_ERROR", "spawn", None, str(exc)
            )
        try:
            sortie, erreur = proc.communicate(timeout=delai)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                proc.kill()
            _, erreur = proc.communicate()
            return _resultat_processus_inobservable(
                "VERIFY_TIMEOUT", "timeout", proc.returncode, erreur
            )
    if proc.returncode != 0:
        return _resultat_processus_inobservable(
            "VERIFY_PROCESS_ERROR", "exit", proc.returncode, erreur
        )
    try:
        result = json.loads(sortie, parse_float=str)
    except json.JSONDecodeError:
        return _resultat_processus_inobservable(
            "VERIFY_PROCESS_ERROR", "output", proc.returncode, erreur
        )
    return result if isinstance(result, dict) else _resultat_processus_inobservable(
        "VERIFY_PROCESS_ERROR", "output", proc.returncode, erreur
    )


def qualifier_v2(args) -> int:
    if not args.campaign_lock or not args.out_receipt:
        print("HOLD: --campaign-lock et --out-receipt sont requis ensemble", file=sys.stderr)
        return 2
    try:
        lock = valider_lock(charger_json(args.campaign_lock), RACINE)
        lock_hash = empreinte_lock(lock)
        dossier = RACINE / lock["task"]["task_dir"]
        provenance_path = dossier / "temoins/provenance.json"
        provenance, temoins_paths = charger_qualification_set(
            dossier, charger_json(provenance_path)
        )
        for card in lock["axes"]:
            for asset in card["verify_manifest"]["assets"]:
                path = RACINE / asset["path"]
                if not path.is_file() or sha256_fichier(path) != asset["sha256"]:
                    raise ContratV2Invalide(f"actif du vérificateur modifié: {asset['path']}")

        env = descripteur()
        valider_environnement_observe(lock, "measurement", env)
        env_hash = empreinte(env)
        witnesses = {}
        observations = {}
        for temoin in temoins_paths:
            nom = temoin.relative_to(dossier).as_posix()
            p = provenance.get(nom) or {}
            temoin_hash = sha256_fichier(temoin)
            witnesses[nom] = {
                "sha256": sha256_fichier(temoin),
                "producer": p.get("producteur"),
                "access_to_verifier": p.get("acces_au_verificateur"),
                "instructions": p.get("consignes"),
                "expected_result": p.get("resultat_attendu"),
            }
            observations[nom] = {}
            for card in lock["axes"]:
                verifier = resoudre_sous(RACINE, card["verifier_path"])
                resultat = noter_v5(temoin, verifier, card["id"], card["watchdog_s"])
                scored = resultat.get("etat") == "SCORED"
                observation = {
                    "score_card_id": card["id"],
                    "witness_sha256": temoin_hash,
                    "verify_hash": card["verify_hash"],
                    "measurement_environment_hash": env_hash,
                    "etat": resultat.get("etat"),
                    "cause_code": resultat.get("cause_code"),
                    "verdict": resultat.get("verdict") if scored else None,
                    "niveau": resultat.get("niveau") if scored else None,
                    "frontiere": resultat.get("frontiere") if scored else None,
                    "predicates": (resultat.get("predicates") or {}) if scored else {},
                    "measurements": (resultat.get("measurements") or {}) if scored else {},
                }
                if "process_diagnostic" in resultat:
                    observation["process_diagnostic"] = resultat["process_diagnostic"]
                valider_resultat_carte(
                    observation, card,
                    champ_predicats="predicates", champ_mesures="measurements",
                )
                observations[nom][card["id"]] = observation

        cards = {}
        complete = True
        attentes_conformes = True
        for card in lock["axes"]:
            couverture = {}
            for predicat in card["predicates"]:
                positifs, negatifs = [], []
                for nom, par_carte in observations.items():
                    resultat = par_carte[card["id"]]
                    attendu_global = witnesses[nom].get("expected_result")
                    attendu_carte = (
                        attendu_global.get(card["id"])
                        if isinstance(attendu_global, dict) else None
                    )
                    attendu = (
                        attendu_carte.get(predicat)
                        if isinstance(attendu_carte, dict) else None
                    )
                    if not isinstance(attendu, bool):
                        continue
                    valeur = resultat["predicates"].get(predicat)
                    if resultat["etat"] != "SCORED" or valeur is not attendu:
                        attentes_conformes = False
                        continue
                    if attendu is True:
                        positifs.append(nom)
                    else:
                        negatifs.append(nom)
                couverture[predicat] = {"positive": positifs, "negative": negatifs}
                complete = complete and bool(positifs) and bool(negatifs)
            cards[card["id"]] = {
                "verify_hash": card["verify_hash"],
                "predicates": couverture,
            }
        independants = all(
            w.get("access_to_verifier") is False
            and w.get("producer")
            and w.get("instructions")
            and isinstance(w.get("expected_result"), dict)
            and bool(w["expected_result"])
            for w in witnesses.values()
        )
        receipt = {
            "schema_version": SCHEMA_COVERAGE,
            "campaign_lock_hash": lock_hash,
            "task_version": lock["task"]["task_version"],
            "prompt_sha256": lock["task"]["prompt_sha256"],
            "measurement_environment": env,
            "measurement_environment_hash": env_hash,
            "provenance_path": provenance_path.relative_to(dossier).as_posix(),
            "provenance_sha256": sha256_fichier(provenance_path),
            "witnesses": witnesses,
            "observations": observations,
            "cards": cards,
            "qualified": bool(independants and attentes_conformes and complete),
        }
        try:
            empreinte(receipt)
        except ValueError as exc:
            raise ContratV2Invalide(f"reçu R-016 non canonique: {exc}") from exc
        ecrire_json_immuable(args.out_receipt, receipt)
    except ContratV2Invalide as exc:
        print(f"HOLD: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"qualified": receipt["qualified"], "receipt": str(args.out_receipt)},
                     ensure_ascii=False, indent=2))
    return 0 if receipt["qualified"] else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("carte", nargs="?")
    ap.add_argument("--jeu", default="dev")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--campaign-lock", type=Path)
    ap.add_argument("--out-receipt", type=Path)
    args = ap.parse_args()

    if args.campaign_lock or args.out_receipt:
        return qualifier_v2(args)
    if not args.carte:
        ap.error("carte requise hors mode v2")

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
    lignes, bloquants, paliers = [], [], []
    for t in temoins:
        note = noter_aveugle(t, verificateur)
        if note and not paliers:
            paliers = list((note.get("niveaux") or {}).keys())
        p = provenance.get(t.name, {})
        niveau = (note or {}).get("niveau_atteint")
        motifs = []
        if not p:
            motifs.append("provenance non déclarée")
        else:
            if p.get("acces_au_verificateur") is not False:
                motifs.append("le producteur voyait le vérificateur")
            if not p.get("producteur"):
                motifs.append("producteur non nommé")
        if note is None:
            motifs.append("le vérificateur n'a rien rendu")
        lignes.append({
            "temoin": t.name,
            "niveau_observe": niveau,
            "producteur": p.get("producteur"),
            "acces_au_verificateur": p.get("acces_au_verificateur"),
            "qualifie": not motifs,
            "motifs": motifs,
        })
        if motifs:
            bloquants.append(t.name)

    def couverture(retenus: list[dict]) -> dict:
        """Quels paliers possèdent un témoin positif et un témoin négatif.

        Sur une carte à paliers, la polarité ne se déclare pas : elle se déduit.
        Un témoin qui atteint le niveau L franchit les paliers 1 à L, ce qui en
        fait leur témoin positif, et bute sur les suivants, ce qui en fait leur
        témoin négatif. Une liste `predicats_couverts` écrite à la main était à
        la fois redondante et fausse : elle nommait `P_precision_ref`, un
        identifiant qui n'existe nulle part dans le vérificateur
        """
        niveaux = [l["niveau_observe"] for l in retenus if l["niveau_observe"] is not None]
        sans_positif = [nom for k, nom in enumerate(paliers, start=1)
                        if not any(n >= k for n in niveaux)]
        sans_negatif = [nom for k, nom in enumerate(paliers, start=1)
                        if not any(n < k for n in niveaux)]
        return {
            "paliers_total": len(paliers),
            "sans_temoin_positif": sans_positif,
            "sans_temoin_negatif": sans_negatif,
            "complete": bool(paliers) and not sans_positif and not sans_negatif,
        }

    qualifies = [l for l in lignes if l["qualifie"]]
    couv_reelle = couverture(qualifies)
    # Deuxième lecture, diagnostique : ce que ces témoins couvriraient s'ils
    # étaient produits indépendamment. Elle sépare ce qui manque en process de
    # ce qui manque en substance, et montre qu'ici les deux manquent
    couv_potentielle = couverture(lignes)

    rapport = {
        "carte": args.carte,
        "regle": "R-016",
        "temoins": lignes,
        "couverture": couv_reelle,
        "couverture_si_temoins_independants": couv_potentielle,
        "matrice_complete": couv_reelle["complete"] and not bloquants,
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
        print(f"Matrice complète sur les {couv_reelle['paliers_total']} paliers.")
        return 0

    def resume(c: dict) -> str:
        if not c["paliers_total"]:
            return "aucun palier connu"
        def plage(noms: list[str]) -> str:
            if not noms:
                return "aucun"
            idx = [paliers.index(n) + 1 for n in noms]
            return f"{len(noms)} paliers, du {min(idx)}e au {max(idx)}e"
        return (f"sans témoin positif : {plage(c['sans_temoin_positif'])}\n"
                f"      sans témoin négatif : {plage(c['sans_temoin_negatif'])}")

    print(f"Matrice incomplète : {len(bloquants)} témoins sur {len(lignes)} ne qualifient rien.")
    print(f"  En l'état      : {resume(couv_reelle)}")
    print(f"  Si les mêmes témoins étaient produits sans accès au vérificateur :")
    print(f"      {resume(couv_potentielle)}")
    print()
    print("Deux manques distincts. Le premier est de procédure et se répare en\n"
          "faisant produire les témoins par quelqu'un d'autre. Le second est de\n"
          "substance : aucun témoin connu n'atteint le haut de l'échelle, donc\n"
          "ces paliers restent non validés même après correction du premier.\n"
          "Tant que la matrice est incomplète, la carte reste hors classement\n"
          "publiable (R-016, R-027).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
