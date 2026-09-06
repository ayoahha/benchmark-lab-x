---
style_gate: pass
---

# PRD de Benchmark Lab-X

## 1. Rôle et autorité

Ce document fixe la vision durable, le besoin, l’audience et les résultats attendus de Benchmark Lab-X. Les parcours et principes décrivent le produit à long terme ; un périmètre associé à une version borne seulement son jalon. Le document ne porte aucun statut de livraison et les options non décidées ne deviennent pas des exigences par leur seule mention.

L'approbation de ce document n'autorise aucune campagne ni publication. Les campagnes historiques restent sous leurs contrats d'origine.

L'[ARD](ARD.md) fixe le contrat d'architecture. Les [règles](RULES.md) portent les invariants. Le [glossaire](../CONTEXT.md) fixe le vocabulaire.

## 2. Besoin

**FAIT ÉTABLI** : le besoin originel est de permettre à la communauté Lab X de tester elle-même des solutions d'IA sur des tâches utiles, avec des preuves lisibles plutôt qu'un palmarès repris d'un tiers.

Le produit met le modèle en avant. Pour une tâche et un contrat fixés avant l'exécution, il doit indiquer quelles configurations de modèle, avec leur mode d'interrogation du LLM (accès OAuth ou API directe), accomplissent le travail sous le même harnais Pi, puis rendre lisible le coût observé de chaque configuration. La recommandation économique et les bénéfices prévus restent limités aux seules configurations admissibles.

Le nom du modèle ne suffit toutefois pas comme preuve. Le modèle est l'identifiant principal présenté, mais le verdict s'applique à sa configuration observée sous les conditions de test communes déclarées. Aucun effet que le fournisseur, l'effort, Pi ou ses réglages peuvent influencer n'est attribué au seul modèle.

## 3. Audience et jobs-to-be-done

### 3.1 Audience et accès

Le produit s'adresse à la communauté Lab X et aux lecteurs qui cherchent une configuration adaptée à une tâche. Les tâches représentent des besoins de métiers et de domaines variés ; le catalogue n’est pas limité aux usages informatiques ou administratifs. Le site public permet de consulter les résultats approuvés. La préparation des tâches, l'exécution et la publication sont réservées aux personnes autorisées.

Le périmètre 0.1.0 ne comprend ni compte public, ni formulaire de soumission, ni commentaire, ni téléversement. Une ouverture aux contributions exige une décision distincte sur le besoin et les protections.

Le catalogue distingue le métier ou domaine, qui donne le contexte, et la famille de tâche, qui décrit le travail, par exemple : extraire, rapprocher, synthétiser, rédiger, décider, organiser, rechercher ou argumenter. Ces repères peuvent se croiser et évoluer. Ils servent à trouver un usage proche, sans promettre une compétence générale sur une profession.

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

### 5.1 Périmètre 0.1.0

Ce jalon réunit les capacités ci-dessous et les [critères d’acceptation produit](#12-critères-dacceptation-produit). Son numéro suit les [règles de versionnement](RULES.md#14-versionnement-du-produit) ; il ne porte aucun état de livraison.

- catalogue de tâches versionnées, avec contrat et cas d'essai identifiés
- plusieurs campagnes, chacune liée à une version de tâche, à ses cas et à un panel figé
- résultats réellement acquis et évalués sur le catalogue et le panel approuvés
- accès directs ou API sous Pi constant pour chaque comparaison
- suivi des tentatives, incidents, coûts et preuves sans relance implicite
- navigation catalogue, tâche, campagne et comparaison des configurations
- consultation publique des seules restitutions approuvées, sans classement universel

Le corpus de 0.1.0 comprend de deux à neuf tâches. Les deux premières consistent à comparer des salles selon le besoin d’une association et à transformer des notes de réunion en suivi des décisions et actions. Le résultat de ces deux tâches doit être utilisable après une relecture ordinaire, sans correction de faits, de calculs, de responsabilités ou d’engagements. Les adaptations de présentation acceptables seront définies dans chaque contrat. Leurs dossiers sont entièrement fictifs : personnes, organismes, situations, échanges, notes et pièces inventés. Ces entrées fictives doivent recevoir des réponses réellement acquises lors de campagnes autorisées ; des sorties simulées ne les remplacent pas.

Le panel nominal retenu par Ayo pour 0.1.0 est : GLM5.3, Deepseek V4 Flash-0731, Muse spark 1.3, Hy4 Preview, Minimax M3, Qwen3.8-Max-0902, Mimo-V2.5-Pro, Gemini 3.8 Flash, Kimi k3 et Grok 4.6. Les révisions `0731` et `0902` sont exigées.

Cette décision ne prouve ni disponibilité, ni identifiant fournisseur, ni compatibilité avec Pi. Les contrats et cas des tâches retenues, l’ajout d’autres tâches, les configurations exactes, les accès, les routes, les agrégations et les budgets restent à décider avant les manifestes de campagne. Aucun alias ou modèle de substitution n’est déduit du nom retenu. La capacité logicielle sur données synthétiques prouve seulement le logiciel ; 0.1.0 exige aussi les résultats réels autorisés.

### 5.2 Extensions

La couverture de métiers variés appartient à la vision durable : droit et notariat, documentation de santé, enseignement, artisanat, maintenance, logistique, agriculture, comptabilité, journalisme ou qualité industrielle, sans liste fermée ni couverture de tous ces domaines exigée pour 0.1.0. Les cas sont choisis pour leur utilité et les difficultés concrètes du travail, sans obligation de mettre en échec un humain ou un modèle réputé performant.

Les bons modèles locaux appartiennent à la vision durable du produit, sans intégration imposée à 0.1.0. Ils peuvent être comparés par un accès déclaré, avec identité des poids, quantification, serveur d'inférence, matériel et base de coût explicites. Leur entrée dans un panel exige une décision propre.

Les abonnements comme objets de comparaison, les produits agentiques et la comparaison de harnais exigent un besoin démontré et une décision de périmètre. Aucun scénario de maquette ne devient implicitement une tâche du catalogue.

## 6. Contrat de réussite

Le contrat d’une version de tâche traduit le besoin en résultat attendu, obligations, erreurs éliminatoires et critères secondaires prévus. Le responsable de campagne l’approuve avant l’exécution. Les [règles](RULES.md#4-contrat-avant-exécution) fixent son contenu minimal, le gel, les verdicts et les conditions d’agrégation.

La tâche annonce ce qu’elle mesure et le travail qui reste à l’utilisateur : brouillon à reprendre, résultat utilisable après relecture ou autre usage explicitement défini. La qualité de l’épreuve dépend aussi de sa référence de jugement et de ses contrôles, qualifiés avant l’approbation du contrat selon les règles ; la réputation d’un modèle ne suffit à elle seule ni à valider l’épreuve ni à l’invalider.

Les cas explicitent les difficultés qu’ils couvrent. La tâche annonce la portée de sa conclusion et la base de coût nécessaire à la décision : une réussite sur un exemple ne suffit pas à promettre une fiabilité générale. L’absence de règle d’agrégation limite la restitution aux verdicts par cas.

Le [gabarit de carte](../tasks/TEMPLATE.md) matérialise ce contrat. La méthode de contrôle, les données et leur provenance rendent chaque obligation vérifiable.

## 7. Ordre de décision

La décision établit d’abord quelles configurations satisfont le contrat, puis examine l’économie et les bénéfices prévus parmi elles, selon l’[ordre de décision](RULES.md#7-ordre-de-décision). Une option économique est utile seulement si elle accomplit le travail demandé.

Ces deux étapes logiques peuvent apparaître dans un même écran. La conclusion reste bornée à la tâche, à sa version et aux observations de la campagne ; elle ne désigne aucun meilleur modèle universel.

## 8. Preuve et transparence

Les [conditions de test communes](../CONTEXT.md#conditions-de-test-communes) sont exposées une fois par comparaison : état de Pi, environnement et date de gel. Chaque configuration observée expose ensuite ses valeurs propres : fournisseur, modèle, accès direct ou API, route, paramètres et effort de raisonnement, demandés puis observés. Les champs exacts sont ceux de l'[ARD](ARD.md#4-objets-et-responsabilités).

Une valeur non observée reste `INCONNU`. La restitution porte l'avertissement suivant ou une formulation équivalente :

> Le verdict porte sur la configuration observée sous les conditions de test communes déclarées. Il n'attribue pas au seul modèle un effet que le fournisseur, l'effort, Pi ou ses réglages peuvent influencer, et ne démontre pas que le modèle isolé aurait produit le même résultat sous un autre harnais, fournisseur, contexte ou environnement.

## 9. Contrats historiques

Les campagnes historiques conservent leurs questions, contrats, observations et verdicts. Leur bilan opérationnel appartient aux preuves d’origine ; il ne vaut pas validation de la méthode courante.

## 10. Restitution publique

Le catalogue permet de chercher un travail proche de son besoin et d’identifier ses versions et campagnes publiées. La page tâche explique le contexte métier, la famille de travail, le résultat attendu et son usage, les cas, leur charge et leurs difficultés concrètes, la couverture recherchée et les exclusions. Pour une recherche documentaire, elle distingue l’exploitation de textes utiles fournis, la recherche dans une bibliothèque figée et la consultation externe autorisée. Les compétences sollicitées et les limites de reproduction diffèrent ; aucune de ces modalités ne présume un connecteur disponible. Elle distingue l’existence d’une tâche de la présence de résultats approuvés.

La page campagne commence par un rappel bref du contexte et du travail demandé, puis expose la conclusion permise, son périmètre, les cas et tentatives couverts, les dates d’acquisition et sa limite principale. Un lien direct vers cette page conserve l’accès à la tâche et au catalogue. Le lecteur peut choisir une autre campagne de la même tâche en voyant sa version, sa date et ses conditions ; ce changement ne fusionne pas les résultats. Une différence de contrat, de cas, d’environnement ou de base de coût rend la limite de comparaison explicite.

Un tableau de synthèse suit cette conclusion et présente chaque configuration, son verdict et son motif, son coût observé, son statut économique et les bénéfices prévus. Une aide à proximité explique les verdicts, unités et inconnues sans exiger un survol. Le tableau conduit directement au détail de chaque configuration ; sa position à gauche ou sa disposition sur mobile ne sont pas imposées. Les [règles de coût](RULES.md#8-coût-et-bénéfices) couvrent les coûts manquants, l’absence de configuration admissible et les égalités. Les dépenses des configurations exclues restent visibles. Une couverture partielle ou une preuve insuffisante ne devient pas un échec du modèle.

Le détail des configurations vient après la synthèse. Le lecteur peut examiner ce que chacune a produit et revenir à la comparaison sans perdre le contexte de campagne. La méthode est accessible dès la synthèse, sans lecture préalable obligatoire ni dissimulation des limites pour prolonger la visite. Depuis une conclusion ou un verdict, le lecteur retrouve les constats et les pièces autorisées : entrée du cas, sortie exacte ou extrait identifié, et passage qui soutient l’évaluation. Une pièce restreinte indique ce que le public peut vérifier et ce qui reste inaccessible, selon les [règles de publication](RULES.md#10-restitution). Les limites de représentativité, de variabilité et de jugement accompagnent la conclusion, sans précision statistique inventée. La méthode expose comment la référence a été vérifiée, l’assistance éventuelle de modèles et l’existence ou l’absence d’une revue professionnelle, avec sa phase et son périmètre. Un résultat sur un exercice métier ne vaut pas habilitation professionnelle.

Une durée affichée précise ce qu’elle mesure : exécution, attente ou travail humain. Elle emploie des secondes, minutes ou heures selon l’ordre de grandeur, en gardant la valeur source accessible. Une limite de temps n’est pas une durée observée ; une durée d’exécution ne prouve pas du temps humain économisé. Cette règle de présentation n’impose aucune nouvelle mesure ni critère de classement.

La navigation, la sélection de campagne et l’accès aux preuves doivent fonctionner au clavier, avec un focus visible et des intitulés compréhensibles par un lecteur d’écran. Les tableaux gardent leurs en-têtes et leur sens sur petit écran ou avec un texte agrandi. Les verdicts et inconnues restent compréhensibles sans couleur seule. Ces propriétés se vérifient sur le parcours complet, y compris les pièces ouvertes depuis la comparaison. Un parcours manuel consigné vérifie les actions principales au clavier et avec un lecteur d’écran ; il nomme l’environnement utilisé, les actions et les écarts observés.

## 11. Hors périmètre documentaire

Les choix techniques relèvent de l'ARD. Le backlog et son avancement relèvent de GitHub. Un panel sélectionné n'autorise ni appel, ni retry, ni dépense. Intégration Git, exécution du produit, appels candidats et budget, provisionnement et publication gardent des autorités distinctes.

## 12. Critères d’acceptation produit

| Situation à vérifier | Résultat attendu |
|---|---|
| Une tâche possède plusieurs versions et campagnes | le lecteur choisit une campagne, retrouve sa tâche et distingue les différences qui bornent la comparaison |
| Le lecteur arrive directement sur une campagne | un contexte bref précède la conclusion et le tableau ; l’aide, la méthode et les sorties par configuration sont accessibles, avec retour à la synthèse |
| Des cas diffèrent par leur charge ou leur difficulté | les caractéristiques et la couverture observée sont lisibles ; aucun niveau non testé ni capacité maximale ne sont déduits du seul résultat |
| Une tâche vise un usage métier | le travail réellement mesuré, l’intervention humaine attendue et la qualification de la référence sont visibles, sans compétence professionnelle générale déduite |
| Les preuves permettent une conclusion | chaque verdict conduit à son contrat, ses constats et ses pièces ; observations et évaluation restent distinguées |
| Une campagne est partielle ou indéterminée | couverture prévue et acquise, incidents et inconnues sont lisibles sans succès ni échec inventé |
| Des configurations sont admissibles, avec égalité, coût manquant ou non comparable | la restitution applique les règles économiques sans cacher les dépenses exclues ni inventer de gagnant |
| Aucune configuration n’est admissible | l’absence de recommandation est explicite ; la dépense reste consultable |
| Une pièce est privée ou du contenu candidat est affiché | la limite de vérification est visible et le parcours ne donne aucun accès privé ni exécution active |
| Le parcours est utilisé au clavier, avec lecteur d’écran ou sur petit écran | tâche, campagne, comparaison et preuves restent compréhensibles et accessibles |
| Une démonstration utilise des données synthétiques | cette nature est visible ; elle ne remplace pas les résultats réels autorisés exigés par 0.1.0 |

La validation logicielle utilise des cas contrôlés couvrant ces situations. La validation du lot de résultats cite séparément les campagnes réelles, leurs autorités et leurs preuves. Ni l’une ni l’autre n’autorise à elle seule la publication ou le déploiement.
