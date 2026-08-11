# /// script
# requires-python = ">=3.12"
# dependencies = ["playwright==1.62.0", "mpmath==1.3.0"]
# ///
"""Vérificateur verify-v4 par carte de score

Chaque invocation mesure une seule carte. Le garde-fou de 180 secondes est
appliqué par `noter_campagne.py`, qui peut ainsi rendre uniquement la carte en
cours `UNKNOWN` sans transformer le dépassement en niveau zéro
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from mpmath import mpf, sqrt

sys.path.insert(0, str(Path(__file__).parent))
import oracle_pentagone as O  # noqa: E402
from protocole_v2 import CARDS_V4, PREDICATS_V4, TOLERANCES_24  # noqa: E402


VERIFY_VERSION = "verify-v4"
SCHEMA_OUTPUT = "benchmark-lab-x/verifier-output/v4"
BUDGET_APPEL_MS = 120_000
MARGE_CONFINEMENT = mpf("-0.002")
T_REFERENCE = mpf("24")
TOLERANCES = {h: mpf("0.01") for h in ("35", "55", "75")}
TOLERANCES_REF = tuple(mpf(x) for x in TOLERANCES_24)
GRILLE_COURTE = tuple(mpf(k) / 2 for k in range(41))
GRILLE_LONGUE = tuple(mpf(k) / 2 for k in range(151))
INSTANTS_DETERMINISME = tuple(dict.fromkeys(
    [*GRILLE_LONGUE, T_REFERENCE, mpf("35"), mpf("55"), mpf("75")]
))


def extraire_html(texte: str) -> str | None:
    m = re.search(r"<html\b.*?</html>", texte, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(0)
    return texte if "<script" in texte.lower() else None


def _base(card_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_OUTPUT,
        "verify_version": VERIFY_VERSION,
        "card_id": card_id,
        "predicates": {p: False for p in PREDICATS_V4[card_id]},
        "measurements": {},
    }


def _unknown(card_id: str, cause: str, detail: str | None = None) -> dict[str, Any]:
    res = _base(card_id)
    res.update({"etat": "UNKNOWN", "cause_code": cause})
    if detail:
        res["detail"] = detail
    return res


def _score_binaire(card_id: str, predicats: dict[str, bool], cause: str | None) -> dict[str, Any]:
    res = _base(card_id)
    res["predicates"] = predicats
    passe = all(predicats.values())
    res.update({"etat": "SCORED", "verdict": "PASS" if passe else "FAIL"})
    if not passe:
        res["cause_code"] = cause
    return res


def _score_niveaux(
    card_id: str,
    predicats: dict[str, bool],
    cause: str | None,
    mesures: dict[str, Any],
) -> dict[str, Any]:
    ordre = PREDICATS_V4[card_id]
    atteint = 0
    frontiere = None
    for rang, nom in enumerate(ordre, start=1):
        if predicats.get(nom) is True:
            atteint = rang
        else:
            frontiere = nom
            break
    res = _base(card_id)
    res.update({
        "etat": "SCORED",
        "verdict": "PASS" if atteint == len(ordre) else "FAIL",
        "niveau": atteint,
        "frontiere": frontiere,
        "predicates": {nom: bool(predicats.get(nom)) for nom in ordre},
        "measurements": mesures,
    })
    if atteint != len(ordre):
        res["cause_code"] = cause
    return res


def _evaluer(page, instants: tuple[mpf, ...] | list[mpf]) -> list[list[float] | None] | None:
    page.set_default_timeout(BUDGET_APPEL_MS)
    js = """(ts) => ts.map(t => {
        try {
            const r = (typeof simulate === 'function') ? simulate(t) : null;
            if (!Array.isArray(r) || r.length !== 2) return null;
            const x = Number(r[0]), y = Number(r[1]);
            return (Number.isFinite(x) && Number.isFinite(y)) ? [x, y] : null;
        } catch (e) { return null; }
    })"""
    try:
        return page.evaluate(js, [float(t) for t in instants])
    except Exception:
        return None


def _page(nav, html: str):
    page = nav.new_page(viewport={"width": 800, "height": 500}, device_scale_factor=1)
    page.route("**/*", lambda route: route.abort())
    page.set_content(html)
    page.wait_for_timeout(300)
    return page


def _valides(valeurs: list[list[float] | None] | None, total: int) -> bool:
    return valeurs is not None and len(valeurs) == total and all(v is not None for v in valeurs)


def _oracle() -> list[tuple[mpf, tuple[mpf, mpf], tuple[mpf, mpf]]]:
    cache = Path(__file__).parent.parent / "tasks/dev/pentagone-rotatif/oracle-cache.json"
    brut = json.loads(cache.read_text(encoding="utf-8"))
    return [(mpf(t), (mpf(q[0]), mpf(q[1])), (mpf(v[0]), mpf(v[1])))
            for t, q, v in brut["etats"]]


def _distance(q: list[float], t: mpf, etats) -> mpf:
    ref = O.position(t, etats)
    return sqrt((mpf(q[0]) - ref[0]) ** 2 + (mpf(q[1]) - ref[1]) ** 2)


def _dedans(q: list[float], t: mpf) -> bool:
    return O.dedans((mpf(q[0]), mpf(q[1])), t, MARGE_CONFINEMENT)


def verifier(card_id: str, chemin: Path) -> dict[str, Any]:
    if card_id not in CARDS_V4:
        raise ValueError(f"carte inconnue: {card_id}")
    html = extraire_html(chemin.read_text(encoding="utf-8"))
    if html is None:
        if card_id == "pentagone-api":
            return _score_binaire(card_id, {"P0_PAGE": False, "P1_API_NUMERIC_TOTAL": False},
                                   "OUTPUT_NO_PAGE")
        return _unknown(card_id, "UPSTREAM_CARD_UNOBSERVABLE", "aucune page exploitable")

    from playwright.sync_api import sync_playwright
    from moteur_rendu import lancer_chromium

    with sync_playwright() as p:
        nav = lancer_chromium(p)
        try:
            page = _page(nav, html)
            if card_id == "pentagone-api":
                valeurs = _evaluer(page, list(INSTANTS_DETERMINISME))
                predicats = {
                    "P0_PAGE": True,
                    "P1_API_NUMERIC_TOTAL": _valides(valeurs, len(INSTANTS_DETERMINISME)),
                }
                res = _score_binaire(
                    card_id, predicats,
                    None if predicats["P1_API_NUMERIC_TOTAL"] else "API_MISSING_OR_INVALID",
                )
            elif card_id == "pentagone-determinisme":
                ordre = list(INSTANTS_DETERMINISME)
                a1 = _evaluer(page, ordre)
                a2 = _evaluer(page, ordre)
                inverse = _evaluer(page, list(reversed(ordre)))
                page.close()
                page2 = _page(nav, html)
                a3 = _evaluer(page2, ordre)
                page2.close()
                if not all(_valides(v, len(ordre)) for v in (a1, a2, inverse, a3)):
                    res = _unknown(card_id, "UPSTREAM_CARD_UNOBSERVABLE",
                                   "API numérique totale non observable")
                else:
                    repeatable = a1 == a2 == a3
                    order_independent = a1 == list(reversed(inverse))
                    cause = None
                    if not repeatable:
                        cause = "NON_DETERMINISTIC"
                    elif not order_independent:
                        cause = "ORDER_DEPENDENT"
                    res = _score_binaire(card_id, {
                        "D1_REPEATABLE": repeatable,
                        "D2_ORDER_INDEPENDENT": order_independent,
                    }, cause)
            elif card_id == "pentagone-confinement-court":
                valeurs = _evaluer(page, list(GRILLE_COURTE))
                if not _valides(valeurs, len(GRILLE_COURTE)):
                    res = _unknown(card_id, "UPSTREAM_CARD_UNOBSERVABLE",
                                   "API numérique totale non observable")
                else:
                    q0 = valeurs[0]
                    initial = sqrt((mpf(q0[0]) - O.P0[0]) ** 2
                                   + (mpf(q0[1]) - O.P0[1]) ** 2) <= mpf("1e-9")
                    predicats = {"I0_INITIAL_STATE": bool(initial)}
                    mesures: dict[str, Any] = {}
                    for h in (2, 10, 20):
                        ok = all(_dedans(q, t) for q, t in zip(valeurs, GRILLE_COURTE) if t <= h)
                        predicats[f"C{h}_CONFINEMENT"] = ok
                        mesures[f"outside_until_{h}"] = sum(
                            not _dedans(q, t) for q, t in zip(valeurs, GRILLE_COURTE) if t <= h
                        )
                    cause = "INITIAL_STATE_INVALID" if not initial else "OUT_OF_BOUNDS"
                    res = _score_niveaux(card_id, predicats, cause, mesures)
            elif card_id == "pentagone-precision-24s":
                valeurs = _evaluer(page, [T_REFERENCE])
                if not _valides(valeurs, 1):
                    res = _unknown(card_id, "UPSTREAM_CARD_UNOBSERVABLE",
                                   "position à 24 s non observable")
                else:
                    ecart = _distance(valeurs[0], T_REFERENCE, _oracle())
                    predicats = {
                        nom: bool(ecart <= tol)
                        for nom, tol in zip(PREDICATS_V4[card_id], TOLERANCES_REF)
                    }
                    res = _score_niveaux(
                        card_id, predicats, "PRECISION_THRESHOLD_FAILED",
                        {"instant_s": 24, "absolute_error": float(ecart)},
                    )
            else:
                valeurs = _evaluer(page, list(GRILLE_LONGUE))
                if not _valides(valeurs, len(GRILLE_LONGUE)):
                    res = _unknown(card_id, "UPSTREAM_CARD_UNOBSERVABLE",
                                   "API numérique totale non observable")
                else:
                    etats = _oracle()
                    predicats: dict[str, bool] = {}
                    mesures = {}
                    cause = None
                    for h in (35, 55, 75):
                        confinement = all(
                            _dedans(q, t) for q, t in zip(valeurs, GRILLE_LONGUE) if t <= h
                        )
                        qh = valeurs[GRILLE_LONGUE.index(mpf(h))]
                        ecart = _distance(qh, mpf(h), etats)
                        precision = ecart <= TOLERANCES[str(h)]
                        predicats[f"C{h}_CONFINEMENT"] = confinement
                        predicats[f"E{h}_PRECISION"] = bool(precision)
                        mesures[f"absolute_error_{h}"] = float(ecart)
                        mesures[f"outside_until_{h}"] = sum(
                            not _dedans(q, t) for q, t in zip(valeurs, GRILLE_LONGUE) if t <= h
                        )
                        if cause is None and not confinement:
                            cause = "OUT_OF_BOUNDS"
                        if cause is None and not precision:
                            cause = "PRECISION_THRESHOLD_FAILED"
                    res = _score_niveaux(card_id, predicats, cause, mesures)
            res["browser_version"] = nav.version
            return res
        finally:
            nav.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--card", choices=CARDS_V4, required=True)
    ap.add_argument("response", type=Path)
    args = ap.parse_args()
    try:
        resultat = verifier(args.card, args.response)
    except Exception as exc:
        print(f"erreur du vérificateur: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(resultat, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
