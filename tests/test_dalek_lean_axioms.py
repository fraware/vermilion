"""Adversarial tests for Lean transitive-axiom receipt parsing."""
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_dalek_lean_axioms import parse_report

N = "layer_a.backend.serial.u64.field.impl__16.as_bytes.assert_13"
M = "layer_a.backend.serial.u64.field.impl__16.as_bytes.assert_16"


class AxiomAuditTests(unittest.TestCase):
    def test_standard_axioms(self):
        message = f"Proof.lean:10:1: info: '{N}' depends on axioms: [propext, Classical.choice, Quot.sound]"
        self.assertEqual(parse_report(message, {N})[N],
                         ["Classical.choice", "Quot.sound", "propext"])

    def test_axiom_free(self):
        self.assertEqual(parse_report(f"'{N}' does not depend on any axioms", {N})[N], [])

    def test_imported_sorry_rejected(self):
        with self.assertRaisesRegex(ValueError, "unapproved"):
            parse_report(f"'{N}' depends on axioms: [sorryAx]", {N})

    def test_custom_axiom_rejected(self):
        with self.assertRaisesRegex(ValueError, "unapproved"):
            parse_report(f"'{N}' depends on axioms: [User.assumeProof]", {N})

    def test_missing_report_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            parse_report(f"'{N}' does not depend on any axioms", {N, M})

    def test_duplicate_report_rejected(self):
        line = f"'{N}' does not depend on any axioms"
        with self.assertRaisesRegex(ValueError, "duplicate"):
            parse_report(line + "\n" + line, {N})

    def test_unexpected_report_rejected(self):
        with self.assertRaisesRegex(ValueError, "unexpected"):
            parse_report(f"'{M}' does not depend on any axioms", {N})

    def test_empty_axiom_list_rejected(self):
        with self.assertRaisesRegex(ValueError, "malformed"):
            parse_report(f"'{N}' depends on axioms: []", {N})


if __name__ == "__main__":
    unittest.main()
