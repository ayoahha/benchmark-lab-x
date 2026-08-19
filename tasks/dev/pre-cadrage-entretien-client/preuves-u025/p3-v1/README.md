---
style_gate: pass
---

# Lock P3 V4

État : `REVIEW_READY_NO_EXECUTION_AUTHORITY`.

Ce paquet amende le lock V3 selon la correction propriétaire publiée dans #61. Les réglages ZDR, le solde, l'auto-recharge, les crédits supplémentaires et la facturation du compte fournisseur relèvent du propriétaire. Le projet ne les vérifie pas et ils ne bloquent pas l'exécution. Il n'autorise aucun appel, aucune tentative fournisseur, aucune campagne, aucune dépense ni aucun retry.

La preuve canonique est `proof-root.json`. Toute dérive d'un fichier couvert par `checksums.json` invalide le lock et les futurs GO qui le référencent.

Les déclarations d'un appelant ne font pas autorité. Chacun des quatre GO doit être un artefact adressé par contenu, lié au lock, à la tentative et à l'autorité, vérifié avant tout réseau. Une clé ou une empreinte GO absente ferme en `INCONNU` ou `HOLD`.

Attendu, demandé et observé restent séparés. Une observation absente vaut `INCONNU`. L'identité servie n'est jamais déduite de la demande.

Les autorités GitHub sont dans `github-authorities.json`, sans corps. La porte exécutable `controls/verify_evidence_gate.py` authentifie ces autorités et vérifie que les réglages de compte restent hors du périmètre du projet. Une attente ou une demande ne devient pas une observation.

Le manifeste d'ordre publie l'engagement du sel, le digest du mapping et la cardinalité 6. Les positions 1 à 6 sont figées en privé. La garde `controls/verify_order.py` recharge les objets privés, recalcule HMAC, prouve la permutation et la chaîne avant fournisseur. La révélation du sel suit le gel des verdicts humains. Le reçu de genèse reste `zero-execution-receipt.json`.

Les plafonds de dépense supplémentaire à zéro n'impliquent pas un coût fournisseur nul. Le coût réel, la dépense supplémentaire et l'allocation de pool restent distincts.

Les composantes d'effort sont uniquement : configuration, integration, execution, human_review, verification, maintenance, report_production.

Aucun juge LLM n'entre dans le verdict officiel.
