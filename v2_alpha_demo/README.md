---
style_gate: pass
---

# Démonstration locale V2-alpha

Ce bundle standard-library prépare une campagne scellée, exécute une fois chaque configuration après autorité S9, produit une revue aveugle, puis construit hors ligne une Salle de décision après décisions et autorité S10.

Depuis la racine du dépôt :

```bash
python3 -B -m v2_alpha_demo prepare --run-dir runs/ma-campagne --pi /chemin/reel/vers/pi
python3 -B -m v2_alpha_demo collect --run-dir runs/ma-campagne --authority /chemin/authorization-s9.json
python3 -B -m v2_alpha_demo review --run-dir runs/ma-campagne
python3 -B -m v2_alpha_demo build --run-dir runs/ma-campagne --decisions /chemin/decisions.json --authority /chemin/authorization-s10.json
python3 -B -m v2_alpha_demo show --run-dir runs/ma-campagne
```

`show` vérifie le sceau final et ouvre la page existante sans la régénérer. L’alternative directe est `open runs/ma-campagne/index.html`.

La page identifie la tâche par un brief (titre public, contexte, objectif, décision éclairée) et par le résultat attendu contractuel. Pour une future campagne, ce brief se fige avant exécution dans `campaign.json` sous la clé `brief` (exactement `title`, `context`, `objective`, `decision`) et entre ainsi dans l’empreinte du contrat ; le résultat attendu reste `expected_result`, unique source contractuelle, et un brief qui porterait `expected` est refusé. Deux replis existent quand ce champ manque : le scénario historique `quote-thread-summary` dispose d’un brief de présentation propre, rédigé après coup, signalé comme tel sur la page et relié à aucune empreinte de source ; toute autre tâche retombe sur son identifiant et le résultat attendu du contrat, avec les autres champs signalés non documentés.

Après une évolution du rendu, `present` construit une nouvelle présentation locale depuis un run final scellé, sans modifier ses résultats ni relancer de candidat :

```bash
python3 -B -m v2_alpha_demo present --source-run runs/ma-campagne --run-dir runs/ma-presentation
python3 -B -m v2_alpha_demo show --run-dir runs/ma-presentation
```

## Témoins d’autorité

Les schémas S9 et S10 sont vérifiés strictement. Les autorités restent externes à `prepare` et doivent utiliser les empreintes du run concerné.

S9 :

```json
{
  "schema": "benchmark-lab-x-v2-alpha-s9-authorization-1",
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
  "schema": "benchmark-lab-x-v2-alpha-s10-authorization-1",
  "effect": "product_execution_and_acceptance_s10",
  "authority_id": "TEMOIN-TEMPORAIRE-S10-DISTINCT",
  "run": "runs/ma-campagne",
  "seal_sha256": "<sha256 seal.json>",
  "review_sha256": "<sha256 review.json>",
  "decisions_sha256": "<sha256 du fichier decisions.json externe>"
}
```

Ces témoins documentent le format. Ils n’accordent aucune autorité réelle.
