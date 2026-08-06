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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("campaign", type=Path)
    ap.add_argument("--reprendre", action="store_true",
                    help="saute les runs déjà marqués COMPLETE")
    args = ap.parse_args()

    conf = tomllib.load(args.campaign.open("rb"))
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
