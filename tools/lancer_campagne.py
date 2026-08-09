# /// script
# requires-python = ">=3.12"
# dependencies = ["tomli-w"]
# ///
"""Lance une campagne complète en une commande, en parallèle, avec reprise.

Une campagne, un fichier `campaign.toml`. Le lanceur n'interprète jamais un
résultat : il collecte, il compte, il s'arrête. La notation vient après.

Usage :
    uv run tools/lancer_campagne.py runs/<date>/campaign.toml [--reprendre]
"""

import argparse
import json
import re
import subprocess
import sys
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from protocole_v2 import (  # noqa: E402
    PROTOCOLE_VERSION as PROTOCOLE_V2,
    SCHEMA_ATTEMPT,
    ContratV2Invalide,
    PlafondDepasse,
    RegistreBudget,
    cellule_du_lock,
    charger_json,
    decision_reprise,
    descripteur_environnement_runner,
    ecrire_json_immuable,
    empreinte_lock,
    valider_abandon_campagne,
    valider_autorisation_payante,
    valider_etat_collecte,
    valider_environnement_observe,
    valider_lock,
    valider_hold_operateur,
    valider_recu_tentative,
)

COLLECT = Path(__file__).parent / "collect.py"

# Codes de sortie de collect.py qui portent un état terminal R-013
CODE_INELIGIBLE = 11
CODE_INFRA = 12


def tentatives_du_run(racine: Path, carte: str, alias: str, run: int) -> list[Path]:
    """Dossiers de tentative d'un run attendu.

    Le glob `r{run}*` employé auparavant faisait correspondre `r1` à `r10` : la
    reprise et le compteur de tentatives se seraient trompés dès qu'une campagne
    dépasse neuf runs. Le motif exact suivi d'une éventuelle tentative écarte ce
    cas (revue du 2026-08-06)
    """
    prefixe = f"{carte}__{alias}__r{run}"
    return [d for d in racine.glob(f"{prefixe}*")
            if d.is_dir() and (d.name == prefixe or d.name.startswith(prefixe + "__"))]


def deja_collecte(racine: Path, carte: str, alias: str, run: int) -> bool:
    """Un run est acquis s'il porte un marqueur COMPLETE, toutes tentatives confondues"""
    return any((d / "COMPLETE").exists() for d in tentatives_du_run(racine, carte, alias, run))


def configuration_ineligible(racine: Path, carte: str, alias: str) -> bool:
    """Une configuration inéligible l'est pour tous ses runs attendus (R-013).

    L'inéligibilité porte sur le couple carte-configuration, pas sur un run :
    si la route refuse le contrat de mesure, les trois autres runs ne sont pas
    plus recevables que le premier. Sans ce test, `--reprendre` relance
    indéfiniment une configuration que le collecteur vient de refuser, et
    chaque relance crée une tentative de plus sur le disque
    """
    return any(
        (d / "INELIGIBLE").exists() for d in racine.glob(f"{carte}__{alias}__r*")
    )


def prochaine_tentative(racine: Path, carte: str, alias: str, run: int) -> int:
    return 1 + len(tentatives_du_run(racine, carte, alias, run))


def attente_avant_reprise(racine: Path, carte: str, alias: str, run: int) -> float:
    """Combien de temps attendre avant de retenter, d'après le dernier reçu.

    Un 429 de pool partagé est transitoire et le fournisseur dit combien de
    temps attendre. La version précédente relançait immédiatement, trois fois
    d'affilée : les douze tentatives de Kimi K3 du 2026-08-05 ont toutes été
    envoyées en quelques secondes sur une route qui demandait deux secondes de
    répit, et le candidat a été déclaré inatteignable. La route répondait
    normalement le lendemain.

    Retenter le MÊME appel après une limite de débit ne change pas le stimulus :
    ce n'est ni une élévation de budget ni un changement de route, seulement le
    respect d'un délai que le fournisseur a lui-même publié
    """
    dernier, rang = None, -1
    for d in tentatives_du_run(racine, carte, alias, run):
        n = int(re.sub(r"\D", "", d.name.split("__")[-1])) if "__a" in d.name else 1
        if n > rang and (d / "FAILED").is_file():
            dernier, rang = d / "FAILED", n
    if dernier is None:
        return 0.0
    texte = dernier.read_text(encoding="utf-8")
    if "http_429" not in texte and "http_503" not in texte:
        return 0.0
    m = re.search(r'"retry_after_seconds"\s*:\s*(\d+(?:\.\d+)?)', texte)
    conseil = float(m.group(1)) if m else 5.0
    # Le délai conseillé vaut pour un appelant isolé sur un pool libre. Mesuré
    # le 2026-08-06 sur le pool partagé de Kimi K3 : il annonce 2 s, et ni 2 s
    # ni 4 s ne le dégagent. Le plancher de 30 s vient de cette observation, pas
    # d'une règle : c'est le délai à partir duquel les reprises passent. Il
    # double à chaque tentative et se borne pour ne pas immobiliser la campagne
    PLANCHER_POOL_PARTAGE = 30.0
    return min(240.0, max(PLANCHER_POOL_PARTAGE, conseil) * (2 ** (rang - 1)))


def collecter(conf: dict, racine: Path, carte: str, alias: str, run: int) -> dict:
    tentative = prochaine_tentative(racine, carte, alias, run)
    pause = attente_avant_reprise(racine, carte, alias, run)
    if pause:
        print(f"  attente {pause:.0f}s avant reprise de {alias} r{run} "
              f"(limite de débit annoncée par le fournisseur)", file=sys.stderr)
        time.sleep(pause)
    # Borne dure de tentatives : au-delà, le run attendu devient `INFRA_ERROR`
    # et la campagne cesse de le poursuivre (R-004, R-013). Sans elle, une route
    # durablement en panne consomme la campagne en relances
    maxi = int(conf.get("tentatives_max", 3))
    if tentative > maxi:
        # Le marqueur va DANS un dossier de run, pas à plat à la racine de la
        # campagne : le rapport ne parcourt que des dossiers `carte__*` et
        # cherche l'état à l'intérieur. Un fichier plat lui était invisible et
        # le run ressortait `MISSING` au lieu d'`INFRA_ERROR` (revue du 2026-08-06)
        dossier = racine / f"{carte}__{alias}__r{run}__a{tentative}"
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / "INFRA_ERROR").write_text(
            json.dumps({"etat": "INFRA_ERROR", "motif": "tentatives_epuisees",
                        "carte": carte, "alias": alias, "run": run,
                        "tentatives": maxi}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return {"carte": carte, "alias": alias, "run": run, "tentative": tentative,
                "code": CODE_INFRA, "ligne": "",
                "erreur": f"tentatives épuisées ({maxi}) : run attendu en INFRA_ERROR"}
    cmd = [
        "uv", "run", str(COLLECT), f"tasks/{conf.get('jeu', 'dev')}/{carte}",
        "--alias", alias, "--run", str(run), "--out-root", str(racine),
    ]
    if tentative > 1:
        cmd += ["--attempt", str(tentative)]
    if conf.get("timeout"):
        cmd += ["--timeout", str(conf["timeout"])]
    out = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "carte": carte, "alias": alias, "run": run, "tentative": tentative,
        "code": out.returncode,
        "ligne": (out.stdout.strip().splitlines() or [""])[-1],
        "erreur": (out.stderr.strip().splitlines() or [""])[-1] if out.returncode else "",
    }


def cout_engage(racine: Path) -> float:
    total = 0.0
    for meta in racine.glob("*/meta.json"):
        try:
            total += json.loads(meta.read_text(encoding="utf-8")).get("cost_usd") or 0.0
        except (OSError, json.JSONDecodeError):
            continue
    return total


def _tentatives_v2(racine: Path, collection_id: str) -> list[Path]:
    dossier = racine / "collections" / collection_id
    return sorted(
        [p for p in dossier.glob("attempt-*") if p.is_dir()],
        key=lambda p: int(p.name.split("-")[-1]),
    )


def _dernier_recu_v2(racine: Path, collection_id: str) -> dict | None:
    for dossier in reversed(_tentatives_v2(racine, collection_id)):
        path = dossier / "attempt-receipt.json"
        if path.is_file():
            return charger_json(path)
    return None


def _collecte_complete_v2(racine: Path, collection_id: str) -> bool:
    return any((d / "collection-receipt.json").is_file() and (d / "COMPLETE").is_file()
               for d in _tentatives_v2(racine, collection_id))


def _etat_collecte_v2(
    racine: Path, collection_id: str, lock_hash: str, cellule: dict
) -> dict | None:
    path = racine / "collections" / collection_id / "collection-state.json"
    return (
        valider_etat_collecte(charger_json(path), lock_hash, cellule)
        if path.is_file() else None
    )


def _fermer_collecte_v2(
    racine: Path,
    lock_hash: str,
    cellule: dict,
    etat: str,
    cause_code: str,
    tentative: int | None,
) -> None:
    if etat not in {"INELIGIBLE", "INFRA_ERROR"}:
        raise ContratV2Invalide(f"fermeture de collecte invalide: {etat}")
    collection_id = cellule["collection_id"]
    recu = {
            "schema_version": "benchmark-lab-x/collection-state/v1",
            "campaign_lock_hash": lock_hash,
            "collection_id": collection_id,
            "state": etat,
            "cause_code": cause_code,
            "last_attempt": tentative,
        }
    valider_etat_collecte(recu, lock_hash, cellule)
    ecrire_json_immuable(
        racine / "collections" / collection_id / "collection-state.json", recu
    )


def _poser_hold_v2(
    racine: Path,
    lock: dict,
    lock_hash: str,
    cause_code: str,
    collection_id: str | None = None,
    tentative: int | None = None,
) -> None:
    hold = {
        "schema_version": "benchmark-lab-x/operator-hold/v1",
        "campaign_lock_hash": lock_hash,
        "decision": "HOLD",
        "cause_code": cause_code,
        "collection_id": collection_id,
        "attempt": tentative,
    }
    valider_hold_operateur(hold, lock, lock_hash)
    ecrire_json_immuable(
        racine / "operator-hold.json", hold
    )


def _abandonner_hold_v2(
    racine: Path,
    lock: dict,
    lock_hash: str,
    abandonment_path: Path,
) -> dict:
    hold_path = racine / "operator-hold.json"
    if not hold_path.is_file() or hold_path.is_symlink():
        raise ContratV2Invalide("HOLD opérateur absent ou lié symboliquement")
    hold = valider_hold_operateur(charger_json(hold_path), lock, lock_hash)
    abandon = valider_abandon_campagne(
        charger_json(abandonment_path), hold, lock_hash
    )
    cellule = cellule_du_lock(lock, abandon["collection_id"])
    if _collecte_complete_v2(racine, cellule["collection_id"]):
        raise ContratV2Invalide("une collecte acquise ne peut pas être abandonnée")
    tentative = hold.get("attempt")
    if not isinstance(tentative, int) or isinstance(tentative, bool):
        raise ContratV2Invalide("tentative d'identité absente du HOLD")
    _fermer_collecte_v2(
        racine, lock_hash, cellule, "INFRA_ERROR",
        abandon["cause_code"], tentative,
    )
    return {
        "status": "ABANDONED_HELD_COLLECTION",
        "collection_id": cellule["collection_id"],
        "state": "INFRA_ERROR",
        "operator_status": "HOLD",
    }


def _reconcilier_budget_v2(
    racine: Path, ledger: RegistreBudget, lock: dict, lock_hash: str
) -> dict:
    state = ledger.etat()
    cellules = {c["collection_id"]: c for c in lock["collections"]}
    for reservation_id, reservation in list(state.get("reservations", {}).items()):
        if reservation.get("status") != "reserved":
            continue
        trouve = None
        for path in (racine / "collections").glob("*/attempt-*/attempt-receipt.json"):
            receipt = charger_json(path)
            accounting = receipt.get("cost_accounting") or {}
            if accounting.get("reservation_id") == reservation_id:
                cellule = cellules.get(receipt.get("collection_id"))
                if cellule is None:
                    raise ContratV2Invalide(
                        "reçu de réconciliation lié à une collecte inconnue"
                    )
                valider_recu_tentative(receipt, cellule, lock_hash)
                trouve = accounting
                break
        if trouve is None:
            ledger.finaliser(reservation_id, None)
        elif trouve.get("status") in {"known", "upper_bound"}:
            ledger.finaliser(reservation_id, trouve.get("cost_microdollars"))
        else:
            ledger.finaliser(reservation_id, None)
    return ledger.etat()


def _collecter_v2(
    runner: dict,
    racine: Path,
    lock_path: Path,
    auth_path: Path,
    ledger_path: Path,
    cellule: dict,
    tentative: int,
) -> dict:
    dernier = _dernier_recu_v2(racine, cellule["collection_id"])
    if tentative > 1 and dernier:
        retry_after = dernier.get("retry_after")
        try:
            pause = max(0.0, float(retry_after)) if retry_after is not None else 0.0
        except (TypeError, ValueError):
            pause = 0.0
        if pause:
            time.sleep(pause)
    reservation_id = f"{cellule['collection_id']}__a{tentative}"
    cmd = [
        "uv", "run", str(COLLECT),
        str(Path(__file__).parent.parent / "tasks/dev/pentagone-rotatif"),
        "--campaign-lock", str(lock_path),
        "--collection-id", cellule["collection_id"],
        "--paid-authorization", str(auth_path),
        "--budget-ledger", str(ledger_path),
        "--reservation-id", reservation_id,
        "--attempt", str(tentative),
        "--out-root", str(racine),
    ]
    cmd += ["--timeout", str(runner["transport_timeout_s"])]
    out = subprocess.run(cmd, capture_output=True, text=True)
    receipt_path = (racine / "collections" / cellule["collection_id"]
                    / f"attempt-{tentative}" / "attempt-receipt.json")
    receipt = charger_json(receipt_path) if receipt_path.is_file() else None
    return {
        "collection_id": cellule["collection_id"],
        "attempt": tentative,
        "reservation_id": reservation_id,
        "code": out.returncode,
        "receipt": receipt,
        "error": (out.stderr.strip().splitlines() or [""])[-1],
    }


def lancer_v2(args, conf: dict) -> int:
    racine = args.campaign.parent
    def resoudre_local(brut, cle: str) -> Path:
        path = Path(brut)
        if path.is_absolute() or ".." in path.parts or "." in path.parts:
            raise ContratV2Invalide(f"chemin non local dans {cle}")
        resolu = (racine / path).resolve()
        if racine.resolve() not in resolu.parents:
            raise ContratV2Invalide(f"chemin hors campagne dans {cle}")
        return resolu

    def artefact_local(cle: str, defaut: str) -> Path:
        return resoudre_local(conf.get(cle, defaut), cle)

    try:
        lock_path = artefact_local("campaign_lock", "campaign.lock.json")
        lock = valider_lock(charger_json(lock_path), Path(__file__).parent.parent)
        lock_hash = empreinte_lock(lock)
    except (ContratV2Invalide, OSError) as exc:
        print(f"HOLD avant toute action v2: {exc}", file=sys.stderr)
        return 2

    abandonment = getattr(args, "abandonment", None)
    if abandonment is not None:
        try:
            resultat = _abandonner_hold_v2(
                racine, lock, lock_hash,
                resoudre_local(abandonment, "abandonment"),
            )
        except (ContratV2Invalide, OSError) as exc:
            print(f"HOLD abandon refusé: {exc}", file=sys.stderr)
            return 2
        print(json.dumps(resultat, ensure_ascii=False, indent=2), file=sys.stderr)
        return 0

    try:
        auth_path = artefact_local("paid_authorization", "paid-authorization.json")
        ledger_path = artefact_local("budget_ledger", "budget-ledger.json")
        valider_environnement_observe(lock, "runner", descripteur_environnement_runner())
        runner = lock["runner"]
        valider_autorisation_payante(
            charger_json(auth_path), lock_hash, lock["budget"]["cap_microdollars"]
        )
        ledger = RegistreBudget(ledger_path, lock["budget"]["cap_microdollars"], lock_hash)
        state = _reconcilier_budget_v2(racine, ledger, lock, lock_hash)
        if state.get("hold"):
            _poser_hold_v2(racine, lock, lock_hash, "IN_FLIGHT_UNRECONCILED")
            raise ContratV2Invalide("registre budgétaire en HOLD après réconciliation")
        operator_hold_path = racine / "operator-hold.json"
        if operator_hold_path.exists():
            valider_hold_operateur(
                charger_json(operator_hold_path), lock, lock_hash
            )
            raise ContratV2Invalide("HOLD opérateur déjà présent pour cette campagne")
    except (ContratV2Invalide, OSError) as exc:
        print(f"HOLD avant tout appel v2: {exc}", file=sys.stderr)
        return 2

    travaux: list[tuple[dict, int]] = []
    bloquants: list[str] = []
    for cellule in lock["collections"]:
        cid = cellule["collection_id"]
        if _collecte_complete_v2(racine, cid):
            continue
        etat_collecte = _etat_collecte_v2(racine, cid, lock_hash, cellule)
        if etat_collecte is not None:
            if etat_collecte.get("state") not in {"INELIGIBLE", "INFRA_ERROR"}:
                bloquants.append(f"{cid}: état de collecte invalide")
            continue
        dernier = _dernier_recu_v2(racine, cid)
        if dernier is None:
            tentative = 1 + len(_tentatives_v2(racine, cid))
            if tentative != 1:
                bloquants.append(f"{cid}: tentative sans reçu structuré")
            else:
                travaux.append((cellule, tentative))
            continue
        try:
            decision = decision_reprise(
                dernier, cellule, lock_hash, lock["attempts_max"]
            )
        except ContratV2Invalide as exc:
            bloquants.append(f"{cid}: reçu de tentative invalide: {exc}")
            continue
        if decision["action"] == "retry":
            travaux.append((cellule, int(dernier["attempt"]) + 1))
        elif decision["action"] == "infra_error":
            _fermer_collecte_v2(
                racine, lock_hash, cellule, "INFRA_ERROR", "ATTEMPTS_EXHAUSTED",
                int(dernier["attempt"]),
            )
        elif decision["action"] == "hold":
            bloquants.append(f"{cid}: {decision['reason']}")
        elif decision["action"] == "complete":
            bloquants.append(f"{cid}: tentative COMPLETE sans reçu de collecte acquis")
    if bloquants:
        _poser_hold_v2(racine, lock, lock_hash, "RETRY_RECONCILIATION_FAILED")
        print("HOLD: reprises non autorisées", file=sys.stderr)
        for motif in bloquants:
            print(f"  - {motif}", file=sys.stderr)
        return 2

    concurrence = runner["concurrency"]
    futurs = {}
    arrete = False
    quota_epuise = False
    plafond_atteint = False
    tentatives_soumises = sum(
        len(_tentatives_v2(racine, cellule["collection_id"]))
        for cellule in lock["collections"]
    )

    def admissible(cellule: dict) -> bool:
        manifeste = cellule["execution_manifest"]
        backend = manifeste["backend"]
        provider = manifeste["provider_pinned"]
        actifs = list(futurs.values())
        actifs_backend = sum(
            c["execution_manifest"]["backend"] == backend for c in actifs
        )
        actifs_provider = sum(
            c["execution_manifest"]["provider_pinned"] == provider for c in actifs
        )
        return (
            actifs_backend < lock["quotas"]["in_flight_by_backend"][backend]
            and actifs_provider < lock["quotas"]["in_flight_by_provider"][provider]
        )

    with ThreadPoolExecutor(max_workers=concurrence) as pool:
        restants = list(travaux)
        while restants or futurs:
            while restants and len(futurs) < concurrence and not arrete:
                if tentatives_soumises >= lock["quotas"]["attempts_total_max"]:
                    quota_epuise = True
                    restants.clear()
                    break
                index = next(
                    (i for i, (cellule, _) in enumerate(restants) if admissible(cellule)),
                    None,
                )
                if index is None:
                    break
                cellule, tentative = restants.pop(index)
                reservation_id = f"{cellule['collection_id']}__a{tentative}"
                try:
                    ledger.reserver(reservation_id, cellule["max_cost_microdollars"])
                except PlafondDepasse as exc:
                    print(f"Plafond atteint avant soumission: {exc}", file=sys.stderr)
                    plafond_atteint = True
                    restants.clear()
                    break
                except ContratV2Invalide as exc:
                    print(f"HOLD budget avant soumission: {exc}", file=sys.stderr)
                    arrete = True
                    break
                futur = pool.submit(
                    _collecter_v2, runner, racine, lock_path, auth_path, ledger_path,
                    cellule, tentative,
                )
                futurs[futur] = cellule
                tentatives_soumises += 1
            if not futurs:
                break
            for futur in as_completed(list(futurs)):
                cellule = futurs.pop(futur)
                result = futur.result()
                receipt = result["receipt"]
                if receipt is None or receipt.get("schema_version") != SCHEMA_ATTEMPT:
                    ledger.finaliser(result["reservation_id"], None)
                    _poser_hold_v2(
                        racine, lock, lock_hash, "ATTEMPT_RECEIPT_MISSING",
                        cellule["collection_id"], result["attempt"],
                    )
                    print(f"HOLD {cellule['collection_id']}: reçu de tentative absent", file=sys.stderr)
                    arrete = True
                    break
                try:
                    valider_recu_tentative(receipt, cellule, lock_hash)
                except ContratV2Invalide as exc:
                    ledger.finaliser(result["reservation_id"], None)
                    _poser_hold_v2(
                        racine, lock, lock_hash, "ATTEMPT_RECEIPT_INVALID",
                        cellule["collection_id"], result["attempt"],
                    )
                    print(
                        f"HOLD {cellule['collection_id']}: reçu de tentative invalide: {exc}",
                        file=sys.stderr,
                    )
                    arrete = True
                    break
                accounting = receipt.get("cost_accounting") or {}
                cout = (
                    accounting.get("cost_microdollars")
                    if accounting.get("status") in {"known", "upper_bound"}
                    else None
                )
                ledger.finaliser(result["reservation_id"], cout)
                if ledger.etat().get("hold"):
                    _poser_hold_v2(
                        racine, lock, lock_hash, "COST_ACCOUNTING_UNKNOWN",
                        cellule["collection_id"], result["attempt"],
                    )
                    print(f"HOLD {cellule['collection_id']}: coût non opposable", file=sys.stderr)
                    arrete = True
                    break
                decision = decision_reprise(
                    receipt, cellule, lock_hash, lock["attempts_max"]
                )
                if decision["action"] == "retry":
                    restants.append((cellule, int(receipt["attempt"]) + 1))
                elif decision["action"] == "infra_error":
                    _fermer_collecte_v2(
                        racine, lock_hash, cellule, "INFRA_ERROR",
                        "ATTEMPTS_EXHAUSTED", int(receipt["attempt"]),
                    )
                elif decision["action"] == "hold":
                    _poser_hold_v2(
                        racine, lock, lock_hash, receipt["cause_code"],
                        cellule["collection_id"], int(receipt["attempt"]),
                    )
                    print(f"HOLD {cellule['collection_id']}: {decision['reason']}", file=sys.stderr)
                    arrete = True
                break
    state = ledger.etat()
    print(json.dumps({
        "protocol_version": PROTOCOLE_V2,
        "collections_complete": sum(_collecte_complete_v2(racine, c["collection_id"])
                                    for c in lock["collections"]),
        "collections_expected": len(lock["collections"]),
        "engaged_microdollars": state["engaged_microdollars"],
        "reserved_microdollars": RegistreBudget._reserve_total(state),
        "attempts_submitted": tentatives_soumises,
        "attempts_quota_exhausted": quota_epuise,
        "budget_cap_reached": plafond_atteint,
        "hold": bool(arrete or state.get("hold")),
    }, ensure_ascii=False, indent=2), file=sys.stderr)
    return 2 if arrete or state.get("hold") else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("campaign", type=Path)
    ap.add_argument("--reprendre", action="store_true",
                    help="saute les runs déjà marqués COMPLETE")
    ap.add_argument(
        "--abandonment", type=Path,
        help="autorisation locale fermant la collecte en HOLD d'identité, sans nouvel appel",
    )
    args = ap.parse_args()

    conf = tomllib.load(args.campaign.open("rb"))
    if conf.get("protocol_version") == PROTOCOLE_V2:
        return lancer_v2(args, conf)
    racine = args.campaign.parent
    for champ in ("question", "cartes", "candidats", "runs"):
        if champ not in conf:
            print(f"champ obligatoire absent de {args.campaign} : {champ}", file=sys.stderr)
            return 2

    plafond = float(conf.get("plafond_dollars", 60.0))
    concurrence = int(conf.get("concurrence", 4))

    travaux = [(c, a, r)
               for c in conf["cartes"]
               for a in conf["candidats"]
               for r in range(1, int(conf["runs"]) + 1)]
    if args.reprendre:
        avant = len(travaux)
        travaux = [t for t in travaux if not deja_collecte(racine, *t)]
        acquis = avant - len(travaux)
        sans_ineligibles = [t for t in travaux if not configuration_ineligible(racine, t[0], t[1])]
        ecartes = len(travaux) - len(sans_ineligibles)
        travaux = sans_ineligibles
        print(f"reprise : {acquis} runs déjà acquis, {ecartes} écartés (configuration "
              f"INELIGIBLE), {len(travaux)} à collecter", file=sys.stderr)

    print(f"question   : {conf['question']}", file=sys.stderr)
    print(f"campagne   : {len(travaux)} runs, {concurrence} en parallèle, "
          f"plafond {plafond} $", file=sys.stderr)

    fait = echecs = ineligibles = infra = 0
    engage = cout_engage(racine)
    arrete = False
    with ThreadPoolExecutor(max_workers=concurrence) as pool:
        futurs = {}
        restants = list(travaux)
        while restants or futurs:
            while restants and len(futurs) < concurrence and not arrete:
                c, a, r = restants.pop(0)
                futurs[pool.submit(collecter, conf, racine, c, a, r)] = (c, a, r)
            if not futurs:
                break
            for f in as_completed(list(futurs)):
                res = f.result()
                futurs.pop(f)
                fait += 1
                if res["code"] == CODE_INELIGIBLE:
                    ineligibles += 1
                    # L'inéligibilité vaut pour le couple carte-configuration :
                    # les runs restants de cette configuration sont retirés de la
                    # file au lieu d'être tentés puis refusés un par un
                    avant = len(restants)
                    restants[:] = [t for t in restants
                                   if not (t[0] == res["carte"] and t[1] == res["alias"])]
                    print(f"  INÉLIG {res['alias']:24} r{res['run']}  {res['erreur'][:70]} "
                          f"(+{avant - len(restants)} runs retirés)", file=sys.stderr)
                elif res["code"] == CODE_INFRA:
                    infra += 1
                    print(f"  INFRA  {res['alias']:24} r{res['run']}  {res['erreur'][:80]}",
                          file=sys.stderr)
                elif res["code"]:
                    echecs += 1
                    print(f"  ÉCHEC  {res['alias']:24} r{res['run']}  {res['erreur'][:80]}",
                          file=sys.stderr)
                else:
                    print(f"  ok     {res['alias']:24} r{res['run']}", file=sys.stderr)
                engage = cout_engage(racine)
                if engage >= plafond and not arrete:
                    arrete = True
                    restants.clear()
                    print(f"\nPLAFOND ATTEINT : {engage:.2f} $ >= {plafond} $. "
                          f"Arrêt propre, relancer avec --reprendre après relèvement.",
                          file=sys.stderr)
                break

    print(f"\n{fait} runs lancés, {echecs} en échec, {ineligibles} INELIGIBLE, "
          f"{infra} INFRA_ERROR, {engage:.2f} $ engagés", file=sys.stderr)
    if ineligibles:
        print("Une configuration INELIGIBLE a été refusée avant tout appel : sa route ne "
              "tient pas le contrat de mesure (R-025). Elle ne sera pas retentée par "
              "--reprendre ; corriger le pin dans models.toml ou retirer le candidat.",
              file=sys.stderr)
    if infra:
        print("Un run attendu est en INFRA_ERROR : les tentatives autorisées sont épuisées. "
              "La page reste provisoire tant que cet état subsiste (R-020, R-027).",
              file=sys.stderr)
    if echecs:
        print("Les échecs laissent un reçu FAILED : les lire avant de conclure quoi que ce "
              "soit sur un modèle (R-024). Relancer avec --reprendre.", file=sys.stderr)
    return 1 if arrete else 0


if __name__ == "__main__":
    sys.exit(main())
