from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter, process_time
import unittest

from tools import graph_engineering_pilot_v1 as pilot
from tools import preuve_u025_p2_manual_v3 as u025


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path(os.environ.get("GRAPH_ENGINEERING_PILOT_V1_OUTPUT", str(ROOT / "runs/graph-engineering-pilot-v1"))).resolve()


def invoke(arguments: list[str], *, read_only_dir: Path | None = None) -> dict[str, object]:
    before = pilot.scope_snapshot(read_only_dir) if read_only_dir is not None else None
    wall_start = perf_counter()
    process = subprocess.Popen(
        [sys.executable, "-m", "tools.graph_engineering_pilot_v1", *arguments],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stdout, stderr = process.communicate()
    wall_seconds = perf_counter() - wall_start
    after = pilot.scope_snapshot(read_only_dir) if read_only_dir is not None else None
    return {
        "argv": arguments,
        "pid": process.pid,
        "returncode": process.returncode,
        "stdout": stdout.strip(),
        "stderr": stderr.strip(),
        "wall_seconds": wall_seconds,
        "read_only_observed": before == after if read_only_dir is not None else None,
        "result": json.loads(stdout),
    }


def rehash_receipt(path: Path, mutate) -> dict[str, object]:
    receipt = json.loads(path.read_bytes())
    mutate(receipt)
    receipt["receipt_sha256"] = pilot.receipt_hash(receipt)
    path.write_bytes(pilot.canonical(receipt))
    return receipt


def rehash_false_payload(case_dir: Path) -> None:
    a_path = pilot.receipt_path(case_dir, "A")
    a = json.loads(a_path.read_bytes())
    a["output"]["u025_root_sha256"] = "f" * 64
    a["output_sha256"] = pilot.digest(pilot.canonical(a["output"]))
    a["receipt_sha256"] = pilot.receipt_hash(a)
    a_path.write_bytes(pilot.canonical(a))

    genesis_sha = pilot.digest((case_dir / "genesis.json").read_bytes())
    j_path = pilot.receipt_path(case_dir, "J")
    j = json.loads(j_path.read_bytes())
    j["parent_receipts"]["A"] = a["receipt_sha256"]
    j["input_sha256"] = pilot.input_sha256(genesis_sha, j["parent_receipts"])
    j["output"]["parent_output_sha256s"]["A"] = a["output_sha256"]
    aggregate = {key: value for key, value in j["output"].items() if key != "aggregate_sha256"}
    j["output"]["aggregate_sha256"] = pilot.digest(pilot.canonical(aggregate))
    j["output_sha256"] = pilot.digest(pilot.canonical(j["output"]))
    j["receipt_sha256"] = pilot.receipt_hash(j)
    j_path.write_bytes(pilot.canonical(j))


class GraphEngineeringPilotV1Test(unittest.TestCase):
    def test_invalid_j_output_is_not_published_as_evaluated(self) -> None:
        with TemporaryDirectory(prefix="graph-pilot-v1-invalid-j-") as temporary:
            run_dir = Path(temporary) / "S1"
            run = invoke([
                "run", "--run-dir", str(run_dir), "--scenario", "S1", "--route", "A",
                "--fault-injection", "invalid-j-output",
            ])
            self.assertEqual(run["returncode"], 1, run)
            self.assertEqual(run["result"]["state"], "HOLD_PILOTE_LOCAL")
            self.assertFalse(pilot.receipt_path(run_dir, "J").exists())
            self.assertEqual(
                {path.parent.name for path in (run_dir / "nodes").glob("*/receipt.json")},
                {"D", "S", "A"},
            )
            verified = invoke(["verify", "--run-dir", str(run_dir)], read_only_dir=run_dir)
            self.assertEqual(verified["returncode"], 1, verified)
            self.assertEqual(verified["result"]["verdict"], "HOLD_PILOTE_LOCAL")
            self.assertTrue(verified["read_only_observed"])

    def test_interrupted_b_receipt_is_uncommitted_and_resume_restarts_b(self) -> None:
        with TemporaryDirectory(prefix="graph-pilot-v1-interrupted-b-") as temporary:
            run_dir = Path(temporary) / "S2"
            interrupted = invoke([
                "run", "--run-dir", str(run_dir), "--scenario", "S2", "--route", "B",
                "--fault-injection", "interrupt-before-b-receipt",
            ])
            self.assertEqual(interrupted["returncode"], 0, interrupted)
            self.assertEqual(interrupted["result"]["state"], "STOPPED_DURING_B_RECEIPT")
            self.assertFalse(pilot.receipt_path(run_dir, "B").exists())
            self.assertTrue((run_dir / "nodes" / "B" / "u025").is_dir())
            closed_before = {
                node: {
                    "sha256": pilot.digest(pilot.receipt_path(run_dir, node).read_bytes()),
                    "mtime_ns": pilot.receipt_path(run_dir, node).stat().st_mtime_ns,
                }
                for node in ("D", "S")
            }

            held = invoke(["verify", "--run-dir", str(run_dir)], read_only_dir=run_dir)
            self.assertEqual(held["returncode"], 1, held)
            self.assertEqual(held["result"]["verdict"], "HOLD_PILOTE_LOCAL")
            self.assertTrue(held["read_only_observed"])

            resumed = invoke([
                "run", "--run-dir", str(run_dir), "--scenario", "S2", "--route", "B", "--resume",
            ])
            self.assertEqual(resumed["returncode"], 0, resumed)
            self.assertEqual(resumed["result"]["first_executed_node"], "B")
            self.assertEqual(resumed["result"]["replayed_nodes"], [])
            closed_after = {
                node: {
                    "sha256": pilot.digest(pilot.receipt_path(run_dir, node).read_bytes()),
                    "mtime_ns": pilot.receipt_path(run_dir, node).stat().st_mtime_ns,
                }
                for node in ("D", "S")
            }
            self.assertEqual(closed_before, closed_after)
            self.assertEqual(
                {path.name for path in (run_dir / "nodes" / "B").iterdir()},
                {"receipt.json", "u025"},
            )
            verified = invoke(["verify", "--run-dir", str(run_dir)], read_only_dir=run_dir)
            self.assertEqual(verified["returncode"], 0, verified)
            self.assertEqual(verified["result"]["verdict"], "PASS_PILOTE_LOCAL")
            self.assertTrue(verified["read_only_observed"])

    def test_resume_refuses_a_symlinked_nodes_directory(self) -> None:
        with TemporaryDirectory(prefix="graph-pilot-v1-symlinked-nodes-") as temporary:
            temporary_path = Path(temporary)
            run_dir = temporary_path / "S2"
            interrupted = invoke([
                "run", "--run-dir", str(run_dir), "--scenario", "S2", "--route", "B",
                "--fault-injection", "interrupt-before-b-receipt",
            ])
            self.assertEqual(interrupted["returncode"], 0, interrupted)

            external_nodes = temporary_path / "external-nodes"
            (run_dir / "nodes").rename(external_nodes)
            (run_dir / "nodes").symlink_to(external_nodes, target_is_directory=True)
            sentinel = external_nodes / "B" / "sentinel"
            sentinel.write_text("must survive")

            resumed = invoke([
                "run", "--run-dir", str(run_dir), "--scenario", "S2", "--route", "B", "--resume",
            ])
            self.assertEqual(resumed["returncode"], 1, resumed)
            self.assertEqual(resumed["result"]["state"], "HOLD_PILOTE_LOCAL")
            self.assertTrue(sentinel.exists())

    def test_contract_five_nodes_interruption_resume_and_false_terminals(self) -> None:
        for name in ("S1", "S2", "S3", "pilot-report.json", "process-results.json"):
            self.assertFalse((OUTPUT / name).exists(), f"preuve pilote déjà présente: {name}")
        wall_start, cpu_start = perf_counter(), process_time()
        processes: list[dict[str, object]] = []

        s1 = OUTPUT / "S1"
        s1_run = invoke(["run", "--run-dir", str(s1), "--scenario", "S1", "--route", "A"])
        processes.append(s1_run)
        self.assertEqual(s1_run["returncode"], 0, s1_run)
        self.assertEqual(s1_run["result"]["state"], "EXECUTION_COMPLETE_PENDING_TERMINAL_VERIFICATION")
        self.assertFalse(pilot.receipt_path(s1, "B").exists())
        s1_verify = invoke(["verify", "--run-dir", str(s1)], read_only_dir=s1)
        processes.append(s1_verify)
        self.assertEqual(s1_verify["returncode"], 0, s1_verify)
        self.assertEqual(s1_verify["result"]["verdict"], "PASS_PILOTE_LOCAL")
        self.assertTrue(s1_verify["read_only_observed"])

        s2 = OUTPUT / "S2"
        s2_interrupt = invoke([
            "run", "--run-dir", str(s2), "--scenario", "S2", "--route", "B", "--stop-after-s"
        ])
        processes.append(s2_interrupt)
        self.assertEqual(s2_interrupt["returncode"], 0, s2_interrupt)
        self.assertEqual(s2_interrupt["result"]["state"], "STOPPED_AFTER_S")
        self.assertEqual({path.parent.name for path in (s2 / "nodes").glob("*/receipt.json")}, {"D", "S"})
        closed_before = {
            node: {
                "sha256": pilot.digest(pilot.receipt_path(s2, node).read_bytes()),
                "mtime_ns": pilot.receipt_path(s2, node).stat().st_mtime_ns,
            }
            for node in ("D", "S")
        }
        s2_hold = invoke(["verify", "--run-dir", str(s2)], read_only_dir=s2)
        processes.append(s2_hold)
        self.assertEqual(s2_hold["returncode"], 1, s2_hold)
        self.assertEqual(s2_hold["result"]["verdict"], "HOLD_PILOTE_LOCAL")
        self.assertTrue(s2_hold["read_only_observed"])
        genesis_sha = pilot.digest((s2 / "genesis.json").read_bytes())
        forbidden_calls: list[str] = []

        def forbidden_prefix_evaluator(*args: object, **kwargs: object) -> object:
            forbidden_calls.append("called")
            raise AssertionError("évaluateur D/S appelé pendant le chargement de reprise")

        original_validate_node = pilot.validate_node
        original_expected_output = pilot.expected_output
        original_source_output = pilot.source_output
        original_verify_sources = u025.verify_sources
        pilot.validate_node = forbidden_prefix_evaluator
        pilot.expected_output = forbidden_prefix_evaluator
        pilot.source_output = forbidden_prefix_evaluator
        u025.verify_sources = forbidden_prefix_evaluator
        try:
            stored_prefix = pilot.load_resume_prefix(s2, genesis_sha)
        finally:
            pilot.validate_node = original_validate_node
            pilot.expected_output = original_expected_output
            pilot.source_output = original_source_output
            u025.verify_sources = original_verify_sources
        self.assertEqual(set(stored_prefix), {"D", "S"})
        self.assertEqual(forbidden_calls, [])
        s2_resume = invoke([
            "run", "--run-dir", str(s2), "--scenario", "S2", "--route", "B", "--resume"
        ])
        processes.append(s2_resume)
        self.assertEqual(s2_resume["returncode"], 0, s2_resume)
        self.assertEqual(s2_resume["result"]["state"], "EXECUTION_COMPLETE_PENDING_TERMINAL_VERIFICATION")
        self.assertEqual(s2_resume["result"]["replayed_nodes"], [])
        self.assertEqual(s2_resume["result"]["first_executed_node"], "B")
        self.assertEqual(s2_resume["result"]["resume_checkpoint_validation"], "canonical-hash-and-stored-links-only")
        closed_after = {
            node: {
                "sha256": pilot.digest(pilot.receipt_path(s2, node).read_bytes()),
                "mtime_ns": pilot.receipt_path(s2, node).stat().st_mtime_ns,
            }
            for node in ("D", "S")
        }
        self.assertEqual(closed_before, closed_after)
        s2_verify = invoke(["verify", "--run-dir", str(s2)], read_only_dir=s2)
        processes.append(s2_verify)
        self.assertEqual(s2_verify["returncode"], 0, s2_verify)
        self.assertEqual(s2_verify["result"]["verdict"], "PASS_PILOTE_LOCAL")
        self.assertTrue(s2_verify["read_only_observed"])

        receipts_s1 = {node: pilot.load_receipt(s1, node) for node in pilot.ROUTES["A"]}
        receipts_s2 = {node: pilot.load_receipt(s2, node) for node in pilot.ROUTES["B"]}
        self.assertEqual({receipt["evaluation"]["contract"] for receipt in [*receipts_s1.values(), *receipts_s2.values()]}, set(pilot.CONTRACTS.values()))
        self.assertEqual({receipts_s2[node]["writer_pid"] for node in ("D", "S")}, {s2_interrupt["pid"]})
        self.assertEqual({receipts_s2[node]["writer_pid"] for node in ("B", "J")}, {s2_resume["pid"]})
        self.assertNotEqual(s2_interrupt["pid"], s2_resume["pid"])
        self.assertEqual(set(receipts_s2["J"]["parent_receipts"]), {"S", "B"})

        original_verify = u025.verify
        original_temporary_directory = u025.TemporaryDirectory
        original_counterexamples = u025.exercise_counterexamples

        def illicit_verify(proof_dir: Path) -> dict[str, object]:
            u025.TemporaryDirectory()
            return {}

        u025.verify = illicit_verify
        try:
            with self.assertRaises(pilot.PilotError):
                pilot.verify_u025_read_only(u025.PROOF)
        finally:
            u025.verify = original_verify
        self.assertIs(u025.TemporaryDirectory, original_temporary_directory)
        self.assertIs(u025.exercise_counterexamples, original_counterexamples)
        control_wall_start, control_cpu_start = perf_counter(), process_time()
        direct, direct_read_only = pilot.verify_u025_read_only(u025.PROOF)
        direct_wall = perf_counter() - control_wall_start
        direct_cpu = process_time() - control_cpu_start
        self.assertEqual(direct_read_only["temporary_directory_calls"], 0)
        self.assertTrue(direct_read_only["content_and_mtime_unchanged"])
        self.assertEqual(receipts_s2["B"]["output"]["u025_root_sha256"], direct["root_sha256"])
        self.assertEqual(receipts_s2["B"]["output"]["u025_conclusion"], direct["conclusion"])
        self.assertEqual(receipts_s2["B"]["output"]["reconstruction_temporary_directory_calls"], 6)
        self.assertEqual(receipts_s2["B"]["output"]["temporary_writes_outside_b"], 0)

        s3_root = OUTPUT / "S3"
        cases = {
            "selected-node-missing": lambda case: pilot.receipt_path(case, "A").unlink(),
            "double-branch": lambda case: (case / "nodes" / "B").mkdir() or (case / "nodes" / "B" / "receipt.json").write_bytes(pilot.receipt_path(case, "A").read_bytes()),
            "pending-state": lambda case: rehash_receipt(pilot.receipt_path(case, "A"), lambda value: value.__setitem__("state", "pending")),
            "running-state": lambda case: rehash_receipt(pilot.receipt_path(case, "A"), lambda value: value.__setitem__("state", "running")),
            "not-evaluated": lambda case: rehash_receipt(pilot.receipt_path(case, "A"), lambda value: value["evaluation"].__setitem__("verdict", "NOT_EVALUATED")),
            "wrong-parent-edge": lambda case: rehash_receipt(pilot.receipt_path(case, "J"), lambda value: value.__setitem__("consumed_edges", ["S->J", "B->J"])),
            "invalid-receipt-chain": lambda case: json.loads(pilot.receipt_path(case, "J").read_bytes())["parent_receipts"].__setitem__("A", "0" * 64),
            "false-payload-rehashed": rehash_false_payload,
            "ambiguous-effect": lambda case: rehash_receipt(pilot.receipt_path(case, "A"), lambda value: value.__setitem__("effect", "ambiguous")),
            "external-effect": lambda case: rehash_receipt(pilot.receipt_path(case, "A"), lambda value: value.__setitem__("effect", "external")),
            "forged-terminal-marker": lambda case: (case / "terminal.json").write_bytes(pilot.canonical({"verdict": "PASS_PILOTE_LOCAL"})),
            "missing-context": lambda case: rehash_receipt(pilot.receipt_path(case, "A"), lambda value: value.pop("context")),
            "altered-context": lambda case: rehash_receipt(pilot.receipt_path(case, "A"), lambda value: value["context"]["altered_fields"].append("requested_route")),
        }
        false_results: list[dict[str, object]] = []
        for case_id, mutation in cases.items():
            case_dir = s3_root / "cases" / case_id
            shutil.copytree(s1, case_dir)
            if case_id == "invalid-receipt-chain":
                j_path = pilot.receipt_path(case_dir, "J")
                value = json.loads(j_path.read_bytes())
                value["parent_receipts"]["A"] = "0" * 64
                j_path.write_bytes(pilot.canonical(value))
            else:
                mutation(case_dir)
            result = invoke(["verify", "--run-dir", str(case_dir)], read_only_dir=case_dir)
            processes.append(result)
            self.assertEqual(result["returncode"], 1, (case_id, result))
            self.assertEqual(result["result"]["verdict"], "HOLD_PILOTE_LOCAL", (case_id, result))
            self.assertTrue(result["read_only_observed"], (case_id, result))
            false_results.append({"case_id": case_id, "verdict": result["result"]["verdict"], "error": result["result"].get("error")})

        false_passes = sum(result["verdict"] == "PASS_PILOTE_LOCAL" for result in false_results)
        self.assertEqual(false_passes, 0)
        node_times = [receipt["time"] for receipt in [*receipts_s1.values(), *receipts_s2.values()]]
        evidence_bytes_before_reports = pilot.tree_bytes(OUTPUT)
        total_wall, total_cpu = perf_counter() - wall_start, process_time() - cpu_start
        report = {
            "schema_version": "graph-engineering-pilot-v1/report/v1",
            "pilot_id": pilot.PILOT_ID,
            "git_base": pilot.GIT_BASE,
            "verdict": "PASS_PILOTE_LOCAL",
            "criteria": {
                "five_node_contracts_tested": True,
                "four_selected_nodes_per_execution": len(receipts_s1) == len(receipts_s2) == 4,
                "join_consumes_s_and_selected_branch": set(receipts_s1["J"]["parent_receipts"]) == {"S", "A"} and set(receipts_s2["J"]["parent_receipts"]) == {"S", "B"},
                "exactly_one_branch_selected": not pilot.receipt_path(s1, "B").exists() and not pilot.receipt_path(s2, "A").exists(),
                "s2_before_resume_hold": s2_hold["result"]["verdict"] == "HOLD_PILOTE_LOCAL",
                "s2_resume_starts_on_b": receipts_s2["B"]["writer_pid"] == s2_resume["pid"],
                "s2_resume_replays_no_prefix_node": s2_resume["result"]["replayed_nodes"] == [] and forbidden_calls == [],
                "closed_receipts_unchanged": closed_before == closed_after,
                "s2_equals_direct_u025": receipts_s2["B"]["output"]["u025_root_sha256"] == direct["root_sha256"],
                "false_passes_zero": false_passes == 0,
                "local_single_writer_no_external_effect": all(receipt["effect"] == "none" and receipt["owner"] == pilot.OWNER for receipt in [*receipts_s1.values(), *receipts_s2.values()]),
                "u025_read_only_guard_and_snapshot": direct_read_only == {"mode": "locked-counterexamples-read-only", "content_and_mtime_unchanged": True, "temporary_directory_calls": 0},
                "u025_temporary_writes_scoped_to_b": receipts_s2["B"]["output"]["reconstruction_temporary_directory_calls"] == 6 and receipts_s2["B"]["output"]["temporary_writes_outside_b"] == 0,
            },
            "measurements": {
                "terminal_accuracy": {"correct": 3 + len(cases), "total": 3 + len(cases)},
                "false_ends": {"attempted": len(cases), "rejected": len(cases), "false_passes": false_passes, "cases": false_results},
                "time": {
                    "pilot_wall_seconds": total_wall,
                    "pilot_parent_cpu_seconds": total_cpu,
                    "node_wall_seconds": sum(value["wall_seconds"] for value in node_times),
                    "node_cpu_seconds": sum(value["cpu_seconds"] for value in node_times),
                    "direct_u025_wall_seconds": direct_wall,
                    "direct_u025_cpu_seconds": direct_cpu,
                },
                "external_cost": {"usd": "0", "candidate_calls": 0, "provider_attempts": 0},
                "human_interventions": 0,
                "resume": {
                    "controlled_stop_after": "S",
                    "intermediate_verdict": "HOLD_PILOTE_LOCAL",
                    "first_resumed_node": "B",
                    "replayed_nodes": [],
                    "prefix_evaluator_calls": len(forbidden_calls),
                    "closed_receipts_byte_and_mtime_equal": closed_before == closed_after,
                    "semantic_root_equal_to_direct": True,
                },
                "read_only": {
                    "snapshot_fields": ["content_sha256", "mtime_ns"],
                    "direct_u025": direct_read_only,
                    "all_terminal_verifiers_content_and_mtime_unchanged": all(process["read_only_observed"] is not False for process in processes),
                    "temporary_directory_guard_rejected_call": True,
                    "b_temporary_directory_calls": receipts_s2["B"]["output"]["reconstruction_temporary_directory_calls"],
                    "b_temporary_writes_outside_scope": 0,
                },
                "context": {"valid_missing_fields": 0, "valid_altered_fields": 0, "injected_missing_cases": 1, "injected_altered_cases": 1, "all_injected_rejected": True},
                "writers": {"logical_writer_count": 1, "sequential_writer_processes_s2": 2, "concurrent_writers": 0, "conflicts_observed": 0},
                "processes": {"subprocess_count": len(processes), "s2_runner_process_count": 2, "s2_writer_pids": sorted({receipts_s2[node]["writer_pid"] for node in receipts_s2})},
                "evidence_bytes_before_reports": evidence_bytes_before_reports,
            },
            "comparison_to_direct_u025": {
                "same_root_sha256": True,
                "same_conclusion": True,
                "direct_behavior": "vérification U-025 V3 sans reçus de dépendance, branche, jointure ni verdict terminal séparé",
                "pilot_behavior": "ajoute D, S, branche, J, reçus évalués, arrêt/reprise externe et refus des fausses fins",
                "claim_limit": "aucun avantage global ni garantie exactly-once n'est déduit",
            },
        }
        self.assertTrue(all(report["criteria"].values()), report)
        pilot.write_new(OUTPUT / "process-results.json", {"schema_version": "graph-engineering-pilot-v1/process-results/v1", "processes": processes})
        pilot.write_new(OUTPUT / "pilot-report.json", report)


if __name__ == "__main__":
    unittest.main()
