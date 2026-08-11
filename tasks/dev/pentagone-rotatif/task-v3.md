# pentagone-rotatif : task-v3

- **Cohorte** : exposée
- **Régime de confidentialité** : exposé
- **Statut** : en qualification, hors catalogue noté
- **Domaine d’usage** : visuel et simulation
- **Scénario d’usage** : produire une simulation déterministe interrogeable à des instants arbitraires
- **Mode d’exécution** : direct
- **Stabilité** : générative, six runs, quatrième meilleur
- **Vérification** : `verify-v5`, cinq cartes de score indépendantes
- **Protocole** : `benchmark-lab-x/protocol/v2`
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
> Le vérificateur dispose d’un garde-fou de 180 secondes par carte de score. Un dépassement rend la carte inobservable avec l’état `UNKNOWN` ; il ne devient ni un niveau zéro ni un critère de départage.
>
> Sortie : uniquement le code HTML, entre les balises `<html>` et `</html>`. Aucun texte avant ou après, aucun bloc de code markdown.

## Résultat attendu

Une page dont `simulate(t)` reproduit la trajectoire du système, aussi longtemps que la précision de son implémentation le permet.

## Cartes de score

Un artefact collecté est noté séparément sur cinq cartes. Un échec sur une carte ne réécrit pas une mesure déjà obtenue sur une autre.

| Identifiant | Structure | Prédicats |
|---|---|---|
| `pentagone-api` | binaire | page exploitable et valeurs numériques finies aux instants requis |
| `pentagone-determinisme` | binaire | répétition exacte et indépendance à l’ordre des appels |
| `pentagone-confinement-court` | 4 niveaux | état initial, confinement jusqu’à 2, 10 et 20 secondes |
| `pentagone-precision-24s` | 37 niveaux | tolérances de `1e+2` à `1e-16` m à 24 secondes |
| `pentagone-horizons-longs` | 6 niveaux | confinement et précision à 35, 55 et 75 secondes |

Une carte binaire retient `PASS` si au moins quatre des six runs valent `PASS`. Une carte à niveaux retient le quatrième meilleur niveau, libellé « niveau franchi dans au moins quatre runs sur six ». Les six valeurs sont publiées. Aucun profil global n’est calculé.

## Causes structurées minimales

| Cause | Portée |
|---|---|
| `OUTPUT_NO_PAGE` | carte API |
| `API_MISSING_OR_INVALID` | carte API |
| `NON_DETERMINISTIC` | carte déterminisme |
| `ORDER_DEPENDENT` | carte déterminisme |
| `VERIFY_TIMEOUT` | carte en cours uniquement |
| `OUT_OF_BOUNDS` | carte de confinement concernée |
| `PRECISION_THRESHOLD_FAILED` | carte de précision concernée |
| `UPSTREAM_CARD_UNOBSERVABLE` | carte qui ne peut pas observer son prédicat |

## Politique de collecte

- six artefacts de collecte par candidat
- un seul résultat scoreable par run
- trois tentatives au maximum, appel initial compris
- reprise automatique limitée à `HTTP_429`, `HTTP_503` et `TRANSPORT_NO_HTTP_RESPONSE`
- reprise avant tout résultat scoreable, sur la même route, avec le même prompt, le même budget et les mêmes paramètres
- aucun fallback ni résolution d’alias après le gel du lock
- `ROUTE_METADATA_UNREACHABLE` bloque le préflight et ne crée aucune tentative
- toute tentative payante entre dans le plafond d’inférence de la campagne

## Mécanisme discriminant

- **Bon chemin** : intégration événementielle, collision avec une paroi en rotation et précision suffisante
- **Échecs attendus** : API partielle, dépendance à l’ordre, pas fixe, paroi immobile, collision grossière ou arrondi précoce
- **Séparation** : interface, déterminisme, confinement court, précision à 24 secondes et horizons longs restent cinq mesures distinctes

## Vérification et qualification

- vérificateur : `tools/verifier_pentagone_v5.py`
- oracle : `tools/oracle_pentagone.py`
- cache figé : `tasks/dev/pentagone-rotatif/oracle-cache.json`
- garde-fou : 180 secondes de temps mural par carte
- moteur : Playwright 1.62.0 et Chromium épinglé par l’environnement de mesure

Chaque score est écrit dans un reçu immuable lié au reçu de collecte, à la réponse, à `verify-v5` et au contexte de mesure. Le rapporteur consomme ces reçus sans lancer Chromium.

La qualification R-016 exige, pour chaque prédicat, un témoin positif et un témoin négatif produits sans accès au vérificateur. Les témoins historiques ne satisfont pas cette condition. La carte reste donc en `HOLD` jusqu’à un reçu de couverture indépendant, complet et lié aux empreintes de `task-v3` et `verify-v5`.

## Revue humaine

La note ne reçoit aucune correction humaine. Avant publication, l’audit R-026 contrôle en aveugle les verdicts et niveaux produits par le code. Un désaccord invalide la page et impose une nouvelle version du vérificateur.
