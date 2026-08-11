---
style_gate: pass
---

# PRD : Benchmark Lab-X

Version documentaire 3.0, 8 août 2026

## 1. Résumé exécutif

**Le banc d’essai des systèmes d’IA. Des preuves, pas des promesses.**

Chaque semaine, un modèle promet de tout changer, et des équipes engagent des budgets sur la foi de démos et de classements qui ne mesurent jamais leur travail. La vraie question n’est pas de savoir qui gagne le classement du mois. C’est de savoir si l’offre la plus chère du marché sert à ce que vous faites : beaucoup d’équipes paient tous les mois une puissance qu’elles n’utilisent jamais, pendant que d’autres économisent et livrent du faux.

Le piège est plus profond qu’un mauvais choix de marque : vous ne déployez pas un modèle, vous déployez une configuration. Un modèle, une infrastructure, un fournisseur, un niveau d’effort, des réglages. Deux équipes qui achètent le même nom n’obtiennent ni la même fiabilité, ni le même prix.

> Pour ce travail, à ce niveau attendu, sous ces contraintes de coût, de délai et de données, quelle configuration choisir ?

Benchmark Lab-X construit l’instrument qui tranche cette question. Il fait exécuter des travaux inspirés de projets réels, puis fait vérifier chaque résultat par un programme, jamais par une impression ni par un autre modèle. Le programme qui corrige ne sait pas quel système a produit la réponse qu’il note. Ce qui a réussi, ce que ça a coûté, le temps que ça a pris et dans quelles conditions : tout est publié, avec ses limites et sa date.

La discipline est le produit. Aucun vainqueur universel, aucune note globale, aucun résultat retouché à la main. Un classement par type de travail, valable pour ce qui a été mesuré, dans ce contexte, à cette date. Et quand la preuve manque, le banc s’abstient au lieu de conclure.

Sous cette formulation publique, l’unité de mesure est la carte d’usage et l’unité de classement est l’axe de score. Chaque axe qualifié produit son classement, borné au panel, au contexte et à la date mesurés. Aucun score global ne mélange des domaines différents, ni des appels directs et des agents outillés.

### 1.1 Autorité documentaire

| Document | Autorité |
|---|---|
| PRD.md, ce document | problème, valeur, utilisateurs, exigences produit, périmètre et jalons |
| [RULES.md](RULES.md) | invariants universels d’éligibilité, notation, agrégation et publication |
| [ARD.md](ARD.md) | objets, identités, flux, états, sécurité et preuves techniques |
| [README](../README.md) | compréhension publique et prise en main |
| [Modèle de carte](../tasks/TEMPLATE.md) | contrat réutilisable d’une carte d’usage |

Les décisions produit restent dans ce PRD. Les décisions techniques restent dans l’ARD. Aucun document de décision ou d’exploitation séparé n’est requis.

### 1.2 État actuel

Le projet est en pré-V0. Une chaîne verticale existe autour de `pentagone-rotatif`, mais les contrats documentaires corrigés ne sont pas encore implémentés de bout en bout.

La préparation locale B0 actuelle est une preuve historique `PREPARED_LOCAL_ONLY`. Elle n’autorise aucune collecte, aucun appel payant ni aucune publication. Elle ne prouve ni la conformité aux schémas cibles, ni la qualification de l’instrument, ni la valeur prédictive de la carte.

## 2. Problème et proposition de valeur

### 2.1 Une décision locale

Les benchmarks généralistes créent des références communes. Ils ne déterminent pas automatiquement quoi choisir pour une tâche locale, avec une route, un effort, un niveau attendu, une politique de données, un coût et une durée donnés.

Benchmark Lab-X relie donc chaque mesure à :

- un travail réel et un stimulus précis
- une décision que le résultat doit éclairer
- un panel de configurations défini avant collecte
- un effet observable et un instrument déterministe
- des limites de proxy explicites
- une conclusion bornée au panel, au contexte et à la date mesurés

### 2.2 Une qualité observée, pas une essence du modèle

Le projet évalue la réussite d’un travail concret. Cette qualité observée appartient à la configuration complète et au contexte de mesure, pas au seul nom du modèle.

Une carte peut éclairer un usage quotidien si son stimulus, ses contraintes et ses conséquences d’erreur représentent cet usage. Elle ne prouve jamais à elle seule la qualité générale d’un modèle ni l’expérience offerte par une application tierce, dont le prompt système, les outils, la mémoire, la route et les traitements peuvent différer.

### 2.3 Un instrument défendable

Un classement utile exige plus qu’un score :

1. des prédicats décidables par code
2. des témoins indépendants et des preuves de couverture
3. des identités et paramètres observables
4. des états qui ne transforment pas une absence de preuve en échec du modèle
5. une renotation possible sans nouvelle collecte
6. un audit humain de l’instrument, sans correction manuelle des notes
7. une publication limitée aux objets réellement qualifiés

## 3. Utilisateurs

| Code | Utilisateur | Travail à accomplir | État de connaissance |
|---|---|---|---|
| U1 | Ayo, mainteneur initial | construire une campagne, comprendre ses limites et choisir une configuration | besoin confirmé |
| U2 | Développeur du Lab-X | ajouter une carte, reproduire une campagne et utiliser un résultat | segment plausible, à interroger |
| U3 | Lecteur technique | comprendre ce qui a été mesuré et contrôler la méthode | public futur |
| U4 | Utilisateur du site | décrire un besoin et recevoir une recommandation étayée ou une abstention | vision V5-V6, besoin à valider |

Ayo reste propriétaire des décisions et validations jusqu’à délégation explicite à un autre mainteneur du Lab-X.

## 4. Vocabulaire produit et mesures

### 4.1 Unités

| Terme | Définition |
|---|---|
| Carte d’usage | travail réel, stimulus, décision visée et contrat ; unité comptée pour la couverture V0 et V1 |
| Axe de score | mesure déterministe appliquée à l’artefact d’une carte |
| Identité de base | mode, modèle, backend, provider épinglé et effort ; pour un agent, nom et version de l’agent en plus |
| Configuration mesurée | paramètres exacts d’une exécution, identifiés par `execution_manifest_hash` |
| Candidat lisible | libellé humain d’une configuration, jamais utilisé pour fusionner des résultats |
| Collecte planifiée | carte d’usage × configuration × index de run |
| Tentative | appel numéroté destiné à une collecte planifiée |
| Artefact accepté | première séquence d’octets candidate matérialisée par l’adaptateur, même vide ou invalide pour la tâche |
| Unité de score | axe × configuration × run |
| Résultat d’axe | agrégation des unités de score d’une configuration pour un axe |
| Profil | décision multi-axes préenregistrée, fondée sur des jointures explicites |
| Oracle | calculateur ou référence déterministe côté juge |
| Run design | répétition du même stimulus ou série d’instances distinctes, explicitement distinguées |

Une carte ne compte comme distincte que si elle soutient une décision et un stimulus distincts. Découper un artefact en plusieurs axes n’augmente pas la couverture.

### 4.2 Coûts

| Mesure | Contenu |
|---|---|
| Coût de tentative | montant facturé ou engagé pour une requête, succès ou non |
| Coût de collecte | somme des tentatives d’une collecte planifiée |
| Coût de résultat fonctionnel | coût total rapporté au nombre de résultats franchissant le minimum fonctionnel déclaré |
| Coût de campagne | toutes les tentatives payantes, y compris erreurs, reprises et réponses tardives facturées |
| Coût d’agent | modèle, outils payants et ressources d’exécution mesurées |
| Coût de profil | coût calculé uniquement depuis une charge d’usage préenregistrée ; absent si le profil n’agrège pas le coût |

Un coût reste un diagnostic ou une contrainte de départage préenregistrée. Il ne modifie jamais la note fonctionnelle.

### 4.3 Durées

| Mesure | Début et fin |
|---|---|
| Latence de tentative | envoi de la requête à réception ou constat d’absence de réponse |
| Attente de reprise | temps imposé entre deux tentatives |
| Durée de collecte | première tentative à fermeture de la collecte planifiée |
| Durée de vérification | début de notation à écriture du reçu de score |
| Travail utilisateur | temps humain requis avant le lancement et après la page provisoire |
| Temps mural de campagne | début du pré-vol à production de la page provisoire |

Une campagne de référence complète, dont les axes utilisés sont valides, est d’abord chronométrée de bout en bout. Ayo approuve ensuite la cible V0. La cible V1 est approuvée à partir des mesures V0. Aucune durée non mesurée n’est une exigence.

### 4.4 Qualité et fiabilité

- **Qualité observée** : réussite et niveau atteints sur un axe, dans le contexte documenté.
- **Répétabilité observée** : distribution de résultats obtenue en répétant le même stimulus. Un seul run ne permet aucune revendication de répétabilité, sauf déterminisme justifié de bout en bout.
- **Robustesse sur instances** : résultats sur des stimuli distincts d’une même famille. Elle ne doit pas être appelée répétabilité.
- **Fiabilité opérationnelle** : capacité du harnais et des fournisseurs à terminer les collectes planifiées sans erreur d’infrastructure.
- **Fiabilité du benchmark** : confiance bornée par le calibrage, l’audit, la reproductibilité et les limites du proxy.
- **Durabilité d’une recommandation** : maintien ou changement observé lors de campagnes longitudinales compatibles.

Ces notions sont publiées séparément. Aucune ne se déduit automatiquement d’une autre.

## 5. Objectifs et critères de réussite

| Priorité | Sens |
|---|---|
| P0 | bloque V0, invalide une mesure ou protège un actif critique |
| P1 | requis pour le prototype V1 |
| P2 | capacité V2 ou V3 |
| P3 | vision V4 à V6 |

### G1. Démontrer l’aide à la décision en V0 `[P0]`

- trois cartes d’usage exposées et qualifiées couvrent au moins deux domaines
- chaque carte nomme la décision, le stimulus, la représentativité, le panel et les limites du proxy
- six configurations forment une charge de référence, sans plafonner le registre
- une carte soumise au plan de répétition du protocole v2 utilise six runs ; une carte à un run ne revendique aucune répétabilité
- chaque axe qualifié possède son classement, ses distributions, coûts, durées et limites
- la démonstration se rejoue sans manipulation manuelle des résultats

Ces nombres décrivent une charge de référence et un objectif d’apprentissage. Ils ne prouvent pas la couverture d’un domaine.

### G2. Produire un prototype public en V1 `[P1]`

- dix cartes d’usage exposées couvrent les cellules prioritaires approuvées après V0
- douze configurations forment la charge de référence, sans devenir une limite universelle
- la campagne reprend après interruption sans doublon ni changement de lock
- un tiers reproduit une campagne complète depuis un clone frais et satisfait la métrique préenregistrée de chaque axe visé
- trois décisions d’usage documentent besoin, recommandation, choix et retour

Ces trois décisions constituent un minimum d’apprentissage. Elles ne garantissent pas la détection de tous les mauvais proxies.

### G3. Ne publier que des mesures défendables `[P0]`

- chaque axe publié a toutes ses unités requises en `SCORED`
- son audit fondé sur le risque est accepté
- tout changement de `verify_hash` impose de nouveaux reçus de couverture et une renotation de l’axe
- la page distingue les axes valides et provisoires sans statut scientifique global implicite
- aucune cohérence documentaire n’est présentée comme preuve de conformité runtime

### G4. Exécuter une campagne exploitable `[P0]`

- une commande lance la campagne depuis son manifeste et son lock
- le pré-vol ferme les décisions avant tout appel
- les reprises autorisées ne changent ni route, ni contenu, ni budget
- un plafond de dépense explicite couvre toutes les tentatives payantes
- une interruption produit des états explicites et une page provisoire exploitable
- le temps mural et le travail utilisateur sont mesurés avant fixation d’une cible

### G5. Reproduire ou renoter sans ambiguïté `[P1]`

Le produit distingue :

- la renotation des mêmes octets sous un nouvel instrument
- la reproduction du même harnais sur un autre hôte compatible
- une nouvelle collecte sous un nouveau lock
- une comparaison longitudinale entre campagnes compatibles

Une divergence d’empreinte n’est jamais masquée par un libellé commun.

### G6. Valider la couverture directe en V2 `[P2]`

Après V1, Ayo approuve une matrice versionnée `domaine × scénario`. Chaque cellule prioritaire porte besoin, décision, proxy, mode, statut et preuve de qualification. La matrice complète est gelée pour V2 ; une cellule est qualifiée ou retirée avec justification.

### G7. Piloter le suivi longitudinal en V4 `[P3]`

V4 compare au moins deux campagnes espacées selon un intervalle préenregistré. Le pilote distingue configuration évoluée, instrument évolué avec renotation commune et profil évolué. Deux campagnes montrent la faisabilité du suivi ; elles ne prouvent pas la durabilité générale du benchmark.

## 6. Modèle du produit

### 6.1 Taxonomie

Une carte porte trois axes descriptifs :

1. **domaine d’usage** : visuel et simulation, développement et automatisation, documents et provenance, données et calcul, planification et arbitrage, opérations et diagnostic, cyber
2. **mode d’exécution** : `direct` ou `agent`
3. **profondeur locale** : `courant`, `exigeant` ou `frontière`

La profondeur est locale à une lignée de cartes. Le domaine cyber ne détermine pas le mode : une carte cyber peut être directe ou outillée. Les exigences d’outillage ne s’appliquent que lorsqu’un candidat exécute des outils.

F1 à F4 sont des patrons techniques, pas des domaines :

| Patron | Effet mesuré |
|---|---|
| F1 | rendu ou simulation |
| F2 | exécution de programme |
| F3 | extraction ou calcul fermé |
| F4 | satisfaction de contraintes et écart à un optimum |

### 6.2 Classements et profils

Chaque axe qualifié classe les configurations dont toutes les unités requises sont `SCORED`. Les ex æquo restent ex æquo, sauf départage préenregistré.

Un profil V5 contient :

- une identité de base commune
- une version et des axes obligatoires
- le couple exact `(measurement_context_hash, execution_manifest_hash)` pour chaque axe
- les minima fonctionnels et contraintes dures
- la règle de départage
- la fenêtre de fraîcheur
- la politique d’abstention
- une charge d’usage seulement si coût ou durée sont réellement agrégés

Un profil s’abstient si un axe obligatoire est provisoire, périmé, absent ou incompatible. Il ne fusionne jamais des résultats par alias.

### 6.3 Registre V0

| Carte d’usage | Domaine | Décision | Stimulus | Axes | Statut |
|---|---|---|---|---:|---|
| `pentagone-rotatif` | visuel et simulation | choisir une configuration capable de produire une simulation conforme au contrat | même demande de génération d’un artefact exécutable | 5 | préparation locale, instrument non qualifié |

Aucune autre carte V0 n’est inventée dans ce registre. Les propositions futures seront ajoutées après validation de leur décision et de leur stimulus.

La tranche B0 comprend une carte d’usage, cinq axes et dix-neuf configurations. Sous le plan v2 à six runs, elle représente 114 collectes planifiées et 570 unités de score. Les cinq axes réutilisent chaque artefact : ils ne créent ni appel ni coût de collecte supplémentaire. B0 ne satisfait pas G1, qui exige trois cartes d’usage et deux domaines.

### 6.4 Cartes exposées et retenues

Une carte exposée passe par un embargo jusqu’à son premier résultat, puis son paquet rejouable est publié. Les campagnes suivantes déclarent le risque de contamination ; aucune absence de connaissance préalable n’est revendiquée.

Une carte retenue V4 reste locale et suit une politique d’accès, sauvegarde, restauration, exposition et retrait approuvée. Seul le stimulus nécessaire à son run officiel atteint le fournisseur. Une fuite avérée ou soupçonnée invalide sa série.

## 7. Exigences fonctionnelles

| ID | Pri. | Exigence | Preuve d’acceptation |
|---|---:|---|---|
| EF-001 | P0 | Une commande prépare et exécute une campagne depuis `campaign.toml` et un `campaign.lock` immuable | pré-vol, lock et exécution concordants |
| EF-002 | P0 | Une collecte planifiée produit au plus un artefact accepté, réutilisable par tous ses axes | un appel, cinq reçus de score, un seul coût de collecte |
| EF-003 | P0 | Chaque tentative et collecte possède un reçu immuable distinct du score | renotation sans mutation de collecte |
| EF-004 | P0 | Un adaptateur par route valide la réponse fournisseur et matérialise les premiers octets candidats, même vides | fixtures succès, vide, refus, troncature et réponse tardive |
| EF-005 | P0 | La machine d’état gère reprises, identité divergente, appel en vol incertain, abandon et `HOLD` selon RULES | scénarios de transition fermés |
| EF-006 | P0 | Un contrôle séparé refuse identité, paramètres, empreintes, états ou preuves incohérents | cas conforme accepté, cas altéré refusé |
| EF-007 | P0 | La notation produit un reçu immuable par axe et permet de renoter les mêmes octets | cinq axes puis nouvel instrument sans recollecte |
| EF-008 | P0 | L’agrégateur produit uniquement `results.html`, avec statuts propres à chaque axe | page mêlant axes valides et provisoires |
| EF-009 | P0 | Une comparaison exige des contextes compatibles et une jointure explicite des configurations | divergence et fusion par alias refusées |
| EF-010 | P0 | Toute carte documente décision, stimulus, axes, run design, besoin de sortie, ressources, panel, représentativité, conséquences d’erreur, proxy et retrait | pré-vol refusant un contrat incomplet |
| EF-011 | P0 | Chaque prédicat possède témoins positifs et négatifs indépendants et un reçu de couverture pour le `verify_hash` et l’environnement | reçu complet et cas témoin contradictoire |
| EF-012 | P0 | Chaque axe possède un plan d’audit fondé sur le risque, approuvé avant publication | sélection aveugle et conclusion limitée à l’échantillon |
| EF-013 | P0 | Reçus et page exposent les coûts et durées définis au §4 sans les intégrer au score | contrôle des agrégats et unités |
| EF-014 | P0 | Toute campagne payante possède prix datés, quotas, concurrence, plafond et réservation des appels en vol | arrêt propre sous plafond volontairement bas |
| EF-015 | P1 | Un tiers reproduit une campagne complète sous les mêmes contrats et compare la métrique préenregistrée de chaque axe visé | exercice depuis clone frais |
| EF-016 | P3 | Une comparaison longitudinale refuse les campagnes incompatibles et nomme ce qui a changé | cas configuration, instrument et profil |
| EF-017 | P3 | V5 recommande depuis un candidat de profil exact dont tous les axes obligatoires sont valides et assez frais, sinon s’abstient | quatre cas d’abstention |
| EF-018 | P2 | La matrice V2 gère cellules proposées, pilotes, qualifiées et retirées | export versionné approuvé |
| EF-019 | P2 | La piste agent possède identités, manifestes, environnements et classements propres | carte agent de bout en bout sans fusion avec direct |
| EF-020 | P3 | V6 trace chaque contrainte utilisateur comme `conservée`, `transformée`, `omise` ou `ambiguë` | omission ou ambiguïté importante bloque la qualification |
| EF-021 | P2 | Groq est qualifié comme backend distinct et crée un nouveau lock et une nouvelle campagne | indisponibilité sans fallback |
| EF-022 | P2 | Toute carte exécutant des outils applique les contrôles d’isolation ; le cyber offensif exige une autorisation séparée | preuve d’isolation et porte humaine |
| EF-023 | P1 | Le cycle d’exposition, d’embargo, de publication, de contamination et de retrait se reconstruit depuis les preuves | historique sans compteur manuel |
| EF-024 | P1 | Collectes, tentatives, retraits et clôture se reconstruisent depuis les reçus et le lock | recompte indépendant |

## 8. Exigences non fonctionnelles

| ID | Pri. | Exigence |
|---|---:|---|
| ENF-001 | P0 | La notation est déterministe, rejouable et aveugle à l’identité du candidat |
| ENF-002 | P0 | Le prompt provient d’une liste d’autorisation fermée et ne contient aucun actif côté juge |
| ENF-003 | P0 | Toute sortie exécutée est isolée du réseau, des secrets, du dépôt, des autres runs et des actifs juge |
| ENF-004 | P0 | Reçus, empreintes, états et causes sont immuables, complets et versionnés |
| ENF-005 | P0 | Aucun modèle, provider, backend, budget ou contenu ne change silencieusement |
| ENF-006 | P0 | Les cibles de temps ne sont fixées qu’après une campagne complète, chronométrée et dont les axes utilisés sont valides |
| ENF-007 | P3 | Le jeu retenu est local, restaurable et soumis à une politique d’accès et d’exposition explicite |
| ENF-008 | P1 | La documentation publique se comprend sans note privée ni artefact de relecture |
| ENF-009 | P0 | Les contenus destinés à un humain sont en français ; identifiants et données machine conservent leur forme nécessaire |
| ENF-010 | P0 | Aucun secret, donnée personnelle, contenu client ou identifiant local d’orchestration n’entre dans un prompt, reçu public, log public ou HTML |
| ENF-011 | P3 | Le site V5 ne détient aucune clé fournisseur et distingue courant, historique, non couvert et abstention |
| ENF-012 | P0 | Qualité, répétabilité, robustesse, fiabilité opérationnelle et fiabilité du benchmark sont présentées séparément |
| ENF-013 | P0 | Les contrats de hash ont des listes de champs fermées, des schémas versionnés et une canonicalisation unique |
| ENF-014 | P0 | Une validation documentaire ne vaut jamais preuve de conformité de l’implémentation ou d’une campagne |

## 9. Trajectoire

| Jalon | Statut | Contenu | Preuve de sortie |
|---|---|---|---|
| Pré-V0 | actuel | chaîne verticale et contrats en évolution | aucune publication revendiquée |
| V0, POC | engagé | trois cartes d’usage, deux domaines, campagne et HTML | G1 à G4 satisfaits et cible de durée approuvée après mesure |
| V1, prototype public | engagé | dix cartes, reprise, reproduction et retours d’usage | G2 et G5 satisfaits |
| V2, couverture directe | conditionnel | matrice complète et pilote cyber défensif synthétique | cellules gelées qualifiées ou retirées |
| V3, agents outillés | conditionnel | piste agent isolée et distincte | une carte agent qualifiée de bout en bout |
| V4, benchmark vivant | pilote | cartes exposées renouvelées et série retenue | comparaison de deux campagnes compatibles, sans généralisation |
| V5, consultation | vision | profils datés, frais et abstention | aucune recommandation incompatible ou périmée |
| V6, studio | vision | brouillon synthétique puis qualification humaine | fidélité tracée, aucune carte auto-approuvée |

### 9.1 Cyber

Le cyber est un domaine, pas un mode. V2 commence par un pilote défensif sur données et environnements synthétiques. Une extension offensive outillée reste facultative et exige modèle de menace, cible synthétique sans route vers un système réel, environnement éphémère, réseau sortant refusé, outils figés, quotas, arrêt d’urgence, journal complet, remise à zéro et décision humaine séparée. Le projet ne cherche jamais à contourner un garde-fou fournisseur.

### 9.2 Site et studio

V5 consulte des résultats existants. Il renvoie jusqu’à trois recommandations seulement si le profil le permet ; il ne complète pas artificiellement la liste.

V6 accepte une description non sensible, produit un brouillon et trace la fidélité de chaque contrainte. Une campagne n’est possible qu’après instrumentation, témoins indépendants, revue de sécurité si nécessaire et approbation humaine.

## 10. Non-objectifs

- score global entre domaines ou entre pistes direct et agent
- vainqueur universel indépendant d’une tâche, d’un panel et d’une contrainte
- reproduction automatique de l’expérience d’une application éditeur
- score mécanique fondé sur un jugement esthétique ou sémantique ouvert
- juge génératif qui approuve sa propre tâche ou son propre score
- entraînement ou fine-tuning de modèles
- exécution cyber sur une cible réelle ou contournement de garde-fous
- données personnelles, secrets ou contenus clients dans une carte notée
- score instantané d’une tâche utilisateur avant instrumentation et validation
- recherche web, outils ou sessions multi-tours dans la piste directe V0
- fallback silencieux vers un autre backend, provider ou modèle

## 11. Dépendances

| Dépendance | Usage | Limite ou porte |
|---|---|---|
| OpenRouter | backend primaire | disponibilité, identité servie, politiques, prix et quotas |
| Providers servis | exécution réelle | révisions opaques, paramètres et dépréciations |
| Groq | backend distinct éventuel | qualification, nouveau lock et nouvelle campagne |
| Chromium, runtimes, solveurs | vérification déterministe | versions, ressources, isolement et tests d’évasion |
| Producteurs de témoins | calibrage | indépendance, provenance et couverture |
| Stockage local et second humain | jeu retenu V4 | approuvés avant première campagne retenue |
| Licence et nom public | publication officielle | décisions humaines avant publication |

## 12. Risques et parades

| ID | Pri. | Risque | Parade et limite |
|---|---:|---|---|
| RP-01 | P0 | le proxy ne prédit aucun usage réel | décision, représentativité, conséquences d’erreur et retour d’usage |
| RP-02 | P0 | le vérificateur accepte une sortie fausse | témoins, couverture, contre-exemples et audit fondé sur le risque |
| RP-03 | P0 | un actif juge atteint le candidat | liste fermée, refus des liens et séparation d’environnement |
| RP-04 | P0 | une sortie exécutée s’échappe | sandbox versionnée, réseau refusé et limites de ressources |
| RP-05 | P0 | une fusion par alias compare des configurations différentes | jointure par empreintes exactes |
| RP-06 | P1 | une route opaque évolue | reçus datés et conclusion limitée à l’endpoint observé |
| RP-07 | P1 | coûts, quotas ou durée empêchent la campagne | pré-vol, plafond, réservations et page incomplète explicite |
| RP-08 | P1 | une carte exposée est mémorisée | paquet public, risque déclaré, renouvellement ou retrait |
| RP-09 | P3 | une recommandation V5 devient périmée | fraîcheur et abstention préenregistrées |
| RP-10 | P3 | V6 omet une contrainte importante | table de fidélité et blocage de qualification |
| RP-11 | P2 | une carte cyber atteint une cible réelle | environnement synthétique et porte de sécurité séparée |
| RP-12 | P0 | documentation et code divergent | contrats versionnés, contrôles statiques et preuve runtime séparée |
| RP-13 | P0 | cinq axes sont comptés comme cinq usages ou cinq appels | registre par carte et comptage par collecte |

## 13. Statut de B0 et lot suivant

Les décisions B0-01 à B0-07 sont maintenues. B0-08 autorise `selection-route/v3` : quantification exacte lorsqu’elle est déclarée ou lorsque la route est tierce ; statut structuré `not_disclosed` seulement pour une API propriétaire gérée directement par l’éditeur, sans valeur supposée et sans rang dans l’échelle numérique des formats. La [carte officielle MiMo V2.5](https://huggingface.co/XiaomiMiMo/MiMo-V2.5) identifie le checkpoint et son déploiement recommandé comme FP8 ; le registre fixe donc `format_reference = "fp8"`. Le snapshot proposé du 8 août 2026 conserve Mimo chez Xiaomi en FP8 et Kimi chez Moonshot AI en MXFP4. Aucun pin ne dérive ; B0-08 est `APPROVED`.

B0-09 conserve un plafond de 55 dollars. Le snapshot proposé `66c1a6b71e88b7d2484704133d10c5636ac4fa341064befa1e5ab9e23544558a` recalcule exactement 31,812500 dollars, sans écart avec l’estimation approuvée et avec 23,187500 dollars de marge sous le plafond. Le nouveau contrat exige néanmoins que l’approbation vise le chemin et l’empreinte exacts de ce snapshot proposé ; le snapshot approuvé en reste une transformation fermée et vérifiable. B0-09 reste en `HOLD` jusqu’à cette liaison explicite. B0-10 reste en `HOLD`.

Avant toute nouvelle autorisation payante, le lot d’implémentation doit :

1. implémenter les contrats de hash et d’état cibles
2. retirer le plancher universel de sortie du code
3. migrer les reçus et contrôles
4. requalifier les témoins et assainir leurs provenances publiques
5. régénérer le lock
6. recalculer l’estimation sous le plafond inchangé
7. obtenir une nouvelle approbation d’Ayo

## 14. Sources de conception

| Source | Fait utilisé | Conséquence locale |
|---|---|---|
| [SWE-bench](https://github.com/SWE-bench/SWE-bench) | tâches logicielles issues de dépôts exécutables | référence complémentaire pour le développement |
| [Terminal-Bench](https://github.com/laude-institute/terminal-bench) | tâches réalisées par des agents dans un terminal | piste agent séparée des appels directs |
| [EvalPlus](https://arxiv.org/abs/2305.01210) | des tests supplémentaires révèlent des programmes faux auparavant acceptés | diversité d’instances et qualification des tests |
| [LiveBench](https://arxiv.org/abs/2406.19314) | questions renouvelées et notation objective | cycle d’exposition et renouvellement |
| [FinQA](https://finqasite.github.io/) | calculs et faits supports annotés | sorties fermées et provenance vérifiable |
| [ConstraintBench](https://arxiv.org/abs/2602.22465) | contraintes vérifiées et comparaison à un optimum | patron F4 |

Ces sources éclairent des choix locaux. Elles ne créent aucune règle universelle.
