# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Produit les données techniques agrégées d'une campagne au format JSON.

Une ligne par run attendu, avec de quoi rejouer la notation et vérifier chaque
chiffre publié. Ce fichier machine reste sous `runs/` et sert d'entrée à la page
de résultats.

Ce que ce rapporteur garantit, et que la version précédente ne garantissait pas :

- le vérificateur voit la réponse sous un chemin neutre, sans alias ni chemin
  de run d'origine (R-010) ;
- chaque run attendu porte l'un des cinq états terminaux, y compris ceux qui
  n'ont jamais été tentés (R-013) ;
- un candidat n'est classé que si tous ses runs attendus sont `SCORED`, et la
  page est marquée provisoire dès qu'un seul ne l'est pas (R-020, R-027) ;
- `verify_hash` porte sur un manifeste canonique des fichiers côté juge, en
  SHA-256 complet, et non sur une concaténation d'octets tronquée (R-015).

Usage :
    uv run tools/rapport_campagne.py <carte> <dossier_de_runs>... > runs/<campagne>/results-data.json
"""

import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from empreintes import empreinte  # noqa: E402
from protocole_v2 import (  # noqa: E402
    PROTOCOLE_VERSION as PROTOCOLE_V2,
    ContratV2Invalide,
    agreger_scores,
    charger_json,
    empreinte_lock,
    valider_chaine_collecte,
    valider_etat_collecte,
    valider_evenements_panel,
    valider_hold_operateur,
    valider_lock,
    valider_recu_audit,
    valider_recu_couverture,
    valider_recu_score,
)

CHAMPS_RUN = ("task", "task_version", "run", "date", "backend", "model_requested",
              "model_served", "revision", "provider_pinned", "provider_served",
              "finish_reason", "duration_s", "cost_usd", "prompt_hash",
              "payload_hash", "execution_manifest_hash", "regime_confidentialite",
              "protocol_version", "params_omitted", "quantization_servie")

SCHEMA_CONTEXTE = "benchmark-lab-x/measurement-context/v1"
PROTOCOLE_VERSION = "benchmark-lab-x/protocol/v1"

# Nom sous lequel la réponse est présentée au vérificateur. Neutre par
# construction : il ne porte ni alias, ni numéro de run, ni tentative
NOM_NEUTRE = "reponse.md"


def actifs_cote_juge(carte: str, verificateur: Path) -> list[dict]:
    """Fichiers qui définissent ou calibrent la note, triés par chemin POSIX.

    L'ancienne version hachait `tools/*_pentagone.py` par simple concaténation,
    ce qui laissait dehors le cache d'oracle et les reçus de témoins : deux
    calibrages différents rendaient la même empreinte
    """
    racine = Path(__file__).parent.parent
    candidats: list[Path] = [verificateur]
    famille = carte.split("-")[0]
    candidats += sorted(verificateur.parent.glob(f"oracle_{famille}.py"))
    dossier_carte = racine / "tasks" / "dev" / carte
    for motif in ("oracle-cache.json", "verify.md", "anchor-*.md", "temoins/*"):
        candidats += sorted(dossier_carte.glob(motif))
    vus, manifeste = set(), []
    for f in candidats:
        if not f.is_file() or f in vus:
            continue
        vus.add(f)
        manifeste.append({
            "path": f.resolve().relative_to(racine.resolve()).as_posix(),
            "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
        })
    return sorted(manifeste, key=lambda x: x["path"])


def instrument_qualifie(carte: str) -> tuple[bool, list[str]]:
    """La matrice de témoins de la carte est-elle qualifiée au sens R-016 ?

    Le contrôle lit `temoins/provenance.json` et **ne rejoue pas le
    vérificateur** : le rejouer ajouterait un lancement de Chromium par témoin
    à chaque rapport, pour une information qui ne change qu'avec le calibrage.

    Ce qui est vérifié ici est la condition nécessaire et la moins chère :
    chaque témoin déclare une provenance, et son producteur n'avait pas accès
    au vérificateur. Un témoin écrit par l'auteur du vérificateur prouve
    seulement la cohérence du code avec lui-même. La couverture palier par
    palier, elle, reste dans `tools/qualifier_temoins.py`, qui doit exécuter
    les témoins pour connaître leur niveau ; elle rejoindra ce contrôle le jour
    où des témoins réellement indépendants existeront, puisqu'aujourd'hui aucun
    ne franchit cette première condition.

    Échoue du côté sûr : pas de fichier de provenance, pas de qualification
    """
    f = Path(__file__).parent.parent / "tasks" / "dev" / carte / "temoins" / "provenance.json"
    if not f.is_file():
        return False, ["aucun fichier de provenance de témoins (R-016)"]
    try:
        temoins = (json.loads(f.read_text(encoding="utf-8")) or {}).get("temoins") or {}
    except (OSError, json.JSONDecodeError) as exc:
        return False, [f"provenance de témoins illisible : {type(exc).__name__}"]
    if not temoins:
        return False, ["provenance de témoins vide (R-016)"]
    motifs = []
    for nom, t in sorted(temoins.items()):
        if t.get("acces_au_verificateur") is not False:
            motifs.append(f"{nom} : producteur non aveugle au vérificateur")
        elif not t.get("producteur"):
            motifs.append(f"{nom} : producteur non nommé")
    return (not motifs), motifs


def version_verificateur(carte: str) -> str:
    """Étiquette `verify-vM` déclarée par la carte"""
    md = Path(__file__).parent.parent / "tasks" / "dev" / carte / "task.md"
    try:
        m = re.search(r"\bverify-v(\d+)\b", md.read_text(encoding="utf-8"))
    except OSError:
        return "inconnue"
    return f"verify-v{m.group(1)}" if m else "inconnue"


def descripteur_environnement() -> dict:
    """Environnement du vérificateur, épinglé (R-015)"""
    sys.path.insert(0, str(Path(__file__).parent))
    from moteur_rendu import descripteur

    return descripteur()


def executer_borne(cmd: list[str], delai: int) -> subprocess.CompletedProcess:
    """Exécuter une commande sous délai, en tuant TOUTE sa descendance au dépassement.

    `subprocess.run(timeout=...)` ne tue que le processus lancé, pas ses enfants.
    Le vérificateur lance `uv`, qui lance Python, qui lance Chromium : au
    dépassement, seul `uv` mourait et le navigateur restait à tourner. Mesuré
    le 2026-08-06 sur cette machine : douze Chromium orphelins consommaient
    chacun un cœur entier, l'un depuis plus de vingt-quatre heures, pour une
    charge moyenne de 18 sur 18 cœurs. Chaque notation d'une page qui ne rend
    pas la main en laissait un de plus.

    Le groupe de processus règle le problème : `start_new_session` en crée un
    nouveau, et le signal frappe le groupe entier plutôt qu'un seul membre
    """
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, start_new_session=True)
    try:
        sortie, erreur = proc.communicate(timeout=delai)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()
        proc.communicate()
        raise
    return subprocess.CompletedProcess(cmd, proc.returncode, sortie, erreur)


def noter_aveugle(dossier: Path, verificateur: Path, delai: int = 180) -> dict | None:
    """Noter un run sans que le vérificateur puisse voir de quel candidat il vient.

    R-010 : la réponse est recopiée sous un nom neutre, dans un dossier
    temporaire dont le chemin ne contient ni alias ni numéro de run. Invoquer le
    vérificateur directement depuis `runs/<carte>__<alias>__r<n>/` reste
    diagnostique et n'est pas éligible à une page validée.

    Un dépassement de délai est un résultat, pas une panne : une page qui
    recalcule toute la trajectoire à chaque appel dépasse le budget de la carte,
    et c'est un échec du candidat. Un run normal se vérifie en moins d'une
    seconde ; 180 s laissent trois ordres de grandeur de marge. C'est ici, et
    pas dans le vérificateur, que le budget est opposable : Playwright
    n'interrompt pas du JavaScript synchrone
    """
    source = dossier / "response.md"
    if not source.is_file():
        return None
    with tempfile.TemporaryDirectory(prefix="notation-") as tmp:
        neutre = Path(tmp) / NOM_NEUTRE
        shutil.copyfile(source, neutre)
        try:
            out = executer_borne(["uv", "run", str(verificateur), str(neutre)], delai)
        except subprocess.TimeoutExpired:
            return {"niveau_atteint": 0, "niveaux": {}, "frontiere": "A1_api_totale",
                    "mesures": {"depassement_temps_s": delai},
                    "verdict": "FAIL", "cause": "budget de temps dépassé"}
    if out.returncode != 0:
        # Le vérificateur a refusé de noter : environnement non conforme, ou
        # défaut d'instrument. Ce n'est pas une note nulle du candidat
        return {"_instrument": (out.stderr or "").strip()[-300:] or f"code {out.returncode}"}
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        return None


def etat_terminal(dossier: Path, meta: dict | None, note: dict | None) -> tuple[str, dict]:
    """Rendre l'état R-013 d'un run tenté, et ce qui le justifie.

    Les cinq états sont exclusifs. `MISSING` n'est pas décidable ici : il porte
    sur un run planifié dont aucun dossier n'existe, et se déduit plus haut
    """
    for etat in ("INELIGIBLE", "INFRA_ERROR"):
        marqueur = dossier / etat
        if marqueur.exists():
            try:
                corps = json.loads(marqueur.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                corps = {}
            return etat, {"motif": corps.get("motif"), "detail": corps.get("detail")}

    if (dossier / "FAILED").exists() and not (dossier / "COMPLETE").exists():
        # Un appel parti qui n'a pas rendu de sortie scoreable. Les tentatives
        # autorisées sont gérées par le lanceur ; à la clôture, ce qui reste
        # sans COMPLETE a épuisé ce qui lui était accordé
        motif = (dossier / "FAILED").read_text(encoding="utf-8").splitlines()[0]
        return "INFRA_ERROR", {"motif": motif}

    if not (dossier / "COMPLETE").exists():
        return "INFRA_ERROR", {"motif": "run interrompu, aucun marqueur COMPLETE"}

    if note is not None and "_instrument" in note:
        return "UNKNOWN", {"motif": "l'instrument a refusé de noter",
                           "detail": note["_instrument"]}
    if note is None:
        return "UNKNOWN", {"motif": "le vérificateur n'a pas rendu de résultat lisible"}

    m = meta or {}
    if m.get("finish_reason") == "length":
        # R-013 : distinguer un arrêt prématuré du fournisseur d'un épuisement
        # réel du budget préenregistré. Sans cette distinction, une coupure de
        # fournisseur se lisait comme une faute du candidat
        budget = ((m.get("params") or {}).get("max_tokens")
                  or (m.get("budget_sortie") or {}).get("max_tokens"))
        consomme = (m.get("usage") or {}).get("completion_tokens")
        if not isinstance(consomme, int) or not isinstance(budget, int) or consomme < budget:
            return "UNKNOWN", {"motif": "finish_reason=length sous le budget résolu",
                               "detail": f"completion_tokens={consomme}, max_tokens={budget}"}
        return "SCORED", {"verdict": "FAIL",
                          "motif": "budget de sortie épuisé, arrêt prouvé"}

    return "SCORED", {"verdict": note.get("verdict")}


def runs_attendus(racine: Path, conf: dict | None, carte: str, alias_vus: set[str]) -> dict:
    """Plan de campagne : quels runs auraient dû exister.

    Sans `campaign.toml`, le plan se déduit de ce qui a été collecté, ce qui ne
    peut jamais révéler un `MISSING`. Le fichier de campagne est donc la seule
    source honnête du plan, et son absence est signalée
    """
    if conf and conf.get("candidats") and conf.get("runs"):
        return {"source": "campaign.toml",
                "alias": sorted(conf["candidats"]),
                "runs": list(range(1, int(conf["runs"]) + 1))}
    return {"source": "déduit des runs présents, MISSING indétectable",
            "alias": sorted(alias_vus), "runs": [1, 2, 3, 4]}


def _score_v2(
    campaign_dir: Path,
    lock: dict,
    lock_hash: str,
    card: dict,
    alias: str,
    run: int,
) -> dict:
    collection_id = f"{alias}__r{run}"
    etat_path = campaign_dir / "collections" / collection_id / "collection-state.json"
    if etat_path.is_file():
        etat_collecte = charger_json(etat_path)
        cellule = next(
            c for c in lock["collections"] if c["collection_id"] == collection_id
        )
        valider_etat_collecte(etat_collecte, lock_hash, cellule)
        etat = etat_collecte["state"]
        return {
            "alias": alias,
            "run": run,
            "etat": etat,
            "cause_code": etat_collecte.get("cause_code"),
        }
    tentatives = sorted((campaign_dir / "collections" / collection_id).glob("attempt-*"))
    recus = [d / "collection-receipt.json" for d in tentatives
            if (d / "collection-receipt.json").is_file() and (d / "COMPLETE").is_file()]
    if len(recus) != 1:
        return {"alias": alias, "run": run, "etat": "MISSING",
                "cause_code": "COLLECTION_UNAVAILABLE"}
    collection = charger_json(recus[0])
    cellule = next(
        c for c in lock["collections"] if c["collection_id"] == collection_id
    )
    attempt_path = recus[0].parent / "attempt-receipt.json"
    if not attempt_path.is_file() or attempt_path.is_symlink():
        raise ContratV2Invalide(f"reçu de tentative absent: {collection_id}")
    valider_chaine_collecte(
        charger_json(attempt_path), collection, lock_hash, cellule
    )
    response_path = recus[0].parent / "response.md"
    if (not response_path.is_file() or response_path.is_symlink()
            or hashlib.sha256(response_path.read_bytes()).hexdigest()
            != (collection.get("candidate") or {}).get("sha256")):
        raise ContratV2Invalide(f"preuve response.md absente ou modifiée: {collection_id}")
    response_json_path = recus[0].parent / "raw.json"
    if (not response_json_path.is_file() or response_json_path.is_symlink()
            or hashlib.sha256(response_json_path.read_bytes()).hexdigest()
            != collection.get("response_json_sha256")):
        raise ContratV2Invalide(f"preuve raw.json absente ou modifiée: {collection_id}")
    collection_hash = empreinte(collection)
    score_path = (campaign_dir / "scores" / collection_hash / card["id"]
                  / f"{card['verify_hash']}.json")
    if not score_path.is_file():
        return {"alias": alias, "run": run, "etat": "MISSING",
                "cause_code": "SCORE_RECEIPT_MISSING",
                "collection_receipt_hash": collection_hash}
    score = charger_json(score_path)
    valider_recu_score(score, lock, lock_hash, card, cellule, collection, collection_hash)
    return {
        "alias": alias,
        "run": run,
        "etat": score.get("etat"),
        "cause_code": score.get("cause_code"),
        "verdict": score.get("verdict"),
        "niveau": score.get("niveau"),
        "frontiere": score.get("frontiere"),
        "predicats": score.get("predicats") or {},
        "mesures": score.get("mesures") or {},
        "measurement_context_hash": score.get("measurement_context_hash"),
        "collection_receipt_hash": collection_hash,
    }


def _rangs_competition(candidats: list[dict], kind: str) -> None:
    def valeur(candidat: dict) -> int | None:
        if candidat.get("panel_state") == "RETIRE":
            return None
        agregat = candidat["agregat"]
        if not agregat.get("classement_valide"):
            return None
        if kind == "binary":
            return 1 if agregat.get("verdict_retenu") == "PASS" else 0
        return agregat.get("niveau_retenu")
    valeurs = [v for c in candidats if (v := valeur(c)) is not None]
    for candidat in candidats:
        v = valeur(candidat)
        candidat["rang_provisoire"] = None if v is None else 1 + sum(x > v for x in valeurs)


def rapport_v2(campaign_dir: Path, conf: dict) -> int:
    lock_path = campaign_dir / conf.get("campaign_lock", "campaign.lock.json")
    try:
        lock = valider_lock(charger_json(lock_path), Path(__file__).parent.parent)
        lock_hash = empreinte_lock(lock)
        couverture_path = campaign_dir / conf.get(
            "coverage_receipt", "witness-coverage-receipt.json"
        )
        if couverture_path.is_file():
            couverture = charger_json(couverture_path)
            instrument_qualifie_v2, motifs_r016 = valider_recu_couverture(
                couverture, lock, lock_hash, Path(__file__).parent.parent
            )
        else:
            couverture = None
            instrument_qualifie_v2 = False
            motifs_r016 = ["reçu de couverture R-016 absent"]

        panel_events_path = campaign_dir / conf.get(
            "panel_events", "panel-events.json"
        )
        if panel_events_path.is_file():
            panel_events = valider_evenements_panel(
                charger_json(panel_events_path), lock, lock_hash
            )
            retraites = {e["alias"] for e in panel_events["events"]}
        else:
            panel_events = None
            retraites = set()

        cartes = []
        for card in lock["axes"]:
            candidats = []
            blocages = []
            contextes = set()
            for alias in lock["panel"]:
                scores = [
                    _score_v2(campaign_dir, lock, lock_hash, card, alias, run)
                    for run in range(1, 7)
                ]
                contextes.update(s["measurement_context_hash"] for s in scores
                                  if s.get("measurement_context_hash"))
                agregat = agreger_scores(card["kind"], scores)
                if not agregat.get("classement_valide"):
                    blocages.append({"alias": alias, "runs": agregat.get("blocages")})
                candidats.append({
                    "alias": alias,
                    "panel_state": "RETIRE" if alias in retraites else None,
                    "scores": scores,
                    "agregat": agregat,
                })
            _rangs_competition(candidats, card["kind"])
            contexte_unique = len(contextes) == 1
            if not contexte_unique:
                blocages.append({"measurement_context_hashes": sorted(contextes)})
            audit_receipt = None
            audit_accepte = False
            audit_path = (
                campaign_dir / conf.get("audits_dir", "audits") / card["id"]
                / f"{card['verify_hash']}.json"
            )
            if contexte_unique and contextes and audit_path.is_file():
                hashes_collecte = {
                    score["collection_receipt_hash"]
                    for candidat in candidats for score in candidat["scores"]
                    if score.get("etat") == "SCORED"
                    and score.get("collection_receipt_hash")
                }
                try:
                    audit_receipt = valider_recu_audit(
                        charger_json(audit_path), lock_hash, card,
                        next(iter(contextes)), hashes_collecte,
                    )
                except ContratV2Invalide as exc:
                    blocages.append({"audit": f"reçu invalide: {exc}"})
                else:
                    audit_accepte = audit_receipt["decision"] == "ACCEPTED"
                    if not audit_accepte:
                        blocages.append({"audit": "désaccord humain avec la note du code"})
            elif contexte_unique and contextes:
                blocages.append({"audit": "reçu d'audit fondé sur le risque absent"})
            else:
                blocages.append({"audit": "contexte de mesure non auditable"})
            classement_valide = not blocages and instrument_qualifie_v2 and audit_accepte
            cartes.append({
                "id": card["id"],
                "kind": card["kind"],
                "verify_version": card["verify_version"],
                "verify_hash": card["verify_hash"],
                "measurement_context_hash": next(iter(contextes)) if contexte_unique else None,
                "statut": "valide" if classement_valide else "provisoire",
                "classement_valide": classement_valide,
                "blocages": blocages + ([] if instrument_qualifie_v2 else [{"R-016": motifs_r016}]),
                "audit_receipt": audit_receipt,
                "candidats": candidats,
            })
        operator_hold_path = campaign_dir / "operator-hold.json"
        if operator_hold_path.is_file():
            operator_hold = valider_hold_operateur(
                charger_json(operator_hold_path), lock, lock_hash
            )
        else:
            operator_hold = None
        resultat = {
            "schema_version": "benchmark-lab-x/results-data/v3",
            "protocol_version": PROTOCOLE_V2,
            "campaign_id": lock["campaign_id"],
            "campaign_lock_hash": lock_hash,
            "task_version": lock["task"]["task_version"],
            "prompt_sha256": lock["task"]["prompt_sha256"],
            "notation_source": "reçus de score immuables, sans rejeu Chromium",
            "conformite": {
                "instrument_qualifie": instrument_qualifie_v2,
                "page_validee": all(c["classement_valide"] for c in cartes),
                "blocages": {"R-016": motifs_r016} if motifs_r016 else {},
            },
            "coverage_receipt": couverture,
            "panel_events": panel_events,
            "campaign_status": (
                "incomplete"
                if any(
                    score["etat"] == "MISSING"
                    for axe in cartes for candidat in axe["candidats"]
                    for score in candidat["scores"]
                )
                else "complete"
            ),
            "operator_status": "HOLD" if operator_hold is not None else None,
            "operator_hold": operator_hold,
            "axes": cartes,
        }
    except ContratV2Invalide as exc:
        print(f"HOLD: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(resultat, ensure_ascii=False, indent=1))
    return 0


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    carte, dossiers = sys.argv[1], [Path(d) for d in sys.argv[2:]]
    if len(dossiers) == 1 and (dossiers[0] / "campaign.toml").is_file():
        conf_v2 = tomllib.loads((dossiers[0] / "campaign.toml").read_text(encoding="utf-8"))
        if conf_v2.get("protocol_version") == PROTOCOLE_V2:
            return rapport_v2(dossiers[0], conf_v2)
    verificateur = Path(__file__).parent / f"verifier_{carte.split('-')[0]}.py"
    if not verificateur.exists():
        print(f"vérificateur introuvable : {verificateur}", file=sys.stderr)
        return 1

    conf = None
    for d in dossiers:
        if (d / "campaign.toml").is_file():
            conf = tomllib.loads((d / "campaign.toml").read_text(encoding="utf-8"))
            break

    runs: list[dict] = []
    vus: set[tuple[str, int]] = set()
    alias_vus: set[str] = set()
    for d in dossiers:
        for dossier in sorted(d.glob(f"{carte}__*")):
            if not dossier.is_dir():
                continue
            parties = dossier.name.split("__")
            alias = parties[1] if len(parties) > 1 else "?"
            numero = int(re.sub(r"\D", "", parties[2])) if len(parties) > 2 else 0
            alias_vus.add(alias)
            meta_f = dossier / "meta.json"
            m = json.loads(meta_f.read_text(encoding="utf-8")) if meta_f.is_file() else None

            note = noter_aveugle(dossier, verificateur) if (dossier / "COMPLETE").exists() else None
            etat, justif = etat_terminal(dossier, m, note)

            ligne: dict[str, Any] = {k: (m or {}).get(k) for k in CHAMPS_RUN}
            ligne["alias"] = alias
            ligne["run"] = numero
            ligne["tentative"] = parties[3][1:] if len(parties) > 3 else "1"
            ligne["etat"] = etat
            ligne.update({k: v for k, v in justif.items() if v is not None})
            p = (m or {}).get("params") or {}
            ligne["max_tokens"] = p.get("max_tokens")
            ligne["source_budget"] = ((m or {}).get("budget_sortie") or {}).get("source")
            ligne["reasoning_effort"] = (p.get("reasoning") or {}).get("effort")
            ligne["reasoning_max_tokens"] = (p.get("reasoning") or {}).get("max_tokens")
            u = (m or {}).get("usage") or {}
            ligne["reasoning_tokens"] = (u.get("completion_tokens_details") or {}).get("reasoning_tokens")
            ligne["completion_tokens"] = u.get("completion_tokens")
            if note and "_instrument" not in note:
                ligne["niveau"] = note.get("niveau_atteint")
                ligne["paliers_total"] = len(note.get("niveaux") or {})
                ligne["frontiere"] = note.get("frontiere")
                ligne["ecart_reference"] = (note.get("mesures") or {}).get("ecart_reference")
                ligne["instant_reference_s"] = (note.get("mesures") or {}).get("instant_reference_s")
                if note.get("cause"):
                    ligne["cause"] = note["cause"]
                    ligne["depassement_temps_s"] = (note.get("mesures") or {}).get("depassement_temps_s")
            else:
                ligne["niveau"] = None
            # Seul un run `SCORED` porte un niveau opposable
            if etat != "SCORED":
                ligne["niveau_opposable"] = None
            else:
                ligne["niveau_opposable"] = ligne["niveau"]
            runs.append(ligne)
            vus.add((alias, numero))

    # R-013 : un run planifié jamais tenté à la clôture est `MISSING`. Il n'a
    # pas de dossier, donc rien ne le signalerait sans ce parcours du plan
    plan = runs_attendus(dossiers[0], conf, carte, alias_vus)
    # R-013 : « ce statut s'applique à tous les runs attendus du couple
    # carte-configuration, sans appel ». Un seul run refusé au pré-vol rend donc
    # les trois autres inéligibles eux aussi, et non manquants : la route ne
    # deviendra pas conforme entre deux runs. Sans cette propagation, une
    # configuration correctement refusée laissait trois `MISSING` qui bloquaient
    # à jamais la page validée (revue du 2026-08-06)
    ineligibles = {r["alias"] for r in runs if r["etat"] == "INELIGIBLE"}
    # R-013a : un candidat retiré du panel après le gel du plan n'est ni en
    # panne ni oublié, c'est une décision. Le déclarer dans `campaign.toml`
    # évite de le maquiller en `INFRA_ERROR`, ce qui accuserait un fournisseur
    # à la place d'une décision humaine, et bloquerait la page pour toujours
    retraits = (conf or {}).get("retraits") or {}
    for alias in plan["alias"]:
        for n in plan["runs"]:
            if (alias, n) in vus:
                continue
            if alias in retraits:
                runs.append({"alias": alias, "run": n, "etat": "RETIRE",
                             "motif": retraits[alias],
                             "niveau": None, "niveau_opposable": None, "tentative": None})
            elif alias in ineligibles:
                runs.append({"alias": alias, "run": n, "etat": "INELIGIBLE",
                             "motif": "propagé depuis un run refusé au pré-vol (R-013)",
                             "niveau": None, "niveau_opposable": None, "tentative": None})
            else:
                runs.append({"alias": alias, "run": n, "etat": "MISSING",
                             "motif": "run planifié jamais tenté à la clôture",
                             "niveau": None, "niveau_opposable": None,
                             "tentative": None})

    # Une tentative n'est pas un run attendu. R-013 attribue un état unique au
    # run attendu, pas à chacun de ses essais : un run repris après un échec de
    # fournisseur et finalement scoré est `SCORED`, et ses tentatives ratées
    # restent des pièces à conviction (R-024), pas des états de plus. Compter
    # les dossiers plutôt que les runs faisait apparaître seize `INFRA_ERROR`
    # là où il y avait quatre runs réussis après reprise
    for r in runs:
        if r["alias"] in retraits and r["etat"] in ("INFRA_ERROR", "MISSING"):
            r["etat"], r["motif"] = "RETIRE", retraits[r["alias"]]

    attendus_resolus: dict[tuple[str, int], dict] = {}
    for r in runs:
        cle = (r["alias"], r["run"])
        courant = attendus_resolus.get(cle)
        meilleur = r["etat"] == "SCORED"
        if courant is None or (meilleur and courant["etat"] != "SCORED"):
            attendus_resolus[cle] = r
        elif courant["etat"] != "SCORED":
            # à défaut de succès, la dernière tentative fait foi. Comparaison
            # entière et non lexicographique : `"2" >= "10"` vaut True en
            # chaînes, ce qui aurait retenu la mauvaise tentative au-delà de
            # neuf essais (revue du 2026-08-06)
            def rang(x: dict) -> int:
                try:
                    return int(x.get("tentative") or 1)
                except (TypeError, ValueError):
                    return 1

            if rang(r) >= rang(courant):
                attendus_resolus[cle] = r
    for r in runs:
        r["tentative_retenue"] = attendus_resolus.get((r["alias"], r["run"])) is r
    runs_attendus_resolus = list(attendus_resolus.values())

    # R-019 : niveau retenu au troisième meilleur des quatre runs, c'est-à-dire
    # le niveau qu'au moins trois runs franchissent. Tolère un mauvais tirage et
    # pas deux. R-020 : le candidat n'est classé que si tous ses runs attendus
    # sont `SCORED` ; sinon il est présenté hors classement avec son manque
    par_alias: dict[str, list] = {}
    for r in runs_attendus_resolus:
        par_alias.setdefault(r["alias"], []).append(r)

    candidats = []
    for alias, v in par_alias.items():
        etats = [r["etat"] for r in v]
        attendus = len(plan["runs"])
        scores = [r for r in v if r["etat"] == "SCORED"]
        niveaux = sorted((r["niveau_opposable"] for r in scores
                          if r["niveau_opposable"] is not None), reverse=True)
        tout_score = len(scores) == attendus and len(niveaux) == attendus
        ineligible = "INELIGIBLE" in etats
        hors_plan = alias not in plan["alias"]
        retire = "RETIRE" in etats
        couts = [r.get("cost_usd") or 0 for r in v if r.get("cost_usd") is not None]
        durees = [r.get("duration_s") or 0 for r in v if r.get("duration_s") is not None]
        candidats.append({
            "alias": alias,
            "model_served": next((r.get("model_served") for r in v if r.get("model_served")), None),
            "provider_served": next((r.get("provider_served") for r in v if r.get("provider_served")), None),
            "reasoning_effort": next((r.get("reasoning_effort") for r in v if r.get("reasoning_effort")), None),
            "execution_manifest_hash": next((r.get("execution_manifest_hash") for r in v
                                             if r.get("execution_manifest_hash")), None),
            "etats": {e: etats.count(e) for e in sorted(set(etats))},
            "runs_attendus": attendus,
            "runs_scored": len(scores),
            "niveaux": niveaux,
            # R-020 : hors classement tant que tout n'est pas `SCORED`
            # R-020 classe les candidats de la campagne, c'est-à-dire ceux du
            # plan gelé. Un alias collecté hors plan est présenté avec ses
            # niveaux mais reste hors classement : sinon un classement « de
            # campagne » cesse d'être la projection de son plan, et n'importe
            # quel dossier déposé sous `runs/` y entre (revue du 2026-08-06)
            "hors_plan": hors_plan,
            "classable": tout_score and not ineligible and not hors_plan and not retire,
            "niveau_retenu": (niveaux[2] if tout_score and not hors_plan
                              and len(niveaux) >= 3 else None),
            "hors_classement": ("RETIRE" if retire
                                else "INELIGIBLE" if ineligible
                                else "absent du plan de campagne" if hors_plan
                                else None if tout_score else "runs non scorés"),
            "niveau_indicatif": min(niveaux) if niveaux else None,
            "cout_moyen_usd": round(sum(couts) / len(couts), 6) if couts else None,
            "duree_moyenne_s": round(sum(durees) / len(durees), 1) if durees else None,
        })
    # Les classables d'abord, par niveau retenu décroissant ; le reste ensuite,
    # sans jamais mêler un niveau indicatif à un niveau retenu (R-020)
    candidats.sort(key=lambda c: (0 if c["classable"] else 1,
                                  -(c["niveau_retenu"] if c["niveau_retenu"] is not None else -1),
                                  -(c["niveau_indicatif"] if c["niveau_indicatif"] is not None else -1),
                                  c["alias"]))

    # R-027 : la page n'est validée que si chaque run attendu de chaque candidat
    # éligible porte `SCORED`. Le contrôle est fail-closed : il énumère ce qui
    # manque au lieu de conclure sur ce qui est présent
    non_termines = {}
    for r in runs_attendus_resolus:
        # Un run hors plan ne peut ni valider ni bloquer une page : il n'est pas
        # un run attendu de cette campagne
        if r["alias"] not in plan["alias"]:
            continue
        if r["etat"] not in ("SCORED", "INELIGIBLE", "RETIRE"):
            non_termines.setdefault(r["etat"], []).append(f"{r['alias']}/r{r['run']}")
    # Deux conditions indépendantes, séparées pour que le lecteur voie laquelle
    # manque. Les fondre dans un seul booléen était le défaut d'origine : la
    # campagne du 2026-08-06 s'est déclarée validée alors que l'instrument ne
    # l'était pas, parce que seuls les états de runs étaient regardés
    runs_termines = not non_termines and plan["source"] == "campaign.toml"
    qualifie, motifs_instrument = instrument_qualifie(carte)
    blocages = dict(non_termines)
    if motifs_instrument:
        blocages["R-016"] = motifs_instrument
    if plan["source"] != "campaign.toml":
        blocages["plan"] = ["plan de campagne absent, un run manquant serait invisible"]
    conformite = {
        "runs_termines": runs_termines,
        "instrument_qualifie": qualifie,
        "page_validee": runs_termines and qualifie,
        "blocages": blocages,
        "plan": plan,
        "motif": ("aucun" if runs_termines and qualifie
                  else "; ".join(filter(None, [
                      None if runs_termines else "des runs attendus ne sont pas dans un état terminal",
                      None if qualifie else "l'instrument n'est pas qualifié : les témoins de la carte "
                                            "ne sont pas produits sans accès au vérificateur (R-016)",
                  ]))),
    }

    # R-017 : compteurs dérivés des reçus, jamais saisis à la main. Un prompt est
    # « parti » dès qu'un appel a atteint un fournisseur, succès ou échec ; les
    # refus au pré-vol ne comptent pas, aucune donnée n'a quitté le poste. Le
    # compte porte sur les tentatives et non sur les runs attendus : une reprise
    # renvoie bel et bien la carte au fournisseur
    partis = sum(1 for r in runs if r["etat"] in ("SCORED", "UNKNOWN")
                 or (r["etat"] == "INFRA_ERROR" and r.get("motif") not in
                     ("metadonnees_route_inatteignables",)))
    cycle_de_vie = {
        "prompts_partis": partis,
        "unite": "tentatives ayant atteint un fournisseur, reprises comprises",
        "runs_attendus": len(runs_attendus_resolus),
        "campagnes": sorted({str(d) for d in dossiers}),
        "campagnes_terminees": sum(1 for d in dossiers if (d / "campaign.toml").is_file()),
        "regle": "R-017 : une carte à information courte participe à deux campagnes au maximum",
    }

    manifeste_juge = actifs_cote_juge(carte, verificateur)
    verify_hash = empreinte(manifeste_juge)
    env = descripteur_environnement()
    contexte = {
        "schema_version": SCHEMA_CONTEXTE,
        "task_version": next((r.get("task_version") for r in runs if r.get("task_version")), None),
        "prompt_hash": next((r.get("prompt_hash") for r in runs if r.get("prompt_hash")), None),
        "verify_version": version_verificateur(carte),
        "verify_hash": verify_hash,
        "protocol_version": PROTOCOLE_VERSION,
        "measurement_environment_hash": empreinte(env),
        "confidentiality_regime": next((r.get("regime_confidentialite") for r in runs
                                        if r.get("regime_confidentialite")), None),
    }

    print(json.dumps({
        "carte": carte,
        "verify_version": contexte["verify_version"],
        "verify_hash": verify_hash,
        "actifs_cote_juge": manifeste_juge,
        "environnement_mesure": env,
        "measurement_context": contexte,
        "measurement_context_hash": empreinte(contexte),
        "conformite": conformite,
        "cycle_de_vie": cycle_de_vie,
        "paliers_total": next((r.get("paliers_total") for r in runs if r.get("paliers_total")), None),
        "runs": runs,
        "candidats": candidats,
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
