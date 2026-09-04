---
style_gate: pass
---

# Carte de tâche : `<nom lisible>`

Suivi de livraison : `<Issue ; Status dans le Project>`

L'état d'exécution de chaque campagne appartient à ses reçus ; il n'est pas déduit du suivi de livraison.

Ce gabarit prépare une version de tâche. Les sections 1 à 4 définissent le contrat ; les suivantes décrivent les informations à référencer depuis chaque manifeste de campagne et restitution, sans les dupliquer dans une version gelée. Une nouvelle campagne ne modifie pas le contrat. Une carte approuvée n'autorise ni acquisition, ni dépense, ni publication.

Toute extension suit la [règle KISS](../docs/RULES.md#11-kiss-et-évolution).

## 1. Identité et autorité

| Champ | Valeur |
|---|---|
| Identifiant stable de tâche | `<slug décidé>` |
| Version de tâche | `<identité et empreinte du contrat et des cas>` |
| Tâche | `<travail précis>` |
| Titre public | `<titre lisible de la tâche, repris tel quel par la restitution>` |
| Demandeur-lecteur | `<besoin exprimé par ce rôle>` |
| Responsable de campagne | `<rôle tenu, sans identité codée>` |
| Date de préparation | `<date>` |
| Approbation du responsable de campagne avant exécution | `EN_ATTENTE` / `<preuve et date>` |

Une valeur `EN_ATTENTE` interdit l'exécution. Le demandeur-lecteur fournit son besoin ; le responsable de campagne prépare et approuve le contrat. Les deux rôles peuvent être tenus par la même personne.

## 2. Besoin et résultat attendu

### Situation

`<acteur, contexte et besoin>`

### Résultat attendu

`<artefact ou état précis qui sert le besoin>`

### Décision éclairée

`<choix entre des modèles sur cette tâche précise>`

### Conclusion permise

`<conclusion bornée à la version, aux cas et tentatives couverts, à la campagne, aux configurations, aux conditions communes et à la date>`

### Conclusions interdites

- meilleur modèle absolu
- classement universel
- podium général ou graphique trompeur
- effet causal du modèle isolé, ou effet attribué au seul modèle alors que le fournisseur, l'effort, Pi ou ses réglages peuvent l'influencer
- conclusion hors de la tâche ou du contrat
- requalification des campagnes historiques

## 3. Entrées et sortie brute

### Cas d'essai

| Cas | Entrée exacte | Identité ou empreinte | Difficulté couverte | Preuves attendues |
|---|---|---|---|---|
| `<id>` | `<texte ou référence>` | `<identité>` | `<motif du choix>` | `<références>` |

Couverture et limites : `<cas retenus et portée réellement recherchée>`.

Règle d'agrégation des verdicts : `<règle fixée avant exécution, ou AUCUNE : verdicts par cas seulement>`.

### Entrées et outils autorisés

| Élément | Rôle | Visible au candidat | Identité ou empreinte |
|---|---|:---:|---|
| `<entrée ou outil>` | `<rôle>` | oui / non | `<version, SHA-256 ou INCONNU>` |

Tout élément non listé est indisponible. Aucun secret ou chemin externe n'est autorisé sans décision explicite.

### Sortie brute attendue

`<artefact, encodage et emplacement attendus>`

La sortie brute est conservée avant contrôle ou jugement. Aucun post-traitement silencieux n'est permis.

## 4. Contrat de réussite

### Obligations

| ID | Obligation | Preuve attendue |
|---|---|---|
| `O1` | `<condition obligatoire>` | `<observation prévue avant exécution>` |

### Erreurs éliminatoires

| ID | Erreur | Preuve | Effet |
|---|---|---|---|
| `E1` | `<défaut précis>` | `<observation>` | interdit `SATISFAIT` |

### Critères secondaires

Conserver au maximum deux lignes. Un critère est défini avant l'exécution et sert seulement à expliquer le bénéfice d'une configuration déjà `SATISFAIT`. Sans unité et sens favorable fixés ici, il reste descriptif et ne départage pas.

| ID | Critère | Question observable | Unité | Sens favorable | Preuve |
|---|---|---|---|---|---|
| `S1` | `<nom>` | `<question>` | `<unité ou descriptif>` | `<plus haut / plus bas / oui>` | `<observation>` |
| `S2` | `<nom ou supprimer la ligne>` | `<question>` | `<unité ou descriptif>` | `<plus haut / plus bas / oui>` | `<observation>` |

### Verdicts

- `SATISFAIT` : résultat attendu et obligations prouvés, aucune erreur éliminatoire
- `NE SATISFAIT PAS` : erreur éliminatoire ou obligation non remplie établie
- `INDETERMINE` : preuve insuffisante ou contradictoire

Aucun autre verdict, score global ou seuil ajouté après résultat n'est permis.

## 5. Références de campagne et de panel

Ces informations appartiennent au manifeste de chaque campagne, référencé par le catalogue ; elles ne réécrivent pas la version de tâche.

| Champ | Valeur |
|---|---|
| Campagne | `<identité>` |
| Version de tâche et cas retenus | `<références et empreintes>` |
| Panel figé | `<référence et empreinte>` |
| Autorité d'exécution produit | `<référence ou ABSENTE>` |
| Autorité des appels candidats et budget | `<référence ou ABSENTE>` |
| Autorité de publication | `<référence ou ABSENTE>` |

Pour chaque configuration du panel, conserver :

| Champ | Valeur |
|---|---|
| Identifiant de configuration | `<identité>` |
| Modèle et révision imposée | `<nom, version exacte et preuve attendue>` |
| Fournisseur et accès direct ou API | `<valeurs>` |
| Identifiant utilisable sur le canal | `<identifiant vérifié, ou INCONNU>` |
| Route demandée et route observée | `<valeurs distinctes, ou INCONNU>` |
| Paramètres et effort demandés puis observés | `<valeurs distinctes, ou INCONNU>` |
| Identité observée | `<valeur et preuve, ou INCONNU>` |

La sélection d'un nom ne prouve pas sa disponibilité. Une révision imposée ne peut pas être remplacée silencieusement. Pour un modèle local autorisé, relever aussi poids, quantification, serveur d'inférence et matériel. Les conditions communes sont référencées une fois en section 6.

## 6. Conditions de test communes

Déclarées et figées dans le manifeste de campagne avant le premier candidat, puis référencées par toutes les configurations de son panel.

| Champ | Valeur commune figée | Statut |
|---|---|---|
| Paquet ou fork Pi | `<valeur>` | `<déclarée / configurée / active / observée>` |
| Version exécutée | `<valeur ou INCONNU>` | `<statut>` |
| Paquets ou extensions | `<identifiants exacts ou aucun>` | `<statut>` |
| Outils | `<liste ou aucun>` | `<statut>` |
| Skills | `<état>` | `<statut>` |
| Contexte | `<identité ou empreinte>` | `<statut>` |
| Réglages par défaut de Pi | `<fournisseur, modèle et effort par défaut>` | `<statut>` |
| Environnement | `<valeur>` | `<statut>` |
| Date de gel | `<date>` | observée |

Tout changement d'un de ces champs ouvre une nouvelle comparaison. Pi reste le harnais commun. L'environnement identifié doit rester disponible pendant la campagne malgré les mises à jour du poste ou du site.

## 7. Acquisition et incidents

### Autorisation propre à la campagne

| Champ | Valeur |
|---|---|
| Tentatives autorisées par cas et configuration | `<règle et autorité, ou aucune>` |
| Retries autorisés | `<règle et autorité, ou aucun>` |
| Dépense maximale | `<montant, devise, périmètre et autorité, ou zéro>` |
| Durée et arrêt | `<limites décidées ou mesurées, sans valeur inventée>` |

Une autorité absente interdit l'opération correspondante. Ces valeurs appartiennent au manifeste de campagne.

### Base de coût fixée avant exécution

| Champ | Valeur |
|---|---|
| Périmètre d'attribution | `<coûts inclus et exclus>` |
| Tentatives comptées | `<première tentative, retries autorisés, incidents>` |
| Unité commune | `<devise et unité>` |
| Règle de conversion | `<source, date et formule, ou SANS OBJET>` |

| Champ | Valeur |
|---|---|
| Les cas et tentatives prévus suffisent-ils à la conclusion permise ? | `<justification et limites ; aucune fiabilité générale déduite d'un seul cas>` |
| Politique de retry | `<règle autorisée ou aucun>` |
| Règle d'arrêt | `<condition>` |
| Source du coût observé | `<reçu, ou INCONNU>` |

| Classe | Preuve | Effet |
|---|---|---|
| Sortie obtenue | artefact relié au reçu | appliquer le contrat |
| Incident fournisseur | preuve attribuable | publier séparément |
| `HARNESS_ERROR` | défaut du dispositif | réduire la couverture, sans produire `NE SATISFAIT PAS` |
| Preuve manquante | champ requis absent | `INDETERMINE` ou `INCONNU` |

Répétitions et statistiques exigent une justification et une règle préalable. Prévision, réservation, coût observé et limite fournisseur restent distincts. Une tentative aux effets inconnus ne doit pas être rejouée ; les observations d'une campagne partielle restent conservées.

## 8. Verdicts et décision économique

La restitution référence les verdicts par cas, les tentatives et les reçus de la campagne, sans les recopier dans le contrat gelé.

| Cas et tentative | Configuration | Erreurs et obligations | Verdict | Motif et critères concernés | Preuves | Coût observé | Bénéfices prévus |
|---|---|---|---|---|---|---|---|
| `<identités>` | `<identité>` | `<constats>` | `<verdict>` | `<motif et références>` | `<pièces et passages>` | `<valeur et unité, ou INCONNU>` | `<faits ou AUCUN>` |

Une synthèse multi-cas applique uniquement la règle d'agrégation du contrat et affiche sa couverture.

Responsable des verdicts : `<rôle>`.

Appliquer l'ordre suivant :

1. erreurs éliminatoires ;
2. obligations et preuve ;
3. verdict ;
4. exclusion de `NE SATISFAIT PAS` et `INDETERMINE` de la recommandation économique ;
5. coût connu et comparable parmi les seuls `SATISFAIT` ;
6. bénéfices prévus des `SATISFAIT` plus chers.

La page campagne expose la conclusion contextualisée, un tableau commun des configurations puis les preuves sur demande. Cet ordre de lecture ne modifie pas l'ordre de calcul. La recommandation économique reste limitée aux configurations `SATISFAIT`.

### Conclusion économique

`<COMPLETE si tous les coûts SATISFAIT sont connus et comparables ; sinon INCOMPLETE>`

### Configurations `SATISFAIT` co-moins-chères

`<identités, ou AUCUNE ; si la conclusion est INCOMPLETE, aucune option n'est déclarée globalement moins chère>`

Un coût inconnu ou non comparable peut conserver l'admissibilité sur les critères non économiques ; les coûts connus restent visibles, mais la conclusion économique est `INCOMPLETE`. Cette mention n'est pas un quatrième verdict. Un coût `INCONNU` ne satisfait jamais une obligation de coût et ne prouve aucune supériorité économique.

### Bénéfices prévus des options `SATISFAIT` plus chères

`<liens aux seuls critères secondaires déclarés, ou AUCUN>`

## 9. Publication et limite d'attribution

Pièces publiables : `<entrées, sorties et passages approuvés>`.

Pièces privées et limites de vérification publique : `<références et motifs>`.

La publication référence son autorité et sa version de restitution. Aucun contenu candidat n'est interprété comme code actif dans le site.

La restitution contient cette formulation ou son équivalent :

> Le verdict porte sur la configuration observée sous les conditions de test communes déclarées. Il n'attribue pas au seul modèle un effet que le fournisseur, l'effort, Pi ou ses réglages peuvent influencer, et ne démontre pas que le modèle isolé aurait produit le même résultat sous un autre harnais, fournisseur, contexte ou environnement.

## 10. Qualification documentaire

- [ ] version, cas et preuves attendues sont identifiés ; la couverture est justifiée
- [ ] résultat attendu, obligations et erreurs éliminatoires sont définis avant exécution
- [ ] toute agrégation des cas est définie avant exécution, sinon seuls les verdicts par cas sont permis
- [ ] chaque campagne référence le contrat sans le réécrire ; ses autorités et états restent distincts
- [ ] les trois verdicts sont présents
- [ ] zéro à deux critères secondaires sont prévus, avec unité et sens favorable s'ils départagent
- [ ] le responsable de campagne a approuvé le contrat ou l'exécution reste interdite
- [ ] les conditions de test communes sont déclarées une fois et identiques entre les configurations comparées
- [ ] chaque configuration expose ses valeurs propres, dont l'effort de raisonnement effectif
- [ ] chaque configuration distingue sa route demandée de sa route observée ; toute valeur non prouvée reste `INCONNU`
- [ ] la base de coût fixe le périmètre d'attribution, les tentatives comptées, l'unité commune et la conversion éventuelle avant exécution
- [ ] chaque verdict porte un motif, ses preuves et son responsable
- [ ] le coût observé de chaque configuration reste visible ; les non-`SATISFAIT` sont exclus de la recommandation économique et la conclusion est `INCOMPLETE` si un coût `SATISFAIT` est inconnu ou non comparable
- [ ] aucun score global, podium général, classement universel ou graphique trompeur n'est produit
- [ ] la limite d'attribution est visible
- [ ] les éléments différés restent absents
- [ ] la conclusion est bornée au contrat, aux cas et tentatives couverts, à la campagne, aux conditions communes et à la date
- [ ] les pièces publiables sont autorisées et les restrictions sont visibles

Un scénario de maquette ne devient pas implicitement une tâche du catalogue.
