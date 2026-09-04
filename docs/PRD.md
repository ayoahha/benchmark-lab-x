---
style_gate: pass
---

# PRD de Benchmark Lab-X

## 1. Rôle et autorité

Ce document fixe le besoin, l'audience, le périmètre produit et les résultats attendus de Benchmark Lab-X. Il ne porte aucun statut de livraison des versions ; les itérations décrivent seulement le découpage du produit.

L'approbation de ce document n'autorise aucune campagne ni publication. Les campagnes historiques restent sous leurs contrats d'origine.

L'[ARD](ARD.md) fixe le contrat d'architecture. Les [règles](RULES.md) portent les invariants. Le [glossaire](../CONTEXT.md) fixe le vocabulaire.

## 2. Besoin

**FAIT ÉTABLI** : le besoin originel est de permettre à la communauté Lab X de tester elle-même des solutions d'IA sur des tâches utiles, avec des preuves lisibles plutôt qu'un palmarès repris d'un tiers.

Le produit met le modèle en avant. Pour une tâche et un contrat fixés avant l'exécution, il doit indiquer quelles configurations de modèle, avec leur mode d'interrogation du LLM (accès OAuth ou API directe), accomplissent le travail sous le même harnais Pi, puis rendre lisible le coût observé de chaque configuration. La recommandation économique et les bénéfices prévus restent limités aux seules configurations admissibles.

Le nom du modèle ne suffit toutefois pas comme preuve. Le modèle est l'identifiant principal présenté, mais le verdict s'applique à sa configuration observée sous les conditions de test communes déclarées. Aucun effet que le fournisseur, l'effort, Pi ou ses réglages peuvent influencer n'est attribué au seul modèle.

## 3. Audience et jobs-to-be-done

### 3.1 Audience et accès

Le produit s'adresse à la communauté Lab X et aux lecteurs qui cherchent une configuration adaptée à une tâche. Le site public permet de consulter les résultats approuvés. La préparation des tâches, l'exécution et la publication sont réservées aux personnes autorisées.

Le périmètre V2 bêta ne comprend ni compte contributeur public, ni formulaire de soumission, ni commentaire, ni téléversement. Une ouverture aux contributions exige une décision distincte sur le besoin et les protections.

### 3.2 Jobs-to-be-done

| Situation                                        | Job-to-be-done                                                                | Résultat utile                                           |
| ------------------------------------------------ | ----------------------------------------------------------------------------- | -------------------------------------------------------- |
| Je dois choisir un modèle pour une tâche précise | savoir quelles configurations accomplissent le travail sous le même Pi        | verdicts bornés par un contrat explicite                 |
| Plusieurs configurations satisfont le contrat    | identifier la moins chère lorsque tous leurs coûts sont connus et comparables | comparaison économique bornée ou conclusion `INCOMPLETE` |
| Une option admissible plus chère existe          | comprendre ce qu'elle apporte sur les critères prévus                         | bénéfices traçables, sans score global                   |
| La preuve ne suffit pas                          | éviter une recommandation artificielle                                        | verdict `INDETERMINE` motivé                             |
| Je veux vérifier une conclusion                  | retrouver tâche, contrat, configuration, sortie et preuves                    | chaîne d'attribution bornée                              |
| Je cherche une tâche proche de mon besoin        | parcourir le catalogue et sa couverture réelle                               | tâche, version, cas et campagnes pertinents              |

Le [demandeur-lecteur](../CONTEXT.md#demandeur-lecteur) exprime son besoin. Il n'a pas à inventer un seuil, une métrique ou une méthode de jugement : le [responsable de campagne](../CONTEXT.md#responsable-de-campagne) prépare et approuve le contrat avant toute exécution. Ces deux rôles génériques peuvent être tenus par la même personne sans imposer de compte public ; aucun rôle n'est lié à une personne ou à une entité.

## 4. Question active

> Pour une tâche précise et un contrat de réussite fixé avant l'exécution, quelles configurations associant un modèle à un accès direct ou API accomplissent la tâche sous le même harnais Pi ? Lorsque leurs coûts sont connus et comparables, laquelle ou lesquelles coûtent le moins, et quels bénéfices prévus une option plus chère apporte-t-elle ?

Qualité ou stabilité ne deviennent des critères que si une tâche les définit de manière testable avant l'exécution, dans la limite du contrat minimal.

## 5. Périmètre produit

### 5.1 Lot V2 bêta

- catalogue de tâches versionnées, avec contrat et cas d'essai identifiés
- plusieurs campagnes, chacune liée à une version de tâche, à ses cas et à un panel figé
- résultats réellement acquis et évalués sur le catalogue et le panel approuvés
- accès directs ou API sous Pi constant pour chaque comparaison
- suivi des tentatives, incidents, coûts et preuves sans relance implicite
- navigation catalogue, tâche, campagne et comparaison des configurations
- consultation publique des seules restitutions approuvées, sans classement universel

Le nombre de configurations et leurs identités exactes appartiennent aux décisions de panel et aux manifestes de campagne. La capacité logicielle seule ne constitue pas la livraison du lot de résultats.

### 5.2 Extensions

Les modèles locaux peuvent être comparés par un accès déclaré, avec identité des poids, quantification, serveur d'inférence, matériel et base de coût explicites. Leur entrée dans un panel exige une décision propre.

Les abonnements comme objets de comparaison, les produits agentiques et la comparaison de harnais exigent un besoin démontré et une décision de périmètre. Aucun scénario de maquette ne devient implicitement une tâche du catalogue.

## 6. Contrat de réussite

Chaque version de tâche possède avant exécution un contrat préparé et approuvé par le responsable de campagne. Il contient :

1. le résultat attendu ;
2. les obligations ;
3. les erreurs éliminatoires ;
4. les verdicts `SATISFAIT`, `NE SATISFAIT PAS` et `INDETERMINE` ;
5. au maximum deux critères secondaires prévus avant l'exécution, avec unité et sens favorable s'ils doivent départager.

Il identifie les cas d'essai et leur couverture. Toute règle agrégeant les verdicts de plusieurs cas est fixée avant exécution ; sans cette règle, seuls les verdicts par cas sont permis. Aucun nombre de cas ou de répétitions n'est imposé sans justification.

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

Cet ordre gouverne le calcul de la recommandation ; il n'impose pas deux sections successives à l'écran. Il n'existe aucun score composite, moyenne transversale, meilleur modèle absolu ou classement universel. Une conclusion reste bornée à la version de tâche, aux cas couverts, à la campagne, au contrat, aux configurations, aux conditions communes, aux preuves et à la date.

## 8. Preuve et transparence

Les [conditions de test communes](../CONTEXT.md#conditions-de-test-communes) sont exposées une fois par comparaison : état de Pi, environnement et date de gel. Chaque configuration observée expose ensuite ses valeurs propres : fournisseur, modèle, accès direct ou API, route, paramètres et effort de raisonnement, demandés puis observés. Les champs exacts sont ceux de l'[ARD](ARD.md#4-objets-et-responsabilités).

Une valeur non observée reste `INCONNU`. La restitution porte l'avertissement suivant ou une formulation équivalente :

> Le verdict porte sur la configuration observée sous les conditions de test communes déclarées. Il n'attribue pas au seul modèle un effet que le fournisseur, l'effort, Pi ou ses réglages peuvent influencer, et ne démontre pas que le modèle isolé aurait produit le même résultat sous un autre harnais, fournisseur, contexte ou environnement.

## 9. Contrats historiques

Les campagnes historiques conservent leurs questions, contrats, observations et verdicts. Leur bilan opérationnel appartient aux preuves d'origine et au README ; il ne vaut pas validation de la méthode courante.

## 10. Restitution publique

Le parcours va du catalogue à la tâche, puis à une campagne. La page campagne expose d'abord la conclusion permise, son périmètre, les nombres de cas et de tentatives, sa date et sa limite principale.

Un tableau commun présente chaque configuration, son verdict, son motif, son coût observé, son statut économique et ses bénéfices prévus. Les dépenses des configurations exclues restent visibles. La recommandation économique reste limitée aux configurations `SATISFAIT`. Si un coût admissible est inconnu ou non comparable, la conclusion est `INCOMPLETE` et aucune option n'est déclarée globalement moins chère.

Le lecteur accède à la méthode et aux preuves depuis la comparaison : entrée du cas, sortie exacte et passages justifiant les constats lorsque leur publication est autorisée. Une empreinte ne remplace pas une pièce accessible ; une restriction de publication est signalée.

Une campagne partielle expose sa couverture et ses incidents sans transformer les cellules manquantes en échecs du modèle ni en résultats acquis. Aucun podium général ou score global n'est produit.

## 11. Hors périmètre documentaire

Les choix techniques relèvent de l'ARD. Le backlog et son avancement relèvent de GitHub. Un panel sélectionné n'autorise ni appel, ni retry, ni dépense. Intégration Git, exécution du produit, appels candidats et budget, provisionnement et publication gardent des autorités distinctes.

## 12. Critères d'acceptation documentaire

La proposition est prête pour revue si :

- tâche, version, cas, campagne et configuration observée sont distingués
- les règles d'évaluation et la portée de chaque conclusion sont fixées avant exécution
- les inconnues, les coûts non comparables et les conditions de test restent explicites
- la consultation publique et les opérations protégées sont séparées
- le parcours rend accessibles la conclusion, la comparaison et les preuves publiables
- les résultats réels sont distingués de la capacité logicielle et des données de démonstration
- les campagnes historiques ne sont pas requalifiées
- aucun statut de livraison des versions ni backlog concurrent n'est introduit

Ces critères ne valent ni autorisation d'exécution, ni PASS du reviewer, ni publication.
