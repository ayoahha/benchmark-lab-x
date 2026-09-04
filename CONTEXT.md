---
style_gate: pass
---

# Glossaire Benchmark Lab-X

Ce glossaire fixe les termes du domaine. Les décisions, règles, états observés et choix d'implémentation vivent dans les documents auxquels il renvoie.

## Objet du benchmark

### Modèle
Objet produit mis en avant dans le premier prototype. Un verdict sur un modèle reste borné à la configuration dans laquelle il a été observé.

### Accès direct ou API
Mode d'accès où le modèle est appelé directement ou par une API déclarée, sans produit agentique sous abonnement comme objet de comparaison.
_À éviter_ : profil API, lorsque ce terme laisse croire qu'un second profil actif existe déjà.

### Configuration observée
Unité de preuve d'un candidat : fournisseur, modèle, mode d'accès, route, paramètres et effort de raisonnement, tels que demandés puis observés, reliés aux [conditions de test communes](#conditions-de-test-communes) sous lesquelles la sortie a été obtenue. Une route demandée ou observée non prouvée reste `INCONNU`.
_À éviter_ : modèle seul, solution complète.

### Conditions de test communes
Objet logique unique, déclaré avant le premier candidat et référencé par toutes les configurations comparées : état de Pi, environnement et date de gel. Une condition commune modifiée ouvre une nouvelle comparaison. Les valeurs qui varient par candidat restent dans sa configuration observée.

### Pi
Harnais obligatoire et constant du premier prototype. Sa constance rend les comparaisons situées ; elle ne prouve ni sa neutralité ni l'effet causal du modèle isolé.

### État de Pi
Description datée du paquet ou fork, de la version, des paquets ou extensions, des outils, des skills, du contexte et des réglages par défaut de Pi. Chaque valeur porte son statut : déclarée, configurée, active ou observée ; une valeur absente reste `INCONNU`.

### Tâche
Travail précis que le benchmark cherche à faire accomplir, avec un résultat attendu et une décision à éclairer.

### Scénario de maquette
Tâche choisie seulement pour rendre un mécanisme compréhensible dans une maquette réversible. Elle n'acquiert aucune autorité sur le benchmark futur.

## Rôles

### Demandeur-lecteur
Personne qui exprime le besoin d'une tâche et lit la restitution pour décider. Elle n'invente ni seuil, ni métrique, ni méthode de jugement.

### Responsable de campagne
Rôle qui prépare et approuve le contrat de réussite avant exécution, déclare les conditions de test communes, répond de chaque verdict et de la restitution. Les deux rôles peuvent être tenus par la même personne dans le premier prototype. Aucun rôle n'est lié à une personne, un compte, une organisation ou un pseudonyme.

## Contrat et verdict

### Contrat de réussite
Contrat préparé et approuvé par le responsable de campagne avant l'exécution d'une tâche. Il contient le résultat attendu, les obligations, les erreurs éliminatoires, les verdicts permis et au maximum deux critères secondaires.

### Résultat attendu
Artefact ou état précis que la tâche doit produire pour servir le besoin déclaré.

### Obligation
Condition que la sortie doit respecter et dont la preuve est prévue avant l'exécution.

### Erreur éliminatoire
Défaut défini avant l'exécution qui interdit le verdict `SATISFAIT`, indépendamment du coût ou d'un autre bénéfice.

### Critère secondaire
Propriété prévue avant l'exécution qui peut expliquer l'intérêt d'une configuration déjà admissible. Un contrat en contient au maximum deux. Un critère ne départage que s'il est comparable, avec une unité et un sens favorable fixés avant l'exécution ; sinon il reste descriptif.

### Verdict d'admissibilité
Conclusion d'une configuration selon le contrat de réussite : `SATISFAIT`, `NE SATISFAIT PAS` ou `INDETERMINE`. Un verdict publiable porte sa valeur, un motif court intelligible, les critères ou constats concernés, les références de preuve et son responsable.

### SATISFAIT
Verdict indiquant que la preuve observée respecte le contrat de réussite et ne présente aucune erreur éliminatoire.

### NE SATISFAIT PAS
Verdict indiquant qu'une erreur éliminatoire ou une obligation non remplie est établie.

### INDETERMINE
Verdict indiquant que la preuve disponible ne permet pas de conclure `SATISFAIT` ou `NE SATISFAIT PAS`.

## Preuve et décision

### Acquisition
Tentative autorisée et bornée d'obtenir une sortie pour une configuration et une tâche données.

### Sortie brute
Artefact produit par une configuration avant correction, transformation ou jugement.

### Erreur du harnais
Incident du dispositif de benchmark qui empêche une observation attribuable. Une erreur du harnais n'est pas un échec de la configuration.

### Coût observé
Coût imputable aux tentatives déclarées d'une configuration. Le contrat fixe avant exécution le périmètre d'attribution, les tentatives comptées, l'unité commune et, si nécessaire, la règle de conversion. Il n'est comparé qu'entre les configurations `SATISFAIT` dont les coûts sont connus et comparables ; `INCONNU` n'est ni zéro, ni estimation, ni maximum. Si le coût d'au moins une configuration `SATISFAIT` est inconnu ou non comparable, la conclusion économique reste `INCOMPLETE` et aucune option n'est déclarée globalement moins chère.

### Bénéfice prévu
Avantage d'une configuration `SATISFAIT` plus chère sur un critère secondaire défini avant l'exécution. Il n'est jamais fusionné avec le coût.

### Restitution
Surface publique en exactement deux étapes : admissibilité de toutes les configurations avec verdict et motif synthétique, puis coût observé de toutes les configurations, la recommandation économique et les bénéfices prévus restant limités aux seules configurations `SATISFAIT`. Critères, preuves, incidents, inconnues et conditions communes s'ouvrent sur demande, sans former une troisième étape.

### Attribution bornée
Limite selon laquelle le verdict décrit la configuration observée sous les conditions de test communes, sans attribuer au seul modèle un effet que le fournisseur, l'effort, Pi ou ses réglages peuvent influencer.

### Conclusion située
Conclusion bornée à la tâche, au contrat, aux configurations, aux conditions de test communes, aux preuves et à la date déclarés.

### Campagne historique
Campagne conservée sous son identité et son contrat d'origine, sans requalification par les règles actuelles.

### Élément différé
Sujet explicitement exclu du premier prototype et réexaminable seulement dans une itération ultérieure sur preuve de besoin.
