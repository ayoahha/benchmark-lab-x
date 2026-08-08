# Plan consolidé - démo historique et classement V0 défendable

Date : 2026-08-07

Statut : plan uniquement. Aucun code, rejeu, appel payant, commit, push ou PR n'est autorisé par ce document.

## 0. Verdict et niveau de preuve

### Verdict

- **Tranche A, démo historique** : `GO SOUS CONDITIONS`.
- **Tranche B, classement V0 défendable** : `HOLD` jusqu'aux décisions de B0 et aux portes techniques B1 à B7.

`runs/2026-08-06-reference-v2` peut être montré comme archive diagnostique interne. Il ne peut pas être promu en V0, en page validée ou en base de sélection de modèle.

Une correction de présentation ne répare ni l'instrument, ni la conformité de route, ni le contexte de mesure. Le classement défendable viendra d'une nouvelle campagne sous de nouvelles versions.

### Provenance de l'avis externe

Avis transmis manuellement par Ayo le 2026-08-07, annoncé comme une réponse de GPT-5.6 Sol en effort Pro.

Niveau de preuve du modèle : **non confirmé localement**. Le wrapper Oracle n'a produit ni réponse ni preuve de sélection du modèle. L'avis reste consultatif. Les conclusions retenues ci-dessous ont été revérifiées contre les artefacts primaires.

### Base de preuve figée

| Artefact | SHA-256 au 2026-08-07 | Usage |
|---|---|---|
| `docs/PROMPT-REPRISE-GPT56.md` | `7988e447ca42e5f662bbdc3e79a5fd6de9c12b6672a06f059ab33ae0c6744495` | objectif et contraintes |
| `docs/RULES.md` | `4b790aae3ee69ce0ffc4f587bbb05f1ddf5cdfbf6e5dd26ee34e426ad8c2f011` | règles et jalons |
| `tasks/dev/pentagone-rotatif/task.md` | `d918a0d693feb6d497d1170f83982df3865303be128c1db81facd275d081c3e3` | contrat historique `task-v2` |
| `runs/2026-08-06-reference-v2/results-data.json` | `4185a4ab9b4512f93bae0b998a939de0eff01151c00a9c01c789b757b62eedfd` | résultats historiques |
| `runs/2026-08-06-reference-v2/routes.json` | `5feae661b3050916973c40ca7212fe13443c1ca87e9e6471b3cc2eda7deae468` | critère de route historique |
| `runs/2026-08-06-reference-v2/campaign.toml` | `6627752ba38268fe0837e63803fe12da3bb8287680daa66367198f5ca819c601` | plan et reprises historiques |
| `models.toml` | `000ae54f6cfae6a93bb898603f97f840062305fc36f0794d5b009eb18665d3ef` | libellés de présentation uniquement |

Les faits temporels ou de conformité de la tranche A viennent des artefacts de campagne, jamais du registre courant.

## 1. Invariants

1. `reference-v2` reste immuable : aucun reçu, score, état, niveau, frontière, tentative ou coût historique n'est modifié.
2. Le `niveau_retenu`, troisième meilleur des quatre runs selon R-019, reste inchangé pour `reference-v2`.
3. Aucun outil de collecte, notation, qualification ou audit n'est exécuté en tranche A.
4. Le rendu historique lit les artefacts existants. Il ne régénère pas `results-data.json`.
5. Kimi reste visible comme preuve historique. Sa réserve de route n'est ni masquée ni réparée rétroactivement.
6. Les termes « validé », « certifié », « meilleur modèle », « classement V0 » et « résultat décisionnel » sont interdits pour `reference-v2`.
7. Toute modification du contenu visible par le candidat, du vérificateur, du protocole ou du critère de mesure crée les versions et empreintes appropriées.
8. La page conserve les contraintes de lisibilité : aucune nouvelle colonne, aucun paragraphe sous le tableau, aucune bande de couleur.

## 2. Tranche A - démo historique honnête

### A1. Périmètre

But : présenter ce qui a été observé sous `task-v2`, `verify-v3` et `benchmark-lab-x/protocol/v1`, avec ses limites connues, sans décision de sélection.

Périmètre d'une future implémentation : couche de rendu seulement. Les entrées historiques restent en lecture seule.

Commandes interdites en tranche A :

- `tools/rapport_campagne.py`
- `tools/qualifier_temoins.py`
- `tools/audit_instrument.py`
- `tools/verifier_pentagone.py`
- tout lancement de Chromium ou Playwright
- tout collecteur ou lanceur de campagne

### A2. Statut visible

Le bandeau existant doit commencer par :

> Campagne historique diagnostique `2026-08-06-reference-v2`. Résultats immuables de `task-v2` et `verify-v3`. Instrument non qualifié, page non validée, blocage R-016. Présentation interne, provisoire et non décisionnelle. Aucun rejeu, aucune renotation, aucune correction des scores.

Le même bandeau, sans créer de paragraphe sous le tableau, doit résumer :

- budget de vérification de 180 s absent des consignes visibles
- causes basses hétérogènes
- écart Kimi au critère de route figé
- échelle nominale historique partiellement inaccessible
- 19 candidats, 76 runs retenus, 84 tentatives enregistrées, 83 prompts ayant atteint un fournisseur

### A3. Rangs de compétition

Le rang est calculé en mémoire dans le rendu :

```text
rang = 1 + nombre de candidats dont niveau_retenu est strictement supérieur
```

Le JSON historique ne reçoit aucun champ `rang`.

Contrôles attendus :

- `reference-gpt-5-6` et `opus-5-high`, niveau 20 : rang 4, puis rang 6
- `grok-4-5`, `deepseek-v4-pro` et `fable-5-xhigh`, niveau 14 : rang 8, puis rang 11
- les quatre candidats au niveau 10 : rang 14, puis rang 18

Dans un groupe ex æquo, l'ordre visuel suit l'ordre du plan de campagne. `niveau_indicatif` ne départage jamais les rangs.

### A4. Barres et plafond historique

Si les barres sont conservées, leur longueur vaut `niveau_retenu / 51` sur l'échelle nominale de `verify-v3`. Elle n'est ni une probabilité, ni un pourcentage de capacité.

Formulation exacte à intégrer au bandeau ou à l'infobulle générale :

> Le niveau 43 est le plafond observé. Les paliers 44 et 45 sont deux seuils de précision extrême non démontrés discriminants avec l'interface numérique historique. Les six paliers d'horizon long, placés ensuite dans l'échelle conjonctive, ne sont jamais atteints. Le niveau 43 ne prouve donc aucune tenue à 35, 55 ou 75 secondes.

Formulation interdite : « les paliers 44 à 51 sont tous sous l'ulp float64 ». Les six derniers sont des paliers d'horizon long rendus inaccessibles par l'ordre de l'échelle.

### A5. Chronologie et causes

La chronologie vient uniquement des objets de `$.runs` portant `tentative_retenue=true`, triés par le champ numérique `run`. `$.candidats[*].niveaux`, trié par performance, ne raconte jamais une chronologie.

Chaque infobulle affiche `r1` à `r4`, le niveau, la frontière et la cause lorsqu'elle existe.

Contrôles obligatoires :

- DeepSeek Flash : `r1=0` timeout 180 s, `r2=17`, `r3=1` à `A1_api_totale` sans timeout, `r4=21`
- Kimi : `r1=43`, `r2=0` timeout 180 s, `r3=13`, `r4=23`
- MiniMax : `r1=0` à `A0_page`, `r2=17`, `r3=11`, `r4=11`
- Mimo : `r1=10`, `r2=3`, `r3=11`, `r4=20`, aucun run à 0

Les deux timeouts restent historiquement enregistrés. La présentation précise que la borne était absente des consignes visibles et que son effet sur le score n'est pas réparé.

### A6. Kimi

La ligne Kimi porte la réserve :

> Écart au critère de route figé : les runs retenus sont épinglés sur `moonshotai` et servis par `Moonshot AI`, tandis que `routes.json` recommande `wafer`. Cette mention documente l'écart à R-003a et ne le répare pas.

La comparaison porte sur les identifiants canoniques de route, pas seulement sur les libellés d'affichage du provider. Le registre courant ne décide jamais de la conformité historique.

### A7. Tentatives et prompts

Trois compteurs distincts sont affichés :

- 76 runs attendus et retenus
- 84 tentatives enregistrées dans `$.runs`
- 83 prompts ayant atteint un fournisseur selon `$.cycle_de_vie.prompts_partis`

La tentative supplémentaire arrêtée avant fournisseur porte le motif `metadonnees_route_inatteignables`.

La divergence entre « une tentative par run » dans la carte et `tentatives_max=6` dans la campagne reste une divergence historique documentée, non réparée.

### A8. Témoins

Seule la formulation suivante est opposable :

> R-016 ouvert : les sept témoins historiques déclarent un producteur non aveugle au vérificateur. La couverture indépendante n'est pas démontrée et aucun reçu de couverture figé n'est consommé par cette page.

Ne pas afficher de niveau de couverture, de « podium calibré » ou de « témoins indépendants jusqu'au niveau 20 ».

### A9. Critères d'acceptation

La tranche A est `GO` seulement si :

1. les SHA-256 de `results-data.json`, `routes.json`, `campaign.toml`, `task.md` et `RULES.md` sont inchangés pendant la tranche ; le hash de `models.toml` ne sert qu'à figer le snapshot de libellés
2. aucun fichier sous `runs/2026-08-06-reference-v2/` n'est modifié
3. aucun outil interdit en A1 n'est exécuté
4. le statut A2 est visible avant le tableau
5. les compteurs 19, 76, 84 et 83 sont exacts et correctement nommés
6. les rangs suivent `niveau_retenu` seul
7. les chronologies et causes A5 sont exactes
8. Mimo n'est associé à aucun niveau 0
9. DeepSeek Flash r3 n'est pas présenté comme un timeout
10. la réserve Kimi est visible sans prétendre réparer la campagne
11. aucune couverture de témoins chiffrée n'est affichée
12. les barres sont explicitement nominales et historiques
13. les contraintes de lisibilité sont respectées
14. aucune phrase ne présente la page comme validée ou décisionnelle

### A10. Stop condition

`HOLD` immédiat si :

- produire la vue exige de relancer le rapporteur, le qualifier ou Chromium
- un nombre n'est pas traçable à un artefact figé
- le JSON historique devrait être enrichi ou réécrit
- les réserves ne tiennent pas dans le bandeau et les infobulles existants
- la démo doit servir à choisir un modèle

## 3. Tranche B - nouvelle campagne V0 défendable

### B0. Décisions préalables d'Ayo

La tranche B reste `HOLD` tant que ces décisions ne sont pas consignées :

| Décision | Recommandation minimale | Porte |
|---|---|---|
| Interface et float64 | conserver `[x, y]` en nombres JavaScript, retirer les seuils non discriminants | GO explicite |
| Horizons longs | les publier dans un axe séparé, non bloqué par la précision à 24 s | GO explicite |
| Temps | le retirer du score de correction, le garder comme diagnostic ou axe d'efficacité | GO explicite |
| Axes publiés | API, déterminisme, confinement, précision à 24 s, horizons longs ; efficacité séparée | GO explicite |
| Scalaire | troisième meilleur sur quatre par axe, libellé littéral, ex æquo conservés ; aucun scalaire global | GO explicite |
| Nombre de runs | conserver quatre pour la V0 ou autoriser une hausse chiffrée et budgétée | GO explicite |
| Tentatives | un seul résultat scoreable ; reprises infra bornées avant `SCORED` seulement | borne à fixer |
| Routes | lock résolu utilisé comme source directe d'exécution | GO explicite |
| Dépense | plafond incluant toutes les tentatives payantes | montant à fixer |
| Nouvelle campagne | appels payants séparément autorisés | GO distinct ultérieur |

Ces recommandations ne deviennent pas des décisions par leur présence dans ce plan.

### B1. Versions et contrat

Selon les décisions B0, créer au minimum :

- `task-v3` si le budget, les consignes ou le format de sortie changent
- `verify-v4` si les axes, paliers, seuils, ordre ou traitement du timeout changent
- `benchmark-lab-x/protocol/v2` si les causes, tentatives, agrégations ou portes changent
- un nouveau `measurement_context_hash`
- de nouveaux `execution_manifest_hash`
- un nouveau dossier de campagne

Si plusieurs axes restent dans une même carte, leur règle d'agrégation doit être couverte explicitement par R-019 et R-020 avant collecte. Sinon, chaque axe devient une carte séparée et leur éventuel profil suit R-007.

`reference-v2` ne reçoit aucune nouvelle sortie.

Porte : `HOLD` pour tout changement silencieux ou toute empreinte non expliquée.

### B2. Instrument corrigé

1. Rendre chaque axe interprétable séparément.
2. Retirer ou recalibrer les deux seuils de précision non démontrés discriminants.
3. Rendre les horizons 35, 55 et 75 s évaluables indépendamment de ces seuils.
4. Ajouter des `cause_code` mécaniques distincts pour page absente, API invalide, non-déterminisme, dépendance à l'ordre, timeout, confinement et seuil de précision.
5. Ne pas créer un nouvel état terminal hors R-013 sans modifier et versionner R-013 et le protocole.
6. Si le timeout reste un garde-fou d'instrument, ne pas le convertir en niveau 0 de correction. La correction reste non observée et porte `UNKNOWN` selon R-013 ; l'efficacité porte le diagnostic.
7. Nommer chaque scalaire par ce qu'il mesure, par exemple « niveau franchi dans au moins trois runs sur quatre ».

Vérification : fixtures locales pour page correcte rapide, correcte lente, bloquante, absente, API invalide, ordre dépendant, trajectoire imprécise et sortie de confinement.

Porte : `GO` seulement si deux mécanismes différents ne partagent plus une cause fausse et si chaque axe mesure un construit unique.

### B3. Gel des routes et reprises

Créer avant le premier appel un lock résolu par candidat contenant modèle, backend, route canonique, provider épinglé, effort, paramètres résolus et omis, résultat du critère de route et empreintes.

Le collecteur lit ce lock comme source d'exécution. Il ne résout pas de nouveau l'alias dans `models.toml` lors d'une reprise.

Règle de reprise :

- un seul résultat scoreable par run
- aucune reprise après `SCORED`
- reprises avant `SCORED` uniquement pour une liste préenregistrée de causes d'infrastructure
- nombre maximal identique dans la carte, le protocole et `campaign.toml`
- route différente = candidat différent, jamais reprise
- coût de toutes les tentatives payantes compté

Vérification : modification d'un alias du panel après gel, modification d'un alias hors panel, reprise après redémarrage, provider servi différent et route indisponible.

Porte : `HOLD` si le collecteur consulte encore le registre courant pour un candidat gelé.

### B4. Témoins indépendants et reçu figé

R-016 est due en V1 dans la matrice. Son absence n'est pas appelée défaut d'automatisation pré-V0. Elle reste toutefois une porte de publication imposée par la carte et le niveau de preuve visé.

Pour le nouvel instrument :

1. produire, sans accès au vérificateur, au moins un témoin positif et un témoin négatif pour chaque prédicat
2. consigner producteur, consignes, provenance, attente et hashes
3. produire un reçu de couverture lié à `task_version`, `prompt_hash`, `verify_version`, `verify_hash`, environnement et hashes des témoins
4. faire consommer ce reçu par le rapporteur sans relancer Chromium
5. échouer du côté sûr si le reçu est absent, incomplet ou périmé

Porte : `HOLD` au premier prédicat sans preuve bilatérale ou si le rapporteur doit rejouer un témoin.

### B5. Préflight sans appel payant

Avant toute campagne :

- exécuter uniquement les fixtures locales et les témoins autorisés
- vérifier déterminisme, monotonie et atteignabilité de chaque palier
- vérifier les causes structurées et les compteurs
- vérifier le lock et les reprises
- vérifier l'absence de processus Chromium orphelin
- générer la page depuis des reçus figés
- figer toutes les empreintes

Porte : `HOLD` au premier échec, processus orphelin, palier non calibré ou hash instable.

### B6. Nouvelle collecte payante

Préconditions cumulatives : B0 approuvé, B1 à B5 en `GO`, plafond de dépense écrit, autorisation payante explicite d'Ayo.

Pendant la campagne : aucune route de repli, aucun changement de contexte, aucun dépassement du plafond, aucune tentative après `SCORED`.

Porte : `HOLD` immédiat sur route servie différente, lock modifié, budget dépassé ou contexte divergent.

### B7. Notation, audit et publication

1. noter en aveugle sous le nouvel instrument
2. agréger selon les règles préenregistrées de chaque axe
3. conserver les ex æquo sans départage post-observation
4. exécuter l'audit humain R-026 sur la nouvelle campagne, pas sur l'instrument historique déjà reconnu défectueux
5. produire un nouveau JSON et une nouvelle page
6. exiger `instrument_qualifie=true`, `page_validee=true` et aucun blocage de conformité

R-020 et R-026 sont dues en V1 dans la matrice. Elles sont néanmoins appliquées ici comme portes de publication du classement défendable, conformément à la carte et à l'objectif produit.

### B8. Critère final d'explication des positions

Pour chaque paire de positions adjacentes non ex æquo, le dossier de campagne doit identifier mécaniquement :

1. l'axe qui les sépare
2. les prédicats ou paliers concernés
3. la distribution complète des runs planifiés
4. la preuve que les seuils sont atteignables et calibrés
5. la preuve du modèle, de la route et de l'effort gelés
6. l'absence de timeout caché
7. l'absence de reprise non conforme
8. l'absence de départage post-observation

Si cette preuve manque, les candidats restent ex æquo ou la publication reste `HOLD`.

## 4. Ordre d'exécution

1. Approuver ou refuser la tranche A comme démo strictement interne.
2. Implémenter A uniquement dans la couche de rendu, après vérification de l'absence de conflit avec les changements en cours.
3. Vérifier A9 et arrêter à la première condition A10.
4. Consigner séparément les décisions B0.
5. N'ouvrir la tranche B qu'après les dix décisions B0.
6. Ne lancer une nouvelle campagne qu'après les portes B1 à B5 et un GO payant distinct.

## 5. Hors périmètre de cette révision du plan

- implémentation de la tranche A ou B
- modification de `docs/RULES.md`, `docs/PRD.md`, `docs/ARD.md` ou de la carte
- exécution d'un témoin ou d'un vérificateur
- renotation ou rejeu historique
- appel API payant
- commit, push, PR ou publication
