from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tools import graph_engineering_pilot_v2 as pilot


ROOT = Path(__file__).resolve().parents[1]


def invoke(arguments: list[str]) -> dict[str, object]:
    process = subprocess.run(
        [sys.executable, "-m", "tools.graph_engineering_pilot_v2", *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "returncode": process.returncode,
        "stdout": process.stdout.strip(),
        "stderr": process.stderr.strip(),
        "result": json.loads(process.stdout),
    }


class GraphEngineeringPilotV2Test(unittest.TestCase):
    def test_control_route_closes_without_agent_and_terminal_passes(self) -> None:
        with TemporaryDirectory(prefix="graph-pilot-v2-control-") as temporary:
            run_dir = Path(temporary) / "control"
            run = invoke(["run", "--run-dir", str(run_dir), "--scenario", "control"])
            self.assertEqual(run["returncode"], 0, run)
            self.assertEqual(
                run["result"]["state"],
                "EXECUTION_COMPLETE_PENDING_TERMINAL_VERIFICATION",
            )
            self.assertEqual(run["result"]["route"], "A")
            self.assertEqual(
                {path.parent.name for path in (run_dir / "nodes").glob("*/receipt.json")},
                {"D", "S", "A", "J"},
            )

            verified = invoke(["verify", "--run-dir", str(run_dir)])
            self.assertEqual(verified["returncode"], 0, verified)
            self.assertEqual(verified["result"]["verdict"], "PASS_PILOTE_AGENTIQUE_LOCAL")
            self.assertEqual(verified["result"]["route"], "A")

    def test_agent_route_interrupts_then_resumes_from_b_without_replaying_prefix(self) -> None:
        with TemporaryDirectory(prefix="graph-pilot-v2-agent-") as temporary:
            temporary_path = Path(temporary)
            run_dir = temporary_path / "agent"
            prepared = invoke(["run", "--run-dir", str(run_dir), "--scenario", "defect"])
            self.assertEqual(prepared["returncode"], 0, prepared)
            self.assertEqual(prepared["result"]["state"], "NEEDS_AGENT_B")
            workspace = run_dir / "nodes" / "B" / "workspace"
            source = workspace / "choisir_provider.py"
            self.assertIn(pilot.DEFECT_LINE, source.read_text())
            closed_before = {
                node: (
                    pilot.v1.digest(pilot.receipt_path(run_dir, node).read_bytes()),
                    pilot.receipt_path(run_dir, node).stat().st_mtime_ns,
                )
                for node in ("D", "S")
            }

            source.write_text(source.read_text().replace(pilot.DEFECT_LINE, pilot.CORRECT_LINE))
            evidence_one = temporary_path / "agent-one.json"
            evidence_one.write_text(json.dumps({
                "schema_version": "graph-engineering-pilot-v2/agent-evidence/v1",
                "harness": "test-double",
                "model_requested": "test-model",
                "model_observed": "test-model",
                "session_id": "agent-attempt-one",
                "wall_seconds": 0.01,
                "tokens": "INCONNU",
            }))
            interrupted = invoke([
                "continue", "--run-dir", str(run_dir),
                "--agent-evidence", str(evidence_one),
                "--interrupt-before-b-receipt",
            ])
            self.assertEqual(interrupted["returncode"], 0, interrupted)
            self.assertEqual(interrupted["result"]["state"], "STOPPED_DURING_B_RECEIPT")
            self.assertFalse(pilot.receipt_path(run_dir, "B").exists())
            attempt_one_path = run_dir / "nodes" / "B" / "attempts" / "1.json"
            self.assertTrue(attempt_one_path.is_file())
            attempt_one_snapshot = (
                pilot.v1.digest(attempt_one_path.read_bytes()),
                attempt_one_path.stat().st_mtime_ns,
            )
            held = invoke(["verify", "--run-dir", str(run_dir)])
            self.assertEqual(held["returncode"], 1, held)
            self.assertEqual(held["result"]["verdict"], "HOLD_PILOTE_AGENTIQUE_LOCAL")

            resumed = invoke([
                "run", "--run-dir", str(run_dir), "--scenario", "defect", "--resume",
            ])
            self.assertEqual(resumed["returncode"], 0, resumed)
            self.assertEqual(resumed["result"]["state"], "NEEDS_AGENT_B")
            self.assertEqual(resumed["result"]["first_executed_node"], "B")
            self.assertEqual(resumed["result"]["replayed_nodes"], [])
            self.assertIn(pilot.DEFECT_LINE, source.read_text())
            closed_after_resume = {
                node: (
                    pilot.v1.digest(pilot.receipt_path(run_dir, node).read_bytes()),
                    pilot.receipt_path(run_dir, node).stat().st_mtime_ns,
                )
                for node in ("D", "S")
            }
            self.assertEqual(closed_before, closed_after_resume)
            self.assertEqual(
                attempt_one_snapshot,
                (
                    pilot.v1.digest(attempt_one_path.read_bytes()),
                    attempt_one_path.stat().st_mtime_ns,
                ),
            )

            source.write_text(source.read_text().replace(pilot.DEFECT_LINE, pilot.CORRECT_LINE))
            evidence_two = temporary_path / "agent-two.json"
            evidence_two.write_text(json.dumps({
                "schema_version": "graph-engineering-pilot-v2/agent-evidence/v1",
                "harness": "test-double",
                "model_requested": "test-model",
                "model_observed": "test-model",
                "session_id": "agent-attempt-two",
                "wall_seconds": 0.01,
                "tokens": "INCONNU",
            }))
            completed = invoke([
                "continue", "--run-dir", str(run_dir),
                "--agent-evidence", str(evidence_two),
            ])
            self.assertEqual(completed["returncode"], 0, completed)
            self.assertEqual(
                completed["result"]["state"],
                "EXECUTION_COMPLETE_PENDING_TERMINAL_VERIFICATION",
            )
            verified = invoke(["verify", "--run-dir", str(run_dir)])
            self.assertEqual(verified["returncode"], 0, verified)
            self.assertEqual(verified["result"]["verdict"], "PASS_PILOTE_AGENTIQUE_LOCAL")
            self.assertEqual(verified["result"]["route"], "B")
            attempts = pilot.load_agent_attempts(run_dir)
            self.assertEqual([attempt["attempt"] for attempt in attempts], [1, 2])
            b_receipt = pilot.load_receipt(run_dir, "B")
            self.assertEqual(b_receipt["attempt"], 2)
            self.assertEqual(b_receipt["cost"]["candidate_calls"], 2)
            self.assertEqual(b_receipt["output"], attempts[-1]["output"])

            missing_history = temporary_path / "missing-history"
            shutil.copytree(run_dir, missing_history)
            (missing_history / "nodes" / "B" / "attempts" / "1.json").unlink()
            held = invoke(["verify", "--run-dir", str(missing_history)])
            self.assertEqual(held["returncode"], 1, held)
            self.assertEqual(held["result"]["verdict"], "HOLD_PILOTE_AGENTIQUE_LOCAL")

            extra_history = temporary_path / "extra-history"
            shutil.copytree(run_dir, extra_history)
            last = pilot.load_agent_attempts(extra_history)[-1]
            extra_base = {
                **{key: value for key, value in last.items() if key != "attempt_sha256"},
                "attempt": 3,
                "previous_attempt_sha256": last["attempt_sha256"],
            }
            extra = {
                **extra_base,
                "attempt_sha256": pilot.v1.digest(pilot.v1.canonical(extra_base)),
            }
            (extra_history / "nodes" / "B" / "attempts" / "3.json").write_bytes(
                pilot.v1.canonical(extra)
            )
            held = invoke(["verify", "--run-dir", str(extra_history)])
            self.assertEqual(held["returncode"], 1, held)
            self.assertEqual(held["result"]["verdict"], "HOLD_PILOTE_AGENTIQUE_LOCAL")


if __name__ == "__main__":
    unittest.main()
