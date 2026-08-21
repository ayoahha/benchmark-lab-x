#!/usr/bin/env python3
"""Génère le rapport interne M10.2 sur stdout à partir de preuves liées."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

BASE = "50b667ed4705bcfff4bdb733308a38927e041517"
CONTRACT = "12951f130eff73e56156ca242051978b8c1a5019d4c10ae842211a5820f7b31b"
ROOTS = {"M6.5": "c378f180f93cb9f2ad481137618a8cd1fe2077f97389283ab13567fe6b857000", "M10.1": "06c1072c2e1b3c49289387295c1a79b52a2e1d4e1f5fc93bec5f229b7a9c31c9"}
AXES = [
    {"metric": "OFFICIAL_ACCEPTANCE_RATE", "direction": "MAXIMIZE"},
    {"metric": "SUPPLIER_COST_PER_OFFICIALLY_ACCEPTABLE_OUTPUT", "direction": "MINIMIZE"},
    {"metric": "LATENCY_UNDER_PREREGISTERED_RULE", "direction": "MINIMIZE"},
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"HOLD_DECISION_REPORT: {message}")


def repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    raise SystemExit("HOLD_DECISION_REPORT: repository root not found")


def validate_sources(repo: Path, bindings: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    roles = {item["role"]: item for item in bindings}
    require(len(bindings) == 4 and set(roles) == {"M6_5_DECISION_POLICY", "M10_1_LINKED_INPUTS", "M10_1_METRICS_TABLE", "M10_1_CALCULATION_RECEIPT"}, "source bindings mismatch")
    for item in bindings:
        path = repo / item["path"]
        require(path.is_file(), f"missing source: {item['path']}")
        raw = path.read_bytes()
        require(len(raw) == item["bytes"], f"size mismatch: {item['path']}")
        require(hashlib.sha256(raw).hexdigest() == item["sha256"], f"hash mismatch: {item['path']}")
        require(bool(item["source_date"]), f"date missing: {item['path']}")
    return roles


def validate_evidence(repo: Path, roles: dict[str, dict[str, Any]], facts: dict[str, Any]) -> None:
    policy = json.loads((repo / roles["M6_5_DECISION_POLICY"]["path"]).read_text())
    table = json.loads((repo / roles["M10_1_METRICS_TABLE"]["path"]).read_text())
    receipt = json.loads((repo / roles["M10_1_CALCULATION_RECEIPT"]["path"]).read_text())
    require(policy["pareto"]["axes"] == AXES and policy["pareto"]["global_score"] == "FORBIDDEN" and policy["pareto"]["preference"] == "ABSENT_VOLUNTARILY", "M6.5 rules mismatch")
    require(table["pareto"]["axes"] == AXES and table["pareto"]["status"] == "FULL_THREE_AXIS_FRONT_NOT_COMPUTABLE", "M10.1 Pareto mismatch")
    require(receipt["calculation_root"]["sha256"] == ROOTS["M10.1"], "M10.1 root mismatch")
    require(table["decision_outputs"] == {"global_score": "FORBIDDEN", "m10_2_recommendation": "NOT_PRODUCED", "winner": "NOT_PRODUCED"}, "M10.1 decision outputs mismatch")
    configs = {item["configuration_id"]: item for item in table["configurations"]}
    require(set(configs) == {"grok46_xai_build_oauth", "kimi_k3_cursor_cli"}, "panel mismatch")
    grok, kimi = configs["grok46_xai_build_oauth"], configs["kimi_k3_cursor_cli"]
    require((grok["official_outcome"], grok["official_acceptance_rate"]["exact_fraction"], grok["coverage"]["exact_fraction"]) == ("CANDIDATE_NOT_ACCEPTABLE", "0/1", "1/1"), "Grok facts mismatch")
    require(kimi["official_outcome"] == "HARNESS_ERROR" and (kimi["official_acceptance_rate"]["numerator"], kimi["official_acceptance_rate"]["denominator"], kimi["official_acceptance_rate"]["state"]) == (0, 0, "NON_DEFINI") and kimi["coverage"]["exact_fraction"] == "0/1", "Kimi facts mismatch")
    aggregate = table["aggregate"]
    require((aggregate["official_acceptance_rate"]["exact_fraction"], aggregate["coverage"]["exact_fraction"], aggregate["supplier_cost_total"]["state"], aggregate["supplier_cost_per_officially_acceptable_output"]["state"]) == ("0/1", "1/2", "INCONNU", "NON_DEFINI"), "aggregate facts mismatch")
    decision = facts["decision"]
    require(facts["pareto"]["axes"] == AXES and facts["pareto"]["status"] == "FULL_THREE_AXIS_FRONT_NOT_COMPUTABLE", "report Pareto mismatch")
    require((decision["conclusion"], decision["recommendation"], decision["winner"], decision["global_score"]) == ("ABSTENTION", "NOT_PRODUCED", "NOT_PRODUCED", "FORBIDDEN"), "report decision mismatch")


def render(data: dict[str, Any]) -> str:
    facts = data["report_facts"]
    grok, kimi = facts["panel"]
    aggregate, decision = facts["aggregate"], facts["decision"]
    reasons = "\n".join(f"- `{reason}`" for reason in decision["reasons"])
    actions = "\n".join(f"- {action}" for action in decision["possible_human_actions"])
    sources = "\n".join(f"- `{item['role']}` : `{item['path']}`; SHA-256 `{item['sha256']}`; source datée `{item['source_date']}`" for item in data["source_bindings"])
    return f"""---
title: Rapport interne de décision M10.2
status: ABSTENTION
style_gate: pass
---

# Rapport interne de décision M10.2

## Besoin et périmètre

{facts['need']}

Ce rapport V0 est produit hors ligne. Il reprend les faits de M10.1 sans appel candidat ou fournisseur, sans retry, sans dépense et sans juge fantôme. Les valeurs `INCONNU` et `NON_DEFINI` restent littérales. Une règle `DECIDED` ou une valeur `EXPECTED` n'est jamais présentée comme `OBSERVED`.

## Panel et sorties

| Configuration | Emplacement | État officiel | Sortie candidate |
| --- | --- | --- | --- |
| `{grok['configuration_id']}` | `{grok['planned_slot']}` | `{grok['official_outcome']}` | `{grok['candidate_output']}` |
| `{kimi['configuration_id']}` | `{kimi['planned_slot']}` | `{kimi['official_outcome']}` | `{kimi['candidate_output']}` |

La sortie Grok disponible a reçu le verdict automatique `CANDIDATE_NOT_ACCEPTABLE`. La sortie Kimi est absente après `HARNESS_ERROR`; aucune candidate n'a été reconstruite.

## Métriques officielles

| Configuration | Acceptation officielle | Couverture | Coût fournisseur total | Coût par sortie officiellement acceptable | Latence préenregistrée |
| --- | ---: | ---: | --- | --- | --- |
| `{grok['configuration_id']}` | `{grok['official_acceptance_rate']['exact_fraction']}` | `{grok['coverage']['exact_fraction']}` | `{grok['supplier_cost_total']}` | `{grok['supplier_cost_per_officially_acceptable_output']}` | `{grok['latency_under_preregistered_rule_ms']}` ms |
| `{kimi['configuration_id']}` | `{kimi['official_acceptance_rate']['exact_fraction']}` (`0/0`, `{kimi['official_acceptance_rate']['state']}`) | `{kimi['coverage']['exact_fraction']}` | `{kimi['supplier_cost_total']}` | `{kimi['supplier_cost_per_officially_acceptable_output']}` | `{kimi['latency_under_preregistered_rule_ms']}` |
| Agrégé | `{aggregate['official_acceptance_rate']['exact_fraction']}` | `{aggregate['coverage']['exact_fraction']}` | `{aggregate['supplier_cost_total']}` | `{aggregate['supplier_cost_per_officially_acceptable_output']}` | non agrégé |

L'effort humain est séparé du coût fournisseur et reste `{aggregate['human_effort']}`. Les 43 509 ms de Kimi décrivent une durée technique terminale après `HARNESS_ERROR`; ils sont exclus de l'axe de latence Pareto.

## Provenance, fraîcheur et incidents

- Grok : identité servie et provenance `{grok['served_identity_and_provenance']}`; fraîcheur `{grok['freshness']}`; incident `{grok['incident']}`.
- Kimi : identité servie et provenance `{kimi['served_identity_and_provenance']}`; fraîcheur `{kimi['freshness']}`; incident `{kimi['incident']}`.
- Le coût fournisseur total reste `{aggregate['supplier_cost_total']}`; aucune valeur de remplacement n'est imputée.

## Front de Pareto

Les trois axes verrouillés sont exactement :

1. `OFFICIAL_ACCEPTANCE_RATE`, direction `MAXIMIZE`;
2. `SUPPLIER_COST_PER_OFFICIALLY_ACCEPTABLE_OUTPUT`, direction `MINIMIZE`;
3. `LATENCY_UNDER_PREREGISTERED_RULE`, direction `MINIMIZE`.

Le statut est `{facts['pareto']['status']}`. Le coût par sortie acceptable est `NON_DEFINI` pour les deux configurations, et la latence Kimi est `INCONNU`. Le front complet ne peut donc pas être calculé.

## Conclusion

Conclusion : `{decision['conclusion']}`.

- recommandation : `{decision['recommendation']}`;
- gagnant : `{decision['winner']}`;
- score global : `{decision['global_score']}`.

L'abstention est imposée par les preuves manquantes ou insuffisantes suivantes :

{reasons}

Actions humaines possibles, sans valeur de remplacement :

{actions}

## Provenance et commande de régénération

{sources}

Commande exacte :

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 /opt/homebrew/bin/python3.13 tasks/dev/pre-cadrage-entretien-client/campagne-v0/rapport-decision-m10-2-v1/generer_rapport.py --input tasks/dev/pre-cadrage-entretien-client/campagne-v0/rapport-decision-m10-2-v1/entrees-liees.json
```
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args()
    data = json.loads(args.input.read_bytes())
    require(data["scope"]["git_base"] == BASE and data["scope"]["frozen_contract_sha256"] == CONTRACT, "scope mismatch")
    require(data["authority_roots"] == ROOTS, "authority roots mismatch")
    authority = data["issue_authority"]
    require((authority["comment_database_id"], authority["comment_node_id"], authority["author"], authority["author_association"], authority["body_sha256"]) == (5369559464, "IC_kwDOTswBxM8AAAABQAz5qA", "ayoahha", "OWNER", "352d77f30b567c06c6227d837991a7eab332aa202052de95a6056a24a53f2bc8"), "GO authority mismatch")
    require(data["boundaries"] == {"candidate_content_copied": False, "no_imputation": True, "decided_or_expected_promoted_to_observed": False, "candidate_campaign_calls": 0, "provider_campaign_calls": 0, "retries": 0, "spend_usd": 0, "ghost_judges": 0, "m11_actions": 0}, "boundary mismatch")
    repo = repo_root(args.input.resolve().parent)
    roles = validate_sources(repo, data["source_bindings"])
    validate_evidence(repo, roles, data["report_facts"])
    print(render(data), end="")


if __name__ == "__main__":
    main()
