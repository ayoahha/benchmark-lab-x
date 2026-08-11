# camembert-parts : task-v1

- **Jeu** : dev
- **Famille** : F1, rendu et simulation
- **Statut** : retirée de la collecte, rôle plancher repris par la variante jumelle `camembert-arc-majeur`. La description publique détaillée a consommé cette carte sous R-017. La campagne du 2026-08-04 viole par ailleurs R-003, R-015 et R-025.
- **Stabilité** : générative (4 runs, niveau retenu au troisième meilleur, R-019)
- **Appels** : 20
- **Campagnes** : 1 (`2026-08-04-camembert`)
- **Langue** : français

## Objectif utilisateur

Produire un anneau de répartition conforme à une spécification géométrique, à partir de valeurs brutes.

## Contexte et fichiers fournis

- `donnees.md` : six canaux avec leurs valeurs brutes, la palette imposée et la géométrie de l'anneau

Données 100 % synthétiques.

## Consignes visibles par le modèle (verbatim)

> À partir de `donnees.md`, produis le graphique au format SVG.
>
> Respecte exactement la spécification qui s'y trouve.
>
> Sortie : uniquement le code SVG, entre les balises `<svg>` et `</svg>`. Aucun texte avant ou après, aucun bloc de code markdown.

## Résultat attendu

Un anneau dont les six parts couvrent chacune l'angle exact correspondant à sa proportion, commençant à midi et se succédant dans le sens horaire.

## Conditions de succès

Cette carte empile quatre difficultés, et c'est délibéré : elle doit rester hors de portée d'un modèle frontière sur au moins un niveau, sinon elle ne sert pas à noter.

1. **Dériver les proportions** : les pourcentages ne sont pas donnés, seulement les valeurs brutes. Total 1000.
2. **Convertir en angles** : 550 → 198°, 180 → 64,8°, 120 → 43,2°, 80 → 28,8°, 45 → 16,2°, 25 → 9°.
3. **Produire des chemins d'arc corrects** : chaque part est un secteur d'anneau, donc deux arcs et deux segments radiaux, avec des points calculés par trigonométrie depuis un départ à midi et une progression horaire.
4. **Le `large-arc-flag`** : la première part fait 198°, donc plus d'un demi-tour. Son arc exige `large-arc-flag = 1`. Le laisser à 0 produit un arc retourné et une part visuellement inversée. C'est l'erreur classique des chemins d'arc SVG, et elle est spectaculaire au rendu.

La difficulté n'est pas cumulative par hasard : un modèle peut réussir 1 et 2 et échouer sur 3 ou 4. Le vérificateur mesure chaque niveau séparément pour que la note soit un gradient et non un verdict binaire.

## Erreurs disqualifiantes

Un SVG qui ne se rend pas ; un nombre de couleurs différent de six ; une couleur hors palette ; un anneau absent (disque plein ou trou de mauvais rayon).

## Vérification automatique possible

Rendu en PNG par le Chromium épinglé, puis mesure sur le raster : pour chaque couleur de la palette, l'ensemble des angles couverts autour du centre, l'angle de départ, l'étendue angulaire, et le rayon des pixels colorés. Aucune lecture du SVG.

## Revue humaine

Aucune. Notation intégrale par code (`tools/verifier_camembert.py`).

## Limites

Un appel par tentative, sans relance automatique du collecteur. Un échec d’infrastructure crée une tentative numérotée distincte.

## Variante jumelle

`camembert-arc-majeur` conserve la compétence et le rôle plancher avec d’autres valeurs et un arc majeur différent. Sa géométrie exacte et ses témoins restent à définir puis à calibrer avant toute collecte. Un seul camembert ne peut pas contenir deux parts supérieures à 180°.
