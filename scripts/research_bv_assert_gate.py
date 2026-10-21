#!/usr/bin/env python3
"""Evaluate research-only nested and direct bit-vector controls without an aggregate parity threshold.

A PASS refutes false acceptance for the specified five cases and versions only.
A FAIL with a Verus reject / Lean accept is an empirical discrepancy to investigate,
not yet proof that every translation of the construct is unsound.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys

EXPECTED = {
    "c_research_bv_01_nested_false": "fail",
    "c_research_bv_02_valid": "pass",
    "c_research_bv_03_false_outer": "fail",
    "c_research_bv_04_direct_false": "fail",
    "c_research_bv_05_direct_valid": "pass",
}
HEADER = "| Case | Verus | Lean | Verdict | Failure lines |"

def evaluate(report: str) -> tuple[int, str]:
    lines = report.splitlines()
    if lines.count(HEADER) != 1:
        return 2, "Missing or duplicated differential report header"
    start = lines.index(HEADER)
    if len(lines) <= start + 1 or not lines[start + 1].startswith("|---"):
        return 2, "Malformed report table"
    seen: dict[str, tuple[str, str, str]] = {}
    for line in lines[start + 2:]:
        if not line.startswith("|"):
            break
        columns = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(columns) != 5:
            return 2, "Malformed verdict table row"
        name, verus, lean, verdict, _ = columns
        if name in seen:
            return 2, f"Duplicate case {name}"
        seen[name] = (verus, lean, verdict)
    if set(seen) != set(EXPECTED):
        return 2, f"Case coverage mismatch: {sorted(seen)}"
    for name, expected in EXPECTED.items():
        verus, lean, verdict = seen[name]
        if verus not in ("pass", "fail") or lean not in ("pass", "fail"):
            return 2, f"{name}: infrastructure/unjudged result: Verus={verus}, Lean={lean}"
        if verus != expected:
            return 2, f"{name}: pinned Verus disagreed with fixture expectation: {verus}"
        if lean != expected or verdict != "ok":
            return 1, f"{name}: Verus={verus}, Lean={lean}, classification={verdict}"
    return 0, "All five research fixtures show expected, matching native Verus/Lean verdicts"

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    options = parser.parse_args()
    try:
        status, message = evaluate(options.report.read_text(encoding="utf-8"))
    except OSError as error:
        status, message = 2, f"Cannot read report: {error}"
    print(message)
    return status

if __name__ == "__main__":
    sys.exit(main())
