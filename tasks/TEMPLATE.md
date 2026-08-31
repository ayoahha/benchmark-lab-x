---
style_gate: pass
---

# Carte de tâche : `<nom lisible>`

Statut de campagne : `<porté par l'Issue et le champ Status du Project>`

Ce gabarit prépare le contrat minimal d'une tâche du premier prototype. Une carte approuvée n'autorise ni acquisition, ni campagne, ni publication.

Toute extension suit la [règle KISS](../docs/specification/RULES.md#11-kiss-et-évolution).

## 1. Identité et autorité

| Champ | Valeur |
|---|---|
| Identifiant de la carte | `<slug non canonique>` |
| Tâche | `<travail précis>` |
| Demandeur-lecteur | `<besoin exprimé par ce rôle>` |
| Responsable de campagne | `<rôle tenu, sans identité codée>` |
| Date de préparation | `<date>` |
| Approbation du responsable de campagne avant exécution | `EN_ATTENTE` / `<preuve et date>` |
| Appels candidats autorisés | `aucun` / `<autorité exacte>` |
| Retries autorisés | `aucun` / `<autorité exacte>` |
| Dépense maximale | `zéro` / `<montant, devise et périmètre>` |

Une valeur `EN_ATTENTE` interdit l'exécution. Le demandeur-lecteur fournit son besoin ; le responsable de campagne prépare et approuve le contrat. Les deux rôles peuvent être tenus par la même personne.

## 2. Besoin et résultat attendu

### Situation

`<acteur, contexte et besoin>`

### Résultat attendu

`<artefact ou état précis qui sert le besoin>`

### Décision éclairée

`<choix entre des modèles sur cette tâche précise>`

### Conclusion permise

`<conclusion bornée à la tâche, au contrat, aux configurations, aux conditions de test communes et à la date>`

### Conclusions interdites

- meilleur modèle absolu
- classement universel
- podium général ou graphique trompeur
- effet causal du modèle isolé, ou effet attribué au seul modèle alors que le fournisseur, l'effort, Pi ou ses réglages peuvent l'influencer
- conclusion hors de la tâche ou du contrat
- requalification de V0 ou V1

## 3. Entrées et sortie brute

### Stimulus

`<texte exact ou chemin versionné>`

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

## 5. Configurations modèle plus accès direct ou API

| Champ | Configuration A | Configuration B |
|---|---|---|
| Fournisseur | `<valeur>` | `<valeur>` |
| Modèle | `<valeur>` | `<valeur>` |
| Accès direct ou API | `<valeur>` | `<valeur>` |
| Route demandée | `<valeur ou INCONNU>` | `<valeur ou INCONNU>` |
| Route observée | `<valeur ou INCONNU>` | `<valeur ou INCONNU>` |
| Paramètres | `<valeurs>` | `<valeurs>` |
| Effort de raisonnement | `<valeur effective ou INCONNU>` | `<valeur effective ou INCONNU>` |
| Identité observée requise | `<preuve>` | `<preuve>` |

Ajouter seulement les colonnes nécessaires au panel autorisé. Les conditions de test communes ne sont pas répétées ici : elles vivent en section 6. Les abonnements et produits agentiques ne sont pas des configurations actives de ce gabarit.

## 6. Conditions de test communes

Déclarées une fois, avant le premier candidat, et référencées par toutes les configurations de la section 5.

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

Tout changement d'un de ces champs ouvre une nouvelle comparaison. Pi est obligatoire ; la carte ne propose ni harnais alternatif, ni comparaison de harnais.

## 7. Acquisition et incidents

### Base de coût fixée avant exécution

| Champ | Valeur |
|---|---|
| Périmètre d'attribution | `<coûts inclus et exclus>` |
| Tentatives comptées | `<première tentative, retries autorisés, incidents>` |
| Unité commune | `<devise et unité>` |
| Règle de conversion | `<source, date et formule, ou SANS OBJET>` |

| Champ | Valeur |
|---|---|
| Une acquisition par configuration suffit-elle à la conclusion permise ? | `<oui justifié / non et besoin observé>` |
| Politique de retry | `<règle autorisée ou aucun>` |
| Règle d'arrêt | `<condition>` |
| Source du coût observé | `<reçu, ou INCONNU>` |

| Classe | Preuve | Effet |
|---|---|---|
| Sortie obtenue | artefact relié au reçu | appliquer le contrat |
| Incident fournisseur | preuve attribuable | publier séparément |
| `HARNESS_ERROR` | défaut du dispositif | réduire la couverture, sans produire `NE SATISFAIT PAS` |
| Preuve manquante | champ requis absent | `INDETERMINE` ou `INCONNU` |

Répétitions et statistiques restent absentes tant que la règle KISS n'autorise pas leur ajout.

## 8. Verdicts et décision économique

| Configuration | Erreurs éliminatoires | Obligations | Verdict | Motif court | Critères ou constats concernés | Preuves | Coût observé | Bénéfices sur S1 ou S2 |
|---|---|---|---|---|---|---|---|---|
| A | `<résultat>` | `<résultat>` | `<verdict>` | `<phrase intelligible expliquant le verdict>` | `<identifiants O, E ou S concernés>` | `<références>` | `<valeur et unité, ou INCONNU>` | `<faits>` |
| B | `<résultat>` | `<résultat>` | `<verdict>` | `<phrase intelligible expliquant le verdict>` | `<identifiants O, E ou S concernés>` | `<références>` | `<valeur et unité, ou INCONNU>` | `<faits>` |

Responsable des verdicts : `<rôle>`.

Appliquer l'ordre suivant :

1. erreurs éliminatoires ;
2. obligations et preuve ;
3. verdict ;
4. exclusion de `NE SATISFAIT PAS` et `INDETERMINE` ;
5. coût connu et comparable parmi les seuls `SATISFAIT` ;
6. bénéfices prévus des `SATISFAIT` plus chers.

Ces six opérations restent internes. La restitution publique en montre deux étapes : les verdicts et leurs motifs, puis les coûts connus et comparables, la conclusion économique et les bénéfices prévus ; le reste s'ouvre sur demande.

### Conclusion économique

`<COMPLETE si tous les coûts SATISFAIT sont connus et comparables ; sinon INCOMPLETE>`

### Configurations `SATISFAIT` co-moins-chères

`<identités, ou AUCUNE ; si la conclusion est INCOMPLETE, aucune option n'est déclarée globalement moins chère>`

Un coût inconnu ou non comparable peut conserver l'admissibilité sur les critères non économiques ; les coûts connus restent visibles, mais la conclusion économique est `INCOMPLETE`. Cette mention n'est pas un quatrième verdict. Un coût `INCONNU` ne satisfait jamais une obligation de coût et ne prouve aucune supériorité économique.

### Bénéfices prévus des options `SATISFAIT` plus chères

`<liens aux seuls critères S1 et S2 déclarés, ou AUCUN>`

## 9. Limite d'attribution

La restitution contient cette formulation ou son équivalent :

> Le verdict porte sur la configuration observée sous les conditions de test communes déclarées. Il n'attribue pas au seul modèle un effet que le fournisseur, l'effort, Pi ou ses réglages peuvent influencer, et ne démontre pas que le modèle isolé aurait produit le même résultat sous un autre harnais, fournisseur, contexte ou environnement.

## 10. Qualification documentaire

- [ ] résultat attendu, obligations et erreurs éliminatoires sont définis avant exécution
- [ ] les trois verdicts sont présents
- [ ] zéro à deux critères secondaires sont prévus, avec unité et sens favorable s'ils départagent
- [ ] le responsable de campagne a approuvé le contrat ou l'exécution reste interdite
- [ ] les conditions de test communes sont déclarées une fois et identiques entre les configurations comparées
- [ ] chaque configuration expose ses valeurs propres, dont l'effort de raisonnement effectif
- [ ] chaque configuration distingue sa route demandée de sa route observée ; toute valeur non prouvée reste `INCONNU`
- [ ] la base de coût fixe le périmètre d'attribution, les tentatives comptées, l'unité commune et la conversion éventuelle avant exécution
- [ ] chaque verdict porte un motif, ses preuves et son responsable
- [ ] les non-`SATISFAIT` sont exclus de la comparaison économique et la conclusion est `INCOMPLETE` si un coût `SATISFAIT` est inconnu ou non comparable
- [ ] aucun score global, podium général, classement universel ou graphique trompeur n'est produit
- [ ] la limite d'attribution est visible
- [ ] les éléments différés restent absents
- [ ] la conclusion est bornée au contrat, aux conditions communes et à la date

Le scénario `quote-thread-summary`, s'il est utilisé dans une maquette, reste un choix local réversible et ne devient pas une tâche canonique.
