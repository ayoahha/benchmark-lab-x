---
title: "Graph Engineering et Loop Engineering pour les boucles agentiques"
date: 2026-08-30
updated: 2026-08-31
status: ready_for_llm_wiki
visibility: public
style_gate: pass
retrieval_terms:
  - graph engineering
  - loop engineering
  - boucle agentique
  - graphe d'exécution agentique
  - goal
  - AOV
---

# Graph Engineering et Loop Engineering pour les boucles agentiques

## Réponse canonique

Le **Loop Engineering** conçoit une boucle agentique qui peut progresser longtemps sans tourner à vide : objectif vérifiable, état durable, évaluateur, gestion du contexte, erreurs récupérables, limites de coût et condition d’arrêt.

Le **Graph Engineering** conçoit, contraint, instrumente et vérifie la structure d’exécution qui relie plusieurs travaux agentiques : nœuds, dépendances, transitions, bifurcations, jointures, évaluateurs et reprises.

Une boucle peut vivre dans un nœud ou piloter plusieurs nœuds. Elle ne suffit pas à former un graphe d’exécution. Une hiérarchie de tâches ou de sous-agents ne suffit pas non plus : un graphe déclare les dépendances réelles, les conditions de déclenchement et les jointures.

Dans ce vocabulaire, Initiative, Epic et Story forment une **structure de livraison**. Le mot « graphe » reste réservé à l’exécution agentique.

## Principe KISS global

`[DÉCISION D’AYO]` KISS s’applique à tous les projets, produits, outils, architectures, méthodes, workflows, règles d’exécution et documents, y compris la gestion d’erreurs.

Ordre de décision :

1. Partir du besoin observé et de sa preuve de réussite.
2. Réutiliser ce qui existe dans le projet ou dans le runtime natif.
3. Choisir le plus petit changement direct qui couvre le besoin.
4. Garder un contrôle exécutable proportionné au risque.
5. Ajouter une couche seulement après une limite constatée pendant un essai.

Une abstraction prévue pour un besoin hypothétique reste hors périmètre. Une gate humaine existe seulement quand une autorité, un effet sensible ou une ambiguïté l’exige. La documentation conserve une source canonique par sujet et un rapport de preuves par pilote ; une note intermédiaire est absorbée ou supprimée après consolidation.

## Niveau de preuve

- `[TEXTE INTÉGRAL]` : papier, documentation active, transcription complète ou artefact lu intégralement.
- `[TITRE/RÉSUMÉ]` : repérage sans lecture complète.
- `[OBSERVATION LOCALE]` : version ou comportement constaté dans l’environnement le 30 août 2026.
- `[DÉDUCTION]` : conclusion tirée des sources et des observations.
- `[HYPOTHÈSE NON VÉRIFIÉE]` : proposition qui demande encore un essai.
- `[DÉCISION D’AYO]` : périmètre ou choix donné directement par Ayo.

## Origine et statut des termes

`[TEXTE INTÉGRAL]` Addy Osmani a publié en juin 2026 une définition praticienne explicite du [Loop Engineering](https://addyo.substack.com/p/loop-engineering). Il place la boucle au-dessus du *harness* d’une exécution unique et insiste sur le déclenchement, la vérification, l’état extérieur à la conversation et les limites de coût.

`[TEXTE INTÉGRAL]` La prépublication [Loop Engineering: Building Blocks, Adoption, and Impact](https://arxiv.org/abs/2608.21884) formalise ensuite une définition de travail. Son échantillon initial comptait 36 710 dépôts ; 36 645 ont réellement été scannés après 65 disparitions. Elle confirme 217 boucles, soit 0,59 % des dépôts scannés. Elle ne démontre aucun gain causal de qualité, de coût ou de productivité. La version 2 du 26 août 2026 est annoncée *under review*.

`[DÉDUCTION]` Le terme est donc formalisé, mais la discipline scientifique n’est pas stabilisée. Les mécanismes qu’il regroupe, comme les schedulers, boucles de contrôle, systèmes événementiels et agents itératifs, lui préexistent.

`[TEXTE INTÉGRAL]` Le même papier mentionne le Graph Engineering comme prolongement prospectif : les agents sont des nœuds ; le travail, l’état et les décisions de routage circulent le long des arêtes. Cette mention ne constitue ni une méthode validée ni une preuve de bénéfice. La définition opérationnelle ci-dessus est une déduction testée localement.

## Glossaire

**AOV, Activity-on-Vertex**
Représentation en graphe orienté acyclique où chaque sommet porte une activité et chaque arête une relation de précédence. Une arête `i -> j` signifie que `i` doit finir avant que `j` commence. [Flow](https://arxiv.org/abs/2501.07834) applique AOV aux sous-tâches agentiques. AOV décrit les travaux dépendants, pas la reprise durable ni le moteur complet.

**Évaluateur**
Contrôle qui décide si la sortie d’un nœud satisfait son contrat de réussite. Il doit lire une preuve observable, pas seulement la déclaration du producteur.

**Guardrail**
Validation automatique d’une entrée, d’une sortie ou d’un appel d’outil. Il peut renvoyer une erreur exploitable et laisser la boucle corriger.

**Gate humain**
Pause réservée à une autorité manquante, un effet externe sensible ou une ambiguïté impossible à trancher automatiquement sans risque.

**Jointure**
Nœud qui attend et vérifie l’ensemble exact des prédécesseurs sélectionnés avant de continuer.

**Reçu durable**
État fermé d’un nœud : identité, empreintes des entrées, statut, tentative, propriétaire d’écriture, sortie ou erreur, preuve d’évaluation et prochaine action autorisée.

**Fausse fin**
Conclusion verte alors qu’un nœud requis manque, qu’une branche incorrecte a été exécutée, qu’un effet reste ambigu ou que la provenance est incohérente.

## Primitives natives actuelles

### Codex `/goal`

`[TEXTE INTÉGRAL]` La documentation active [Follow a goal](https://learn.chatgpt.com/use-cases/follow-goals) décrit un objectif durable attaché à la tâche, utilisable pendant plusieurs heures. Il possède une condition de fin, un journal de progression et des commandes de consultation, édition, pause, reprise et effacement. Le goal ne change ni les permissions ni le sandbox.

`[OBSERVATION LOCALE]` Codex CLI `0.151.0` expose `goals`, `hooks` et `multi_agent` comme fonctions stables.

`[DÉDUCTION]` `/goal` est une primitive native de Loop Engineering. Il ne déclare ni dépendances par nœud, ni bifurcations, ni jointures, ni propriétaire d’écriture, ni reprise exacte d’un effet externe. Sa condition terminale ne remplace pas un vérificateur qui lit l’état durable.

### Claude Code `/goal` et `/loop`

`[TEXTE INTÉGRAL]` [Claude Code `/goal`](https://code.claude.com/docs/en/goal) relance un tour tant qu’un petit modèle évaluateur renvoie « not yet met ». L’évaluateur distinct ne voit que le transcript et n’utilise aucun outil. La reprise restaure la condition, mais remet à zéro le compteur de tours, le chronomètre et la base de coût. Les erreurs transitoires conservent le goal ; certaines erreurs d’authentification, de crédit, de contexte ou de modèle l’effacent.

`[TEXTE INTÉGRAL]` [Claude Code `/loop`](https://code.claude.com/docs/en/scheduled-tasks) relance un prompt selon le temps. La session doit rester ouverte, les tâches expirent après sept jours, les déclenchements manqués ne sont pas rattrapés et les processus de fond ne sont pas restaurés.

`[DÉDUCTION]` `/goal` poursuit une condition. `/loop` fournit une cadence. Ni l’un ni l’autre ne constitue un graphe d’exécution.

## Contrat minimal d’un nœud

| Champ | Contenu minimal |
|---|---|
| Identité | Exécution, nœud, tentative, base ou version |
| Entrée | Références immuables vers les sorties parentes admises |
| Sortie | Objet durable et empreinte |
| État | `pending`, `running`, `waiting`, `evaluated`, `failed`, `abstained` ou `ambiguous` |
| Déclenchement | Prédécesseurs et condition sélectionnée |
| Écriture | Propriétaire unique et chemins autorisés |
| Réussite | Critère automatique décidable |
| Évaluateur | Contrat, version, verdict et preuve |
| Transition | Dépendances consommées et route choisie |
| Reprise | Dernier reçu fermé et premier nœud incomplet |
| Provenance | Sources et chaîne d’empreintes |
| Mesures | Temps, coût observable et intervention humaine |

`evaluated` signifie que la réussite a été admise par l’évaluateur. La jointure compare l’ensemble exact des prédécesseurs sélectionnés. Un nœud absent, supplémentaire, non évalué ou ambigu garde le terminal rouge. L’état `ambiguous` interdit le rejeu automatique.

## Mise en œuvre minimale

Le pilote Benchmark Lab‑X V1 corrigé utilise un graphe codé en dur, Python standard, un reçu JSON immuable par nœud et un vérificateur terminal séparé. Chaque évaluateur s’exécute avant la fermeture de son reçu. La publication exclusive passe par un temporaire synchronisé, puis le répertoire est synchronisé. Aucun moteur générique n’est nécessaire.

Le V2 agentique réutilise ce harnais dans un worktree distinct. La route A vérifie la source courante sans modèle. La route B injecte un défaut d’une ligne dans une copie isolée, laisse Codex produire le correctif, puis exécute un oracle de trois assertions. Chaque tentative évaluée est écrite une seule fois dans `nodes/B/attempts/`. Une reprise conserve ce journal et les reçus fermés, reconstruit seulement le workspace non fermé, puis aligne le reçu B terminal sur le nombre exact de tentatives.

Un DSL, une interface visuelle, une base de données, un moteur distribué, le multi-écrivain ou une nouvelle plateforme restent hors périmètre tant qu’un essai ne démontre pas leur nécessité.

## Gestion d’erreurs

Les erreurs sont normales dans une boucle longue. Le but n’est pas de tout bloquer, mais de savoir quelle reprise reste sûre.

| Classe | Action par défaut | Intervention humaine |
|---|---|---|
| Service indisponible, rate limit, réseau | `waiting`, reprise bornée avec délai croissant | Budget ou délai global épuisé |
| Sortie invalide, test rouge, preuve absente | Retour au même nœud avec le diagnostic | Absence de progrès après la limite prévue |
| Dépendance encore active | `waiting`, aucun échec terminal | Dépendance définitivement impossible |
| Conflit d’écriture | Abandonner la tentative, relire l’état, reprendre si l’opération est sûre | Propriété ou valeur courante impossible à établir |
| Timeout après effet externe | `ambiguous`, aucun rejeu aveugle | Tant qu’un reçu fiable ne tranche pas |
| Authentification, autorité, budget ou contexte irrécupérable | `failed` ou `abstained` | Quand une nouvelle décision est nécessaire |

Une reprise relit le dernier reçu fermé et commence au premier nœud incomplet. Elle ne déduit pas la prochaine action du seul transcript.

## Guardrails sans accumulation de gates

`[TEXTE INTÉGRAL]` La documentation OpenAI sur les [guardrails et la revue humaine](https://developers.openai.com/api/docs/guides/agents/guardrails-approvals) distingue la validation automatique d’une pause avant action sensible et recommande de placer le contrôle près de l’effet concerné.

Politique retenue :

1. Un guardrail déterministe renvoie une erreur que le nœud peut corriger.
2. L’évaluateur vérifie la postcondition du nœud.
3. Une panne transitoire utilise une reprise bornée et un délai croissant.
4. Une gate humaine existe seulement pour une autorité manquante, un effet sensible, une ambiguïté persistante ou un budget épuisé.

Un test rouge, une sortie invalide ou un rate limit ordinaire ne justifie pas un HOLD global.

## Boucles de plusieurs heures ou de plus de 24 heures

Oui, elles sont techniquement plausibles. Codex documente des goals de plusieurs heures. Claude restaure un goal actif et conserve certaines erreurs transitoires. Ces garanties restent inférieures à une reprise exacte de chaque opération.

Une boucle de plus de 24 heures doit être une suite d’unités courtes et reprenables :

- état durable après chaque transition importante ;
- nœud idempotent ou clé d’idempotence pour un effet externe ;
- distinction entre `waiting`, `failed` et `ambiguous` ;
- délai et limite de reprise ;
- coût et durée cumulés observables ;
- terminal calculé depuis les reçus ;
- intervention humaine seulement sur ambiguïté, effet sensible ou nouvelle autorité.

`[HYPOTHÈSE NON VÉRIFIÉE]` Un essai réel de plus de 24 heures doit encore vérifier la veille du Mac, l’expiration de session, les quotas, les mises à jour du client et un redémarrage de l’hôte. Une conversation maintenue ouverte pendant 24 heures n’est pas une preuve de reprise.

## Décisions d’outillage pour Ayo

- `[DÉCISION D’AYO]` Paperclip courant se trouve sur `perso-hermes`. Son ancien dépôt local n’appartient pas au périmètre du MacBook et ne doit pas être utilisé pour ce travail.
- `[DÉDUCTION]` Herdr n’est pas nécessaire. Le pilote a démontré son contrat minimal avec les primitives natives, Git, des reçus et un vérificateur. Herdr ne devra être réévalué que si une défaillance observée exige sa capacité propre.
- `[DÉDUCTION]` Aucun nouveau moteur de workflow n’est justifié. Utiliser d’abord `/goal`, les sous-agents, les worktrees, les hooks d’observabilité et l’état durable déjà disponibles.

## Ce que la vidéo fournie apporte réellement

`[TEXTE INTÉGRAL]` La vidéo [« J’ai automatisé mon travail avec ChatGPT »](https://www.youtube.com/watch?v=J9J-EHePEP0), IA Talkshow, 28 août 2026, décrit l’état durable, les checkpoints, les postconditions, les erreurs et l’intervention humaine. Elle ne montre ni code, ni journal brut, ni coût, ni test de reprise. Elle reste un retour terrain commercial.

`[TEXTE INTÉGRAL]` Une [vidéo connexe](https://www.youtube.com/watch?v=1-A_vU9Wheo) reconnaît le biais d’auto-évaluation et recommande un second évaluateur. L’affirmation d’une exécution de 17 heures n’est accompagnée d’aucune trace reproductible.

Conserver : état durable, postconditions, terminal borné, erreurs classées et intervention sur ambiguïté. Rejeter comme règles : nombre universel de tentatives, seuil universel de lignes, suppression automatique et promesse de fiabilité multi-agent sans mesure.

## Preuve locale Benchmark Lab-X

`[TEXTE INTÉGRAL]` Le premier pilote local corrigé a utilisé cinq nœuds déclarés, une bifurcation, une jointure, un évaluateur exécuté avant fermeture pour chaque nœud et un vérificateur terminal extérieur. Deux campagnes neuves ont chacune produit :

- 13 critères sur 13 ;
- 16 décisions terminales correctes sur 16 ;
- 13 fausses fins refusées sur 13, avec zéro fausse réussite ;
- une reprise contrôlée sur `B`, sans rejeu ni modification des reçus `D/S` fermés ;
- aucun reçu final pour une sortie `J` fausse mais sérialisable ;
- zéro appel modèle ou fournisseur et zéro coût externe pendant le run ;
- zéro conflit, avec un seul propriétaire logique et aucun test multi-écrivain.

La preuve reste locale et déterministe. Elle couvre une interruption contrôlée pendant la fermeture de `B`, sans arrêt brutal du processus ni panne électrique. Elle ne démontre ni exécution exactement une fois, ni effet externe, ni transfert à tous les projets.

`[OBSERVATION LOCALE]` Le V2 a ensuite exécuté deux sessions Codex réellement observées sous `gpt-5.6-sol`. Les deux correctifs ont satisfait les trois assertions, sans être identiques octet pour octet. La première tentative a été interrompue avant publication du reçu B ; le terminal est resté en `HOLD`. Après reprise, les octets et dates de D/S sont restés inchangés et B a été le premier nœud repris.

`[OBSERVATION LOCALE]` Grok Build a sélectionné explicitement `grok-4.6` ; la trace de revue rapporte `grok-4.6-build`. Son verdict initial `CORRIGER_V2` a identifié une perte de provenance : le reçu terminal ne comptait que la seconde tentative. Une seule passe corrective a ajouté le journal immuable des tentatives, aligné `attempt` et `candidate_calls`, puis fait refuser au terminal tout journal absent, discontinu ou non aligné. Six tests V1 et V2 passent. Une campagne de correction fraîche rend A `PASS`, B interrompu `HOLD`, puis B repris `PASS` avec deux tentatives durables.

`[DÉDUCTION]` Ce résultat autorise à proposer un pilote long dans Benchmark Lab‑X. Il ne prouve ni une durée de plusieurs heures, ni une panne réelle, ni un coût monétaire Codex, ni la sûreté multi-écrivain. Il n’autorise aucune généralisation globale.

## Seuil de complexification

Ajouter un composant seulement lorsqu’un essai produit un problème que les primitives natives et les reçus ne peuvent pas résoudre : perte d’état, double effet, conflit d’écriture, absence de reprise ou observabilité insuffisante.

`[DÉDUCTION]` Le prochain essai proposé est une boucle longue bornée dans Benchmark Lab‑X, sous autorité distincte d’Ayo. Aucune mutation globale ne découle automatiquement de cette page.

## Sources principales

- [AGORA, arXiv:2505.24354](https://arxiv.org/abs/2505.24354)
- [Loop Engineering: Building Blocks, Adoption, and Impact, arXiv:2608.21884v2](https://arxiv.org/abs/2608.21884)
- [Flow, arXiv:2501.07834](https://arxiv.org/abs/2501.07834)
- [OpenAI, Follow a goal](https://learn.chatgpt.com/use-cases/follow-goals)
- [Anthropic, Claude Code goals](https://code.claude.com/docs/en/goal)
- [Anthropic, scheduled tasks](https://code.claude.com/docs/en/scheduled-tasks)
- [OpenAI, Guardrails and human review](https://developers.openai.com/api/docs/guides/agents/guardrails-approvals)
