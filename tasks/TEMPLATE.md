---
style_gate: pass
---

# Carte de tâche : `<nom lisible>`

Ce gabarit prépare le contrat d’une tâche de benchmark, distinct d’une Story de livraison. Les sections 1 à 4 définissent le contrat à geler. L’empreinte porte sur le contenu contractuel identifié, sans sa propre valeur ni les enregistrements marqués hors empreinte. Les sections 5 à 7 décrivent le manifeste de campagne et les enregistrements d’exploitation qui lui sont liés ; les sections 8 et 9 concernent les résultats et la publication. Les observations et autorisations acquises après le gel ne réécrivent ni le contrat ni le manifeste.

Le suivi GitHub reste extérieur à la carte : état de l’Issue, `Status` du Project et progrès des sous-Issues ne décrivent pas l’exécution d’une campagne. Une carte approuvée n’autorise ni acquisition, ni dépense, ni publication.

Toute extension suit la [règle KISS](../docs/RULES.md#11-kiss-et-évolution).

## 1. Identité et autorité

| Champ | Valeur |
|---|---|
| Identifiant stable de tâche | `<slug décidé>` |
| Version de tâche | `<identité et empreinte du contrat, des cas, de la référence de jugement et de la méthode d’évaluation>` |
| Tâche | `<travail précis>` |
| Métier ou domaine ; famille de tâche | `<contexte d’usage ; travail demandé, sans comparabilité implicite>` |
| Titre public | `<titre lisible de la tâche, repris tel quel par la restitution>` |
| Demandeur-lecteur | `<besoin exprimé par ce rôle>` |
| Responsable de campagne | `<rôle et référence de responsabilité vérifiable ; identité privée si nécessaire>` |
| Date de préparation | `<date>` |

Approbation du responsable de campagne avant exécution, hors empreinte du contrat : `EN_ATTENTE` / `<preuve et date, référençant l’empreinte du contrat et les preuves de qualification>`. Cette preuve est liée au contrat sans entrer dans l’empreinte qu’elle approuve.

Une valeur `EN_ATTENTE` interdit l'exécution. Le demandeur-lecteur fournit son besoin ; le responsable de campagne prépare et approuve le contrat. Les deux rôles peuvent être tenus par la même personne.

## 2. Besoin et résultat attendu

### Situation

`<acteur, contexte et besoin>`

### Résultat attendu

`<artefact ou état précis qui sert le besoin ; propriétés réellement mesurées et propriétés non évaluées>`

Usage du résultat et intervention humaine : `<ce que le destinataire peut en faire ; relecture, adaptations ou corrections nécessaires admises par le contrat>`.

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

| Cas | Entrée exacte et provenance | Identité ou empreinte | Charge et difficulté décrites | Preuves attendues |
|---|---|---|---|---|
| `<id>` | `<texte ou référence>` | `<identité>` | `<quantité et unité pertinentes ; contraintes concrètes et motif du choix>` | `<références>` |

Niveau éventuel : `<définition et dimensions approuvées avant exécution, ou NON DÉFINI>`. Décrire les caractéristiques qui varient entre cas et celles qui restent communes, selon les [règles de charge et de portée](../docs/RULES.md#4-contrat-avant-exécution). Une étiquette ne remplace pas cette description.

Couverture et limites : `<motif de sélection, usages couverts et exclus, nature synthétique ou réelle, biais connus et limites de généralisation>`.

Règle d’agrégation : `<forme et portée du résultat ; cas et tentatives pris en compte, dénominateur, traitement des manquants, incidents et INDETERMINE ; ou AUCUNE : verdicts par cas et tentative seulement>`.

### Entrées et outils autorisés

| Élément | Rôle | Visible au candidat | Identité ou empreinte |
|---|---|:---:|---|
| `<entrée ou outil>` | `<rôle>` | oui / non | `<version, SHA-256 ou INCONNU>` |

Modalité documentaire, si pertinente : `<textes utiles fournis, recherche dans une bibliothèque figée ou consultation externe autorisée ; corpus, versions et droits ; preuves prévues des requêtes et pièces consultées>`.

Tout élément non listé est indisponible. Aucun secret ou chemin externe n'est autorisé sans décision explicite.

### Sortie brute attendue

`<artefact, encodage et emplacement attendus>`

La sortie brute est conservée avant contrôle ou jugement. Aucun post-traitement silencieux n'est permis.

## 4. Contrat de réussite

### Obligations

| ID | Obligation | Preuve attendue |
|---|---|---|
| `O1` | `<condition nécessaire à l’usage ; motif et tolérances recevables propres à ce critère>` | `<contrôle, version, observation et pièce attendue>` |

### Erreurs éliminatoires

| ID | Erreur | Preuve | Effet |
|---|---|---|---|
| `E1` | `<défaut précis, avec limites ou tolérances propres à cette condition>` | `<contrôle, version et observation>` | interdit `SATISFAIT` |

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

Appliquer les [règles de verdict](../docs/RULES.md#6-erreurs-et-verdict), notamment lorsqu’un défaut est prouvé mais qu’un autre contrôle manque.

### Référence et méthode d’évaluation

Référence de jugement : `<identité et empreinte ; attendus reliés aux passages, calculs ou contraintes ; solutions alternatives recevables ; informations insuffisantes et points discutables>`.

Qualification avant approbation, enregistrée hors empreinte du contrat : `<preuves référençant le contrat candidat exact ; vérification de la consigne, des cas, de la référence et des contrôles ; témoins adaptés de réussite, de défaut et d’alternative valable lorsqu’il en existe ; ambiguïtés lorsqu’elles sont prévues ; limites non résolues>`.

Méthode : `<contrôles automatiques et témoins prévus identifiés et versionnés ; jugement humain ou assisté, configuration et consignes prévues de l’assistance IA éventuelle ; responsable, constats et approbation requis ; visibilité de l’identité et du coût pendant le jugement>`.

Revue de la référence et de la méthode avant approbation, enregistrée hors empreinte du contrat : `<auteurs et pièces ; pour chaque assistance IA, configuration, consignes et sources, critiques, désaccords et arbitrage ; revue professionnelle : phase, périmètre et preuve, ou ABSENTE ; limites restantes>`. Appliquer les [règles de qualification et de revue](../docs/RULES.md#4-contrat-avant-exécution).

Exposition connue avant approbation : `<part de la référence visible au candidat ; connaissance préalable des cas par les modèles ou évaluateurs, si connue ; protections et limites>`. Une référence incertaine suit les [règles de verdict](../docs/RULES.md#6-erreurs-et-verdict).

### Base de coût fixée avant exécution

| Champ | Valeur |
|---|---|
| Périmètre d'attribution | `<coûts inclus et exclus ; préparation et jugement distingués, avec règle d’imputation s’ils entrent dans la comparaison>` |
| Tentatives comptées | `<première tentative, retries autorisés, incidents>` |
| Unité commune | `<devise et unité>` |
| Règle de conversion | `<source, date et formule, ou SANS OBJET>` |

La base fixe aussi l’unité de travail comparable : `<cas et quantité de travail auxquels le coût se rapporte>`. Les prix datés, prévisions, réservations et dépenses observées appartiennent à la campagne ; ils ne réécrivent pas cette base.

## 5. Références de campagne et de panel

Le manifeste de chaque campagne, référencé par le catalogue, fige les informations suivantes sans réécrire la version de tâche.

| Champ | Valeur |
|---|---|
| Campagne et version de manifeste | `<identité et empreinte>` |
| Moteur prévu | `<version et interfaces retenues>` |
| Version de tâche et cas retenus | `<références et empreintes>` |
| Panel figé | `<référence et empreinte>` |

Liens entre l’assistance IA et ce panel : `<modèle ou fournisseur commun à la préparation, au jugement et aux candidats ; exposition connue lors de la campagne, protections et limites>`, selon les [règles de revue](../docs/RULES.md#4-contrat-avant-exécution).

Autorités liées au manifeste : exécution produit `<référence ou ABSENTE>` ; appels candidats et budget `<référence ou ABSENTE>`. Leur preuve, comme celle d’une reprise ultérieure, est conservée séparément des conditions figées. L’autorité de publication est référencée en section 9.

Pour chaque configuration demandée du panel, conserver :

| Champ | Valeur |
|---|---|
| Identifiant de configuration | `<identité>` |
| Modèle et révision imposée | `<nom, version exacte et preuve attendue>` |
| Fournisseur et accès direct ou API | `<valeurs>` |
| Identifiant utilisable sur le canal | `<identifiant vérifié, ou INCONNU>` |
| Route demandée | `<valeur, ou INCONNU>` |
| Paramètres et effort demandés | `<valeurs, ou INCONNU>` |
| Observations exigées | `<sources, champs ou pièces observables attendus pour prouver l’identité, la route, les paramètres et l’effort>` |

La sélection d'un nom ne prouve pas sa disponibilité. Une révision imposée ne peut pas être remplacée silencieusement. Pour un modèle local autorisé, relever aussi poids, quantification, serveur d'inférence et matériel. Les conditions communes sont référencées une fois en section 6.

## 6. Conditions de test communes

Déclarées et figées dans le manifeste de campagne avant le premier candidat, puis référencées par toutes les configurations de son panel.

| Champ | Valeur commune figée | Statut |
|---|---|---|
| Paquet ou fork Pi | `<valeur>` | `<déclarée / configurée / active / observée>` |
| Version exécutée et empreinte de Pi | `<valeurs ou INCONNU>` | `<statut>` |
| Paquets ou extensions | `<identifiants exacts ou aucun>` | `<statut>` |
| Outils | `<liste ou aucun>` | `<statut>` |
| Skills | `<état>` | `<statut>` |
| Contexte | `<identité ou empreinte>` | `<statut>` |
| Réglages par défaut de Pi | `<fournisseur, modèle et effort par défaut>` | `<statut>` |
| Environnement | `<système, matériel, runtimes, dépendances et identités nécessaires à l’attribution>` | `<statut>` |
| Date de gel | `<date>` | observée |

Chaque valeur référence sa preuve et sa date. Les [règles de gel](../docs/RULES.md#4-contrat-avant-exécution) et l’[identité d’environnement](../docs/ARD.md#31-identité-de-lenvironnement-dexécution) s’appliquent. Les réglages influents non observables et les limites de reproduction sont déclarés.

## 7. Acquisition et incidents

### Autorisation propre à la campagne

| Champ | Valeur |
|---|---|
| Tentatives autorisées par cas et configuration | `<règle et autorité, ou aucune>` |
| Retries autorisés | `<règle et autorité, ou aucun>` |
| Dépense maximale | `<montant, devise, périmètre et autorité, ou ABSENTE : appel interdit>` |
| Durée et arrêt | `<limites décidées ou mesurées, sans valeur inventée>` |

Une autorité absente interdit l’opération correspondante. Le manifeste fixe aussi le plan d’ordre, les répétitions éventuelles et leur justification ; aucun nombre n’est imposé par le gabarit. La reprise doit nommer les cellules encore autorisées et les effets acquis, selon les [règles d’admission et de reprise](../docs/RULES.md#9-incidents-et-inconnues).

La base de coût est celle du contrat en section 4. Chaque campagne lui associe :

| Champ | Valeur |
|---|---|
| Prix et prévision avant appel | `<source datée, calcul, périmètre et limite de facturation connue>` |
| Réservations et dépenses | `<registre lié aux tentatives ; coût observé sourcé ou INCONNU>` |
| Admission | `<preuve des identités, conditions, stockage, autorités et budget avant émission>` |
| Interruption ou reprise | `<motif, intentions, reçus et effets inconnus conservés ; autorité de reprise éventuelle>` |

Les incidents conservent leur preuve et leur portée. Leur effet sur l’évaluation suit les [règles de verdict](../docs/RULES.md#6-erreurs-et-verdict) ; la couverture manquante reste visible.

## 8. Verdicts et décision économique

La restitution référence les verdicts par cas, les tentatives et les reçus de la campagne, sans les recopier dans le contrat gelé. Chaque opération conserve son identifiant d’exécution, sa version réelle du moteur, ses entrées, son autorité et sa terminaison. Chaque tentative relie la demande figée aux valeurs observées de fournisseur, modèle, accès, route, paramètres et effort, avec leur source ou `INCONNU`, selon les [objets d’acquisition](../docs/ARD.md#44-acquisition-tentative-et-exécution).

| Cas et tentative | Configuration | Erreurs et obligations | Verdict | Motif et critères concernés | Preuves | Coût observé | Bénéfices prévus |
|---|---|---|---|---|---|---|---|
| `<identités>` | `<identité>` | `<constats>` | `<verdict>` | `<motif et références>` | `<pièces et passages>` | `<valeur et unité, ou INCONNU>` | `<faits ou AUCUN>` |

Les reçus d’évaluation conservent les configurations et consignes réellement utilisées par l’assistance IA éventuelle, les pièces vues, les constats, désaccords et arbitrages requis par la méthode, sans les ajouter rétroactivement à la carte gelée.

Une synthèse multi-cas applique uniquement la règle d'agrégation du contrat et affiche sa couverture.

Responsable des verdicts : `<rôle>`.

Appliquer l’[ordre de décision](../docs/RULES.md#7-ordre-de-décision) et les [règles économiques](../docs/RULES.md#8-coût-et-bénéfices). La restitution suit le [parcours public](../docs/PRD.md#10-restitution-publique).

### Conclusion économique

`<conclusion bornée aux cas et tentatives comparables ; INCOMPLETE si le coût d’une configuration SATISFAIT est INCONNU ou non comparable ; sans admissible, indiquer que la comparaison est sans objet>`

### Configurations `SATISFAIT` co-moins-chères

`<identités, ou AUCUNE ; si la conclusion est INCOMPLETE, aucune option n'est déclarée globalement moins chère>`

Un coût inconnu ou non comparable peut conserver l'admissibilité sur les critères non économiques ; les coûts connus restent visibles, mais la conclusion économique est `INCOMPLETE`. Cette mention n'est pas un quatrième verdict. Un coût `INCONNU` ne satisfait jamais une obligation de coût et ne prouve aucune supériorité économique.

### Bénéfices prévus des options `SATISFAIT` plus chères

`<liens aux seuls critères secondaires déclarés, ou AUCUN>`

## 9. Publication et limite d'attribution

Pièces publiables : `<entrées, sorties et passages approuvés>`.

Pièces privées et limites de vérification publique : `<références et motifs>`.

La publication référence son autorité et sa version de restitution. Aucun contenu candidat n'est interprété comme code actif dans le site.

Limite d’attribution affichée : `<formulation conforme au PRD, section 8, et limites propres à la campagne>`.

## 10. Qualification documentaire

- [ ] version, cas et preuves attendues sont identifiés ; la couverture est justifiée
- [ ] résultat attendu, usage, intervention humaine, obligations et tolérances, erreurs éliminatoires sont définis avant exécution
- [ ] référence et méthode sont identifiées et qualifiées ; alternatives, exposition, assistance IA et éventuelle revue professionnelle sont documentées
- [ ] toute agrégation des cas est définie avant exécution, sinon seuls les verdicts par cas sont permis
- [ ] chaque campagne référence le contrat sans le réécrire ; ses autorités et états restent distincts
- [ ] les trois verdicts sont présents
- [ ] zéro à deux critères secondaires sont prévus, avec unité et sens favorable s'ils départagent
- [ ] le responsable de campagne a approuvé le contrat ou l'exécution reste interdite
- [ ] les conditions de test communes sont déclarées une fois et identiques entre les configurations comparées
- [ ] chaque configuration expose l’effort demandé et l’effort observé, ou `INCONNU` pour une valeur non prouvée
- [ ] chaque configuration distingue sa route demandée de sa route observée ; toute valeur non prouvée reste `INCONNU`
- [ ] la base de coût fixe le périmètre d'attribution, les tentatives comptées, l'unité commune et la conversion éventuelle avant exécution
- [ ] chaque verdict porte un motif, ses preuves et son responsable
- [ ] le coût observé de chaque configuration reste visible ; les non-`SATISFAIT` sont exclus de la recommandation économique et la conclusion est `INCOMPLETE` si un coût `SATISFAIT` est inconnu ou non comparable
- [ ] aucun score global, podium général, classement universel ou graphique trompeur n'est produit
- [ ] la limite d'attribution est visible
- [ ] les extensions non autorisées restent absentes
- [ ] la conclusion est bornée au contrat, aux cas et tentatives couverts, à la campagne, aux conditions communes et à la date
- [ ] les pièces publiables sont autorisées et les restrictions sont visibles

Un scénario de maquette ne devient pas implicitement une tâche du catalogue.
