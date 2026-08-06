"""Moteur de rendu épinglé, partagé par les vérificateurs à page web.

Pourquoi ce fichier existe. Les trois vérificateurs faisaient
`p.chromium.launch()` sans épingle, puis lisaient `nav.version` pour l'écrire
dans leur résultat. Un numéro de version dans une sortie prouve ce qui a tourné,
jamais ce qui tournera : une mise à jour de Playwright aurait changé le moteur
sans qu'aucune alerte se déclenche, et deux campagnes se seraient comparées sous
des rendus différents. La carte, le README et l'artefact publié affirmaient
pourtant « Chromium épinglé ».

L'épingle tient à deux verrous, et il en faut deux :

- la version de Playwright est figée dans l'en-tête `uv` de chaque vérificateur,
  ce qui détermine quel Chromium est téléchargé ;
- la version du moteur est vérifiée au lancement contre la constante ci-dessous,
  ce qui attrape un navigateur installé autrement, un cache partagé ou un
  `channel` local qui prendrait le dessus.

Le second verrou existe parce que le premier ment en silence : rien n'empêche un
Chromium déjà présent d'être réutilisé.

Relever l'épingle est un changement de l'environnement de mesure au sens R-015 :
il incrémente `verify-vM` et impose une renotation commune avant toute
comparaison avec les campagnes antérieures.
"""

from typing import Any

# Relevé le 2026-08-06 : playwright 1.62.0 embarque ce Chromium
PLAYWRIGHT_EPINGLE = "1.62.0"
CHROMIUM_EPINGLE = "151.0.7922.34"
SCHEMA_ENVIRONNEMENT = "benchmark-lab-x/environment/v1"


class MoteurNonConforme(RuntimeError):
    """Le moteur de rendu diffère de l'épingle : la mesure n'est pas comparable"""


def lancer_chromium(p: Any, strict: bool = True) -> Any:
    """Lancer le Chromium épinglé, ou refuser de mesurer.

    `strict=False` sert au diagnostic hors campagne ; il ne doit jamais servir
    à produire un résultat destiné à une page
    """
    nav = p.chromium.launch()
    if strict and nav.version != CHROMIUM_EPINGLE:
        version = nav.version
        nav.close()
        raise MoteurNonConforme(
            f"Chromium {version} au lieu de {CHROMIUM_EPINGLE} : l'environnement "
            f"de mesure a changé. Réinstaller le navigateur de playwright "
            f"{PLAYWRIGHT_EPINGLE} (`uv run playwright install chromium`), ou "
            f"relever l'épingle et incrémenter verify-vM (R-015)"
        )
    return nav


def descripteur(navigateur: Any = None) -> dict:
    """Descripteur d'environnement de mesure, au format de l'ARD §2.2.

    `sandbox_image_digest` vaut `null` tant que la vérification tourne sur
    l'hôte et non dans une image : l'ARD ne le rend obligatoire qu'à partir de
    G4, et inventer une valeur serait pire que l'absence
    """
    import locale as _locale
    import platform
    import time as _time

    # Locale et fuseau sont LUS sur l'hôte, jamais posés en constante. Une
    # constante mettrait dans l'empreinte une affirmation invérifiée : deux
    # machines aux réglages différents rendraient la même empreinte de contexte,
    # ce qui est pire qu'une empreinte absente. Signalé par la revue du
    # 2026-08-06, la version précédente écrivait « fr_FR.UTF-8 » et « UTC » en dur
    try:
        langue, codage = _locale.getlocale()
        lu = f"{langue}.{codage}" if langue and codage else (langue or "opaque")
    except (ValueError, TypeError):
        lu = "opaque"

    return {
        "schema_version": SCHEMA_ENVIRONNEMENT,
        "os": {
            "name": platform.system(),
            "version": platform.release(),
            "kernel": platform.version(),
        },
        "architecture": platform.machine(),
        "locale": lu,
        "timezone": _time.tzname[0] if _time.tzname else "opaque",
        "runtimes": sorted(
            [
                {"name": "python", "version": platform.python_version()},
                {"name": "playwright", "version": PLAYWRIGHT_EPINGLE},
            ],
            key=lambda x: x["name"],
        ),
        "browser": {
            "name": "chromium",
            "version": navigateur.version if navigateur is not None else CHROMIUM_EPINGLE,
        },
        "sandbox_image_digest": None,
    }
