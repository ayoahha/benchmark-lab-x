---
title: Rapport interne de décision M10.2
status: ABSTENTION
style_gate: pass
---

# Rapport interne de décision M10.2

## Besoin et périmètre

Comparer les configurations du panel V0 sur les seules preuves officielles disponibles afin d'éclairer une décision, sans fabriquer de donnée absente.

Ce rapport V0 est produit hors ligne. Il reprend les faits de M10.1 sans appel candidat ou fournisseur, sans retry, sans dépense et sans juge fantôme. Les valeurs `INCONNU` et `NON_DEFINI` restent littérales. Une règle `DECIDED` ou une valeur `EXPECTED` n'est jamais présentée comme `OBSERVED`.

## Panel et sorties

| Configuration | Emplacement | État officiel | Sortie candidate |
| --- | --- | --- | --- |
| `grok46_xai_build_oauth` | `ACQ-GROK46-PRIMARY-001` | `CANDIDATE_NOT_ACCEPTABLE` | `AVAILABLE_AND_AUTOMATICALLY_REJECTED` |
| `kimi_k3_cursor_cli` | `ACQ-KIMIK3-PRIMARY-001` | `HARNESS_ERROR` | `ABSENT_NOT_RECONSTRUCTED` |

La sortie Grok disponible a reçu le verdict automatique `CANDIDATE_NOT_ACCEPTABLE`. La sortie Kimi est absente après `HARNESS_ERROR`; aucune candidate n'a été reconstruite.

## Métriques officielles

| Configuration | Acceptation officielle | Couverture | Coût fournisseur total | Coût par sortie officiellement acceptable | Latence préenregistrée |
| --- | ---: | ---: | --- | --- | --- |
| `grok46_xai_build_oauth` | `0/1` | `1/1` | `INCONNU` | `NON_DEFINI` | `382217` ms |
| `kimi_k3_cursor_cli` | `NON_DEFINI` (`0/0`, `NON_DEFINI`) | `0/1` | `INCONNU` | `NON_DEFINI` | `INCONNU` |
| Agrégé | `0/1` | `1/2` | `INCONNU` | `NON_DEFINI` | non agrégé |

L'effort humain est séparé du coût fournisseur et reste `INCONNU`. Les 43 509 ms de Kimi décrivent une durée technique terminale après `HARNESS_ERROR`; ils sont exclus de l'axe de latence Pareto.

## Provenance, fraîcheur et incidents

- Grok : identité servie et provenance `INCONNU`; fraîcheur `INCONNU`; incident `MISSING_OBSERVATION`.
- Kimi : identité servie et provenance `INCONNU`; fraîcheur `INCONNU`; incident `HARNESS_ERROR`.
- Le coût fournisseur total reste `INCONNU`; aucune valeur de remplacement n'est imputée.

## Front de Pareto

Les trois axes verrouillés sont exactement :

1. `OFFICIAL_ACCEPTANCE_RATE`, direction `MAXIMIZE`;
2. `SUPPLIER_COST_PER_OFFICIALLY_ACCEPTABLE_OUTPUT`, direction `MINIMIZE`;
3. `LATENCY_UNDER_PREREGISTERED_RULE`, direction `MINIMIZE`.

Le statut est `FULL_THREE_AXIS_FRONT_NOT_COMPUTABLE`. Le coût par sortie acceptable est `NON_DEFINI` pour les deux configurations, et la latence Kimi est `INCONNU`. Le front complet ne peut donc pas être calculé.

## Conclusion

Conclusion : `ABSTENTION`.

- recommandation : `NOT_PRODUCED`;
- gagnant : `NOT_PRODUCED`;
- score global : `FORBIDDEN`.

L'abstention est imposée par les preuves manquantes ou insuffisantes suivantes :

- `INCOMPLETE_COVERAGE`
- `SERVED_IDENTITY_PROVENANCE_INCONNU`
- `FRESHNESS_INCONNU`
- `SUPPLIER_COST_TOTAL_INCONNU`
- `SUPPLIER_COST_PER_OFFICIALLY_ACCEPTABLE_OUTPUT_NON_DEFINI`
- `LATENCY_KIMI_INCONNU`
- `ABSENT_OR_NON_DECISIVE_OWNER_PREFERENCE`

Actions humaines possibles, sans valeur de remplacement :

- Décider de conserver l'abstention et de ne sélectionner aucune configuration.
- Autoriser séparément une future collecte des preuves manquantes, sans imputer de valeur de remplacement.
- Fournir séparément une préférence propriétaire explicite seulement après obtention de trois axes complets et comparables.

## Provenance et commande de régénération

- `M6_5_DECISION_POLICY` : `tasks/dev/pre-cadrage-entretien-client/campagne-v0/politique-decision-v1/politique-decision.json`; SHA-256 `c378f180f93cb9f2ad481137618a8cd1fe2077f97389283ab13567fe6b857000`; source datée `2026-08-20T12:32:56Z`
- `M10_1_LINKED_INPUTS` : `tasks/dev/pre-cadrage-entretien-client/campagne-v0/metriques-decision-m10-1-v1/entrees-liees.json`; SHA-256 `387613e29d9656e8f830b474a4d449cefbfb1319db1313027fdf6a7862294f2d`; source datée `2026-08-21T09:54:37Z`
- `M10_1_METRICS_TABLE` : `tasks/dev/pre-cadrage-entretien-client/campagne-v0/metriques-decision-m10-1-v1/table-metriques.json`; SHA-256 `3a8fd94da674a962619b08450a89381634aa5a5cdad5eeed742af5ea2566e6ab`; source datée `2026-08-21T09:54:37Z`
- `M10_1_CALCULATION_RECEIPT` : `tasks/dev/pre-cadrage-entretien-client/campagne-v0/metriques-decision-m10-1-v1/recu-calcul.json`; SHA-256 `a3e12939dfb2b879c51220931fe58efb1354d2d89c5469c739fbfa8b68806fd0`; source datée `2026-08-21T09:54:37Z`

Commande exacte :

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 /opt/homebrew/bin/python3.13 tasks/dev/pre-cadrage-entretien-client/campagne-v0/rapport-decision-m10-2-v1/generer_rapport.py --input tasks/dev/pre-cadrage-entretien-client/campagne-v0/rapport-decision-m10-2-v1/entrees-liees.json
```
