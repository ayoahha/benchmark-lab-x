---
style_gate: pass
---

# Outillage local de Benchmark Lab-X

Cet outil Python utilise la bibliothèque standard. Il prépare une campagne scellée, exécute une fois chaque configuration après autorité S9, produit une revue aveugle, puis construit hors ligne une Salle de décision après décisions et autorité S10.

Il utilise le scénario et le panel figés de [campaign.json](campaign.json), Pi `0.84.4`, un plafond historique de 0,50 USD et des fichiers privés sous `runs/`. Ces paramètres appartiennent à ce scénario ; ils ne définissent pas les tâches, le panel ni les budgets du [jalon produit](../docs/PRD.md#51-périmètre-010). La revue et la construction refusent un panel incomplet ; route et effort non observés restent `INCONNU`.

Les commandes ci-dessous décrivent une séquence : obtenir l’autorité d’acquisition avant `collect`, puis les décisions et l’autorité de construction avant `build`. Elles ne constituent pas un script à lancer d’un bloc. Le lancement d’une campagne réelle exige des identités actuellement vérifiées ; le panel historique ne prouve pas la disponibilité des modèles.

Depuis la racine du dépôt, sur macOS, avec Python 3 et le binaire Pi requis :

```bash
mkdir -p -m 700 runs
python3 -B -m benchmark_lab_x prepare --run-dir runs/ma-campagne --pi /chemin/reel/vers/pi
python3 -B -m benchmark_lab_x collect --run-dir runs/ma-campagne --authority /chemin/authorization-s9.json
python3 -B -m benchmark_lab_x review --run-dir runs/ma-campagne
python3 -B -m benchmark_lab_x build --run-dir runs/ma-campagne --decisions /chemin/decisions.json --authority /chemin/authorization-s10.json
python3 -B -m benchmark_lab_x show --run-dir runs/ma-campagne
```

`show` vérifie le sceau final et ouvre la page existante sans la régénérer. L’alternative directe est `open runs/ma-campagne/index.html`.

La page identifie la tâche par un brief (titre public, contexte, objectif, décision éclairée) et par le résultat attendu contractuel. Pour une future campagne, ce brief se fige avant exécution dans `campaign.json` sous la clé `brief` (exactement `title`, `context`, `objective`, `decision`) et entre ainsi dans l’empreinte du contrat ; le résultat attendu reste `expected_result`, unique source contractuelle, et un brief qui porterait `expected` est refusé. Deux replis existent quand ce champ manque : le scénario historique `quote-thread-summary` dispose d’un brief de présentation propre, rédigé après coup, signalé comme tel sur la page et relié à aucune empreinte de source ; toute autre tâche retombe sur son identifiant et le résultat attendu du contrat, avec les autres champs signalés non documentés.

Après une évolution du rendu, `present` construit une nouvelle présentation locale depuis un run final scellé, sans modifier ses résultats ni relancer de candidat :

```bash
python3 -B -m benchmark_lab_x present --source-run runs/ma-campagne --run-dir runs/ma-presentation
python3 -B -m benchmark_lab_x show --run-dir runs/ma-presentation
```

## Témoins d’autorité

Les schémas S9 et S10 sont vérifiés strictement. Les autorités restent externes à `prepare` et doivent utiliser les empreintes du run concerné.

S9 :

```json
{
  "schema": "benchmark-lab-x-s9-authorization-1",
  "effect": "candidate_calls_and_spend_s9",
  "authority_id": "TEMOIN-TEMPORAIRE-S9",
  "run": "runs/ma-campagne",
  "seal_sha256": "<sha256 seal.json>",
  "contract_sha256": "<sources.campaign.json du sceau>",
  "panel_sha256": "<artifacts.panel.json du sceau>",
  "pi": {
    "binary_sha256": "<pi.sha256 du sceau>",
    "version": "0.84.4",
    "settings_sha256": "<artifacts.settings.json du sceau>",
    "models_sha256": "<artifacts.models.json du sceau>"
  },
  "budget": {
    "currency": "USD",
    "cap": 0.5,
    "price_date": "<date>",
    "price_source": "<source>",
    "forecasts": {"C1": 0.1, "C2": 0.1, "C3": 0.1}
  }
}
```

Les décisions contiennent `accepted: true`, l’empreinte exacte de `review.json`, une décision par identifiant aveugle et les neuf constats `O1` à `O6`, `E1` à `E3`. Chaque constat possède un texte `finding` et une référence `evidence` parmi `blind-copy`, `receipt`, `incident`. `S1` et `S2` valent `acceptable` ou `excellent` uniquement pour `SATISFAIT`.

S10 lie le run, `seal.json`, `review.json` et les octets exacts des décisions :

```json
{
  "schema": "benchmark-lab-x-s10-authorization-1",
  "effect": "product_execution_and_acceptance_s10",
  "authority_id": "TEMOIN-TEMPORAIRE-S10-DISTINCT",
  "run": "runs/ma-campagne",
  "seal_sha256": "<sha256 seal.json>",
  "review_sha256": "<sha256 review.json>",
  "decisions_sha256": "<sha256 du fichier decisions.json externe>"
}
```

Ces témoins documentent le format. Ils n’accordent aucune autorité réelle.

## Compatibilité et intégrité

La commande courante est `python3 -B -m benchmark_lab_x`. Les nouveaux enregistrements utilisent le préfixe de schéma `benchmark-lab-x-`, suivi de leur objet et de leur version de format. Les exemples d’autorité ci-dessus correspondent à ces formats.

Le contrat figé dans `campaign.json`, les données d’entrée et la carte du scénario conservent leurs octets et identifiants historiques. Les lecteurs `show` et `present` reconnaissent explicitement les anciens formats de résultats et de sceaux. `present` copie les résultats à l’identique dans une présentation distincte et conserve le lien au sceau source ; il ne convertit pas une campagne et ne change aucun verdict.

Une préparation antérieure au changement de moteur n’est pas réutilisable pour acquérir, revoir ou construire : ses empreintes de sources ne correspondent plus. Il faut une nouvelle préparation et les autorités correspondantes. Aucun ancien reçu ou témoin d’autorité n’est converti automatiquement. Cette migration de noms ne constitue pas la livraison du périmètre produit.

Le workflow [GitHub Pages](../.github/workflows/pages.yml) publie `pages/` lors des changements configurés sur `main`. Construire une page locale et l’intégrer dans cette publication sont deux actions d’autorités distinctes.

## Interfaces locales du service Linux en construction

Le module `benchmark_lab_x.runtime` fournit une initialisation privée, la vérification de SQLite et des pièces, la maintenance, une sauvegarde cohérente et une restauration vers un nouvel emplacement. Ces interfaces sont distinctes du moteur historique ci-dessus. Les processus web et exécuteur sont fournis ci-dessous. Le candidat local ajoute le parcours fictif S2 décrit plus bas. Les appels assistés réels et le traitement des campagnes restent à construire.

Avec Python 3.12 ou supérieur, le répertoire parent des données doit exister. L’initialisation crée son emplacement privé ou utilise le répertoire vide préparé par Ansible sous le compte de service. Elle refuse tout emplacement contenant déjà des données :

```sh
python3 -B -m benchmark_lab_x.runtime initialize --data /chemin/prive/benchmark
python3 -B -m benchmark_lab_x.runtime verify --data /chemin/prive/benchmark
python3 -B -m benchmark_lab_x.runtime status --data /chemin/prive/benchmark
```

Ces commandes n’émettent aucun appel modèle. Les pièces et les révisions de dossier sont immuables. Une empreinte divergente, une pièce orpheline, une référence dangereuse ou un schéma inconnu provoque un refus. La bibliothèque S1 conserve les montants en texte décimal exact, les intentions, les réservations et les reçus. Elle persiste l’état `EMISSION_POSSIBLE` avant le transport. Elle ne fournit pas encore le transport ni l’interface publique d’autorisation.

Le runtime ne possède aucun transport réel. Sur une base S1 seule, `admission` reste faux. L’extension explicite S2 permet une admission opérateur ; `maintenance` la ferme durablement. Même avec cette admission configurée, l’absence de transport interdit tout appel. `quiescence` et `backup` refusent les opérations S1 encore en `EMISSION_POSSIBLE`. Après arrêt du processus, les effets inconnus sont conservés en `AMBIGUOUS` ; ils restent sauvegardables et bloquent les nouveaux appels dépendants dans S1 :

```sh
python3 -B -m benchmark_lab_x.runtime maintenance --data /chemin/prive/benchmark
python3 -B -m benchmark_lab_x.runtime quiescence --data /chemin/prive/benchmark
python3 -B -m benchmark_lab_x.runtime backup --data /chemin/prive/benchmark --destination /chemin/prive/sauvegarde-neuve
python3 -B -m benchmark_lab_x.runtime verify-backup --data /chemin/prive/sauvegarde-neuve
python3 -B -m benchmark_lab_x.runtime restore --data /chemin/prive/sauvegarde-neuve --destination /chemin/prive/restauration-neuve
```

La sauvegarde bloque les écrivains SQLite pendant la copie des pièces et vérifie leurs liens. La restauration préserve la source et toute cible existante. Elle crée le marqueur privé `restore.json`, conservé par les sauvegardes suivantes et exposé par `restore_pending`. Aucun effacement ni reprise n’est fourni : le rapprochement des effets postérieurs à la sauvegarde doit être réalisé avant toute future ouverture des appels. Une copie de données vérifiée ne prouve pas la restauration d’un service Linux ni une récupération PBS.

`tools/build_runtime.py` construit une archive déterministe depuis les seuls fichiers suivis d’un commit complet. Il ignore les modifications du worktree et refuse une source dépourvue des interfaces runtime. La sortie JSON relie le commit, l’arbre, les blobs Git et l’empreinte de l’archive. Le build n’installe aucune dépendance et n’exécute pas la source construite :

```sh
python3 tools/build_runtime.py --source <commit-produit-complet> --output /chemin/benchmark-runtime.tar.gz
```

Le reçu décrit la construction effectuée ; son authenticité doit être vérifiée depuis le job ou l’opérateur identifié. L’archive utilise le format `release.json` du candidat infra. Elle inclut les deux processus, leur commande et le stockage S1 ; le build refuse une archive sans ces composants. Aucun tag de livraison 0.1.0 n’est créé par ces interfaces.

Les commandes `benchmark-runtime web --public … --socket …` et
`benchmark-runtime executor --data … --socket …` fournissent les processus
Linux. Le web expose `/healthz` et `/readyz` sans appel modèle ; le second contrôle
interroge l'exécuteur par socket Unix et vérifie le stockage. Au démarrage,
l'exécuteur conserve les émissions S1 sans reçu en `AMBIGUOUS`, avec leur
réservation et un motif d'interruption. Les campagnes locales S4 utilisent le travailleur explicite décrit ci-dessous ; ce processus ne reprend aucune file candidate et ne fournit pas S5.

En dehors de `/preparation`, le web sert une projection nommée par l'empreinte de son manifeste
`publication.json`, sélectionnée par `public/active.json`. Chaque fichier servi
est vérifié ; sans publication vérifiée, la racine répond 503. Ce mécanisme ne
publie aucun dossier du parcours privé S2 et ne fournit pas S6. Les deux processus, leur
arrêt et leur redémarrage sont testés avec de vraies sockets locales ; la preuve
de déploiement Linux reste distincte.

Le schéma S1 reste en version 1 avec ses contraintes exactes. Le premier candidat
de la PR #197 possédait un autre schéma portant aussi le numéro 1 ; il est refusé
sans conversion ni réécriture. Un déploiement sur des données de ce candidat
exige une décision distincte de migration ou d'initialisation dans un nouvel
emplacement, en préservant la base d'origine. Cette intégration ne migre aucune
donnée et ne déploie aucun service.

## Parcours fictif de préparation S2

Le module fournit `/preparation` : saisie du besoin, clarification, consultation des pièces, correction et validation du dossier, de sa révision et de l’empreinte exacte du paquet. Ce parcours utilise les services locaux et un transport fictif de test. L’assistant réel, l’ouverture du service et la publication gardent leurs qualifications et autorités distinctes.

L’exécuteur existant porte les sessions et les opérations ; le web relaie les actions par sa socket Unix et rend des formulaires HTML natifs, sans script ni dépendance ajoutée. Un GET ne lance aucun travail. Après un envoi, le lien vers le dossier permet de consulter l’attente puis le résultat. Les erreurs de révision imposent de consulter la version courante. Les anciennes révisions, pièces et validations restent consultables ; tout nouveau paquet exige un nouvel accord. Le besoin et les réponses restent dans le payload S1, les corrections dans les actions attribuées. Les paramètres fictifs ne deviennent pas des accords. La validation du besoin ne qualifie pas la référence et n’approuve aucun contrat, appel, budget ou publication.

Le cookie `benchmark_session` est opaque, `HttpOnly`, `Secure`, `SameSite=Strict`, `Path=/preparation`, sans `Domain`, `Expires` ou `Max-Age`. Le stockage ne conserve que son SHA-256 et une identité interne. Le même navigateur retrouve ses dossiers tant qu’il conserve ce cookie ; sa survie à la fermeture n’est pas garantie. Perdre le cookie fait perdre l’accès sans effacer les dossiers. Aucun compte, durée de conservation ou récupération n’est ajouté. Chaque action et pièce exige sa session propriétaire ; les POST exigent aussi le jeton CSRF. Les champs d’autorité ne sont pas acceptés dans les formulaires. Les pièces sont du texte inerte, et la référence privée de jugement reste hors du paquet demandeur/candidat.

L’initialisation suivante est une opération locale explicite sur une base S1 intégrée neuve, sans données métier ni pièces résiduelles. Elle refuse une base S1 peuplée, une extension partielle, un schéma inconnu et le schéma distinct de #197 :

```sh
python3 -B -m benchmark_lab_x.runtime initialize-preparation --data /chemin/prive/benchmark
```

Elle ajoute les six tables identifiées `benchmark-lab-x/preparation/v1`, dans une seule transaction, avec admission fermée. Sur une extension déjà exacte, elle ne réécrit rien. `user_version=1` et les tables S1 restent inchangés. Le lecteur courant conserve la lecture des deux formes S1 ; les lecteurs S1 antérieurs refusent les tables S2 supplémentaires. Aucune migration ou compatibilité inverse n’est annoncée. Sauvegarde, restauration et vérification comprennent les jointures S2 et les empreintes des paquets.

L’opérateur peut enregistrer une admission depuis un fichier privé contenant exactement `authority_id`, `budget_id`, `reserve_amount` (texte décimal) et `requested_configuration` (objet non vide). Le budget S1 doit déjà exister ; cette commande ne crée pas d’enveloppe :

```sh
python3 -B -m benchmark_lab_x.runtime admit-preparation --data /chemin/prive/benchmark --authority /chemin/prive/autorite.json
```

Cette commande ne fournit aucun transport. Le seul point d’injection est `serve_executor(data, socket_path, source, *, transport=None)` ; seul le lanceur de test fournit la fonction fictive `transport(operation, request)`. Aucun paramètre HTTP, fichier utilisateur ou variable d’environnement ne peut la sélectionner. La valeur par défaut refuse tout appel. Les valeurs fictives des tests ne prouvent aucun coût réel : coûts réels et tarifs de l’implémentation sur abonnement restent inconnus, `UNMEASURED`.

L’action, son contexte exact, l’intention S1 et la réserve sont persistés avant accusé de réception. L’admission et le marqueur de restauration sont revérifiés dans la transaction qui précède l’émission. Le travailleur possède sa connexion SQLite et laisse le gestionnaire de santé disponible. Un doublon aux mêmes données retrouve son opération ; une identité réutilisée avec un autre contenu est refusée. Un reçu publié conserve les coûts sourcés, y compris `UNKNOWN`, puis les pièces vérifiées et le nouveau pointeur deviennent visibles ensemble. Si le reçu S1 est valide mais le résultat applicatif inutilisable, le reçu et le coût originaux sont conservés avec une révision suspendue et l’admission fermée, dans une seule transaction. Aucun paquet ni accord ne sont inventés. Un effet sans reçu S1 valide reste ambigu ; une interruption ne relance aucun travail, même une intention jamais émise. Démarrage, maintenance et restauration ferment l’admission. Le marqueur `restore_pending` ne peut être supprimé par le navigateur ou `admit-preparation`.

L’API négocie JSON avec `Accept: application/json`. Ses routes sont :

| Méthode | Route | Effet |
|---|---|---|
| GET | `/preparation` | Session, CSRF et liste des dossiers propres |
| POST | `/preparation/dossiers` | Brouillon et opération réservée, réponse 202 |
| GET | `/preparation/dossiers/{id}` | Vue courante, attente ou suspension |
| GET | `/preparation/dossiers/{id}/revisions/{n}` | Révision exacte conservée |
| POST | `/preparation/dossiers/{id}/messages` | Clarification ou correction depuis la révision courante |
| POST | `/preparation/dossiers/{id}/validation` | Accord lié au dossier, à la révision et à `package_sha256` |
| GET | `/preparation/dossiers/{id}/revisions/{n}/pieces/{piece_id}` | Octets vérifiés d’une pièce candidate appartenant au paquet |

Les requêtes JSON et formulaires portent les mêmes champs. Une création porte `dossier_id`, `action_id`, `request`, `csrf_token` ; un message porte `action_id`, `revision` (entier JSON), `kind` (`clarify` ou `correct`), `message`, `csrf_token` ; une validation porte `dossier_id`, `revision`, `package_sha256`, `csrf_token`. Les champs supplémentaires sont refusés. Une soumission ne transforme pas son texte en autorité opérateur.

Les contrôles S2 de publication du paquet portent sur sa structure, les jointures, la relecture des pièces et leurs empreintes. À eux seuls, ils laissent la justesse métier de la référence NON VÉRIFIÉ et `qualified` faux. L’extension locale S3 ci-dessous conserve une qualification distincte. Les déclarations de limites et les demandes de clarification sont celles du transport fictif attribué ; aucun assistant réel n’a été évalué.

La commande CI est `uv run --with requests --with mpmath==1.3.0 python -m unittest discover -s tests` : 870 tests passent sur macOS pour le candidat corrigé. Elle exclut `benchmark_lab_x/test_demo.py`, dont les 69 tests ont été exécutés séparément sur macOS. Les huit parcours HTTP avec vrais processus Web et exécuteur locaux passent également. Les transports sont entièrement fictifs ; ces preuves ne qualifient aucun assistant réel.

La vérification manuelle du 7 septembre 2026 utilise macOS 27.0 (26A5425a) et Chrome 152.0.7977.83 installé. Saisie, clarification, consultation de la pièce textuelle, retour à l’aperçu, validation et correction ont été effectués au clavier, avec focus visible. Le texte de la pièce a été effectivement affiché ; la correction conserve les accords antérieurs et exige une nouvelle validation. Le zoom Chrome à 200 % a été observé sur l’aperçu, ses limites et son lien de pièce. Le contrôle antérieur à 320 × 720 dans le navigateur Codex a vérifié l’absence de débordement horizontal de la page ; il reste une preuve distincte.

Le 7 septembre 2026, Ayo a retiré l’exigence de qualification au lecteur d’écran du périmètre produit. Le contrôle VoiceOver a été interrompu sans verdict de réussite ; il ne conditionne plus la fusion S2. La [CI Ubuntu de la PR #199](https://github.com/ayoahha/benchmark-lab-x/actions/runs/34130571182) a exécuté 870 tests et construit le runtime de `009ae3293ba89955db47a1af3448d987ac23dabc`, avec les fichiers de préparation inclus. Elle ne lance ni les huit parcours HTTP du complément local ni la suite demo ; ces preuves restent acquises séparément sur macOS. Le test HTTP relaie explicitement le cookie Secure ; la qualification HTTPS et d’exploitation reste distincte de la preuve logicielle.

## Qualification et approbation locales S3

Le candidat local [qualification.py](qualification.py) ajoute des contrats versionnés, leurs qualifications et une approbation opérateur explicite sur les mêmes octets. Il applique le [contrat de preuve](../docs/RULES.md#4-contrat-avant-exécution) aux pièces privées conservées par S1/S2. Aucun contrôleur métier universel, chargeur de plugin ou transport assistant n’est fourni. Le code produit n’importe aucun test ni rapport de préparation.

L’appel interne `qualification.initialize(data)` ajoute explicitement l’extension `benchmark-lab-x/qualification/v1` à une base S2 reconnue, y compris peuplée dans les fixtures locales. Il conserve ses lignes, ses pièces et `user_version=1`. Il refuse une autre base ou une extension partielle ; une extension exacte déjà présente reste inchangée. Ouvrir le stockage n’effectue aucune migration. L’usage sur une base existante hors fixtures n’est pas autorisé par cette construction locale. Les anciens lecteurs S2 refusent les objets S3 supplémentaires.

| Interface locale | Effet |
|---|---|
| `draft(store, dossier_id, revision, specification)` | Nouvelle version, paquet candidat exact et empreintes des références réservées ; retourne `contract` et `contract_sha256` |
| `qualify(store, contract_sha256, reviewer=…, check=…)` | Lit les octets, appelle une seule fois le contrôleur injecté par l’appelant de confiance et conserve sa preuve attribuée |
| `approve(store, contract_sha256, qualification_id, actor=…, authority=…)` | Lie explicitement la version courante à sa dernière qualification complète et à l’autorité locale |
| `inspect_contract(store, contract_sha256)` | Relit le contrat, ses `qualifications` et son `approval`, y compris historiques, sans les modifier |

La spécification structurée contient `result_expected`, `obligations`, `eliminatory_errors`, `reference_piece_ids`, `method`, `witnesses`, `secondary_criteria`, `aggregation`, `cost_basis`, `exposure`, `professional_review` et `limits`. Les obligations justifient leur usage et leurs tolérances ; obligations et erreurs relient leurs identifiants de contrôle à une méthode identifiée et versionnée, sa preuve attendue et son responsable. Les témoins sont déclarés avant le contrôle. Une référence doit appartenir à la même révision et être réservée au jugement. Les champs supplémentaires, dont un classement implicite des obligations, sont refusés.

Zéro à deux critères secondaires sont acceptés, chacun avec `id`, `measure`, `proof`, `unit`, `favorable` (`lower`, `higher` ou `yes`) et `aggregation`. Une agrégation absente vaut `null` ; aucune agrégation n’est calculée par S3. Une déclaration présente explicite `scope`, `cases`, `attempts`, `denominator`, `missing`, `incidents`, `indeterminate` et `rule`. La base de coût déclare `scope`, `attempts`, `unit` et `conversion`, celle-ci étant absente ou attribuée par `source`, `date` et `formula`. Aucune valeur de mesure ou de coût n’est acquise par ces déclarations.

Le contrôleur reçoit une copie du contrat et un dictionnaire des identifiants de pièces vers leurs octets relus. Il retourne `checks`, `limits`, `professional_review`, `assistance` et `disagreements`. Chaque contrôle porte `control_id`, `status`, `finding` et un objet `proof` non vide. Tous les contrôles déclarés doivent être présents exactement une fois et prouvés `PASS`. Un contrôle manquant, supplémentaire, répété, `FAIL`, `INDETERMINE` ou sans preuve produit `BLOCKED` ; une structure invalide est refusée sans écriture. Un désaccord sans arbitrage et preuve bloque aussi la qualification. La revue professionnelle est `ABSENTE` ou attribuée par `author`, `phase`, `scope` et `proof`. L’assistance reste `null` dans cette interface locale sans transport ni enveloppe de jugement.

La couverture des contrôles et l’intégrité des octets sont vérifiées par le mécanisme ; la justesse métier dépend du contrôleur de confiance et de ses preuves. La qualification conserve au moins les limites du contrat et la même déclaration de revue professionnelle. Un contrôleur qui affirme à tort un succès ne devient pas fiable par sa signature, sa configuration ou un consensus. Les tests locaux utilisent des entrées inventées ; ils ne qualifient ni une profession ni un assistant réel.

Contrat, preuves et approbation sont stockés séparément dans SQLite. Le SHA-256 du contrat porte sur le JSON UTF-8 strict canonique, sans saut de ligne, sans sa propre empreinte ni validation, qualification ou approbation. Les preuves possèdent aussi leurs empreintes. Les écritures sont transactionnelles ; les mises à jour, suppressions et remplacements d’une identité S3 existante sont refusés. La version courante est dérivée de l’historique conservé. Un nouveau contrat impose une nouvelle qualification et approbation ; un nouveau paquet exige en plus une nouvelle validation S2. Une correction en attente bloque l’éligibilité courante. Après approbation, une nouvelle qualification exige une nouvelle version. Les anciennes versions et preuves restent lisibles ; sauvegarde, vérification et restauration les contrôlent ensemble. Le marqueur de restauration interdit une nouvelle approbation, même répétée à l’identique.

Ayo est l’approbateur local désigné par le GO S3. Les seuls acteurs fictifs des tests sont `responsable-fictif-S3` et son autorité `TEST_ONLY_APPROVAL_S3` ; ces reçus fictifs n’accordent aucun droit réel. La frontière de confiance est l’accès opérateur autorisé au stockage privé et au fichier de décision. Une chaîne `actor`, un rôle, une session ou une saisie publique n’authentifie personne. Aucune route HTTP d’approbation n’existe.

Les commandes suivantes consomment un fichier privé, sans appel fournisseur. Elles retournent du JSON et le code 0 en cas de réussite ; une entrée ou opération non vérifiée retourne `HOLD` et le code 78 :

```sh
python3 -B -m benchmark_lab_x.runtime inspect-qualification --data /chemin/prive/benchmark --authority /chemin/prive/inspection.json
python3 -B -m benchmark_lab_x.runtime approve-qualification --data /chemin/prive/benchmark --authority /chemin/prive/decision.json
```

Pour inspecter, le fichier contient `contract_sha256`. Pour approuver, il contient exactement `contract_sha256`, `qualification_id`, `actor` et `authority = {authority_id, actor}`. L’acteur doit correspondre à l’autorité explicite ; les autorités fictives ne sont pas utilisables au nom de l’approbateur réel. L’inspection accepte aussi ce fichier complet. Les résultats de cette inspection sont privés. Le responsable examine les alternatives et limites dans `contract.specification`, les contrôles dans `qualifications` et les octets de chaque référence via `store.read_piece(piece['id'])` pour les entrées de `contract.reference_pieces`.

La vue du demandeur présente séparément validation, qualification et approbation. Sur une base S3, `qualification` expose `status`, `contract_sha256`, `qualification_status` et `approval_status`. `qualified` ne remplace pas l’approbation : celle-ci est indiquée par `APPROVED`. Attente, blocage et nouvelle validation requise restent distincts ; aucune référence, sortie de contrôle ou limite privée n’est projetée. Les formulaires, les pièces autorisées et les liens de retour S2 sont réutilisés. Leur HTML ne prouve pas à lui seul le parcours clavier, le focus visible, le petit écran ou le texte agrandi : une observation sur ce candidat reste requise, distincte des preuves historiques S2 et des tests HTTP.

Les régressions complémentaires sont dans [test_s3_regressions.py](../tests/test_s3_regressions.py). La découverte CI les inclut ; l’acceptation privée S3 et la suite demo restent séparées. Une évaluation empêchée par le sandbox de l’écrivain n’est pas un succès : les tests de sockets doivent être exécutés par le juge local Graph autorisé. Les preuves macOS restent distinctes d’une validation Linux. Cette construction ne réalise aucune intégration Git, migration opérationnelle, campagne ou publication.

## Campagnes privées locales S4

Le module [campaigns.py](campaigns.py) conserve plusieurs manifestes et leurs cellules sur les contrats approuvés S3. Il fournit l’admission, la réservation, une acquisition par callback fictif et le suivi du dossier S2. Il ne raccorde aucun fournisseur ni Pi réel. Les paramètres du prototype historique restent propres à celui-ci. La capacité locale ne produit aucun verdict de contenu, classement ou publication.

L’initialisation est explicite sur une base S3 reconnue et intègre, même peuplée. Elle ajoute l’identité `benchmark-lab-x/campaigns/v1`, ses tables et contraintes, avec admission fermée pour chaque nouvelle campagne. `user_version=1`, les pièces et les lignes S1–S3 sont conservés. Répéter cette initialisation, celle de S3 ou celle de S2 ne réécrit pas une extension S4 exacte. L’ouverture et l’inspection ne migrent rien ; les anciens lecteurs refusent l’extension non reconnue. L’usage opérationnel de données existantes garde son autorité distincte.

```sh
python3 -B -m benchmark_lab_x.runtime initialize-campaigns --data /chemin/prive/benchmark
python3 -B -m benchmark_lab_x.runtime create-campaign --data /chemin/prive/benchmark --authority /chemin/prive/manifeste.json
python3 -B -m benchmark_lab_x.runtime inspect-campaign --data /chemin/prive/benchmark --authority /chemin/prive/inspection.json
```

Les fichiers opérateur sont des fichiers réguliers privés, sans lien symbolique ni accès groupe/autres, comme pour S3. Les entrées sont du JSON strict ; champs supplémentaires et clés répétées sont refusés. Le runtime retourne du JSON privé, code 0 à réussite ou `HOLD` et code 78 en cas de refus. L’inspection contient les reçus et sorties brutes : sa sortie doit rester privée.

| Commande | Contenu exact du fichier `--authority` |
|---|---|
| `create-campaign` | `{manifest: objet}` |
| `inspect-campaign` | `{campaign_id: identifiant}` |
| `admit-campaign` | `{campaign_id, authority, evidence}`, avec `authority.purpose = "start"` |
| `stop-campaign` | `{campaign_id, reason}` |
| `resume-campaign` | `{campaign_id, authority, evidence}`, avec `authority.purpose = "resume"` |

Ces formes décrivent les clés ; les fichiers utilisent la syntaxe JSON avec clés et textes entre guillemets. Chaque commande d’admission ou de reprise prend les mêmes options `--data` et `--authority`. Aucune de ces commandes n’émet d’appel. L’identité de campagne est unique ; modifier un manifeste exige une autre identité et conserve les campagnes précédentes.

Le manifeste contient exactement `campaign_id`, `version` (entier positif), `contract_sha256`, `cases`, `panel`, `conditions`, `plan`, `attempt_policy` et `cost_basis`. Son SHA-256 porte sur le JSON UTF-8 canonique S3 : clés triées, sans espaces de séparation ni saut de ligne. Les autorités, états, réserves et observations restent hors de cette empreinte.

- Chaque cas contient `id` et `package_sha256`, égal à celui du contrat S3. Cette tranche utilise le paquet exact de ce contrat pour les cas déclarés ; elle ne construit pas de nouvelles entrées de tâche.
- Chaque configuration contient `id`, `provider`, `model`, `revision`, `access` (`direct` ou `API`), `channel_id`, `route`, `parameters` (objet), `effort` et `required_observations`. Cette dernière liste inclut au moins `revision` et `channel_id`. Une révision mobile non prouvée est refusée.
- `conditions` contient `pi`, `packages`, `tools`, `skills`, `context_sha256`, `defaults`, `environment` et `frozen_at` (date avec fuseau). `pi` contient `package`, `version`, `sha256`, `status` (`declared`, `configured`, `active` ou `observed`) et `proof`. Ces déclarations ne prouvent pas une exécution réelle.
- Chaque cellule de `plan` contient `cell_id`, `case_id` et `configuration_id`. `attempt_policy` contient `retries: false`, `order` (chaque cellule une seule fois) et `reason`. L’ordre est contrôlé avant émission. Aucune cellule reçue ou ambiguë ne peut être rejouée sous une seconde identité.
- `cost_basis` est exactement la base S3 approuvée ; aucun critère n’est copié ou changé par l’acquisition.

L’objet `authority` contient `actor`, `authority_id`, `purpose`, `manifest_sha256`, `execution_authority`, `candidate_authority`, `budget_authority`, `budget_id`, `allowed_cells` et `reserve_amounts`. Ayo reste l’opérateur local désigné ; ce champ ne l’authentifie pas. La frontière de confiance est l’accès opérateur privé autorisé, jamais une saisie HTTP. Les autorités `TEST_ONLY` et les identités `fictional-*` des tests ne donnent aucun droit réel.

Le budget doit déjà exister dans S1 via `Store.create_budget(budget_id, limit, currency)`, sous autorité propre ; montants et réserves sont des textes décimaux non négatifs. Sa devise doit égaler l’unité contractuelle. Avant la première admission, le suivi montre l’enveloppe portant l’identifiant de campagne si elle existe, sinon `INCONNU` ; cette convention d’affichage n’accorde aucune autorité de budget. L’admission lie explicitement `budget_id`, les cellules autorisées et leurs réserves. Les montants prévus des cellules sans intention doivent tenir dans le solde disponible. Une reprise conserve l’enveloppe et les réserves des intentions existantes.

L’objet `evidence` contient `pi_sha256`, `context_sha256`, `channels` et `confinement`. Chaque canal, indexé par l’identifiant de configuration, contient `available: true`, `revision`, `channel_id`, `route`, `proof` et les autres champs d’observation exigés, identiques à la demande. `confinement` contient `code_execution: false` et une preuve textuelle non vide. Cette tranche refuse les outils, paquets et skills non vides ainsi que toute exécution de code candidat : elle ne dispose pas du vérificateur de confinement nécessaire. Une déclaration opérateur ne qualifie pas un adaptateur réel.

Le lanceur local de confiance utilise les interfaces Python suivantes, avec son propre transport fictif installé dans le code du lanceur :

| Interface | Effet |
|---|---|
| `create(store, manifest)` | Manifeste conservé et `manifest_sha256`, sans appel |
| `inspect(store, campaign_id)` / `list_campaigns(store)` | État privé, cellules, tentatives, reçus, budgets et autorités conservées |
| `admit(store, campaign_id, authority, evidence)` | Nouvelle preuve d’admission distincte du manifeste ; aucune réservation implicite |
| `reserve(store, campaign_id, cell_id, attempt_id)` | Identité d’exécution, intention S1 et réserve atomiques ; `operation_id = attempt_id` |
| `execute(data, attempt_id, transport=None)` | Connexion propre, recontrôles et callback unique ; sans callback, refus avant émission |
| `stop(store, campaign_id, reason=...)` | Admission fermée durablement ; intentions, réserves et reçus conservés |

Le callback reçoit des copies de l’opération S1 persistée et de la requête : campagne, empreintes du manifeste et du contrat, cellule et cas, configuration demandée, conditions communes, paquet S3 et pièces candidates `{id, sha256, content}` relues en UTF-8. Il ne reçoit ni Store ni références réservées. Aucun champ du manifeste, fichier opérateur, chemin utilisateur, variable d’environnement ou route HTTP ne sélectionne un transport. Les empreintes des sources moteur sont conservées à la réservation et recontrôlées avant émission.

La réponse contient `receipt` et `cost` au format S1. Le reçu contient `receipt_id`, `observed_configuration`, `resources_seen` et `result = {output, incident, emission}`. `output` est un texte UTF-8 exact ou `null`, `incident` un motif ou `null`, `emission` vaut `ESTABLISHED`, `UNKNOWN` ou `INCONNU`. Les observations exigées portent leurs sources dans `observed_configuration.sources`. Une valeur absente reste `INCONNU` dans le suivi, avec source absente visible ; la demande n’est jamais utilisée pour compléter l’observation. Le coût contient `status`, `amount`, `currency`, `source` ; `UNKNOWN` exige un montant `null`.

Avant le callback, l’admission utilisée et la transition S1 `EMISSION_POSSIBLE` sont visibles depuis une autre connexion. Le reçu, son coût et la pièce de sortie sont ensuite reliés dans la même transaction. La sortie est conservée exactement, même erronée, avec le rôle privé `judge` de S1 pour préserver le paquet candidat S2. Ce rôle de stockage n’est pas un verdict. L’inspection vérifie aussi les empreintes des reçus, les jointures et les octets de sortie. Une interruption d’écriture peut laisser une pièce orpheline détectée par la vérification S1 ; elle n’est pas effacée automatiquement.

Un coût sourcé supérieur à la prévision reste acquis. Un coût inconnu garde la réserve ; un effet ambigu, une émission non établie ou une observation exigée divergente bloque les appels dépendants, y compris sur une enveloppe partagée. Le reçu original reste conservé. Une réponse inexploitable ou une exception sans reçu vérifiable laisse la tentative ambiguë, sans coût inventé ni retry. Les journaux n’exposent pas le texte d’exception privé.

Le suivi est ajouté à la page propriétaire S2, avec son lien « Actualiser cet état ». Il présente chaque campagne, la version de tâche, les configurations demandées, les conditions communes, les autorités à fournir ou renouveler, les prévisions, réserves et coûts connus. Une cellule `NOT_STARTED` n’a aucune tentative ; `INTENT_RECORDED`, `EMISSION_POSSIBLE`, `AMBIGUOUS` et `RECEIVED` décrivent la technique. Les sorties brutes et références de jugement restent réservées à l’inspection opérateur. Les sources d’observation absentes et le solde non établi sont signalés. Une session étrangère et les actions HTTP de lancement, admission, arrêt ou reprise sont refusées.

Maintenance, démarrage et arrêt de l’exécuteur ferment aussi les admissions S4. Un worker indépendant garde son état actif et peut rendre son reçu après cet arrêt. `status` conserve les champs `admission`, `restore_pending` et `operations` du protocole de santé S1–S3. Son booléen `admission` tient compte des admissions S2 et S4. `quiescence` et `backup` refusent une admission ouverte, une émission possible ou un worker S4 encore actif. Le worker tient un verrou partagé sur le répertoire de données pendant toute son acquisition ; le contrôle d’arrêt et la sauvegarde exigent le verrou exclusif. La sauvegarde le conserve pendant la copie, en plus du verrou SQLite. Aucun fichier de verrou ni état de processus n’est recopié dans la sauvegarde.

L’arrêt du service ne prouve pas l’arrêt des workers S4. Le rapprochement `runtime.stop(..., after_process_exit=True)` ne marque leurs émissions sans reçu ambiguës que si aucun worker ne détient encore le verrou. Après une mort forcée, le noyau libère le verrou ; le rapprochement explicite conserve alors l’ambiguïté et la réserve, et permet une sauvegarde sans autoriser le rejeu. Tant qu’un autre worker S4 reste actif dans la même base, ce rapprochement attend aussi son arrêt. Les autres opérations gardent le contrat d’arrêt de leur service. Une simple ouverture ne change pas les états. La reprise explicite nomme les cellules jamais émises et refait les contrôles ; aucune file n’est drainée au démarrage. Ne pas mélanger des workers de versions différentes sur une base active.

Sauvegarde et restauration couvrent SQLite, toutes les pièces et leurs liens S4. Le marqueur `restore.json` bloque durablement l’admission, y compris pour une nouvelle campagne, car une sauvegarde ancienne ne prouve pas l’absence d’appels ultérieurs. Cette tranche ne fournit aucune commande de levée de ce blocage sans rapprochement des preuves.

Les [régressions S4](../tests/test_s4_regressions.py) utilisent uniquement des données fictives et les interfaces S1–S3. Elles vérifient notamment l’intention concurrente unique, l’immutabilité des preuves, la conservation des dépenses de préparation, le contrôle d’ordre, la reprise et l’isolation du suivi. Les contrôles automatiques ne qualifient aucun modèle ni contenu métier. La revue propriétaire du candidat reste nécessaire pour les libellés, la retrouvabilité des campagnes, le clavier/focus, le petit écran et le texte agrandi ; aucune observation de navigateur S4 n’est revendiquée. Les preuves macOS restent distinctes de Linux, et la suite demo du prototype reste séparée de la découverte CI.

### Validation du candidat local du 7 septembre 2026

État de la première remise, avant E1 : `HOLD`. Les contrôles ci-dessous ont été exécutés sur macOS 27.0 arm64 dans le sandbox de l’écrivain, par les commandes du juge épinglé. Ils ne constituent pas une évaluation native Graph hors sandbox ni une preuve Linux. Le manifeste de préparation SHA-256 `38c9689c38d70910e70f6fa226b53c44ed423234ee33c266af43055a21915dcd` et ses 45 fichiers ont été revérifiés inchangés. À cette première remise, le fusible natif comptait une entrée `implementation`, zéro entrée `correction` ; aucun registre parallèle n’a été créé.

| Commande exécutée | Résultat observé |
|---|---|
| `python3 -B -m unittest tests.test_s4_regressions` | 15 tests, succès |
| `python3 -B reports/s4-preparation/judge.py witnesses` | 4 tests, succès |
| `python3 -B reports/s4-preparation/judge.py s4` | 14 tests, un échec : coût de préparation attendu `2`, reçu conservé `3` |
| `python3 -B reports/s4-preparation/judge.py s3` | 16 tests, une erreur : ouverture TCP locale refusée par le sandbox |
| `python3 -B reports/s4-preparation/judge.py s2` | 13 tests, une erreur : ouverture TCP locale refusée par le sandbox |
| `python3 -B reports/s4-preparation/judge.py storage` | 23 tests, succès |
| `python3 -B reports/s4-preparation/judge.py services` | 2 tests, une erreur : chemin temporaire de socket Unix trop long |
| `python3 -B reports/s4-preparation/judge.py ci` | 894 tests, deux erreurs : ouverture TCP refusée et chemin de socket Unix trop long |
| `python3 -B reports/s4-preparation/judge.py demo` | 69 tests, succès, suite historique séparée |

Le mode `ci` exécute bien `uv run --with requests --with mpmath==1.3.0 python -m unittest discover -s tests`, avec les variables offline du juge et vérification des dépendances avant/après. Syntaxe Python, liens locaux du README, absence d’import produit de tests/rapports et `git diff --check` ont aussi été vérifiés.

Le défaut du critère S4 est reproductible avant toute initialisation S4 : `seeded(data)` du juge scellé appelle la fixture S3, qui reçoit `amount = "3"` de `response_for` dans `tests/test_s2_review_regressions.py`. L’inspection S1 donne alors `spent = "3"`, `reserved = "0"`, `available = "97"` sur l’enveloppe `fictional`. L’assertion de `reports/s4-preparation/acceptance.py:242` attend pourtant `"2"`. S4 conserve ce reçu et ce coût ; les diminuer pour satisfaire l’assertion contredirait la conservation des preuves S1–S3. Aucun test, juge ni critère scellé n’a été modifié ou ignoré. Ce test interrompu ne prouve pas les sous-cas placés après son assertion en échec.

La coordination doit résoudre cette contradiction sous autorité et faire exécuter les contrôles réseau dans le contexte du juge Graph qualifié avant de pouvoir établir tous les critères. Aucune correction produit ne peut fabriquer le montant attendu. La revue propriétaire du code et du parcours demeure distincte, sans score qualitatif automatique. Aucun appel réel, opération Git de livraison ou action externe n’a été effectué.

### Correction unique après E1

État du candidat après la correction autorisée : `HOLD_EVALUATOR_FAILURE`. Le retour natif E1 porte sur le contrat Graph SHA-256 `49ec773fd55f8ca5f269175bbcd534819a1d40c81101f24f51f904dc935f7d14` et le candidat `836983652919d28932415116fd132827018644f6b7855a0868dd938cbe375729`. Le fusible natif lu pendant cette passe compte une implémentation et une correction. L’écrivain ne modifie ni ce registre ni les critères scellés et n’engage aucune autre boucle.

E1 a révélé un défaut produit que les refus de sockets du sandbox écrivain empêchaient d’observer : `runtime.status()` ajoutait `campaign_admissions`, alors que `service.executor_health()` exige exactement les cinq champs de sa réponse de santé. Le lecteur rejetait la réponse, puis `/readyz` retournait 503. La correction retire ce champ supplémentaire de `status` et conserve la prise en compte des admissions S4 dans le booléen existant `admission`. Le service et ses tests existants restent inchangés.

La régression `test_health_consumer_accepts_s4_status_before_during_and_after_admission` transmet le JSON du producteur réel au lecteur produit inchangé, avec seulement les entrées/sorties de socket simulées. Avant correction, ses trois états reproduisaient `ValueError: Réponse de santé invalide` à `service.py:44`. Après correction, elle passe et vérifie les états d’admission fermé, ouvert puis arrêté. Cette preuve du format échangé reste distincte des tests avec processus et sockets réels.

Fichiers touchés pendant cette seule correction : [runtime.py](runtime.py), [test_s4_regressions.py](../tests/test_s4_regressions.py) et ce README. Résultats des mêmes commandes épinglées après correction :

| Contrôle | Résultat dans le sandbox écrivain |
|---|---|
| Régressions S4 | 16 tests, succès |
| `witnesses` | 4 tests, succès |
| `s4` | 14 tests, un échec : `2 != 3` à l’assertion scellée de coût |
| `s3` | 16 tests, une erreur : ouverture TCP locale refusée |
| `s2` | 13 tests, une erreur : ouverture TCP locale refusée |
| `storage` | 23 tests, succès |
| `services` | 2 tests, une erreur : chemin de socket Unix trop long |
| `ci` | 895 tests, deux erreurs : ouverture TCP refusée et chemin de socket Unix trop long |
| `demo` | 69 tests, succès, suite historique séparée |

La contradiction de coût décrite ci-dessus subsiste après l’unique correction : le juge attend `2 TEST` pour un reçu de préparation sourcé à `3 TEST`. Corriger le protocole de santé ne change pas cette dépense. Modifier le reçu, son calcul ou le juge pour obtenir un succès contournerait le contrat scellé. Ce critère restant impose l’arrêt ; aucun `READY_FOR_OWNER_REVIEW_LOCAL` ni succès natif E2 n’est revendiqué. L’exécution native du candidat corrigé, les observations Linux et la revue propriétaire du code/parcours restent des preuves distinctes. Aucun appel réel ou acte de livraison n’a été effectué.

### Correction locale des constats de revue

Sous `GO_CORRIGER_S4_CONSTATS_DE_REVUE_SANS_APPEL`, la durée de vie des workers S4 est vérifiée par verrou système, indépendamment de celle du service. Les appels existants de `service.py` passent par le contrôle commun corrigé ; leur code reste inchangé. L’identité moteur inclut désormais `runtime.py`, qui porte ce contrôle. Les commentaires signalés respectent la règle locale de ponctuation.

Les deux nouvelles régressions lancent un vrai service local et un worker séparé à transport fictif. Elles vérifient l’arrêt puis le redémarrage du service pendant le callback, le refus de quiescence et de sauvegarde pendant l’activité, puis la réception tardive ou la mort forcée suivie du rapprochement. Elles reproduisaient le défaut avant correction et passent après correction ; les 18 régressions S4 passent également. Les preuves et juges antérieurs restent conservés. Le terminal Graph historique n’est ni repris ni réécrit. Le nouveau candidat attend sa revue, sans intégration ni appel modèle.

## Évaluations privées fictives S5

[evaluation.py](evaluation.py) évalue une tentative S4 identifiée sous son contrat S3 exact. Cette frontière locale reçoit des constats d’un contrôleur de confiance injecté par l’opérateur ; elle calcule le verdict, conserve les preuves et les rend consultables dans la session propriétaire S2. Aucun transport, chargeur de contrôleur, endpoint de jugement ou appel modèle n’est fourni. Le responsable réel des verdicts reste à désigner ; l’approbation locale S3 par Ayo ne l’attribue pas.

| Interface Python | Effet |
|---|---|
| `evaluation.initialize(data)` | Extension explicite d’une base S4 reconnue et intègre |
| `evaluation.evaluate(store, campaign_id, attempt_id, *, responsible, authority, check, previous_evaluation_id=None)` | Contrôle fictif local, verdict et conservation atomique |
| `evaluation.inspect(store, evaluation_id)` | Lecture vérifiée du résultat conservé, sans rejouer le contrôleur |

La seule autorité acceptée est `authority = {"actor": "responsable-fictif-S5", "authority_id": "TEST_ONLY_EVALUATION_S5"}`, avec ce même `responsible`, dans des données fictives isolées. Ces chaînes ne constituent pas une authentification ni une autorisation réelle. L’accès opérateur privé reste la frontière de confiance. Aucun formulaire ne peut fournir un callback.

Le callback `check(context, resources)` reçoit des copies des inspections S4 et S3 sous `{campaign, qualification, attempt}` et les octets des seules entrées candidates, références et sortie de cette tentative. Une intention sans reçu est évaluable comme observation insuffisante ; une cellule jamais lancée n’est pas une tentative. Le callback retourne exactement `findings`, `measures`, `judgment` et `limits`, sans verdict imposé. Les pièces et le contexte sont revérifiés avant conservation.

- Un constat porte `criterion_id`, `control_id`, `status` (`PASS`, `FAIL`, `INDETERMINE`), `attribution`, `finding` et `evidence`. Critère et contrôle doivent être déclarés ensemble au contrat. Chaque preuve contient `piece_id`, `sha256` et `passage`, vérifiés sur les octets du contexte. Une preuve booléenne, étrangère ou divergente est refusée. Un passage vide peut seulement témoigner d’une pièce exactement vide. Un contrôle prévu absent devient un constat explicite d’insuffisance.
- Une mesure porte `criterion_id`, `value`, `unit`, `evidence`. Sa définition contractuelle est jointe au reçu ; une unité divergente ou un critère ajouté après coup est refusé. Une mesure absente conserve une valeur `null` et un état `UNKNOWN`. Les valeurs sources restent conservées, y compris sur une sortie non admissible. Aucune agrégation n’est calculée ; sa déclaration préalable ou son absence reste consultable.
- Le jugement porte `mode` (`local`, `human`, `assisted`), `instructions`, `resources_seen`, `assistance_operation_id`, `model_links`, `disagreements` et `professional_review`. Les liens déclarés sont un objet explicite ou `INCONNU`. Chaque désaccord conserve `finding` et `arbitration`, nul si absent, sinon `{responsible, decision, proof}` ; l’arbitrage est attribué au responsable fictif. La revue professionnelle est `ABSENTE` ou `{author, phase, scope, proof}`. Ses pièces, comme celles de l’arbitrage, doivent appartenir aux ressources vues.

Sur une sortie intègre et attribuable, un `FAIL` candidat prouvé donne `NE SATISFAIT PAS`, même si un autre contrôle manque, si une autre référence est contestée ou si un autre jugement reste non arbitré. Un conflit `PASS`/`FAIL` sur le même contrôle ne prouve pas ce défaut ; un défaut établi sur un autre contrôle reste conservé. `SATISFAIT` exige tous les contrôles d’obligations et d’erreurs éliminatoires prouvés, sans désaccord non arbitré. Sinon le verdict est `INDETERMINE`. Une attribution requise manquante, une émission inconnue ou un `HARNESS_ERROR` empêche d’attribuer un défaut de contenu. Un autre incident reste distinct d’un éventuel défaut établi indépendamment dans la sortie. Une rupture d’intégrité provoque un refus, sans créer d’erreur candidate.

La justesse d’un constat dépend du contrôleur qualifié et de ses preuves. Le produit vérifie les liens, les passages, la couverture et la règle de verdict ; il n’interprète pas universellement les obligations écrites en langage naturel. Le contrôleur applique aussi les obligations économiques éventuellement prévues : il doit conserver l’insuffisance lorsque le coût requis est inconnu. Un coût inconnu n’annule pas la satisfaction des obligations non économiques. Les dépenses candidates proviennent du reçu S1 de la tentative, avec leur base et leur source ; elles ne comprennent pas implicitement la préparation ou le jugement.

L’assistance fictive réutilise une intention S1 de phase `judgment`, sous `TEST_ONLY_JUDGMENT_S5`, liée au même dossier et à sa révision, avec un budget en `TEST`. Sa première ressource est le JSON strict `{instructions, context_sha256, piece_ids}`, suivi des identifiants de pièces dans le même ordre que `resources`. L’empreinte du contexte est calculée avec `qualification.digest(context)`. Consignes, contexte et pièces sont vérifiés contre le jugement. L’opération conserve configuration demandée, reçu, configuration observée, ressources vues, autorité, moteur, réserve, coût et effets inconnus. Une opération candidate ou un jugement étranger est refusé. Un reçu absent ne permet pas une satisfaction assistée ; son éventuelle réception tardive ne réécrit pas l’évaluation précédente. Une correction reste explicite. Aucun appel ni retry n’est réalisé par S5.

Les configurations demandées et observées des assistants de préparation, du juge éventuel et de la tentative sont rapprochées séparément pour exposer les liens connus de modèle ou fournisseur, avec les identifiants d’opération et de reçu sources. Une valeur absente reste `INCONNU` ; des noms différents ne prouvent pas l’indépendance. Le temps humain et le coût local restent inconnus sans méthode ni mesure. Les témoins fictifs conservent leurs dépenses propres : notamment `3 TEST` pour la préparation S2, `2 TEST` pour l’acquisition et `4 TEST` pour le reçu de jugement utilisé par l’acceptation. Ces unités ne sont pas des dépenses réelles de modèles ou de Graph.

Chaque évaluation conserve les identités de campagne, manifeste, tentative, cas, configuration, contrat, qualification et méthode, la sortie brute et son empreinte, les observations sourcées, les constats, les mesures, le responsable et la provenance du moteur d’évaluation. Le contexte observé au moment du jugement est conservé séparément du résultat. Une réception, un arrêt, une restauration ou une nouvelle révision de dossier ne substitue pas les observations ultérieures à ce contexte.

La correction doit référencer la dernière évaluation de la même tentative dans `previous_evaluation_id`. Une première évaluation, puis ses successeurs, forment une chaîne conservée ; les mises à jour, suppressions et remplacements sont refusés en SQLite. Deux corrections concurrentes ne peuvent consommer le même prédécesseur. Une nouvelle méthode ou référence contractuelle exige une nouvelle version S3 ; elle ne remplace pas les octets d’une campagne existante.

Le format `benchmark-lab-x/evaluations/v1` ajoute explicitement `s5_control`, `s5_evaluations` et leurs contraintes au schéma de stockage 1. Les dispositions canary et S1–S4 restent reconnues sans réécriture. Un ancien lecteur sans reconnaissance S5 refuse cette structure ; aucun rollback de données ni migration implicite n’est fourni. La vérification du stockage contrôle aussi les évaluations, leurs empreintes, leurs sources et leur chaîne. L’évaluation conserve le verrou partagé de worker et une transaction SQLite pendant le callback ; la sauvegarde exige le verrou exclusif. Sauvegarde et restauration couvrent les nouvelles tables avec les pièces existantes, en gardant le blocage de reprise après restauration.

La page du dossier propriétaire présente les évaluations dans chaque tentative, leurs motifs, limites, coûts séparés, mesures, qualification exacte, jugement et liens de correction. Les liens GET `/preparation/dossiers/{dossier_id}/evaluations/{evaluation_id}/pieces/{piece_id}` vérifient la session et la chaîne d’appartenance avant de rendre les octets en texte inerte. Le rôle `judge` ne donne pas d’accès global : une pièce étrangère, même réservée dans le même dossier, reste refusée. La route historique des pièces candidates reste limitée au paquet candidat. Les données sont échappées dans le HTML ; le service conserve ses en-têtes de protection existants. Aucun tri, filtre de comparaison, classement ni publication S6 n’est ajouté.

Les deux commandes locales suivantes retournent du JSON et le code 0 après vérification, ou `HOLD` avec le code 78 si l’opération n’est pas vérifiée :

```sh
python3 -B -m benchmark_lab_x.runtime initialize-evaluations --data /chemin/prive/benchmark
python3 -B -m benchmark_lab_x.runtime inspect-evaluation --data /chemin/prive/benchmark --authority /chemin/prive/inspection.json
```

Le fichier d’inspection, ordinaire, privé et détenu par l’opérateur, contient exactement `{"evaluation_id": "identifiant-conserve"}`. L’inspection n’initialise rien et ne donne aucune autorité de jugement réel.

Les [régressions S5](../tests/test_s5_regressions.py) couvrent les garanties complémentaires de concurrence, d’intégrité, d’évolution du dossier, de réception tardive et de sauvegarde. Elles sont indépendantes des rapports et fixtures du juge scellé. La découverte CI et la suite `benchmark_lab_x.test_demo` restent des validations distinctes ; les preuves macOS ne valent pas preuve Linux. La revue du code et du parcours propriétaire reste nécessaire : comprendre le motif, retrouver qualification et correction, ouvrir la sortie et ses preuves, revenir au dossier, puis vérifier clavier, focus, petit écran et texte agrandi dans un navigateur identifié. Les contrôles binaires ne certifient ni la qualité métier ni ce parcours humain.

## Outillage des premières campagnes

Les outils sous `tools/` conservent leurs contrats historiques et ne sont pas les commandes décrites ci-dessus. Dans `tools/campagne_v1.py`, le rendu et sa vérification calculent encore les empreintes des canons du checkout courant sous des libellés historiques ; les tests rétablissent au contraire les contrats du commit `38e226a59020aad517cd0dbb16892ffb87d448ab`. Leur réussite ne valide pas une restitution historique régénérée contre les canons courants. Toute opération sur ces campagnes doit identifier ses sources d’origine avant exécution.
