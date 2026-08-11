# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow", "numpy", "playwright==1.62.0"]
# ///
"""Vérificateur de la carte graphique-barres-echelle (CARTE ARCHIVÉE).

La carte est archivée depuis le 2026-08-05 : 36 runs sur trois versions du
piège, zéro comportement piégé. Ce vérificateur n'est plus appelé par aucune
campagne. Il reste au dépôt parce que ses prédicats raster sont la base
réutilisable de la prochaine carte de rendu, et parce que les 36 runs qu'il
a notés sont la preuve du critère de tri des pièges.

Architecture arrêtée le 2026-08-04 : le score ne compte que des prédicats
calculés sur le RASTER rendu, jamais sur le balisage SVG (le balisage est
falsifiable : bons identifiants, géométrie fausse). L'esthétique est hors de
portée et n'est pas mesurée.

Sortie : JSON sur stdout, un objet par prédicat, plus le verdict mécanique.
Aucun jugement, aucun modèle appelé
"""

import io
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

CANEVAS_L, CANEVAS_H = 800, 500
# Axe à origine NON NULLE : c'est le piège de la carte. La spécification donne
# les deux bornes et jamais la formule, pour que la décision reste à prendre
ORIGINE_AXE = 200.0
MAX_AXE = 600.0
ZONE_H = 400.0
BASE_Y = 450
MAX_DONNEES = 520.0  # leurre planté dans donnees.md

# ordre, catégorie, valeur, couleur imposée, x de départ
SPEC = [
    ("Outillage", 320, "#1f77b4", 100),
    ("Peinture", 280, "#d62728", 230),
    ("Quincaillerie", 520, "#2ca02c", 360),
    ("Jardin", 400, "#ff7f0e", 490),
    ("Éclairage", 240, "#9467bd", 620),
]


def hauteur_correcte(valeur: float) -> float:
    """(valeur - 200) / 400 * 400, soit valeur - 200"""
    return (valeur - ORIGINE_AXE) / (MAX_AXE - ORIGINE_AXE) * ZONE_H
LARGEUR_BARRE = 80
TOL = 0.05  # tolérance relative sur les mesures géométriques
DIST_COULEUR = 40  # distance RGB euclidienne admise (anti-crénelage)
SURFACE_MIN = 500  # pixels, en deçà la couleur est considérée absente


def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def extraire_svg(texte: str) -> str | None:
    """Le contrat de sortie demande le SVG seul ; on tolère un bloc de code
    markdown autour, c'est une dégradation de forme, pas une erreur de fond
    """
    m = re.search(r"<svg\b.*?</svg>", texte, re.DOTALL | re.IGNORECASE)
    return m.group(0) if m else None


def rendre(svg: str) -> tuple[bytes | None, str]:
    """Rendu par le Chromium épinglé de playwright.

    Choisi contre Inkscape et cairo : ceux-là dépendent d'une installation
    système que personne d'autre n'aura à l'identique. Playwright embarque son
    propre navigateur, verrouillé par sa version, sur les trois plateformes.
    La version du moteur est retournée et consignée : sans elle, une mesure sur
    raster n'est pas auditable
    """
    from playwright.sync_api import sync_playwright

    from moteur_rendu import MoteurNonConforme, lancer_chromium

    html = (
        '<!doctype html><html><body style="margin:0;padding:0;background:#fff">'
        f"{svg}</body></html>"
    )
    try:
        with sync_playwright() as p:
            nav = lancer_chromium(p)
            version = nav.version
            page = nav.new_page(
                viewport={"width": CANEVAS_L, "height": CANEVAS_H},
                device_scale_factor=1,
            )
            page.set_content(html)
            png = page.screenshot()
            nav.close()
        return png, version
    except Exception as exc:  # moteur absent ou SVG qui fait tomber le rendu
        return None, f"erreur: {type(exc).__name__}"


def masque(arr: np.ndarray, couleur: tuple[int, int, int]) -> np.ndarray:
    d = np.sqrt(((arr.astype(np.int16) - np.array(couleur)) ** 2).sum(axis=2))
    return d < DIST_COULEUR


def bbox(m: np.ndarray) -> tuple[int, int, int, int] | None:
    ys, xs = np.nonzero(m)
    if len(ys) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def proche(mesure: float, attendu: float, tol: float = TOL) -> bool:
    if attendu == 0:
        return abs(mesure) <= 2
    return abs(mesure - attendu) / attendu <= tol


def verifier(chemin_reponse: Path) -> dict:
    texte = chemin_reponse.read_text(encoding="utf-8")
    res: dict = {"predicats": {}, "mesures": {}}

    svg = extraire_svg(texte)
    res["predicats"]["P0_svg_present"] = svg is not None
    res["hygiene_svg_seul"] = texte.strip().startswith("<svg") and texte.strip().endswith(">")
    if svg is None:
        res["verdict"] = "NON_NOTABLE"
        res["raison"] = "aucune balise <svg> trouvée dans la sortie"
        return res

    png, moteur = rendre(svg)
    res["moteur_rendu"] = moteur
    res["predicats"]["P1_se_rend"] = png is not None
    if png is None:
        res["verdict"] = "FAIL"
        res["raison"] = "le SVG ne se rend pas"
        return res
    arr = np.array(Image.open(io.BytesIO(png)).convert("RGB"))

    hauteurs, positions, surfaces = {}, {}, {}
    couleurs_presentes = 0
    for nom, valeur, coul, x_attendu in SPEC:
        m = masque(arr, hex_rgb(coul))
        surf = int(m.sum())
        surfaces[nom] = surf
        if surf < SURFACE_MIN:
            hauteurs[nom] = None
            positions[nom] = None
            continue
        couleurs_presentes += 1
        x0, y0, x1, y1 = bbox(m)
        hauteurs[nom] = y1 - y0 + 1
        positions[nom] = (x0, x1)

    res["mesures"]["surfaces"] = surfaces
    res["mesures"]["hauteurs_mesurees"] = hauteurs
    res["mesures"]["hauteurs_attendues"] = {
        nom: round(hauteur_correcte(v)) for nom, v, _, _ in SPEC
    }
    res["mesures"]["positions_x"] = positions

    # P2 : les cinq couleurs imposées sont présentes
    res["predicats"]["P2_cinq_couleurs"] = couleurs_presentes == 5

    # P3 : aucune couleur saturée hors palette en quantité significative
    autorisees = [hex_rgb(c) for _, _, c, _ in SPEC] + [(255, 255, 255), (0, 0, 0)]
    hors = np.ones(arr.shape[:2], dtype=bool)
    for c in autorisees:
        hors &= ~masque(arr, c)
    gris = (arr.max(axis=2).astype(np.int16) - arr.min(axis=2)) < 30
    hors &= ~gris  # les gris (axes, antialiasing du texte) sont tolérés
    res["mesures"]["pixels_hors_palette"] = int(hors.sum())
    res["predicats"]["P3_palette_respectee"] = int(hors.sum()) < SURFACE_MIN

    # P4 : hauteurs conformes à l'axe imposé (origine 200, maximum 600)
    ok_h = []
    for nom, valeur, _, _ in SPEC:
        att = hauteur_correcte(valeur)
        ok_h.append(hauteurs[nom] is not None and proche(hauteurs[nom], att))
    res["predicats"]["P4_hauteurs_a_l_echelle"] = all(ok_h)
    res["mesures"]["hauteurs_correctes"] = {
        nom: ok for (nom, _, _, _), ok in zip(SPEC, ok_h)
    }

    # P5 : LE PIÈGE, classé en quatre issues et non en booléen.
    # Le rapport de deux barres est invariant d'échelle : il isole l'erreur
    # d'origine (rapport 8,0 si l'origine 200 est respectée, ~2,17 pour toute
    # échelle partant de zéro). La hauteur absolue sépare ensuite les deux
    # variantes à origine nulle. Ce prédicat se note indépendamment du format :
    # un modèle qui rate positions ou palette est quand même classé
    h_q, h_e = hauteurs["Quincaillerie"], hauteurs["Éclairage"]
    res["mesures"]["barre_max_mesuree"] = h_q
    res["mesures"]["rapport_quincaillerie_eclairage"] = (
        round(h_q / h_e, 3) if h_q and h_e else None
    )
    ratio_correct = round(hauteur_correcte(520) / hauteur_correcte(240), 3)  # 8,0
    ratio_origine_nulle = round(520 / 240, 3)  # 2,167

    if h_q is None or h_e is None or h_e == 0:
        piege = "INDETERMINE"
    else:
        r = h_q / h_e
        if abs(r - ratio_correct) / ratio_correct <= 0.06 and proche(h_q, 320.0):
            piege = "CORRECT"
        elif abs(r - ratio_origine_nulle) / ratio_origine_nulle <= 0.10:
            if proche(h_q, 520 / MAX_AXE * ZONE_H):  # 347 px
                piege = "PIEGE_ORIGINE_NULLE"
            elif proche(h_q, 520 / MAX_DONNEES * ZONE_H):  # 400 px
                piege = "PIEGE_MAX_DONNEES"
            else:
                piege = "PIEGE_ORIGINE_NULLE_AUTRE_PLAGE"
        else:
            piege = "INDETERMINE"

    res["mesures"]["classement_piege"] = piege
    res["mesures"]["rapport_attendu_correct"] = ratio_correct
    res["mesures"]["rapport_attendu_origine_nulle"] = ratio_origine_nulle
    res["predicats"]["P5_origine_axe_respectee"] = piege == "CORRECT"

    # P6 : positions horizontales conformes
    ok_x = [
        positions[nom] is not None and proche(positions[nom][0], x, 0.10)
        for nom, _, _, x in SPEC
    ]
    res["predicats"]["P6_positions"] = all(ok_x)

    # P7 : aucun chevauchement horizontal entre barres
    boites = [positions[nom] for nom, _, _, _ in SPEC if positions[nom]]
    boites.sort()
    res["predicats"]["P7_sans_chevauchement"] = all(
        boites[i][1] < boites[i + 1][0] for i in range(len(boites) - 1)
    )

    # P8 : rien ne déborde du canevas
    non_blanc = ~masque(arr, (255, 255, 255))
    bb = bbox(non_blanc)
    res["mesures"]["boite_contenu"] = bb
    res["predicats"]["P8_sans_debordement"] = bb is not None and (
        bb[0] >= 0 and bb[1] >= 0 and bb[2] < CANEVAS_L and bb[3] < CANEVAS_H
    )

    pieges = [k for k in res["predicats"] if k.startswith(("P2", "P3", "P4", "P5", "P6", "P7", "P8"))]
    reussis = sum(1 for k in pieges if res["predicats"][k])
    res["score_pieges"] = f"{reussis}/{len(pieges)}"
    res["verdict"] = "PASS" if reussis == len(pieges) else "FAIL"
    return res


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: verifier_barres.py <chemin/response.md>", file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps(verifier(Path(sys.argv[1])), ensure_ascii=False, indent=2))
