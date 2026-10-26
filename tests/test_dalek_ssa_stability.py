"""Adversarial contract tests for the source-keyed experimental SSA guard."""
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_dalek_ssa_stability as guard


class TestStatementStability(unittest.TestCase):
    def setUp(self):
        self.original = {"existing.a": "hashA", "existing.b": "hashB"}
        patch = mock.patch.multiple(
            guard, CONTROL_VCS=2,
            CONTROL_FINGERPRINT=guard.fingerprint(self.original),
        )
        patch.start()
        self.addCleanup(patch.stop)
        self.document = {
            "source_sha": guard.SOURCE_SHA,
            "verus_sha": guard.VERUS_SHA,
            "whole_case_study_verified": False,
            "refused_functions": {},
            "source_keyed_obligations": {
                **self.original, guard.RECOVERED + "assert_0": "new",
            },
        }

    def test_exact_preservation_and_recovery(self):
        result = guard.validate_acquisition(self.document)
        self.assertEqual(result["preexisting_vcs_exactly_preserved"], 2)
        self.assertEqual(result["as_bytes_new_vcs"], 1)
        self.assertFalse(result["whole_case_study_verified"])

    def test_bad_source_or_verus_pin(self):
        for key in ("source_sha", "verus_sha"):
            with self.subTest(key=key):
                old = self.document[key]
                self.document[key] = "wrong"
                with self.assertRaises(ValueError):
                    guard.validate_acquisition(self.document)
                self.document[key] = old

    def test_changed_existing_statement(self):
        self.document["source_keyed_obligations"]["existing.a"] = "tampered"
        with self.assertRaises(ValueError):
            guard.validate_acquisition(self.document)

    def test_missing_existing_statement(self):
        del self.document["source_keyed_obligations"]["existing.b"]
        with self.assertRaises(ValueError):
            guard.validate_acquisition(self.document)

    def test_unrelated_new_statement(self):
        self.document["source_keyed_obligations"]["unrelated"] = "changed"
        with self.assertRaises(ValueError):
            guard.validate_acquisition(self.document)

    def test_missing_as_bytes(self):
        del self.document["source_keyed_obligations"][guard.RECOVERED + "assert_0"]
        with self.assertRaises(ValueError):
            guard.validate_acquisition(self.document)

    def test_refused_function(self):
        self.document["refused_functions"] = {"as_bytes": "still refused"}
        with self.assertRaises(ValueError):
            guard.validate_acquisition(self.document)

    def test_false_proof_claim(self):
        self.document["whole_case_study_verified"] = True
        with self.assertRaises(ValueError):
            guard.validate_acquisition(self.document)

    def test_wrong_vc_type(self):
        self.document["source_keyed_obligations"]["existing.a"] = 1
        with self.assertRaises(ValueError):
            guard.validate_acquisition(self.document)

    def test_unescaped_key_or_value(self):
        for obj in ({"bad\tkey": "a"}, {"key": "bad\nvalue"}):
            with self.subTest(obj=obj), self.assertRaises(ValueError):
                guard.fingerprint(obj)

    def test_duplicate_nested_keys(self):
        content = json.dumps(self.document).replace(
            '"existing.a": "hashA",',
            '"existing.a": "hashA", "existing.a": "malicious",',
        )
        with self.assertRaisesRegex(ValueError, "duplicate"):
            guard.load_receipt(content)

    def test_non_object_json(self):
        with self.assertRaises(ValueError):
            guard.load_receipt("[]")


if __name__ == "__main__":
    unittest.main()
