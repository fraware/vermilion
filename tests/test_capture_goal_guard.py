"""Cross-mode and adversarial checks of the generated Lean statement guard."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_capture_goals import CASES, inspect, obligation_file


def fixture(root, mode, *, sabotage=None):
    for stem, fn, quant, relation in CASES:
        record_name = f"{stem}.{fn}.ensures_0"
        digest = f"h_{stem}"
        lean_path = f"tests/differential/generated/{stem}.lean" if mode == "per-file" else f"tests/differential/generated/{stem}/{fn}.lean"
        symbol = '∀' if quant == 'forall' else '∃'
        expr = f"i_vrml_0 {relation} i"
        if sabotage == 'captured' and stem == CASES[0][0]:
            expr = f"i {relation} i"
        source = (f"-- vrml:begin {record_name} {digest}\n"
                  f"theorem ensures_0 (i : Int) : ({symbol} (i_vrml_0 : Int), ({expr})) := by\n"
                  f"  sorry\n"
                  f"-- vrml:end {record_name}\n")
        dest = root / lean_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(source, encoding='utf-8')
        rec = {"name": record_name, "statement_hash": digest}
        if mode == "per-function":
            rec["lean_file"] = lean_path
        manifest = {"mode": mode, "obligations": [rec], "refused": [],
                    "lean_file": lean_path if mode == "per-file" else f"tests/differential/generated/{stem}"}
        path = root / 'tests/differential/generated' / f'{stem}.json'
        path.write_text(json.dumps(manifest), encoding='utf-8')


class InspectTests(unittest.TestCase):
    def test_per_file_accepts_noncapturing_statement(self):
        with tempfile.TemporaryDirectory() as t:
            fixture(Path(t), 'per-file')
            self.assertEqual(inspect(Path(t)), [])

    def test_per_function_accepts_noncapturing_statement(self):
        with tempfile.TemporaryDirectory() as t:
            fixture(Path(t), 'per-function')
            self.assertEqual(inspect(Path(t)), [])

    def test_self_captured_statement_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            fixture(Path(t), 'per-file', sabotage='captured')
            self.assertTrue(any('noncapturing' in e for e in inspect(Path(t))))

    def test_missing_statement_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            fixture(Path(t), 'per-file')
            stem = CASES[0][0]
            (Path(t) / f'tests/differential/generated/{stem}.lean').unlink()
            self.assertTrue(any('missing or escaping' in e for e in inspect(Path(t))))

    def test_wrong_hash_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            fixture(Path(t), 'per-file')
            stem = CASES[0][0]
            path = Path(t) / f'tests/differential/generated/{stem}.json'
            manifest = json.loads(path.read_text())
            manifest['obligations'][0]['statement_hash'] = 'wrong_hash'
            path.write_text(json.dumps(manifest))
            self.assertTrue(any('statement/hash binding missing' in e for e in inspect(Path(t))))

    def test_per_function_missing_record_file_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            fixture(Path(t), 'per-function')
            stem = CASES[0][0]
            path = Path(t) / f'tests/differential/generated/{stem}.json'
            manifest = json.loads(path.read_text())
            manifest['obligations'][0].pop('lean_file')
            path.write_text(json.dumps(manifest))
            self.assertTrue(any('missing obligation Lean file' in e for e in inspect(Path(t))))

    def test_unknown_mode_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unexpected emission mode'):
            obligation_file({'mode': 'nonsense', 'lean_file': 'x'}, {})

    def test_refused_function_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            fixture(Path(t), 'per-file')
            stem = CASES[0][0]
            path = Path(t) / f'tests/differential/generated/{stem}.json'
            manifest = json.loads(path.read_text())
            manifest['refused'] = [{'function': 'x', 'message': 'refused'}]
            path.write_text(json.dumps(manifest))
            self.assertTrue(any('unsupported lowering' in e for e in inspect(Path(t))))


if __name__ == '__main__':
    unittest.main()
