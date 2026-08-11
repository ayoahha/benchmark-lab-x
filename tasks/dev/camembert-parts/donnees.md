# Données et spécification du graphique

## Données

Répartition du chiffre d'affaires par canal de vente, exercice 2026, en milliers d'euros.

| Ordre | Canal | Valeur |
| ---: | --- | ---: |
| 1 | Magasin | 550 |
| 2 | Web | 180 |
| 3 | Grossistes | 120 |
| 4 | Marchés | 80 |
| 5 | Téléphone | 45 |
| 6 | Export | 25 |

Les pourcentages ne sont pas fournis. Ils se déduisent des valeurs.

## Spécification du graphique

**Canevas** : largeur 800, hauteur 500. Fond blanc.

**Anneau** : un anneau centré en `(400, 250)`, de rayon extérieur **180** et de rayon intérieur **90**. Le disque central reste blanc.

**Parts** : chaque canal occupe une part de l'anneau **proportionnelle à sa valeur**. La première part commence exactement **en haut de l'anneau** (position midi) et les parts se succèdent **dans le sens des aiguilles d'une montre**, dans l'ordre du tableau.

**Palette imposée**, une couleur par canal, dans l'ordre du tableau :

| Ordre | Canal | Couleur |
| ---: | --- | --- |
| 1 | Magasin | `#1f77b4` |
| 2 | Web | `#d62728` |
| 3 | Grossistes | `#2ca02c` |
| 4 | Marchés | `#ff7f0e` |
| 5 | Téléphone | `#9467bd` |
| 6 | Export | `#8c564b` |

Aucune autre couleur que celles-ci n'est autorisée pour les parts.

**Aucun trait de séparation** entre les parts : elles se touchent directement.

**Pas d'étiquettes, pas de légende, pas de titre.** L'anneau seul.
