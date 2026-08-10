---
style_gate: pass
---

# Règles de mesure

Version documentaire 3.3, 10 août 2026

Ce fichier contient uniquement les invariants d’éligibilité, de notation, d’agrégation et de publication. Le [PRD](PRD.md) gouverne le produit et ses jalons. L’[ARD](ARD.md) gouverne l’architecture et les preuves techniques.

Une règle devient opposable dès qu’un résultat revendique une propriété qui en dépend. L’absence de la preuve requise maintient le résultat concerné au statut provisoire. L’état d’implémentation ne fait pas partie de RULES.

## 1. Périmètre, identité et confidentialité

- **R-001. Données synthétiques.** Toute donnée utilisée par une carte notée est synthétique. Une donnée personnelle, un secret, un contenu client ou un fait privé réel est refusé avant persistance et collecte.

- **R-002. Jeu retenu confidentiel.** Une carte retenue reste sur un environnement contrôlé, hors dépôt public, chat, cache et outil tiers. Seul le stimulus strictement nécessaire à son run officiel peut atteindre le candidat. Sa politique d’accès, sauvegarde, restauration, exposition et retrait est approuvée avant la première campagne. Une fuite avérée ou soupçonnée invalide la série concernée.

- **R-003. Identités et configuration explicites.** L’identité de modèle comprend le mode, le modèle canonique demandé et la révision déclarée. L’identité de route comprend le backend, le provider et l’endpoint. La configuration scientifique ajoute la quantification, l’effort, les paramètres, le contexte et la politique de données. Une identité agent ajoute le nom et la version de l’agent. Le manifeste d’exécution conserve la configuration et la route exactes de chaque acquisition. Un changement de provider ne renomme pas le modèle. Chaque route réellement utilisée reste visible, et une série qui en réunit plusieurs porte le statut `multi-route`.

- **R-003a. Route préenregistrée.** Le critère de sélection de route est déclaré et versionné avant le lot. Modèle, backend, provider, endpoint observé au pré-vol, révision et dimensions obligatoires sont épinglés avant le premier appel. Une quantification déclarée est conservée exactement. Une route tierce sans quantification déclarée est `INELIGIBLE`. Une API propriétaire gérée directement par l’éditeur peut porter le statut structuré `not_disclosed`, lié au modèle, au provider, à l’endpoint, à la révision et à l’empreinte des métadonnées. Ce statut ne suppose aucune valeur de quantification et n’occupe aucun rang dans l’échelle numérique des formats. Un lock reste mono-route. Une route secondaire préenregistrée peut servir le même slot dans un nouveau lot après épuisement de la route primaire, uniquement sans artefact candidat accepté et sous égalité du modèle, de la révision, de la quantification, des paramètres, du contexte et de la politique de données. Une égalité non démontrée interdit la fusion silencieuse et reste signalée comme configuration `multi-route`.

- **R-003b. Reprises fermées.** Sous `benchmark-lab-x/protocol/v2`, une tentative supplémentaire est autorisée après `HTTP_429`, `HTTP_502`, `HTTP_503`, absence confirmée de réponse HTTP ou corps HTTP vide lorsqu’aucun artefact candidat n’a été accepté. Une collecte comporte trois tentatives au maximum. Route, contenu et budget restent inchangés. Aucune reprise n’est autorisée après acceptation d’un artefact candidat. Un seul appel d’un alias est en vol ; un `Retry-After` reçu suspend tout l’alias jusqu’à l’échéance sans suspendre les autres alias. À l’épuisement des tentatives, seule la cellule concernée devient `INFRA_ERROR` et les autres collectes continuent. Sous `campaign-lock/v6`, un `HTTP_NON_RETRYABLE` ou `API_ERROR` sans artefact accepté ferme en `INFRA_ERROR/PROVIDER_ROUTE_UNAVAILABLE` les slots non démarrés du même alias sous la même route ; les appels déjà en vol sont drainés sans reprise et les autres alias continuent. Les locks v5 et antérieurs conservent leur comportement historique de `HOLD` global. Un appel en vol incertain est réconcilié ou place la campagne en `HOLD` ; il n’est jamais renvoyé par supposition. Une réponse tardive ne remplace jamais un artefact déjà accepté.

- **R-004. Attendu et observé séparés.** Le lock conserve modèle, backend et provider attendus. Le reçu lie cette configuration attendue au modèle et au provider observés ainsi qu’aux informations opaques. Une dimension obligatoire inconnue au pré-vol rend la configuration `INELIGIBLE`. Le statut fermé `not_disclosed` autorisé par R-003a est une information de divulgation résolue, jamais une valeur physique connue. Une identité servie divergente donne `FAILED_NON_RETRYABLE` et place la campagne en `HOLD`. La campagne est alors abandonnée, avec les cellules concernées fermées en `INFRA_ERROR`, ou remplacée par une nouvelle campagne et un nouveau lock. Aucun pin ne change dans la campagne existante.

- **R-005. Régimes de confidentialité.** Chaque collecte déclare le régime demandé et le reçu le conserve.
  - **R-005a, retenu.** Une route qui ne peut satisfaire la politique de données requise est `INELIGIBLE`. Une politique inconnue n’est jamais présumée conforme.
  - **R-005b, exposé.** Une carte destinée à être publique peut utiliser une route autorisée par son contrat si la politique demandée et l’identité servie sont consignées.

  L’outillage échoue du côté sûr : une carte retenue ne peut pas être exécutée sous un régime exposé.

- **R-006. Score par code.** Le score est produit et modifié uniquement par du code déterministe. L’humain conçoit, calibre, audite et approuve l’instrument ; il ne corrige aucune note à la main.

- **R-007. Classements situés.** Chaque axe qualifié produit son classement. Les domaines et les pistes `direct` et `agent` ne sont jamais fusionnés dans un score global. Un profil doit être préenregistré et joindre explicitement, pour chaque axe, le couple `(measurement_context_hash, execution_manifest_hash)`. Une fusion silencieuse par alias est interdite.

- **R-008. Aucun changement silencieux.** Toute modification du contenu visible par le candidat incrémente `task-vN`. Toute modification de l’instrument, de l’oracle, des prédicats, seuils, actifs juge ou témoins qualifiants incrémente `verify-vM`. N et M sont des compteurs entiers indépendants, pas des versions sémantiques.

- **R-009. Côté juge séparé.** Oracle, vérificateur, témoins, tests cachés, seuils et points d’évaluation ne sont jamais envoyés au candidat. Leur publication éventuelle suit R-017 et ne modifie jamais cette frontière pendant une collecte.

## 2. Collecte, notation et traçabilité

- **R-010. Vérificateur aveugle.** Le vérificateur reçoit les octets candidats sous une identité et un chemin neutres. Il ne lit ni alias, ni chemin du run d’origine, ni reçu de collecte, ni métadonnée identifiant la configuration. Le contrôle de conformité est un composant distinct.

- **R-011. Prédicat fermé.** Chaque point noté se décide par exécution, comptage, motif, citation exacte, contrainte vérifiée ou écart numérique à un oracle déterministe.

- **R-012. Pas de jugement ouvert noté.** Style, esthétique, préférence, pertinence ouverte ou causalité non instrumentée peuvent être observés, mais ne reçoivent aucun score mécanique.

- **R-013. Machine d’état totale.** Chaque objet termine dans un état ou une décision de son niveau :

  | Niveau | États ou décisions |
  |---|---|
  | Tentative | `COMPLETE`, `FAILED_RETRYABLE`, `FAILED_NON_RETRYABLE` |
  | Collecte | `COLLECTED`, `INELIGIBLE`, `INFRA_ERROR`, `MISSING` |
  | Unité de score | `SCORED`, `UNKNOWN`, `INELIGIBLE`, `INFRA_ERROR`, `MISSING` |
  | Contrôle opérateur | `HOLD`, distinct d’un résultat de mesure |
  | Panel | événement `RETIRE`, sans mutation du lock |
  | Résultat d’axe | valide ou provisoire |
  | Profil | valide, non couvert, périmé ou abstention |
  | Campagne | complète ou incomplète |
  | HTML | conteneur multi-statut reflétant les objets sous-jacents |

  Une collecte devient `COLLECTED` dès que l’adaptateur matérialise les octets du candidat, même si le contenu candidat est vide ou fonctionnellement invalide. Un corps HTTP vide ne contient aucun artefact candidat. Un refus matérialisé est noté comme sortie. Une erreur de vérificateur ne provoque jamais de recollecte. Chaque état autre que `SCORED`, et chaque résultat `SCORED` non réussi, porte un `cause_code` fermé.

- **R-013a. Retrait du panel.** `RETIRE` est un événement motivé, daté et indépendant du résultat observé. Il ne modifie ni le lock, ni les octets déjà collectés. Les collectes restantes sont fermées selon leur état réel ; aucune cellule n’est effacée pour améliorer un classement.

- **R-014. Un défaut observable par item.** Chaque item mesure un seul effet. Une carte trop ambiguë est simplifiée, séparée en axes ou retirée. Aucun nombre universel d’items n’est imposé.

- **R-015. Versions, empreintes et reçus.** Le protocole reste `benchmark-lab-x/protocol/v2`. Les contrats cibles de hash sont `execution-manifest/v4`, `campaign-lock/v4`, `campaign-lock/v6`, `measurement-context/v3`, `acquisition-inventory/v1` et `continuation-draft/v1`, définis par des listes positives fermées dans l’ARD. `campaign-lock/v5` reste lisible avec sa sémantique historique ; `campaign-lock/v6` lie en plus `failure-scope/v1`. Les autres schémas historiques gardent leur signification. Le snapshot `route-preflight-snapshot/v3` lie chaque route aux métadonnées publiques datées et hachées qui ont soutenu sa sélection. Toute approbation B0-09 vise le chemin et le SHA-256 du snapshot proposé exact ; le snapshot approuvé et le lock conservent cette liaison. Le reçu de collecte lie lock, payload, configuration attendue, identité servie, réponse, usage, coût, durée et cause ; il ne porte aucun score. Une réponse OpenRouter `HTTP_429`, `HTTP_502`, `HTTP_NON_RETRYABLE` ou `API_ERROR` reçue avant tout artefact candidat porte un coût connu nul conformément à la politique publique de facturation des tentatives échouées. Les reçus historiques qui conservaient une borne maximale ne sont pas réécrits : l’inventaire les réconcilie à zéro en liant leur chemin, leur SHA-256 et la preuve publique appliquée. Un transport sans réponse ou une facturation non démontrée reste inconnu et place le registre en `HOLD`. Le reçu de score, produit par axe, lie `measurement_context_hash`, `verify_hash`, environnement, prédicats et résultat. L’inventaire d’une série référence chaque acquisition dans son lock source, refuse les doublons et ne copie ni ne réécrit les reçus. Un lot de continuation contient uniquement les slots encore absents. Son commit de collecte peut évoluer sans modifier le commit d’instrument ; tâche, prompt, prédicats, `verify_hash`, actifs juge et cellules reprises restent alors identiques au lock de référence.

- **R-016. Calibrage indépendant et couverture.** Chaque prédicat possède au moins un témoin positif et un témoin négatif produits sans accès au vérificateur. Provenance, consignes, attente et empreintes sont consignées. Les mêmes octets témoins et leur reçu peuvent être réutilisés entre plusieurs lots lorsque tâche, prompt, prédicats, `verify_hash`, provenance et environnement de mesure restent identiques. Le `campaign_lock_hash` du reçu documente son lot de production ; il ne définit pas la compatibilité de l’instrument. Chaque nouveau `verify_hash` ou environnement exige un nouveau reçu de couverture. Un changement de `verify_hash` impose la renotation de tous les axes concernés.

- **R-017. Cycle de vie des actifs exposés.** Les actifs juge d’une carte exposée restent sous embargo avant la première publication. Le premier résultat publie un paquet rejouable comprenant le contrat et les actifs nécessaires. Les campagnes ultérieures sont marquées `exposées` et déclarent le risque de contamination. Aucune absence de connaissance préalable n’est revendiquée. Chaque carte préenregistre sa politique d’exposition, de renouvellement et de retrait ; aucun plafond universel de campagnes n’est imposé.

- **R-018. Structure explicite.** Une carte définit ses axes, prédicats, paliers ou verdicts, ordre, prérequis, run design, règle d’agrégation et limites. Un niveau à préfixe exige tous les paliers précédents ; une checklist décide ses items indépendamment.

## 3. Agrégation, audit et publication

- **R-019. Agrégation du protocole v2.** Pour un axe soumis au plan de répétition du même stimulus, le protocole v2 planifie six runs et retient le quatrième meilleur. Une checklist binaire retient `PASS` si au moins quatre runs sont `PASS`, sinon `FAIL`. Une carte à paliers retient le niveau franchi dans au moins quatre runs sur six. Les six valeurs et les ex æquo sont publiés. Une carte justifiée par un déterminisme de bout en bout peut n’utiliser qu’un run, sans revendiquer de répétabilité. Une série d’instances distinctes préenregistre sa propre agrégation et parle de robustesse sur instances.

- **R-020. Classement par axe.** Un classement est valide uniquement si toutes les unités requises de l’axe sont `SCORED` et si son audit est accepté. Les configurations `INELIGIBLE` apparaissent hors classement. Un `UNKNOWN`, `INFRA_ERROR` ou `MISSING` maintient seulement l’axe concerné au statut provisoire. Une page peut réunir des axes valides et provisoires sans revendiquer un statut global trompeur.

- **R-021. Diagnostics séparés du score.** Coût, durée, dispersion, usage et jetons ne modifient jamais la note. Ils peuvent départager un profil uniquement si la contrainte et sa charge d’usage ont été préenregistrées.

- **R-022. Catalogue noté fermé.** Une carte entre au catalogue noté seulement lorsque tous ses points comptés sont décidables par code. Une carte à jugement ouvert reste exploratoire.

- **R-023. Mécanisme discriminant explicite.** Avant collecte, la carte décrit le bon chemin, les échecs attendus, les conséquences d’erreur et ce que chaque axe distingue. Une carte adversariale définit `trap_triggered` et préenregistre un critère de qualification ou de retrait justifié en collectes indépendantes. Aucun nombre universel de versions ou de runs n’est imposé.

- **R-024. Harnais avant candidat.** Un résultat aberrant bloque la validation jusqu’à examen du `finish_reason`, du payload, des paramètres, de la route, de l’adaptateur et du vérificateur. Un défaut du harnais est recherché avant d’attribuer la surprise au candidat.

- **R-025. Besoin de sortie déclaré.** La carte justifie son besoin de sortie ; la campagne résout et fige `max_tokens` avant appel. Il n’existe aucun plancher universel. Le budget ne change pas après observation. L’adaptateur normalise refus et troncature selon les signaux réellement disponibles, sans supposer une sémantique universelle des providers. Un artefact candidat présent dont le contenu est vide reste accepté et la notation décide de son échec fonctionnel. Un corps HTTP sans artefact candidat relève de R-003b.

- **R-026. Audit humain fondé sur le risque.** Avant audit, le plan fixe :
  - classes et frontières à examiner
  - anomalies et causes particulières
  - méthode aveugle de sélection
  - taille d’échantillon justifiée
  - conclusion limitée à cet échantillon

  L’auditeur voit la sortie et les preuves, jamais l’identité du candidat. Il décide si le résultat produit par le code décrit correctement ce qu’il observe. Il ne modifie aucune note. Une erreur de verdict ou de niveau invalide l’axe, impose une nouvelle `verify-vM` et une renotation.

- **R-027. Publication fail-closed par axe.** Le contrôle vérifie identités, empreintes, paramètres, états, audit et unités attendues avant validation d’un axe. Une page provisoire peut expliquer les manques. Aucun résultat invalide ou absent ne devient un chiffre publié.

- **R-028. Français comme langue de mesure.** Cartes, consignes, données d’entrée, documents, messages d’outillage, pages et sorties attendues destinés à un humain sont en français. Identifiants, clés machine, slugs, URL, littéraux d’API et messages bruts d’un fournisseur conservent leur forme nécessaire. Changer la langue d’une carte crée une nouvelle `task-vN`.

## 4. Extensions contrôlées

- **R-029. Exécution outillée isolée.** Cette règle s’applique seulement lorsqu’une carte exécute des outils. La configuration fixe outils, versions, permissions minimales et limites. L’environnement est synthétique, éphémère, sans secret, réseau refusé par défaut, quotas, arrêt d’urgence, journal complet et remise à zéro vérifiée. Aucune carte cyber ne vise un système réel. Une carte offensive exige en plus un modèle de menace approuvé et une décision humaine distincte.

- **R-030. Aucune carte auto-approuvée.** Une description utilisateur ou une génération automatique produit seulement un brouillon. Chaque contrainte est marquée `conservée`, `transformée`, `omise` ou `ambiguë`. Une omission ou ambiguïté importante bloque la qualification. Instrument, oracle, témoins indépendants, sécurité éventuelle et validation humaine précèdent toute collecte notée.
