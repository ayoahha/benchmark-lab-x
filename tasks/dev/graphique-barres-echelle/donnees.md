# Données et spécification du graphique

## Données

Chiffre d'affaires par gamme de produits, exercice 2026, en milliers d'euros.

| Ordre | Catégorie | Valeur |
| ---: | --- | ---: |
| 1 | Outillage | 320 |
| 2 | Peinture | 280 |
| 3 | Quincaillerie | 520 |
| 4 | Jardin | 400 |
| 5 | Éclairage | 240 |

Maximum observé sur la période, toutes gammes confondues : **520**.

## Spécification du graphique

**Canevas** : largeur 800, hauteur 500.

**Zone de tracé** : les barres reposent sur la ligne `y = 450` et montent vers le haut. La zone de tracé fait **400 pixels de haut**, de `y = 50` à `y = 450`.

**Axe des valeurs** : l'axe part de **200** (ligne de base, `y = 450`) et va jusqu'à **600** (haut de la zone, `y = 50`). Ces bornes sont imposées. Elles ne se déduisent pas des données. Toute valeur se lit relativement à ces deux bornes.

**Barres** : cinq barres, largeur 80 pixels chacune, dans l'ordre du tableau de gauche à droite. La première commence à `x = 100`, écart de 130 pixels entre deux débuts de barre consécutifs.

**Palette imposée**, une couleur par catégorie, dans l'ordre du tableau :

| Ordre | Catégorie | Couleur |
| ---: | --- | --- |
| 1 | Outillage | `#1f77b4` |
| 2 | Peinture | `#d62728` |
| 3 | Quincaillerie | `#2ca02c` |
| 4 | Jardin | `#ff7f0e` |
| 5 | Éclairage | `#9467bd` |

Aucune autre couleur que celles-ci n'est autorisée pour les barres.

**Fond** : blanc.

**Étiquettes** : le nom de chaque catégorie sous sa barre, en noir. Les étiquettes ne comptent pas dans la vérification des couleurs de barres.
