"""Adversarial contract tests for isolated dalek BV original-context replay."""
import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from replay_dalek_bv_contexts import source_declaration, validate_original_imports


HEADER = "import Vermilion.Obligations\nimport generated.field_u64.Specs\n\n"
GOAL = """namespace example
-- vrml:begin example.assert_bv_0 0123456789abcdef
@[vrml_obligation] theorem assert_bv_0
    (v : Int)
    (h : True) :
    (1 : Int) = 1 := by
  sorry
-- vrml:end example.assert_bv_0
end example
"""


class OriginalContextReplayTests(unittest.TestCase):
    def test_exact_import_namespace_and_order(self):
        self.assertEqual(
            validate_original_imports(HEADER, "field_u64", "field_u64.rs:1431"),
            ["Vermilion.Obligations", "generated.field_u64.Specs"],
        )

    def test_generator_may_omit_unused_specs(self):
        self.assertEqual(
            validate_original_imports("import Vermilion.Obligations\n",
                                      "pow2k_lemmas", "pow2k_lemmas.rs:236"),
            ["Vermilion.Obligations"],
        )

    def test_unexpected_namespace_refused(self):
        with self.assertRaisesRegex(ValueError, "unexpected"):
            validate_original_imports(
                "import Vermilion.Obligations\nimport generated.bad.Specs\n",
                "field_u64", "field_u64.rs:1431",
            )

    def test_duplicate_import_refused(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_original_imports(
                "import Vermilion.Obligations\nimport Vermilion.Obligations\n",
                "field_u64", "field_u64.rs:1431",
            )

    def test_missing_obligations_refused(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            validate_original_imports(
                "import generated.field_u64.Specs\n",
                "field_u64", "field_u64.rs:1431",
            )

    def test_exact_original_header_with_two_binders(self):
        with tempfile.TemporaryDirectory() as td:
            file = Path(td) / "source.lean"
            file.write_text(HEADER + GOAL)
            header, imports, binder_count = source_declaration(
                file, "example.assert_bv_0", "0123456789abcdef"
            )
        self.assertIn("(v : Int)", header)
        self.assertIn("(h : True)", header)
        self.assertIn("(1 : Int) = 1", header)
        self.assertEqual(binder_count, 2)
        self.assertEqual(imports.strip(), HEADER.strip())

    def test_wrong_hash_refused(self):
        with tempfile.TemporaryDirectory() as td:
            file = Path(td) / "source.lean"
            file.write_text(HEADER + GOAL)
            with self.assertRaisesRegex(ValueError, "missing/duplicate"):
                source_declaration(file, "example.assert_bv_0", "0000000000000000")


if __name__ == "__main__":
    unittest.main()
