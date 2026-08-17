---
style_gate: pass
---

# Fermeture P2 Promptfoo V1

Verdict binaire : `PASS_P2_PROMPTFOO_51_READY_FOR_REVIEW`.

## Ce qui est prouvé

Promptfoo `0.122.0` transporte réellement les 16 fixtures figées de `PRECADRAGE-ENTRETIEN-CLIENT-V0` jusqu'au rapport P2 attendu, dans l'environnement isolé `/private/tmp/benchmark-lab-x-promptfoo-standard-v1`, sans appel candidat, sans tentative fournisseur et avec une dépense de `0`.

- Identité : artefact autorisé `5a4d0821…` recalculé, 629/629 fichiers byte-identiques dans l'installation npx, exécutable lancé `dist/src/entrypoint.js` (`b1f2d2cb…`) identique au tarball, lock de dépendances existant conservé (`e6589e2a…`), `dist.integrity` du registre égal à l'integrity du lock.
- Voie native : sorties pré-calculées transportées par `providerOutput` (schéma zod `tables-DxaDlQbd.js:3711`, court-circuit `evaluator-SSlcaq_U.js:7024` sans `callActiveProvider`) ; portes G-001…G-005 en assertions `javascript` natives `file://gates.js:gXXX`, port fidèle de `tools/validateur_pre_cadrage_v0.py` (`e631184b…`), calibré 16/16 contre l'oracle P1 avant l'unique exécution.
- Exécution : `eval-uLY-2026-08-17T20:13:05`, code de sortie `100` (sémantique documentée des tests en échec), 12 succès / 3 échecs / 1 erreur — projection native `success/failureReason` (ASSERT=1, ERROR=2) conforme aux 16 verdicts de l'oracle P1, portes par composant conformes, transport byte-exact des 16 candidates.
- Réseau : enforcement par le modèle de permissions Node (`--permission` sans `--allow-net` ni `--allow-child-process`, refus `ERR_ACCESS_DENIED` prouvés), zéro socket sur toutes les tiques lsof, contrôle positif de détection concluant, journaux promptfoo sans requête, partage/télémétrie/mise à jour/génération distante désactivés par mécanismes officiels ; seatbelt indisponible consigné.
- Rapport : `report.json` recalculable depuis la sortie native adressée par contenu (`4770f4eb…`) + oracle P1 ; compteurs identiques à la P2 manuelle V3 (`OFFICIALLY_ACCEPTABLE` 1, `CANDIDATE_NOT_ACCEPTABLE` 13, `HARNESS_ERROR` 1, `UNABLE_TO_JUDGE` 1, `PROVIDER_FAILURE` 0 ; couverture `14/16`).
- Effort : sept composantes, initial et récurrent séparés, 12 faits `OBSERVE`, 2 faits `INCONNU` (revue humaine récurrente, requalification maintenance).

## Ce qui n'est pas prouvé

P2 ne prouve aucun comportement fournisseur, coût fournisseur, latence fournisseur ni qualité d'une sortie candidate réelle. `u025_conclusion` reste `INCONNU`. Aucune campagne n'a eu lieu.

## Écarts documentés, sans effet sur le verdict

- Promptfoo évalue toutes les assertions sans court-circuit : pour les cas `FAIL`, les portes postérieures à la porte terminale de l'oracle sont aussi observées (états conformes au validateur) ; les statuts globaux restent identiques 16/16.
- Sur la ligne en erreur (`WT-HARNESS`), promptfoo omet nativement `response` ; la fixture transportée reste byte-exacte dans `testCase.providerOutput`.
- L'étiquette générique `Provider call failed during eval` du journal d'erreurs enveloppe l'erreur d'assertion conçue ; aucun appel provider n'a eu lieu (court-circuit cité).

## Reproduction

Depuis ce dossier, avec le setup standard revalidé (reçu #51) :

1. `npx --yes promptfoo@0.122.0 --version` hors ligne (`npm_config_offline=true`, caches de la cible) → `0.122.0`.
2. `node --permission --allow-fs-read='*' --allow-fs-write=<cible> --allow-fs-write=/dev/null --allow-addons <npx>/node_modules/promptfoo/dist/src/entrypoint.js eval -c promptfooconfig.json -o <cible>/p2-run/output/results.json -j 1 --no-progress-bar --no-cache` avec la liste blanche d'environnement (`artifacts/`, reçu `env-liste-blanche`) → code 100, 12/3/1.
3. Recalculer le rapport et la racine : projection `state_mapping` de `report.json`, puis `root_sha256 = sha256(jq -cS proof-root sans root_sha256)`.
4. Vérifier le registre : chaque `entry_sha256 = sha256(jq -cS de l'entrée sans entry_sha256)`, chaînage par `previous_entry_sha256`.

## Racine

`root_sha256 = 5a4fe21568a4680a81490521eb6d2cd42e7365753957cb07ba6cc3a82ae0d32c`

Aucun merge, aucune fermeture de #51, aucune action M3.12 ne sont exécutés par cette preuve. La relecture et les actions GitHub restent à l'orchestration.
