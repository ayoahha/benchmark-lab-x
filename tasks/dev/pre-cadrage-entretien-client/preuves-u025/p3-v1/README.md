---
style_gate: pass
---

# Lock P3 V2

État : `REVIEW_READY_NO_EXECUTION_AUTHORITY`.

Ce paquet ferme les deux écarts restants du lock V2. Il authentifie les décisions propriétaire déjà reçues, fige la porte des futures preuves ZDR et de facturation, crée le stockage privé autorisé et publie l'engagement d'ordre. Il n'autorise aucun appel, aucune tentative fournisseur, aucune campagne, aucune dépense ni aucun retry.

La preuve canonique est `proof-root.json`. Toute dérive d'un fichier couvert par `checksums.json` invalide le lock et les futurs GO qui le référencent.

Les déclarations d'un appelant ne font pas autorité. Un GO, une preuve ZDR ou une preuve de facturation doit être un artefact adressé par contenu, lié au lock, à la tentative et à l'autorité, vérifié avant tout réseau. Une clé, une empreinte ou une décision absente laisse le contrat visible et ferme en `INCONNU` ou `HOLD`.

Attendu, demandé et observé restent séparés. Une observation absente vaut `INCONNU`. L'identité servie n'est jamais déduite de la demande.

Les autorités GitHub sont dans `github-authorities.json`, sans corps. La porte exécutable est `controls/verify_evidence_gate.py`. ZDR et facturation restent `INCONNU`. Une attente ou une demande ne devient pas une observation. `OBSERVED` exige une preuve brute fournisseur de première partie, authentifiée, rejouable ou signée, adressée par contenu et liée au reçu.

Le manifeste d'ordre publie l'engagement du sel, le digest du mapping et la cardinalité 6. Les positions 1 à 6 sont figées en privé. La garde `controls/verify_order.py` recharge les objets privés, recalcule HMAC, prouve la permutation et la chaîne avant fournisseur. La révélation du sel suit le gel des verdicts humains. Le reçu de genèse reste `zero-execution-receipt.json`.

Les plafonds de dépense supplémentaire à zéro n'impliquent pas un coût fournisseur nul. Le coût réel, la dépense supplémentaire et l'allocation de pool restent distincts.

Les composantes d'effort sont uniquement : configuration, integration, execution, human_review, verification, maintenance, report_production.

Aucun juge LLM n'entre dans le verdict officiel.
