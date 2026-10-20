#!/usr/bin/env python3
"""Fail-closed exact verdict/coverage gate over the generated differential report."""
import re
import sys
from pathlib import Path

def gate(report: str, corpus: Path) -> tuple[int, str]:
    rows = report.splitlines()
    header = "| Case | Verus | Lean | Verdict | Failure lines |"
    if rows.count(header) != 1:
        return 2, "missing or ambiguous verdict table"
    idx = rows.index(header)
    if idx + 1 >= len(rows) or not rows[idx + 1].startswith("|---"):
        return 2, "missing verdict table separator"
    got = {}
    for line in rows[idx+2:]:
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 5:
            return 2, "malformed table row"
        name, verus, lean, note, _ = cells
        if not name or name in got:
            return 2, "duplicate or missing name"
        if verus not in ("pass", "fail") or lean not in ("pass", "fail"):
            return 2, f"missing or unjudged verifier outcome for {name}"
        if note != "ok":
            return 1, f"disagreement or invalid expectation for {name}: {note}"
        got[name] = (verus == "pass", lean == "pass")
    expected = {}
    for path in corpus.glob("*.rs"):
        first = path.read_text(encoding="utf-8").splitlines()[0]
        match = re.fullmatch(r"// expect: (pass|fail)(?: @ \d+)?", first)
        if not match:
            return 2, f"invalid expectation: {path.name}"
        expected[path.stem] = match.group(1) == "pass"
    if not expected or got.keys() != expected.keys():
        return 2, f"coverage mismatch: missing={sorted(expected.keys()-got.keys())}"
    for case, (verus, lean) in got.items():
        if not verus and lean:
            return 1, f"FALSE ACCEPTANCE: {case}"
        if verus != lean or verus != expected[case]:
            return 1, f"mismatch: {case}"
    return 0, f"all {len(got)} differential cases agreed with Verus and expectations"

if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: differential_soundness.py REPORT CORPUS")
    path, corpus = Path(sys.argv[1]), Path(sys.argv[2])
    if not path.is_file():
        raise SystemExit("missing differential report")
    code, message = gate(path.read_text(encoding="utf-8"), corpus)
    print(message)
    sys.exit(code)
