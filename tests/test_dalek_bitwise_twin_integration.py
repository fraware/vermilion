import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from migrate_dalek_bitwise_twin import migrate
from research_dalek_bitwise_proofs import SOURCE, ORIGINAL


class TwinIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding="utf-8")

    def test_preserves_both_statement_hashes(self):
        updated, receipt = migrate(self.source)
        self.assertEqual(len(receipt["migrated_obligations"]), 2)
        for digest, _ in ORIGINAL:
            self.assertEqual(updated.count('statementHash := "' + digest + '"'), 1)
        self.assertEqual(updated.count("namespace collision_635d62c1"), 1)

    def test_original_is_never_modified(self):
        before = SOURCE.read_bytes()
        migrate(self.source)
        self.assertEqual(before, SOURCE.read_bytes())

    def test_wrong_hash_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "historical source hash"):
            migrate(self.source.replace("0a4e09fc4eccff1f", "eeeeeeeeeeeeeeee"))

    def test_tactic_drift_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "helper tactic"):
            migrate(self.source.replace("  bv_decide\n", "  simp\n", 1))

    def test_changed_proof_body_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "tracked admission"):
            migrate(self.source.replace(
                "  -- TODO(vermilion): automation failed; prove this obligation.\n  sorry\n",
                "  simp\n", 1,
            ))


if __name__ == "__main__":
    unittest.main()
