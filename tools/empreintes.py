"""Canonicalisation et empreintes des manifestes, source unique (ARD §2.2).

Ce module existe parce que la fonction vivait en double, dans `collect.py` et
`rapport_campagne.py`. Deux copies d'une fonction de hachage sont une dérive qui
attend : le jour où l'une des deux change, deux manifestes sémantiquement
identiques rendent deux empreintes différentes, et rien ne le signale — c'est
exactement le genre de panne silencieuse que les empreintes sont censées
empêcher. Signalé par la revue d'implémentation du 2026-08-06.

L'ARD impose RFC 8785. Cette implémentation en couvre ce dont les manifestes
actuels ont besoin, et `verifier_canonicalisable` refuse ce qu'elle ne couvre
pas plutôt que de produire une empreinte fausse en silence :

- les clés sont triées par point de code, ce qui coïncide avec le tri par unité
  de code UTF-16 de RFC 8785 tant que les clés restent dans le plan multilingue
  de base ; au-delà, elles sont refusées ;
- un flottant de valeur entière s'écrit `0` et non `0.0` ;
- un flottant non entier est refusé : RFC 8785 impose la représentation la plus
  courte au sens ECMAScript, que `json.dumps` ne produit pas, et aucun manifeste
  du schéma actuel n'en contient.
"""

import hashlib
import json
from typing import Any


class ManifesteNonCanonicalisable(ValueError):
    """L'objet contient une valeur que cette implémentation ne sait pas canonicaliser"""


def _normaliser(v: Any, chemin: str = "$") -> Any:
    if isinstance(v, bool):
        # avant le test d'entier : en Python, un booléen EST un entier
        return v
    if isinstance(v, float):
        if not v.is_integer():
            raise ManifesteNonCanonicalisable(
                f"{chemin} : flottant non entier {v!r}. RFC 8785 impose la "
                f"représentation ECMAScript la plus courte, que cette "
                f"implémentation ne produit pas. Convertir en chaîne ou en entier"
            )
        return int(v)
    if isinstance(v, dict):
        for k in v:
            if not isinstance(k, str):
                raise ManifesteNonCanonicalisable(f"{chemin} : clé non textuelle {k!r}")
            if any(ord(c) > 0xFFFF for c in k):
                raise ManifesteNonCanonicalisable(
                    f"{chemin} : clé hors du plan multilingue de base {k!r} ; "
                    f"le tri par point de code cesserait de coïncider avec UTF-16"
                )
        return {k: _normaliser(x, f"{chemin}.{k}") for k, x in v.items()}
    if isinstance(v, list):
        return [_normaliser(x, f"{chemin}[{i}]") for i, x in enumerate(v)]
    if v is None or isinstance(v, (str, int)):
        return v
    raise ManifesteNonCanonicalisable(f"{chemin} : type non sérialisable {type(v).__name__}")


def canonicaliser(obj: Any) -> bytes:
    """Octets canoniques d'un manifeste, en UTF-8"""
    return json.dumps(_normaliser(obj), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def empreinte(obj: Any) -> str:
    """SHA-256 hexadécimal minuscule complet, 64 caractères comme l'exige l'ARD"""
    return hashlib.sha256(canonicaliser(obj)).hexdigest()
