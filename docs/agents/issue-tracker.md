# Tracker : GitHub

Le tracker de ce dépôt est GitHub.

## Autorités

- GitHub Issues porte les tâches, dépendances, décisions et preuves
- le champ `Status` du Project personnel global `Pilotage global ayoahha` porte uniquement le statut de travail
- l’état ouvert ou fermé d’une Issue indique seulement si elle reste à résoudre
- aucun label, titre, checklist ou document local ne duplique le statut Project
- `Backlog.md` et tout substitut local ne sont pas utilisés
- les commits et pull requests référencent l’Issue qu’ils servent

## Project et statuts

- propriétaire : `ayoahha`
- Project : `Pilotage global ayoahha`
- URL : `https://github.com/users/ayoahha/projects/5`
- statuts autorisés : `Backlog`, `Ready`, `In progress`, `In review`, `Ready to ship`, `Done`

Lire le Project et son champ `Status` avant toute écriture de statut. Si le Project, son champ, ses options ou les permissions sont absents ou ambigus, arrêter sans écrire.

## Publication

Créer les Issues dans l’ordre nécessaire à la résolution de leurs références.

Chaque Issue contient :

- résultat attendu, formulé pour une personne non technique
- périmètre et hors périmètre
- dépendances
- décisions à prendre ou déjà prises
- preuves attendues
- condition binaire de fermeture

Utiliser les dépendances natives GitHub. Ne jamais déduire une dépendance depuis l’ordre du Project.

Après création :

1. ajouter l’Issue au Project cible
2. appliquer une option existante du champ `Status`
3. ne créer, renommer ou supprimer aucune option sans décision propriétaire

## Opérations

- publier une tâche ou une spécification : créer une GitHub Issue
- lire la tâche pertinente : lire l’Issue et ses commentaires
- enregistrer une décision : commenter l’Issue concernée
- enregistrer une preuve : commenter l’Issue avec la commande, le résultat utile et la référence de l’artefact
- résoudre : vérifier la condition de fermeture, commenter la preuve, puis fermer l’Issue

Les pull requests externes ne sont pas une surface de triage.
