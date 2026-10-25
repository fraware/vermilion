import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_dalek_completion import audit, complete


class FullConeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.generated = self.root / "generated"
        self.proofs = self.root / "proofs"
        self.generated.mkdir()
        self.proofs.mkdir()
        self.unit = self.generated / "core" / "unit.lean"
        self.unit.parent.mkdir()
        self.unit.write_text("theorem x : True := by\n  trivial\n")
        self.twin = self.proofs / "unit.lean"
        self.twin.write_text("theorem x : True := by\n  trivial\n")
        self.manifest = self.generated / "core.json"
        self.source = {
            "mode": "per-function",
            "obligations": [{"name": "core.x", "statement_hash": "0123456789abcdef", "lean_file": str(self.unit)}],
            "refused": [],
        }
        self.persist()

    def tearDown(self):
        self.temp.cleanup()

    def persist(self):
        self.manifest.write_text(json.dumps(self.source))

    def test_no_checker_cannot_pass(self):
        self.assertFalse(complete(self.generated, self.proofs, None, None)["accepted"])

    def test_refusals_block(self):
        self.source["refused"] = [{"function": "load8_at", "message": "missing termination"}]
        self.persist()
        self.assertEqual(audit(self.generated, self.proofs)["refused_count"], 1)

    def test_sorry_blocks(self):
        self.twin.write_text("theorem x : True := by\n  sorry\n")
        self.assertEqual(audit(self.generated, self.proofs)["tracked_admission_count"], 1)

    def test_missing_manifest_fails_closed(self):
        self.manifest.unlink()
        self.assertTrue(audit(self.generated, self.proofs)["problems"])

    def test_duplicate_obligation_fails(self):
        self.source["obligations"].append(self.source["obligations"][0])
        self.persist()
        self.assertTrue(audit(self.generated, self.proofs)["problems"])

    def test_missing_generated_file_fails(self):
        self.unit.unlink()
        self.assertTrue(audit(self.generated, self.proofs)["problems"])

    def test_bad_mode_fails(self):
        self.source["mode"] = "per-file"
        self.persist()
        self.assertTrue(audit(self.generated, self.proofs)["problems"])

    def test_missing_proof_fails(self):
        self.twin.unlink()
        self.assertTrue(audit(self.generated, self.proofs)["problems"])

    def test_failing_checker_cannot_pass(self):
        checker = self.root / "checker"
        checker.write_text("#!/bin/sh\nexit 1\n")
        checker.chmod(0o755)
        self.assertFalse(complete(self.generated, self.proofs, checker, checker)["accepted"])

    def test_checker_must_pass_exact_twin_flag(self):
        checker = self.root / "checker"
        checker.write_text('#!/bin/sh\n[ "$2" = "--twin-check" ] || exit 3\nexit 0\n')
        checker.chmod(0o755)
        probe = self.root / "sync"
        probe.write_text('#!/bin/sh\n[ "$2" = "--probe" ] || exit 5\nexit 0\n')
        probe.chmod(0o755)
        result = complete(self.generated, self.proofs, checker, probe)
        self.assertTrue(result["accepted"])
        self.assertTrue(result["kernel_checked"])

    def test_unverified_freshness_fails(self):
        checker = self.root / "checker"
        checker.write_text('#!/bin/sh\nexit 0\n')
        checker.chmod(0o755)
        probe = self.root / "sync"
        probe.write_text('#!/bin/sh\nexit 1\n')
        probe.chmod(0o755)
        result = complete(self.generated, self.proofs, checker, probe)
        self.assertFalse(result["accepted"])
        self.assertTrue(any("stale proof twin" in x for x in result["problems"]))

    def test_refusal_dedup_across_manifests(self):
        self.source["refused"] = [{"function": "recursive_fn", "message": "missing decrease"}]
        self.persist()
        (self.generated / "another.json").write_text(json.dumps(self.source))
        result = audit(self.generated, self.proofs)
        self.assertEqual(result["refused_count"], 1)
        self.assertEqual(result["refused_records_count"], 2)


if __name__ == "__main__":
    unittest.main()
