# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow", "numpy", "playwright==1.62.0"]
# ///
"""Vérificateur de la carte camembert-parts.

Mesure le raster rendu, jamais le balisage. Pour chaque couleur, les pixels de
l’anneau donnent la surface remplie et le départ angulaire. La surface varie
avec un large-arc-flag fautif, contrairement à la seule étendue angulaire.

Six prédicats P2 à P7 sont comptés : couleurs, anneau creux, surfaces, départ à
midi, sens horaire et arc majeur. Le score indique combien passent ; le verdict
reste PASS ou FAIL pour cette carte historique
"""

import io
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

CANEVAS_L, CANEVAS_H = 800, 500
CX, CY = 400, 250
R_EXT, R_INT = 180, 90

# ordre, canal, valeur, couleur
SPEC = [
    ("Magasin", 550, "#1f77b4"),
    ("Web", 180, "#d62728"),
    ("Grossistes", 120, "#2ca02c"),
    ("Marchés", 80, "#ff7f0e"),
    ("Téléphone", 45, "#9467bd"),
    ("Export", 25, "#8c564b"),
]
TOTAL = sum(v for _, v, _ in SPEC)
DIST_COULEUR = 40
PIXELS_MIN = 200
TOL_ANGLE = 6.0  # degrés


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def angles_attendus():
    """Départ et étendue de chaque part, en degrés horaires depuis midi"""
    out, cur = {}, 0.0
    for nom, val, _ in SPEC:
        etendue = val / TOTAL * 360.0
        out[nom] = (cur, etendue)
        cur += etendue
    return out


def extraire_svg(texte):
    m = re.search(r"<svg\b.*?</svg>", texte, re.DOTALL | re.IGNORECASE)
    return m.group(0) if m else None


def rendre(svg):
    from playwright.sync_api import sync_playwright

    from moteur_rendu import MoteurNonConforme, lancer_chromium
    html = ('<!doctype html><html><body style="margin:0;padding:0;background:#fff">'
            f"{svg}</body></html>")
    try:
        with sync_playwright() as p:
            nav = lancer_chromium(p)
            version = nav.version
            page = nav.new_page(viewport={"width": CANEVAS_L, "height": CANEVAS_H},
                                device_scale_factor=1)
            page.set_content(html)
            png = page.screenshot()
            nav.close()
        return png, version
    except MoteurNonConforme:
        # environnement de mesure non conforme, jamais un défaut du candidat
        raise
    except Exception as exc:
        return None, f"erreur: {type(exc).__name__}"


def verifier(chemin):
    texte = Path(chemin).read_text(encoding="utf-8")
    res = {"predicats": {}, "mesures": {}}
    svg = extraire_svg(texte)
    res["predicats"]["P0_svg_present"] = svg is not None
    if svg is None:
        res["verdict"] = "NON_NOTABLE"
        return res

    png, moteur = rendre(svg)
    res["moteur_rendu"] = moteur
    res["predicats"]["P1_se_rend"] = png is not None
    if png is None:
        res["verdict"] = "FAIL"
        return res
    arr = np.array(Image.open(io.BytesIO(png)).convert("RGB"))

    ys, xs = np.mgrid[0:CANEVAS_H, 0:CANEVAS_L]
    dx, dy = xs - CX, ys - CY
    rayon = np.sqrt(dx ** 2 + dy ** 2)
    # angle horaire depuis midi, dans [0, 360)
    ang = (np.degrees(np.arctan2(dx, -dy))) % 360.0

    attendus = angles_attendus()
    res["mesures"]["angles_attendus"] = {
        n: [round(d, 2), round(e, 2)] for n, (d, e) in attendus.items()
    }

    anneau = (rayon >= R_INT) & (rayon <= R_EXT)
    aire_anneau = float(np.pi * (R_EXT ** 2 - R_INT ** 2))

    mesures, presentes = {}, 0
    for nom, val, coul in SPEC:
        d = np.sqrt(((arr.astype(np.int16) - np.array(hex_rgb(coul))) ** 2).sum(axis=2))
        m = (d < DIST_COULEUR) & anneau
        n = int(m.sum())
        if n < PIXELS_MIN:
            mesures[nom] = None
            continue
        presentes += 1
        a = np.sort(ang[m])
        # début de la part : l'angle qui suit le plus grand trou circulaire
        trous = np.diff(a)
        boucle = (a[0] + 360.0) - a[-1]
        i = int(np.argmax(trous)) if len(trous) and trous.max() > boucle else None
        depart = float(a[i + 1]) if i is not None else float(a[0])
        # La SURFACE est la mesure qui compte. L'étendue angulaire ne distingue
        # pas un arc retourné : la forme est fermée par Z, donc elle balaie les
        # mêmes angles quel que soit le large-arc-flag. Seule l'aire remplie
        # change, et elle change de moitié
        aire_att = val / TOTAL * aire_anneau
        mesures[nom] = {
            "depart": round(depart, 1),
            "aire_px": n,
            "aire_attendue": round(aire_att),
            "ecart_pct": round(100.0 * (n - aire_att) / aire_att, 1),
        }

    res["mesures"]["parts_mesurees"] = mesures
    res["predicats"]["P2_six_couleurs"] = presentes == len(SPEC)

    # anneau : centre blanc, couronne colorée
    centre = np.sqrt(((arr[CY, CX].astype(int) - np.array([255, 255, 255])) ** 2).sum())
    res["mesures"]["centre_blanc"] = bool(centre < 40)
    res["predicats"]["P3_anneau_creux"] = bool(centre < 40)

    # P4 : surface de chaque part, tolérance 6 % (le crénelage en coûte ~2 %)
    ok_e = []
    for nom, _, _ in SPEC:
        mm = mesures.get(nom)
        ok_e.append(mm is not None and abs(mm["ecart_pct"]) <= 6.0)
    res["predicats"]["P4_surfaces_des_parts"] = all(ok_e)
    res["mesures"]["surfaces_correctes"] = {n: o for (n, _, _), o in zip(SPEC, ok_e)}

    # P5 : la première part commence à midi
    m1 = mesures.get(SPEC[0][0])
    depart_ok = m1 is not None and (m1["depart"] <= TOL_ANGLE or m1["depart"] >= 360 - TOL_ANGLE)
    res["predicats"]["P5_depart_midi"] = bool(depart_ok)

    # P6 : sens horaire, départs croissants dans l'ordre du tableau
    departs = [mesures[n]["depart"] if mesures.get(n) else None for n, _, _ in SPEC]
    ok_ordre = all(d is not None for d in departs) and all(
        departs[i] < departs[i + 1] for i in range(len(departs) - 1)
    )
    res["predicats"]["P6_sens_horaire"] = bool(ok_ordre)
    res["mesures"]["departs_mesures"] = departs

    # P7 : le piège, la part de 198° dépasse le demi-tour
    # large-arc-flag laissé à 0 produit l'arc complémentaire : ~162° au lieu de 198°
    mm = mesures.get("Magasin")
    if mm is None:
        drapeau = "INDETERMINE"
    elif abs(mm["ecart_pct"]) <= 6.0:
        drapeau = "CORRECT"
    elif -65.0 <= mm["ecart_pct"] <= -38.0:
        # l'arc retourné remplit environ la moitié de la surface attendue
        drapeau = "PIEGE_LARGE_ARC_FLAG"
    else:
        drapeau = "INDETERMINE"
    res["mesures"]["classement_large_arc"] = drapeau
    res["mesures"]["magasin_aire"] = mm["aire_px"] if mm else None
    res["mesures"]["magasin_aire_attendue"] = mm["aire_attendue"] if mm else None
    res["mesures"]["magasin_ecart_pct"] = mm["ecart_pct"] if mm else None
    res["predicats"]["P7_large_arc_flag"] = drapeau == "CORRECT"

    pieges = [k for k in res["predicats"] if k[1] in "234567"]
    reussis = sum(1 for k in pieges if res["predicats"][k])
    res["score_pieges"] = f"{reussis}/{len(pieges)}"
    res["verdict"] = "PASS" if reussis == len(pieges) else "FAIL"
    return res


if __name__ == "__main__":
    print(json.dumps(verifier(sys.argv[1]), ensure_ascii=False, indent=2))
