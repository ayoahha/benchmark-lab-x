---
style_gate: pass
---

# PRD : Benchmark Lab-X V0

Version documentaire : V0 canonique, 14 août 2026

## 1. Question produit

Benchmark Lab-X répond à cette question :

> Sur le workflow exact de mon besoin, combien me coûte en pratique une sortie acceptable, et quelle configuration choisir ?

La V0 ne recherche pas le meilleur modèle en général. Elle mesure la capacité d’une configuration complète à produire une sortie officiellement acceptable sur un workflow précis, avec son coût, sa latence, sa couverture et sa provenance.

## 2. Autorité documentaire

| Document | Autorité courante |
|---|---|
| Ce PRD | problème, utilisateurs, décision V0, métriques, périmètre et portes d’arrêt |
| [ARD](ARD.md) | architecture logique, objets, identités, états, preuves et frontières de confiance |
| [RULES](RULES.md) | invariants universels de la V0 |
| [Gabarit de carte](../tasks/TEMPLATE.md) | contrat réutilisable d’une carte hybride |
| [README](../README.md) | compréhension du projet et démarrage documentaire |

Les documents [VERIFY-V7](VERIFY-V7.md) et [PREUVE-ATTEIGNABILITE-FLOAT64](PREUVE-ATTEIGNABILITE-FLOAT64.md) sont historiques et spécialisés. Ils ne gouvernent pas la V0.

## 3. Utilisateurs et usage

### 3.1 Utilisateur V0

L’utilisateur V0 est Ayo ou un consultant Lab-X. L’usage est interne et expert-assisté. La sortie sert à décider, pas à communiquer directement avec un client.

### 3.2 Workflow pilote

Le workflow pilote est le pré-cadrage avant entretien client pour un consultant ou entrepreneur IA et cybersécurité intervenant auprès de PME.

Le besoin métier est de transformer des notes brutes synthétiques en un pré-cadrage structuré, fidèle et utile pour préparer l’entretien, sous revue du consultant.

### 3.3 Livrable produit

La sortie V0 recommandée est un **rapport interne de décision**. Il présente les résultats comparables, les lacunes, le front de Pareto observé et, seulement lorsque les préférences le permettent, une recommandation.

Aucun site public n’est requis en V0.

## 4. État réel

### 4.1 Faits actuels

- Le paquet [`PRECADRAGE-ENTRETIEN-CLIENT-V0`](../tasks/dev/pre-cadrage-entretien-client/registre-verite.md) contient un stimulus synthétique, un registre de vérité, des contrôles automatiques, une rubrique humaine aveugle et des témoins.
- Le manifeste immuable sépare `qualification_status`, instantané initial en attente d’approbation, et `execution_status`, non exécutée.
- La [décision propriétaire D1](https://github.com/ayoahha/benchmark-lab-x/issues/15#issuecomment-5301590597) approuve exactement le paquet identifié par le SHA-256 `8030128d159e4203483b19f0e37692a53f01baecc38fbccaa321541c23e71a10`. Cette preuve GitHub externe liée à l’empreinte porte l’état courant de qualification. La [preuve M2.1](https://github.com/ayoahha/benchmark-lab-x/issues/34#issuecomment-5302877516) établit séparément l’intégrité cryptographique des fichiers présents. Cette règle documentaire ne devient canonique qu’après sa fusion dans la branche principale.
- Le paquet qualifie un contrat de sortie. Il ne constitue pas encore une mesure comparative.
- Aucune campagne comparative V0 ne prouve aujourd’hui le coût fournisseur par sortie officiellement acceptable ni le choix d’une configuration.
- Le dépôt conserve du code, des cartes, des reçus et des campagnes historiques. Ces preuves restent immuables et ne prouvent pas la nouvelle V0.
- `pentagone-rotatif` est un prototype historique et spécialisé, hors V0 active.

### 4.2 Décisions prises

- La V0 porte sur un seul workflow réel et étroit.
- L’acceptabilité officielle combine contrôle automatique et revue humaine aveugle.
- Les configurations API fixes et Auto Router sont deux types d’identité différents.
- Le budget est facultatif.
- Une absence de preuve conduit à l’abstention ou à un défaut de couverture, jamais à une conclusion inventée.

### 4.3 Capacités prospectives

- choix entre Promptfoo, Ori Eval, méthode manuelle ou composants spécifiques
- runner et adaptateurs V0
- canaris OpenRouter
- campagne comparative sur un paquet approuvé
- rapport interne de décision
- import de signaux externes datés

Cette distinction entre fait actuel, décision et prospectif reste visible dans toute restitution V0.

## 5. Entrées et sortie de la décision

### 5.1 Entrées

| Entrée | Contenu |
|---|---|
| Besoin exact | workflow, acteur, décision, conséquences d’erreur et sortie attendue |
| Contraintes | confidentialité, outils, routes, paramètres, délai, formats et exclusions |
| Budget | valeur facultative, unité, période et portée si l’utilisateur en fournit un |
| Préférences | arbitrage explicite entre taux d’acceptation officiel, coût fournisseur par sortie officiellement acceptable et latence |
| Politique de fraîcheur | règle déclarée pour accepter ou refuser une preuve datée |
| Paquet de carte | stimulus, contrat de sortie, contrôles, rubrique humaine, témoins, provenance et empreintes approuvées |
| Panel | configurations compatibles que la campagne peut réellement mesurer |

L’absence de budget ne devient ni un budget implicite ni un motif pour exclure les configurations les plus chères.

### 5.2 Sortie

Le rapport interne contient au minimum :

- le besoin et le périmètre exacts
- le panel mesuré et ses absences
- la provenance et la fraîcheur de chaque preuve
- les résultats automatiques et humains séparés
- le taux de sorties officiellement acceptables
- le coût fournisseur par sortie officiellement acceptable
- la latence et la couverture du harnais
- les pannes fournisseur attribuées à la configuration concernée
- les défauts du harnais séparés
- toutes les configurations compatibles et comparables
- le front de Pareto observé
- une recommandation liée aux préférences, ou une abstention motivée

## 6. Acceptabilité officielle

### 6.1 Formule

Une sortie est officiellement acceptable si et seulement si :

1. les contrôles automatiques rendent `PASS`
2. une revue humaine aveugle rend `ACCEPTABLE`

La formule officielle est **`PASS` automatique + `ACCEPTABLE` humain**.

### 6.2 Répartition des responsabilités

Les contrôles automatiques couvrent seulement les propriétés entièrement décidables par code : enveloppe, champs fermés, ordre, ancres valides, empreintes et cohérence mécanique du paquet.

La revue humaine aveugle couvre la fidélité sémantique, les contradictions, les contraintes, les risques, la priorité des questions, la sûreté de la prochaine action et l’utilité sans reconstruction matérielle.

Le relecteur ne voit pas l’identité de la configuration. Il ne réécrit pas la sortie et ne transforme pas son verdict en score mécanique.

### 6.3 Juge fantôme

Un juge LLM fantôme peut examiner le même dossier seulement après le gel du verdict humain. Son observation reste séparée. Elle ne modifie ni le résultat automatique, ni le verdict humain, ni l’acceptabilité officielle.

## 7. Configurations comparées

### 7.1 Configuration API fixe

Une configuration fixe comprend les dimensions qui influencent la sortie :

- modèle demandé et révision lorsqu’elle est déclarée
- backend, route, provider et endpoint attendus
- paramètres exacts, effort, contexte et politique de données
- version de l’adaptateur et du harnais
- canari et observations servies

Pour obtenir un statut officiel, la route, le provider et les paramètres servis doivent être observables et concordants avec le contrat. L’acceptation d’une requête ne prouve pas à elle seule qu’un paramètre a été honoré.

### 7.2 OpenRouter Auto Router

Auto Router est une **politique de routage**, jamais une identité de modèle fixe. Son identité comprend son slug et la configuration versionnée qui influence la sélection, notamment les modèles autorisés ou exclus, le niveau de coût, les contraintes de provider et les métadonnées demandées.

Chaque reçu conserve le modèle effectivement sélectionné et les métadonnées de route ou de provider réellement disponibles. Un champ non observé reste inconnu.

Auto Router doit être diagnostiqué avant toute configuration officielle. Aucun gain de coût, de qualité ou de fiabilité n’est présumé. Le diagnostic vérifie la stabilité utile au workflow, les informations observables, les restrictions, les fallbacks et l’effet de la politique sur la comparabilité.

### 7.3 Canari OpenRouter

Toute configuration OpenRouter officielle exige un canari séparé de la campagne. Le canari est lié au contrat exact de la configuration. Il vérifie la réponse, la provenance, les paramètres obligatoires et les erreurs sans produire de score ni d’acquisition V0.

Une preuve manquante ou ambiguë place la configuration en `HOLD` avant campagne.

### 7.4 Sens de « tous les modèles »

« Tous les modèles » signifie tous les candidats du panel compatible qui disposent de preuves comparables et assez fraîches selon la politique déclarée. Cette expression ne désigne jamais un catalogue exhaustif.

## 8. Résultats et métriques

### 8.1 États utiles à la décision

| État | Effet |
|---|---|
| `OFFICIALLY_ACCEPTABLE` | `PASS` automatique et `ACCEPTABLE` humain |
| `CANDIDATE_NOT_ACCEPTABLE` | `FAIL` automatique ou `NOT_ACCEPTABLE` humain |
| `PROVIDER_FAILURE` | la route appartenant à la configuration ne fournit pas la sortie requise ; échec bout en bout de cette configuration |
| `HARNESS_ERROR` | le dispositif ne permet pas d’attribuer un résultat ; aucune pénalisation de la configuration |
| `UNABLE_TO_JUDGE` | la preuve humaine manque ; aucune pénalisation de la configuration |

Une sortie absente à cause du provider n’est pas confondue avec une sortie sémantiquement mauvaise. Les deux empêchent toutefois une sortie officiellement acceptable pour l’acquisition concernée.

### 8.2 Taux de sorties officiellement acceptables

Le numérateur est le nombre de sorties `OFFICIALLY_ACCEPTABLE`.

Le dénominateur décidable comprend les sorties officiellement acceptables, les sorties candidat non acceptables et les pannes fournisseur attribuables à la configuration. `HARNESS_ERROR` et `UNABLE_TO_JUDGE` sont exclus du dénominateur décidable et réduisent la couverture.

Le rapport publie les comptes avec le taux. Il ne masque jamais la taille du dénominateur.

### 8.3 Coût fournisseur par sortie officiellement acceptable

La métrique monétaire officielle V0 est le coût fournisseur par sortie officiellement acceptable. Le coût attribuable à une configuration compte uniquement la dépense fournisseur, avec toutes ses tentatives, y compris ses pannes et reprises autorisées. Il est divisé par le nombre de sorties officiellement acceptables de cette configuration.

L’effort humain et le coût des opérations sont consignés et publiés séparément. Aucune conversion monétaire implicite ne les agrège à la métrique officielle.

Si ce nombre vaut zéro, le coût fournisseur par sortie officiellement acceptable est `non défini`. Le coût total engagé et l’absence de sortie acceptable restent visibles.

### 8.4 Latence

La campagne conserve les temps de collecte, de validation automatique et d’obtention du verdict humain. Le rapport distingue la latence de la configuration du délai complet avant décision officielle. La statistique publiée et sa règle sont déclarées avant lecture des résultats, ou la distribution complète est présentée.

### 8.5 Couverture

La couverture indique la part du plan pour laquelle une décision officielle ou un échec fournisseur attribuable est disponible. Les `HARNESS_ERROR`, les verdicts humains indisponibles et les preuves manquantes restent visibles avec leur cause.

### 8.6 Provenance

Chaque résultat est lié au besoin, au paquet et à ses empreintes, à la configuration, au payload, à la route observée, aux versions du harnais, aux coûts, aux temps, au résultat automatique et au reçu humain aveugle.

## 9. Politique de décision

### 9.1 Budget présent

Le rapport filtre uniquement selon le budget et la portée explicitement fournis. Il montre les configurations compatibles avec cette contrainte, puis applique les préférences déclarées.

### 9.2 Budget absent

Le rapport conserve toutes les configurations compatibles et comparables, y compris les plus chères. Il publie le front de Pareto observé sur exactement trois axes :

- le taux de sorties officiellement acceptables, maximisé ; les pannes fournisseur attribuables sont déjà comptées dans son dénominateur décidable
- le coût fournisseur par sortie officiellement acceptable, minimisé
- la latence selon la règle préenregistrée, minimisée

La couverture n’est pas un axe du front. Elle conditionne l’éligibilité d’une configuration à la comparaison et l’interprétation du front.

Aucun point dominé n’est présenté comme meilleur. Aucune recommandation unique n’est produite sans préférence explicite permettant de départager le front.

### 9.3 Abstention

Lab-X s’abstient lorsque :

- aucune configuration ne satisfait les contraintes du besoin
- les preuves ne sont pas comparables ou assez fraîches
- la couverture ne permet pas la décision annoncée
- l’identité ou la provenance reste ambiguë
- une préférence indispensable à une recommandation unique manque

L’abstention nomme la preuve absente et l’action humaine éventuelle. Elle ne crée aucune valeur de remplacement.

## 10. Benchmarks et signaux publics

Les benchmarks publics fournissent du contexte et des signaux externes. Chaque import conserve la source officielle, l’URL, la date de publication ou de mise à jour, la date de consultation, la tâche, le panel, la métrique et les limites déclarées.

Lab-X ne fusionne pas des scores incomparables et n’invente aucun score global. Les essais locaux priment seulement pour le workflow exact qu’ils mesurent.

GDPval inspire l’emploi de tâches proches du travail réel et de comparaisons humaines expertes en aveugle. Il ne remplace pas automatiquement le pilote local. Son propre contrat et ses limites restent visibles.

## 11. Porte d’arrêt avant plateforme spécifique

Avant de développer une plateforme propre à Lab-X, la V0 compare au minimum les capacités pertinentes de :

- Promptfoo
- Ori Eval
- une méthode manuelle contrôlée

La comparaison porte sur le même contrat de décision : paquet exact, identités de configurations, collecte des coûts et latences, contrôles automatiques, revue humaine aveugle, provenance, abstention et effort d’exploitation.

L’effort complet inclut la configuration, l’intégration, l’exécution, la revue humaine, la vérification, la maintenance et la production du rapport.

Si une solution existante produit la même décision sans perte pertinente avec un effort complet inférieur, la plateforme spécifique s’arrête. Le projet utilise ou adapte la solution existante. Une préférence d’implémentation ne suffit pas à franchir cette porte.

## 12. Critères de succès V0

La V0 est réussie lorsque les preuves suivantes existent :

- le workflow exact et la décision sont figés
- le paquet est approuvé par un humain via une référence externe liée au SHA-256 de son manifeste
- aucune donnée client réelle, secret, connecteur de production ou action externe n’entre dans la carte
- la porte Promptfoo, Ori Eval ou manuel est tranchée avec l’effort complet observé
- le panel et les identités de configurations sont figés sans nombre arbitraire
- Auto Router est diagnostiqué avant inclusion officielle
- les canaris OpenRouter requis sont acceptés
- la campagne produit des reçus comparables sous le contrat exact
- chaque résultat officiel combine contrôle automatique et verdict humain aveugle
- le rapport présente les métriques, la couverture, la provenance, le front de Pareto et la décision ou l’abstention
- toute recommandation unique est reliée à une préférence explicite

Une vérification documentaire ne prouve aucun de ces comportements d’exécution.

## 13. Critères d’arrêt et HOLD

La V0 s’arrête sans campagne officielle lorsque l’identité, le canari, le paquet, la sécurité ou l’autorisation de dépense manque.

La plateforme spécifique s’arrête si la porte des outils existants est satisfaite par une solution moins coûteuse en effort complet.

Le rapport s’arrête sur une abstention lorsque les preuves ne permettent pas de choisir. Il ne demande une décision propriétaire que si une préférence ou une autorisation réellement nécessaire manque.

## 14. Trajectoire

### Versions cumulatives et profils parallèles

Les versions produit sont cumulatives : chaque version ajoute un profil de mesure sans retirer les précédents. Les profils API, abonnement et auto-hébergé sont parallèles et qualifiés indépendamment. Aucune comparaison inter-profils n’est permise sans contrat commun explicite.

### V1 : ajout du profil abonnement

V1 ajoute le profil de mesure abonnement, qui compare l’expérience réelle de produits par abonnement. L’identité comprend le produit, le plan, les quotas, les resets, l’interface, le harnais et l’intervention humaine. Un même modèle dans deux produits ou plans ne crée pas une identité commune.

### V2 : ajout du profil auto-hébergé

V2 ajoute le profil de mesure auto-hébergé. Il compare modèle ou checkpoint, quantification, matériel, stack, énergie, amortissement, administration, occupation GPU, confidentialité et souveraineté. Il distingue coût marginal et coût complet.

### Site ou sélecteur

Un site devient envisageable seulement après une décision utile du pilote ou une abstention justifiée acceptée par le propriétaire, et sous la porte outil de la section 11. Il reçoit un besoin, des contraintes et un budget facultatif, puis recommande ou s’abstient avec provenance. Cette vision n’est pas un engagement V0.

## 15. Non-objectifs V0

- plusieurs cartes ou plusieurs domaines pour simuler une couverture
- classement général ou vainqueur universel
- score global mêlant mesures locales et benchmarks publics
- juge LLM officiel
- comparaison de produits par abonnement
- auto-hébergement
- site public
- donnée client réelle, secret, connecteur de production ou action externe
- modernisation rétroactive des campagnes historiques
- nombre de runs, modèles, seuils, budgets ou délais inventé

## 16. Sources officielles consultées

| Source officielle | Date utile | Usage local | Limite |
|---|---|---|---|
| [OpenRouter, Auto Router](https://openrouter.ai/docs/guides/routing/routers/auto-router) | consultation le 14 août 2026 | confirmer qu’Auto sélectionne un modèle selon une politique et que la réponse expose le modèle sélectionné | comportement susceptible d’évoluer ; diagnostic et canari locaux requis |
| [Promptfoo, documentation d’introduction](https://www.promptfoo.dev/docs/intro/) | consultation le 14 août 2026 | confirmer les évaluations par cas d’usage, providers, métriques automatiques et revue structurée | capacité annoncée, pas preuve d’adéquation au pilote |
| [OpenRouter, Ori Eval](https://openrouter.ai/docs/guides/ori/eval) | consultation le 14 août 2026 | confirmer le harnais par run, les comparaisons de modèles, coûts, temps et rapports | exécute de vrais appels ; aucun essai réalisé dans cette tranche |
| [OpenAI, GDPval](https://openai.com/index/gdpval/) | publication le 25 septembre 2025, consultation le 14 août 2026 | méthode de tâches professionnelles réalistes et comparaison humaine experte aveugle | évaluation large et one-shot ; pas substitut au workflow local |

Ces sources soutiennent seulement les faits cités. Elles ne prouvent ni l’adéquation d’un outil à la V0, ni un résultat de configuration.
