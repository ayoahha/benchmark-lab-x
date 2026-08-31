from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tools import graph_engineering_pilot_v1 as v1
from tools import graph_engineering_v2_2 as ge
from tools import graph_engineering_v2_2_adapter as adapter
from tools import graph_engineering_v2_2_evaluator as evaluator

ROOT = Path(__file__).resolve().parents[1]
SESSION_ID = "01a00000-0000-7000-8000-000000000022"


def git(directory: Path, *arguments: str, input_bytes: bytes | None = None) -> bytes:
    process = subprocess.run(
        ["git", "-C", str(directory), *arguments],
        input=input_bytes,
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        raise AssertionError(process.stderr.decode(errors="replace"))
    return process.stdout


class Fixture:
    def __init__(self, route: str = "B", *, create_contract: bool = True) -> None:
        self.temporary = TemporaryDirectory(prefix="ge22-test-")
        self.root = Path(self.temporary.name)
        self.canonical = self.root / "canonical"
        self.worktree = self.root / "worktree"
        self.sessions = self.root / "sessions"
        self.fake_codex = self.root / "codex"
        self.route = route
        self._build_repository()
        self._build_fake_codex()
        git(self.canonical, "worktree", "add", "-b", "feat/graph-v2-2", str(self.worktree))
        self.runner_root = Path("runs/graph-engineering-v2-2/test-run")
        self.run_dir = self.worktree / self.runner_root
        self.run_dir.mkdir(parents=True)
        self.request_path = self.run_dir / "request.json"
        expected = "PENDING" if route == "A" else "READY"
        self.request = {
            "run_id": f"test-{route.lower()}",
            "task": "micro-pilote local hors produit",
            "canonical_repository": str(self.canonical),
            "worktree": str(self.worktree),
            "runner_root": self.runner_root.as_posix(),
            "route": route,
            "prompt": "tests/fixtures/graph_engineering_v2_2_prompt.md",
            "agent_root": "tests/fixtures/graph_engineering_v2_2",
            "agent_paths": ["tests/fixtures/graph_engineering_v2_2/target.txt"],
            "immutable_paths": [
                "tests/fixtures/graph_engineering_v2_2_prompt.md",
                "tests/test_sample.py",
            ],
            "acceptance": [
                {
                    "id": "targeted",
                    "argv": [
                        sys.executable,
                        "-c",
                        f"from pathlib import Path; assert Path('tests/fixtures/graph_engineering_v2_2/target.txt').read_text().strip() == '{expected}'",
                    ],
                    "cwd": ".",
                    "test_parser": "none",
                },
                {
                    "id": "repository",
                    "argv": [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                    "cwd": ".",
                    "test_parser": "unittest",
                },
            ],
            "harness": {"kind": "codex-exec", "binary": str(self.fake_codex), "model": "gpt-5.6-sol"},
        }
        self.write_request()
        self.contract_path = self.run_dir / "contract.json"
        if create_contract:
            ge.create_contract(self.request_path)

    def close(self) -> None:
        self.temporary.cleanup()

    def write_request(self) -> None:
        self.request_path.write_bytes(ge.canonical(self.request))

    def _build_repository(self) -> None:
        self.canonical.mkdir()
        git(self.canonical, "init", "-b", "feat/fixture")
        git(self.canonical, "config", "user.name", "Graph Test")
        git(self.canonical, "config", "user.email", "graph@example.invalid")
        for relative in ge.EXECUTABLE_PATHS.values():
            destination = self.canonical / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, destination)
        prompt = self.canonical / "tests/fixtures/graph_engineering_v2_2_prompt.md"
        prompt.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "tests/fixtures/graph_engineering_v2_2_prompt.md", prompt)
        target = self.canonical / "tests/fixtures/graph_engineering_v2_2/target.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("PENDING\n", encoding="utf-8")
        sample = self.canonical / "tests/test_sample.py"
        sample.write_text(
            "import os\nfrom pathlib import Path\nimport unittest\n\nclass Sample(unittest.TestCase):\n"
            "    def test_one(self): self.assertTrue(True)\n"
            "    def test_two(self): self.assertEqual(1 + 1, 2)\n"
            "    def test_v1_output_is_external(self):\n"
            "        output = Path(os.environ['GRAPH_ENGINEERING_PILOT_V1_OUTPUT']).resolve()\n"
            "        self.assertNotIn(Path.cwd().resolve(), [output, *output.parents])\n",
            encoding="utf-8",
        )
        (self.canonical / ".gitignore").write_text("runs/\n__pycache__/\n*.pyc\n", encoding="utf-8")
        git(self.canonical, "add", ".")
        git(self.canonical, "commit", "-m", "test: create fixture")

    def _build_fake_codex(self) -> None:
        self.fake_codex.write_text(
            textwrap.dedent(
                f"""\
                #!{sys.executable}
                import json
                import os
                from pathlib import Path
                import sys
                import time

                if "--version" in sys.argv:
                    print("codex-cli 0.151.0")
                    raise SystemExit(0)

                session_id = "{SESSION_ID}"
                model = sys.argv[sys.argv.index("--model") + 1]
                sandbox = (
                    sys.argv[sys.argv.index("--sandbox") + 1]
                    if "--sandbox" in sys.argv else "danger-full-access"
                )
                print(json.dumps({{"type": "thread.started", "thread_id": session_id}}), flush=True)
                waiting = os.environ.get("GE22_FAKE_WAIT") == "1" and "resume" not in sys.argv
                if waiting:
                    time.sleep(0.1)
                root = Path(os.environ["GE22_FAKE_SESSION_ROOT"])
                root.mkdir(parents=True, exist_ok=True)
                path = root / f"rollout-2026-08-31T00-00-00-{{session_id}}.jsonl"
                events = []
                if not path.exists():
                    events.append({{"type": "session_meta", "payload": {{"id": session_id}}}})
                events.append({{
                    "type": "turn_context",
                    "payload": {{
                        "model": model,
                        "cwd": str(Path.cwd()),
                        "sandbox_policy": {{"type": sandbox, "network_access": False}},
                    }},
                }})
                with path.open("a", encoding="utf-8") as stream:
                    for event in events:
                        stream.write(json.dumps(event, separators=(",", ":")) + "\\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                if waiting:
                    time.sleep(60)
                Path("target.txt").write_text("READY\\n", encoding="utf-8")
                print(json.dumps({{"type": "turn.completed", "usage": {{"input_tokens": 1, "output_tokens": 1}}}}), flush=True)
                """
            ),
            encoding="utf-8",
        )
        self.fake_codex.chmod(0o755)

    def agent_environment(self, *, wait: bool = False) -> dict[str, str]:
        values = {"GE22_FAKE_SESSION_ROOT": str(self.sessions)}
        if wait:
            values["GE22_FAKE_WAIT"] = "1"
        return values

    def complete_agent(self, *, interrupted: bool = False) -> dict[str, object]:
        ge.prepare(self.contract_path)
        if interrupted:
            with patch.dict(os.environ, self.agent_environment(wait=True), clear=False):
                stopped = adapter.run_adapter(
                    self.contract_path,
                    resume=False,
                    interrupt_after_session=True,
                    session_roots=[self.sessions],
                )
            if stopped["state"] != "INTERRUPTED_AGENT_SESSION":
                raise AssertionError(stopped)
            with patch.dict(os.environ, self.agent_environment(), clear=False):
                result = adapter.run_adapter(
                    self.contract_path,
                    resume=True,
                    interrupt_after_session=False,
                    session_roots=[self.sessions],
                )
        else:
            with patch.dict(os.environ, self.agent_environment(), clear=False):
                result = adapter.run_adapter(
                    self.contract_path,
                    resume=False,
                    interrupt_after_session=False,
                    session_roots=[self.sessions],
                )
        return result


class GraphEngineeringV22Test(unittest.TestCase):
    def test_control_real_worktree_closes_and_discovers_tests(self) -> None:
        fixture = Fixture("A")
        self.addCleanup(fixture.close)
        prepared = ge.prepare(fixture.contract_path)
        self.assertEqual(prepared["state"], "GRAPH_CLOSED_PENDING_INDEPENDENT_EVALUATION")
        result = evaluator.evaluate(fixture.contract_path, session_roots=[fixture.sessions])
        self.assertEqual(result["verdict"], ge.VERDICT_READY)
        self.assertEqual(result["tests_discovered"], {"repository": 3})
        repeated = evaluator.evaluate(fixture.contract_path, session_roots=[fixture.sessions])
        self.assertTrue(repeated["reused_terminal_report"])

    def test_interrupted_agent_resumes_same_session_and_reuses_durable_attempt(self) -> None:
        fixture = Fixture("B")
        self.addCleanup(fixture.close)
        result = fixture.complete_agent(interrupted=True)
        self.assertEqual(result["session_id"], SESSION_ID)
        self.assertEqual(result["adapter_process_invocations"], 2)
        interruption = ge.read_object(
            fixture.run_dir / "adapter/invocations/1-interrupted.json"
        )
        self.assertEqual(interruption["session_rollout"]["session_id"], SESSION_ID)
        manifest = ge.load_adapter_manifest(
            *self._contract(fixture),
        )
        self.assertEqual(manifest["session_id"], SESSION_ID)
        self.assertEqual(manifest["agent_logical_sessions"], 1)
        self.assertEqual(manifest["benchmark_candidate_calls"], 0)
        held = self._held(lambda: evaluator.evaluate(fixture.contract_path, session_roots=[fixture.sessions]))
        self.assertIn("objet absent", str(held.exception))
        artifacts_before_close = manifest["artifact_hashes"].copy()
        closed = ge.close_agent_branch(fixture.contract_path)
        self.assertFalse(closed["agent_reinvoked"])
        self.assertEqual(
            ge.load_adapter_manifest(*self._contract(fixture))["artifact_hashes"],
            artifacts_before_close,
        )
        terminal = evaluator.evaluate(fixture.contract_path, session_roots=[fixture.sessions])
        self.assertEqual(terminal["verdict"], ge.VERDICT_READY)
        self.assertEqual(terminal["tests_discovered"], {"repository": 3})
        report = ge.read_object(fixture.run_dir / "pilot-report.json")
        self.assertTrue(report["evaluation_start_matches_agent_end"])
        self.assertEqual(report["git_effects"]["agent_commits"], 0)

    def test_dirty_index_conflict_wrong_identity_symlink_and_lock_block_prepare(self) -> None:
        cases = ("dirty", "index", "conflict", "head", "branch", "symlink", "lock")
        for case in cases:
            with self.subTest(case=case):
                fixture = Fixture("B")
                try:
                    target = fixture.worktree / "tests/fixtures/graph_engineering_v2_2/target.txt"
                    if case == "dirty":
                        target.write_text("DIRTY\n")
                    elif case == "index":
                        target.write_text("STAGED\n")
                        git(fixture.worktree, "add", str(target.relative_to(fixture.worktree)))
                    elif case == "conflict":
                        relative = target.relative_to(fixture.worktree).as_posix()
                        base = git(fixture.worktree, "hash-object", str(target)).decode().strip()
                        ours = git(fixture.worktree, "hash-object", "-w", "--stdin", input_bytes=b"OURS\n").decode().strip()
                        theirs = git(fixture.worktree, "hash-object", "-w", "--stdin", input_bytes=b"THEIRS\n").decode().strip()
                        git(fixture.worktree, "update-index", "--force-remove", relative)
                        index_info = (
                            f"100644 {base} 1\t{relative}\n"
                            f"100644 {ours} 2\t{relative}\n"
                            f"100644 {theirs} 3\t{relative}\n"
                        ).encode()
                        git(fixture.worktree, "update-index", "--index-info", input_bytes=index_info)
                    elif case == "head":
                        git(fixture.worktree, "commit", "--allow-empty", "-m", "test: drift")
                    elif case == "branch":
                        git(fixture.worktree, "switch", "-c", "wrong-branch")
                    elif case == "symlink":
                        target.unlink()
                        target.symlink_to(fixture.root / "outside")
                    else:
                        contract, contract_sha = self._contract(fixture)
                        v1.write_new(ge.writer_lock_path(contract), {"foreign": contract_sha})
                    self._held(lambda target_fixture=fixture: ge.prepare(target_fixture.contract_path))
                    self.assertFalse(any(fixture.sessions.rglob("*.jsonl")))
                finally:
                    fixture.close()

    def test_contract_helper_prompt_evaluator_and_head_tampering_hold(self) -> None:
        cases = {
            "contract": lambda fixture: fixture.contract_path.write_bytes(fixture.contract_path.read_bytes() + b" "),
            "helper": lambda fixture: self._append(fixture.worktree / ge.EXECUTABLE_PATHS["helper_v1"]),
            "prompt": lambda fixture: self._append(fixture.worktree / "tests/fixtures/graph_engineering_v2_2_prompt.md"),
            "evaluator": lambda fixture: self._append(fixture.worktree / ge.EXECUTABLE_PATHS["evaluator"]),
            "head": lambda fixture: git(fixture.worktree, "commit", "--allow-empty", "-m", "test: new head"),
        }
        for case, mutate in cases.items():
            with self.subTest(case=case):
                fixture = Fixture("B")
                try:
                    mutate(fixture)
                    self._held(lambda target_fixture=fixture: ge.prepare(target_fixture.contract_path))
                finally:
                    fixture.close()

    def test_manual_manifest_divergence_second_session_and_extra_invocation_hold(self) -> None:
        manual = Fixture("B")
        try:
            ge.prepare(manual.contract_path)
            directory = manual.run_dir / "adapter"
            directory.mkdir()
            v1.write_new(directory / "manifest.json", {"manual": True})
            self._held(lambda: ge.close_agent_branch(manual.contract_path))
        finally:
            manual.close()

        divergent = Fixture("B")
        try:
            divergent.complete_agent()
            manifest_path = divergent.run_dir / "adapter/manifest.json"
            manifest_path.write_bytes(manifest_path.read_bytes() + b" ")
            self._held(lambda: ge.close_agent_branch(divergent.contract_path))
        finally:
            divergent.close()

        completed = Fixture("B")
        try:
            completed.complete_agent()
            contract, contract_sha = self._contract(completed)
            self._held(lambda: adapter.persist_session(contract, contract_sha, "second-session"))
            with patch.dict(os.environ, completed.agent_environment(), clear=False):
                self._held(lambda: adapter.run_adapter(
                    completed.contract_path,
                    resume=False,
                    interrupt_after_session=False,
                    session_roots=[completed.sessions],
                ))
        finally:
            completed.close()

    def test_native_sandbox_denies_write_outside_agent_root(self) -> None:
        codex = shutil.which("codex")
        if codex is None:
            self.skipTest("Codex CLI absent")
        index_path = Path(git(ROOT, "rev-parse", "--path-format=absolute", "--git-path", "index").decode().strip())
        before = {
            "head": git(ROOT, "rev-parse", "HEAD"),
            "branch": git(ROOT, "symbolic-ref", "HEAD"),
            "index": ge.digest(index_path.read_bytes()),
            "status": git(ROOT, "status", "--porcelain=v1", "-z", "--untracked-files=all"),
        }
        runs_root = ROOT / "runs"
        runs_root.mkdir(exist_ok=True)
        with TemporaryDirectory(prefix="ge22-sandbox-", dir=runs_root) as temporary:
            temporary_path = Path(temporary)
            scope = temporary_path / "scope"
            scope.mkdir()
            outside = temporary_path / "outside-scope.txt"
            process = subprocess.run(
                [
                    codex,
                    "sandbox",
                    "-P",
                    ":workspace",
                    "-C",
                    str(scope),
                    "--",
                    sys.executable,
                    "-c",
                    "from pathlib import Path; Path('../outside-scope.txt').write_text('forbidden')",
                ],
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(process.returncode, 0)
            self.assertFalse(outside.exists())
        after = {
            "head": git(ROOT, "rev-parse", "HEAD"),
            "branch": git(ROOT, "symbolic-ref", "HEAD"),
            "index": ge.digest(index_path.read_bytes()),
            "status": git(ROOT, "status", "--porcelain=v1", "-z", "--untracked-files=all"),
        }
        self.assertEqual(before, after)

    def test_missing_extra_and_modified_artifacts_hold_terminal(self) -> None:
        cases = {
            "missing": lambda fixture: (fixture.run_dir / "nodes/B/receipt.json").unlink(),
            "extra": lambda fixture: (fixture.run_dir / "unexpected.json").write_text("{}\n"),
            "modified": lambda fixture: self._append(fixture.run_dir / "nodes/J/receipt.json"),
        }
        for case, mutate in cases.items():
            with self.subTest(case=case):
                fixture = Fixture("B")
                try:
                    fixture.complete_agent()
                    ge.close_agent_branch(fixture.contract_path)
                    mutate(fixture)
                    self._held(lambda target_fixture=fixture: evaluator.evaluate(
                        target_fixture.contract_path,
                        session_roots=[target_fixture.sessions],
                    ))
                finally:
                    fixture.close()

    def test_traversal_and_request_symlink_are_rejected(self) -> None:
        traversal = Fixture("B", create_contract=False)
        try:
            traversal.request["agent_paths"] = ["../outside.txt"]
            traversal.write_request()
            self._held(lambda: ge.create_contract(traversal.request_path))
        finally:
            traversal.close()

        linked = Fixture("B", create_contract=False)
        try:
            prompt = linked.worktree / "tests/fixtures/graph_engineering_v2_2_prompt.md"
            prompt.unlink()
            prompt.symlink_to(linked.root / "outside-prompt")
            self._held(lambda: ge.create_contract(linked.request_path))
        finally:
            linked.close()

    @staticmethod
    def _append(path: Path) -> None:
        path.write_bytes(path.read_bytes() + b"#")

    @staticmethod
    def _contract(fixture: Fixture) -> tuple[dict[str, object], str]:
        return ge.load_contract(fixture.contract_path)

    def _held(self, callback):
        with self.assertRaises((ge.GraphHold, v1.PilotError)) as context:
            callback()
        return context


if __name__ == "__main__":
    unittest.main()
