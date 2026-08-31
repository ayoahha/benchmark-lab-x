---
style_gate: pass
---

# PRD de Benchmark Lab-X

Décisions propriétaires intégrées : 31 août 2026

## 1. Rôle et autorité

Ce document fixe le besoin, l'audience, la question active, le périmètre du premier prototype et le résultat attendu de Benchmark Lab-X.

Il ne lance aucune campagne et ne requalifie pas V0 ou V1. La prochaine phase porte le nom `V2-alpha` ; son architecture, son découpage, son panel et ses exécutions restent en attente de décisions distinctes.

L'[ARD](ARD.md) décrit le modèle logique. Les [règles](RULES.md) portent les invariants. Le [glossaire](../CONTEXT.md) fixe le vocabulaire.

## 2. Besoin

**FAIT ÉTABLI** : le besoin originel est de permettre à la communauté Lab X de tester elle-même des solutions d'IA sur des tâches utiles, avec des preuves lisibles plutôt qu'un palmarès repris d'un tiers.

**DÉCISION PROPRIÉTAIRE** : le produit met maintenant le modèle en avant. Pour une tâche et un contrat fixés avant l'exécution, il doit indiquer quelles configurations modèle plus accès direct ou API accomplissent le travail sous le même Pi, puis rendre lisibles le coût et les bénéfices prévus parmi les seules configurations admissibles.

Le nom du modèle ne suffit toutefois pas comme preuve. Le modèle est l'identifiant principal présenté, mais le verdict s'applique à sa configuration observée sous les conditions de test communes déclarées. Aucun effet que le fournisseur, l'effort, Pi ou ses réglages peuvent influencer n'est attribué au seul modèle.

## 3. Audience et jobs-to-be-done

### 3.1 Audience et trajectoire d'accès

**DÉCISION PROPRIÉTAIRE** : l'accès et l'utilisation initiaux sont destinés à la communauté Lab X, afin qu'elle éprouve le produit sur des tâches utiles et contribue à son amélioration.

Le produit a vocation à devenir public et accessible à tous après cette phase initiale. Cette vocation cible ne constitue ni une publication actuelle, ni une autorisation de merge, de publication ou d'ouverture d'accès.

**HYPOTHÈSE NON VÉRIFIÉE** : des membres de Lab X contribueront des besoins ou reliront des sorties si le protocole reste compréhensible et le coût d'entrée raisonnable. Une observation d'usage est nécessaire avant d'en faire une promesse.

### 3.2 Jobs-to-be-done

| Situation | Job-to-be-done | Résultat utile |
|---|---|---|
| Je dois choisir un modèle pour une tâche précise | savoir quelles configurations accomplissent le travail sous le même Pi | verdicts bornés par un contrat explicite |
| Plusieurs configurations satisfont le contrat | identifier la moins chère lorsque tous leurs coûts sont connus et comparables | comparaison économique bornée ou conclusion `INCOMPLETE` |
| Une option admissible plus chère existe | comprendre ce qu'elle apporte sur les critères prévus | bénéfices traçables, sans score global |
| La preuve ne suffit pas | éviter une recommandation artificielle | verdict `INDETERMINE` motivé |
| Je veux vérifier une conclusion | retrouver tâche, contrat, configuration, sortie et preuves | chaîne d'attribution bornée |
| Je participe à la phase initiale Lab X | éprouver le produit et contribuer à partir de tâches et preuves concrètes | retours situés sans prétendre à une validation publique |

Le [demandeur-lecteur](../CONTEXT.md#demandeur-lecteur) exprime son besoin. Il n'a pas à inventer un seuil, une métrique ou une méthode de jugement : le [responsable de campagne](../CONTEXT.md#responsable-de-campagne) prépare et approuve le contrat avant toute exécution. Ces deux rôles génériques peuvent être tenus par la même personne dans le premier prototype ; aucun rôle n'est lié à une personne ou à un pseudonyme.

## 4. Question active

> Pour une tâche précise et un contrat de réussite fixé avant l'exécution, quelles configurations associant un modèle à un accès direct ou API accomplissent la tâche sous le même Pi ? Lorsque leurs coûts sont connus et comparables, laquelle ou lesquelles coûtent le moins, et quels bénéfices prévus une option plus chère apporte-t-elle ?

Cette question remplace les formulations générales centrées sur « qualité et stabilité » et les deux profils actifs. Qualité ou stabilité ne deviennent des critères que si une tâche les définit de manière testable avant l'exécution, dans la limite du contrat minimal.

## 5. Périmètre du premier prototype

### 5.1 Inclus

- une tâche précise
- des modèles accessibles directement ou par API
- Pi comme harnais obligatoire et constant
- des conditions de test communes déclarées avant le premier candidat
- une configuration observée enregistrée pour chaque candidat
- un contrat de réussite fixé avant l'exécution
- un verdict d'admissibilité explicable avant toute comparaison de coût
- une restitution située en deux étapes, sans classement universel

### 5.2 Différé

- abonnements et produits agentiques
- comparaison de harnais
- autres harnais dépouillés
- OrbStack
- `perso-hermes`
- répétitions, statistiques ou rubriques supplémentaires sans besoin démontré

Ces sujets ne sont pas rejetés. Ils sont différés selon la règle KISS des [règles](RULES.md#11-kiss-et-évolution).

Le scénario `quote-thread-summary` est seulement un scénario réversible de maquette. Il n'est pas la tâche canonique d'un benchmark futur.

## 6. Contrat de réussite

Chaque tâche possède avant exécution un contrat préparé et approuvé par le responsable de campagne. Il contient exactement :

1. le résultat attendu ;
2. les obligations ;
3. les erreurs éliminatoires ;
4. les verdicts `SATISFAIT`, `NE SATISFAIT PAS` et `INDETERMINE` ;
5. au maximum deux critères secondaires prévus avant l'exécution, avec unité et sens favorable s'ils doivent départager.

Il fixe aussi le périmètre d'attribution du coût, les tentatives comptées, l'unité commune et, si nécessaire, la règle de conversion.

Une erreur éliminatoire interdit `SATISFAIT`. Une preuve insuffisante produit `INDETERMINE`. Aucun coût ou bénéfice ne transforme un résultat non admissible en recommandation.

Le [gabarit de carte](../tasks/TEMPLATE.md) matérialise ce contrat sans imposer une méthode plus lourde.

## 7. Ordre de décision

L'ordre interne suit les six opérations des [règles](RULES.md#7-ordre-de-décision) :

1. erreurs éliminatoires ;
2. obligations et preuve ;
3. verdict d'admissibilité ;
4. exclusion de `NE SATISFAIT PAS` et `INDETERMINE` de la recommandation économique ;
5. coût connu et comparable entre les seuls `SATISFAIT` ;
6. bénéfices prévus des options `SATISFAIT` plus chères.

Ces six opérations ne sont pas les deux étapes visibles de la restitution. Il n'existe aucun score composite, moyenne transversale, meilleur modèle absolu ou classement universel. Une conclusion reste bornée à la tâche, au contrat, aux configurations, aux conditions de test communes, aux preuves et à la date.

## 8. Preuve et transparence

Les [conditions de test communes](../CONTEXT.md#conditions-de-test-communes) sont exposées une fois par comparaison : état de Pi, environnement et date de gel. Chaque configuration observée expose ensuite ses valeurs propres : fournisseur, modèle, accès direct ou API, route, paramètres et effort de raisonnement, demandés puis observés. Les champs exacts sont ceux de l'[ARD](ARD.md#4-objets-et-responsabilités).

Une valeur non observée reste `INCONNU`. La restitution porte l'avertissement suivant ou une formulation équivalente :

> Le verdict porte sur la configuration observée sous les conditions de test communes déclarées. Il n'attribue pas au seul modèle un effet que le fournisseur, l'effort, Pi ou ses réglages peuvent influencer, et ne démontre pas que le modèle isolé aurait produit le même résultat sous un autre harnais, fournisseur, contexte ou environnement.

## 9. État historique, pas état cible

### 9.1 V0

**FAIT ÉTABLI** : V0 a obtenu une sortie sur deux configurations API, sans répétition. Grok a échoué à `G-001` ; Kimi a fini en `HARNESS_ERROR`. Il n'existe aucun verdict humain, coût total connu, front à trois axes calculable, gagnant ou recommandation.

### 9.2 V1

**FAIT ÉTABLI** : V1 a obtenu six sorties sur sept produits d'abonnement. Les six ont échoué à `G-001`, sans `PASS` ni revue humaine officielle. Quotas et effort humain restent inconnus dans la restitution consolidée. Le coût d'abonnement par sortie acceptable est `NON_DEFINI` par décision propriétaire V1. Aucun classement qualitatif n'est soutenu.

### 9.3 Limite

V0 et V1 restent sous leurs contrats et verdicts d'origine. Elles ne fournissent ni classement qualitatif, ni baseline, ni coût par résultat acceptable, ni recommandation rétrospective, ni validation de la méthode actuelle.

## 10. Restitution publique

La restitution comporte exactement deux étapes visibles :

1. **Admissibilité** : toutes les configurations comparées, chacune avec son verdict et un motif synthétique ;
2. **Comparaison économique** : coûts connus et comparables et bénéfices prévus parmi les seules configurations `SATISFAIT`. Si le coût d'au moins une configuration `SATISFAIT` est inconnu ou non comparable, les coûts connus restent visibles, mais aucune option n'est déclarée globalement moins chère et la conclusion économique porte la mention `INCOMPLETE`.

Cette mention ne crée pas un quatrième verdict et ne change pas l'admissibilité.

Critères, preuves, incidents, inconnues, limite d'attribution et conditions de test communes sont accessibles sur demande par divulgation progressive ; leur ouverture n'est pas une troisième étape. La restitution ne produit ni podium général, ni score global, ni graphique trompeur.

La variante A de maquette reste une direction réversible de présentation, pas une architecture canonique.

## 11. Hors périmètre documentaire

- conception d'une plateforme
- architecture et découpage de V2-alpha avant validation du Graph Engineering
- panel définitif
- appels candidats, retries, achats ou campagnes
- classement rétrospectif de V0 ou V1
- publication, merge ou fermeture de tickets

## 12. Critères d'acceptation documentaire

La proposition est prête pour revue si :

- le modèle est l'objet produit et la configuration observée, reliée aux conditions de test communes, l'unité de preuve
- l'accès commence avec la communauté Lab X pour éprouver et contribuer, puis vise un produit public accessible à tous sans publication implicite
- le premier prototype est limité aux accès directs ou API sous le même Pi
- Pi et le statut de chaque valeur de son état, déclarée, configurée, active ou observée, sont explicites
- les rôles produit se limitent au demandeur-lecteur et au responsable de campagne ; aucune personne n'est codée comme approbateur
- chaque verdict publiable porte valeur, motif, critères ou constats, preuves et responsable
- la route demandée et la route observée sont distinctes ; toute valeur non prouvée reste `INCONNU`
- la base de coût est fixée avant exécution et toute conclusion économique s'abstient si un coût admissible est inconnu ou non comparable
- le contrat de réussite et les six opérations de l'ordre de décision sont cohérents dans les documents canoniques
- la restitution comporte exactement deux étapes visibles, sans podium ni graphique trompeur
- les éléments différés n'ont aucun statut actif
- V0 et V1 restent historiques et non requalifiées
- aucun score global ou classement universel n'est prévu

Ces critères ne valent ni autorisation d'exécution, ni PASS du reviewer, ni publication.
