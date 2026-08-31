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
        "result": json.loads(process.stdout) if process.stdout.strip() else None,
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
            forged_time = invoke([
                "verify", "--run-dir", str(run_dir), "--now-utc", "2099-01-01T00:00:00Z",
            ])
            self.assertEqual(forged_time["returncode"], 1, forged_time)
            self.assertEqual(
                forged_time["result"]["verdict"],
                "HOLD_PILOTE_AGENTIQUE_LOCAL",
            )

    def test_agent_route_crashes_then_reuses_one_durable_attempt_after_deadline(self) -> None:
        with TemporaryDirectory(prefix="graph-pilot-v2-agent-") as temporary:
            temporary_path = Path(temporary)
            run_dir = temporary_path / "agent"
            prepared = invoke([
                "run", "--run-dir", str(run_dir), "--scenario", "defect",
                "--duration-seconds", "7200", "--now-utc", "2026-08-31T10:00:00Z",
            ])
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
            cache = workspace / "__pycache__"
            cache.mkdir()
            (cache / "choisir_provider.cpython-test.pyc").write_bytes(b"cache")
            evidence = temporary_path / "agent.json"
            evidence.write_text(json.dumps({
                "schema_version": "graph-engineering-pilot-v2/agent-evidence/v1",
                "harness": "test-double",
                "model_requested": "test-model",
                "model_observed": "test-model",
                "session_id": "agent-attempt",
                "wall_seconds": 0.01,
                "tokens": "INCONNU",
            }))
            crashed = invoke([
                "continue", "--run-dir", str(run_dir),
                "--agent-evidence", str(evidence), "--crash-after-attempt",
            ])
            self.assertEqual(crashed["returncode"], 86, crashed)
            self.assertIsNone(crashed["result"])
            self.assertFalse(cache.exists())
            self.assertFalse(pilot.receipt_path(run_dir, "B").exists())
            attempt_path = run_dir / "nodes" / "B" / "attempts" / "1.json"
            self.assertTrue(attempt_path.is_file())
            attempt_snapshot = (
                pilot.v1.digest(attempt_path.read_bytes()),
                attempt_path.stat().st_mtime_ns,
            )
            attempts = pilot.load_agent_attempts(run_dir)
            self.assertEqual(len(attempts), 1)
            self.assertEqual(
                attempts[0]["output"]["candidate_source_utf8"],
                source.read_text(encoding="utf-8"),
            )

            waiting = invoke([
                "status", "--run-dir", str(run_dir), "--expect", "waiting",
                "--now-utc", "2026-08-31T11:59:59Z",
            ])
            self.assertEqual(waiting["returncode"], 0, waiting)
            self.assertEqual(waiting["result"]["state"], "WAITING_UNTIL_DEADLINE")
            held = invoke([
                "verify", "--run-dir", str(run_dir),
                "--now-utc", "2026-08-31T11:59:59Z",
            ])
            self.assertEqual(held["returncode"], 1, held)
            self.assertEqual(held["result"]["verdict"], "HOLD_PILOTE_AGENTIQUE_LOCAL")
            early = invoke([
                "continue", "--run-dir", str(run_dir), "--reuse-last-attempt",
                "--now-utc", "2026-08-31T11:59:59Z",
            ])
            self.assertEqual(early["returncode"], 1, early)
            closed_while_waiting = {
                node: (
                    pilot.v1.digest(pilot.receipt_path(run_dir, node).read_bytes()),
                    pilot.receipt_path(run_dir, node).stat().st_mtime_ns,
                )
                for node in ("D", "S")
            }
            self.assertEqual(closed_before, closed_while_waiting)
            self.assertEqual(
                attempt_snapshot,
                (
                    pilot.v1.digest(attempt_path.read_bytes()),
                    attempt_path.stat().st_mtime_ns,
                ),
            )

            ready = invoke([
                "status", "--run-dir", str(run_dir), "--expect", "ready",
                "--now-utc", "2026-08-31T12:00:00Z",
            ])
            self.assertEqual(ready["returncode"], 0, ready)
            self.assertEqual(ready["result"]["state"], "READY_TO_RESUME")
            completed = invoke([
                "continue", "--run-dir", str(run_dir),
                "--reuse-last-attempt", "--now-utc", "2026-08-31T12:00:00Z",
            ])
            self.assertEqual(completed["returncode"], 0, completed)
            self.assertEqual(
                completed["result"]["state"],
                "EXECUTION_COMPLETE_PENDING_TERMINAL_VERIFICATION",
            )
            verified = invoke([
                "verify", "--run-dir", str(run_dir),
                "--now-utc", "2026-08-31T12:00:00Z",
            ])
            self.assertEqual(verified["returncode"], 0, verified)
            self.assertEqual(verified["result"]["verdict"], "PASS_PILOTE_AGENTIQUE_LOCAL")
            self.assertEqual(verified["result"]["route"], "B")
            attempts = pilot.load_agent_attempts(run_dir)
            self.assertEqual([attempt["attempt"] for attempt in attempts], [1])
            b_receipt = pilot.load_receipt(run_dir, "B")
            self.assertEqual(b_receipt["attempt"], 1)
            self.assertEqual(b_receipt["cost"]["candidate_calls"], 1)
            self.assertEqual(b_receipt["output"], attempts[-1]["output"])
            self.assertEqual(closed_before, {
                node: (
                    pilot.v1.digest(pilot.receipt_path(run_dir, node).read_bytes()),
                    pilot.receipt_path(run_dir, node).stat().st_mtime_ns,
                )
                for node in ("D", "S")
            })
            self.assertEqual(
                attempt_snapshot,
                (pilot.v1.digest(attempt_path.read_bytes()), attempt_path.stat().st_mtime_ns),
            )

            missing_history = temporary_path / "missing-history"
            shutil.copytree(run_dir, missing_history)
            (missing_history / "nodes" / "B" / "attempts" / "1.json").unlink()
            held = invoke([
                "verify", "--run-dir", str(missing_history),
                "--now-utc", "2026-08-31T12:00:00Z",
            ])
            self.assertEqual(held["returncode"], 1, held)
            self.assertEqual(held["result"]["verdict"], "HOLD_PILOTE_AGENTIQUE_LOCAL")

            tampered_source = temporary_path / "tampered-source"
            shutil.copytree(run_dir, tampered_source)
            tampered_path = tampered_source / "nodes" / "B" / "attempts" / "1.json"
            tampered = json.loads(tampered_path.read_text())
            tampered["output"]["candidate_source_utf8"] += "\n# tamper\n"
            tampered["output_sha256"] = pilot.v1.digest(pilot.v1.canonical(tampered["output"]))
            tampered_base = {
                key: value for key, value in tampered.items() if key != "attempt_sha256"
            }
            tampered["attempt_sha256"] = pilot.v1.digest(pilot.v1.canonical(tampered_base))
            tampered_path.write_bytes(pilot.v1.canonical(tampered))
            held = invoke([
                "verify", "--run-dir", str(tampered_source),
                "--now-utc", "2026-08-31T12:00:00Z",
            ])
            self.assertEqual(held["returncode"], 1, held)

            extra_history = temporary_path / "extra-history"
            shutil.copytree(run_dir, extra_history)
            last = pilot.load_agent_attempts(extra_history)[-1]
            extra_base = {
                **{key: value for key, value in last.items() if key != "attempt_sha256"},
                "attempt": 2,
                "previous_attempt_sha256": last["attempt_sha256"],
            }
            extra = {
                **extra_base,
                "attempt_sha256": pilot.v1.digest(pilot.v1.canonical(extra_base)),
            }
            (extra_history / "nodes" / "B" / "attempts" / "2.json").write_bytes(
                pilot.v1.canonical(extra)
            )
            held = invoke([
                "verify", "--run-dir", str(extra_history),
                "--now-utc", "2026-08-31T12:00:00Z",
            ])
            self.assertEqual(held["returncode"], 1, held)
            self.assertEqual(held["result"]["verdict"], "HOLD_PILOTE_AGENTIQUE_LOCAL")


if __name__ == "__main__":
    unittest.main()
