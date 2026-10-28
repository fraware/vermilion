#!/usr/bin/env python3
"""Source-keyed carry-times-19 VC candidate; certification is by pinned Lean CI."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

TARGET = "layer_a.backend.serial.u64.field.impl__16.as_bytes"
NAME = TARGET + ".assert_24"
PIN = "722ade88657f727b1e01ff1980cb95037cd8ca15c9134b757f56cd5e6b5b641c"
M = "18446744073709551616"
L = "Vermilion.Seq.index (layer_a.backend.serial.u64.field.FieldElement51.get_FieldElement51_limbs tmp_)"
x = [f"{L} {i}" for i in range(5)]
e0 = f"({x[0]} + 19)"
c0 = f"Vermilion.Bits.shr 64 ({e0} % {M}) 51"
e1 = f"({x[1]} + {c0})"
c1 = f"Vermilion.Bits.shr 64 ({e1} % {M}) 51"
e2 = f"({x[2]} + {c1})"
c2 = f"Vermilion.Bits.shr 64 ({e2} % {M}) 51"
e3 = f"({x[3]} + {c2})"
c3 = f"Vermilion.Bits.shr 64 ({e3} % {M}) 51"
e4 = f"({x[4]} + {c3})"
c4 = f"Vermilion.Bits.shr 64 ({e4} % {M}) 51"
GOAL = f"Vermilion.inUnsignedRange 64 (19 * {c4})"
BLOCK = re.compile(
    r"(?ms)^-- vrml:begin (?P<name>[^\n ]+) (?P<hash>[a-f0-9]{16})\n"
    r"(?P<body>.*?)^-- vrml:end (?P=name)$"
)

def generate(index: Path, modules: Path, output: Path, report: Path) -> None:
    idx = json.loads(index.read_text())
    rows = idx["obligations"]
    if idx["target_function"] != TARGET or idx["obligation_count"] != 156:
        raise ValueError("pinned target or obligation count changed")
    if len(rows) != 156 or len({r["name"] for r in rows}) != 156:
        raise ValueError("duplicate or missing source-keyed obligation")
    paths = {r["module"] for r in rows}
    if len(paths) != 1:
        raise ValueError("unexpected generated module count")
    source = (modules / next(iter(paths))).resolve()
    if not source.is_relative_to(modules.resolve()):
        raise ValueError("path outside generated proof root")
    content = source.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if digest != PIN or any(r["module_sha256"] != PIN for r in rows):
        raise ValueError("generated module SHA-256 changed")
    indexed = {r["name"]: r["statement_hash"] for r in rows}
    original = content.decode("utf-8")
    blocks = list(BLOCK.finditer(original))
    if len(blocks) != 156 or {b["name"] for b in blocks} != set(indexed):
        raise ValueError("mismatched generated theorem inventory")
    if any(b["hash"] != indexed[b["name"]] for b in blocks):
        raise ValueError("source-keyed theorem hash mismatch")
    matches = [b for b in blocks if b["name"] == NAME]
    if len(matches) != 1 or matches[0]["body"].count(" := by\n") != 1:
        raise ValueError("target source theorem missing or malformed")
    match = matches[0]
    decl, _old_proof = match["body"].split(" := by\n", 1)
    if ("@[vrml_obligation] theorem assert_24" not in decl
        or decl.rsplit(" :\n", 1)[-1].strip() != GOAL):
        raise ValueError("original theorem statement or name changed")
    for required in (
        "(assert_22 : Vermilion.inUnsignedRange 64 ",
        "(assert_23 : (0 ≤ 51) ∧ (51 < 64)",
        "(call_reduce_ensures_1 : (∀ (vrml_i0 : Int)",
        "(call_reduce_ensures_3 : layer_a.specs.field_specs.fe51_limbs_bounded tmp_ 52)",
    ):
        if required not in decl:
            raise ValueError("required original hypothesis missing: " + required)
    proof = f"""  have hprev_nonneg : 0 ≤ {e4} := assert_22.1
  have hprev_high : {e4} < (2 : Int) ^ 64 := assert_22.2
  have hcarry_nonneg : 0 ≤ {c4} :=
    Vermilion.Bits.shr_nonneg 64 ({e4} % {M}) 51
  have hcarry_max : {c4} ≤ 8191 := by
    have hmod : {e4} % {M} = {e4} := by
      apply Int.emod_eq_of_lt hprev_nonneg
      norm_num only [Int.reducePow] at hprev_high
      exact hprev_high
    rw [hmod, Vermilion.Bits.shr_eq_div 64 {e4} 51 hprev_nonneg hprev_high]
    have hdenom : (2 : Int) ^ (51 : Int).toNat = 2251799813685248 := by decide
    rw [hdenom]
    norm_num only [Int.reducePow] at hprev_high
    omega
  unfold Vermilion.inUnsignedRange
  norm_num only [Int.reducePow]
  constructor <;> omega
"""
    header = original.split("namespace " + TARGET, 1)[0]
    if not header.startswith("import Vermilion.Obligations\nimport generated.field_u64.Specs\n"):
        raise ValueError("unexpected Lean import header")
    lean = (header + "namespace " + TARGET + "\n\n"
            + f'-- vrml:begin {NAME} {match["hash"]}\n'
            + decl + " := by\n" + proof
            + f"-- vrml:end {NAME}\n\nend {TARGET}\n")
    if lean.count("@[vrml_obligation] theorem ") != 1 or re.search(
        r"\b(sorry|admit|sorryAx)\b", lean
    ):
        raise ValueError("candidate contains admission or extra theorem")
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(lean)
    report.write_text(json.dumps({
        "name": NAME, "statement_hash": match["hash"],
        "source_module_sha256": digest, "theorem_count": 1,
        "requires_lean_kernel_check": True, "whole_case_study_verified": False,
    }, sort_keys=True, indent=2) + "\n")
    print("SSA_CARRY_TIMES19_PROOF_CANDIDATE", NAME)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("index", "modules", "output", "report"):
        parser.add_argument("--" + flag, type=Path, required=True)
    args = parser.parse_args()
    generate(args.index, args.modules, args.output, args.report)
