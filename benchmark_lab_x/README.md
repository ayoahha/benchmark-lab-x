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

Le module `benchmark_lab_x.runtime` fournit une initialisation privée, la vérification de SQLite et des pièces, la maintenance, une sauvegarde cohérente et une restauration vers un nouvel emplacement. Ces interfaces sont distinctes du moteur historique ci-dessus. Le serveur public, le traitement des travaux longs et leurs accès ne sont pas encore fournis ; ces commandes ne constituent pas le service 0.1.0 complet.

Avec Python 3.12 ou supérieur, le répertoire parent des données doit exister. L’initialisation crée son emplacement privé ou utilise le répertoire vide préparé par Ansible sous le compte de service. Elle refuse tout emplacement contenant déjà des données :

```sh
python3 -B -m benchmark_lab_x.runtime initialize --data /chemin/prive/benchmark
python3 -B -m benchmark_lab_x.runtime verify --data /chemin/prive/benchmark
python3 -B -m benchmark_lab_x.runtime status --data /chemin/prive/benchmark
```

Ces commandes n’émettent aucun appel modèle. Les pièces et les révisions de dossier sont immuables. Une empreinte divergente, une pièce orpheline, une référence dangereuse ou un schéma inconnu provoque un refus. La bibliothèque de stockage utilise des réservations monétaires entières, attribuées à leur phase ; elle persiste l’intention et l’état d’émission avant le transport. Elle ne fournit pas encore le transport ni l’interface publique d’autorisation.

Pour une sauvegarde, arrêter les admissions puis attendre la fin des émissions actives. La vérification de quiescence distingue les travaux encore en cours des effets historiques inconnus. Ces derniers restent conservés et bloquent la reprise des appels :

```sh
python3 -B -m benchmark_lab_x.runtime maintenance --data /chemin/prive/benchmark
python3 -B -m benchmark_lab_x.runtime quiescence --data /chemin/prive/benchmark
python3 -B -m benchmark_lab_x.runtime backup --data /chemin/prive/benchmark --destination /chemin/prive/sauvegarde-neuve
python3 -B -m benchmark_lab_x.runtime verify-backup --data /chemin/prive/sauvegarde-neuve
python3 -B -m benchmark_lab_x.runtime restore --data /chemin/prive/sauvegarde-neuve --destination /chemin/prive/restauration-neuve
```

La sauvegarde bloque les écrivains SQLite pendant la copie des pièces et vérifie leurs liens. La restauration préserve la source et toute cible existante. Elle impose un blocage durable des admissions, même après une autre maintenance : le rapprochement des effets postérieurs à la sauvegarde doit être réalisé avant toute reprise. Cette interface de rapprochement reste à construire. Une copie de données vérifiée ne prouve pas la restauration d’un service Linux ni une récupération PBS.

`tools/build_runtime.py` construit une archive déterministe depuis les seuls fichiers suivis d’un commit complet. Il ignore les modifications du worktree et refuse une source dépourvue des interfaces runtime. La sortie JSON relie le commit, l’arbre, les blobs Git et l’empreinte de l’archive. Le build n’installe aucune dépendance et n’exécute pas la source construite :

```sh
python3 tools/build_runtime.py --source <commit-produit-complet> --output /chemin/benchmark-runtime.tar.gz
```

Le reçu décrit la construction effectuée ; son authenticité doit être vérifiée depuis le job ou l’opérateur identifié. L’archive utilise le format `release.json` du candidat infra. Elle ne fournit pas encore de serveur web ni d’exécuteur et ne doit pas être déployée comme un service complet. Aucun tag de livraison 0.1.0 n’est créé par ces interfaces.

## Outillage des premières campagnes

Les outils sous `tools/` conservent leurs contrats historiques et ne sont pas les commandes décrites ci-dessus. Dans `tools/campagne_v1.py`, le rendu et sa vérification calculent encore les empreintes des canons du checkout courant sous des libellés historiques ; les tests rétablissent au contraire les contrats du commit `38e226a59020aad517cd0dbb16892ffb87d448ab`. Leur réussite ne valide pas une restitution historique régénérée contre les canons courants. Toute opération sur ces campagnes doit identifier ses sources d’origine avant exécution.
