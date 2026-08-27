# /// script
# requires-python = ">=3.12"
# ///
"""Helpers de fixtures V1 partagés entre modules de tests.

Uniquement des ajustements de cohérence de fixtures de test : aucune
preuve versionnée du dépôt n'est modifiée et aucun comportement de
production n'est contourné."""

from __future__ import annotations

import json
from pathlib import Path


def retirer_couverture_publiee(chemin_etat: "Path") -> None:
    """Aligne la copie bac à sable de l'état V1 sur le scénario testé :
    sans l'arbre de reçus et de verdicts officiels, aucune couverture
    annoncée ne peut être redérivée. Le bloc hérité du dépôt est retiré
    pour annoncer honnêtement « aucune couverture publiée »."""
    contenu = json.loads(chemin_etat.read_text(encoding="utf-8"))
    contenu.pop("couverture", None)
    chemin_etat.write_text(
        json.dumps(contenu, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
