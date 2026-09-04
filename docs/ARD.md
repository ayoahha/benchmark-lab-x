---
style_gate: pass
---

# ARD : contrat d'architecture de Benchmark Lab-X

## 1. Portée

Cet ARD fixe les objets, frontières, flux et contraintes de l'architecture retenue. Il prescrit ce que l'implémentation doit garantir, sans attester sa construction ou son déploiement. Les versions et états livrés se vérifient dans le code et les reçus, hors de ce document.

Le [PRD](PRD.md) gouverne le besoin et le périmètre. Les [règles](RULES.md) portent les invariants. Le [glossaire](../CONTEXT.md) fixe le sens des termes. Le [gabarit de carte](../tasks/TEMPLATE.md) prépare le contrat d'une tâche.

## 2. Principes

1. Le modèle est l'objet produit mis en avant.
2. La configuration observée, reliée aux conditions de test communes, est l'unité de preuve.
3. Les configurations comparables utilisent des accès directs ou API sous le même Pi.
4. Pi est obligatoire ; son état appartient aux conditions de test communes déclarées avant le premier candidat.
5. Chaque version de tâche possède des cas identifiés et un contrat approuvé avant toute sortie.
6. Une sortie brute précède son contrôle et son verdict.
7. L'admissibilité précède le coût.
8. Une conclusion est située et n'isole pas causalement le modèle.
9. Les campagnes historiques restent immuables.
10. La complexité entre seulement après preuve d'un besoin antérieur.
11. La consultation publique est séparée des opérations protégées ; le lot V2 bêta n'expose aucune contribution publique.

## 3. Pi comme frontière constante

Pi est le harnais commun des comparaisons. Sa constance réduit une source de variation entre configurations ; elle ne prouve pas que Pi est neutre ou que le modèle seul cause le résultat. Pi, ses paquets et l'environnement sont présentés une fois comme conditions de test communes, jamais comme propriétés répétées de chaque modèle.

### 3.1 Identité de l'environnement d'exécution

Chaque campagne doit figer le paquet ou fork Pi, sa version exécutée, les empreintes nécessaires, les paquets, outils, skills, contexte, réglages, environnement et date de gel. Les paramètres demandés et observés restent distincts.

`déclaré` vient d'une source documentaire, `configuré` d'un réglage, `actif` d'une preuve de chargement et `observé` d'une exécution. Une valeur absente reste `INCONNU`. Un réglage du poste ou un numéro de changelog ne prouve pas la version exécutée.

La campagne doit conserver son environnement identifié indépendamment des mises à jour du poste et du site. Une nouvelle version de présentation ne doit ni réécrire les preuves ni imposer une nouvelle acquisition.

## 4. Objets et responsabilités

### 4.1 Tâche, version et cas d'essai

Responsabilité : relier un besoin précis à un résultat attendu, des obligations, des erreurs éliminatoires, trois verdicts permis et au maximum deux critères secondaires, puis fixer la base de coût avant exécution : périmètre d'attribution, tentatives comptées, unité commune et règle de conversion éventuelle.

La tâche possède un identifiant stable ; chaque version relie un contrat approuvé aux cas d'essai et à leurs entrées identifiées. Une modification après observation crée une nouvelle version. Le catalogue référence ces tâches sans confondre leurs versions.

Une campagne référence une version de tâche, les cas retenus, le panel, les conditions communes et les autorisations. Plusieurs campagnes peuvent référencer une même version. Une éventuelle agrégation des cas exige une règle préalable ; les verdicts par cas restent accessibles.

### 4.2 Conditions de test communes

Responsabilité : déclarer une fois, avant le premier candidat, ce que toutes les configurations comparées partagent : état de Pi (paquet ou fork, version, paquets, outils, skills, contexte, réglages par défaut), environnement et date de gel. Chaque valeur porte son statut : déclarée, configurée, active ou observée.

Toute configuration comparée référence ces conditions. Une condition commune modifiée ouvre une nouvelle comparaison ; elle ne requalifie pas les sorties déjà obtenues.

### 4.3 Configuration observée

Responsabilité : conserver, pour un candidat, tout ce qui borne l'attribution de sa sortie :

- fournisseur
- modèle et révision exacte exigée par le contrat
- accès direct ou API
- route demandée et route observée
- paramètres demandés et observés
- effort de raisonnement
- identité demandée et identité observée
- référence aux conditions de test communes

Une demande et une observation restent distinctes. Une identité, une route ou une valeur absente reste `INCONNU`. Une révision imposée ne peut pas être remplacée par un alias mobile non vérifié. Le panel fige la liste des configurations ; il ne prouve pas leur disponibilité.

Pour une configuration locale, l'identité inclut les poids, leur révision, la quantification, le serveur d'inférence et le matériel nécessaires à l'attribution.

### 4.4 Acquisition

Responsabilité : exécuter une unité autorisée et conserver :

- campagne, version de tâche, cas, contrat et identifiant de tentative
- configuration demandée et observée
- requête
- sortie brute ou absence de sortie
- chronologie
- coût observé
- incident, retry et intervention
- reçu relié aux autres preuves

Une acquisition ne décide pas de son propre verdict. L'exécuteur doit enregistrer l'intention avant l'appel puis conserver le reçu ou l'ambiguïté. Après interruption, une tentative aux effets inconnus ne doit pas être rejouée ; une cellule jamais lancée reste distincte d'un échec.

### 4.5 Évaluation

Responsabilité : appliquer les erreurs éliminatoires et obligations du contrat, puis produire exactement un verdict publiable :

- `SATISFAIT`
- `NE SATISFAIT PAS`
- `INDETERMINE`

L'évaluation s'applique à un cas et une tentative identifiés. Le verdict porte les éléments exigés par la règle « Verdict explicable » des [règles](RULES.md#6-erreurs-et-verdict) : valeur, motif court, critères ou constats concernés, références de preuve et responsable. Les critères secondaires décrivent uniquement les résultats déjà `SATISFAIT`. Ils ne compensent jamais une erreur éliminatoire.

### 4.6 Vue de décision

Responsabilité : exclure `NE SATISFAIT PAS` et `INDETERMINE` de la recommandation économique tout en laissant leur dépense observée visible, comparer seulement les coûts connus et comparables des configurations `SATISFAIT`, puis exposer les bénéfices prévus sur les seuls critères secondaires déclarés, selon les règles de [coût et bénéfices](RULES.md#8-coût-et-bénéfices). Si le coût d'au moins une configuration `SATISFAIT` est inconnu ou non comparable, elle conserve son admissibilité, les coûts connus restent visibles, mais la vue ne déclare aucune option globalement moins chère et marque la conclusion économique `INCOMPLETE`.

Elle ne calcule aucun score global, ne fusionne jamais coût et bénéfice, et ne modifie ni sortie, ni reçu, ni verdict source.

### 4.7 Restitution

Responsabilité : rendre accessibles le catalogue, la tâche et ses campagnes, puis la conclusion contextualisée, le tableau commun des configurations et leurs preuves. L'admissibilité gouverne le calcul économique sans imposer deux sections successives.

Une publication doit identifier la restitution et les preuves approuvées, indépendamment de l'état d'exécution. Une campagne partielle doit conserver ses observations exploitables et signaler sa couverture. Une conclusion économique `INCOMPLETE` interdit une option déclarée globalement moins chère.

La restitution affiche la limite d'attribution : le verdict porte sur la configuration observée sous les conditions communes, pas sur le modèle isolé. Elle ne produit ni podium général, ni score global, ni graphique trompeur.

## 5. Flux minimal

```text
Besoin précis du demandeur-lecteur
  -> Version de tâche, contrat et cas approuvés par le responsable de campagne
     -> Campagne, panel, conditions communes et autorisations figés
        -> Configurations modèle + accès direct/API sous ces conditions
           -> Acquisition autorisée
              -> Sortie brute ou incident
                 -> Erreurs éliminatoires et obligations
                    -> SATISFAIT / NE SATISFAIT PAS / INDETERMINE, avec motif et preuves
                       -> Coût observé de toutes les configurations
                          -> Recommandation parmi les seuls SATISFAIT
                             -> Bénéfices prévus des SATISFAIT plus chers
                                -> Publication approuvée : conclusion, comparaison et preuves
```

Cette représentation décrit les dépendances métier ; les composants doivent respecter les frontières de la section 12.

## 6. Identités, jointures et immutabilité

Chaque tâche, version, cas, campagne, contrat, conditions communes, configuration, acquisition, sortie, verdict et publication possède une identité vérifiable. Les jointures relient explicitement :

- la tâche à ses versions, contrats et cas
- la campagne à sa version de tâche, ses cas, son panel et ses autorisations
- la configuration à ses conditions de test communes
- l'acquisition à sa configuration demandée et observée
- la sortie au reçu d'acquisition
- le verdict à la sortie, au contrat utilisés et à ses preuves
- la vue de décision aux seuls verdicts compatibles
- la publication à la vue et aux preuves explicitement approuvées

Un libellé public n'est pas une clé de jointure. La sortie brute et les preuves historiques ne sont pas corrigées silencieusement.

Une vue de décision refuse au minimum :

- contrats différents ou modifiés après résultat
- conditions de test communes différentes entre candidats présentés comme comparables
- identité incomplète au regard du contrat
- sortie modifiée après acquisition
- bénéfice absent des critères prévus
- recommandation économique fondée sur une configuration non `SATISFAIT` ou sur un coût `INCONNU`

## 7. Verdict, coût et bénéfices

L'ordre interne est celui des six opérations des [règles](RULES.md#7-ordre-de-décision) :

1. erreurs éliminatoires ;
2. obligations et preuve ;
3. verdict d'admissibilité ;
4. exclusion de `NE SATISFAIT PAS` et `INDETERMINE` de la recommandation économique ;
5. coût connu et comparable entre les seuls `SATISFAIT` ;
6. bénéfices prévus des options `SATISFAIT` plus chères.

Une valeur absente reste `INCONNU`. Un résultat `INDETERMINE` n'est ni un succès par défaut ni un échec inventé. Le coût n'est jamais agrégé à l'admissibilité ni au bénéfice dans une note unique. Une conclusion économique `INCOMPLETE` n'est pas un quatrième verdict.

## 8. Incidents et attribution

| Classe | Sens | Effet |
|---|---|---|
| Sortie obtenue | artefact disponible pour le contrat | entre dans l'évaluation |
| Incident fournisseur | fournisseur ou route n'accomplit pas l'unité prévue | observation attribuable, séparée du contenu de la sortie |
| `HARNESS_ERROR` | Pi ou le dispositif empêche l'attribution | réduit la couverture, ne devient pas `NE SATISFAIT PAS` |
| Preuve manquante | identité ou preuve nécessaire absente | `INDETERMINE` ou `INCONNU` selon le champ |

Le verdict n'attribue pas au seul modèle un effet que le fournisseur, l'effort, Pi ou ses réglages peuvent influencer, et ne permet pas d'affirmer que le modèle isolé aurait produit la même sortie avec un autre harnais, fournisseur, contexte ou environnement.

## 9. Vues historiques

Les campagnes historiques restent dans leurs questions, panels, schémas et verdicts d'origine. Une vue historique peut les résumer fidèlement. Elle ne peut pas :

- renoter une sortie et appeler cela le verdict d'origine
- fabriquer des répétitions ou une stabilité
- déduire un rang qualitatif des `FAIL G-001`
- transformer un `PASS` de qualification du harnais en `PASS` produit
- produire une baseline, un coût par résultat acceptable ou une recommandation absente
- remplacer une inconnue par une estimation

## 10. Sécurité et autorité

- données réelles ou sensibles exclues sans autorité explicite
- secrets absents des tâches, sorties publiées et reçus publics
- permissions minimales et outils déclarés
- sorties brutes privées par défaut avant décision de publication
- intégration Git, exécution produit, appels candidats et budget, provisionnement et publication soumis à des autorités distinctes
- champs, filtres, chemins, contenus et sorties considérés comme non fiables : validation côté serveur, requêtes paramétrées et rendu échappé
- aucune donnée candidate rendue comme code actif dans le site ; aucune opération protégée autorisée par un simple libellé ou identifiant public

## 11. Éléments différés

Les extensions de périmètre suivent le PRD et les règles KISS. Aucun microservice, Kubernetes, bus de messages, système de plugins ou moteur d'inférence supplémentaire n'est requis par cette architecture.

## 12. Composants et exploitation

Le front-end et le back-end appartiennent au même dépôt produit et doivent être servis depuis une même VM Linux, sous une même origine. Le moteur commun doit être vérifiable sous Linux et macOS ; les dépendances propres à l'exploitation Linux restent dans cette couche.

L'application doit exposer la consultation publique et protéger les commandes d'exploitation. Un processus supervisé, issu du même produit et indépendant des requêtes HTTP, doit exécuter les campagnes. Une interface opérateur web n'est pas exigée.

SQLite sur disque local doit conserver les métadonnées transactionnelles. Les pièces privées doivent vivre hors du dépôt et des répertoires de release. Les références et empreintes relient état et pièces ; sauvegarde et restauration doivent couvrir les deux. L'état d'exécution, le verdict et la publication sont distincts.

Les secrets candidats doivent être accessibles au seul exécuteur autorisé et absents du navigateur, des journaux publics et des artefacts de release. Les identités de déploiement restent séparées. Le code éventuellement produit par une tâche doit être exécuté dans un environnement séparé du serveur web et des secrets.

GitHub porte le produit et le backlog ; Forgejo doit piloter la release et le déploiement. Le contrôleur appartient à cybrel-infrastructure et doit consommer une identité de source ou d'artefact approuvée, vérifier son empreinte et produire un reçu de déploiement. Ses accès au runner, au réseau et aux secrets doivent être définis avant son installation. Aucun miroir bidirectionnel ni deuxième backlog produit n'est requis.

Le provisionnement doit utiliser les primitives Terraform, l'orchestrateur Bash et Ansible de Cybrel. L'exposition doit respecter la chaîne Consul, consul-template et HAProxy, notamment la déclaration initiale du backend avant son référencement dynamique. Une release produit ne doit pas relancer implicitement le provisionnement.

Graph Engineering Tool reste un outil indépendant d'exécution agentique des Stories. Il ne remplace ni le moteur des campagnes ni leurs autorisations. Son identité doit être épinglée dans le contrat de chaque run ; aucun numéro de version de cet outil n'est fixé ici.
