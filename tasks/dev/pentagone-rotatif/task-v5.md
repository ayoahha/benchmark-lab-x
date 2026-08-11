---
style_gate: pass
---

# pentagone-rotatif : task-v5

- **Cohorte** : exposée
- **Régime de confidentialité** : exposé
- **Statut** : brouillon non officiel, hors qualification et hors catalogue noté
- **Domaine d’usage** : visuel et simulation
- **Scénario d’usage** : produire une simulation déterministe interrogeable à des instants arbitraires
- **Mode d’exécution** : direct
- **Stabilité** : générative, six runs, quatrième meilleur
- **Vérification candidate** : `verify-v7`, cinq axes
- **Contrat de vérification** : [`docs/VERIFY-V7.md`](../../../docs/VERIFY-V7.md)
- **Protocole** : `benchmark-lab-x/protocol/v2`
- **Limite d’exécution de l’artefact** : absente, non qualifiée et non approuvée
- **Langue** : français

## Objectif utilisateur

Simuler exactement une balle qui rebondit dans un pentagone en rotation, et pouvoir donner sa position à n’importe quel instant.

## Contexte et fichiers visibles

- `donnees.md` : géométrie, état initial et lois du système

Les données sont entièrement synthétiques. Le manifeste de campagne porte la liste fermée et l’empreinte de chaque fichier visible.

## Consignes visibles par le modèle (verbatim)

> À partir de `donnees.md`, produis une page HTML autonome qui simule le système décrit.
>
> La page doit définir une fonction globale `simulate(t)` qui rend la position de la balle à l’instant `t`, exprimé en secondes depuis le départ, sous la forme d’un tableau `[x, y]` de deux nombres JavaScript finis. Cette fonction sera appelée pour des instants que nous choisissons entre 0 et 90 secondes, dans un ordre quelconque, et elle doit rendre la même valeur quel que soit l’ordre des appels.
>
> La page doit aussi dessiner, dans un élément `<canvas>` de 800 par 500, le pentagone et la balle tels qu’ils se trouvent à l’instant 0.
>
> Interdits : aucun accès réseau, aucune bibliothèque externe, aucune horloge, aucun tirage aléatoire. Deux exécutions successives de la page doivent produire exactement les mêmes valeurs.
>
> Sortie : uniquement le code HTML, entre les balises `<html>` et `</html>`. Aucun texte avant ou après, aucun bloc de code markdown.

Aucune valeur de limite n’apparaît aujourd’hui dans les consignes candidat-visibles, car elle n’est pas qualifiée. Cette absence bloque toute acquisition task-v5 et n’autorise aucune limite cachée. Avant tout statut officiel, le bloc verbatim ci-dessus doit intégrer la valeur approuvée, son unité, le début et la fin du budget, ainsi que la conséquence `ARTIFACT_EXECUTION_LIMIT`, puis être lié au hash exact de task-v5. Un ajout après le gel de la tâche incrémente task-vN selon R-008.

## Résultat attendu

Une page dont `simulate(t)` reproduit la trajectoire du système, aussi longtemps que la précision de son implémentation le permet.

## Axes

Une acquisition alimente cinq unités d’axe. Les unités partagent l’acquisition et référencent tout incident commun sans le compter comme cinq pannes.

| Identifiant | Structure | Prédicats |
|---|---|---|
| `pentagone-api` | binaire | page exploitable et valeurs numériques finies aux instants requis |
| `pentagone-determinisme` | binaire | répétition exacte et indépendance à l’ordre des appels |
| `pentagone-confinement-court` | 4 niveaux | état initial, confinement jusqu’à 2, 10 et 20 secondes |
| `pentagone-precision-24s` | 37 niveaux | tolérances de `1e+2` à `1e-16` m à 24 secondes |
| `pentagone-horizons-longs` | 5 niveaux | confinement à 35, 55 et 75 secondes ; précision à 35 et 55 secondes |

La position à 75 secondes reste un diagnostic. Elle ne produit aucun prédicat de précision et ne modifie pas le niveau : les deux références numériques disponibles ne s’accordent pas sous la tolérance historique à cet horizon.

Une unité binaire `SCORED` porte `PASS` ou `FAIL`. Une unité à niveaux `SCORED` porte le niveau atteint. L’agrégation retient `PASS` si au moins quatre des six runs portent `PASS`, ou le quatrième meilleur niveau pour un axe à niveaux. Les six valeurs et le dénominateur `SCORED` sont publiés. Aucun profil global n’est calculé.

Les états de mesure, classes causales, verdicts et métriques suivent exclusivement les [§3 et §7 du contrat verify-v7](../../../docs/VERIFY-V7.md#3-modèle-de-mesure). Une panne fournisseur ne devient aucun verdict d’axe. Un `HARNESS_ERROR` reste une couverture manquante et maintient le classement concerné au statut provisoire.

## Adaptateur de modalité HTML

Le contrat d’admission accepte uniquement les octets d’un document HTML autonome conforme à l’enveloppe candidat-visible. L’admission vérifie l’encodage, l’unicité du document et l’absence d’octets hors de l’enveloppe. Son échec donne `ARTIFACT_INVALID` une seule fois pour l’acquisition.

Après admission, l’absence ou l’invalidité de `simulate(t)`, une valeur non finie, une trajectoire fausse ou un dessin incorrect reste un résultat fonctionnel de l’axe concerné. Ces défauts produisent un verdict `FAIL` sous `SCORED` lorsque l’évaluation se termine.

Chaque unité d’axe exécute les mêmes octets candidats dans une instance propre, après son propre reçu `HARNESS_READY`. Le chargement du document, son initialisation et l’évaluation de cette unité entrent dans son budget artefact. Un incident de route ou d’admission reste lié une seule fois à l’acquisition ; un incident apparu dans une instance d’axe reste lié à cette unité. Le watchdog et le teardown du harnais suivent l’enveloppe distincte définie par verify-v7.

## Mécanisme discriminant

- **Bon chemin** : intégration événementielle, collision avec une paroi en rotation et précision suffisante
- **Échecs attendus** : API partielle, dépendance à l’ordre, pas fixe, paroi immobile, collision grossière ou arrondi précoce
- **Séparation** : interface, déterminisme, confinement court, précision à 24 secondes et horizons longs restent cinq mesures distinctes

## Qualification

La carte reste `brouillon` et non officielle. La valeur numérique de `ARTIFACT_EXECUTION_LIMIT` ne figure pas encore dans ce document : elle sera dérivée du besoin d’usage, de témoins indépendants et de la variabilité mesurée dans un environnement épinglé, puis approuvée et divulguée selon le [§6 de verify-v7](../../../docs/VERIFY-V7.md#6-qualification-de-la-limite-numérique).

Les anciens artefacts de modèles ne peuvent intervenir qu’après le gel de cette valeur, comme stress tests. Ils ne servent ni à la choisir ni à la renoter dans cette tranche.

La qualification exige encore le noyau et l’adaptateur implémentés, leurs reçus de couverture, la limite approuvée et le canari OpenRouter de chaque configuration officielle. Aucun de ces éléments n’est produit par cette tranche documentaire.

## Historique et renotation expérimentale

Task-v4, ses locks, reçus et résultats restent inchangés. Une future vue rétroactive ou renotation expérimentale suit le [§8 de verify-v7](../../../docs/VERIFY-V7.md#8-vue-rétroactive-versionnée), produit de nouveaux reçus identifiés et conserve les sources intactes.

Une acquisition historique non produite sous le contenu candidat-visible et le hash exacts de task-v5 ne devient jamais une preuve officielle task-v5.

## Revue humaine

La note ne reçoit aucune correction humaine. Avant publication, l’audit contrôle en aveugle les verdicts et niveaux produits par l’instrument. Un désaccord invalide l’axe et impose une nouvelle version du vérificateur avec sa propre couverture.
