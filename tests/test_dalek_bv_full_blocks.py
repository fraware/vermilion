"""Regression tests for exact untouched metadata and theorem headers."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from replay_dalek_bv_full_blocks import select_exact_block

TEXT = """import Vermilion.Obligations
namespace example
-- vrml:begin example.assert_bv_0 0123456789abcdef
def assert_bv_0_meta : Vermilion.ObligationMeta := {
  statementHash := "0123456789abcdef"
}
@[vrml_obligation] theorem assert_bv_0
    (n : Int)
    (h : True) :
    (2 : Int) = 2 := by
  -- Existing automation not automatically trusted.
  sorry
-- vrml:end example.assert_bv_0
end example
"""


class GeneratedBlockTests(unittest.TestCase):
    def pick(self, content=TEXT, digest="0123456789abcdef"):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "original.lean"
            p.write_text(content, encoding="utf-8")
            return select_exact_block(p, "example.assert_bv_0", digest)

    def test_keeps_complete_generated_header(self):
        r = self.pick()
        self.assertIn("statementHash := \"0123456789abcdef\"", r["patched_block"])
        self.assertIn("(n : Int)", r["patched_block"])
        self.assertIn("(h : True)", r["patched_block"])
        self.assertIn("(2 : Int) = 2 := by", r["patched_block"])
        self.assertIn("@[vrml_obligation] theorem assert_bv_0", r["patched_block"])
        self.assertIn("  decide", r["patched_block"])
        self.assertNotIn("  sorry", r["patched_block"])

    def test_wrong_digest_fails(self):
        with self.assertRaisesRegex(ValueError, "missing or duplicated"):
            self.pick(digest="ffffffffffffffff")

    def test_metadata_digest_drift_fails(self):
        with self.assertRaisesRegex(ValueError, "metadata statement hash"):
            self.pick(TEXT.replace('statementHash := "0123456789abcdef"',
                                   'statementHash := "aaaaaaaaaaaaaaaa"'))

    def test_duplicate_exact_markers_fail(self):
        with self.assertRaisesRegex(ValueError, "missing or duplicated"):
            self.pick(TEXT + "\n" + TEXT)

    def test_deleted_end_marker_fails(self):
        with self.assertRaisesRegex(ValueError, "missing/duplicated end"):
            self.pick(TEXT.replace("-- vrml:end example.assert_bv_0", ""))


if __name__ == "__main__":
    unittest.main()
