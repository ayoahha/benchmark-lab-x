---
style_gate: pass
---

# Benchmark Lab-X

Benchmark Lab-X aide à choisir un modèle pour une tâche précise à partir de preuves lisibles. Le modèle est mis en avant, mais chaque verdict reste borné à la configuration réellement observée et aux conditions communes du test.

## État actuel

- V0 et V1 sont historiques. Elles n'établissent ni gagnant, ni classement qualitatif, ni coût par résultat acceptable.
- L'harmonisation documentaire est terminée. Une seule version du PRD, de l'ARD et des règles fait autorité.
- La prochaine phase porte le nom `V2-alpha`.
- Le Graph Engineering est encore en cours. Aucun découpage, développement ou benchmark V2-alpha ne démarre avant sa validation.

## Question produit

> Pour une tâche et un contrat fixés avant l'exécution, quelles configurations associant un modèle à un accès direct ou API accomplissent le travail sous le même Pi ? Parmi les configurations `SATISFAIT`, lesquelles coûtent le moins et quels bénéfices prévus justifient une option plus chère ?

## Principes

- le contrat de réussite précède toute exécution
- Pi reste le harnais commun
- les erreurs éliminatoires précèdent le verdict
- le coût ne départage que les configurations `SATISFAIT`
- toute conclusion reste située, traçable et sans classement universel
- l'accès commence avec la communauté Lab X, avec une vocation publique ultérieure

## Documents faisant autorité

- [PRD](docs/PRD.md) : besoin et périmètre produit
- [ARD](docs/ARD.md) : objets, frontières et flux
- [Règles](docs/RULES.md) : invariants de décision et de preuve
- [Glossaire](CONTEXT.md) : vocabulaire du domaine
- [Gabarit de tâche](tasks/TEMPLATE.md) : contrat minimal d'une future tâche
- [Instructions agents](AGENTS.md) : méthode de travail dans le dépôt

Il n'existe aucune copie parallèle de ces documents. Leur historique appartient à Git.

## Validation

La CI exécute :

```bash
uv run --with requests --with mpmath==1.3.0 python -m unittest discover -s tests
```

Les tâches et leur état vivent dans les [GitHub Issues](https://github.com/ayoahha/benchmark-lab-x/issues) et le [Project #5](https://github.com/users/ayoahha/projects/5), jamais dans un backlog local.
