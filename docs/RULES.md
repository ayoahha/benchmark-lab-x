---
style_gate: pass
---

# Invariants universels de Benchmark Lab-X

Version documentaire du 14 août 2026

Ce fichier porte les invariants communs aux mesures actuelles et futures. Le protocole v2 et ses règles `R-001` à `R-030` restent historiques. Leur texte byte-identique est conservé dans l’[archive du 14 août 2026](archive/legacy-benchmark-v0-2026-08-14/docs-RULES.md). Les identifiants `U-*` forment un nouveau contrat. Ils ne renumérotent pas silencieusement les règles historiques.

Le [PRD](PRD.md) gouverne le produit. L’[ARD](ARD.md) gouverne les objets et les flux. Une carte versionnée précise les règles propres à son workflow.

## 1. Besoin et portée

- **U-001. Besoin exact.** Toute conclusion répond à un workflow, une sortie attendue, des contraintes et une décision explicitement identifiés. Elle ne s’étend pas à un autre besoin sans preuve comparable.

- **U-002. Conclusion bornée.** Toute comparaison nomme son panel, sa date, ses absences, sa fraîcheur et ses limites. « Tous les modèles » signifie tous les candidats compatibles du panel disposant de preuves comparables et assez fraîches.

- **U-003. Données sûres.** Une carte V0 ne contient aucune donnée client réelle, aucun secret, aucun connecteur de production et aucune action externe. Les données sont synthétiques ou publiquement réutilisables avec provenance.

- **U-004. Limites autorisées.** Aucun nombre de cartes, candidats, runs, relectures, seuil, budget ou délai n’est fixé sans décision propriétaire, contrat technique applicable ou mesure nécessaire à la preuve.

## 2. Versions, identités et preuves

- **U-005. Identité complète.** L’objet comparé inclut tous les composants qui influencent matériellement la sortie, le coût ou la latence. Le nom du modèle seul ne suffit pas.

- **U-006. Configuration fixe.** Une configuration fixe verrouille le modèle demandé, le fournisseur et la route lorsqu’ils sont imposés, les paramètres, la politique de données, l’adaptateur et le harnais pertinents. Route, fournisseur et paramètres servis doivent être observables pour soutenir un résultat officiel.

- **U-007. Politique de routage.** OpenRouter Auto Router est comparé comme une politique de routage, jamais comme l’identité d’un modèle fixe. Le modèle, le fournisseur et la route servis restent des observations de chaque acquisition.

- **U-008. Canari.** Toute configuration OpenRouter officielle exige un canari préalable lié à son identité et à ses paramètres. Auto Router est diagnostiqué avant son admission. Un canari ne prouve aucun bénéfice comparatif.

- **U-009. Empreintes et approbation.** Carte, stimulus, instrument, rubrique humaine et campagne sont versionnés et liés par empreinte. Plusieurs humains ou LLM peuvent préparer un paquet, mais seule l’approbation humaine liée aux empreintes fait autorité.

- **U-010. Immutabilité.** Une campagne et ses reçus ne sont jamais réécrits. Une correction crée un nouvel objet versionné. Une vue ou une politique future peut évoluer si elle déclare sa version et ses sources.

- **U-011. Historique non transférable.** Une preuve historique établit seulement les propriétés de son propre contrat. Elle ne prouve pas une nouvelle carte, une nouvelle campagne ou la V0 décisionnelle.

## 3. Acceptabilité et incidents

- **U-012. Contrôles automatiques décidables.** Un contrôle automatique officiel porte uniquement sur une propriété entièrement décidable par code. Toute autre propriété reste hors du verdict automatique.

- **U-013. Revue humaine aveugle.** La fidélité sémantique et l’utilité sont évaluées par un humain sans identité de candidat ni information de coût. La rubrique et l’ordre de présentation sont gelés avant la revue officielle.

- **U-014. Sortie officiellement acceptable.** Une sortie est officiellement acceptable si, et seulement si, elle reçoit `PASS` automatique et `ACCEPTABLE` humain.

- **U-015. Juge fantôme.** Un juge LLM peut intervenir seulement après gel du verdict humain. Son avis reste séparé et sans effet officiel.

- **U-016. Panne fournisseur.** Une panne fournisseur pénalise la réussite bout en bout lorsque la route appartient à la configuration comparée. Elle ne devient pas un verdict de qualité de la sortie.

- **U-017. Défaut du harnais.** `HARNESS_ERROR` ne pénalise pas la configuration. Il réduit la couverture, reste visible et empêche toute conclusion qui dépend de la mesure manquante.

- **U-018. Abstention.** Une identité, une provenance, une fraîcheur, une comparabilité ou une préférence insuffisante impose l’abstention correspondante. Une absence de preuve n’est jamais transformée en résultat favorable.

## 4. Mesures et décision

- **U-019. Mesures centrales.** Toute comparaison V0 présente le taux de sorties officiellement acceptables, le coût fournisseur par sortie officiellement acceptable, la latence, la couverture du harnais et la provenance. Elle publie les dénominateurs et les données manquantes nécessaires à leur interprétation.

- **U-020. Coût fournisseur par sortie officiellement acceptable.** La métrique monétaire officielle compte uniquement la dépense fournisseur imputable à la configuration, avec toutes ses tentatives. L’effort humain et les opérations sont consignés séparément, sans conversion monétaire implicite. En l’absence de sortie acceptable, la mesure est signalée comme non définie et les coûts engagés restent visibles.

- **U-021. Budget facultatif.** Un budget absent n’est ni remplacé par un seuil implicite ni utilisé pour écarter les configurations les plus chères. Toutes les configurations compatibles et comparables sont présentées.

- **U-022. Pareto et préférence.** Le front de Pareto V0 porte sur exactement trois axes : taux de sorties officiellement acceptables maximisé, coût fournisseur par sortie officiellement acceptable minimisé, latence selon la règle préenregistrée minimisée. Les pannes fournisseur sont déjà comptées dans le taux. La couverture conditionne l’éligibilité et l’interprétation sans être un axe. Sans préférence explicite suffisante, la restitution présente ce front puis s’abstient de nommer un gagnant unique.

- **U-023. Benchmarks publics séparés.** Un benchmark public reste un signal externe avec provenance, date, fraîcheur, protocole et limites. Aucun score global n’est inventé et aucun score incomparable n’est fusionné avec le pilote local.

- **U-024. Primauté locale bornée.** Les essais Lab-X priment seulement pour le workflow exact qu’ils mesurent. GDPval et les méthodes comparables inspirent les tâches réalistes et l’évaluation experte, sans se substituer automatiquement au pilote local.

## 5. Nécessité de la plateforme

- **U-025. Critère d’arrêt.** Avant de construire ou d’étendre une plateforme spécifique, comparer Promptfoo, Ori Eval et une méthode manuelle à l’effort complet nécessaire. Si une solution existante produit la même décision sans perte pertinente avec un effort complet inférieur, arrêter la plateforme spécifique.

- **U-026. Distinction d’état.** Tout document ou rapport distingue fait actuel, décision prise et capacité prospective. Une intention, une structure locale ou un test ne prouve pas une campagne exécutée ni une valeur produit.
