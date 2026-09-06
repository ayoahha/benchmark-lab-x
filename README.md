---
style_gate: pass
---

# Benchmark Lab-X

Benchmark Lab-X aide à choisir une configuration de modèle d’IA pour une tâche précise. Il rapproche le travail demandé, les résultats obtenus, leur évaluation et leur coût pour permettre une décision fondée sur des preuves consultables.

La question est simple : **quelles configurations accomplissent ce travail, à quel coût et avec quelles limites ?** Une conclusion vaut pour la tâche et les conditions testées. Le projet ne cherche pas à désigner un meilleur modèle universel.

## Découvrir les résultats

[Ouvrir la comparaison publique](https://ayoahha.github.io/benchmark-lab-x/).

Le site présente une restitution statique sur un scénario et trois configurations. Pour l’utiliser :

1. Lisez le besoin, l’entrée et le résultat attendu pour vérifier que la tâche ressemble à votre usage.
2. Examinez le verdict de chaque configuration et les constats qui le justifient.
3. Comparez les coûts des configurations qui satisfont les critères, puis les bénéfices prévus d’une option plus chère.
4. Consultez les sorties, incidents et limites avant de transposer la conclusion à votre situation.

Un verdict indéterminé signifie que les preuves ne permettent pas de conclure. Un coût manquant limite la comparaison économique ; les dépenses des configurations non admissibles restent visibles. Les [règles de décision](docs/RULES.md#7-ordre-de-décision) expliquent ces distinctions.

## Utiliser l’outil local

L’outillage Python prépare un scénario figé, recueille les sorties après autorisation, prépare une revue et construit une page à partir de décisions approuvées. Il peut aussi produire une nouvelle présentation d’un résultat scellé sans relancer de candidat.

Depuis la racine du dépôt, avec Python 3 :

```bash
python3 -B -m benchmark_lab_x --help
```

Pour consulter une campagne locale déjà construite et scellée, remplacez le chemin d’exemple par le sien :

```bash
python3 -B -m benchmark_lab_x show --run-dir runs/ma-campagne
```

Cette commande vérifie l’intégrité puis ouvre la page sur macOS. Le [guide local](benchmark_lab_x/README.md) détaille les étapes, les prérequis et les autorisations nécessaires. Les [tests hors ligne](benchmark_lab_x/verify.md) utilisent un faux Pi et n’appellent aucun modèle.

L’outil actuel reste attaché à un scénario et à son panel figés. Il ne fournit pas encore le catalogue de tâches, la navigation entre plusieurs campagnes, le serveur Linux et la persistance décrits dans les spécifications. Le [périmètre produit](docs/PRD.md#5-périmètre-produit) définit ces capacités attendues.

## Préparer une tâche de benchmark

Une tâche part d’un travail concret : comparer des salles pour une association, transformer des notes de réunion en suivi ou rechercher une information dans un dossier professionnel. Le projet vise des métiers variés ; le catalogue prévu distingue le contexte métier du type de travail demandé. Le [gabarit de tâche](tasks/TEMPLATE.md) aide à décrire :

- le besoin, le résultat utilisable, ce que l’utilisateur doit encore faire et la décision à éclairer ;
- les cas d’essai, leurs données et les conditions communes ;
- les obligations, les variations acceptables, les erreurs éliminatoires et la référence permettant de juger ;
- le périmètre des coûts et les limites de la conclusion.

La préparation vérifie aussi que la référence est étayée et que les contrôles acceptent une solution valable et repèrent les défauts visés. Des modèles peuvent aider à la relire ; leur accord ne suffit pas à établir sa justesse. Le responsable de campagne prépare et approuve ce contrat avant l’exécution, selon les [règles de qualification](docs/RULES.md#4-contrat-avant-exécution). Le choix des configurations et du budget nécessite ses propres décisions.

Remplir cette carte ne l’enregistre pas automatiquement dans un catalogue et ne la rend pas exécutable par l’outillage actuel. L’intégration d’une nouvelle tâche doit relier la carte à ses données, à ses contrôles et à une campagne autorisée. Le site public ne propose ni formulaire de contribution, ni téléversement, ni commentaire.

## Comprendre le projet et suivre son évolution

- [PRD](docs/PRD.md) : utilisateurs, parcours, périmètre et critères produit
- [ARD](docs/ARD.md) : architecture, données, interfaces et exploitation
- [Règles](docs/RULES.md) : évaluation, coûts, autorités et [versionnement](docs/RULES.md#14-versionnement-du-produit)
- [Glossaire](CONTEXT.md) : vocabulaire partagé
- [Instructions agents](AGENTS.md) : travail et validation dans le dépôt

Les [Issues GitHub](https://github.com/ayoahha/benchmark-lab-x/issues) et le [Project](https://github.com/users/ayoahha/projects/5) portent le travail de livraison et son avancement.
