---
style_gate: pass
---

# Instructions pour les agents

## Mission et phase actuelle

Benchmark Lab-X aide à choisir un modèle pour une tâche précise à partir de preuves lisibles. Le verdict porte sur la configuration observée sous des conditions communes, jamais sur le nom du modèle seul.

La prochaine phase s'appelle `V2-alpha`. Son architecture, son découpage, son backlog, ses campagnes et son implémentation suivent les décisions explicites d'Ayo et les documents canoniques.

## Sources faisant autorité

Lire les documents utiles avant de modifier leur domaine :

- `docs/PRD.md` pour le besoin et le périmètre produit
- `docs/ARD.md` pour les objets, frontières et flux
- `docs/RULES.md` pour les invariants de décision et de preuve
- `CONTEXT.md` pour le vocabulaire
- `tasks/TEMPLATE.md` pour le contrat minimal d'une future tâche

Ces chemins sont uniques. Ne jamais créer de copie, variante datée ou dossier d'archives. Git porte l'historique. Une Issue, une PR, un ancien résultat ou une branche ne remplace pas la spécification courante.

La demande actuelle d'Ayo prévaut sur ce fichier. PRD, ARD et règles gouvernent des domaines distincts ; aucun ne corrige silencieusement les autres. Signaler un conflit au lieu d'inventer une synthèse.

## Manière de travailler

- comprendre le flux concerné avant d'écrire
- viser le plus petit changement qui satisfait la demande
- réutiliser l'existant avant d'ajouter une abstraction ou une dépendance
- préserver les changements non liés, notamment ceux déjà présents dans le worktree
- ne pas transformer une découverte adjacente en nouvelle tâche
- ne pas fabriquer de mesure, de preuve, d'état ou d'autorité absente
- séparer clairement fait établi, déduction et hypothèse lorsque cette distinction change une décision
- ne jamais requalifier V0 ou V1 à partir de la spécification courante

## Autorité et sécurité

Une approbation documentaire n'autorise ni appel candidat, ni retry, ni dépense, ni campagne, ni publication, ni déploiement.

Demander une autorisation explicite avant toute opération Git destructive, fusion, suppression de branche, fermeture de PR ou d'Issue, release, appel payant ou action sur un système externe. Ne jamais exposer de secret. Les données et sorties réelles restent privées tant qu'une publication n'est pas autorisée.

## GitHub

GitHub Issues porte les tâches, dépendances, décisions et preuves. Le champ `Status` du [Project #5](https://github.com/users/ayoahha/projects/5) porte l'état de travail. Aucun backlog local ne le duplique.

Créer ou redécouper les Issues V2-alpha seulement après une décision explicite d'Ayo sur le découpage de livraison. Une Issue se ferme avec sa preuve de résultat ou une décision explicite de remplacement.

## Validation

Exécuter d'abord le test le plus proche du changement. Avant livraison d'un changement susceptible d'affecter le comportement, exécuter la validation complète :

```bash
uv run --with requests --with mpmath==1.3.0 python -m unittest discover -s tests
```

Pour un changement documentaire, vérifier aussi les liens, les chemins canoniques et l'absence de source concurrente. Ne pas déplacer dans la prose un contrôle que la CI peut garantir.

## Livraison et arrêt

Avant de conclure, fournir :

- les fichiers modifiés ou supprimés
- les validations exécutées et leur résultat
- les limites ou décisions encore ouvertes

S'arrêter dès que le résultat autorisé est prouvé. Si une information ou une autorité indispensable manque, rester en `HOLD` sans fallback implicite.

## Règles de revue

Signaler comme bloquant toute nouvelle autorité documentaire concurrente, requalification de V0 ou V1, architecture V2-alpha sans autorité, secret versionné ou contournement d'une preuve requise. Laisser le formatage automatique aux outils du dépôt.
