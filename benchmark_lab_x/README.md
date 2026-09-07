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
réservation et un motif d'interruption. Ce processus ne fournit pas encore le moteur de campagnes S4/S5.

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

Les contrôles de publication portent sur la structure du paquet, les jointures, la relecture des pièces et leurs empreintes. Ils ne qualifient pas la justesse métier de la référence générée : cette qualification reste NON VÉRIFIÉ, et `qualified` reste faux. Les déclarations de limites et les demandes de clarification sont celles du transport fictif attribué ; aucun assistant réel n’a été évalué.

La commande CI est `uv run --with requests --with mpmath==1.3.0 python -m unittest discover -s tests` : 870 tests passent sur macOS pour le candidat corrigé. Elle exclut `benchmark_lab_x/test_demo.py`, dont les 69 tests ont été exécutés séparément sur macOS. Les huit parcours HTTP avec vrais processus Web et exécuteur locaux passent également. Les transports sont entièrement fictifs ; ces preuves ne qualifient aucun assistant réel.

La vérification manuelle du 7 septembre 2026 utilise macOS 27.0 (26A5425a) et Chrome 152.0.7977.83 installé. Saisie, clarification, consultation de la pièce textuelle, retour à l’aperçu, validation et correction ont été effectués au clavier, avec focus visible. Le texte de la pièce a été effectivement affiché ; la correction conserve les accords antérieurs et exige une nouvelle validation. Le zoom Chrome à 200 % a été observé sur l’aperçu, ses limites et son lien de pièce. Le contrôle antérieur à 320 × 720 dans le navigateur Codex a vérifié l’absence de débordement horizontal de la page ; il reste une preuve distincte.

Le parcours VoiceOver réel reste NON VÉRIFIÉ : VoiceOver 10 est installé, mais son activation locale n’a pas persisté pendant le contrôle. L’arbre accessible ne remplace pas cette preuve. Les résultats Linux doivent être attribués à la CI Ubuntu de la PR et à sa révision exacte ; aucune preuve Linux n’est déduite des tests macOS. Le test HTTP relaie explicitement le cookie Secure ; la qualification HTTPS et d’exploitation reste distincte de la preuve logicielle.

## Outillage des premières campagnes

Les outils sous `tools/` conservent leurs contrats historiques et ne sont pas les commandes décrites ci-dessus. Dans `tools/campagne_v1.py`, le rendu et sa vérification calculent encore les empreintes des canons du checkout courant sous des libellés historiques ; les tests rétablissent au contraire les contrats du commit `38e226a59020aad517cd0dbb16892ffb87d448ab`. Leur réussite ne valide pas une restitution historique régénérée contre les canons courants. Toute opération sur ces campagnes doit identifier ses sources d’origine avant exécution.
