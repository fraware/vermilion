"""Real Lean integration tests for the transitive axiom guard."""
import sys
from pathlib import Path
import shutil
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_lean_axioms import audit_proof_unit, make_audit_source


@unittest.skipUnless(shutil.which("lean"), "pinned Lean not installed")
class LeanAxiomTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.file = Path(self.temp.name) / "Source.lean"

    def audit(self, code, names):
        self.file.write_text(code)
        return audit_proof_unit(self.file, names, timeout=50)

    def test_rfl_accepted(self):
        accepted, why = self.audit("theorem clean : 1 = 1 := by rfl\n", ["clean"])
        self.assertTrue(accepted, why)

    def test_classical_choice_allowed(self):
        accepted, why = self.audit(
            "theorem classical_ok (p : Prop) : p ∨ ¬ p := Classical.em p\n",
            ["classical_ok"],
        )
        self.assertTrue(accepted, why)

    def test_sorry_rejected(self):
        accepted, _ = self.audit("theorem bad : False := by sorry\n", ["bad"])
        self.assertFalse(accepted)

    def test_transitive_sorry_rejected(self):
        accepted, _ = self.audit(
            "theorem bad : False := by sorry\n"
            "theorem downstream : False := bad\n", ["downstream"])
        self.assertFalse(accepted)

    def test_custom_axiom_rejected(self):
        accepted, _ = self.audit(
            "axiom fabricated : False\n"
            "theorem derived : False := fabricated\n", ["derived"])
        self.assertFalse(accepted)

    def test_missing_declaration_rejected(self):
        accepted, _ = self.audit("theorem clean : True := by trivial\n", ["missing"])
        self.assertFalse(accepted)

    def test_non_theorem_rejected(self):
        accepted, _ = self.audit("def constant : Nat := 1\n", ["constant"])
        self.assertFalse(accepted)


    def test_full_acceptance_contract_safe_and_custom_axiom(self):
        import json
        from check_dalek_completion import complete
        root = Path(self.temp.name)
        generated = root / "generated"
        proofs = root / "proofs"
        (generated / "core").mkdir(parents=True)
        (proofs / "core").mkdir(parents=True)
        unit = "namespace core\n theorem x : True := by trivial\nend core\n"
        (generated / "core" / "unit.lean").write_text(unit)
        target = proofs / "core" / "unit.lean"
        target.write_text(unit)
        manifest = {"mode": "per-function",
                    "obligations": [{"name": "core.x", "statement_hash": "0123456789abcdef",
                                     "lean_file": str(generated / "core" / "unit.lean")}],
                    "refused": []}
        (generated / "core.json").write_text(json.dumps(manifest))
        checker = root / "checker"
        probe = root / "probe"
        for command in (checker, probe):
            command.write_text("#!/bin/sh\nexit 0\n")
            command.chmod(0o755)
        result = complete(generated, proofs, checker, probe)
        self.assertTrue(result["accepted"], result["problems"])
        self.assertTrue(result["kernel_checked"])
        self.assertTrue(result["axiom_dependencies_audited"])
        self.assertEqual(result["axiom_audited_units"], 1)
        self.assertEqual(result["status"], "ALL_GENERATED_TWINS_NATIVE_AND_AXIOMS_CHECKED")

        target.write_text("axiom poison : False\n"
                          "namespace core\n theorem x : True := False.elim poison\nend core\n")
        result = complete(generated, proofs, checker, probe)
        self.assertFalse(result["accepted"])
        self.assertTrue(result["kernel_checked"])
        self.assertFalse(result["axiom_dependencies_audited"])
        self.assertTrue(any("axiom audit" in p for p in result["problems"]))

    def test_injection_and_empty_lists_rejected(self):
        for names in ([], ["bad); #eval 42"], ["x", "x"]):
            with self.subTest(names=names), self.assertRaises(ValueError):
                make_audit_source("theorem x : True := by trivial\n", names)


if __name__ == "__main__":
    unittest.main()
