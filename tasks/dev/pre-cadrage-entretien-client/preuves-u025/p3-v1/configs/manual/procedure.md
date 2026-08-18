---
style_gate: pass
---

# Procédure manuelle P3 V2

Cette procédure est inerte sans quatre GO distincts authentifiés, une preuve ZDR adressée par contenu et une preuve de facturation adressée par contenu. Elle n'autorise aucun appel, aucune tentative fournisseur, aucune campagne, aucune dépense supplémentaire et aucun retry.

## Commande figée

Le runtime est `/opt/homebrew/bin/python3` version `3.14.7`, SHA-256 `87d4df53fd91304be5bac391fb204643c36b7df2023c04a0953bcbc7d4fdf634`.

Variables : `P3_AUTHORIZATION` (fichier d'autorisation), `P3_CONFIGURATION` (`grok46_xai_build_oauth` ou `kimi_k3_opencode_zen`), `P3_STAGE` (`canary` ou `campaign`).

```
/opt/homebrew/bin/python3 adapters/manual-acquire.py --authorization "$P3_AUTHORIZATION" --configuration "$P3_CONFIGURATION" --stage "$P3_STAGE"
```

`manual-acquire.py` injecte `--path manual`. L'opérateur ne passe pas `--path`.

## Contrôles

Après une acquisition autorisée, le cœur partagé invoque `controls/run_controls.py`, lié à `tools/validateur_pre_cadrage_v0.py` SHA-256 `e631184b84270c4b3dbf931910436ad65b7d08c02016c94d2dfe53e27ead2056`, dans l'ordre G-005, G-001, G-002, G-003, G-004.

Vérification autonome de la même sortie :

```
/opt/homebrew/bin/python3 controls/run_controls.py --candidate "$SORTIE_CANDIDATE"
```

## Revue aveugle

Le contrat est `blind-review.json`. Rôles, gel des reçus, décision mécanique et révélation après gel. Aucun juge LLM.

## Arrêt

Sans artefact GO, ZDR ou facturation authentifiable, ou sans prédécesseur réel dont le fichier existe et dont l'empreinte concorde, la commande ferme en `HOLD` ou `INCONNU` avant tout réseau.
