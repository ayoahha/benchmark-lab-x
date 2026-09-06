---
style_gate: pass
---

# Glossaire Benchmark Lab-X

Ce glossaire fixe les termes du domaine. Il ne porte ni statut de livraison des versions, ni backlog, ni inventaire d'environnement.

## Objet du benchmark

### Modèle
Objet produit mis en avant. Un verdict sur un modèle reste borné à la configuration dans laquelle il a été observé.

### Accès direct ou API
Mode d’accès déclaré au modèle, notamment OAuth ou API directe. Il décrit le canal utilisé ; un produit agentique sous abonnement n’est pas pour autant l’objet comparé.

### Configuration demandée
Cible figée du panel de campagne : modèle, fournisseur, accès, route, paramètres et effort requis, avec les identités exactes attendues. Sa présence dans un manifeste ne prouve ni disponibilité ni exécution.

### Configuration observée
Valeurs établies pour une tentative, avec leurs sources, reliées à la configuration demandée et aux [conditions de test communes](#conditions-de-test-communes). Une valeur absente reste `INCONNU`. Les champs et relations sont définis dans l’[ARD](docs/ARD.md#43-configuration-demandée-et-configuration-observée).
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
Identité immuable reliant un contrat approuvé, ses cas, sa référence de jugement et sa méthode d’évaluation. Son évolution suit les [règles de gel](docs/RULES.md#4-contrat-avant-exécution).

### Métier ou domaine et famille de tâche
Le métier ou domaine situe l’usage ; la famille décrit le travail demandé. Ces repères de navigation peuvent se croiser. Ils ne prouvent ni représentativité ni comparabilité ; leur rôle produit est défini dans le [PRD](docs/PRD.md#31-audience-et-accès).

### Corpus
Ensemble identifié de tâches, de cas ou de ressources, dont le périmètre est précisé : corpus de tâches du catalogue ou corpus documentaire d’un cas. Un corpus fictif décrit la nature des entrées ; une campagne réelle décrit l’acquisition effective des réponses. Les deux sont compatibles.

### Cas d'essai
Entrée identifiée utilisée pour éprouver une tâche, avec les preuves attendues. Un cas n'est pas toute la tâche ; les conclusions indiquent la couverture effectivement observée.

### Catalogue
Ensemble navigable des tâches, de leurs versions et des campagnes associées.

### Panel
Le panel nominal est la sélection de modèles du [PRD](docs/PRD.md#51-périmètre-010). Le panel d’une campagne est la liste figée des configurations demandées, avec les révisions exigées. Le second exige des identités et conditions précises que le premier ne prouve pas.

### Campagne
Ensemble organisé sur une version de tâche, des cas, un panel, des conditions communes et des autorisations identifiés. Elle relie plusieurs opérations et leurs preuves. Son état reste distinct de celui d’une Issue, des verdicts et de sa publication.

### Scénario de maquette
Tâche choisie seulement pour rendre un mécanisme compréhensible dans une maquette réversible. Elle n'acquiert aucune autorité sur le benchmark futur.

## Rôles

### Demandeur-lecteur
Personne qui exprime le besoin d'une tâche et lit la restitution pour décider. Elle n'invente ni seuil, ni métrique, ni méthode de jugement.

### Responsable de campagne
Rôle qui prépare et approuve le contrat de réussite avant exécution, déclare les conditions de test communes, répond de chaque verdict et de la restitution. Les deux rôles peuvent être tenus par la même personne si le besoin le permet. Aucun rôle n'est lié à une personne, un compte, une organisation ou un pseudonyme.

## Contrat et verdict

### Contrat de réussite
Contrat préparé et approuvé avant l’exécution, reliant le besoin aux critères vérifiables, aux cas, à l’évaluation et à la base de coût. Son contenu normatif est défini dans les [règles](docs/RULES.md#4-contrat-avant-exécution) et renseigné dans le [gabarit](tasks/TEMPLATE.md).

### Résultat attendu
Artefact ou état précis que la tâche doit produire pour servir le besoin déclaré.

### Référence de jugement
Éléments justifiant l’attendu d’un cas : faits, sources, calculs, contraintes, alternatives recevables et limites. Sa qualification établit ce que l’évaluation peut soutenir, selon les [règles du contrat](docs/RULES.md#4-contrat-avant-exécution). Elle se distingue de la sortie candidate et d’un exemple unique de bonne réponse.

### Obligation
Condition que la sortie doit respecter et dont la preuve est prévue avant l'exécution.

### Erreur éliminatoire
Défaut défini avant l'exécution qui interdit le verdict `SATISFAIT`, indépendamment du coût ou d'un autre bénéfice.

### Critère secondaire
Propriété prévue au contrat qui explique l’intérêt d’une configuration admissible. Ses conditions d’usage sont définies par les [règles de coût et bénéfices](docs/RULES.md#8-coût-et-bénéfices).

### Verdict d'admissibilité
Conclusion d'une configuration selon le contrat de réussite : `SATISFAIT`, `NE SATISFAIT PAS` ou `INDETERMINE`. Un verdict publiable porte sa valeur, un motif court intelligible, les critères ou constats concernés, les références de preuve et son responsable.

### SATISFAIT
Verdict indiquant que la preuve observée respecte le contrat de réussite et ne présente aucune erreur éliminatoire.

### NE SATISFAIT PAS
Verdict indiquant qu'une erreur éliminatoire ou une obligation non remplie est établie.

### INDETERMINE
Verdict indiquant que la preuve disponible ne permet pas de conclure `SATISFAIT` ou `NE SATISFAIT PAS`.

## Preuve et décision

### Exécution du produit
Déroulement identifié d’une opération sur une campagne, avec version du moteur, entrées, autorité et reçu. Préparer, acquérir, évaluer et construire une restitution sont des opérations différentes ; toutes ne contiennent pas un appel candidat.

### Tentative
Intention d’appel identifiée pour un cas et une configuration demandée. Elle peut aboutir à une sortie, un incident ou des effets inconnus. Une tentative locale ne prouve pas un appel reçu par le fournisseur ; une cellule jamais lancée n’est pas une tentative.

### Acquisition
Opération autorisée visant à obtenir et conserver une sortie. Elle relie les tentatives à leurs observations et reçus, sans prononcer leur verdict. Le cycle de vie est défini dans l’[ARD](docs/ARD.md#123-interfaces-et-cycle-de-vie).

### Observation, évaluation et conclusion
L’observation rapporte ce qui a été obtenu, avec sa provenance. L’évaluation applique le contrat à ces observations. La conclusion relie les évaluations compatibles à la décision permise ; aucune de ces étapes ne remplace sa source.

### Sortie brute
Artefact produit par une configuration avant correction, transformation ou jugement.

### Pièce
Artefact identifié utilisé comme source ou preuve : entrée figée, sortie brute ou extrait identifié. Les métadonnées le décrivent et le relient aux autres objets sans en remplacer le contenu.

### Reçu
Enregistrement d’une opération ou tentative, avec identité, chronologie, effets établis ou inconnus et liens aux pièces. Il peut lui-même être conservé comme pièce ; il ne décide pas du verdict.

### Erreur du harnais
Incident du dispositif de benchmark qui empêche une observation attribuable. Une erreur du harnais n'est pas un échec de la configuration.

### Coût observé
Dépense établie par une source pour les tentatives imputables selon la base de coût du contrat. Elle est distincte du prix affiché, de la prévision, de la réservation et du plafond. Les [règles économiques](docs/RULES.md#8-coût-et-bénéfices) gouvernent les inconnues et la comparaison.

### Bénéfice prévu
Avantage d'une configuration `SATISFAIT` plus chère sur un critère secondaire défini avant l'exécution. Il n'est jamais fusionné avec le coût.

### Restitution
Présentation reliant tâche et campagne à la conclusion, à la comparaison et aux preuves. Elle peut être locale et privée ; son exposition publique passe par une publication approuvée.

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

### Version du produit
Numéro SemVer identifiant une livraison du logiciel selon les [règles de versionnement](docs/RULES.md#14-versionnement-du-produit). Il est distinct de la version d’une tâche, d’un schéma de données ou d’un modèle.

### Jalon
Périmètre produit et critères d’acceptation associés à une version cible. Son suivi dans GitHub ne prouve pas à lui seul la livraison ni l’exécution des campagnes.

### Initiative, Epic et Story
Niveaux de la structure de livraison portée par GitHub Issues. La hiérarchie utilise Parent issue et Sub-issues progress ; Status porte l'état de travail.

### Graphe
Structure d'exécution agentique, notamment consommée par Graph Engineering Tool. Ce terme ne désigne pas la hiérarchie Initiative, Epic et Story.
