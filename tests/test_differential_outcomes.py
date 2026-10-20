"""Regression tests for strict differential outcome distinctions."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from differential_outcomes import classify_verus, classify_lean

class OutcomeTests(unittest.TestCase):
    def test_success(self):
        self.assertEqual(classify_verus(0, "verification results:: 1 verified, 0 errors", "").status, "verified")
    def test_reject(self):
        self.assertEqual(classify_verus(1, "", "error: postcondition not satisfied\n --> x.rs:9:1\nverification results:: 0 verified, 1 errors").status, "rejected")
    def test_compiler_error_not_rejection(self):
        self.assertEqual(classify_verus(1, "", "error[E0308]: mismatched types\n --> x.rs:9:1\nverification results:: 0 verified, 1 errors").status, "infrastructure")
    def test_missing_summary(self):
        self.assertEqual(classify_verus(1, "", "error: proof failed\n --> x.rs:9:1").status, "infrastructure")
    def test_crash(self):
        self.assertEqual(classify_verus(101, "", "thread panicked at foo").status, "infrastructure")
    def test_lean_missing_module(self):
        import json
        error = json.dumps({"$message_type":"diagnostic", "level":"error", "code":{"code":"vermilion::obligation_failed"}, "vermilion":{"obligation":"a"}, "spans":[{"is_primary":True,"line_start":3}]})
        self.assertEqual(classify_lean(1,error,"error: cannot find module Foo").status, "infrastructure")
    def test_lean_reject(self):
        import json
        error = json.dumps({"$message_type":"diagnostic", "level":"error", "code":{"code":"vermilion::obligation_failed"}, "vermilion":{"obligation":"a"}, "spans":[{"is_primary":True,"line_start":3}]})
        self.assertEqual(classify_lean(1,error,"").status, "rejected")
    def test_lean_unstructured_failure(self):
        self.assertEqual(classify_lean(1, "", "error: failed").status, "infrastructure")

    def test_covered_twin_is_informational(self):
        import json
        receipt = json.dumps({
            "$message_type": "diagnostic", "level": "error",
            "code": {"code": "vermilion::obligation_failed"},
            "vermilion": {"obligation": "ensures_0", "covered_by_twin": True},
            "spans": [{"is_primary": True, "line_start": 9}],
        })
        self.assertEqual(classify_lean(0, receipt, "").status, "verified")
        self.assertEqual(classify_lean(1, receipt, "").status, "infrastructure")

    def test_unresolved_evidence_stays_rejected(self):
        import json
        diagnostic = json.dumps({
            "$message_type": "diagnostic", "level": "error",
            "code": {"code": "vermilion::evidence_unresolved"},
            "vermilion": {"obligation": "evidence_0", "covered_by_twin": False},
            "spans": [{"is_primary": True, "line_start": 7}],
        })
        self.assertEqual(classify_lean(1, diagnostic, "").status, "rejected")
        self.assertEqual(classify_lean(0, diagnostic, "").status, "infrastructure")

    def test_verus_proof_failure_not_compiler_failure(self):
        stderr = ("error: postcondition not satisfied\n"
                  "  --> tests/differential/x.rs:7:11\n"
                  "error: aborting due to 1 previous error\n"
                  "verification results:: 0 verified, 1 errors")
        self.assertEqual(classify_verus(1, "", stderr).status, "rejected")

if __name__ == "__main__":
    unittest.main()
