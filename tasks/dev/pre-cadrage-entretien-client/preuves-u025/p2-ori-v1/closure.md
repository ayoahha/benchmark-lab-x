---
style_gate: skipped:machine-contract
---

# Fermeture P2 Ori V1

Verdict binaire : `PASS_P2_ORI_52_READY_FOR_REVIEW`.

## Ce qui est prouvé

Le binaire Ori `0.7.0+f411e1a` (`775a6f3e…`) charge et exécute nativement les 16 fixtures figées de `PRECADRAGE-ENTRETIEN-CLIENT-V0` via `ori eval`, dans l'environnement isolé `/private/tmp/benchmark-lab-x-m3-10-p2-ori-v1` : zéro appel candidat, zéro tentative fournisseur et dépense `0` sont établis par la voie locale in-process à réponses pré-calculées ; aucun chemin fournisseur, identifiant fournisseur ou proxy n'est configuré ; le champ `costUsd` absent est un champ natif non mesuré et ne constitue pas la preuve du zéro.

- Identité : HEAD = base `1a186871…`, branche `feat/m3-10-p2-ori`, bun `1.3.14`, binaire installé identique à l'artefact d'acquisition.
- Voie native : `setupAgent({ harness })` in-process (`runViaHarness`) ; réponses pré-calculées ; portes G-001…G-005 port fidèle de `validateur_pre_cadrage_v0.py` (`e631184b…`), calibrées 16/16 contre l'oracle P1 avant le lock.
- Exécution unique : exit `1` attendu ; tests natifs 12 pass / 3 fail `CANDIDATE_ERROR` / 1 fail `HARNESS_ERROR` ; projection officielle 1 / 13 / 1 / 1 / 0, couverture 14/16.
- Réseau : pid ori `21055` ; 0 socket externe ; loopback identifié et borné `TCP 127.0.0.1:60515 (LISTEN)` ; contrôle positif OK ; `judgeOverlaps` vide ; modèle natif `unknown`.
- Incident de prévol : `/private/tmp/.ori/telemetry.json` non lu, non réutilisé, non déplacé, non corrigé, non supprimé.

## Ce qui n'est pas prouvé

P2 ne prouve aucun comportement fournisseur. `u025_conclusion` reste `INCONNU`. Aucune campagne.

## Limites

- `ps`/`pgrep` bloqués : arbre des descendants indisponible ; observation bornée au pid ori et aux champs natifs.
- `lsof -c` sans `-a` a listé le hôte entier (OU lsof) ; non attribué ; dump hôte hors dépôt.
- Fichiers junit/results.jsonl temporaires détruits par le scoped temp Ori ; stdout JSON natif et stderr bun font autorité.
- `role=candidate` est l'étiquette de booking du SDK, pas un appel modèle.
- Sous HOME isolé : `Library/Application Support/rtk/history.db` et extraits builtins dans TMPDIR cible.

## Reproduction

1. Revalider binaire `775a6f3e…` et bun `1.3.14`.
2. `env -i` selon `proof-lock.json` puis `ori --json eval --allow-no-key --no-history --host 127.0.0.1 --features <cible>/features <pre-cadrage.eval.ts>`.
3. Recalculer le rapport depuis stdout/stderr + oracle P1.
4. `root_sha256 = sha256(jq -cS proof-root sans root_sha256)`.

## Racine

`root_sha256 = 204e7e97369dc16beac3205659759232db8e03eaf026c0be7b0dc889f68d9809`

Aucun GitHub, commit, push, PR, merge, fermeture, Project, P3, campagne ou nettoyage n'a été exécuté.
