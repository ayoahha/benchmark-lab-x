---
style_gate: pass
---

# Contrat task-v5 / verify-v7

Version contractuelle 7, 11 août 2026

Statut : **candidat, brouillon non officiel**

## 1. Autorité et portée

Ce document est la source de vérité unique du modèle prospectif task-v5 / verify-v7. Il gouverne les états de mesure, les classes causales, les verdicts d’axe, les stades, les budgets, les preuves, les métriques, la vue rétroactive et le canari OpenRouter de cette tranche.

Les règles générales de Benchmark Lab-X restent dans [RULES](RULES.md). La carte [pentagone-rotatif task-v5](../tasks/dev/pentagone-rotatif/task-v5.md) porte uniquement le contenu visible par le candidat et les choix propres à cette modalité.

Ce contrat s’applique prospectivement. Il ne modifie aucun fichier task-v4, reçu, lock ou résultat historique. Cette tranche ne produit aucune acquisition, notation, renotation, vue rétroactive ni preuve d’exécution.

## 2. Unités et incidents

Une **acquisition** représente une configuration et un run. Une **unité d’axe** représente un axe attendu pour cette acquisition. Le plan verrouillé énumère les acquisitions et unités d’axe requises avant toute exécution.

Un incident possède un identifiant stable, un stade, une portée et les preuves qui soutiennent son attribution :

- portée `ACQUISITION` lorsque l’incident précède les unités d’axe ou les affecte toutes
- portée `AXIS` lorsqu’il apparaît uniquement pendant l’évaluation d’un axe
- liste des unités affectées lorsque plusieurs unités renvoient au même incident

Un même événement causal produit un incident unique. Les unités affectées le référencent ; elles ne le recopient pas comme plusieurs pannes indépendantes.

## 3. Modèle de mesure

Chaque unité d’axe porte trois dimensions distinctes.

| Dimension | Valeurs | Règle |
|---|---|---|
| État de mesure | `SCORED`, `NOT_SCORED` | indique seulement si une mesure d’axe exploitable existe |
| Classe causale | `MEASUREMENT_COMPLETED`, `PROVIDER_FAILURE`, `ARTIFACT_INVALID`, `ARTIFACT_EXECUTION_LIMIT`, `HARNESS_ERROR` | attribue la terminaison à un stade prouvé |
| Verdict d’axe | verdict ou niveau défini par la carte | existe uniquement avec `SCORED` et `MEASUREMENT_COMPLETED` |

`SCORED` est un état de mesure. Ce n’est jamais une classe causale ni un verdict.

### 3.1 Classes causales

| Classe | Définition | Effet métrique |
|---|---|---|
| `MEASUREMENT_COMPLETED` | le harnais a terminé l’évaluation requise et produit un verdict d’axe | unité incluse dans la qualité de l’axe et dans la décision bout-en-bout de son acquisition |
| `PROVIDER_FAILURE` | la route ou le fournisseur épinglé n’a fourni aucun artefact candidat admissible | échec bout-en-bout de la configuration ; aucune mesure de qualité d’axe |
| `ARTIFACT_INVALID` | les octets candidats échouent au contrat d’admission déterministe de la modalité avant tout jugement de qualité | échec bout-en-bout de la configuration ; aucune mesure de qualité d’axe |
| `ARTIFACT_EXECUTION_LIMIT` | le travail imputable à l’artefact dépasse son budget qualifié après `HARNESS_READY` | échec bout-en-bout de la configuration ; aucune mesure de qualité d’axe |
| `HARNESS_ERROR` | le harnais, son environnement, son watchdog, son teardown ou ses preuves ne permettent pas une attribution fiable | aucune pénalisation du modèle ou de la configuration ; couverture manquante |

Un artefact admis qui produit une réponse fonctionnellement fausse reçoit un verdict d’axe `FAIL` sous `SCORED` et `MEASUREMENT_COMPLETED`. `ARTIFACT_INVALID` reste réservé à l’échec du contrat d’admission de la modalité.

Toute unité `NOT_SCORED` omet le verdict d’axe et référence son incident. Toute absence, contradiction ou ambiguïté dans les preuves ferme l’attribution sur `HARNESS_ERROR`. Une classe pénalisante exige toutes ses preuves minimales.

## 4. Noyau commun et adaptateurs de modalité

Le noyau verify-v7 ne dépend ni de HTML, ni d’un navigateur, ni de Chromium. Il orchestre les stades, les événements, les budgets, les incidents et les reçus communs.

Chaque modalité fournit un contrat d’adaptateur versionné qui fixe :

- les octets et interfaces admissibles
- les opérations de chargement, d’initialisation et d’évaluation imputables à l’artefact
- la frontière entre invalidité de l’artefact, verdict fonctionnel et défaut du harnais
- les preuves de stade et d’isolation
- la relation entre une exécution d’artefact, l’acquisition et les unités d’axe affectées
- le teardown requis avant finalisation d’une unité

Une future carte de document, données, planification ou diagnostic fournit son propre adaptateur tout en conservant ce noyau et les mêmes dimensions de mesure.

## 5. Stades, temps et attribution

### 5.1 Frontière `HARNESS_READY`

Le harnais atteint `HARNESS_READY` uniquement après :

1. bootstrap réussi dans l’environnement épinglé
2. auto-test réussi sans lire ni charger le contenu candidat
3. enregistrement de la version et des empreintes du noyau, de l’adaptateur et de l’environnement
4. émission du reçu `HARNESS_READY`

Le reçu rend cette frontière observable. Il lie les résultats du bootstrap et de l’auto-test, leurs preuves, les empreintes attendues et le marqueur temporel utilisé par le budget artefact.

### 5.2 Budget artefact

Le budget artefact démarre immédiatement avant la première lecture ou le premier chargement du contenu candidat, après `HARNESS_READY`. Il s’achève lorsque l’évaluation couverte est terminée, avant le teardown. Il inclut :

- le chargement du contenu candidat
- l’initialisation candidate
- l’évaluation des unités d’axe couvertes par cette exécution

Le lock lie la portée du budget, sa valeur numérique approuvée, son unité, la règle de mesure et l’environnement qualifié. Une opération candidate ne peut être déplacée avant `HARNESS_READY` pour sortir du budget.

`ARTIFACT_EXECUTION_LIMIT` pénalise la réussite bout-en-bout. Avant tout statut officiel, les consignes visibles par le candidat doivent donc reproduire verbatim la valeur numérique approuvée, son unité, le début du budget, sa fin et la conséquence `ARTIFACT_EXECUTION_LIMIT`. Le lock lie ces consignes et leur hash task-vN au budget approuvé. Une absence ou une divergence donne `HOLD` avant acquisition.

### 5.3 Watchdog et teardown

Le watchdog du harnais possède sa propre enveloppe versionnée. Le temps consacré à l’arrêt contrôlé, à la collecte des preuves et au teardown reste hors du budget artefact. Une unité ne devient finale qu’après le teardown requis par son adaptateur.

L’expiration prouvée du budget artefact donne `ARTIFACT_EXECUTION_LIMIT`. Le déclenchement du watchdog sans preuve suffisante d’expiration candidate, un teardown incomplet ou un défaut du watchdog donne `HARNESS_ERROR`.

### 5.4 Preuves minimales par stade

| Stade terminal | Preuves minimales | Classe autorisée |
|---|---|---|
| route ou fournisseur avant artefact | lock et payload liés, route et fournisseur épinglés, reçu de tentative, réponse ou erreur structurée | `PROVIDER_FAILURE` |
| admission de modalité | SHA-256 des octets, version et hash de l’adaptateur, règle d’admission et résultat déterministe | `ARTIFACT_INVALID` |
| chargement, initialisation ou évaluation candidate | reçu `HARNESS_READY`, valeur et hash du budget approuvé, marqueurs de début et de stade, expiration observée, santé du watchdog | `ARTIFACT_EXECUTION_LIMIT` |
| bootstrap, auto-test, instrumentation, watchdog, teardown ou preuve ambiguë | empreintes disponibles, stade atteint, erreur structurée et inventaire des preuves manquantes | `HARNESS_ERROR` |
| évaluation terminée | reçu `HARNESS_READY`, SHA-256 des octets, marqueurs de début et de fin, teardown réussi, reçu d’axe et verdict | `MEASUREMENT_COMPLETED` |

L’attribution retient le premier stade terminal directement prouvé. Une preuve insuffisante interdit toute imputation au fournisseur, à l’artefact, au modèle ou à la configuration.

## 6. Qualification de la limite numérique

La valeur numérique du budget artefact est **absente, non qualifiée et non approuvée**. Aucun nombre historique ou intuitif ne la remplace. Task-v5 reste donc au statut `brouillon`, sans acquisition ni classement officiel.

La qualification suit cet ordre :

1. décrire le besoin d’usage que la limite doit protéger
2. épingler le matériel, le système, les runtimes, le noyau, l’adaptateur et leur configuration
3. produire des témoins indépendants issus du besoin et de la spécification, sans artefact de modèle ni accès au seuil proposé
4. mesurer leur variabilité dans l’environnement épinglé et conserver les observations brutes
5. dériver une valeur candidate du besoin d’usage et de cette variabilité
6. geler la valeur, la règle de mesure, les témoins et leurs empreintes
7. obtenir l’approbation explicite du propriétaire sur cet ensemble exact

La qualification devient opposable seulement après l’ajout verbatim de la valeur, de l’unité, des frontières de début et de fin et de la conséquence `ARTIFACT_EXECUTION_LIMIT` dans les consignes candidat-visibles. Le hash exact de task-vN est alors lié au lock. Si cet ajout intervient après le gel de la tâche, R-008 impose l’incrément de task-vN.

Les anciens artefacts de modèles peuvent servir de stress tests seulement après ce gel. Ils ne participent jamais au choix de la valeur. Un stress test qui invalide la proposition rouvre la qualification indépendante ; il ne permet pas d’ajuster le nombre à partir des performances historiques.

## 7. Métriques et publication

### 7.1 Qualité des axes

La qualité d’un axe utilise uniquement ses unités `SCORED`. Chaque valeur publiée affiche son dénominateur `SCORED` et la couverture `SCORED / unités requises`. Les verdicts, niveaux et règles d’agrégation restent ceux de la carte.

Une classe `PROVIDER_FAILURE`, `ARTIFACT_INVALID`, `ARTIFACT_EXECUTION_LIMIT` ou `HARNESS_ERROR` ne devient jamais un verdict d’axe. Une unité requise non scorée maintient le classement concerné au statut provisoire selon R-020.

### 7.2 Réussite bout-en-bout de la configuration

Chaque acquisition compte une seule fois :

- succès lorsque toutes ses unités requises terminent en `MEASUREMENT_COMPLETED`, quels que soient leurs verdicts d’axe
- échec lorsqu’un incident prouvé porte `PROVIDER_FAILURE`, `ARTIFACT_INVALID` ou `ARTIFACT_EXECUTION_LIMIT`
- exclusion du calcul lorsqu’un `HARNESS_ERROR` empêche de décider le résultat bout-en-bout

Le taux publié affiche le nombre de succès et le dénominateur des acquisitions décidables. Le dénominateur comprend les succès et les trois classes d’échec. Il exclut `HARNESS_ERROR`.

### 7.3 Couverture et santé d’infrastructure

Les `HARNESS_ERROR`, unités manquantes et acquisitions exclues sont publiés comme couverture manquante. Le classement reste provisoire tant que la couverture requise par le lock n’est pas restaurée.

La santé d’infrastructure présente les incidents, leurs stades, leurs preuves et les manques de couverture. Elle reste un diagnostic et ne produit aucun score.

## 8. Vue rétroactive versionnée

La vue rétroactive est append-only. Chaque enregistrement contient :

- le chemin relatif de la source et son SHA-256
- l’état et la cause portés par la source
- le résultat dérivé sous les trois dimensions verify-v7
- le niveau de preuve `DIRECT`, `RULE_DERIVED` ou `INSUFFICIENT`
- la version et le hash de la règle appliquée
- la version et le hash de l’outil de dérivation
- la comparabilité explicite `COMPARABLE`, `DIAGNOSTIC_ONLY` ou `NOT_COMPARABLE`, avec motif
- un identifiant propre à l’enregistrement dérivé

Un enregistrement s’ajoute ; il ne remplace ni ne corrige un reçu, un lock ou une vue antérieure. Une preuve `INSUFFICIENT` ne soutient aucune classe pénalisante.

Cette tranche définit le schéma et ne reclassifie aucune campagne.

### 8.1 Renotation expérimentale future

Une renotation expérimentale future produit de nouveaux reçus identifiés, liés aux octets sources, au `verify_hash`, à la règle et à l’outil exacts. Elle conserve le statut `EXPERIMENTAL` et ne modifie aucune source.

Ces reçus ne constituent jamais une preuve officielle task-v5 lorsque l’acquisition source n’a pas été produite sous le contrat candidat-visible et le hash exacts de task-v5. Une acquisition conforme reste nécessaire à toute preuve officielle.

## 9. Canari OpenRouter

Toute configuration OpenRouter candidate à un statut officiel exige d’abord un canari distinct, verrouillé et budgété. Le canari est lié à la configuration, à la route, au fournisseur et aux paramètres exacts. Il ne devient jamais une acquisition, une unité d’axe ou un score.

Le reçu du canari doit prouver de bout en bout :

- la route et le fournisseur réellement servis correspondent aux pins
- les paramètres requis ont été effectivement honorés ; une requête simplement acceptée ne suffit pas
- le succès et l’erreur suivent des structures validables par l’adaptateur
- la réponse porte les identifiants et métadonnées nécessaires à l’audit
- le payload, le budget, les observations et les empreintes du contrat restent liés au lock du canari

Une preuve absente ou ambiguë donne `HOLD` pour la configuration officielle. Un changement de route, fournisseur, paramètres obligatoires ou contrat d’adaptateur exige un nouveau canari lié au nouvel ensemble exact.

Aucune requête réseau ni aucun canari n’est exécuté dans cette tranche documentaire.

## 10. Portes restantes

Task-v5 / verify-v7 reste non officiel tant que manquent :

- la valeur numérique qualifiée et son approbation exacte
- les preuves de témoins indépendants et de variabilité
- l’implémentation et la qualification du noyau et de l’adaptateur de modalité
- les reçus de couverture requis
- le canari de chaque configuration OpenRouter destinée au statut officiel

La tranche documentaire est complète lorsque les sources de vérité sont cohérentes, task-v4 et les preuves historiques restent inchangés, et les contrôles textuels demandés passent. Elle s’arrête avant toute implémentation ou exécution.
