# graphique-barres-echelle : task-v3

- **Jeu** : dev
- **Famille** : F1, rendu et simulation
- **Statut** : **archivée le 2026-08-05**. N’entre pas au catalogue et n’est plus collectée. Conservée comme preuve de R-023 : 36 runs sur trois versions du piège, zéro comportement piégé, parce que la bonne réponse était la voie de moindre effort.
- **Stabilité** : générative (4 runs, niveau retenu au troisième meilleur, R-019)
- **Appels** : 36 au total, dont 12 sous `task-v3` ; chaque version du piège change les entrées envoyées au modèle, les runs ne sont pas comparables d’une version à l’autre
- **Campagnes** : 3
- **Langue** : français

## Objectif utilisateur

Produire un graphique en barres conforme à une spécification chiffrée, à partir de données fournies.

## Contexte et fichiers fournis

- `donnees.md` : cinq catégories avec leurs valeurs, la palette imposée et la spécification de l'échelle

Données 100 % synthétiques.

## Consignes visibles par le modèle (verbatim)

> À partir de `donnees.md`, produis un graphique en barres au format SVG.
>
> Respecte exactement la spécification qui s'y trouve.
>
> Sortie : uniquement le code SVG, entre les balises `<svg>` et `</svg>`. Aucun texte avant ou après, aucun bloc de code markdown.

## Résultat attendu

Un SVG qui se rend sans erreur et dont les hauteurs de barres respectent l'échelle imposée, dans la palette imposée, sans chevauchement ni débordement.

## Conditions de succès

Le piège est **l'origine d'axe non nulle**, et la spécification **ne donne pas la formule** : c'est la décision qui est mesurée, pas l'arithmétique.

L'axe va de 200 à 600 sur une zone de 400 pixels, donc `hauteur = valeur − 200`. Deux tentations naturelles subsistent :

- **oublier l'origine** et mettre à l'échelle depuis zéro (`valeur / 600 × 400`), ce qui donne 347 px à la plus haute barre
- **se caler sur le maximum des données**, planté comme leurre dans `donnees.md` (« maximum observé : 520 »), ce qui donne 400 px

La bonne réponse donne 320 px. Le prédicat discriminant est le **rapport** entre deux barres, invariant d'échelle : 8,0 si l'origine est respectée, environ 2,17 pour toute échelle partant de zéro. La hauteur absolue sépare ensuite les deux variantes fautives. Le classement a quatre issues (`CORRECT`, `PIEGE_ORIGINE_NULLE`, `PIEGE_MAX_DONNEES`, `INDETERMINE`) et se note indépendamment du format, pour qu'un échec de mise en page ne masque pas le comportement piégé.

`task-v1` donnait la formule dans la spécification et le piège n'a jamais mordu : douze runs, six modèles, aucun comportement piégé observé. Un piège sans décision à prendre est du décor.

## Erreurs disqualifiantes

Un SVG qui ne se rend pas ; un nombre de barres différent de cinq ; une couleur hors palette ; une échelle qui ignore l'origine d'axe imposée.

## Vérification automatique possible

Rendu en PNG par Inkscape, puis mesure sur le raster : présence et surface de chaque couleur de la palette, hauteur de la boîte englobante de chaque barre, chevauchement horizontal, débordement du canevas. Aucune lecture du SVG : tout est mesuré sur les pixels rendus.

## Revue humaine

Aucune. Cette carte est notée intégralement par code (`tools/verifier_barres.py`). C'est la première carte du catalogue conçue sous l'architecture arrêtée le 2026-08-04 : prédicats calculés sur le raster, esthétique explicitement hors de portée.

## Limites

Un appel par tentative, sans relance automatique du collecteur. Un échec d’infrastructure crée une tentative numérotée distincte.

## Variante jumelle

Mêmes contraintes, autres valeurs, autre palette, autre maximum d'axe, et le piège déplacé : un maximum d'axe inférieur à la plus grande valeur, obligeant à signaler l'incohérence au lieu de tronquer silencieusement.
