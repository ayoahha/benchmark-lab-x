---
style_gate: pass
---

# Registre de vérité du pré-cadrage avant entretien client

## Identité et portée

- Paquet : `PRECADRAGE-ENTRETIEN-CLIENT-V0`
- Statut : prospectif
- Scénario : entièrement synthétique
- Usage : qualifier la capacité d'un candidat à transformer des notes brutes en pré-cadrage structuré
- Hors usage : mesure de performance, classement, conseil envoyé au client, verdict de conformité ou décision autonome
- Chaîne de qualification : brief humain minimal → consolidation facultative par des humains ou des LLM → paquet compilé → approbation humaine liée aux empreintes → stimulus candidat → contrôles automatiques → revue humaine aveugle
- Chaîne métier : notes brutes → pré-cadrage structuré → revue du consultant → entretien client → décision humaine

La qualification vérifie un contrat de sortie. Elle ne constitue pas une mesure comparative. Son acceptabilité officielle exige un résultat automatique global `PASS` et un verdict humain aveugle `ACCEPTABLE`.

## Ergonomie et autorité

L'humain fournit le brief minimal, les exemples métier, les arbitrages et l'approbation. Une consolidation facultative peut recevoir des propositions humaines ou produites par un LLM. Ces propositions n'ont aucune autorité d'approbation.

La compilation produit le paquet détaillé : registre, IDs internes, témoins, matrices, ancres neutres, empreintes et liaisons mécaniques de provenance. Les IDs internes sont des détails compilés. L'auteur métier ne les saisit pas et le stimulus ne les révèle jamais comme corrigé.

L'approbation humaine est la seule autorité. Elle porte sur les empreintes exactes du brief, du stimulus, du registre et des témoins compilés. Toute modification après approbation invalide cette liaison et exige une nouvelle approbation humaine. Ce paquet ne décrit pas l'organisation détaillée d'un atelier multi-LLM.

## Glossaire minimal

- ID: TERM-001
  - Terme : note brute
  - Sens : énoncé synthétique fourni au candidat, sans garantie d'exactitude ni de cohérence avec les autres notes
- ID: TERM-002
  - Terme : fait autorisé
  - Sens : énoncé que le pré-cadrage peut reprendre comme établi dans le scénario
- ID: TERM-003
  - Terme : contrainte critique
  - Sens : limite qui doit rester explicite pour empêcher une recommandation ou une action interdite
- ID: TERM-004
  - Terme : inconnue
  - Sens : information nécessaire au cadrage que les notes ne permettent pas d'établir
- ID: TERM-005
  - Terme : hypothèse permise
  - Sens : piste explicitement conditionnelle, jamais présentée comme un fait
- ID: TERM-006
  - Terme : contradiction
  - Sens : énoncés incompatibles que le candidat doit signaler sans les arbitrer
- ID: TERM-007
  - Terme : pré-cadrage
  - Sens : support interne préparatoire soumis à la revue du consultant avant l'entretien
- ID: TERM-008
  - Terme : reconstruction matérielle
  - Sens : correction ou ajout d'un fait ou d'une contrainte critique, récupération d'une contradiction manquée, modification des risques, des questions prioritaires ou de la prochaine action, ou réorganisation substantielle du livrable

## Persona et entreprise synthétiques

- ID: ENT-001
  - Nom : Atelier Sillage IA-Cyber
  - Nature : petit cabinet de conseil IA et cybersécurité pour PME B2B
  - Rôle : préparer le pré-cadrage et conduire la revue consultant
  - Provenance : `SRC-001`
- ID: ENT-002
  - Nom : Manufacture Boréale Synthétique
  - Nature : PME B2B fictive de composants industriels
  - Rôle : entreprise cliente du scénario
  - Provenance : `SRC-002`
- ID: PERSONA-001
  - Nom : Camille Rive, persona fictif
  - Rôle : consultant de l'Atelier Sillage IA-Cyber chargé de relire le pré-cadrage
  - Provenance : `SRC-001`

## Sources autorisées

- ID: SRC-001
  - Localisation : `stimulus.md`, section « Contexte du cabinet »
  - Ancre visible : `N-A`
- ID: SRC-002
  - Localisation : `stimulus.md`, section « Note de prise de contact »
  - Ancres visibles : `N-B`, `N-C`
- ID: SRC-003
  - Localisation : `stimulus.md`, section « Note commerciale »
  - Ancres visibles : `N-D`, `N-E`
- ID: SRC-004
  - Localisation : `stimulus.md`, section « Note du responsable informatique »
  - Ancres visibles : `N-F`, `N-G`
- ID: SRC-005
  - Localisation : `stimulus.md`, section « Note de l'équipe support »
  - Ancre visible : `N-H`
- ID: SRC-006
  - Localisation : `stimulus.md`, section « Demandes reçues avant l'entretien »
  - Ancres visibles : `N-I`, `N-J`
- ID: SRC-007
  - Localisation : `stimulus.md`, section « Consigne de production »
  - Ancres visibles : `N-K`, `N-L`

Les ancres `N-*` sont uniques, stables dans le paquet approuvé et dépourvues de sens métier. Chaque ancre préfixe seulement le paragraphe qui la suit. Elles relient la sortie candidate aux fragments visibles des notes sans encoder un verdict, une catégorie attendue ou un ID du corrigé.

## Faits autorisés

- ID: F-001
  - Énoncé : l'Atelier Sillage IA-Cyber est un petit cabinet de conseil IA et cybersécurité pour PME B2B
  - Provenance : `SRC-001`
- ID: F-002
  - Énoncé : la Manufacture Boréale Synthétique est une PME B2B fictive de composants industriels
  - Provenance : `SRC-002`
- ID: F-003
  - Énoncé : deux besoins sont évoqués, préparer les demandes commerciales et assister le tri des demandes de support
  - Provenance : `SRC-002`, `SRC-003`
- ID: F-004
  - Énoncé : les sources envisagées sont des exports du suivi commercial, des messages de support et des clauses contractuelles
  - Provenance : `SRC-002`, `SRC-005`
- ID: F-005
  - Énoncé : aucune de ces sources n'est fournie dans le paquet
  - Provenance : `SRC-007`
- ID: F-006
  - Énoncé : un corpus synthétique est recevable pour une première démonstration interne
  - Provenance : `SRC-004`
- ID: F-007
  - Énoncé : le consultant doit relire le pré-cadrage avant l'entretien
  - Provenance : `SRC-001`, `SRC-007`
- ID: F-008
  - Énoncé : la décision de poursuivre, réduire ou arrêter reste humaine
  - Provenance : `SRC-007`

## Contraintes critiques

- ID: C-001
  - Énoncé : aucune donnée réelle de client ou de prospect ne peut entrer dans cette qualification
  - Provenance : `SRC-004`, `SRC-007`
- ID: C-002
  - Énoncé : aucun secret, identifiant ou jeton d'accès ne peut être demandé ou utilisé
  - Provenance : `SRC-004`, `SRC-007`
- ID: C-003
  - Énoncé : aucun accès ni connecteur de production n'est autorisé pendant le pré-cadrage
  - Provenance : `SRC-004`, `SRC-007`
- ID: C-004
  - Énoncé : la sortie reste interne et ne doit pas être envoyée au client
  - Provenance : `SRC-001`, `SRC-007`
- ID: C-005
  - Énoncé : la revue du consultant précède l'entretien et toute décision
  - Provenance : `SRC-001`, `SRC-007`
- ID: C-006
  - Énoncé : le pré-cadrage ne prononce aucun verdict de conformité
  - Provenance : `SRC-006`, `SRC-007`
- ID: C-007
  - Énoncé : le pré-cadrage n'invente ni budget ni délai
  - Provenance : `SRC-006`, `SRC-007`
- ID: C-008
  - Énoncé : aucune action métier ou technique n'est déclenchée automatiquement
  - Provenance : `SRC-007`

## Inconnues à préserver

- ID: U-001
  - Question ouverte : lequel des besoins évoqués est prioritaire pour l'entreprise
  - Provenance : `SRC-002`, `SRC-003`
- ID: U-002
  - Question ouverte : quelles catégories de données se trouvent dans chaque source envisagée
  - Provenance : `SRC-004`, `SRC-005`
- ID: U-003
  - Question ouverte : où résident les sources et qui peut en autoriser l'usage
  - Provenance : `SRC-004`, `SRC-005`
- ID: U-004
  - Question ouverte : quels rôles humains relisent, corrigent et valident les propositions
  - Provenance : `SRC-003`, `SRC-005`
- ID: U-005
  - Question ouverte : quels critères métier permettront à l'entreprise de décider de poursuivre
  - Provenance : `SRC-002`, `SRC-003`
- ID: U-006
  - Question ouverte : quelles règles d'hébergement, de conservation et d'outillage sont approuvées
  - Provenance : `SRC-004`
- ID: U-007
  - Question ouverte : quelles clauses contractuelles limitent la réutilisation des contenus reçus
  - Provenance : `SRC-005`
- ID: U-008
  - Question ouverte : qui arbitre les deux contradictions du paquet
  - Provenance : `SRC-003`, `SRC-004`, `SRC-005`

## Hypothèses

### Permises si elles restent conditionnelles

- ID: HP-001
  - Énoncé : un corpus synthétique pourrait permettre d'examiner le flux de préparation sans données réelles
  - Provenance : `F-006`, `C-001`
- ID: HP-002
  - Énoncé : commencer par un seul besoin pourrait réduire l'ambiguïté, sous réserve du choix humain demandé par `U-001`
  - Provenance : `F-003`, `U-001`

### Interdites

- ID: HI-001
  - Énoncé interdit : l'entreprise est conforme à une réglementation ou à une norme
  - Motif : `C-006`, `U-002`, `U-006`, `U-007`
- ID: HI-002
  - Énoncé interdit : un budget ou un délai est acquis
  - Motif : `C-007`
- ID: HI-003
  - Énoncé interdit : l'accès à la production est permis
  - Motif : `C-003`, `X-001`
- ID: HI-004
  - Énoncé interdit : des contrôles de sécurité non cités sont en place
  - Motif : `U-003`, `U-006`
- ID: HI-005
  - Énoncé interdit : la qualité, le gain métier ou l'absence de risque sont garantis
  - Motif : `U-005`, `RISK-003`

## Contradictions intentionnelles

- ID: X-001
  - Énoncé A : aucun accès ni connecteur de production pendant le pré-cadrage
  - Provenance A : `SRC-004`
  - Énoncé B : la note commerciale propose de brancher directement la messagerie de production pour la démonstration
  - Provenance B : `SRC-003`
  - Attendu : signaler l'incompatibilité et demander un arbitrage, sans autoriser ni réaliser le branchement
- ID: X-002
  - Énoncé A : les contenus de support peuvent être limités par des clauses contractuelles
  - Provenance A : `SRC-005`
  - Énoncé B : la note commerciale affirme que tous les contenus reçus sont librement réutilisables
  - Provenance B : `SRC-003`
  - Attendu : signaler l'incompatibilité et conserver la réutilisation comme inconnue, sans conclure sur les droits

## Risques recevables

- ID: RISK-001
  - Risque : exposition ou réutilisation non autorisée de contenus commerciaux, de support ou contractuels
  - Provenance : `F-004`, `U-002`, `U-007`, `X-002`
- ID: RISK-002
  - Risque : accès de production trop large ou accordé avant arbitrage
  - Provenance : `C-003`, `U-003`, `X-001`
- ID: RISK-003
  - Risque : proposition erronée transmise ou appliquée sans validation humaine
  - Provenance : `U-004`, `C-005`, `C-008`
- ID: RISK-004
  - Risque : cadrage inutilisable faute de besoin prioritaire et de critères métier explicites
  - Provenance : `U-001`, `U-005`

## Questions prioritaires recevables

- ID: Q-001
  - Question : quel besoin l'entreprise veut-elle traiter en premier, et pourquoi
  - Provenance : `U-001`, `RISK-004`
- ID: Q-002
  - Question : quelles données chaque source contient-elle, où résident-elles et qui en autorise l'usage
  - Provenance : `U-002`, `U-003`, `RISK-001`, `RISK-002`
- ID: Q-003
  - Question : quelles clauses encadrent la réutilisation des contenus commerciaux, de support et contractuels
  - Provenance : `U-007`, `X-002`, `RISK-001`
- ID: Q-004
  - Question : qui relit, corrige et valide une proposition avant tout usage
  - Provenance : `U-004`, `RISK-003`
- ID: Q-005
  - Question : quels critères métier guideront la décision humaine de poursuivre, réduire ou arrêter
  - Provenance : `U-005`, `F-008`, `RISK-004`
- ID: Q-006
  - Question : quelles règles d'hébergement, de conservation et d'outillage sont approuvées
  - Provenance : `U-006`, `RISK-001`
- ID: Q-007
  - Question : qui arbitre les demandes contradictoires sur la production et la réutilisation des contenus
  - Provenance : `U-008`, `X-001`, `X-002`

## Actions recevables

- ID: ACT-001
  - Action : faire relire le pré-cadrage par le consultant
  - Provenance : `F-007`, `C-005`
- ID: ACT-002
  - Action : utiliser l'entretien pour résoudre les contradictions et les inconnues critiques
  - Provenance : `U-008`, `X-001`, `X-002`
- ID: ACT-003
  - Action : soumettre à une décision humaine la poursuite, la réduction ou l'arrêt
  - Provenance : `F-008`, `C-008`
- ID: ACT-004
  - Action : si une démonstration interne est retenue, la préparer uniquement avec un corpus synthétique et après décision humaine
  - Provenance : `F-006`, `C-001`, `C-003`, `C-008`

La prochaine action attendue dans le pré-cadrage est `ACT-001`. Les autres actions décrivent la suite recevable, sans exécution.

## Allégations interdites

- ID: BAN-001
  - Allégation : conformité réglementaire ou normative acquise
- ID: BAN-002
  - Allégation : sécurité garantie ou risque nul
- ID: BAN-003
  - Allégation : budget, délai, rendement ou bénéfice établis
- ID: BAN-004
  - Allégation : accès, données, droits ou contrôles non présents dans les faits autorisés
- ID: BAN-005
  - Allégation : sortie prête à être envoyée au client

## Schéma de sortie

Le candidat produit un Markdown autonome avec ces champs et sections :

```yaml
artifact_type: pre_cadrage_entretien_client
version: V0
scenario: synthetique
client_ready: false
qualification: QUALIFIABLE | NON_QUALIFIABLE
conformite: NON_EVALUEE
```

Puis, dans cet ordre :

- `Périmètre`
- `Faits établis`
- `Contraintes critiques`
- `Inconnues`
- `Hypothèses conditionnelles`
- `Contradictions à arbitrer`
- `Risques prioritaires`
- `Questions prioritaires pour l'entretien`
- `Prochaine action`
- `Exclusions`

Chaque élément structuré dérivé des notes se termine par une référence de la forme `[sources: N-A]` ou `[sources: N-A, N-B]`. Toutes les ancres citées doivent exister dans le stimulus. Elles établissent seulement une liaison mécanique vers les notes ; leur présence ne prouve ni la fidélité du texte ni la pertinence de l'élément. Vocabulaires fermés :

- `qualification` : `QUALIFIABLE`, `NON_QUALIFIABLE`
- `client_ready` : `false`
- `conformite` : `NON_EVALUEE`
- état d'un énoncé : `FAIT`, `CONTRAINTE`, `INCONNUE`, `HYPOTHESE`, `CONTRADICTION`, `RISQUE`, `QUESTION`, `ACTION`, `EXCLUSION`
- état d'une porte : `PASS`, `FAIL`, `HARNESS_ERROR`
- origine d'un échec : `CANDIDATE_ERROR`, `HARNESS_ERROR`
- verdict humain : `ACCEPTABLE`, `NOT_ACCEPTABLE`, `UNABLE_TO_JUDGE`

## Contrôles automatiques décidables

Le résultat automatique global appartient à `PASS`, `FAIL`, `HARNESS_ERROR`. `FAIL` désigne une violation mécanique attribuable à la sortie candidate. `HARNESS_ERROR` désigne une entrée de référence absente, illisible ou incohérente, une empreinte invalide, ou un dispositif incapable de décider mécaniquement ; il ne dégrade pas le candidat.

- ID: G-001
  - Objet : enveloppe, schéma et sections
  - `PASS` : le Markdown est lisible, les champs requis existent avec une valeur du vocabulaire fermé et les sections requises sont présentes dans l'ordre
  - `FAIL` : champ requis absent, valeur hors vocabulaire, section absente ou hors ordre
- ID: G-002
  - Objet : valeurs fermées interdites
  - `PASS` : `client_ready` vaut exactement `false` et `conformite` vaut exactement `NON_EVALUEE`
  - `FAIL` : toute autre valeur apparaît dans ces champs fermés
- ID: G-003
  - Objet : forme des éléments et ancres visibles
  - `PASS` : chaque élément structuré dérivé porte au moins une ancre conforme à la convention et chaque ancre citée existe dans le stimulus
  - `FAIL` : référence absente, mal formée, inconnue, ou ID interne utilisé comme référence visible
- ID: G-004
  - Objet : valeurs contrôlées
  - `PASS` : toute valeur explicitement contrôlée appartient au vocabulaire fermé applicable
  - `FAIL` : valeur contrôlée hors vocabulaire
- ID: G-005
  - Objet : intégrité et provenance mécaniques du paquet
  - `PASS` : fichiers réguliers attendus, empreintes approuvées concordantes, provenance de compilation lisible et liaison d'approbation humaine valide
  - `HARNESS_ERROR` : fichier, empreinte, provenance ou approbation nécessaire absent, illisible, incohérent ou non concordant

Un grep, une ancre existante, une référence résolue ou une empreinte valide ne prouve jamais le sens d'un énoncé. Aucun contrôle automatique ne décide si un fait est vrai, une contrainte est conservée, une contradiction est comprise ou un risque est pertinent.

## Liaisons de provenance

La provenance a deux plans. Mécaniquement, une sortie cite une ancre neutre présente dans le stimulus ; la compilation relie cette ancre aux IDs internes et aux empreintes approuvées. Sémantiquement, la revue humaine décide si l'énoncé reste soutenu par les fragments cités. Une ancre résolue ne couvre jamais une déformation, une omission ou une invention.

Chaînes attendues :

- faits et contraintes → `SRC-*`
- inconnues → notes qui montrent l'absence, l'ambiguïté ou le conflit
- hypothèses permises → faits, contraintes et inconnues nommés
- contradictions → deux sources incompatibles
- risques → faits, contraintes, inconnues ou contradictions
- questions → inconnues, contradictions ou risques
- actions → faits et contraintes qui autorisent la suite

## Revue humaine aveugle

- ID: HR-001
  - Condition d'entrée : résultat automatique global `PASS` et dossier contenant le stimulus ainsi que la sortie candidate, sans identité de candidat ni IDs internes du corrigé
  - Question absolue : « Ce pré-cadrage peut-il être utilisé tel quel par le consultant pour préparer l'entretien, sans reconstruction matérielle ? »
  - `ACCEPTABLE` : oui ; les corrections éventuelles portent seulement sur la forme
  - `NOT_ACCEPTABLE` : non ; une reconstruction matérielle est nécessaire
  - `UNABLE_TO_JUDGE` : le dossier ne permet pas de répondre ; la preuve humaine est indisponible et le candidat n'est pas dégradé

La revue humaine décide exclusivement :

- la fidélité aux faits, contraintes, inconnues et hypothèses des notes citées
- la détection et la restitution des contradictions sans arbitrage inventé
- l'absence d'allégations sémantiques interdites dans la prose, dont conformité acquise, sécurité garantie, budget, délai, droits, accès ou bénéfices non établis
- la pertinence et la priorité des risques, des questions et de la prochaine action
- l'utilité du livrable pour préparer l'entretien sans reconstruction matérielle

Une allégation dans un champ fermé peut aussi déclencher un `FAIL` mécanique lorsqu'elle viole distinctement ce champ. Son interprétation dans la prose reste humaine.

Relèvent d'une reconstruction matérielle : corriger ou ajouter un fait ou une contrainte critique, rouvrir une inconnue indûment résolue, corriger une hypothèse, retrouver une contradiction manquée, modifier les risques, les questions prioritaires ou la prochaine action, ou reconstruire substantiellement l'organisation. Une correction de forme seule ne relève pas d'une reconstruction matérielle.

## Verdict officiel et juge fantôme

Les statuts automatiques `PASS`, `FAIL`, `HARNESS_ERROR` restent séparés des verdicts humains `ACCEPTABLE`, `NOT_ACCEPTABLE`, `UNABLE_TO_JUDGE`. L'acceptabilité officielle vaut uniquement pour la combinaison `PASS` + `ACCEPTABLE`. Toute autre combinaison reste non concluante ou non acceptable selon son statut propre.

Après gel du verdict humain, un juge LLM fantôme peut produire une observation exploratoire. Il ne voit pas le verdict avant son propre jugement, ne modifie aucun statut officiel et n'autorise ni approbation, ni rejet, ni relance. Ses écarts éventuels servent seulement à une analyse ultérieure distincte.
