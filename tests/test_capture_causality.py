"""Adversarial structural tests for the capture causality comparison."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from capture_causality import STEMS, evaluate, parse_report


def report(rows):
    out = [
        "| Case | Verus | Lean | Verdict | Failure lines |",
        "|---|---|---|---|---|",
    ]
    out.extend(
        f"| {name} | {v} | {l} | ok | |"
        for name, (v, l) in rows.items()
    )
    return "\n".join(out)


class CompareTests(unittest.TestCase):
    def setUp(self):
        self.fixed = {
            n: ("pass", "pass") if n.endswith("06_bounded") else ("fail", "fail")
            for n in STEMS
        }
        self.base = self.fixed.copy()
        self.base["c_hygiene_01_ret_param"] = ("fail", "pass")
        self.base["c_hygiene_04_call_param"] = ("fail", "pass")
        self.base["c_hygiene_05_assert_alias"] = ("fail", "pass")

    def test_expected_causality(self):
        self.assertEqual(evaluate(self.base, self.fixed), [])

    def test_false_acceptance_not_observed_fails(self):
        self.assertTrue(evaluate(self.fixed, self.fixed))

    def test_bad_fixed_case_fails(self):
        fixed = self.fixed.copy()
        fixed["c_hygiene_01_ret_param"] = ("fail", "pass")
        self.assertTrue(evaluate(self.base, fixed))

    def test_changed_positive_control_fails(self):
        base = self.base.copy()
        base["c_hygiene_06_bounded"] = ("pass", "fail")
        self.assertTrue(evaluate(base, self.fixed))

    def test_changed_rename_only_control_fails(self):
        base = self.base.copy()
        base["c_hygiene_02_ret_param_ctrl"] = ("fail", "pass")
        self.assertTrue(evaluate(base, self.fixed))

    def test_malformed_table_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"bad.md"
            path.write_text(report(self.fixed).replace("c_hygiene_05_assert_alias", "duplicate"),
                            encoding="utf-8")
            with self.assertRaises(ValueError):
                parse_report(path)

    def test_valid_table_accepted(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"ok.md"
            path.write_text(report(self.fixed),encoding="utf-8")
            self.assertEqual(parse_report(path),self.fixed)


if __name__=="__main__":
    unittest.main()
