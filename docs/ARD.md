---
style_gate: pass
---

# ARD : modèle logique de Benchmark Lab-X

Décisions propriétaires intégrées : 31 août 2026

## 1. Portée

Cet ARD décrit les objets, frontières et flux minimaux du premier prototype. Il ne choisit ni plateforme, ni stockage, ni interface, ni technologie future.

Le [PRD](PRD.md) gouverne le besoin et le périmètre. Les [règles](RULES.md) portent les invariants. Le [glossaire](../CONTEXT.md) fixe le sens des termes. Le [gabarit de carte](../tasks/TEMPLATE.md) prépare le contrat d'une tâche.

## 2. Principes

1. Le modèle est l'objet produit mis en avant.
2. La configuration observée, reliée aux conditions de test communes, est l'unité de preuve.
3. Le premier prototype compare uniquement des accès directs ou API sous le même Pi.
4. Pi est obligatoire ; son état appartient aux conditions de test communes déclarées avant le premier candidat.
5. Chaque tâche possède un contrat de réussite approuvé avant toute sortie.
6. Une sortie brute précède son contrôle et son verdict.
7. L'admissibilité précède le coût.
8. Une conclusion est située et n'isole pas causalement le modèle.
9. Les campagnes historiques restent immuables.
10. La complexité entre seulement après preuve d'un besoin antérieur.
11. L'utilisation commence avec la communauté Lab X pour éprouver et contribuer ; la vocation publique ultérieure reste séparée de toute autorité de publication.

## 3. Pi comme frontière constante

Pi est le seul harnais du premier prototype. Sa constance réduit une source de variation entre configurations ; elle ne prouve pas que Pi est neutre ou que le modèle seul cause le résultat. Pi, ses paquets et l'environnement sont présentés une fois comme conditions de test communes, jamais comme propriétés répétées de chaque modèle.

### 3.1 État de Pi relevé le 30 août 2026

**FAIT ÉTABLI**, relevé du 30 août 2026 depuis le contrat d'harmonisation et `/Users/ayo/.pi/agent/settings.json` ; chaque valeur porte son statut :

| Champ | Valeur relevée | Statut |
|---|---|---|
| Paquet ou fork | `@earendil-works/pi-coding-agent` | déclaré |
| Version | `0.84.4` d'après `lastChangelogVersion` ; version exécutée `INCONNU` | déclaré, non vérifié à l'exécution |
| Paquets configurés | `npm:pi-context-view`, `npm:@ff-labs/pi-fff`, `npm:@dietrichgebert/ponytail` | configuré, non prouvé actif |
| Skills exclus | `!skills/**`, `!/Users/ayo/.agents/skills/**` | configuré |
| Réglages par défaut | `defaultProvider` `vllm`, `defaultModel` `qwen38-27b`, `defaultThinkingLevel` `medium` | configuré ; les valeurs effectives par candidat sont relevées dans sa configuration observée |
| Outils | `INCONNU` | non relevé |
| Contexte | `INCONNU` | non relevé |
| Environnement d'exécution candidat | aucune exécution candidate dans cette tranche | sans objet |
| Date de relevé | 30 août 2026 | observé |

`déclaré` vient d'une source documentaire, `configuré` d'un fichier de réglages, `actif` d'une preuve de chargement, `observé` d'une exécution. `lastChangelogVersion` ne prouve pas la version exécutée. Les valeurs `INCONNU` ne sont pas remplacées par une hypothèse. Avant une exécution réelle, le reçu des conditions communes complète la version exécutée, les outils, le contexte et l'environnement, puis fige l'ensemble pour les candidats comparés.

## 4. Objets et responsabilités

### 4.1 Tâche et contrat de réussite

Responsabilité : relier un besoin précis à un résultat attendu, des obligations, des erreurs éliminatoires, trois verdicts permis et au maximum deux critères secondaires, puis fixer la base de coût avant exécution : périmètre d'attribution, tentatives comptées, unité commune et règle de conversion éventuelle.

Le contrat est préparé et approuvé par le responsable de campagne avant toute exécution. Une modification après observation d'une sortie crée un nouveau contrat ; elle ne réécrit pas le précédent.

### 4.2 Conditions de test communes

Responsabilité : déclarer une fois, avant le premier candidat, ce que toutes les configurations comparées partagent : état de Pi (paquet ou fork, version, paquets, outils, skills, contexte, réglages par défaut), environnement et date de gel. Chaque valeur porte son statut : déclarée, configurée, active ou observée.

Toute configuration comparée référence ces conditions. Une condition commune modifiée ouvre une nouvelle comparaison ; elle ne requalifie pas les sorties déjà obtenues. Aucun schéma physique, registre versionné, API ou service n'est prescrit.

### 4.3 Configuration observée

Responsabilité : conserver, pour un candidat, tout ce qui borne l'attribution de sa sortie :

- fournisseur
- modèle
- accès direct ou API
- route demandée et route observée
- paramètres
- effort de raisonnement
- identité demandée et identité observée
- référence aux conditions de test communes

Une demande et une observation restent distinctes. Une identité, une route ou une valeur absente reste `INCONNU`.

### 4.4 Acquisition

Responsabilité : exécuter une unité autorisée et conserver :

- tâche et contrat
- configuration demandée et observée
- requête
- sortie brute ou absence de sortie
- chronologie
- coût observé
- incident, retry et intervention
- reçu relié aux autres preuves

Une acquisition ne décide pas de son propre verdict.

### 4.5 Évaluation

Responsabilité : appliquer les erreurs éliminatoires et obligations du contrat, puis produire exactement un verdict publiable :

- `SATISFAIT`
- `NE SATISFAIT PAS`
- `INDETERMINE`

Le verdict porte les éléments exigés par la règle « Verdict explicable » des [règles](RULES.md#6-erreurs-et-verdict) : valeur, motif court, critères ou constats concernés, références de preuve et responsable. Les critères secondaires décrivent uniquement les résultats déjà `SATISFAIT`. Ils ne compensent jamais une erreur éliminatoire.

### 4.6 Vue de décision

Responsabilité : exclure `NE SATISFAIT PAS` et `INDETERMINE` de la recommandation économique tout en laissant leur dépense observée visible, comparer seulement les coûts connus et comparables des configurations `SATISFAIT`, puis exposer les bénéfices prévus sur les seuls critères secondaires déclarés, selon les règles de [coût et bénéfices](RULES.md#8-coût-et-bénéfices). Si le coût d'au moins une configuration `SATISFAIT` est inconnu ou non comparable, elle conserve son admissibilité, les coûts connus restent visibles, mais la vue ne déclare aucune option globalement moins chère et marque la conclusion économique `INCOMPLETE`.

Elle ne calcule aucun score global, ne fusionne jamais coût et bénéfice, et ne modifie ni sortie, ni reçu, ni verdict source.

### 4.7 Restitution

Responsabilité : rendre la conclusion compréhensible et vérifiable en exactement deux étapes visibles : admissibilité de toutes les configurations avec verdict et motif synthétique, puis coût observé de toutes les configurations avec leur statut économique. La recommandation économique et les bénéfices prévus restent limités aux seules configurations `SATISFAIT`. Une conclusion économique `INCOMPLETE` laisse les coûts connus visibles sans déclarer d'option globalement moins chère. Critères, preuves, incidents, inconnues, limite d'attribution et conditions de test communes s'ouvrent sur demande, sans former une troisième étape.

La restitution affiche la limite d'attribution : le verdict porte sur la configuration observée sous les conditions communes, pas sur le modèle isolé. Elle ne produit ni podium général, ni score global, ni graphique trompeur.

## 5. Flux minimal

```text
Besoin précis du demandeur-lecteur
  -> Contrat de réussite préparé et approuvé par le responsable de campagne
     -> Conditions de test communes déclarées avant le premier candidat
        -> Configurations modèle + accès direct/API sous ces conditions
           -> Acquisition autorisée
              -> Sortie brute ou incident
                 -> Erreurs éliminatoires et obligations
                    -> SATISFAIT / NE SATISFAIT PAS / INDETERMINE, avec motif et preuves
                       -> Coût observé de toutes les configurations
                          -> Recommandation parmi les seuls SATISFAIT
                             -> Bénéfices prévus des SATISFAIT plus chers
                                -> Restitution en deux étapes
```

Cette représentation décrit des dépendances. Elle n'impose aucun service ni schéma physique.

## 6. Identités, jointures et immutabilité

Chaque tâche, contrat, conditions de test communes, configuration, acquisition, sortie et verdict possède une identité vérifiable. Les jointures relient explicitement :

- la tâche à son contrat approuvé
- la configuration à ses conditions de test communes
- l'acquisition à sa configuration demandée et observée
- la sortie au reçu d'acquisition
- le verdict à la sortie, au contrat utilisés et à ses preuves
- la vue de décision aux seuls verdicts compatibles

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

V0 et V1 restent dans leurs questions, panels, schémas et verdicts d'origine. Une vue historique peut les résumer fidèlement. Elle ne peut pas :

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
- appels candidats, achats, dépassements et retries soumis à autorité explicite

## 11. Éléments différés

Les abonnements, produits agentiques, autres harnais dépouillés, comparaisons de harnais, OrbStack et `perso-hermes` n'appartiennent pas à cette architecture active. Ils ne reçoivent ni objet, ni flux, ni interface anticipée. Leur étude dépend d'un besoin démontré dans une itération antérieure, conformément aux [règles KISS](RULES.md#11-kiss-et-évolution).

Le nom `V2-alpha` désigne la prochaine phase sans canoniser de plateforme, de conteneur, de service, d'architecture ou de découpage. Ces choix relèvent de décisions distinctes.
