#!/usr/bin/env python3
"""Classify native Lean runs of selected dalek-lite tracked proof units.

Only zero-diagnostic successful elaboration or an exact, known vrml tactic
failure is accepted as evidence. A known failure is not proof of its unit.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

# Pin the spelling to the native Lean 4.33 vrml diagnostic. Diagnostic changes
# must be reviewed, rather than silently expanding the accepted error class.
RUNG_FAILURE = """vrml: no ladder rung closed the goal (tried [grind,
 omega,
 simp_all,
 simp_omega,
 simp_disch_omega,
 split_ifs,
 split_ifs_hyps,
 split_clip_ifs,
 guard_split,
 clip_nlinarith,
 nlinarith,
 scalar_saturate,
 smt])"""
FORBIDDEN = re.compile(r"\b(?:sorryAx|admit|Lean\.trustCompiler|Lean\.ofReduceBool)\b|_native\.")


def classify(source: str, exit_code: int, stdout: str, stderr: str) -> dict:
    """Classify one Lean process; all unexpected results fail closed.

    The source must be the exact repo-relative Lean path passed to Lean.
    Errors in unrelated paths, timeouts, and compiler diagnostics are rejected.
    """
    if exit_code == 0 and not stdout.strip() and not stderr.strip():
        return {"status": "compiled", "error_count": 0, "whole_unit_compiled": True}
    # A bounded Lean run which exhausted its wall-clock budget is
    # INCONCLUSIVE, not a failed proof or successful kernel check. Accept
    # only a clean timeout receipt with no partial diagnostics; unexpected
    # output continues to fail closed.
    if exit_code == 124 and not stdout.strip() and not stderr.strip():
        return {"status": "resource_timeout_incomplete", "error_count": 0,
                "whole_unit_compiled": False, "timed_out": True}
    if exit_code != 1 or stderr.strip() or FORBIDDEN.search(stdout):
        raise ValueError("unexpected exit, stderr, or forbidden proof diagnostic")
    pattern = re.compile(
        rf"{re.escape(source)}:[1-9][0-9]*:[1-9][0-9]*: error: "
        + re.escape(RUNG_FAILURE) + r"\n?"
    )
    matches = list(pattern.finditer(stdout))
    if not matches or pattern.sub("", stdout).strip():
        raise ValueError("unrecognized Lean error or additional output")
    return {"status": "known_automation_failure", "error_count": len(matches),
            "whole_unit_compiled": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stem", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--exit-code", required=True, type=int)
    parser.add_argument("--stdout", required=True, type=Path)
    parser.add_argument("--stderr", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = classify(args.source, args.exit_code,
                          args.stdout.read_text(encoding="utf-8"),
                          args.stderr.read_text(encoding="utf-8"))
    except (ValueError, OSError) as error:
        print(f"UNEXPECTED_LEAN_OUTCOME {args.stem}: {error}", file=sys.stderr)
        return 2
    result.update({"stem": args.stem, "source": args.source,
                   "exit_code": args.exit_code, "complete_case_study_verified": False})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(f"DALEK_TRACKED_UNIT {args.stem} {result['status']} errors={result['error_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
