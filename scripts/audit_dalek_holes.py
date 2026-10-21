#!/usr/bin/env python3
"""Inventory the exact residual dalek-lite Lean proof holes without proving them.

Classifies a goal literally True separately from a substantive theorem.
Neither class is counted as discharged; a kernel-checked proof is required.
"""
import argparse
import json
from pathlib import Path
import re
import sys

TARGETS = {
    "square2": "field_u64/layer_a_backend_serial_u64_field_impl__16_square2.lean",
    "lemma_pow2k_loop_boundary":
        "pow2k_lemmas/layer_a_lemmas_field_lemmas_pow2k_lemmas_lemma_pow2k_loop_boundary.lean",
    "lemma_mul_boundary":
        "field_lemmas_mul_lemmas/layer_a_lemmas_field_lemmas_mul_lemmas_lemma_mul_boundary.lean",
    "lemma_or_bit":
        "bit_lemmas/layer_a_lemmas_common_lemmas_bit_lemmas_lemma_or_bit.lean",
}
SORRY = re.compile(r"(?m)^\s*sorry\s*$")
START = re.compile(r"(?m)^-- vrml:begin (\S+) (\S+)\s*$")
TRUE_GOAL = re.compile(r"(?s):\s*True\s*:= by\s*$")


def inventory(root: Path) -> list[dict]:
    rows = []
    for unit, rel in TARGETS.items():
        filename = root / "case-studies/dalek-lite/proofs" / rel
        source = filename.read_text(encoding="utf-8")
        for match in SORRY.finditer(source):
            marker = list(START.finditer(source[:match.start()]))
            if not marker:
                raise ValueError(f"unbound hole in {filename}")
            name, digest = marker[-1].groups()
            region = source[marker[-1].end():match.start()]
            if ":= by" not in region or "@[vrml_obligation] theorem" not in region:
                raise ValueError(f"nonobligation proof hole in {filename}: {name}")
            header = region.split(":= by")[0]
            classification = "literal-True VC" if TRUE_GOAL.search(header + ":= by") else "substantive VC"
            rows.append({
                "unit": unit,
                "file": str(filename.relative_to(root)),
                "line": source.count("\n", 0, match.start()) + 1,
                "obligation": name,
                "statement_hash": digest,
                "classification": classification,
                "state": "unproved",
            })
    return rows


def main() -> int:
    cli = argparse.ArgumentParser()
    cli.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    cli.add_argument("--output", type=Path)
    args = cli.parse_args()
    rows = inventory(args.root)
    if args.output:
        args.output.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    for row in rows:
        print(f"{row['unit']}:{row['line']} {row['statement_hash']} {row['classification']}")
    kinds = [row["classification"] for row in rows]
    expected = {"literal-True VC": 6, "substantive VC": 2}
    found = {kind: kinds.count(kind) for kind in expected}
    print(f"Unproved: {len(rows)}; breakdown: {found}")
    if len(rows) != 8 or found != expected:
        print("Audit baseline changed: review all proof and translation evidence", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
