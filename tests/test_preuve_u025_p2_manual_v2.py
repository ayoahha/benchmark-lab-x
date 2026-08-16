from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from tools import preuve_u025_p2_manual_v2 as p2v2


class PreuveU025P2ManualV2Tests(unittest.TestCase):
    def test_prepare_reprend_apres_une_frontiere_sans_recrire_les_objets_fermes(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            proof_dir = Path(temporary_directory) / "p2-manual-v2"

            interrupted = p2v2.prepare(
                p2v2.GIT_BASE,
                proof_dir=proof_dir,
                interrupt_after_receipts=3,
            )
            closed_objects = {
                path.name: path.read_bytes()
                for path in (proof_dir / "artifacts").iterdir()
            }

            self.assertEqual("INTERRUPTED", interrupted["state"])
            self.assertEqual(3, interrupted["prepare_receipts"])

            resumed = p2v2.prepare(p2v2.GIT_BASE, proof_dir=proof_dir)

            self.assertEqual("PREPARED", resumed["state"])
            self.assertEqual(16, resumed["prepare_receipts"])
            self.assertEqual(
                closed_objects,
                {
                    name: (proof_dir / "artifacts" / name).read_bytes()
                    for name in closed_objects
                },
            )
            resume_events = [
                json.loads(line)
                for line in (proof_dir / "resume-events.jsonl").read_bytes().splitlines()
            ]
            self.assertEqual(
                resume_events[0]["closed_register_tail_sha256"],
                resume_events[1]["closed_register_tail_sha256"],
            )

    def test_finalize_refuse_un_tail_prepare_divergent(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            proof_dir = Path(temporary_directory) / "p2-manual-v2"
            p2v2.prepare(p2v2.GIT_BASE, proof_dir=proof_dir)
            prepare_root_path = proof_dir / "prepare-root.json"
            prepare_root = json.loads(prepare_root_path.read_bytes())
            prepare_root["register_tail_sha256"] = "0" * 64
            prepare_root_path.write_bytes(p2v2.canonical(prepare_root))

            with self.assertRaises(p2v2.InvalidProof):
                p2v2.finalize(
                    p2v2.V1_PROOF / "human-input.json",
                    proof_dir=proof_dir,
                )

    def test_finalize_refuse_un_human_input_v1_divergent(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            proof_dir = temporary_path / "p2-manual-v2"
            human_input = temporary_path / "human-input.json"
            human_input.write_bytes(
                (p2v2.V1_PROOF / "human-input.json").read_bytes() + b"\n"
            )
            p2v2.prepare(p2v2.GIT_BASE, proof_dir=proof_dir)

            with self.assertRaises(p2v2.InvalidProof):
                p2v2.finalize(human_input, proof_dir=proof_dir)

    def test_finalize_reprend_apres_un_recu_humain_sans_recrire_les_objets_fermes(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            proof_dir = Path(temporary_directory) / "p2-manual-v2"
            p2v2.prepare(p2v2.GIT_BASE, proof_dir=proof_dir)

            interrupted = p2v2.finalize(
                p2v2.V1_PROOF / "human-input.json",
                proof_dir=proof_dir,
                interrupt_after_human_receipts=2,
            )
            closed_objects = {
                path.name: path.read_bytes()
                for path in (proof_dir / "artifacts").iterdir()
            }

            self.assertEqual("INTERRUPTED", interrupted["state"])
            self.assertEqual(2, interrupted["human_receipts"])

            resumed = p2v2.finalize(
                p2v2.V1_PROOF / "human-input.json",
                proof_dir=proof_dir,
            )

            self.assertEqual("FINALIZED", resumed["state"])
            self.assertEqual(12, resumed["human_receipts"])
            self.assertEqual(16, resumed["final_receipts"])
            self.assertEqual(
                closed_objects,
                {
                    name: (proof_dir / "artifacts" / name).read_bytes()
                    for name in closed_objects
                },
            )
            resume_events = [
                json.loads(line)
                for line in (proof_dir / "resume-events.jsonl").read_bytes().splitlines()
            ]
            human_events = [event for event in resume_events if event["stage"] == "HUMAN"]
            self.assertEqual(
                human_events[0]["closed_register_tail_sha256"],
                human_events[1]["closed_register_tail_sha256"],
            )


if __name__ == "__main__":
    unittest.main()
