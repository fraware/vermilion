#!/usr/bin/env python3
"""Compare pinned BV preprocessing modes without implying source verification."""
import argparse
import json
import sys
from pathlib import Path

TRUE = "Const(Bool(true))"
KEYS = {
    "mul_lemmas.rs:227", "mul_lemmas.rs:231",
    "pow2k_lemmas.rs:236", "pow2k_lemmas.rs:240",
    "field_u64.rs:1431", "field_u64.rs:1446",
}


def inspect(path):
    report = json.loads(path.read_text(encoding="utf-8"))
    rows = report.get("observations", [])
    indexed = {r["source"]: r for r in rows}
    if len(rows) != len(KEYS) or set(indexed) != KEYS:
        raise ValueError(f"Missing, extra, or duplicate source keys in {path}")
    return indexed


def compare(original, unsimplified):
    old, new = inspect(original), inspect(unsimplified)
    details = []
    for key in sorted(KEYS):
        base, raw = old[key], new[key]
        if base["prepoly_SST_ensure_debug"] != TRUE:
            raise ValueError(f"Historical true SST query changed at {key}")
        if base["neutral_lowered_ensure_debug"] != "True":
            raise ValueError(f"Historical neutral True changed at {key}")
        if not base["generated_lean"]["literal_true_goal"]:
            raise ValueError(f"Historical Lean True goal changed at {key}")
        if not base["matches_historical_hash"]:
            raise ValueError(f"Historical statement hash drift at {key}")
        if raw["prepoly_SST_ensure_debug"] == TRUE:
            raise ValueError(f"Unsimplified query is still true in pinned SST: {key}")
        if raw["neutral_lowered_ensure_debug"] == "True":
            raise ValueError(f"Neutral lowering still erased the expression: {key}")
        if raw["generated_lean"]["literal_true_goal"]:
            raise ValueError(f"Generated Lean obligation is still literal True: {key}")
        details.append({
            "source_key": key,
            "original_SST": base["prepoly_SST_ensure_debug"],
            "preprocessing_disabled_SST": raw["prepoly_SST_ensure_debug"],
            "preprocessing_disabled_neutral": raw["neutral_lowered_ensure_debug"],
            "original_statement_hash": base["generated_lean"]["statement_hash"],
            "unsimplified_statement_hash": raw["generated_lean"]["statement_hash"],
        })
    return {
        "interpretation": "Expression simplification occurs in the pinned Verus SST elaborator before Vermilion lowering",
        "limit": "No Lean kernel checking or semantic equivalence certificate was performed",
        "samples": details,
    }


def main():
    arg = argparse.ArgumentParser()
    arg.add_argument("normal", type=Path)
    arg.add_argument("without_bv_simplification", type=Path)
    arg.add_argument("--output", type=Path, required=True)
    opts = arg.parse_args()
    try:
        data = compare(opts.normal, opts.without_bv_simplification)
        opts.output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print("All six source-keyed BV queries differ as expected across pinned modes")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"INCOMPLETE BV-mode comparison: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
