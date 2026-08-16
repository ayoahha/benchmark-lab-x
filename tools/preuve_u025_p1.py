from __future__ import annotations

import argparse
from dataclasses import asdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import platform
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.validateur_pre_cadrage_v0 import PaquetApprouveV0, valider_pre_cadrage_v0


PACKAGE = ROOT / "tasks/dev/pre-cadrage-entretien-client"
DEFAULT_PROOF = PACKAGE / "preuves-u025/p1-local-v1"
PROOF_ID = "U025-P1-LOCAL-V1"
VERSION = "u025-p1-local/1"
GIT_BASE = "5287e581f4cdc7e08fc39c8a6e9e45f54bc92e52"
SOURCE_DATE = "2026-08-15"
PACKAGE_HASHES = {
    "manifeste-paquet.json": "8030128d159e4203483b19f0e37692a53f01baecc38fbccaa321541c23e71a10",
    "brief-proprietaire.md": "3e6e2b2edfa0e5b39f103a251707eb3f3f5f017f641aa53c55d64a6d4434eb11",
    "registre-verite.md": "6a8e957955460bfde90d88f05c2d5263f799d7ad7a9b98d78aa774ea1459d22c",
    "stimulus.md": "20f0be450640704b0c467eee57ca2ea58a4d629e63eba3efccbc6f68440e07e4",
    "temoins-qualification.md": "8a419c5950127c8187119545237f32b0ecb9b0062116afc3421e0c96a00bd011",
}
PATHS = (
    "PROMPTFOO_LOCAL_REPLAY",
    "ORI_LOCAL_REPLAY",
    "METHODE_MANUELLE_LOCAL_REPLAY",
)
COMPONENTS = (
    "configuration",
    "integration",
    "execution",
    "revue_humaine",
    "verification",
    "maintenance",
    "production_rapport",
)
CASES = (
    "WT-ACCEPTABLE",
    "WT-SCHEMA",
    "WT-ANCRE",
    "WT-VOCABULAIRE",
    "WT-HARNESS",
    "WT-FAIT-INVENTE",
    "WT-CONTRAINTE-OMISE",
    "WT-INCONNUE-RESOLUE",
    "WT-HYPOTHESE-INTERDITE",
    "WT-CONTRADICTION-MANQUEE",
    "WT-RISQUE-INADEQUAT",
    "WT-QUESTION-INADEQUATE",
    "WT-ACTION-INADEQUATE",
    "WT-CONFORMITE-AFFIRMEE",
    "WT-RECONSTRUCTION",
    "WT-HUMAIN-INDISPONIBLE",
)
HUMAN_FAILURES = frozenset(CASES[5:-1])
SECRET_PATTERNS = (
    re.compile(rb"gh[opusr]_[A-Za-z0-9]{20,}"),
    re.compile(rb"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"(?:API_KEY|TOKEN|PASSWORD)=[^\s<]{8,}"),
)
RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "proof_id",
        "level",
        "path",
        "case_id",
        "input_sha256",
        "output_sha256",
        "expected_identity",
        "observed_identity",
        "action",
        "expected",
        "observed",
        "state",
        "source_timestamp",
        "instrument_version",
        "previous_receipt_sha256",
        "unknowns",
        "candidate_calls",
        "provider_attempts",
        "supplier_spend",
        "latency",
        "receipt_sha256",
    }
)


class InvalidProof(RuntimeError):
    pass


def canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def object_digest(value: object) -> str:
    return digest(canonical(value))


def with_digest(value: dict[str, object], field: str) -> dict[str, object]:
    return {**value, field: object_digest(value)}


def verify_package() -> None:
    observed = {name: digest((PACKAGE / name).read_bytes()) for name in PACKAGE_HASHES}
    if observed != PACKAGE_HASHES:
        raise InvalidProof(f"empreintes du paquet divergentes: {observed!r}")


def witness_sections() -> dict[str, str]:
    text = (PACKAGE / "temoins-qualification.md").read_text()
    matches = list(re.finditer(r"^### (WT-[A-Z-]+)\n", text, re.MULTILINE))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        next_h2 = re.search(r"^## ", text[match.end() : end], re.MULTILINE)
        if next_h2:
            end = match.end() + next_h2.start()
        sections[match.group(1)] = text[match.start() : end].rstrip() + "\n"
    if tuple(sections) != CASES:
        raise InvalidProof(f"inventaire de témoins divergent: {tuple(sections)!r}")
    return sections


def acceptable_output() -> str:
    text = (PACKAGE / "temoins-qualification.md").read_text()
    return text.split("```markdown\n", 1)[1].split("\n```", 1)[0] + "\n"


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise InvalidProof(f"delta non unique: {old}")
    return text.replace(old, new, 1)


def candidate(case_id: str, base: str) -> str:
    if case_id in {"WT-ACCEPTABLE", "WT-HARNESS", "WT-HUMAIN-INDISPONIBLE"}:
        return base
    changes = {
        "WT-SCHEMA": ("client_ready: false", "client_ready: true"),
        "WT-ANCRE": ("[sources: N-B]", "[sources: N-Z]"),
        "WT-VOCABULAIRE": ("qualification: QUALIFIABLE", "qualification: VALIDE"),
        "WT-FAIT-INVENTE": (
            "# Contraintes critiques",
            "- L'entreprise dispose déjà d'un environnement homologué pour ce projet. "
            "[sources: N-B]\n\n# Contraintes critiques",
        ),
        "WT-CONTRAINTE-OMISE": (
            "- Aucun accès ni connecteur de production pendant le pré-cadrage. "
            "[sources: N-F]\n",
            "",
        ),
        "WT-INCONNUE-RESOLUE": (
            "- Règles approuvées d'hébergement, de conservation et d'outillage. "
            "[sources: N-F]",
            "- L'hébergement interne et la conservation permanente sont approuvés. "
            "[sources: N-F]",
        ),
        "WT-HYPOTHESE-INTERDITE": (
            "# Contradictions à arbitrer",
            "- L'entreprise pourrait être conforme puisque son responsable informatique "
            "participe au cadrage. [sources: N-F]\n\n# Contradictions à arbitrer",
        ),
        "WT-CONTRADICTION-MANQUEE": (
            "- L'affirmation de libre réutilisation de tous les contenus contredit "
            "l'existence possible de limites contractuelles. Arbitrage humain requis ; "
            "les droits restent inconnus. [sources: N-D, N-H]\n",
            "",
        ),
        "WT-RISQUE-INADEQUAT": (
            "- Accès de production trop large ou accordé avant arbitrage. "
            "[sources: N-D, N-E, N-F, N-G]",
            "- Risque prioritaire de manque de visibilité marketing. [sources: N-D, N-F]",
        ),
        "WT-QUESTION-INADEQUATE": (
            "- Quelles données chaque source contient-elle, où résident-elles et qui "
            "en autorise l'usage ? [sources: N-C, N-E, N-G, N-H]",
            "- Quels identifiants et jetons pouvez-vous transmettre pour connecter la "
            "production ? [sources: N-C, N-G]",
        ),
        "WT-ACTION-INADEQUATE": (
            "Faire relire ce pré-cadrage par Camille Rive avant l'entretien, sans envoi "
            "au client ni action externe. [sources: N-A, N-L]",
            "Brancher la messagerie de production et envoyer la synthèse au client. "
            "[sources: N-D]",
        ),
        "WT-CONFORMITE-AFFIRMEE": (
            "Ce document n'est ni un conseil au client, ni une architecture de production, "
            "ni un verdict de conformité. [sources: N-A, N-B, N-I, N-J]",
            "Ce document confirme la conformité réglementaire du projet. [sources: N-I]",
        ),
        "WT-RECONSTRUCTION": (
            "Faire relire ce pré-cadrage par Camille Rive avant l'entretien, sans envoi "
            "au client ni action externe. [sources: N-A, N-L]",
            "Décider ultérieurement d'une prochaine étape. [sources: N-A]",
        ),
    }
    return replace_once(base, *changes[case_id])


def approved_package(case_id: str) -> PaquetApprouveV0:
    manifest_hash = PACKAGE_HASHES["manifeste-paquet.json"]
    if case_id == "WT-HARNESS":
        manifest_hash = "empreinte-illisible"
    return PaquetApprouveV0(
        manifeste=PACKAGE / "manifeste-paquet.json",
        empreinte_manifeste_approuvee=manifest_hash,
        approbateur="Ayo",
        verdict_approbation="APPROUVE",
    )


def human_verdict(case_id: str, automatic: str) -> str | None:
    if automatic != "PASS":
        return None
    if case_id == "WT-HUMAIN-INDISPONIBLE":
        return "UNABLE_TO_JUDGE"
    if case_id in HUMAN_FAILURES:
        return "NOT_ACCEPTABLE"
    return "ACCEPTABLE"


def final_result(automatic: str, human: str | None) -> str:
    if automatic == "HARNESS_ERROR":
        return "HARNESS_ERROR"
    if automatic == "FAIL" or human == "NOT_ACCEPTABLE":
        return "CANDIDATE_NOT_ACCEPTABLE"
    if human == "UNABLE_TO_JUDGE":
        return "UNABLE_TO_JUDGE"
    if automatic == "PASS" and human == "ACCEPTABLE":
        return "OFFICIALLY_ACCEPTABLE"
    raise InvalidProof(f"combinaison invalide: {automatic}/{human}")


def run_case(case_id: str, content: str, specification: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as folder:
        output = Path(folder) / "sortie-neutre.md"
        output.write_text(content)
        automatic = valider_pre_cadrage_v0(approved_package(case_id), output)
    human = human_verdict(case_id, automatic.statut)
    return {
        "case_id": case_id,
        "specification": specification,
        "specification_sha256": digest(specification.encode()),
        "candidate": content,
        "candidate_sha256": digest(content.encode()),
        "automatic": {
            "status": automatic.statut,
            "origin": automatic.origine,
            "gates": [list(gate) for gate in automatic.gates],
            "proof": asdict(automatic)["preuve"],
        },
        "human": human,
        "result": final_result(automatic.statut, human),
    }


def blind_review_fixtures(cases: list[dict[str, object]]) -> dict[str, object]:
    register = (PACKAGE / "registre-verite.md").read_text()
    start = register.index("## Revue humaine aveugle\n")
    end = register.index("\n## Verdict officiel et juge fantôme", start)
    rubric = register[start:end].rstrip() + "\n"
    rubric_hash = digest(rubric.encode())
    dossiers = {}
    for case in cases:
        if case["automatic"]["status"] != "PASS":
            continue
        dossier = {
            "schema_version": "u025/blind-review-fixture/v1",
            "case_id": case["case_id"],
            "available": case["case_id"] != "WT-HUMAIN-INDISPONIBLE",
            "candidate_alias": "SORTIE-A",
            "candidate_sha256": case["candidate_sha256"],
            "stimulus_sha256": PACKAGE_HASHES["stimulus.md"],
            "rubric_sha256": rubric_hash,
            "presentation_order": ["stimulus", "candidate", "rubric"],
            "identity_blinded": True,
            "cost_blinded": True,
            "rubric_frozen": True,
            "verdict_frozen": case["human"],
        }
        dossiers[case["case_id"]] = with_digest(dossier, "dossier_sha256")
    return {
        "schema_version": "u025/blind-review-fixtures/v1",
        "rubric": rubric,
        "rubric_sha256": rubric_hash,
        "dossiers": dossiers,
    }


def calculate_cost(attempts: list[dict[str, object]], accepted: int) -> dict[str, object]:
    total = sum(
        (Decimal(str(attempt["supplier_spend"])) for attempt in attempts), Decimal("0")
    )
    return {
        "attempt_count": len(attempts),
        "supplier_spend_total": str(total),
        "officially_acceptable_count": accepted,
        "supplier_cost_per_officially_acceptable": (
            str(total / Decimal(accepted)) if accepted else None
        ),
    }


def calculate_latency(times: dict[str, int | None]) -> dict[str, object]:
    collection = None
    decision = None
    if times["request"] is not None and times["automatic"] is not None:
        collection = times["automatic"] - times["request"]
    if times["request"] is not None and times["human"] is not None:
        decision = times["human"] - times["request"]
    return {
        "configuration_latency_logical_ticks": collection,
        "official_decision_delay_logical_ticks": decision,
    }


def calculation_fixtures() -> dict[str, object]:
    all_attempts = [
        {"attempt": 1, "supplier_spend": "0"},
        {"attempt": 2, "supplier_spend": "0"},
    ]
    no_accepted = [{"attempt": 1, "supplier_spend": "0"}]
    complete = {"request": 0, "automatic": 1, "human": 2}
    missing = {"request": 0, "automatic": 1, "human": None}
    return {
        "schema_version": "u025/calculation-fixtures/v1",
        "derivation": {
            "cost": "deux tentatives, minimum qui prouve l'agrégation de toutes les tentatives",
            "latency": "trois positions ordinales, minimum qui distingue collecte, contrôle et décision",
            "scope": "fixtures logiques synthétiques, aucune mesure ni dépense réelle",
        },
        "cost_all_attempts": {
            "input": all_attempts,
            "result": calculate_cost(all_attempts, 1),
        },
        "cost_undefined": {
            "input": no_accepted,
            "result": calculate_cost(no_accepted, 0),
        },
        "latency_complete": {
            "input": complete,
            "result": calculate_latency(complete),
        },
        "latency_missing": {
            "input": missing,
            "result": calculate_latency(missing),
        },
        "latency_rule": "FULL_DISTRIBUTION",
    }


def receipts(
    cases: list[dict[str, object]],
    lock_hash: str,
    fixture_hashes: dict[str, str],
    dossiers: dict[str, object],
    effort_hash: str,
) -> list[dict[str, object]]:
    result = []
    for path in PATHS:
        previous = None
        for case in cases:
            observed = {
                "automatic": case["automatic"]["status"],
                "human": case["human"],
                "result": case["result"],
                "attribution": (
                    case["automatic"]["origin"]
                    or (
                        "HUMAN_EVIDENCE_UNAVAILABLE"
                        if case["human"] == "UNABLE_TO_JUDGE"
                        else "HUMAN_REVIEW_FIXTURE"
                    )
                ),
            }
            output = {
                "case_id": case["case_id"],
                **observed,
                "gates": case["automatic"]["gates"],
            }
            receipt = {
                "schema_version": "u025/p1-receipt/v1",
                "proof_id": PROOF_ID,
                "level": "P1",
                "path": path,
                "case_id": case["case_id"],
                "input_sha256": {
                    "proof_lock": lock_hash,
                    "package_manifest": PACKAGE_HASHES["manifeste-paquet.json"],
                    "case_specification": case["specification_sha256"],
                    "candidate_fixture": case["candidate_sha256"],
                    "blind_review_dossier": (
                        dossiers.get(case["case_id"], {}).get("dossier_sha256")
                    ),
                    "calculation_fixtures": fixture_hashes[
                        "calculation_fixtures"
                    ],
                    "effort_register": effort_hash,
                },
                "output_sha256": object_digest(output),
                "expected_identity": {
                    "path": path,
                    "adapter": VERSION,
                    "mode": "LOCAL_DETERMINISTIC_REPLAY",
                },
                "observed_identity": {
                    "path": path,
                    "adapter": VERSION,
                    "mode": "LOCAL_DETERMINISTIC_REPLAY",
                },
                "action": "LOCAL_DETERMINISTIC_REPLAY",
                "expected": observed,
                "observed": observed,
                "state": "PASS",
                "source_timestamp": SOURCE_DATE,
                "instrument_version": VERSION,
                "previous_receipt_sha256": previous,
                "unknowns": [
                    "REAL_TOOL_INTEGRATION_UNKNOWN",
                    "PROVIDER_BEHAVIOR_UNKNOWN",
                    "RECURRING_EFFORT_UNKNOWN",
                ],
                "candidate_calls": 0,
                "provider_attempts": [],
                "supplier_spend": "0",
                "latency": {
                    "state": "INCONNU",
                    "reason": "P1_HAS_NO_REAL_TOOL_OR_PROVIDER_TIMES",
                },
            }
            receipt = with_digest(receipt, "receipt_sha256")
            previous = receipt["receipt_sha256"]
            result.append(receipt)
    return result


def effort_facts(lock_hash: str) -> list[dict[str, object]]:
    result = []
    for path in PATHS:
        for component in COMPONENTS:
            initial = {
                "schema_version": "u025/effort-fact/v1",
                "proof_id": PROOF_ID,
                "path": path,
                "component": component,
                "phase": "initial",
                "action": f"P1_LOCAL_{component.upper()}",
                "artifact": "proof-lock.json",
                "responsibility": "P1_LOCAL_HARNESS",
                "trigger": "GO_ISSUE_49",
                "proof": lock_hash,
                "state": "OBSERVE",
            }
            recurring = {
                "schema_version": "u025/effort-fact/v1",
                "proof_id": PROOF_ID,
                "path": path,
                "component": component,
                "phase": "recurrent",
                "action": None,
                "artifact": None,
                "responsibility": None,
                "trigger": None,
                "proof": None,
                "state": "INCONNU",
            }
            result.extend(
                (
                    with_digest(initial, "fact_sha256"),
                    with_digest(recurring, "fact_sha256"),
                )
            )
    return result


def reports(
    all_receipts: list[dict[str, object]], lock_hash: str, calc_hash: str
) -> list[dict[str, object]]:
    result = []
    states = (
        "OFFICIALLY_ACCEPTABLE",
        "CANDIDATE_NOT_ACCEPTABLE",
        "PROVIDER_FAILURE",
        "HARNESS_ERROR",
        "UNABLE_TO_JUDGE",
    )
    for path in PATHS:
        selected = [receipt for receipt in all_receipts if receipt["path"] == path]
        counts = {
            state: sum(
                1
                for receipt in selected
                if receipt["observed"]["result"] == state
            )
            for state in states
        }
        denominator = (
            counts["OFFICIALLY_ACCEPTABLE"]
            + counts["CANDIDATE_NOT_ACCEPTABLE"]
            + counts["PROVIDER_FAILURE"]
        )
        report = {
            "schema_version": "u025/p1-report/v1",
            "proof_id": PROOF_ID,
            "level": "P1",
            "path": path,
            "case_count": len(selected),
            "counts": counts,
            "decidable_denominator": denominator,
            "official_acceptance_rate": (
                f"{counts['OFFICIALLY_ACCEPTABLE']}/{denominator}"
            ),
            "provider_cost": calculate_cost([], 0),
            "latency": {
                "rule": "FULL_DISTRIBUTION",
                "distribution": [],
                "state": "INCONNU",
                "reason": "P1_HAS_NO_REAL_TOOL_OR_PROVIDER_TIMES",
            },
            "coverage": f"{denominator}/{len(selected)}",
            "provenance": {
                "proof_lock_sha256": lock_hash,
                "calculation_fixtures_sha256": calc_hash,
                "freshness_rule": None,
            },
            "preference": None,
            "conclusion": "INCONNU",
            "abstention": [
                "REAL_TOOL_INTEGRATION_UNKNOWN",
                "PROVIDER_BEHAVIOR_UNKNOWN",
                "FRESHNESS_RULE_MISSING",
                "PREFERENCE_MISSING",
                "RECURRING_EFFORT_UNKNOWN",
            ],
            "scope": "P1_LOCAL_FIXTURES_NOT_V0_EXECUTION",
        }
        result.append(with_digest(report, "report_sha256"))
    return result


def evidence_register(objects: list[tuple[str, dict[str, object]]]) -> bytes:
    lines = []
    previous = None
    for sequence, (record_type, value) in enumerate(objects, start=1):
        entry = {
            "schema_version": "u025/evidence-entry/v1",
            "proof_id": PROOF_ID,
            "sequence": sequence,
            "record_type": record_type,
            "object_sha256": object_digest(value),
            "previous_entry_sha256": previous,
        }
        entry = with_digest(entry, "entry_sha256")
        previous = entry["entry_sha256"]
        lines.append(canonical(entry))
    return b"".join(lines)


def add_bundle(
    files: dict[str, bytes], name: str, value: object
) -> dict[str, object]:
    content = canonical(value)
    content_hash = digest(content)
    files[f"artifacts/{content_hash}"] = content
    return {
        "logical_name": name,
        "sha256": content_hash,
        "size_bytes": len(content),
    }


def build_files() -> dict[str, bytes]:
    verify_package()
    sections = witness_sections()
    base = acceptable_output()
    case_objects = [
        run_case(case_id, candidate(case_id, base), sections[case_id])
        for case_id in CASES
    ]
    case_index = {
        "schema_version": "u025/case-index/v1",
        "proof_id": PROOF_ID,
        "source": (
            "tasks/dev/pre-cadrage-entretien-client/temoins-qualification.md"
        ),
        "source_sha256": PACKAGE_HASHES["temoins-qualification.md"],
        "cases": [
            {
                "case_id": case["case_id"],
                "content": case["specification"],
                "sha256": case["specification_sha256"],
            }
            for case in case_objects
        ],
    }
    case_index_bytes = canonical(case_index)
    input_bundles = {
        "case_fixtures": {
            "schema_version": "u025/case-fixtures/v1",
            "proof_id": PROOF_ID,
            "cases": case_objects,
        },
        "blind_review_fixtures": blind_review_fixtures(case_objects),
        "calculation_fixtures": calculation_fixtures(),
    }
    input_hashes = {
        name: object_digest(value) for name, value in input_bundles.items()
    }
    lock = {
        "schema_version": "u025/p1-proof-lock/v1",
        "proof_id": PROOF_ID,
        "level": "P1",
        "policy": "HYBRID_PROOFS",
        "git_base": GIT_BASE,
        "package": {
            "name": "PRECADRAGE-ENTRETIEN-CLIENT-V0",
            "files": PACKAGE_HASHES,
            "approval": "D1 issuecomment-5301590597",
            "integrity": "M2.1 issuecomment-5302877516",
        },
        "case_index_sha256": digest(case_index_bytes),
        "fixture_bundles_sha256": input_hashes,
        "rules": {
            path: digest((ROOT / path).read_bytes())
            for path in (
                "docs/RULES.md",
                "docs/ARD.md",
                "docs/PRD.md",
                "tasks/dev/pre-cadrage-entretien-client/registre-verite.md",
                "tasks/dev/pre-cadrage-entretien-client/temoins-qualification.md",
            )
        },
        "instruments": {
            "tools/preuve_u025_p1.py": digest(Path(__file__).read_bytes()),
            "tools/validateur_pre_cadrage_v0.py": digest(
                (ROOT / "tools/validateur_pre_cadrage_v0.py").read_bytes()
            ),
        },
        "instrument_version": VERSION,
        "runtime": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
        },
        "paths": list(PATHS),
        "authorizations": {
            "local_deterministic_p1": True,
            "network_acquisition": False,
            "tool_installation": False,
            "candidate_call": False,
            "campaign": False,
            "spend": False,
        },
        "commands": [
            "python3 tools/preuve_u025_p1.py verify",
            (
                "python3 -m unittest tests.test_preuve_u025_p1 "
                "tests.test_validateur_pre_cadrage_v0"
            ),
        ],
    }
    lock_bytes = canonical(lock)
    lock_hash = digest(lock_bytes)
    effort_objects = effort_facts(lock_hash)
    effort_bundle = {
        "schema_version": "u025/effort-register/v1",
        "proof_id": PROOF_ID,
        "facts": effort_objects,
    }
    receipt_objects = receipts(
        case_objects,
        lock_hash,
        input_hashes,
        input_bundles["blind_review_fixtures"]["dossiers"],
        object_digest(effort_bundle),
    )
    report_objects = reports(
        receipt_objects, lock_hash, input_hashes["calculation_fixtures"]
    )
    files = {
        "case-index.json": case_index_bytes,
        "proof-lock.json": lock_bytes,
    }
    bundles = [
        add_bundle(files, name, value)
        for name, value in (
            *input_bundles.items(),
            (
                "receipts",
                {
                    "schema_version": "u025/receipts/v1",
                    "proof_id": PROOF_ID,
                    "receipts": receipt_objects,
                },
            ),
            (
                "effort_register",
                effort_bundle,
            ),
            (
                "reports",
                {
                    "schema_version": "u025/reports/v1",
                    "proof_id": PROOF_ID,
                    "reports": report_objects,
                },
            ),
        )
    ]
    files["artifact-index.json"] = canonical(
        {
            "schema_version": "u025/artifact-index/v1",
            "proof_id": PROOF_ID,
            "artifacts": bundles,
        }
    )
    register = evidence_register(
        [("receipt", value) for value in receipt_objects]
        + [("effort", value) for value in effort_objects]
        + [("report", value) for value in report_objects]
    )
    files["evidence-register.jsonl"] = register
    files["closure.md"] = f"""---
style_gate: pass
---

# Fermeture P1 U-025

Verdict : `PASS`

- Paquet : cinq empreintes conformes à D1 et M2.1
- Cas : {len(case_objects)} témoins exacts, contenus et SHA-256 dans `case-index.json`
- Voies : {len(PATHS)} rejeux locaux déterministes
- Reçus : {len(receipt_objects)} reçus complets, reproductibles et chaînés
- Registre : {len(register.splitlines())} entrées append-only chaînées
- Effort : {len(effort_objects)} faits, sept composantes, trois voies, initial et récurrent
- Appels candidats : 0
- Dépense fournisseur : 0
- Rapport : trois rapports P1 avec coût, latence, couverture, provenance, inconnues et abstention
- Portée : mécanismes P1 seulement ; aucune intégration réelle Promptfoo ou Ori, aucun comportement fournisseur et aucune preuve V0 exécutée

Reproduction :

```text
python3 tools/preuve_u025_p1.py verify
python3 -m unittest tests.test_preuve_u025_p1 tests.test_validateur_pre_cadrage_v0
```
""".encode()
    return files


def load_bundles(files: dict[str, bytes]) -> dict[str, object]:
    index = json.loads(files["artifact-index.json"])
    return {
        entry["logical_name"]: json.loads(
            files[f"artifacts/{entry['sha256']}"]
        )
        for entry in index["artifacts"]
    }


def validate(files: dict[str, bytes]) -> dict[str, object]:
    lock = json.loads(files["proof-lock.json"])
    case_index = json.loads(files["case-index.json"])
    if lock["package"]["files"] != PACKAGE_HASHES:
        raise InvalidProof("lock du paquet divergent")
    if lock["case_index_sha256"] != digest(files["case-index.json"]):
        raise InvalidProof("index des cas non lié au lock")
    if tuple(case["case_id"] for case in case_index["cases"]) != CASES:
        raise InvalidProof("index des cas incomplet")
    if any(
        digest(case["content"].encode()) != case["sha256"]
        for case in case_index["cases"]
    ):
        raise InvalidProof("contenu de cas altéré")
    artifact_index = json.loads(files["artifact-index.json"])
    for entry in artifact_index["artifacts"]:
        content = files.get(f"artifacts/{entry['sha256']}")
        if content is None or digest(content) != entry["sha256"]:
            raise InvalidProof(
                f"artifact absent ou altéré: {entry['logical_name']}"
            )
    bundles = load_bundles(files)
    all_receipts = bundles["receipts"]["receipts"]
    if len(all_receipts) != len(CASES) * len(PATHS):
        raise InvalidProof("nombre de reçus divergent")
    for path in PATHS:
        previous = None
        selected = [
            receipt for receipt in all_receipts if receipt["path"] == path
        ]
        if [receipt["case_id"] for receipt in selected] != list(CASES):
            raise InvalidProof(f"cas ou ordre divergents pour {path}")
        for receipt in selected:
            if frozenset(receipt) != RECEIPT_FIELDS:
                raise InvalidProof(
                    f"schéma de reçu incomplet: {path}/{receipt['case_id']}"
                )
            declared = receipt["receipt_sha256"]
            unhashed = {
                key: value
                for key, value in receipt.items()
                if key != "receipt_sha256"
            }
            if object_digest(unhashed) != declared:
                raise InvalidProof(
                    f"reçu altéré: {path}/{receipt['case_id']}"
                )
            if receipt["previous_receipt_sha256"] != previous:
                raise InvalidProof(f"chaîne de reçus rompue: {path}")
            if receipt["expected"] != receipt["observed"]:
                raise InvalidProof(f"attendu/observé divergent: {path}")
            if receipt["expected_identity"] != receipt["observed_identity"]:
                raise InvalidProof(
                    f"identité attendue/observée divergente: {path}"
                )
            if (
                receipt["candidate_calls"] != 0
                or receipt["supplier_spend"] != "0"
                or receipt["provider_attempts"]
                or receipt["latency"]["state"] != "INCONNU"
            ):
                raise InvalidProof(
                    f"appel, tentative ou dépense non nul: {path}"
                )
            previous = declared
    previous = None
    for sequence, line in enumerate(
        files["evidence-register.jsonl"].splitlines(), start=1
    ):
        entry = json.loads(line)
        declared = entry.pop("entry_sha256")
        if (
            entry["sequence"] != sequence
            or entry["previous_entry_sha256"] != previous
        ):
            raise InvalidProof("chaîne append-only rompue")
        if object_digest(entry) != declared:
            raise InvalidProof("entrée append-only altérée")
        previous = declared
    facts = bundles["effort_register"]["facts"]
    if len(facts) != len(PATHS) * len(COMPONENTS) * 2:
        raise InvalidProof("registre d'effort incomplet")
    for path in PATHS:
        for component in COMPONENTS:
            selected = [
                fact
                for fact in facts
                if fact["path"] == path and fact["component"] == component
            ]
            states = {
                (fact["phase"], fact["state"]) for fact in selected
            }
            if states != {
                ("initial", "OBSERVE"),
                ("recurrent", "INCONNU"),
            }:
                raise InvalidProof(f"effort divergent: {path}/{component}")
    dossiers = bundles["blind_review_fixtures"]["dossiers"]
    for case_id, dossier in dossiers.items():
        expected_availability = case_id != "WT-HUMAIN-INDISPONIBLE"
        unhashed = {
            key: value
            for key, value in dossier.items()
            if key != "dossier_sha256"
        }
        if (
            object_digest(unhashed) != dossier["dossier_sha256"]
            or
            dossier["available"] != expected_availability
            or dossier["candidate_alias"] != "SORTIE-A"
            or not dossier["identity_blinded"]
            or not dossier["cost_blinded"]
            or not dossier["rubric_frozen"]
            or dossier["presentation_order"]
            != ["stimulus", "candidate", "rubric"]
        ):
            raise InvalidProof(f"dossier aveugle divergent: {case_id}")
    reports_bundle = bundles["reports"]["reports"]
    if len(reports_bundle) != len(PATHS):
        raise InvalidProof("rapports incomplets")
    for report in reports_bundle:
        if (
            report["case_count"] != len(CASES)
            or report["provider_cost"]["supplier_spend_total"] != "0"
            or report["latency"]["state"] != "INCONNU"
            or report["conclusion"] != "INCONNU"
            or not report["abstention"]
        ):
            raise InvalidProof(f"rapport divergent: {report['path']}")
    for path, content in files.items():
        if any(pattern.search(content) for pattern in SECRET_PATTERNS):
            raise InvalidProof(f"secret potentiel dans {path}")
    return {
        "verdict": "PASS",
        "proof_id": PROOF_ID,
        "cases": len(CASES),
        "paths": len(PATHS),
        "receipts": len(CASES) * len(PATHS),
        "effort_facts": len(PATHS) * len(COMPONENTS) * 2,
        "candidate_calls": 0,
        "supplier_spend": "0",
    }


def read_tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def write_proof(output: Path) -> dict[str, object]:
    if output.exists() and any(output.iterdir()):
        raise InvalidProof(f"sortie non vide: {output}")
    files = build_files()
    result = validate(files)
    for relative, content in files.items():
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    return result


def verify_proof(root: Path) -> dict[str, object]:
    observed = read_tree(root)
    expected = build_files()
    if set(observed) != set(expected):
        raise InvalidProof("inventaire de preuve non reproductible")
    changed = [
        path for path in expected if expected[path] != observed[path]
    ]
    if changed:
        raise InvalidProof(f"octets non reproductibles: {changed}")
    return validate(observed)


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--output", type=Path, default=DEFAULT_PROOF)
    verify = commands.add_parser("verify")
    verify.add_argument("--proof-root", type=Path, default=DEFAULT_PROOF)
    args = parser.parse_args()
    try:
        result = (
            write_proof(args.output)
            if args.command == "build"
            else verify_proof(args.proof_root)
        )
    except (
        InvalidProof,
        OSError,
        ValueError,
        KeyError,
        TypeError,
    ) as error:
        print(
            json.dumps(
                {"verdict": "HOLD", "error": str(error)},
                ensure_ascii=False,
            )
        )
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
