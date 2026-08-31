---
style_gate: pass
---

# Dossier de refondation produit, 29 août 2026

Harmonisation des décisions propriétaires : 30 août 2026. Correction documentaire ciblée de seconde passe : 30 août 2026.

Base relue : `81c217e0a585e89c0151090d6cef9581b8a2c741`

La spécification active est désormais portée par `docs/specification/PRD.md`, `docs/specification/ARD.md` et `docs/specification/RULES.md`. Les chemins `docs/PRD.md`, `docs/ARD.md` et `docs/RULES.md` sont des sources historiques gelées, restaurées byte-identiquement à la base relue pour les générateurs, tests et rejeux V0, V1 et U025. Aucun document actif ne les utilise comme spécification normative.

Les journaux, inventaires, états et bilans historiques portent le statut `FAIT ÉTABLI`. Chaque ligne de cartographie porte son statut propre. Une `DÉCISION PROPRIÉTAIRE` vient d'Ayo ; une `DÉDUCTION RAISONNÉE` nomme ses prémisses ; une `HYPOTHÈSE NON VÉRIFIÉE` nomme la preuve attendue.

## 1. Objet, preuve et arrêt

Ce dossier relie les sources locales et GitHub aux affirmations proposées dans le README, la spécification active, le glossaire et le gabarit de carte.

Il sert au checkpoint documentaire et à sa correction ciblée de seconde passe. Il ne décide pas du nom de la prochaine version, ne lance pas de campagne et ne prépare pas le découpage agile.

La preuve attendue est une chaîne lisible : source, mode de lecture, affirmation, statut, conflit, décision documentaire et document cible. La présence d'un texte ou d'un test vert ne vaut jamais preuve de satisfaction d'une tâche.

## 2. Méthode de lecture

Les petits contrats et documents d’autorité ont été lus intégralement. Pour les familles volumineuses, l’inventaire a été compté, puis les contrats, reçus de fermeture, registres, matrices, rapports, tests et sections de code réutilisés ont été lus de manière ciblée. Les blobs adressés par contenu de `preuves-u025` n’ont pas tous fait l’objet d’une lecture sémantique individuelle.

Les sources GitHub ont été consultées en lecture seule. L’état du Project et des PR est un instantané de suivi au 29 août 2026, pas une preuve produit.

### Racines reproductibles

| Famille | Racine |
|---|---|
| Dépôt et corpus local | `/Users/ayo/Projects/benchmark-lab-x` au commit `81c217e0a585e89c0151090d6cef9581b8a2c741` |
| Dossier préparatoire privé | `/Users/ayo/Library/Application Support/Benchmark Lab-X/private/handoffs/2026-08-29-product-reset/` |
| Oracle principal | `/Users/ayo/.oracle/sessions/handoff-consult-f035e886/artifacts/transcript.md` |
| Oracle de suivi | `/Users/ayo/.oracle/sessions/ayo-veut-repartir-dans-une/artifacts/transcript.md` |
| Contrat d'harmonisation propriétaire | `/Users/ayo/Library/Application Support/Benchmark Lab-X/private/orchestration/2026-08-30-owner-harmonization/contract.md`, SHA-256 `147bba750436459da164876d91c25f194c9e6681e18b9fc452193fdc7fdcc64d` |
| Oracle d'harmonisation | `/Users/ayo/.oracle/sessions/handoff-consult-75f6076b/artifacts/transcript.md` |
| Contrat de correction de seconde passe | `/Users/ayo/Library/Application Support/Benchmark Lab-X/private/orchestration/2026-08-30-fable-oracle-second-pass/documentary-correction-contract.md`, SHA-256 attendu `979c9a619ad9e281b4ed779499a660fb37e73be105bebb8277bcd85292dc664a`, non recalculé dans la passe d'écriture |
| Contrat de compatibilité CI documentaire | `/Users/ayo/Library/Application Support/Benchmark Lab-X/private/orchestration/2026-08-30-ci-documentary-compatibility/contract.md`, SHA-256 `16018ae4c95256827ed17bd614e22b893a7eee8c27654619dfe64f2451754544` |
| Réglages Pi | `/Users/ayo/.pi/agent/settings.json`, lignes `1-16` |
| Audit externe | `/Users/ayo/.codex/attachments/7fb868fa-1060-4a02-a2db-a48835439438/pasted-text.txt` |
| Lot 5576 préservé | `/Users/ayo/.codex/worktrees/5576/benchmark-lab-x` |
| Dépôt GitHub | `https://github.com/ayoahha/benchmark-lab-x` |
| Project personnel #5 | `https://github.com/users/ayoahha/projects/5` |

Une Issue `N` est reproductible à `https://github.com/ayoahha/benchmark-lab-x/issues/N`; une PR `N` à `https://github.com/ayoahha/benchmark-lab-x/pull/N`. Les commentaires d’autorité cités dans les artefacts locaux conservent leur URL complète et leur empreinte.

## 3. Journal de couverture

| Source ID | Chemin ou URL | Mode de lecture | Affirmation couverte | Statut | Conflit | Décision documentaire | Cible |
|---|---|---|---|---|---|---|---|
| S01 | `AGENTS.md` | intégrale | autorité, preuve, mutation étroite, arrêt | FAIT ÉTABLI | aucun | respecter le checkout writer et l’absence d’exécution | tous |
| S02 | `docs/agents/issue-tracker.md` | intégrale | Issues pour tâches et preuves, Project `Status` pour l’état | FAIT ÉTABLI | corps #95 divergent des relations natives | séparer suivi et vérité produit | README, RULES |
| S03 | `README.md` à la base | intégrale | formulation coût-first et audience interne héritées | FAIT ÉTABLI | besoin originel communautaire et absence de trajectoire publique | remplacer par l'accès initial Lab X puis la vocation publique, conserver l'histoire | README, PRD |
| S04 | `.github/workflows/ci.yml`, `.github/workflows/pages.yml`, `pages/index.html` | intégrale | CI et Pages ne prouvent pas une campagne | FAIT ÉTABLI | `main` sert un placeholder; PR #151 est ouverte | rendre la limite visible | README, dossier |
| S05 | `docs/PRD.md`, `docs/ARD.md`, `docs/RULES.md` à la base | intégrale | contrat V0 coût/acceptabilité, provenance et abstention | FAIT ÉTABLI | qualité réduite à acceptabilité et Pareto | refondre sans réécrire V0 | PRD, ARD, RULES |
| S06 | `tasks/TEMPLATE.md` à la base | intégrale | run design, axes, audit et conclusion située déjà présents | FAIT ÉTABLI | statut unique et analyse finale réduite à trois axes | garder les bons contrats, séparer qualité et profils | TEMPLATE |
| S07 | `docs/VERIFY-V7.md` | intégrale | contrat spécialisé de mesure et qualification | FAIT ÉTABLI | ne gouverne pas la nouvelle proposition | archiver comme actif spécialisé | ARD, dossier |
| S08 | `docs/PREUVE-ATTEIGNABILITE-FLOAT64.md` | intégrale | preuve numérique du prototype historique | FAIT ÉTABLI | aucune portée sur le recadrage produit | archiver sans migration | ARD, dossier |
| S09 | `tasks/dev/pre-cadrage-entretien-client/manifeste-paquet.json` | intégrale | identité du paquet approuvé | FAIT ÉTABLI | paquet conçu hors benchmark | conserver comme source historique | dossier |
| S10 | `tasks/dev/pre-cadrage-entretien-client/brief-proprietaire.md` | intégrale | périmètre documentaire du pré-cadrage | FAIT ÉTABLI | exclut performance et classement | exiger une nouvelle version de carte qualité-first | PRD, RULES |
| S11 | `tasks/dev/pre-cadrage-entretien-client/registre-verite.md` | intégrale | vérité métier, inconnues et exclusions | FAIT ÉTABLI | exclut mesure de performance, classement et recommandation | ne pas requalifier le paquet | PRD, RULES |
| S12 | `tasks/dev/pre-cadrage-entretien-client/stimulus.md` | intégrale | exemple de sortie visible avec bloc `yaml` | FAIT ÉTABLI | `G-001` exige `---` en première ligne | cartographier le conflit, aucune conclusion qualitative | README, dossier |
| S13 | `tasks/dev/pre-cadrage-entretien-client/temoins-qualification.md` | intégrale | seize témoins de contrôles et jugement | FAIT ÉTABLI | témoins ne sont pas des sorties candidat | borner les PASS de qualification | RULES, dossier |
| S14 | `docs/archive/legacy-benchmark-v0-2026-08-14/` | inventaire et documents par fichiers | dix fichiers; manifeste SHA-256 validé sur neuf entrées | FAIT ÉTABLI | base de l’archive 5576 différente de la base courante | préserver, ne pas prendre comme autorité courante | dossier |
| S15 | `tasks/archives/` | inventaire et lecture des 24 fichiers | cartes retirées, ancrages et rubriques historiques | FAIT ÉTABLI | rubriques utiles mais non qualifiées pour la future carte | réutiliser les concepts, pas les verdicts | ARD, TEMPLATE |
| S16 | `tasks/dev/pre-cadrage-entretien-client/preuves-u025/` | inventaire de 550 fichiers, lecture des fermetures, rapports, matrices, locks et reçus d’arrêt | P1/P2 qualifient trois voies sur fixtures; conclusion U-025 `INCONNU` | FAIT ÉTABLI | PASS locaux contre absence de décision V0 réelle | séparer qualification technique et résultat produit | dossier |
| S17 | `preuves-u025/m3-12-consolidation-v1/closure.md` et `matrix.json` | intégrale | trois voies survivent, aucune dominance d’effort, zéro appel fournisseur en P2 | FAIT ÉTABLI | égalité de projection sur fixtures ne prouve pas même décision réelle | conserver `INCONNU` | dossier |
| S18 | `preuves-u025/p3-v1/README.md`, `zero-execution-receipt.json`, `execution-v4/hold-receipt.json` | intégrale | lock review-ready puis `HOLD_M3_14_P3_EXECUTION`, zéro appel, retry ou dépense | FAIT ÉTABLI | préparation ne vaut pas exécution | historique seulement | dossier |
| S19 | `tasks/dev/pre-cadrage-entretien-client/campagne-v0/` | inventaire et lecture des manifestes, reçus, registres, métriques et restitution | panel 2, une sortie, Grok `FAIL G-001`, Kimi `HARNESS_ERROR`, abstention | FAIT ÉTABLI | PASS du harnais contre absence de résultat produit positif | bilan historique sans gagnant | README, PRD, dossier |
| S20 | `tasks/dev/pre-cadrage-entretien-client/campagne-v1/` | inventaire 56 fichiers, lecture des contrats et résultats | sept produits, treize reçus, six sorties, six `FAIL G-001`, zéro PASS humain | FAIT ÉTABLI | plusieurs comptages hérités divergent | utiliser les manifestes courants, publier les conflits | README, PRD, dossier |
| S21 | `campagne-v1/guide-utilisation-v1/README.md` | intégrale | parcours opérateur, autorités, quotas, restitution et limites | FAIT ÉTABLI | surface documentée et invocations historiques divergent parfois | garder la discipline, pas la trajectoire produit | ARD, RULES |
| S22 | `tools/campagne_v1.py` | extraction ciblée puis lecture complète des contrats réutilisés | identités, comparabilité, incidents, métriques, coût `NON_DEFINI`, verdicts | FAIT ÉTABLI | code affirme parfois des constantes plus fortes que les preuves U-025 | la preuve externe borne le code | ARD, RULES |
| S23 | `tests/test_campagne_v1_*.py`, aide et fixtures | inventaire 30 fichiers, extraction ciblée et lecture des tests des contrats réutilisés | comportements de validation, coût, métriques, dossiers et restitution | FAIT ÉTABLI | test vert ne prouve pas qualité réelle | utiliser comme preuve de contrat seulement | dossier |
| S24 | `tools/validateur_pre_cadrage_v0.py` | lecture ciblée de `_parser_g001` et appels | `G-001` exige `---`, ordre fermé des champs et sections | FAIT ÉTABLI | stimulus visible emploie une clôture `yaml` | aucune requalification qualitative des six FAIL | README, dossier |
| S25 | dossier privé `2026-08-29-product-reset/01-04` et `oracle-product-reset-v1.json` | intégrale | besoin, état des docs, règles et contrat d’entrée Oracle | FAIT ÉTABLI | JSON est une entrée, pas un verdict | citer les transcripts pour les avis | tous |
| S26 | transcript Oracle `handoff-consult-f035e886` | intégrale; consultation `LIVE_VERIFIED`, preuve modèle `verified=yes` | avis Oracle : recadrage qualité-first, profils séparés, classement situé, ties, abstention | FAIT ÉTABLI | nombres proposés de tâches/runs/juges ne sont pas décisions | retenir principes comme déductions, pas les nombres | PRD, ARD |
| S27 | transcript Oracle `ayo-veut-repartir-dans-une` | intégrale | avis Oracle : démarche agile compatible sous conditions | FAIT ÉTABLI | preuve modèle `verified=no`; phase agile fermée | ne pas appeler cet avis `LIVE_VERIFIED`; ne pas ticketiser | dossier |
| S28 | audit externe privé | intégrale | contenu de l’audit : C1-C2 et M1-M5, limites d’identité, coût, chemins positifs et herméticité | FAIT ÉTABLI | rapport externe ne remplace pas les preuves primaires | vérifier puis intégrer seulement les constats soutenus | dossier |
| S29 | Project personnel #5 | requête GitHub live read-only du 29 août | 85 éléments, Done 82, Backlog 1, In progress 1, In review 1 | FAIT ÉTABLI | Done ne prouve pas réussite produit | état de suivi séparé | README, dossier |
| S30 | Objets GitHub #14-19, #34, #37, #40, #42, #44, #48-55, #59, #61, #64-77 | lecture corps, commentaires et relations utiles | décisions et preuves V0/U-025 | FAIT ÉTABLI | #50 et #55 sont des PR, pas des Issues | corriger la nature des objets; garder décisions historiques | dossier |
| S31 | Issues pertinentes #93-116 hors PR #94, puis #131, #133, #138, #139, #145, #148 et #150 | lecture corps, commentaires et relations utiles | préparation, campagne et restitution V1 | FAIT ÉTABLI | fermeture technique contre absence de qualité | bilan historique borné | dossier |
| S32 | PR #94 et #151 | lecture GitHub du 29 août des états, checks et fichiers | deux PR ouvertes, checks verts | FAIT ÉTABLI | non fusionnées, aucune publication implicite | ne pas merger, ne pas présenter comme courant | README, dossier |
| S33 | Issue #95 | lecture du 29 août du corps et de la relation native | relation native 22/22 sous-Issues fermées | FAIT ÉTABLI | corps annonce et liste 21; #148 est la 22e | corriger le suivi séparément, sans inférer un succès | dossier |
| S34 | worktree `/Users/ayo/.codex/worktrees/5576/benchmark-lab-x` | Git et diff read-only | branche à `19bef4e`, 66 commits derrière, gros diff non commité | FAIT ÉTABLI | base et concepts anciens, lot non repris | préserver intact, reprise manuelle conceptuelle seulement | dossier |
| S35 | contrat d'harmonisation propriétaire du 30 août, SHA-256 `147bba750436459da164876d91c25f194c9e6681e18b9fc452193fdc7fdcc64d` | intégrale | modèle-first, accès direct/API, Pi obligatoire, contrat de réussite, admissibilité avant coût, KISS et différés | DÉCISION PROPRIÉTAIRE | supersède les décisions ouvertes sur les deux profils et « qualité-stabilité » | harmoniser les sept documents sans rouvrir Pi | tous |
| S36 | transcript Oracle `handoff-consult-75f6076b` | intégrale ; consultation `LIVE_VERIFIED` en amont | cohérence du noyau documentaire et frontière d'attribution sous Pi | FAIT ÉTABLI | l'avis ne décide pas à la place d'Ayo | retenir seulement ce qui consolide S35 | tous |
| S37 | décision D1 d'Ayo dans la session propriétaire `01a05178-5ae3-70a2-9770-30b7f2b9a92a`, transmise par la correction consolidée du 30 août | instruction propriétaire relue intégralement | accès et utilisation initiaux par Lab X pour éprouver et contribuer, puis vocation publique accessible à tous | DÉCISION PROPRIÉTAIRE | l'ancienne proposition s'arrêtait à une audience interne ou à des lecteurs secondaires | inscrire la trajectoire sans prétendre à une publication actuelle | README, PRD, ARD, dossier |
| S38 | `/Users/ayo/.pi/agent/settings.json`, lignes `12-15` | extraction primaire ciblée du 30 août | exclusions de skills `!skills/**` et `!/Users/ayo/.agents/skills/**` | FAIT ÉTABLI | « deux arbres de skills exclus » ne permettait pas de reproduire l'état | consigner les deux valeurs littérales sans compléter les inconnues | ARD, dossier |
| S39 | contrat de correction de seconde passe du 30 août, SHA-256 attendu `979c9a619ad9e281b4ed779499a660fb37e73be105bebb8277bcd85292dc664a` | intégrale | rôles génériques, conditions communes, verdict explicable, attribution honnête, deux étapes publiques, ordre interne unique, économie déterministe, Pi factuel, vocabulaire V1 retiré, preuves bornées, KISS | DÉCISION PROPRIÉTAIRE | la première harmonisation codait l'approbation sur une personne, répétait l'état de Pi par configuration et laissait le coût `INCONNU` non spécifié | appliquer en une passe sur les sept documents sans toucher aux artefacts historiques | tous |
| S40 | revue read-only Fable 5, session `58a330f2-d328-4d0d-9317-eff26eff52e3` | session de l'autrice, lecture intégrale des sept documents | cinq défauts matériels, trois cas économiques non spécifiés, état de Pi imprécis, rupture sémantique du générateur V1 | FAIT ÉTABLI | verdict `FIX` contre le `PASS` documentaire précédent | corriger par S39 | tous |
| S41 | consultation Oracle `handoff-consult-10937ea7` | non lue directement ; citée `LIVE_VERIFIED` par S39 | consolidation de la revue S40 en corrections minimales | FAIT ÉTABLI | l'avis ne décide pas à la place d'Ayo | retenir seulement ce que S39 fige | tous |
| S42 | `/Users/ayo/.pi/agent/settings.json`, lignes `1-16` | extraction primaire du 30 août | `lastChangelogVersion` `0.84.4`, paquets `npm:pi-context-view`, `npm:@ff-labs/pi-fff`, `npm:@dietrichgebert/ponytail`, réglages `defaultProvider` `vllm`, `defaultModel` `qwen38-27b`, `defaultThinkingLevel` `medium`, exclusions de skills | FAIT ÉTABLI | la première rédaction élidait les scopes npm, disait « actifs » et lisait `0.84.4` comme observée | statuts déclaré, configuré, actif, observé ; version exécutée `INCONNU` | ARD, dossier |
| S43 | contrat de compatibilité CI documentaire du 30 août, SHA-256 `16018ae4c95256827ed17bd614e22b893a7eee8c27654619dfe64f2451754544` | intégrale | spécification active sous `docs/specification/` et chemins racine historiques gelés | DÉCISION PROPRIÉTAIRE | les mêmes chemins servaient auparavant de spécification active et de sources de rejeu historique | séparer les deux responsabilités sans modifier les preuves historiques | README, PRD, ARD, RULES, TEMPLATE, dossier |

## 4. Cartographie source vers affirmation et décision

Les décisions D01 à D26 constituent la cartographie courante. D01 à D16 viennent du contrat S35 ; D17 vient de la décision propriétaire S37 ; D18 à D26 viennent du contrat de seconde passe S39, appuyé par la revue S40 et l'Oracle S41. S36 consolide le noyau sans rouvrir l'autorité d'Ayo ; S38 et S42 fournissent les preuves primaires de D05 et D25.

| ID | Affirmation | Sources | Statut | Conflit antérieur | Décision documentaire | Cibles |
|---|---|---|---|---|---|---|
| D01 | Le produit met le modèle en avant ; la configuration observée est l'unité de preuve | S35, S36 | DÉCISION PROPRIÉTAIRE | l'ancienne proposition mettait la solution complète au premier plan | distinguer objet produit et unité de preuve | README, CONTEXT, PRD, ARD, RULES |
| D02 | Le premier prototype couvre seulement les accès directs ou API sous le même Pi | S35, S36 | DÉCISION PROPRIÉTAIRE | deux profils actifs étaient proposés | retirer le profil abonnement du périmètre actif | README, CONTEXT, PRD, ARD, RULES, TEMPLATE |
| D03 | Pi est obligatoire et constant ; son choix n'est plus ouvert | S35 | DÉCISION PROPRIÉTAIRE | Pi avait été présenté comme défavorable ou remplaçable | rendre Pi invariant du prototype | README, CONTEXT, PRD, ARD, RULES, TEMPLATE |
| D04 | L'état de Pi expose paquet ou fork, version, extensions, outils, skills, contexte, environnement et date | S35, S36 | DÉCISION PROPRIÉTAIRE | « harnais constant » ne précisait pas sa transparence | rendre ces champs obligatoires et laisser l'absent `INCONNU` | CONTEXT, PRD, ARD, RULES, TEMPLATE |
| D05 | L'état relevé le 30 août 2026 est `@earendil-works/pi-coding-agent` déclaré, `0.84.4` d'après `lastChangelogVersion` avec version exécutée `INCONNU`, paquets configurés `npm:pi-context-view`, `npm:@ff-labs/pi-fff`, `npm:@dietrichgebert/ponytail` non prouvés actifs, exclusions `!skills/**`, `!/Users/ayo/.agents/skills/**` | S35, S36, S38, S42 | FAIT ÉTABLI | Pi pouvait être lu comme vanilla ou dépouillé ; la première rédaction élidait les scopes npm et appelait « actifs » des paquets seulement configurés | publier les identifiants exacts avec leur statut, sans en déduire une neutralité ni compléter outils, contexte ou version exécutée | README, ARD, dossier |
| D06 | Le verdict porte sur la configuration observée sous Pi et n'isole pas causalement le modèle | S35, S36 | DÉCISION PROPRIÉTAIRE | certaines formulations classaient le modèle seul | ajouter une limite d'attribution explicite | README, CONTEXT, PRD, ARD, RULES, TEMPLATE |
| D07 | Chaque tâche possède avant exécution un contrat préparé et approuvé par le responsable de campagne | S35, S36, S39 | DÉCISION PROPRIÉTAIRE | la méthode de jugement restait ouverte ou déléguée à l'utilisateur ; la version antérieure de cette ligne nommait une équipe et une personne | figer préparation et approbation avant résultat, portées par le rôle | README, CONTEXT, PRD, ARD, RULES, TEMPLATE |
| D08 | Le contrat contient résultat attendu, obligations, erreurs éliminatoires, trois verdicts et au maximum deux critères secondaires | S35, S36 | DÉCISION PROPRIÉTAIRE | rubriques, répétitions et métriques formaient un socle trop large | réduire le contrat au minimum décidé | CONTEXT, PRD, ARD, RULES, TEMPLATE |
| D09 | Le demandeur-lecteur n'invente ni seuil ni méthode de jugement | S35, S39 | DÉCISION PROPRIÉTAIRE | les dimensions et seuils pouvaient être reportés sur l'utilisateur ; la version antérieure de cette ligne disait « utilisateur final » et « Ayo approuve » | le responsable de campagne cadre et approuve | PRD, RULES, TEMPLATE |
| D10 | L'ordre interne compte six opérations canoniques : erreurs éliminatoires ; obligations et preuve ; verdict d'admissibilité ; exclusion de `NE SATISFAIT PAS` et `INDETERMINE` de la recommandation économique ; coût entre les seuls `SATISFAIT` ; bénéfices prévus des options `SATISFAIT` plus chères | S35, S36, S39 | DÉCISION PROPRIÉTAIRE | « qualité-stabilité puis compromis » restait abstrait ; la version antérieure de cette ligne résumait quatre pas | rendre l'ordre exécutable en six opérations, distinctes des deux étapes visibles | README, PRD, ARD, RULES, TEMPLATE |
| D11 | Aucun score global, meilleur modèle absolu ou classement universel | S35, S36 | DÉCISION PROPRIÉTAIRE | un agrégat de qualité restait une décision ouverte | interdire l'agrégat global | README, PRD, ARD, RULES, TEMPLATE |
| D12 | `quote-thread-summary` est seulement un scénario réversible de maquette | S35, S36 | DÉCISION PROPRIÉTAIRE | le scénario pouvait être lu comme tâche canonique | marquer son statut local et réversible | README, CONTEXT, PRD, RULES, TEMPLATE |
| D13 | Abonnements, produits agentiques, comparaison de harnais, autres harnais dépouillés, OrbStack et `perso-hermes` sont différés | S35, S36 | DÉCISION PROPRIÉTAIRE | deux profils et des environnements futurs étaient actifs ou ouverts | retirer leurs objets et flux du prototype | README, PRD, ARD, RULES, TEMPLATE |
| D14 | KISS : une complexité entre après démonstration d'un besoin dans une itération antérieure | S35, S36 | DÉCISION PROPRIÉTAIRE | répétitions, rubriques et architecture anticipaient des besoins | centraliser la règle dans `docs/specification/RULES.md` et pointer vers elle | README, PRD, ARD, RULES, TEMPLATE |
| D15 | V0 et V1 restent historiques sans classement qualitatif, baseline, coût par résultat acceptable ni recommandation | S19, S20, S35 | DÉCISION PROPRIÉTAIRE appuyée par des faits | des preuves techniques pouvaient être promues en résultat produit | conserver les faits et interdire leur requalification | tous |
| D16 | Aucun nom ou numéro de version n'est canonisé | S35 | DÉCISION PROPRIÉTAIRE | plusieurs noms futurs restaient proposés | retirer les choix de nom actifs | README, PRD, ARD, RULES, dossier |
| D17 | L'accès et l'utilisation commencent avec la communauté Lab X pour éprouver et contribuer ; le produit a ensuite vocation à devenir public et accessible à tous | S37 | DÉCISION PROPRIÉTAIRE | la proposition disait seulement audience Lab X et lecteurs extérieurs secondaires | inscrire la trajectoire d'accès sans déclarer le produit publié | README, PRD, ARD, dossier |
| D18 | Deux rôles génériques seulement, demandeur-lecteur et responsable de campagne, cumulables par une même personne ; Ayo reste l'autorité actuelle du projet et des décisions documentaires, jamais une identité produit codée. Cette décision corrige les versions antérieures de D07, D09 et D10, réécrites ci-dessus pour les deux rôles et les six opérations canoniques | S39, S40, S41 | DÉCISION PROPRIÉTAIRE | les versions antérieures de D07 et D09 nommaient une équipe et une personne comme approbateur ; « équipe » et « utilisateur final » restaient indéfinis ; D10 résumait quatre pas | remplacer la personne par le rôle dans les surfaces produit ; conserver l'autorité d'Ayo dans le README et ce dossier | README, CONTEXT, PRD, ARD, RULES, TEMPLATE |
| D19 | Un objet logique unique, conditions de test communes, déclaré avant le premier candidat et référencé par toutes les configurations comparées ; une condition modifiée ouvre une nouvelle comparaison | S39, S40 | DÉCISION PROPRIÉTAIRE | l'état de Pi était répété dans chaque configuration et la liste des champs existait en cinq copies | définir l'objet dans le glossaire et l'ARD, y renvoyer ailleurs | README, CONTEXT, PRD, ARD, RULES, TEMPLATE |
| D20 | Tout verdict publiable porte valeur, motif court, critères ou constats concernés, références de preuve et responsable | S39, S40 | DÉCISION PROPRIÉTAIRE | le verdict était une valeur seule ; seule l'exclusion exigeait une raison | règle unique dans RULES §6, colonnes dans le gabarit | CONTEXT, PRD, ARD, RULES, TEMPLATE |
| D21 | Le modèle est l'identifiant principal présenté ; aucun effet que le fournisseur, l'effort, Pi ou ses réglages peuvent influencer n'est attribué au seul modèle | S39 | DÉCISION PROPRIÉTAIRE | la citation d'attribution omettait l'effort, les réglages et l'environnement selon les documents | une citation canonique alignée | README, CONTEXT, PRD, ARD, RULES, TEMPLATE |
| D22 | Restitution publique en exactement deux étapes, admissibilité puis comparaison économique entre `SATISFAIT`, détails sur demande sans troisième étape ; variante A comme direction de maquette réversible ; ni podium, ni score global, ni graphique trompeur | S39, S41 | DÉCISION PROPRIÉTAIRE | la restitution était une liste plate de six contenus ; la maquette n'avait aucun statut | structurer PRD §10, RULES §10 et ARD 4.7 ; laisser la maquette hors architecture | README, CONTEXT, PRD, ARD, RULES, TEMPLATE |
| D23 | Ordre interne unique en six opérations, celles de RULES §7 et du gabarit, distinct des deux étapes visibles | S39, S40 | DÉCISION PROPRIÉTAIRE | PRD et ARD numérotaient cinq pas différents | aligner PRD §7 et ARD §7 | PRD, ARD, RULES, TEMPLATE |
| D24 | Économie déterministe : coût `INCONNU` ni zéro, ni estimation, ni maximum, jamais économiquement supérieur ni satisfaisant une obligation de coût ; égalités co-moins-chères ; critère secondaire départageant seulement avec unité et sens favorable déclarés ; dépense des non admissibles visible mais exclue ; coût et bénéfice jamais fusionnés | S39, S40 | DÉCISION PROPRIÉTAIRE | trois cas restaient non spécifiés | règles dans RULES §8, renvoi depuis ARD 4.6 et le gabarit | CONTEXT, ARD, RULES, TEMPLATE |
| D25 | Pi factuel : statuts déclaré, configuré, actif, observé ; `lastChangelogVersion` ne prouve pas la version exécutée ; identifiants de paquets exacts ; valeurs effectives de fournisseur, modèle et effort relevées par candidat ; Pi, paquets et environnement présentés une fois | S39, S40, S42 | DÉCISION PROPRIÉTAIRE appuyée par des faits | voir D05 | tableau ARD 3.1 avec statuts ; ligne « effort » par candidat | README, CONTEXT, ARD, RULES, TEMPLATE |
| D26 | Le sigle anglais de classification des affirmations du générateur V1 n'apparaît dans aucun document actif ; le générateur, la restitution V1 et leurs tests restent inchangés et non normatifs ; leurs références restent liées aux chemins racine historiques gelés et ne sont pas remappées vers la spécification active | S39, S40, S43 | DÉCISION PROPRIÉTAIRE | les mêmes chemins servaient de sources historiques et de spécification active | séparer les chemins historiques et actifs, règle dans RULES §12, contradiction C08 résolue | RULES, dossier |

## 5. Contradictions et résolution documentaire

### C01. Stimulus contre `G-001`

**FAIT ÉTABLI** : `stimulus.md` montre l’exemple sous une clôture Markdown `yaml`. `_parser_g001` dans `tools/validateur_pre_cadrage_v0.py` refuse toute sortie dont la première ligne n’est pas `---`. L’Issue #150 reproduit le conflit : le même contenu en frontmatter franchit `G-001`, puis rencontre `G-003`.

**DÉCISION PROPRIÉTAIRE** : conserver les six `FAIL G-001` V1 comme preuve du défaut mécanique exact sous le validateur historique. Ils ne soutiennent aucune conclusion comparative sur la qualité des six sorties.

### C02. Paquet approuvé contre finalité benchmark

**FAIT ÉTABLI** : `brief-proprietaire.md` et `registre-verite.md` excluent explicitement mesure de performance, classement et recommandation de modèle.

**DÉCISION PROPRIÉTAIRE** : conserver le paquet comme preuve historique de pré-cadrage. Une future campagne exige un nouveau contrat de réussite et une nouvelle autorité.

### C03. Rubrique riche contre agrégation étroite

**FAIT ÉTABLI** : le TEMPLATE historique sait porter répétitions, audit et rubrique humaine multidimensionnelle. Son analyse décisionnelle finale se réduit pourtant à acceptabilité, coût et latence.

**DÉCISION PROPRIÉTAIRE** : conserver cette structure comme patrimoine historique. Le premier prototype applique le contrat minimal actuel ; rubriques et répétitions n'entrent qu'après démonstration d'un besoin.

### C04. PASS techniques contre absence de résultat produit

**FAIT ÉTABLI** : P1/P2 U-025, témoins et qualification V1 comportent des `PASS`. La consolidation U-025 reste `INCONNU`; V0 et V1 n’ont aucun verdict humain réel ni classement qualitatif.

**DÉCISION PROPRIÉTAIRE** : chaque `PASS` reste borné à son objet technique. Aucun n'est présenté comme verdict `SATISFAIT` ou succès produit.

### C05. Comptages V1 divergents

**FAIT ÉTABLI** : le gel de verdicts historique annonce `ABSENTE=2` et `FAIL=2`, tandis que le manifeste courant des dossiers annonce `ABSENTE=3` et `FAIL=6`. `etat-v1.json` porte aussi `panel=[]` malgré sept configurations dans le registre officiel.

**DÉCISION PROPRIÉTAIRE** : les artefacts courants de couverture, validation et dossiers portent le bilan historique ; les divergences restent publiées comme dette de cohérence. Aucune réparation silencieuse.

### C06. Corps #95 contre relation native

**FAIT ÉTABLI** : le corps de #95 annonce et liste 21 sous-Issues. La relation native compte 22/22 sous-Issues fermées, la 22e étant #148.

**DÉCISION PROPRIÉTAIRE** : traiter ce point comme incohérence de suivi. Il ne change ni la couverture V1 de `6/7`, ni les verdicts produit.

### C07. Pages et PR ouvertes

**FAIT ÉTABLI** : `pages/index.html` sur `main` est un placeholder. Les PR #94 et #151 sont ouvertes avec checks verts.

**DÉCISION PROPRIÉTAIRE** : ne présenter aucune restitution de PR comme publication courante et ne fusionner aucune PR.

### C08. Générateur V1 et spécification active

**FAIT ÉTABLI** : `tools/campagne_v1.py` cite `docs/PRD.md` section 14, `docs/ARD.md` section 7 et des règles `U-009` à `U-019` de `docs/RULES.md` comme sources autorisées de la restitution V1. Ces trois chemins sont désormais les sources historiques gelées attendues par V1. La spécification active sous `docs/specification/` n'expose pas ces références. La restitution `restitution-humaine-v1/index.html` et ses tests emploient un sigle anglais de classification des affirmations, retiré des documents actifs.

**DÉCISION PROPRIÉTAIRE** : générateur, restitution et tests V1 restent inchangés sous leur identité d'origine et non normatifs. Leurs références restent liées aux sources historiques gelées ; elles ne sont pas remappées vers la spécification active. Cette séparation résout la collision de chemins sans régénérer ni requalifier V1.

## 6. Bilan historique V0 et V1

### 6.1 V0

| Élément | Fait établi |
|---|---|
| Profil | API |
| Panel | Grok et Kimi |
| Plan | une acquisition par configuration, aucune répétition |
| Exécution | deux invocations, une sortie, un appel modèle ou fournisseur observé |
| Grok | sortie présente; identité servie, paramètres, provenance et coût `INCONNU`; `FAIL G-001` |
| Kimi | `HARNESS_ERROR` |
| Revue humaine | zéro dossier, zéro verdict |
| Couverture | `1/2` |
| Acceptabilité | `0/1` sortie disponible |
| Coût | total `INCONNU`, par acceptable `NON_DEFINI` |
| Classement | front à trois axes non calculable |
| Conclusion | `ABSTENTION`, aucun gagnant ou recommandation |

Le terminal `HOLD_M7_1_ACQUISITION` et la fermeture ultérieure de P3 par décision propriétaire avec zéro nouvel appel restent des faits de processus. Ils n’améliorent pas la qualité observée.

### 6.2 V1

| Élément | Fait établi |
|---|---|
| Profil | abonnement, API explicitement exclu par #97 |
| Panel | sept produits-plans |
| Preuves | treize reçus, six sorties sur sept |
| Validation | six `FAIL G-001`, zéro `PASS` |
| Produit absent | Cursor Kimi; #148 prépare seulement un nouveau créneau, sans appel |
| Revue humaine | aucun dossier éligible, zéro verdict |
| Qualité | aucune mesure multidimensionnelle officielle |
| Répétitions | aucun objet actuel de stabilité qualitative |
| Quotas et effort | `INCONNU` dans la consolidation |
| Coût abonnement par acceptable | `NON_DEFINI` par décision `D_V1_02` |
| Conclusion | abstention sur les trois axes historiques; aucun gagnant ou recommandation |

### 6.3 Limite commune

Ni V0 ni V1 ne soutient un classement qualitatif rétrospectif. Les sorties peuvent servir à diagnostiquer les contrats, mais toute nouvelle étude doit annoncer qu'elle applique un nouveau contrat et qu'elle ne remplace pas les verdicts historiques.

## 7. Conservation, changement, différé et archive

### Conserver

- workflow et conclusion bornés
- identité complète, provenance, empreintes et reçus
- sortie brute distincte du verdict
- contrat figé avant acquisition
- distinction incident fournisseur et `HARNESS_ERROR`
- inconnues littérales et abstention historique
- campagnes historiques immuables

### Changer maintenant

- objet produit principal : modèle
- accès et utilisation initiaux par Lab X pour éprouver et contribuer, puis vocation publique accessible à tous
- unité de preuve : configuration observée sous Pi
- périmètre actif : accès direct ou API uniquement
- Pi obligatoire, constant et transparent
- contrat minimal de réussite préparé et approuvé par le responsable de campagne avant exécution
- deux rôles génériques, sans personne ni pseudonyme codé
- conditions de test communes déclarées une fois avant le premier candidat
- verdict explicable : valeur, motif, critères ou constats, preuves, responsable
- admissibilité avant coût, économie déterministe pour `INCONNU` et les égalités
- bénéfices du plus cher bornés aux critères prévus, avec unité et sens favorable
- restitution publique en deux étapes, détails sur demande, sans score global ni classement universel

### Différer

- abonnements et produits agentiques
- comparaison de harnais et autres harnais dépouillés
- OrbStack et `perso-hermes`
- répétitions, statistiques, rubriques ou architecture supplémentaires sans besoin démontré

### Déprécier comme valeur active

- « qualité et stabilité » comme dimensions universelles
- audience interne sans trajectoire vers un produit public accessible à tous
- deux profils actifs dès le premier prototype
- coût par sortie acceptable comme question universelle
- taux d'acceptabilité comme synonyme de qualité
- Pareto qualité ou fiabilité, coût et latence comme réponse produit par défaut
- panel, nombre de runs ou trajectoire versionnelle historique comme limites futures
- termes « V1-bis », « BLX-QF1 » et « V2-alpha » comme noms implicites
- une personne ou un pseudonyme comme approbateur ou destinataire codé dans une surface produit
- le sigle anglais de classification des affirmations du générateur V1 ; les documents actifs disent règles, contrats, preuves, périmètres et conditions d'arrêt
- l'état de Pi répété dans chaque configuration

### Archiver

- V0 et V1 avec leurs verdicts exacts
- preuves U-025 et P3, dont `INCONNU` et `HOLD`
- VERIFY-V7 et PREUVE-ATTEIGNABILITE-FLOAT64 comme actifs spécialisés
- anciennes cartes dans `tasks/archives`
- anciennes formulations PRD/ARD/RULES comme histoire documentaire
- générateur, restitution et tests V1 sous leur identité d'origine, non normatifs

« Différer » signifie exclure du premier prototype sans interdire une étude future motivée. « Archiver » signifie conserver et rendre lisible, sans autorité courante.

## 8. Stratégie explicite pour le lot 5576

### État vérifié

**FAIT ÉTABLI** : `/Users/ayo/.codex/worktrees/5576/benchmark-lab-x` est sur `docs/v0-canonical-rewrite`, HEAD `19bef4ecdccd6c797fb21261837a3efa0c48e081`, avec un diff entièrement non commité. Il est 66 commits derrière la base documentaire courante et ne contient aucun commit à reprendre.

Le lot touche README, PRD, ARD, RULES, TEMPLATE, VERIFY-V7, la preuve float64 et une archive. Il appartient à une autre tranche et doit rester intact.

### Décision de traitement

**DÉCISION PROPRIÉTAIRE** : conserver un `HOLD` d'intégration non bloquant :

- aucun cleanup, reset, commit, cherry-pick, merge ou écrasement du lot
- aucune reprise silencieuse de ses fichiers
- lecture read-only seulement
- reprise manuelle des concepts encore valides, après vérification primaire

Concepts retenus : workflow borné, abstention, provenance, revue humaine aveugle, séparation panne fournisseur et `HARNESS_ERROR`.

Concepts changés ou dépréciés : question coût-first, audience interne sans trajectoire publique, qualité réduite à acceptabilité/Pareto, V1 prospective et statut unique du TEMPLATE.

### Action ultérieure possible

Après la revue de la refondation courante, Ayo pourra autoriser séparément la conservation, l'extraction manuelle ou l'abandon du lot 5576. Aucune de ces actions n'est autorisée par ce dossier.

## 9. État GitHub au checkpoint

Instantané live read-only au 29 août 2026 :

- Project personnel #5 ouvert, 85 éléments
- `Done=82`, `Backlog=1`, `In progress=1`, `In review=1`
- Issues ouvertes : #93, #95, #150
- PR ouvertes : #94, #151, checks verts
- #95 : relation native `22/22` sous-Issues fermées, corps resté à 21

Le Project porte l’état de travail. Les preuves de campagne portent l’état produit. Ces deux plans ne sont jamais fusionnés.

## 10. Décisions propriétaires intégrées

Les décisions D01 à D26 de la section 4 remplacent les anciennes décisions ouvertes sur « qualité et stabilité », les deux profils, l'objet classé, la trajectoire d'accès, l'approbateur nominal, l'état de Pi répété et l'économie non spécifiée.

Le périmètre actif est désormais fermé pour cette tranche :

- modèle mis en avant, configuration observée reliée aux conditions de test communes comme unité de preuve
- accès initial par Lab X pour éprouver et contribuer, puis vocation publique accessible à tous
- accès direct ou API sous Pi obligatoire et constant
- deux rôles génériques ; contrat minimal préparé et approuvé par le responsable de campagne ; Ayo reste l'autorité du projet, hors surface produit
- conditions de test communes déclarées une fois
- trois verdicts explicables, puis coût et bénéfices entre les seuls `SATISFAIT`, avec économie déterministe
- restitution publique en exactement deux étapes
- aucun score global, podium général, graphique trompeur ou classement universel
- complexité future et éléments différés soumis à la règle KISS

Le panel, l'exécution, la publication et un éventuel nom de version nécessitent des autorités ultérieures distinctes. Ils ne bloquent pas l'harmonisation documentaire.

## 11. Limites de la refondation

- aucun utilisateur de la communauté n’a été interrogé dans cette tranche
- aucun contrat futur n'a été calibré sur des sorties réelles
- aucun appel candidat, coût ou bénéfice nouveau n'a été mesuré
- les outils, le contexte et l'environnement d'une future exécution sous Pi restent à figer dans son reçu
- aucune comparaison d'abonnement, de produit agentique, de harnais ou d'environnement différé n'a été menée
- l’audit externe a orienté la vérification mais ne remplace aucune source primaire
- les 550 fichiers U-025 ont été inventoriés; seuls contrats, fermetures, rapports, matrices et preuves d’arrêt utiles ont été lus sémantiquement
- l’état GitHub et les prix ou plans historiques peuvent dériver après le checkpoint
- la version exécutée de Pi reste non vérifiée : `0.84.4` vient de `lastChangelogVersion`
- l'empreinte SHA-256 du contrat de seconde passe a été fournie, pas recalculée, dans la passe d'écriture

### 11.1 Compatibilité des preuves historiques

**FAIT ÉTABLI** : avant la séparation des chemins, la refonte des trois documents racine rompait les empreintes attendues par les preuves historiques : la reproduction documentaire ciblée rendait `59/61` et la suite complète exécutait 831 tests avant de finir avec deux échecs et cinq erreurs.

**FAIT ÉTABLI** : les chemins `docs/ARD.md`, `docs/PRD.md` et `docs/RULES.md` ont été restaurés byte-identiquement à la base relue, avec les SHA-256 respectifs `f452dbfeeccbf8713be541a466066cc5ba1cd48be0da276181c09b6432f12db7`, `0aaab457eaf3202025c33754b7fd87f41aea858c1108981fbd4c0ccee1dc0126` et `f1edbdc9f8914aca41beef6221418704bff5db5f913688a5cc3281df71921938`. Les trois contenus refondus sont conservés sous `docs/specification/`, et les liens actifs pointent vers eux.

**FAIT ÉTABLI** : après cette séparation et la correction consolidée, les cinq modules ciblés rendent `73/73 OK` et la commande CI autoritative complète rend `831/831 OK`, avec un code de sortie nul dans les deux cas.

**DÉCISION PROPRIÉTAIRE** : aucun générateur, test, journal, reçu, verrou, manifeste ou artefact de campagne n'est modifié. V0, V1 et U025 ne sont ni recalculés, ni régénérés, ni requalifiés. La validation de cette séparation exige les 73 tests ciblés et la commande CI autoritative complète ; leur réussite prouve uniquement la compatibilité technique des chemins.

## 12. Cohérence des documents consolidés

| Document | Responsabilité | Ne décide pas |
|---|---|---|
| `README.md` | promesse, périmètre actif, état historique et navigation | protocole détaillé |
| `CONTEXT.md` | glossaire du domaine et des deux rôles | architecture ou tickets |
| `docs/specification/PRD.md` | besoin, audience, question active, périmètre, restitution en deux étapes et résultat | technologie |
| `docs/specification/ARD.md` | objets, conditions de test communes, état de Pi, flux, preuves et frontière d'attribution | plateforme exhaustive |
| `docs/specification/RULES.md` | invariants décidés et règle KISS | autorité d'exécution |
| `docs/PRD.md`, `docs/ARD.md`, `docs/RULES.md` | sources historiques gelées pour V0, V1 et U025 | spécification active |
| `tasks/TEMPLATE.md` | contrat minimal d'une future tâche | autorité d'exécution |
| ce dossier | sources, conflits, migration et checkpoint | phase agile |

## 13. Portée du dossier

**DÉDUCTION RAISONNÉE** : prémisses : les sept documents actifs mettent le modèle en avant, prennent la configuration observée reliée aux conditions de test communes comme unité de preuve, définissent deux rôles génériques sans personne codée, exigent un verdict explicable, une restitution en exactement deux étapes et une économie déterministe, utilisent le même contrat minimal et les six mêmes opérations internes ; ils conservent V0/V1, le générateur V1 et le lot 5576 ; la spécification active est séparée des trois sources historiques gelées. Conclusion : la proposition est cohérente et bornée.

Ce dossier ne s'auto-certifie pas. Le verdict indépendant vit dans les preuves privées de la tranche. Ni ce dossier, ni ce verdict n'accorde d'autorité d'exécution, de publication ou de mutation GitHub.
