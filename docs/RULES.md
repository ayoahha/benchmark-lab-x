# Règles de mesure

Version 2.0, mise à jour le 5 août 2026

Ce fichier définit les invariants qui rendent une mesure éligible et un classement défendable. Il prévaut uniquement sur l’éligibilité, la notation et la validité des résultats. Le [PRD](PRD.md) gouverne le produit et ses jalons ; l’[ARD](ARD.md) gouverne l’architecture et les preuves techniques.

Une règle peut précéder son automatisation de plusieurs versions : ces règles couvrent tout le développement à venir, pas seulement la V0. La matrice de conformité du §5 dit pour chaque règle à quelle version son automatisation est due et où elle en est. Un écart n'est un défaut que si la version cible est atteinte. Tant que la preuve d'une règle manque, le résultat concerné reste provisoire.

## 1. Périmètre et identité

- **R-001. Données synthétiques.** Toute donnée utilisée par une carte notée est synthétique : aucun nom, entreprise, adresse, secret ou fait personnel réels. Une description utilisateur contenant de telles données est refusée avant création de carte.

- **R-002. Jeu retenu confidentiel.** À partir de V4, une carte retenue reste sur le poste contrôlé par Ayo, hors Git public, chats, caches et outils tiers. Seul le prompt strictement nécessaire à son run officiel peut être transmis au candidat. Toute fuite avérée ou soupçonnée invalide la carte et remet sa série longitudinale à zéro.

- **R-003. Candidat et configuration explicites.** Le candidat lisible est le triplet modèle, route d’exécution épinglée et effort de raisonnement déclaré. La route comprend le backend et le provider réellement servi. Chaque run conserve aussi un `execution_manifest_hash` couvrant les paramètres et composants qui influencent l’exécution. Deux valeurs d’effort, deux providers ou deux backends constituent des candidats distincts.

- **R-003a. Route choisie par un critère déclaré.** La route épinglée résulte d’un critère écrit, versionné et rejouable, appliqué avant la campagne et consigné avec elle. Le critère n’ordonne que des propriétés stables de la route, dans cet ordre : précision numérique servie, puis appartenance à l’éditeur du modèle, puis paramètres du contrat acceptés. L’éditeur précède les paramètres parce qu’un critère qui privilégie la route acceptant le harnais laisse l’outillage choisir l’objet mesuré ; un paramètre refusé se déclare et se consigne, une route qui n’est pas celle de l’éditeur ne se rattrape pas. Une quantification non déclarée par l’éditeur vaut précision native ; non déclarée par un revendeur, elle passe derrière toute précision déclarée. Disponibilité, statut et débit sont observés et signalés, jamais ordonnants : un critère qui en dépend rend un verdict différent d’un jour à l’autre. Une route qui sert le modèle sous une quantification plus dégradée qu’une autre route disponible ne peut être épinglée sans que la carte le justifie par écrit. Le changement de pin est un acte préalable qui crée un candidat distinct ; aucun basculement de route ne peut avoir lieu pendant un run ni entre les runs d’un même candidat.

- **R-003b. Reprise après limite de débit.** Une limite de débit annoncée par le fournisseur est une condition transitoire, pas une non-conformité de route. Le délai qu’il publie est respecté avant toute nouvelle tentative, et le nombre de tentatives reste borné par la campagne. Renvoyer le même appel après ce délai ne modifie ni le budget, ni la route, ni le stimulus : ce n’est pas une relance au sens de R-025.

- **R-004. Route et opacité déclarées.** Backend, modèle demandé et servi, provider demandé et servi, révision exposée et politique de données sont consignés. Une non-conformité connue au pré-vol rend `INELIGIBLE`, sans appel, chaque run attendu du couple carte-configuration. Après un appel, un modèle ou provider servi différent du pin invalide la tentative, qui ne devient jamais `SCORED`. Si le nombre maximal de tentatives est atteint sans succès, le run attendu devient `INFRA_ERROR`. Une configuration conforme dont un run planifié n’a jamais été tenté à la clôture reste `MISSING`. Si le fournisseur ne révèle pas la révision, elle vaut `opaque` ; une comparaison temporelle décrit alors le même endpoint observé à deux dates, jamais un binaire prouvé identique.

- **R-005. Deux régimes de confidentialité.** Chaque run déclare son régime et le reçu le conserve.
  - **R-005a, retenu.** Les routes susceptibles d’entraîner sur les requêtes sont exclues. Si aucune route conforme n’existe, le candidat est `INELIGIBLE` sur cette carte.
  - **R-005b, exposé.** La carte étant publique, une route susceptible d’entraîner sur la requête peut être utilisée si cette propriété et le provider servi sont consignés.

  L’outillage échoue du côté sûr : une carte retenue ne peut jamais être exécutée sous un régime exposé.

- **R-006. Score par code.** Le score est produit et modifié uniquement par du code déterministe. L’humain conçoit, calibre, audite et approuve l’instrument ; il ne corrige jamais une note à la main.

- **R-007. Classements séparés.** Les domaines ne sont jamais fusionnés en un score global. Les pistes `direct` et `agent` restent distinctes. Un profil peut regrouper plusieurs cartes uniquement si ses niveaux minimaux et sa contrainte de départage ont été écrits avant la campagne.

- **R-008. Aucun changement silencieux.** Toute modification du contenu visible par le candidat ou de l’instrument incrémente la version correspondante selon R-015.

- **R-009. Côté juge séparé.** Oracle, vérificateur, témoins, tests cachés et points d’évaluation ne sont jamais envoyés au candidat. Un actif côté juge peut être public pour une carte exposée ; il reste confidentiel pour une carte retenue.

## 2. Notation et traçabilité

- **R-010. Vérificateur aveugle.** Le composant de notation présente la réponse au vérificateur sous un chemin neutre indépendant du candidat. Le vérificateur lit seulement ces octets et les actifs côté juge nécessaires, jamais l’alias, le chemin du run original, `meta.json` ni une autre identité. Une invocation directe depuis un chemin contenant l’alias reste diagnostique et n’est pas éligible à une page validée. Le contrôle de conformité, composant séparé, lit les métadonnées.

- **R-011. Prédicat fermé.** Chaque point noté se décide par exécution, comptage, motif, citation exacte, contrainte vérifiée ou écart numérique à un oracle.

- **R-012. Pas de jugement sémantique noté.** Une recommandation ouverte, un lien causal, la pertinence d’une citation, le style ou l’esthétique peuvent être observés, mais ne reçoivent aucun score mécanique.

- **R-013. États terminaux explicites.** Chaque run attendu termine dans un état unique :
  - `SCORED`, avec un verdict `PASS`, `PARTIAL` ou `FAIL`
  - `UNKNOWN`, lorsque l’instrument ou la preuve est ambigu
  - `INELIGIBLE`, lorsque la route ou la configuration est non conforme avant mesure ; ce statut s’applique à tous les runs attendus du couple carte-configuration, sans appel
  - `INFRA_ERROR`, lorsque les tentatives autorisées sont épuisées sans sortie scoreable à cause d’un défaut de collecte ou de fournisseur
  - `MISSING`, lorsqu’un run planifié pour une configuration par ailleurs conforme n’a jamais été tenté à la clôture

- **R-013a. Retrait de candidat.** Un candidat retiré du panel après le gel du plan est consigné `RETIRE` avec son motif écrit. Ses runs déjà collectés restent publiés comme preuves. Un retrait ne peut jamais être motivé par le résultat observé. `RETIRE` est une décision consignée, non une panne : il ne bloque pas une page validée, là où `INFRA_ERROR` et `MISSING` accusent l’un une défaillance et l’autre un oubli.

  Un refus produit après appel vaut par défaut `FAIL`. Le diagnostic informatif `model_refusal`, hors score, n’est ajouté que sur un signal structuré du fournisseur ou un constat humain consigné ; le vérificateur ne l’infère jamais du sens du texte. Il ne peut être un succès que si le refus est le comportement correct inscrit dans la tâche et l’oracle versionnés avant collecte. Pour `finish_reason=length`, une valeur `completion_tokens` absente ou inférieure au `max_tokens` résolu indique un arrêt prématuré du fournisseur et donne `UNKNOWN` ; une valeur supérieure ou égale prouve l’épuisement du budget préenregistré et donne `FAIL`.

- **R-014. Un défaut par item.** Chaque item mesure un seul défaut observable. Une carte trop complexe à calibrer est simplifiée ou retirée ; aucun nombre artificiel d’items n’est imposé.

- **R-015. Versions, empreintes et reçus.**
  - `task-vN` couvre les consignes et entrées envoyées au candidat
  - `verify-vM` couvre vérificateur, oracle, points d’évaluation et calibrage
  - le reçu de collecte conserve `task-vN`, `prompt_hash` et `execution_manifest_hash`
  - le reçu de score conserve `verify-vM` et `verify_hash`
  - `measurement_context_hash` couvre tâche, prompt, vérificateur, protocole, environnement de mesure et régime, sans inclure l’identité du candidat

  Deux candidats sont comparables sous le même `measurement_context_hash`. Une série longitudinale de la même configuration exige aussi le même `execution_manifest_hash`. Une comparaison de versions différentes doit être annoncée comme telle. La canonicalisation et le calcul des empreintes suivent l’ARD §2.2. Les empreintes font foi ; les étiquettes servent la lecture humaine.

- **R-016. Calibrage indépendant.** Chaque prédicat possède au moins un témoin positif et un témoin négatif produits sans accès au vérificateur. Pour une carte exposée, le producteur peut être un humain distinct ou un générateur déterministe ou génératif séparé ; sa provenance, ses consignes et le résultat attendu sont consignés. Pour une carte retenue, le producteur est obligatoirement un humain autorisé distinct de l’auteur du vérificateur. Un contre-exemple conforme à la tâche mais rejeté par le vérificateur casse la carte, pas la réponse.

- **R-017. Cycle de vie des cartes.** Les prompts partis et campagnes terminées sont comptés séparément depuis les reçus. Une carte à information courte et mémorisable participe à deux campagnes au maximum et est retirée dès une publication détaillée. Une carte procédurale peut durer davantage après analyse écrite. Toute rotation côté juge incrémente `verify-vM` ; une comparaison exige ensuite une renotation commune.

## 3. Verdicts et publication

- **R-018. Structure explicite.** Une carte à checklist marque chaque item `[C]` critique ou `[S]` secondaire. Une carte à paliers utilise des prédicats ordonnés ; elle ne leur ajoute pas une seconde criticité. Les erreurs éliminatoires restent annoncées dans la tâche.

- **R-019. Verdict et répétabilité.** Sur une checklist, un `[C]` échoué donne `FAIL`; tous les items réussis donnent `PASS`; seuls des `[S]` échoués donnent `PARTIAL`. La clé de classement est alors l’ordre `PASS` > `PARTIAL` > `FAIL`. Sur une carte à paliers, le niveau atteint est le plus grand `k` tel que les paliers 1 à `k` passent tous ; le run vaut `PASS` si toute l’échelle passe et `FAIL` sinon, le niveau conservant le gradient de classement. Un défaut de sortie imputable au candidat reste `FAIL` au niveau 0.

  Une carte fermée utilise un run par candidat et retient son verdict ou son niveau. Une carte générative en utilise quatre. Pour une checklist, son verdict retenu est le troisième meilleur des quatre dans l’ordre défini ci-dessus. Pour une carte à paliers, son niveau retenu est le troisième meilleur des quatre. La page publie la distribution complète et parle de répétabilité observée sur les runs planifiés, sans inférence statistique générale.

- **R-020. Classement situé.** Chaque carte classe les candidats dont tous les runs attendus sont `SCORED`. Une checklist utilise le verdict retenu dans l’ordre `PASS` > `PARTIAL` > `FAIL` ; une carte à paliers utilise le niveau retenu décroissant. Les ex æquo restent ex æquo, sauf diagnostic de départage préenregistré. Les candidats `INELIGIBLE` sont affichés hors classement. Un `UNKNOWN`, `INFRA_ERROR` ou `MISSING` laisse la page provisoire et bloque le classement validé.

- **R-021. Diagnostics séparés du score.** Coût, durée, dispersion et jetons ne modifient jamais la note. Ils peuvent ordonner une recommandation uniquement si la contrainte correspondante a été déclarée avant collecte.

- **R-022. Catalogue noté fermé.** Une carte n’entre au catalogue noté que si tous ses points comptés sont décidables par code. Une carte demandant un jugement reste exploratoire et n’entre dans aucun classement.

- **R-023. Mécanisme discriminant explicite.** Avant collecte, toute carte décrit le bon chemin, le mode d’échec attendu et ce que ses items ou paliers distinguent. Une carte adversariale documente aussi le coût du bon chemin, du mauvais chemin et de la voie de moindre résistance, puis définit un prédicat déterministe binaire `trap_triggered` avant collecte. Par défaut, la qualification de piège est retirée si ce prédicat reste faux dans les campagnes de référence de deux versions `task-vN` successives évaluées sous le même `verify-vM`, chaque campagne comptant au moins 24 runs attendus et chacun de ces runs portant l’état `SCORED`. Une population plus petite ou un autre seuil doit être préenregistré dans la carte avant collecte.

- **R-024. Harnais avant candidat.** Un résultat aberrant bloque la validation jusqu’à l’examen du `finish_reason`, des paramètres, des jetons, de la route et du vérificateur. Le défaut du harnais est recherché avant d’imputer la surprise au candidat.

- **R-025. Budget de sortie non discriminant.** `max_tokens` est résolu avant l’appel depuis ce que la route déclare, avec un plancher de 65 536 et un plafond de campagne. Une route dont la limite déclarée est inférieure à ce plancher est `INELIGIBLE` avant toute tentative. Sa valeur et sa provenance sont consignées. Le collecteur ne relance ni n’augmente le budget après observation de la sortie. Un paramètre de raisonnement à sémantique variable n’est utilisé qu’après qualification du provider.

- **R-026. Audit humain de l’instrument.** Après notation, les sorties sont ordonnées par la clé de leur run définie en R-019, verdict pour une checklist et niveau pour une carte à paliers. Une graine consignée départage les ex æquo et sélectionne jusqu’à trois sorties hautes et trois basses. Une strate incomplète est compensée par l’autre ; sous six sorties, toutes sont auditées. L’auditeur voit la sortie et les preuves, sans identité du candidat, et répond uniquement : « le résultat noté du code, verdict et niveau éventuel, décrit-il ce que je vois ? » Un verdict ou niveau faux invalide la page, incrémente `verify-vM` et impose la renotation complète.

- **R-027. Publication fail-closed.** Le contrôle de conformité vérifie les identités, empreintes, paramètres, états et runs attendus avant agrégation finale. Une page provisoire peut expliquer les manques. Une page validée n’existe que lorsque chaque run attendu de chaque candidat éligible porte l’état `SCORED`. Aucun résultat invalide ne devient un chiffre publié.

- **R-028. Français comme langue de mesure.** Les cartes, consignes, données d’entrée, documents, messages d’outillage, pages de résultats et sorties attendues destinés à un humain sont en français. Identifiants techniques, clés machine, slugs, URL, littéraux d’API et messages bruts d’un fournisseur conservent leur forme nécessaire. Un changement de langue d’une carte crée une nouvelle `task-vN` et un contexte de mesure distinct.

## 4. Extensions contrôlées

- **R-029. Exécution outillée isolée.** Une carte agent ou cyber n’est éligible qu’avec manifeste d’outils, permissions minimales, environnement synthétique éphémère, réseau refusé par défaut, absence de secrets, quotas, arrêt d’urgence, journal complet et remise à zéro vérifiée. Aucune carte cyber ne vise un système réel. Une carte offensive exige en plus un modèle de menace approuvé et une décision humaine distincte selon AR-S-012 ; elle ne cherche jamais à contourner les garde-fous d’un fournisseur.

- **R-030. Aucune carte auto-approuvée.** Une description utilisateur ou une génération automatique produit seulement un brouillon. Instrument, oracle, témoins indépendants et validation humaine doivent être qualifiés avant toute collecte notée. Le système qui propose une tâche ne peut pas approuver seul son instrument.

## 5. Matrice de conformité

Une règle peut précéder son automatisation de plusieurs versions. Ce tableau dit, pour chaque règle, à quelle version son automatisation est **due** et où elle en est aujourd'hui. Un écart n'est un défaut que si la version cible est atteinte ou dépassée.

**Niveaux** : `écrit` la règle existe et est appliquée à la main ; `partiel` une partie est automatisée ; `outillé` le code l'applique ; `prouvé` un test ou un témoin le vérifie à chaque campagne.

| Règle | Objet | Due en | État au 2026-08-06 | Ce qui manque |
|---|---|---|---|---|
| R-001 | Données synthétiques | V0 | écrit | contrôle humain à la création de carte, jamais automatisable seul |
| R-002 | Jeu retenu confidentiel | **V4** | écrit | rien à faire avant V4 |
| R-003 | Candidat et configuration | V0 | **outillé** | `execution_manifest_hash` et backend au reçu depuis le 2026-08-06 |
| R-003a | Route choisie par un critère déclaré | V0 | **outillé** | `tools/choisir_provider.py`, critère `selection-route/v2` ; trois pins restent à réviser |
| R-003b | Reprise après limite de débit | V0 | **outillé** | le lanceur lit `retry_after_seconds` du reçu et attend avant de retenter |
| R-004 | Route et opacité | V1 | partiel | politique de données par route non publiée par le backend, voir le point ouvert ci-dessous |
| R-005 | Deux régimes | V0 | **prouvé** | témoin rejoué le 2026-08-05, régime porté par la carte |
| R-006 | Score par code | V0 | **outillé** | |
| R-007 | Classements séparés | V1 | écrit | agrégateur par domaine |
| R-008 | Aucun changement silencieux | V0 | écrit | discipline de version, pas de contrôle |
| R-009 | Côté juge séparé | V0 | **prouvé** | exclusion testée dans le collecteur |
| R-010 | Vérificateur aveugle | V1 | **outillé** | notation par chemin neutre temporaire depuis le 2026-08-06 |
| R-011 | Prédicat fermé | V0 | **outillé** | |
| R-012 | Pas de jugement sémantique | V0 | **outillé** | |
| R-013 | États terminaux | V1 | **outillé** | les cinq états et la règle `length` sont produits et agrégés ; reste le diagnostic `model_refusal`, sans cas connu |
| R-013a | Retrait de candidat | V0 | **outillé** | `retraits` déclarés dans `campaign.toml`, lus par le rapport |
| R-014 | Un défaut par item | V0 | écrit | |
| R-015 | Versions, empreintes, reçus | V1 | **outillé** | empreintes complètes, `task-vN`, `verify-vM`, `measurement_context_hash` et Chromium épinglé au 2026-08-06 |
| R-016 | Calibrage indépendant | V1 | partiel | `tools/qualifier_temoins.py` refuse la qualification tant que la provenance manque ou déclare un producteur non aveugle ; les sept témoins actuels sont dans ce cas et le disent |
| R-017 | Cycle de vie des cartes | V1 | **outillé** | compteurs dérivés des reçus dans le rapport de campagne |
| R-018 | Structure explicite | V0 | écrit | |
| R-019 | Verdict et répétabilité | V0 | **outillé** | quatre runs, troisième meilleur |
| R-020 | Classement situé | V1 | **outillé** | seuls les candidats tout-`SCORED` sont classés, les autres présentés hors classement |
| R-021 | Diagnostics séparés | V0 | **outillé** | |
| R-022 | Catalogue noté fermé | V0 | écrit | |
| R-023 | Mécanisme discriminant | V1 | partiel | `trap_triggered`, seuil de retrait versionné ; dû seulement pour une carte adversariale |
| R-024 | Harnais avant candidat | V0 | écrit | discipline ; douze artefacts trouvés par elle en deux jours |
| R-025 | Budget non discriminant | V0 | **outillé** | `INELIGIBLE` avant appel et provenance au reçu depuis le 2026-08-06 |
| R-026 | Audit humain de l'instrument | V1 | partiel | `tools/audit_instrument.py` produit le tirage aveugle ; l'audit lui-même reste un acte humain non tenu |
| R-027 | Publication fail-closed | V1 | **outillé** | le rapport énumère ses blocages et refuse le statut de page validée |
| R-028 | Français | V0 | **outillé** | contrôle d'accents au pré-envoi |
| R-029 | Exécution outillée isolée | **V3** | écrit | rien à faire avant V3 |
| R-030 | Aucune carte auto-approuvée | V0 | écrit | |

**Lecture au 2026-08-06, après la session d'outillage.** Toutes les règles dues en V0 sont désormais outillées ou prouvées, à l'exception de celles qui relèvent d'un acte humain et ne seront jamais tenues par du code seul : R-001 le contrôle des données à la création d'une carte, R-008 la discipline de version, R-014, R-018, R-022, R-024 et R-030. R-024 en particulier restera toujours une discipline, et c'est elle qui a trouvé douze artefacts de harnais en deux jours.

Les règles dues en V1 sont en avance sur leur jalon : R-010, R-013, R-015, R-017, R-020 et R-027 sont outillées alors que rien ne l'exigeait encore. Trois restent ouvertes et le sont légitimement : R-007 attend un second domaine, R-016 attend des témoins produits sans accès au vérificateur, R-026 attend un auditeur humain — l'outil de tirage existe, l'audit non.

**Point ouvert, R-004.** La règle demande de consigner la politique de données de la route. L'API du backend ne publie plus cette information par endpoint : aucun outillage ne peut satisfaire la règle telle qu'elle est écrite. Ce que le collecteur consigne aujourd'hui est la politique **demandée**, qu'il contrôle, et `opaque` pour celle de la route. Trois issues possibles, à trancher et à écrire : un registre versionné épinglé à la main, la même sémantique `opaque` que pour la révision, ou un filtre de compte documenté avec sa preuve hors API. Tant que ce choix n'est pas fait, R-004 reste `partiel` par défaut de la règle et non par défaut du code.

## 6. Hors périmètre du POC V0

Recherche web dans les tâches, sessions multi-tours, outils donnés au candidat, jugement automatisé non déterministe, score global, interface graphique publique, service planifié, fallback silencieux, jeu retenu et cyber offensif.

Le nombre de candidats n’est pas plafonné par la notation. Chaque campagne impose toutefois quotas, concurrence et plafond de dépense.
