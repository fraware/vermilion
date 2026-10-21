#!/usr/bin/env python3
"""Fail-closed baseline-versus-fixed capture regression experiment.

This is a *causality* test, not a proof of translation soundness:
the old translator must accept specific known-false obligations, while
the fixed translator rejects them under exactly the same front end and
Lean installation.
"""
from __future__ import annotations
import argparse
import re
from pathlib import Path

STEMS = (
    "c_hygiene_01_ret_param",
    "c_hygiene_02_ret_param_ctrl",
    "c_hygiene_03_ret_param_exists",
    "c_hygiene_04_call_param",
    "c_hygiene_05_assert_alias",
    "c_hygiene_06_bounded",
)
FALSE_POSITIVE_CANDIDATES = {
    "c_hygiene_01_ret_param",
    "c_hygiene_04_call_param",
    "c_hygiene_05_assert_alias",
}
NEGATIVE = set(STEMS[:-1])
VALID = STEMS[-1]


def parse_report(path: Path) -> dict[str, tuple[str, str]]:
    if not path.is_file():
        raise ValueError(f"missing report: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    header = "| Case | Verus | Lean | Verdict | Failure lines |"
    if lines.count(header) != 1:
        raise ValueError(f"unexpected report header: {path}")
    position = lines.index(header)
    if position + 1 >= len(lines) or not lines[position + 1].startswith("|---"):
        raise ValueError(f"invalid table: {path}")
    verdicts = {}
    for line in lines[position+2:]:
        if not line.startswith("|"):
            break
        fields = [s.strip() for s in line.strip().strip("|").split("|")]
        if len(fields) != 5:
            raise ValueError(f"malformed verdict: {line}")
        name, verus, lean, note, _ = fields
        if name in verdicts or verus not in {"pass", "fail"} or lean not in {"pass", "fail"}:
            raise ValueError(f"duplicate or unclassified verdict: {line}")
        verdicts[name] = verus, lean
    if set(verdicts) != set(STEMS):
        raise ValueError(f"missing or extraneous fixtures: {set(STEMS) ^ set(verdicts)}")
    return verdicts


def evaluate(base: dict, fixed: dict) -> list[str]:
    errors = []
    for name in STEMS:
        expected = "pass" if name == VALID else "fail"
        if fixed[name] != (expected, expected):
            errors.append(f"fixed {name}: expected two {expected} verdicts, got {fixed[name]}")
        if base[name][0] != expected:
            errors.append(f"baseline Verus for {name}: expected {expected}, got {base[name][0]}")
    false_accepts = sorted(
        name for name in FALSE_POSITIVE_CANDIDATES
        if base[name] == ("fail", "pass")
    )
    if len(false_accepts) < 2:
        errors.append(
            "baseline reproduced fewer than two expected false acceptances: "
            + ", ".join(false_accepts)
        )
    if base[VALID] != ("pass", "pass"):
        errors.append(f"positive control changed under baseline: {base[VALID]}")
    if base["c_hygiene_02_ret_param_ctrl"] != ("fail", "fail"):
        errors.append(
            "the rename-only negative control did not remain correctly rejected"
        )
    print("baseline false acceptances:", ", ".join(false_accepts) or "<none>")
    print("fixed:", len(fixed), "of", len(STEMS), "Verus/Lean fixture decisions correct")
    return errors


def main() -> int:
    cli = argparse.ArgumentParser()
    cli.add_argument("baseline", type=Path)
    cli.add_argument("fixed", type=Path)
    args = cli.parse_args()
    try:
        errors = evaluate(parse_report(args.baseline), parse_report(args.fixed))
    except (ValueError, OSError) as exc:
        print(f"invalid experiment: {exc}")
        return 2
    for error in errors:
        print(f"FAIL: {error}")
    if errors:
        return 1
    print("PASS: old lowering independently reproduced false acceptance; "
          "fixed lowering rejected every negative fixture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
