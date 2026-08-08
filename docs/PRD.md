# PRD : Benchmark Lab-X

Version 2.0, mise à jour le 5 août 2026

## 1. Résumé exécutif

L’outil Benchmark Lab-X cherche à savoir quel modèle, quelle configuration ou quel agent réussit un travail réel : avec quelle fiabilité, à quel coût, en combien de temps. Puis si cette réponse tient encore quand les systèmes évoluent.

Les modèles sont appelés directement par leurs API, comparés sur des tâches représentatives d’usages concrets, en français, et dans un contexte technique préalablement défini. La qualité mesurée tient à la réussite de la tâche, au respect de contraintes vérifiables et à la répétabilité observée. Elle ne résume en revanche pas la qualité intrinsèque d’un modèle.

Le projet est créé pour répondre à une question : **pour ce travail, avec ce niveau de besoin et cette contrainte de coût ou de durée, quelle modèle et configuration choisir ?**

Il produit :

- un classement par carte (i.e. l’unité de test notée, décrite en §6.1)
- une recommandation multi-cartes uniquement pour un profil d’usage pré-enregistré
- les coûts, durées, jetons et dispersions comme diagnostics
- à terme, un suivi dans le temps de la recommandation sur un petit jeu de tâches tenues en réserve, non publiées

Ce projet n’a pas pour but de produire ni score global entre domaines, ni de classement du « meilleur modèle » universel, ni d’équivalence automatique avec une application tierce (harnais ou autre).

### 1.1 Autorité documentaire

| Document             | Autorité                                                    |
| -------------------- | ----------------------------------------------------------- |
| PRD.md (ce document) | Problème, utilisateurs, objectifs, périmètre et jalons      |
| [ARD.md](ARD.md)     | Architecture, frontières de confiance et preuves techniques |
| [RULES.md](RULES.md) | Éligibilité, notation et validité des résultats             |

Les décisions restent dans le PRD ou l’ARD, près des exigences concernées.

Aucun document de décision séparé n’est requis.

### 1.2 État actuel

Le projet est actuellement en **pré-V0**.

Une chaîne verticale collecte et note des réponses sur la carte `pentagone-rotatif`. Son instrument `verify-v3` reste encore en qualification. Les autres cartes présentes servent au développement ou sont retirées. Le lanceur et l’agrégateur sont à l’état de prototype : ils ne produisent pas encore une campagne publiable conforme à toutes les règles.

Une partie de la chaîne est donc techniquement faisable. Rien de plus : ni couverture des usages, ni reproduction externe, ni valeur prédictive des cartes, ni stabilité dans le temps.

## 2. Problème

### 2.1 Décision locale

Un benchmark public généraliste compare des systèmes sur une référence commune. Il ne dit pas quoi choisir pour une tâche locale, avec un niveau attendu, une route, un effort et un budget précis.

C’est ce passage-là que Benchmark Lab-X instrumente. Une carte part d’un travail réel envisagé, définit des niveaux vérifiables, puis compare les configurations sous le même contexte de mesure.

### 2.2 Instrument fiable

Un jugement non déterministe ne permet pas de renoter à l’identique des sorties anciennes, et une suite de tests insuffisante peut produire un `PASS` faux. Le projet doit donc :

1. noter via du code déterministe
2. calibrer chaque prédicat avec des témoins indépendants
3. auditer l’instrument sans autoriser une modification humaine du score
4. conserver les sorties et empreintes nécessaires à une renotation

Un total de 4 runs génératifs mesurent une répétabilité observée, jamais une garantie statistique générale.

### 2.3 Exploitation

Le POC doit rendre le projet démontrable sans manipulation répétitive.
Le prototype quant à lui doit exécuter une campagne plus large, reprendre après interruption, respecter les quotas et le plafond de dépense, puis produire une page prête pour audit.

Les charges de référence sont des scénarios de capacité, jamais une limite du registre :

| Jalon |         Enveloppe maximale de référence | Durée de génération envisagée |
| ----- | --------------------------------------: | ----------------------------: |
| V0    |    3 cartes × 6 candidats × 4 runs = 72 |             moins de 3 heures |
| V1    | 10 cartes × 12 candidats × 4 runs = 480 |             moins de 8 heures |

Une carte fermée peut n’exiger qu’un run. Le manifeste calcule alors le total exact. L’audit humain intervient après le chronomètre.

## 3. Utilisateurs

| Code | Utilisateur             | Travail à accomplir                                                          | État de connaissance                    |
| ---- | ----------------------- | ---------------------------------------------------------------------------- | --------------------------------------- |
| U1   | Ayo, mainteneur initial | Construire une campagne, comprendre ses limites et choisir une configuration | Besoin confirmé par le projet           |
| U2   | Développeur du Lab-X    | Ajouter une carte, reproduire une tranche publique et utiliser un résultat   | Segment plausible, pas encore interrogé |
| U3   | Lecteur technique       | Comprendre ce qui a été mesuré et vérifier la méthode                        | Segment public futur                    |
| U4   | Utilisateur du site     | Décrire un besoin et obtenir des recommandations étayées                     | Vision V5-V6, besoin à valider          |

Ayo reste propriétaire des décisions et validations jusqu’à délégation explicite à un mainteneur du Lab-X si besoin.

## 4. Objectifs et réussite

| Priorité | Sens                                                        |
| -------- | ----------------------------------------------------------- |
| P0       | Bloque V0, invalide une mesure ou protège un actif critique |
| P1       | Requis pour le prototype V1                                 |
| P2       | Capacité conditionnelle V2 ou V3                            |
| P3       | Vision V4 à V6                                              |

### G1. Aide à la prise de décision modèle `[P0]`

**V0 :**

- 3 cartes exposées qualifiées couvrent au moins 2 domaines d’usage
- chaque carte part d’un objectif utilisateur et d’une décision écrite
- 6 candidats de référence sont comparés ; le registre peut en contenir davantage
- la page permet d’expliquer le choix selon niveau, coût ou durée
- la démonstration se rejoue en une commande

**V1 :**

- 10 cartes exposées couvrent les cellules prioritaires approuvées après V0
- 3 décisions de sélection consignent besoin, niveau, contrainte, recommandation, choix et retour d’usage
- tout désaccord entre recommandation et usage déclenche une revue du proxy

3 décisions ne prouvent rien de général, mais elles suffisent après tests à repérer les premiers proxies inutiles.

### G2. Ne publier que des mesures défendables `[P0]`

- tous les runs d’une page validée passent le contrôle de conformité
- chaque prédicat possède ses témoins produits sans accès au vérificateur, avec provenance consignée
- l’audit humain ne laisse aucun verdict ou niveau faux non corrigé
- toute correction d’instrument crée une nouvelle version et une renotation complète
- la page distingue résultats notés, inéligibilité, erreurs d’infrastructure et absences

### G3. Produire une campagne exploitable `[P0]`

- une commande lance la campagne depuis son manifeste
- aucune intervention humaine entre le pré-vol et la page provisoire
- V0 respecte la cible de 3 heures ; V1 celle de 8 heures
- en V0, un arrêt au plafond ou une interruption laisse une page provisoire qui marque les runs non tentés `MISSING`
- la page provisoire nomme toute preuve manquante

**Extension V1 `[P1]`.** La reprise idempotente ne crée ni doublon ni trou.

Ces durées sont des critères d’acceptation. Aucune n’est encore mesurée. On ne les abaisse ni ne les contourne en silence.

### G4. Reproduire la tranche publique `[P1]`

Un développeur autre qu’Ayo part d’un clone frais et reproduit une campagne validée dont l’identifiant figure dans le lock.

Le lock impose une image portable, par son digest, pour la collecte comme pour la vérification. Les observations propres à l’hôte restent hors des empreintes et sont consignées séparément. La reproduction tourne donc sous le même `measurement_context_hash`, les mêmes `execution_manifest_hash` et le même ensemble de candidats.

Le critère de réussite dépend du type de carte :

- **carte fermée** : même verdict
- **carte générative** : une seule métrique choisie dans son contrat, verdict retenu ou écart absolu de niveau retenu, avec sa tolérance fixée avant l’exercice

Toute autre divergence d’empreinte rend l’exercice non comparable. Elle reste consignée avec les écarts observés.

### G5. Valider la couverture des usages `[P2]`

Après V1, Ayo approuve une matrice versionnée `domaine × scénario`. Chaque cellule prioritaire porte un besoin documenté, une décision visée, un proxy, un mode de mesure, un statut et une preuve de qualification. V2 est terminée lorsque toutes les cellules gelées pour ce jalon sont qualifiées ou retirées avec justification.

### G6. Suivre une recommandation dans le temps `[P3]`

V4 utilise au moins deux cartes retenues et deux campagnes espacées d’au moins trente jours. Le seuil de changement est préenregistré. Le résultat distingue :

- configuration évoluée sous instrument fixe
- instrument évolué avec renotation commune
- profil d’usage évolué, qui produit une nouvelle décision et non une régression

Pour un endpoint opaque, la conclusion porte sur le même libellé observé à deux dates.

## 5. Non-objectifs

- score global entre domaines ou entre pistes direct et agent
- vainqueur universel indépendant d’une tâche et d’une contrainte
- reproduction automatique de l’expérience d’une application éditeur
- score mécanique fondé sur un jugement esthétique ou sémantique ouvert
- juge génératif qui approuve sa propre tâche ou son propre score
- entraînement ou fine-tuning de modèles
- exécution cyber sur une cible réelle ou contournement des garde-fous d’un fournisseur
- acceptation de données personnelles, de secrets ou de contenus clients dans une carte notée
- score instantané d’une tâche décrite par un utilisateur avant instrumentation et validation

## 6. Modèle du projet

### 6.1 Objets

| Objet                 | Définition                                                               |
| --------------------- | ------------------------------------------------------------------------ |
| Candidat              | Triplet modèle, route backend/provider et effort de raisonnement         |
| Configuration mesurée | Candidat et manifeste complet des paramètres et composants exécutés      |
| Carte                 | Objectif, consignes, entrées, oracle, vérificateur et témoins versionnés |
| Run attendu           | Cellule planifiée pour une carte, une configuration et un numéro de run  |
| Tentative             | Appel numéroté destiné à satisfaire un run attendu                       |
| Campagne              | Question, cartes, configurations, profils, quotas, plafond et runs gelés |
| Profil d’usage        | Niveaux minimaux par carte et contrainte de départage préenregistrés     |

### 6.2 Taxonomie

Une carte porte trois axes :

1. **domaine d’usage** : visuel et simulation, développement et automatisation, documents et provenance, données et calcul, planification et arbitrage, opérations et diagnostic, cyber
2. **mode d’exécution** : `direct` ou `agent`
3. **profondeur locale** : `courant`, `exigeant` ou `frontière`

La profondeur est calibrée dans une lignée de cartes et ne se compare pas entre cartes. F1 à F4 sont des patrons techniques : rendu, exécution, extraction/calcul fermés et optimisation sous contraintes. Ils ne sont ni des domaines d’usage ni des scores.

### 6.3 Classements et recommandation

Chaque carte classe les candidats complets avec la clé adaptée à son contrat. Une checklist utilise le verdict retenu dans l’ordre `PASS` > `PARTIAL` > `FAIL` ; une carte à paliers utilise le niveau retenu décroissant. Les ex æquo restent ex æquo, sauf départage préenregistré. Un profil peut retenir les configurations qui franchissent tous ses seuils minimaux, puis les ordonner par sa contrainte déclarée.

Une page validée affiche aussi les candidats inéligibles hors classement. Une erreur d’infrastructure, un run manquant ou un état `UNKNOWN` maintient la page au statut provisoire.

La recommandation montre au minimum : candidat, configuration, date, carte ou profil, runs observés, verdict ou niveau retenu, coût, durée, contexte de mesure et limites.

### 6.4 Public, exposé et retenu

| Actif                                    | Dépôt public |         Envoyé au candidat         |
| ---------------------------------------- | :----------: | :--------------------------------: |
| Consignes et entrées d’une carte exposée |     Oui      |                Oui                 |
| Oracle, vérificateur et témoins exposés  |   Possible   |                Non                 |
| Reçus expurgés et page validée           |   Possible   |                Non                 |
| Contenu d’une carte retenue V4           |     Non      | Seulement pendant son run officiel |
| Oracle, témoins et sorties retenus       |     Non      |                Non                 |

Le projet n’a pas de licence. Son choix et la vérification du nom bloquent la première publication officielle, pas le travail V0 local.

## 7. Exigences fonctionnelles

| ID     | Pri. | Exigence                                                                                                                                                             | Preuve d’acceptation                                                                          |
| ------ | ---: | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| EF-001 |   P0 | Un lanceur exécute une campagne depuis `runs/<campagne>/campaign.toml` en une commande et selon la concurrence déclarée                                              | V0 et V1 respectent leurs enveloppes et cibles chronométrées                                  |
| EF-002 |   P0 | Collecte et notation produisent des reçus séparés et immuables                                                                                                       | Une renotation ajoute un reçu de score sans modifier la collecte                              |
| EF-003 |   P0 | Un contrôle de conformité séparé refuse les identités, paramètres, empreintes ou états invalides                                                                     | Cas conforme à zéro ; cas invalide en code non nul                                            |
| EF-004 |   P0 | L’agrégateur produit `results.html` sans saisie manuelle et conserve le statut provisoire tant que la campagne est incomplète                                        | Cas `UNKNOWN`, `INFRA_ERROR` et `MISSING` testés                                              |
| EF-005 |   P0 | Deux candidats ne sont comparés que sous le même `measurement_context_hash`                                                                                          | Une divergence de contexte bloque la comparaison                                              |
| EF-006 |   P3 | Deux campagnes retenues compatibles appliquent une règle longitudinale préenregistrée                                                                                | Écarts et verdict mécanique ; divergence refusée                                              |
| EF-007 |   P0 | Toute carte documente besoin, décision, défaut attendu, items ou paliers et mécanisme discriminant                                                                   | Le pré-vol refuse un contrat incomplet                                                        |
| EF-008 |   P0 | Chaque prédicat possède des témoins positif et négatif produits sans accès au vérificateur                                                                           | Reçu de calibrage, provenance et séparation des rôles selon R-016                             |
| EF-009 |   P1 | Appels partis, campagnes et cycle de vie d’une carte se reconstruisent depuis les reçus                                                                              | Recompte sans champs historiques manuels                                                      |
| EF-010 |   P0 | La page affiche classement, runs, configuration, verdict ou niveau retenu, coût, durée, états, versions et limites                                                   | Contrôle du schéma HTML sur une checklist et une carte à paliers                              |
| EF-011 |   P1 | Une commande reproduit une campagne validée nommée depuis un clone frais, dans l’image portable épinglée, avec les mêmes empreintes et le même ensemble de candidats | Même verdict sur carte fermée ; métrique et tolérance préenregistrées sur carte générative    |
| EF-012 |   P0 | Chaque campagne possède un plafond de dépense et s’arrête proprement                                                                                                 | Test sous plafond volontairement bas                                                          |
| EF-013 |   P1 | Le lanceur conserve une machine d’état idempotente et un nombre maximal de tentatives préenregistré pour chaque run attendu                                          | Arrêt brutal, épuisement des tentatives puis reprise sans doublon                             |
| EF-014 |   P0 | Chaque résultat possède un `execution_manifest_hash` et un `measurement_context_hash` distincts                                                                      | Deux candidats se comparent sous le même contexte ; deux configurations restent identifiables |
| EF-015 |   P2 | La matrice V2 gère cellules proposées, pilotes, qualifiées et retirées                                                                                               | Export versionné approuvé par Ayo                                                             |
| EF-016 |   P2 | La piste agent possède son manifeste et ses classements propres                                                                                                      | Une carte agent qualifiée de bout en bout sans fusion avec le direct                          |
| EF-017 |   P3 | Le site V5 propose jusqu’à trois configurations depuis les seules campagnes validées, compatibles et assez fraîches                                                  | Aucun résultat historique ou incompatible présenté comme courant                              |
| EF-018 |   P3 | Le studio V6 transforme une description non sensible en brouillon, jamais directement en score                                                                       | Instrumentation, témoins et approbation humaine obligatoires avant campagne                   |
| EF-019 |   P1 | Une carte F2 utilise plusieurs instances et une suite cachée qualifiée par mutation                                                                                  | Taux de mutation gelé avant qualification                                                     |
| EF-020 |   P1 | Une carte F4 prouve l’optimum sous une borne déclarée                                                                                                                | Solveur épinglé et test de délai                                                              |

### 7.1 Manifeste de campagne

`campaign.toml` exprime l’intention. `campaign.lock` fige avant le premier appel :

- question, date, profil, fenêtre de fraîcheur éventuelle et campagne de référence lorsqu’il s’agit d’une reproduction
- cartes, versions, fichiers visibles et empreintes
- candidats, paramètres résolus et politique de données
- nombre de runs par carte, nombre maximal de tentatives par run, concurrence, quotas et plafond
- versions du protocole, du runner et des environnements de mesure ; digest de l’image portable pour une reproduction G4
- commit du dépôt et tarifs observés

Le lock ne contient aucun secret. Une valeur non exposée par un fournisseur est marquée `opaque`, jamais devinée.

## 8. Exigences non fonctionnelles

| ID      | Pri. | Exigence                                                                                                                    | Contrat ARD                    |
| ------- | ---: | --------------------------------------------------------------------------------------------------------------------------- | ------------------------------ |
| ENF-001 |   P0 | Notation déterministe et rejouable                                                                                          | AR-M-002 à AR-M-007            |
| ENF-002 |   P0 | Aucun actif côté juge dans le prompt ; liste autorisée explicite                                                            | AR-S-001 à AR-S-003            |
| ENF-003 |   P0 | Toute sortie exécutée est isolée du réseau, des secrets, du dépôt et des autres runs                                        | AR-S-006 à AR-S-008            |
| ENF-004 |   P0 | Reçus immuables, empreintes distinctes et états complets                                                                    | AR-R-001 à AR-R-006            |
| ENF-005 |   P0 | Aucun fallback silencieux de modèle, provider ou backend                                                                    | AR-C-008 et AR-C-009           |
| ENF-006 |   P0 | V0 tient sous 3 heures et V1 sous 8 heures dans leurs enveloppes documentées                                                | AR-R-009                       |
| ENF-007 |   P3 | Le jeu retenu reste local, sauvegardé et restaurable ; seul son prompt officiel sort pendant le run                         | AR-S-009, AR-S-010 et AR-P-005 |
| ENF-008 |   P1 | Documentation publique utilisable sans notes privées du mainteneur                                                          | AR-P-006 à AR-P-008            |
| ENF-009 |   P0 | Français pour les contenus destinés à un humain, y compris messages d’outillage et HTML ; exceptions techniques selon R-028 | AR-P-012                       |
| ENF-010 |   P0 | Aucun secret ni donnée réelle dans prompt, reçu public, log ou manifeste                                                    | AR-S-004 et AR-S-005           |
| ENF-011 |   P3 | Le site ne contient aucune clé de fournisseur et distingue courant, historique et non couvert                               | AR-P-009 et AR-P-010           |
| ENF-012 |   P0 | La répétabilité observée n’est jamais présentée comme une garantie statistique                                              | AR-P-003                       |

## 9. Trajectoire du projet

| Jalon                  | Statut       | Contenu                                                       | Preuve de sortie                                                                                                      |
| ---------------------- | ------------ | ------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Pré-V0                 | actuel       | chaîne verticale et contrats en qualification                 | aucune publication revendiquée                                                                                        |
| V0, POC                | engagé       | 3 cartes exposées, 6 candidats de référence, campagne et HTML | HTML provisoire sous 3 heures, puis audit réussi et démonstration rejouable                                           |
| V1, prototype          | engagé       | 10 cartes exposées, reprise, reproduction et retours d’usage  | charge jusqu’à 10 × 12 × 4 en moins de 8 heures, reproduction externe réussie selon G4 et trois décisions documentées |
| V2, couverture directe | conditionnel | matrice d’usages et pilote cyber défensif synthétique         | toutes les cellules prioritaires gelées sont qualifiées ou retirées                                                   |
| V3, agents             | conditionnel | manifeste agent, outils isolés et classement séparé           | au moins une carte agent qualifiée de bout en bout                                                                    |
| V4, vivant             | vision       | cohortes exposée et retenue, plus historique des campagnes    | deux campagnes retenues compatibles à 30 jours ou plus                                                                |
| V5, consultation       | vision       | site sans appel live                                          | recommandations datées depuis données validées                                                                        |
| V6, studio             | vision       | brouillon synthétique puis qualification humaine              | aucune tâche auto-approuvée ni score instantané                                                                       |

### 9.1 Cyber

V2 peut accueillir un pilote défensif sur données et environnements synthétiques. L’offensif est une extension facultative de V3. Il exige après le pilote défensif : modèle de menace approuvé, environnement éphémère sans sortie réseau, cible synthétique, outils autorisés, quotas, arrêt d’urgence, journalisation, remise à zéro et décision humaine distincte. Le refus d’un fournisseur est mesuré selon R-013 ; il ne justifie aucun reroutage vers une route plus permissive.

### 9.2 Site dynamique

V5 consulte les mesures existantes. Il montre jusqu’à trois recommandations, sans compléter artificiellement la liste, avec date, contexte, couverture et fenêtre de fraîcheur préenregistrée.

V6 accepte d’abord une description, sans fichier réel ni secret. Il produit un brouillon et peut rapprocher le besoin de cartes existantes. Une nouvelle campagne n’est possible qu’après instrumentation et validation humaine.

## 10. Dépendances

| Dépendance                      | Usage                     | Limite ou porte                                                 |
| ------------------------------- | ------------------------- | --------------------------------------------------------------- |
| OpenRouter                      | Backend primaire          | disponibilité, identité servie, politiques et quotas            |
| Providers servis                | Exécution réelle          | endpoints opaques, paramètres et dépréciations                  |
| Groq                            | Backend distinct éventuel | qualification complète avant tout classement                    |
| Chromium, runtimes, solveurs    | Vérification déterministe | versions, isolement et tests d’évasion                          |
| Tarifs providers                | Diagnostic et plafond     | valeur datée, jamais supposée stable                            |
| Producteur de témoins exposés   | Calibrage V0 et V1        | humain distinct ou générateur séparé sans accès au vérificateur |
| Second humain et stockage local | Jeu retenu V4             | requis avant la première carte retenue                          |
| Licence et nom public           | Publication officielle    | décision humaine avant publication                              |

## 11. Risques et parades

| ID    | Pri. | Risque                                                         | Parade et limite                                                              |
| ----- | ---: | -------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| RP-01 |   P0 | Le proxy ne prédit aucun usage réel                            | relier chaque carte à une décision et retirer les proxies contredits          |
| RP-02 |   P0 | Le vérificateur accepte une sortie fausse                      | témoins, contre-exemples, mutation lorsque pertinente et audit R-026          |
| RP-03 |   P0 | Une réponse obtient des éléments côté juge                     | liste autorisée de fichiers, tests de traversée et séparation d’environnement |
| RP-04 |   P0 | Une sortie exécutée s’échappe du harnais                       | réseau refusé, environnement jetable, quotas et tests d’évasion               |
| RP-05 |   P1 | Une route opaque change silencieusement                        | manifestes datés ; conclusion limitée à l’endpoint observé                    |
| RP-06 |   P1 | Coût, quota ou durée rendent la campagne impraticable          | pré-vol, plafond, concurrence contrôlée et page provisoire explicite          |
| RP-07 |   P1 | Une carte exposée devient mémorisable                          | cycle de vie et variante de remplacement                                      |
| RP-08 |   P3 | Une recommandation V5 devient périmée                          | fenêtre de fraîcheur préenregistrée et état historique visible                |
| RP-09 |   P3 | V6 reçoit une donnée personnelle ou un secret                  | description synthétique seulement ; refus avant persistance                   |
| RP-10 |   P2 | Le cyber atteint une cible réelle ou publie un actif dangereux | porte R-029, GO séparé et publication expurgée                                |
| RP-11 |   P0 | PRD, ARD, règles et cartes divergent                           | matrice de traçabilité et contrôles de cohérence avant publication            |

## 12. Sources de conception

| Source                                                              | Fait utilisé                                                               | Conséquence locale                                              |
| ------------------------------------------------------------------- | -------------------------------------------------------------------------- | --------------------------------------------------------------- |
| [SWE-bench](https://github.com/SWE-bench/SWE-bench)                 | tâches logicielles issues de dépôts exécutables                            | référence complémentaire pour le développement                  |
| [Terminal-Bench](https://github.com/laude-institute/terminal-bench) | tâches réalisées par des agents dans un terminal                           | piste agent séparée des appels directs                          |
| [EvalPlus](https://arxiv.org/abs/2305.01210)                        | des tests supplémentaires révèlent des programmes faux auparavant acceptés | diversité d’instances et qualification des tests                |
| [LiveBench](https://arxiv.org/abs/2406.19314)                       | questions renouvelées et notation objective                                | cartes exposées renouvelables, au prix de la comparaison exacte |
| [FinQA](https://finqasite.github.io/)                               | calculs et faits supports annotés                                          | sorties fermées et provenance vérifiable                        |
| [ConstraintBench](https://arxiv.org/abs/2602.22465)                 | contraintes vérifiées et comparaison à un optimum                          | patron F4                                                       |

Ces sources expliquent des choix locaux. Elles ne font pas règle.

## 13. Portes de validation futures

| Porte                                                                | Propriétaire initial | Échéance                                    |
| -------------------------------------------------------------------- | -------------------- | ------------------------------------------- |
| matrice exacte des usages V2                                         | Ayo                  | revue de sortie V1                          |
| seuil de mutation d’une carte F2                                     | Ayo                  | avant qualification de la deuxième carte F2 |
| concurrence et quotas de référence                                   | Ayo                  | avant les recettes V0 et V1                 |
| modèle de menace et autorisation cyber offensive                     | Ayo                  | après réussite du pilote défensif           |
| emplacement, sauvegarde, restauration et second humain du jeu retenu | Ayo                  | avant V4                                    |
| règle de régression par carte retenue                                | Ayo                  | avant la campagne de référence V4           |
| fenêtre de fraîcheur de chaque profil public                         | Ayo                  | avant V5                                    |
| licence et vérification du nom                                       | Ayo                  | avant la première publication officielle    |
| qualification ou abandon de Groq                                     | Ayo                  | avant tout run classé via Groq              |
