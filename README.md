---
style_gate: pass
---

# Benchmark Lab-X

Benchmark Lab-X doit répondre à une question pratique :

> Sur le workflow exact de mon besoin, combien me coûte en pratique une sortie acceptable, et quelle configuration choisir ?

La V0 est un pilote décisionnel interne, utilisé par Ayo ou un consultant Lab-X. Elle porte sur un seul workflow : préparer un pré-cadrage avant un entretien client pour une activité de conseil IA et cybersécurité auprès de PME.

Le livrable attendu est un rapport interne de décision. Aucun site public, classement général ou vainqueur universel n’est requis en V0.

## Ce que signifie « acceptable »

Une sortie est **officiellement acceptable** lorsque deux conditions sont réunies :

1. les contrôles automatiques rendent `PASS` sur les propriétés entièrement décidables par code
2. une revue humaine aveugle rend `ACCEPTABLE` sur la fidélité sémantique et l’utilité métier

La formule officielle est donc : **`PASS` automatique + `ACCEPTABLE` humain**.

Un juge LLM peut intervenir après le gel du verdict humain. Il reste fantôme, exploratoire et sans effet sur le résultat officiel.

## Ce qui sera comparé

Le pilote compare deux types de candidats sans les confondre :

- des configurations API fixes, identifiées par le modèle demandé, le backend, la route ou le provider, les paramètres et les versions qui influencent l’exécution
- OpenRouter Auto Router, identifié comme une politique de routage versionnée, jamais comme un modèle fixe

Auto Router doit être diagnostiqué avant toute configuration officielle. Un canari OpenRouter est obligatoire. Pour une configuration fixe, la route, le provider et les paramètres effectivement servis doivent être observables. Une preuve absente ou ambiguë bloque le statut officiel.

## Décision produite

Le rapport V0 présente :

- le taux de sorties officiellement acceptables
- le coût fournisseur par sortie officiellement acceptable
- la latence
- la couverture du harnais
- la provenance de chaque résultat

La métrique monétaire officielle V0 est le coût fournisseur par sortie officiellement acceptable. L’effort humain et les opérations sont consignés séparément, sans conversion monétaire implicite.

Le budget est facultatif. Lorsqu’il est absent, le rapport ne désigne pas arbitrairement un gagnant. Il montre toutes les configurations compatibles disposant de preuves comparables et assez fraîches, puis le front de Pareto observé sur exactement trois axes : le taux de sorties officiellement acceptables, maximisé ; le coût fournisseur par sortie officiellement acceptable, minimisé ; la latence selon la règle préenregistrée, minimisée. Les pannes fournisseur sont déjà comptées dans le taux. La couverture conditionne l’éligibilité des configurations et l’interprétation du front ; elle n’est pas un axe.

Une recommandation unique exige une préférence explicite. Si les preuves sont insuffisantes, incompatibles ou périmées au regard de la politique déclarée, Lab-X s’abstient.

## État réel au 14 août 2026

### Faits actuels

- Le paquet [`PRECADRAGE-ENTRETIEN-CLIENT-V0`](tasks/dev/pre-cadrage-entretien-client/registre-verite.md) décrit le stimulus synthétique, le contrat de sortie, les contrôles automatiques, la revue humaine aveugle et les témoins de qualification.
- Ce paquet qualifie un contrat de sortie. Il ne constitue pas encore une mesure comparative et ne soutient aucun choix de configuration.
- Le paquet sépare `qualification_status`, en attente d’approbation, et `execution_status`, non exécutée. Aucune approbation humaine n’est prouvée. L’approbation future est externe et liée au SHA-256 du [manifeste du paquet](tasks/dev/pre-cadrage-entretien-client/manifeste-paquet.json) ou de la PR qui le porte.
- Le dépôt contient des prototypes techniques, du code de campagnes antérieures et des preuves historiques.
- Les campagnes et reçus historiques restent immuables. Ils ne prouvent pas la nouvelle V0.
- `pentagone-rotatif` est un prototype historique et spécialisé, hors pilote V0 actif.

### Décisions prises

- Le pilote V0 reste étroit : un workflow réel, un rapport interne de décision et une évaluation hybride automatique plus humaine.
- Les pannes fournisseur comptent dans la réussite bout en bout lorsque la route appartient à la configuration.
- `HARNESS_ERROR` reste séparé, non pénalisant pour la configuration et visible comme défaut de couverture.
- Les benchmarks publics servent de contexte daté et sourcé. Leurs scores ne sont ni fusionnés entre eux, ni mélangés avec la mesure locale.

### Travail encore prospectif

- comparer Promptfoo, Ori Eval et une méthode manuelle au besoin exact
- arrêter la plateforme spécifique si une solution existante produit la même décision sans perte pertinente avec un effort complet inférieur
- implémenter ou choisir le runner, les adaptateurs, les reçus, la validation, la revue aveugle et l’analyse décisionnelle
- diagnostiquer Auto Router et exécuter les canaris autorisés avant toute campagne officielle
- produire la première campagne comparative V0

Aucun appel de modèle, canari, collecte ou résultat comparatif n’est réalisé par cette refonte documentaire.

## Démarrage documentaire

1. Lire le [PRD](docs/PRD.md) pour le besoin, la décision V0, les métriques et les portes d’arrêt.
2. Lire l’[ARD](docs/ARD.md) pour l’architecture logique, les identités, les preuves et les états.
3. Lire les [règles canoniques V0](docs/RULES.md) pour les invariants universels.
4. Utiliser le [gabarit de carte](tasks/TEMPLATE.md) pour une nouvelle carte compatible avec l’évaluation hybride.
5. Examiner le [paquet pré-cadrage](tasks/dev/pre-cadrage-entretien-client/registre-verite.md) sans le modifier : son approbation reste en attente et sera liée au SHA-256 de son manifeste.
6. Suivre le [guide d’utilisation de la campagne V1](tasks/dev/pre-cadrage-entretien-client/campagne-v1/guide-utilisation-v1/README.md) pour le parcours en six étapes, ses commandes et leurs codes de sortie.

L’ancien pipeline `pentagone-rotatif`, ses commandes et ses rapports ne constituent pas le démarrage du produit V0. Les anciens documents remplacés sont conservés dans l’[archive du socle antérieur](docs/archive/legacy-benchmark-v0-2026-08-14/README.md). L’ancien glossaire racine `CONTEXT.md` y est archivé byte-identiquement comme [`root-CONTEXT.md`](docs/archive/legacy-benchmark-v0-2026-08-14/root-CONTEXT.md) : il est historique, non normatif, et cède à PRD, ARD et RULES.

## Trajectoire conditionnelle

Les versions produit sont cumulatives : chaque version ajoute un profil de mesure sans retirer les précédents. Les profils API, abonnement et auto-hébergé sont parallèles et qualifiés indépendamment. Aucune comparaison inter-profils n’est permise sans contrat commun explicite.

- **V0** : profil de mesure API sur le workflow de pré-cadrage, rapport interne et abstention explicite
- **V1** : ajoute le profil de mesure abonnement, avec produit, plan, quotas, resets, interface, harnais et intervention humaine dans l’identité
- **V2** : ajoute le profil de mesure auto-hébergé, avec checkpoint, quantification, matériel, stack, énergie, amortissement, administration, occupation GPU, confidentialité, souveraineté et distinction entre coût marginal et coût complet
- **Site ou sélecteur** : conditionné à une décision utile du pilote ou à une abstention justifiée acceptée par le propriétaire, et à la porte outil existante ; il reçoit le besoin, les contraintes et un budget facultatif, puis recommande ou s’abstient avec provenance

Chaque extension exige son propre contrat versionné. Elle ne réécrit aucune campagne antérieure.
