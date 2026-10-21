"""Adversarial theorem-statement identity checks for external proof twins."""
import tempfile
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from vrml_external_bindings import markers, verify_bindings, strip_comments
from vrml_external import ContractError


NAME = "sample.increment.ensures_0"
DIGEST = "abcdef0123456789"
SOURCE = (f"-- vrml:begin {NAME} {DIGEST}\n"
          "/-- proof comment mentions sorry, which is not proof code -/\n"
          "@[vrml_obligation] theorem ensures_0\n"
          "    (x : Int) : x = x := by\n"
          "  rfl\n"
          f"-- vrml:end {NAME}\n")


class BindingGuardTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)
        self.gen = self.root / "src/generated/sample/increment.lean"
        self.twin = self.root / "src/proofs/sample/increment.lean"
        self.gen.parent.mkdir(parents=True)
        self.twin.parent.mkdir(parents=True)
        self.gen.write_text(SOURCE, encoding="utf-8")
        self.twin.write_text(SOURCE, encoding="utf-8")
        self.manifest = {"mode": "per-function", "obligations": [{
            "name": NAME, "statement_hash": DIGEST,
            "lean_file": "src/generated/sample/increment.lean"
        }]}

    def test_valid_signatures(self):
        verify_bindings(self.root, self.manifest)

    def test_altered_theorem_type_rejected(self):
        self.twin.write_text(SOURCE.replace("x = x", "x = 0"))
        with self.assertRaisesRegex(ContractError, "statement changed"):
            verify_bindings(self.root, self.manifest)

    def test_proof_hole_rejected(self):
        self.twin.write_text(SOURCE.replace("  rfl", "  sorry"))
        with self.assertRaisesRegex(ContractError, "proof hole"):
            verify_bindings(self.root, self.manifest)

    def test_axiom_declaration_rejected(self):
        self.twin.write_text(SOURCE + "\naxiom all_goals : False\n")
        with self.assertRaisesRegex(ContractError, "unchecked declaration"):
            verify_bindings(self.root, self.manifest)

    def test_statement_hash_rejected(self):
        self.twin.write_text(SOURCE.replace(DIGEST, "stale0000000000"))
        with self.assertRaisesRegex(ContractError, "statement hash"):
            verify_bindings(self.root, self.manifest)

    def test_missing_twin_rejected(self):
        self.twin.unlink()
        with self.assertRaises(ContractError):
            verify_bindings(self.root, self.manifest)

    def test_comment_keywords_ignored(self):
        self.twin.write_text(SOURCE.replace("  rfl", "  /- sorry -/\n  rfl"))
        verify_bindings(self.root, self.manifest)

    def test_extra_marker_rejected(self):
        self.twin.write_text(SOURCE + SOURCE.replace(NAME, "sample.increment.extra"))
        with self.assertRaises(ContractError):
            verify_bindings(self.root, self.manifest)


if __name__ == "__main__":
    unittest.main()
