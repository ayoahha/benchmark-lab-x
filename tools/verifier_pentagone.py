# /// script
# requires-python = ">=3.12"
# dependencies = ["playwright==1.62.0", "mpmath"]
# ///
"""Vérificateur de la carte pentagone-rotatif.

Charge la page du modèle dans le Chromium épinglé, hors ligne, appelle
`simulate(t)` aux instants d'évaluation, et compare à l'oracle événementiel.

Cinquante et un paliers sont mesurés séparément : la note est le plus grand k tel que
les paliers 1 à k passent tous. Aucun jugement, aucun raster dans le score
"""

import json
import re
import sys
from pathlib import Path

from mpmath import mpf, sqrt

sys.path.insert(0, str(Path(__file__).parent))
import oracle_pentagone as O  # noqa: E402

# Instants d’évaluation côté juge : ils ne figurent ni dans task.md ni dans
# donnees.md et sont versionnés avec le vérificateur
# Six horizons de confinement, une échelle de précision à 24 s et trois
# horizons longs avec précision : 51 paliers au total
# Le dernier, à 75 s, reste hors de portée du meilleur modèle observé
# Au-delà de 80 s, l’erreur sature à la taille du polygone et le niveau cesse
# de mesurer : 75 s est le dernier horizon informatif
HORIZONS = ["2", "10", "20", "35", "55", "75"]
T_NIVEAUX = {h: mpf(h) for h in HORIZONS}
TOLERANCES = {"2": mpf("0.05"), "10": mpf("0.02"), "20": mpf("0.01"),
              "35": mpf("0.01"), "55": mpf("0.01"), "75": mpf("0.01")}

# verify-v2, 2026-08-05 : échelle de tolérance à instant fixe
# La v1 plaçait sept horizons à 2, 5, 10, 20, 35, 55 et 75 s. Mesuré sur les
# 26 réponses de la campagne du 2026-08-04 : tout float64 correct passe jusqu'à
# 20 s sans effort et aucun ne passe 35 s, si bien que six candidats sur treize
# tombaient exactement au même palier. L'information discriminante vit entre
# 22 et 30 s, où la carte ne regardait rien
# Déplacer les horizons ne suffit pas : l'erreur croît de e^1,06 par seconde,
# soit une demi-décade, donc la résolution temporelle plafonne à un facteur 3
# Ce qui discrimine vraiment est la tolérance à un instant fixe. T_REFERENCE
# est choisi dans la bande utile, et la précision y est mesurée par demi-décades
T_REFERENCE = mpf("24")
# verify-v3, 2026-08-05 : l'échelle couvre toute l'étendue mesurée
# Les écarts observés à 24 s vont de 5,1e-17 m pour la meilleure implémentation
# à 1,4e+6 m pour la pire, soit 24,5 décades. Une échelle qui s'arrêtait à 1e-6
# écrasait tout le haut du panel. Les crans sont des demi-décades : 39 paliers
# de précision, ce qui porte le total à 51
# Limite connue et assumée : l'écart observé entre runs d'un même candidat vaut
# 1,38 décade en médiane. Les paliers se lisent donc comme une distribution,
# jamais comme une précision statistique absolue
TOLERANCES_REF = [mpf(x) for x in
                  ("1e+2", "3e+1", "1e+1", "3e+0", "1e+0", "3e-1", "1e-1", "3e-2", "1e-2", "3e-3", "1e-3", "3e-4", "1e-4", "3e-5", "1e-5", "3e-6", "1e-6", "3e-7", "1e-7", "3e-8", "1e-8", "3e-9", "1e-9", "3e-10", "1e-10", "3e-11", "1e-11", "3e-12", "1e-12", "3e-13", "1e-13", "3e-14", "1e-14", "3e-15", "1e-15", "3e-16", "1e-16", "3e-17", "1e-17")]



# Confinement testé sur le MÊME horizon que les niveaux, pas au-delà. Le tester
# jusqu'à 60 s alors que le dernier niveau s'arrête à 45 s recalait des
# implémentations excellentes sur un domaine où rien d'autre n'est mesuré :
# le score mentait
T_CONFINEMENT = [mpf(k) * mpf("75") / 150 for k in range(151)]  # 0 à 75 s
MARGE_CONFINEMENT = mpf("-0.002")  # 2 mm de tolérance vers l'extérieur


def extraire_html(texte: str) -> str | None:
    m = re.search(r"<html\b.*?</html>", texte, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(0)
    # tolérance de forme : une page sans balise <html> mais avec du script
    return texte if "<script" in texte.lower() else None


# Budget de temps déclaré par la carte. Ce délai borne ce que Playwright sait
# borner : chargement, navigation, attentes. Il ne borne PAS du JavaScript
# synchrone qui monopolise le thread de la page — mesuré le 2026-08-05, une
# page qui recalcule toute la trajectoire à chaque appel a tourné dix minutes
# malgré ce réglage. Le seul verrou fiable est le délai de processus posé par
# l'appelant, dans `tools/rapport_campagne.py`
BUDGET_APPEL_MS = 120_000


def appeler(page, instants):
    """Appelle simulate() sur une liste d'instants

    Rend None si l'appel casse ou si Playwright peut interrompre son attente.
    Le délai opposable au processus complet est appliqué par le rapporteur
    """
    page.set_default_timeout(BUDGET_APPEL_MS)
    js = """(ts) => ts.map(t => {
        try {
            const r = (typeof simulate === 'function') ? simulate(t) : null;
            if (!Array.isArray(r) || r.length < 2) return null;
            const x = Number(r[0]), y = Number(r[1]);
            return (Number.isFinite(x) && Number.isFinite(y)) ? [x, y] : null;
        } catch (e) { return null; }
    })"""
    try:
        return page.evaluate(js, [float(t) for t in instants])
    except Exception:  # attente interruptible, page morte, moteur en erreur
        return None


def verifier(chemin: Path) -> dict:
    texte = chemin.read_text(encoding="utf-8")
    res: dict = {"niveaux": {}, "mesures": {}}

    html = extraire_html(texte)
    res["predicats"] = {"P0_page_presente": html is not None}
    if html is None:
        res["verdict"] = "FAIL"
        res["niveau_atteint"] = 0
        res["frontiere"] = "A0_page"
        return res

    from playwright.sync_api import sync_playwright

    from moteur_rendu import MoteurNonConforme, lancer_chromium

    instants_ordre1 = T_CONFINEMENT + list(T_NIVEAUX.values()) + [T_REFERENCE]
    instants_ordre2 = list(reversed(instants_ordre1))

    try:
        with sync_playwright() as p:
            nav = lancer_chromium(p)
            res["moteur_rendu"] = nav.version
            page = nav.new_page(viewport={"width": 800, "height": 500},
                                device_scale_factor=1)
            page.route("**/*", lambda route: route.abort())  # hors ligne strict
            page.set_content(html)
            page.wait_for_timeout(300)
            a = appeler(page, instants_ordre1)
            b = appeler(page, instants_ordre2)
            capture = page.screenshot()
            nav.close()
    except MoteurNonConforme:
        # L'environnement de mesure n'est pas conforme : ce n'est pas un défaut
        # du candidat et cela ne doit jamais devenir un FAIL à son nom. On
        # laisse remonter, le vérificateur s'arrête sans produire de note
        raise
    except Exception as exc:
        res["verdict"] = "FAIL"
        res["raison"] = f"la page ne s'exécute pas : {type(exc).__name__}"
        res["niveau_atteint"] = 0
        res["frontiere"] = "A0_page"
        return res

    res["taille_capture"] = len(capture)

    # Oracle : lu depuis le cache figé de la carte. Le recalculer à chaque run
    # coûte 30 s pour un résultat identique ; le cache est un artefact de la
    # carte, régénérable par `oracle_pentagone.py` et vérifiable
    cache = chemin.parent / "oracle-cache.json"
    if not cache.is_file():
        cache = Path(__file__).parent.parent / "tasks/dev/pentagone-rotatif/oracle-cache.json"
    brut = json.loads(cache.read_text(encoding="utf-8"))
    etats = [(mpf(t), (mpf(q[0]), mpf(q[1])), (mpf(v[0]), mpf(v[1])))
             for t, q, v in brut["etats"]]

    # Mesures nécessaires à l’échelle de cinquante et un paliers
    N = {}

    # A1 : TOUS les instants répondent, dans les deux ordres. Un `any` laissait
    # passer une fonction qui ne répond qu'à un seul instant : ce n'est pas une
    # interface, c'est un accident
    b_remis = list(reversed(b)) if b else None
    totale = a is not None and all(x is not None for x in a)
    N["A0_page"] = True  # atteint dès qu'on arrive ici
    N["A1_api_totale"] = bool(
        totale and b_remis is not None
        and all(y is not None and x[0] == y[0] and x[1] == y[1]
                for x, y in zip(a, b_remis))
    )

    # I0 : la fonction rend bien l'état initial
    q0 = a[0] if a else None
    N["I0_etat_initial"] = bool(
        q0 is not None
        and sqrt((mpf(q0[0]) - O.P0[0]) ** 2 + (mpf(q0[1]) - O.P0[1]) ** 2) <= mpf("1e-9")
    )

    dehors_total, premiere_sortie, depassement_max = 0, None, 0.0
    par_horizon = {h: 0 for h in HORIZONS}
    for i, t in enumerate(T_CONFINEMENT):
        q = a[i] if a else None
        ok = q is not None and O.dedans((mpf(q[0]), mpf(q[1])), t, MARGE_CONFINEMENT)
        if not ok:
            dehors_total += 1
            if premiere_sortie is None:
                premiere_sortie = float(t)
            if q is not None:
                d = min(float(n_[0] * (mpf(q[0]) - w[0]) + n_[1] * (mpf(q[1]) - w[1]))
                        for w, n_ in (O.paroi(k, t) for k in range(5)))
                depassement_max = max(depassement_max, -d)
            for h in par_horizon:
                if t <= mpf(h):
                    par_horizon[h] += 1
    res["mesures"]["instants_hors_pentagone"] = dehors_total
    res["mesures"]["premiere_sortie_s"] = premiere_sortie
    res["mesures"]["depassement_max_mm"] = round(depassement_max * 1000, 1)

    base = len(T_CONFINEMENT)
    for j, (h, t) in enumerate(T_NIVEAUX.items()):
        nom = h
        N[f"C{h}_confinement"] = par_horizon[h] == 0
        q = a[base + j] if a else None
        if q is None:
            res["mesures"][f"ecart_{nom}"] = None
            N[f"E{h}_precision"] = False
            continue
        ref = O.position(t, etats)
        d = sqrt((mpf(q[0]) - ref[0]) ** 2 + (mpf(q[1]) - ref[1]) ** 2)
        res["mesures"][f"ecart_{nom}"] = float(d)
        res["mesures"][f"tolerance_{nom}"] = float(TOLERANCES[nom])
        N[f"E{h}_precision"] = bool(d <= TOLERANCES[nom])

    # Échelle de tolérance à instant fixe : la mesure qui discrimine
    qr = a[base + len(T_NIVEAUX)] if a else None
    if qr is None:
        ecart_ref = None
    else:
        refr = O.position(T_REFERENCE, etats)
        ecart_ref = sqrt((mpf(qr[0]) - refr[0]) ** 2 + (mpf(qr[1]) - refr[1]) ** 2)
    res["mesures"]["instant_reference_s"] = float(T_REFERENCE)
    res["mesures"]["ecart_reference"] = None if ecart_ref is None else float(ecart_ref)
    for tol in TOLERANCES_REF:
        cle = f"P{float(tol):.0e}_precision_ref".replace("e-0", "e-")
        N[cle] = bool(ecart_ref is not None and ecart_ref <= tol)

    # Ordre des paliers. Les confinements courts et l'échelle de précision
    # viennent AVANT les horizons longs : un témoin précis à 24 s mais qui
    # quitte le polygone à 60 s doit garder son crédit de précision, sinon le
    # score ment. Le calibrage du 2026-08-05 a rejeté un ordre où C75 précédait
    # l'échelle : les cinq témoins précis y tombaient tous à 8
    ORDRE = ["A0_page", "A1_api_totale", "I0_etat_initial"]
    ORDRE += [f"C{h}_confinement" for h in ("2", "10", "20")]
    ORDRE += [f"P{float(tol):.0e}_precision_ref".replace("e-0", "e-")
              for tol in TOLERANCES_REF]
    for h in ("35", "55", "75"):
        ORDRE += [f"C{h}_confinement", f"E{h}_precision"]
    res["niveaux"] = {k: bool(N.get(k)) for k in ORDRE}
    atteint, frontiere = 0, ORDRE[0]
    for k, nom in enumerate(ORDRE, start=1):
        if N.get(nom):
            atteint, frontiere = k, nom
        else:
            frontiere = nom
            break
    res["niveau_atteint"] = atteint
    res["frontiere"] = frontiere
    res["verdict"] = "PASS" if atteint == len(ORDRE) else "FAIL"
    return res


if __name__ == "__main__":
    print(json.dumps(verifier(Path(sys.argv[1])), ensure_ascii=False, indent=2))
