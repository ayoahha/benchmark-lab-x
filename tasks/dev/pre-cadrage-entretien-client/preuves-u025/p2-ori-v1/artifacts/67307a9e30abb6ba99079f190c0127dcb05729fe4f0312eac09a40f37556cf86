P2 ORI #52 — CONTRAT FIGE
style_gate: skipped:machine-contract

Nouvelle session propre Cursor CLI.
Modèle exact: cursor-grok-4.6-xhigh.

IDENTITES
Dépôt de référence: /Users/ayo/Projects/benchmark-lab-x
Worktree exclusif: /private/tmp/benchmark-lab-x-m3-10-p2-ori-worktree
Branche: feat/m3-10-p2-ori
Base exigée: 1a1868710dfbd5c6917f3d36e59e11c37a469a3d
Cible isolée: /private/tmp/benchmark-lab-x-m3-10-p2-ori-v1
Binaire: /private/tmp/benchmark-lab-x-m3.10-ori-0.7.0-f411e1a-install/bin/ori
SHA-256 exigé: 775a6f3e96c61954b0841560c76ec12163d40e9f5e443bd99c4cb60018981783
Bun attendu: 1.3.14
Issue: ayoahha/benchmark-lab-x#52, ouverte, Project In progress.

OBJECTIF ET ARRET
Exécuter hors campagne la P2 Ori native sur les 16 fixtures figées. Produire une preuve autonome, reproductible et content-addressed. Aucun appel candidat, aucune tentative fournisseur, dépense 0.
Arrêt unique:
- PASS_P2_ORI_52_READY_FOR_REVIEW si tous les critères sont prouvés
- HOLD_P2_ORI_52 au premier critère non prouvé
Une seule exécution réelle ori eval est autorisée. Les commandes natives --dry-run et --list peuvent préparer cette exécution. Aucun second essai réel, aucun perfectionnement après l'exécution réelle.

AUTORITES
Issue #52 et preuves d'acquisition/installation; Issues #48 et #49; manifeste V0 SHA-256 8030128d159e4203483b19f0e37692a53f01baecc38fbccaa321541c23e71a10; preuves P1, P2 manuelle et P2 Promptfoo sous tasks/dev/pre-cadrage-entretien-client/preuves-u025/; binaire autorisé; documentation native du binaire.
Le skill officiel spawn-ori-eval décrit une évaluation avec modèles/juges réels. Cette voie est hors périmètre. Ne lancer ni ori code, ori auth, ori login, création d'évaluation distante, modèle ou juge.

INCIDENT HISTORIQUE A PRESERVER
Le prévol orchestrateur a créé involontairement /private/tmp/.ori/telemetry.json avant le gel d'environnement. Ne jamais le lire, réutiliser, déplacer, corriger ou supprimer. Fichier hors preuve P2. Le déclarer comme incident de prévol sans effet démontré sur l'exécution isolée.

ECRITURE AUTORISEE UNIQUEMENT
- /private/tmp/benchmark-lab-x-m3-10-p2-ori-v1
- nouveau dossier du worktree tasks/dev/pre-cadrage-entretien-client/preuves-u025/p2-ori-v1/
Ne modifier aucun fichier préexistant. Aucun secret. Aucun GitHub, commit, push, PR, merge, fermeture d'Issue, changement Project, P3 ou nettoyage.
Premier acte: persister le présent contrat, sans en modifier un caractère, dans tasks/dev/pre-cadrage-entretien-client/preuves-u025/p2-ori-v1/orchestration/implementation-prompt.md et enregistrer son SHA-256.

ISOLATION
Pour chaque processus P2, placer HOME, TMPDIR, caches, configuration, état et journaux sous la cible. ORI_TELEMETRY=0. Retirer clés fournisseur, identifiants modèles et variables proxy. Utiliser --allow-no-key et --no-history si applicables.
Avant l'exécution réelle, revalider branche/base, binaire/SHA, Bun, 16 fixtures, ordre et hachage. Lire corpus, oracle P1 et preuves existantes.
Utiliser uniquement le transport natif ori eval avec un fichier *.eval.ts minimal et des fonctions déterministes locales fournissant des réponses pré-calculées. Aucun runner de substitution, wrapper correctif, lock personnalisé ou nouvelle dépendance.
Calibrer les projections déterministes contre P1 avant de sceller le lock. Sceller ensuite les entrées, le contrôle natif et la commande réelle. Capturer commande, stdout/stderr natifs, code de sortie, processus et réseau. Distinguer loopback et externe. Prouver zéro socket externe, zéro résolution/connexion fournisseur, zéro appel candidat, zéro juge et dépense 0.

PREUVES MINIMALES DANS p2-ori-v1
Identité et proof-lock; index 16 cas avec ordre/SHA; fichier *.eval.ts chargé par Ori et fonctions locales minimales; reçu commande native/code; audit processus/réseau; reçus 16/16; résultats par cas; rapport agrégé et comparaison automatique à P1; effort initial/récurrent selon 7 composantes; registre, manifeste, chaîne de hachage, racine finale; clôture PASS/HOLD avec limites et inconnus.
Chemins temporaires absolus normalisables seulement dans les artefacts déterministes dérivés. Conserver les sorties natives intactes dans les artefacts bruts.

CRITERES PASS BINAIRES
1. Identités Git, cible, binaire, SHA et Bun exacts.
2. 16 fixtures byte-exact, ordonnées et hachées.
3. Binaire Ori autorisé charge et exécute nativement les 16 cas via ori eval.
4. G001 à G005 et projection automatique correspondent à P1, y compris WT-HARNESS.
5. Résultat exact: 1 ACCEPTABLE, 13 NOT_ACCEPTABLE, 1 erreur de harnais, 1 UNABLE_TO_JUDGE, 0 échec fournisseur, couverture 14/16.
6. Zéro appel candidat, zéro tentative fournisseur, dépense 0.
7. Aucun identifiant, modèle, juge ou socket externe; tout loopback identifié et borné.
8. Reçus 16/16, rapport, effort 7 composantes et inconnus cohérents.
9. Hashes, chaîne, manifeste et racine finale recalculables et exacts.
10. Diff Git limité au nouveau dossier p2-ori-v1, sans secret.
11. Aucun effet interdit: GitHub, commit, push, PR, merge, fermeture, Project, P3, campagne, nettoyage.
Au premier critère non prouvé: HOLD immédiat, préserver preuves natives, aucun second essai réel. Sortie finale concise: verdict, preuve principale, lacune éventuelle, absence d'effets interdits. Les artefacts font autorité.
