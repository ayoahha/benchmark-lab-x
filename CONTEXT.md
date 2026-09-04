---
style_gate: pass
---

# Glossaire Benchmark Lab-X

Ce glossaire fixe les termes du domaine. Il ne porte ni statut de livraison des versions, ni backlog, ni inventaire d'environnement.

## Objet du benchmark

### Modèle
Objet produit mis en avant. Un verdict sur un modèle reste borné à la configuration dans laquelle il a été observé.

### Accès direct ou API
Mode d'accès où le modèle est appelé directement ou par une API déclarée, sans produit agentique sous abonnement comme objet de comparaison.


### Configuration observée
Unité de preuve d'un candidat : fournisseur, modèle, mode d'accès, route, paramètres et effort de raisonnement, tels que demandés puis observés, reliés aux [conditions de test communes](#conditions-de-test-communes) sous lesquelles la sortie a été obtenue. Une route demandée ou observée non prouvée reste `INCONNU`.
_À éviter_ : modèle seul, solution complète.

### Conditions de test communes
Objet logique unique, déclaré avant le premier candidat et référencé par toutes les configurations comparées : état de Pi, environnement et date de gel. Une condition commune modifiée ouvre une nouvelle comparaison. Les valeurs qui varient par candidat restent dans sa configuration observée.

### Pi
Harnais commun de chaque comparaison. Sa constance rend les comparaisons situées ; elle ne prouve ni sa neutralité ni l'effet causal du modèle isolé.

### État de Pi
Description datée du paquet ou fork, de la version, des paquets ou extensions, des outils, des skills, du contexte et des réglages par défaut de Pi. Chaque valeur porte son statut : déclarée, configurée, active ou observée ; une valeur absente reste `INCONNU`.

### Tâche
Travail précis que le benchmark cherche à faire accomplir, avec un résultat attendu et une décision à éclairer.

### Version de tâche
Identité immuable reliant un contrat de réussite à des cas d'essai. Une modification après observation crée une nouvelle version.

### Cas d'essai
Entrée identifiée utilisée pour éprouver une tâche, avec les preuves attendues. Un cas n'est pas toute la tâche ; les conclusions indiquent la couverture effectivement observée.

### Catalogue
Ensemble navigable des tâches, de leurs versions et des campagnes associées.

### Panel
Liste figée des configurations sélectionnées pour une campagne, avec les révisions exigées. Sa sélection n'autorise aucun appel.

### Campagne
Exécution organisée sur une version de tâche, des cas, un panel, des conditions communes et des autorisations identifiés. Son état d'exécution est distinct de l'état d'une Issue et de sa publication.

### Scénario de maquette
Tâche choisie seulement pour rendre un mécanisme compréhensible dans une maquette réversible. Elle n'acquiert aucune autorité sur le benchmark futur.

## Rôles

### Demandeur-lecteur
Personne qui exprime le besoin d'une tâche et lit la restitution pour décider. Elle n'invente ni seuil, ni métrique, ni méthode de jugement.

### Responsable de campagne
Rôle qui prépare et approuve le contrat de réussite avant exécution, déclare les conditions de test communes, répond de chaque verdict et de la restitution. Les deux rôles peuvent être tenus par la même personne si le besoin le permet. Aucun rôle n'est lié à une personne, un compte, une organisation ou un pseudonyme.

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
Tentative autorisée et bornée d'obtenir une sortie pour une configuration, un cas et une campagne identifiés. Son intention est enregistrée avant l'appel ; une issue inconnue ne permet pas son replay.

### Sortie brute
Artefact produit par une configuration avant correction, transformation ou jugement.

### Erreur du harnais
Incident du dispositif de benchmark qui empêche une observation attribuable. Une erreur du harnais n'est pas un échec de la configuration.

### Coût observé
Coût imputable aux tentatives déclarées d'une configuration. Le contrat fixe avant exécution le périmètre d'attribution, les tentatives comptées, l'unité commune et, si nécessaire, la règle de conversion. Il n'est comparé qu'entre les configurations `SATISFAIT` dont les coûts sont connus et comparables ; `INCONNU` n'est ni zéro, ni estimation, ni maximum. Si le coût d'au moins une configuration `SATISFAIT` est inconnu ou non comparable, la conclusion économique reste `INCOMPLETE` et aucune option n'est déclarée globalement moins chère.

### Bénéfice prévu
Avantage d'une configuration `SATISFAIT` plus chère sur un critère secondaire défini avant l'exécution. Il n'est jamais fusionné avec le coût.

### Restitution
Surface publique reliant catalogue, tâche et campagne à une conclusion contextualisée, un tableau comparatif et des preuves accessibles sur demande. La recommandation économique et les bénéfices prévus restent limités aux configurations `SATISFAIT`.

### Publication
Projection explicitement approuvée d'une restitution et de ses preuves publiables. Elle n'expose pas implicitement les pièces privées ni toutes les observations en cours.

### Attribution bornée
Limite selon laquelle le verdict décrit la configuration observée sous les conditions de test communes, sans attribuer au seul modèle un effet que le fournisseur, l'effort, Pi ou ses réglages peuvent influencer.

### Conclusion située
Conclusion bornée à la version de tâche, aux cas et tentatives couverts, à la campagne, au contrat, aux configurations, aux conditions communes, aux preuves et à la date.

### Campagne historique
Campagne conservée sous son identité et son contrat d'origine, sans requalification par les règles actuelles.

### Élément différé
Sujet hors du périmètre décidé, réexaminable sur preuve de besoin et décision explicite.

## Livraison et exécution agentique

### Initiative, Epic et Story
Niveaux de la structure de livraison portée par GitHub Issues. La hiérarchie utilise Parent issue et Sub-issues progress ; Status porte l'état de travail.

### Graphe
Structure d'exécution agentique, notamment consommée par Graph Engineering Tool. Ce terme ne désigne pas la hiérarchie Initiative, Epic et Story.
