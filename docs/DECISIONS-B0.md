---
title: "Fiche de décisions B0 pour une nouvelle campagne V0"
date: 2026-08-08
status: "B0-01 à B0-09 approuvées, estimation B0-09 réapprouvée, B0-10 en HOLD"
style_gate: pass
---

# Fiche de décisions B0

## Verdict

`GO` sur la préparation locale de B1 à B5 et sur le gel local du lock. `HOLD` sur B0-10, toute collecte, tout appel payant et toute modification du plafond de `55 $`.

Cette fiche transforme les dix décisions ouvertes du plan en un paquet cohérent. Ayo a approuvé B0-01 à B0-09 le 8 août 2026, puis l'estimation B0-09 révisée à `31,812500 $`. L'autorisation couvre la préparation locale et le lock, sans Chromium, commit, push ni publication. Elle n'autorise aucune collecte.

## Base de preuve

| Source | SHA-256 | Usage |
|---|---|---|
| `docs/PLAN-DEMO-PREV0.md` | `b4e9961aa558042fedb369254d7b38305f2fc854eb0016b07630e14ddb5dcc5c` | portes A et B |
| `docs/PROMPT-REPRISE-GPT56.md` | `7988e447ca42e5f662bbdc3e79a5fd6de9c12b6672a06f059ab33ae0c6744495` | défauts établis et mission |
| `docs/RULES.md` | `247476008add276497cf08397859045cc46e18cb7a70e897564bc556dcc232f9` | règles de mesure |
| `tasks/dev/pentagone-rotatif/task.md` | `d918a0d693feb6d497d1170f83982df3865303be128c1db81facd275d081c3e3` | contrat historique |
| `runs/2026-08-06-reference-v2/results-data.json` | `4185a4ab9b4512f93bae0b998a939de0eff01151c00a9c01c789b757b62eedfd` | résultats et coûts historiques |
| `runs/2026-08-06-reference-v2/routes.json` | `5feae661b3050916973c40ca7212fe13443c1ca87e9e6471b3cc2eda7deae468` | routes historiques |
| `runs/2026-08-06-reference-v2/campaign.toml` | `6627752ba38268fe0837e63803fe12da3bb8287680daa66367198f5ca819c601` | panel et plafond historiques |

## Décisions recommandées

Chaque ligne exige un accord explicite d'Ayo. L'approbation d'une ligne n'autorise aucune dépense.

| ID | Sujet | Décision recommandée | Conséquence versionnée |
|---|---|---|---|
| `B0-01` | Interface et float64 | Conserver `simulate(t) -> [x, y]` avec deux nombres JavaScript. Arrêter l'axe de précision à `1e-16`. Retirer les seuils `3e-17` et `1e-17`. | `verify-v4` |
| `B0-02` | Horizons longs | Publier `C35/E35`, `C55/E55` et `C75/E75` dans une carte de notation séparée. Leur mesure ne dépend plus du passage de la précision à 24 s. | `verify-v4` et nouvelle carte |
| `B0-03` | Temps | Conserver 180 s comme garde-fou de l'instrument, déclaré dans la tâche et le protocole. Un dépassement produit `UNKNOWN` avec `cause_code=VERIFY_TIMEOUT` pour la carte en cours. La durée reste un diagnostic d'efficacité. | `task-v3`, `verify-v4`, R-013 et protocole v2 |
| `B0-04` | Axes publiés | Créer cinq cartes de notation : API, déterminisme, confinement court, précision à 24 s et horizons longs. Elles réutilisent le même artefact collecté pour un candidat et un run. Chaque carte porte son état, son verdict ou son niveau et son reçu de score. Aucun profil global en V0. | R-013, R-020, R-007, `verify-v4`, protocole v2 |
| `B0-05` | Scalaire | Pour chaque carte à niveaux, retenir le quatrième meilleur de six runs, libellé « niveau franchi dans au moins quatre runs sur six ». Pour une carte binaire, ordonner `PASS > FAIL` et retenir le quatrième meilleur : `PASS` exige au moins quatre PASS, sinon le verdict retenu est `FAIL`. Publier les six valeurs et conserver les ex aequo. | révision versionnée de R-019 et R-020, protocole v2 |
| `B0-06` | Nombre de runs | Six runs par candidat. Avec le panel historique de 19 candidats, le plan contient 114 artefacts de collecte, chacun noté par les cinq cartes. | révision versionnée de R-019, `campaign.toml`, protocole v2 |
| `B0-07` | Tentatives | Trois tentatives au maximum par run, soit l'appel initial et deux reprises. Une reprise reste limitée à `HTTP_429`, `HTTP_503` ou `TRANSPORT_NO_HTTP_RESPONSE`, avant tout résultat `SCORED`, sur la même route et sans lecture du contenu candidat. Aucun changement de contenu, budget ou provider. | `task-v3`, protocole v2 |
| `B0-08` | Routes | Générer et valider le lock résolu avant le premier appel, puis l'utiliser comme source directe d'exécution. `ROUTE_METADATA_UNREACHABLE` bloque le préflight et ne crée aucune tentative. Aucun fallback. Une route conforme absente donne `INELIGIBLE` avant appel. Une identité servie différente place la campagne en `HOLD`. | lock et nouvelles empreintes |
| `B0-09` | Dépense | Estimation approuvée : `31,812500 $` d'inférence. Plafond ferme : `55,00 $`, toutes tentatives comprises. Toute nouvelle modification du panel ou des prix impose un nouveau calcul et une nouvelle approbation. | plafond de campagne |
| `B0-10` | Nouvelle campagne | Maintenir les appels payants en `HOLD`. Une autorisation distincte sera demandée après le passage de B1 à B5. | aucune collecte à ce stade |

## Justification des choix

### Interface numérique

L'interface impose déjà deux nombres JavaScript. Cinq runs plafonnent au niveau 43 avec le même écart `5.1178986216292804e-17` et la frontière `P3e-17_precision_ref`. Le seuil `1e-16` est le dernier seuil franchi dans ces runs. Les deux seuils suivants ne sont pas démontrés discriminants avec ce contrat.

Le passage à une représentation décimale explicite mesurerait aussi l'obéissance à un nouveau format. Cette option reste disponible pour une version ultérieure si un usage réel exige une précision supérieure au float64.

### Axes

L'échelle historique combine plusieurs mécanismes dans un préfixe unique. La séparation proposée crée cinq cartes de notation qui réutilisent le même artefact de collecte :

1. présence et validité de l'API
2. déterminisme et indépendance à l'ordre des appels
3. confinement à 2, 10 et 20 secondes
4. précision à 24 secondes, de `1e+2` à `1e-16`
5. confinement et précision à 35, 55 et 75 secondes

Chaque triplet `(carte, candidat, run)` porte un état terminal unique de R-013. Une absence d'API donne un échec scoreable sur la carte API et `UNKNOWN` sur les cartes qui ne peuvent rien observer. Un `UNKNOWN` bloque le classement de la carte concernée. Il ne réécrit pas les cartes déjà notées. La V0 ne regroupe pas ces cartes dans un profil au sens de R-007.

Ce schéma exige une révision explicite et versionnée de R-013, R-019 et R-020 dans `docs/RULES.md`. Le protocole v2 ne peut pas contredire seul ces règles. La page devra aussi respecter les contraintes d'interface déjà décidées. La forme exacte relève de B1 à B5.

### Six runs et scalaire par axe

Quatre runs donnent un titre très sensible à une seule sortie. Six runs limitent ce poids sans doubler le coût de la campagne. Le quatrième meilleur signifie directement que le niveau a été franchi dans au moins quatre runs sur six. Pour les cartes binaires, quatre PASS ou plus donnent `PASS` ; zéro à trois PASS donnent `FAIL`.

Ce scalaire décrit une répétabilité opérationnelle sur les runs planifiés. Il ne produit aucune inférence statistique générale. Les distributions complètes restent opposables.

### Temps et causes

Le garde-fou de 180 s protège la machine contre une page bloquante. Il ne devient plus un niveau 0 de correction. Les mécanismes suivants reçoivent des causes distinctes par carte :

| Mécanisme | État ou résultat recommandé | `cause_code` minimal |
|---|---|---|
| aucune page exploitable | `SCORED`, niveau 0 sur l'axe API | `OUTPUT_NO_PAGE` |
| API absente ou invalide | `SCORED`, niveau 0 sur l'axe API | `API_MISSING_OR_INVALID` |
| non-déterminisme | résultat de l'axe déterminisme | `NON_DETERMINISTIC` |
| dépendance à l'ordre | résultat de l'axe déterminisme | `ORDER_DEPENDENT` |
| dépassement du garde-fou | `UNKNOWN` sur la correction | `VERIFY_TIMEOUT` |
| sortie hors confinement | résultat de l'axe concerné | `OUT_OF_BOUNDS` |
| seuil de précision échoué | niveau de l'axe concerné | `PRECISION_THRESHOLD_FAILED` |

Les cinq valeurs d'état de R-013 restent inchangées. Leur unité devient le triplet `(carte, candidat, run)`. `UNKNOWN` bloque toute publication validée de la carte concernée. `docs/RULES.md` et le protocole v2 fixent le couple `etat` et `cause_code` avant implémentation.

## Estimation budgétaire

### Faits historiques

La campagne `reference-v2` contient :

- 19 candidats
- 76 runs attendus et retenus
- 84 tentatives enregistrées
- 83 prompts ayant atteint un fournisseur
- 76 reçus `meta.json` portant un coût
- `19,399129918 $` de coût d'inférence consigné

Les huit tentatives non retenues ne portent aucun coût dans les reçus historiques. Cette absence ne prouve pas une facturation nulle côté fournisseur.

### Projection initiale

Pour six runs et le même panel :

```text
base linéaire = 19,399129918 × 6 / 4 = 29,098694877 $
facteur historique de prompts = 83 / 76 = 1,092105
estimation de travail = 29,098694877 × 1,092105 = 31,778838 $
```

| Runs par candidat | Runs attendus | Projection linéaire | Projection avec le facteur de prompts | Plafond indicatif |
|---:|---:|---:|---:|---:|
| 4 | 76 | `19,3991 $` | `21,1859 $` | `35 $` |
| **6** | **114** | **`29,0987 $`** | **`31,7788 $`** | **`55 $`** |
| 8 | 152 | `38,7983 $` | `42,3718 $` | `70 $` |

Le plafond de `55 $` reprend le plafond historique de `35 $`, l'augmente de 50 % pour les deux runs supplémentaires, puis l'arrondit au-dessus à `55 $`.

### Réestimation figée avant le lock

Le snapshot public du 8 août 2026, SHA-256 `a066652cc46a53a307a7e96da86fc334c898523ae10b031c6786fba6b078b169`, résout les 19 alias sur 13 modèles et applique les tarifs observés aux jetons historiques. La même méthode donne `31,812500 $`, soit `+0,033662 $` par rapport à la projection initiale.

Ayo a approuvé cette estimation révisée le 8 août 2026. Le plafond reste `55 $`, avec une marge de `23,187500 $`. Le snapshot approuvé conserve l'empreinte du snapshot source et la portée locale de l'autorisation.

Cette projection suppose le même panel, une longueur de sortie comparable et des prix proches de ceux observés le 6 août 2026. Elle ne constitue pas un devis fournisseur. Avant le gel de campagne, le lock devra consigner les prix de chaque route. La documentation officielle OpenRouter indique que son API Models expose les prix en dollars par jeton, requête ou unité : <https://openrouter.ai/docs/api/api-reference/models/get-models>.

Si de nouveaux crédits doivent être achetés, OpenRouter annonce actuellement des frais de recharge de 5,5 %, avec un minimum de `0,80 $` : <https://openrouter.ai/docs/faq>. Sur une recharge de `55 $`, 5,5 % représentent `3,03 $`. Ces frais éventuels et les taxes restent hors du plafond d'inférence.

### Garde budgétaire recommandé

Le lanceur maintient un registre durable et atomique `coût engagé + coût réservé`. Avant tout envoi, il réserve le coût maximal préenregistré de la tentative sous verrou. La condition de départ est `engagé + réservé + maximum de la nouvelle tentative <= 55 $`, y compris avec deux travailleurs concurrents.

Après réception d'un coût opposable, la réservation devient le coût engagé réel et le solde est libéré. Sans télémétrie opposable, la réservation maximale reste consommée et la campagne passe en `HOLD`. Un prix absent, une modification du panel ou une réservation impossible bloque l'envoi.

Atteindre le plafond avant les 114 runs ne déclenche aucune extension automatique. Ayo décide alors d'un nouveau plafond ou arrête la campagne. Le maximum théorique de trois tentatives sur 114 runs est de 342 prompts ; le plafond financier reste prioritaire.

## Versions minimales après approbation

| Artefact | Version proposée | Motif |
|---|---|---|
| règles | révision datée de R-013, R-019 et R-020 | unité par carte, six runs et agrégation |
| tâche | `task-v3` | garde-fou temporel déclaré et politique de tentatives |
| vérificateur | `verify-v5` avec cinq cartes de score | axes, seuils, horizons, timeout et contrôle d'ordre en contexte neuf |
| protocole | `benchmark-lab-x/protocol/v2` | six runs, quatrième meilleur, causes et reprises |
| campagne | nouveau dossier daté | aucun ajout à `reference-v2` |
| contexte | nouveau `measurement_context_hash` | comparabilité distincte |
| exécution | nouveaux `execution_manifest_hash` | lock résolu par candidat |

## Portes après approbation B0

L'approbation des décisions B0 autoriserait uniquement la préparation locale de B1 à B5 : contrat versionné, instrument corrigé, lock, témoins et préflight sans réseau payant.

La collecte resterait bloquée jusqu'aux preuves cumulatives suivantes :

1. chaque palier possède un témoin positif et négatif indépendant
2. chaque axe est monotone et atteignable
3. les causes structurées passent les fixtures locales
4. un `UNKNOWN` bloque seulement la carte concernée et aucune valeur manquante ne devient un score
5. le lock pilote réellement l'exécution
6. le registre budgétaire résiste à deux réservations concurrentes et à une télémétrie absente
7. le rapporteur consomme les reçus figés sans rejouer les témoins
8. toutes les empreintes sont stables
9. Ayo donne un GO payant distinct avec le plafond exact

R-016 exige encore une qualification dynamique des témoins indépendants sous `verify-v5`. Un même témoin peut couvrir plusieurs prédicats, mais chaque prédicat doit disposer d'une preuve positive et négative avec provenance.

## Approbation B0-09 consignée

> J’approuve l’estimation B0-09 révisée à 31,812500 $, avec un plafond inchangé de 55 $. J’autorise la mise à jour locale de B0-09 et la production du brouillon et du lock final, sans Chromium, collecte, commit, push ni publication. B0-10 reste en HOLD.
