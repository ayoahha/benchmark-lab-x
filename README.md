---
style_gate: pass
---

# Benchmark Lab-X

Benchmark Lab-X aide à choisir un modèle pour une tâche précise à partir de preuves lisibles. Le modèle est mis en avant, mais chaque verdict reste borné à la configuration réellement observée et aux conditions communes du test.

## État actuel

- La V2-alpha est publiée sur [GitHub Pages](https://ayoahha.github.io/benchmark-lab-x/) : une tâche, une campagne et une restitution statique de trois configurations.
- Publication de référence : [commit 8f121a3c97d0997590edafd6e980e0cb29314a56](https://github.com/ayoahha/benchmark-lab-x/commit/8f121a3c97d0997590edafd6e980e0cb29314a56), [déploiement réussi](https://github.com/ayoahha/benchmark-lab-x/actions/runs/33898902009).
- Les canons décrivent le produit et son contrat d'architecture ; leur approbation ne prouve pas une implémentation ni une publication.

## Décisions pour V2 bêta

Ayo retient un monorepo front-end et back-end, une même VM et une même origine publique, l'architecture minimale de l'ARD, GitHub pour le produit et le backlog, et Forgejo pour la release et le déploiement. Les besoins du contrôleur dans cybrel-infrastructure doivent être précisés avant son installation. Les contributions publiques sont hors de ce lot.

Le panel sélectionné comprend dix modèles :

- GLM5.3
- Deepseek V4 Flash-0731
- Muse spark 1.3
- Hy4 Preview
- Minimax M3
- Qwen3.8-Max-0902
- Mimo-V2.5-Pro
- Gemini 3.8 Flash
- Kimi k3
- Grok 4.6

Les révisions `0731` et `0902` sont exigées. Ces noms sont une sélection propriétaire, pas une preuve de disponibilité. Identifiants des canaux, fournisseurs, routes, paramètres et identités observables doivent être résolus dans les manifestes approuvés, sans alias mobile substitué silencieusement.

Le contenu du catalogue, les cas, les règles d'agrégation, les budgets et les autorisations d'appel restent à définir. Aucune Story de tâche, campagne ou candidat n'est créée avant décision de son contenu, de son panel et de son budget.

## Repères historiques

V0 a obtenu une sortie sur deux configurations API, sans répétition. Grok a échoué à `G-001` ; Kimi a fini en `HARNESS_ERROR`. Aucun verdict humain, coût total connu, front à trois axes calculable, gagnant ou recommandation n'en découle.

V1 a obtenu six sorties sur sept produits d'abonnement. Les six ont échoué à `G-001`, sans `PASS` ni revue humaine officielle. Quotas et effort humain restent inconnus dans la restitution consolidée. Le coût d'abonnement par sortie acceptable est `NON_DEFINI` par décision propriétaire V1.

Ces campagnes restent sous leurs contrats d'origine, sans classement qualitatif, baseline ou requalification.

## Question produit

> Pour une tâche et un contrat fixés avant l'exécution, quelles configurations associant un modèle à un accès direct ou API accomplissent le travail sous le même Pi ? Parmi les configurations `SATISFAIT`, lesquelles coûtent le moins et quels bénéfices prévus justifient une option plus chère ?

## Principes

- le contrat de réussite précède toute exécution
- Pi reste le harnais commun
- les erreurs éliminatoires précèdent le verdict
- le coût ne départage que les configurations `SATISFAIT`
- toute conclusion reste située, traçable et sans classement universel
- le public consulte les restitutions approuvées ; les opérations et la publication restent protégées

## Documents faisant autorité

- [PRD](docs/PRD.md) : besoin et périmètre produit
- [ARD](docs/ARD.md) : objets, frontières et flux
- [Règles](docs/RULES.md) : invariants de décision et de preuve
- [Glossaire](CONTEXT.md) : vocabulaire du domaine
- [Gabarit de tâche](tasks/TEMPLATE.md) : contrat minimal d'une future tâche
- [Instructions agents](AGENTS.md) : méthode de travail dans le dépôt

Il n'existe aucune copie parallèle de ces documents. Leur historique appartient à Git.

## Validation

La CI configurée exécute :

```bash
uv run --with requests --with mpmath==1.3.0 python -m unittest discover -s tests
```

Cette découverte ne couvre pas `v2_alpha_demo/test_demo.py`. Plusieurs preuves d'interruption de cette suite exigent macOS. Leur couverture en CI et leur équivalent Linux doivent être traités avant de revendiquer une validation complète du moteur.

Les tâches de livraison et leur état vivent dans les [GitHub Issues](https://github.com/ayoahha/benchmark-lab-x/issues) et le [Project #5](https://github.com/users/ayoahha/projects/5), sans backlog local. Parent issue porte la hiérarchie ; Sub-issues progress sa progression. Les états des campagnes appartiennent au produit.
