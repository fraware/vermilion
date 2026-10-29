"""Adversarial tests for the dalek-lite full-unit outcome classifier."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from classify_dalek_tracked_unit import RUNG_FAILURE, classify

SOURCE = "case-studies/dalek-lite/proofs/field_u64/unit.lean"
DIAGNOSTIC = f"{SOURCE}:42:2: error: {RUNG_FAILURE}\n"


class DalekUnitClassifierTests(unittest.TestCase):
    def test_clean_success(self):
        self.assertEqual(classify(SOURCE, 0, "", "")["status"], "compiled")

    def test_multi_error_failure_is_incomplete(self):
        result = classify(SOURCE, 1, DIAGNOSTIC * 3, "")
        self.assertEqual(result["status"], "known_automation_failure")
        self.assertEqual(result["error_count"], 3)
        self.assertFalse(result["whole_unit_compiled"])

    def test_success_with_unexpected_output_is_rejected(self):
        with self.assertRaises(ValueError):
            classify(SOURCE, 0, "sorryAx", "")

    def test_unexpected_exit_status_is_rejected(self):
        for code in (2, 137):
            with self.subTest(code=code), self.assertRaises(ValueError):
                classify(SOURCE, code, DIAGNOSTIC, "")


    def test_empty_timeout_is_incomplete_not_proof(self):
        result = classify(SOURCE, 124, "", "")
        self.assertEqual(result["status"], "resource_timeout_incomplete")
        self.assertFalse(result["whole_unit_compiled"])
        self.assertTrue(result["timed_out"])

    def test_timeout_with_unexpected_output_is_rejected(self):
        for out, err in ((DIAGNOSTIC, ""), ("", "error: compiler fault"),
                         ("sorryAx", "")):
            with self.subTest(out=out, err=err), self.assertRaises(ValueError):
                classify(SOURCE, 124, out, err)

    def test_missing_diagnostic_is_rejected(self):
        with self.assertRaises(ValueError):
            classify(SOURCE, 1, "", "")

    def test_unexpected_error_is_rejected(self):
        for output in ("unit.lean:2:1: error: unknown constant\n",
                       DIAGNOSTIC + "unit.lean:5:1: error: unknown constant\n"):
            with self.subTest(output=output), self.assertRaises(ValueError):
                classify(SOURCE, 1, output, "")

    def test_stray_source_is_rejected(self):
        with self.assertRaises(ValueError):
            classify(SOURCE, 1, DIAGNOSTIC.replace(SOURCE, "other.lean"), "")

    def test_stderr_is_rejected(self):
        with self.assertRaises(ValueError):
            classify(SOURCE, 1, DIAGNOSTIC, "Lean warning")

    def test_forbidden_axiom_diagnostic_is_rejected(self):
        for needle in ("sorryAx", "Lean.trustCompiler", "admit", "_native.foo"):
            with self.subTest(needle=needle), self.assertRaises(ValueError):
                classify(SOURCE, 1, DIAGNOSTIC + needle, "")


if __name__ == "__main__":
    unittest.main()
