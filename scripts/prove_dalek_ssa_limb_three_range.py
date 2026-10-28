#!/usr/bin/env python3
"""Third indexed-SSA carry-range source theorem candidate; native Lean CI is the acceptance gate."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

TARGET = "layer_a.backend.serial.u64.field.impl__16.as_bytes"
NAME = TARGET + ".assert_42"
PIN = "722ade88657f727b1e01ff1980cb95037cd8ca15c9134b757f56cd5e6b5b641c"
M = "18446744073709551616"
ORIG = "layer_a.backend.serial.u64.field.FieldElement51.get_FieldElement51_limbs tmp_"
L2_4 = "Vermilion.Seq.index limbs_ssa_4 2"
L2_5 = "Vermilion.Seq.index limbs_ssa_5 2"
L3_5 = "Vermilion.Seq.index limbs_ssa_5 3"
X3 = f"Vermilion.Seq.index ({ORIG}) 3"
E2 = "Vermilion.Seq.index limbs_ssa_3 2 + Vermilion.Bits.shr 64 (Vermilion.Seq.index limbs_ssa_3 1) 51"
GOAL = f"Vermilion.inUnsignedRange 64 ({L3_5} + Vermilion.Bits.shr 64 ({L2_5}) 51)"
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
    if ("@[vrml_obligation] theorem assert_42" not in decl
        or decl.rsplit(" :\n", 1)[-1].strip() != GOAL):
        raise ValueError("original theorem statement or name changed")
    if match["hash"] != "c4a26a0cc35e67b1":
        raise ValueError("pinned assert_37 source identity changed")
    for required in (
        "(assert_37 : Vermilion.inUnsignedRange 64 ",
        "(assert_36 : (0 ≤ 2) ∧ (2 < Vermilion.Seq.len limbs_ssa_3))",
        "(assume_52 : limbs_ssa = Vermilion.Seq.update ",
        "(assume_59 : limbs_ssa_2 = Vermilion.Seq.update limbs_ssa 1 ",
        "(assume_61 : limbs_ssa_3 = Vermilion.Seq.update limbs_ssa_2 0 ",
        "(assume_66 : limbs_ssa_4 = Vermilion.Seq.update limbs_ssa_3 2 ",
        "(assume_68 : limbs_ssa_5 = Vermilion.Seq.update limbs_ssa_4 1 ",
        "(call_reduce_ensures_0 : Vermilion.Seq.len ",
        "(call_reduce_ensures_1 : (∀ (vrml_i0 : Int)",
        "(call_reduce_ensures_3 : layer_a.specs.field_specs.fe51_limbs_bounded tmp_ 52)",
    ):
        if required not in decl:
            raise ValueError("original hypothesis missing: " + required)
    update2 = decl.split("(assume_66 : ", 1)[1].split("\n    (assert_38 :", 1)[0]
    if f"limbs_ssa_4 = Vermilion.Seq.update limbs_ssa_3 2 (({E2}) % {M})" not in update2:
        raise ValueError("indexed SSA update at index 2 changed")
    update1 = decl.split("(assume_68 : ", 1)[1].split("\n    (assert_39 :", 1)[0]
    if "limbs_ssa_5 = Vermilion.Seq.update limbs_ssa_4 1 (Vermilion.Bits.band 64 " not in update1:
        raise ValueError("indexed SSA mask update at index 1 changed")
    proof = f"""  have hlen : Vermilion.Seq.len ({ORIG}) = 5 := call_reduce_ensures_0
  have h37hi : ({E2}) < {M} := by
    have h := assert_37.2
    norm_num only [Int.reducePow] at h
    exact h
  have hlimb2_4 : {L2_4} = ({E2}) := by
    rw [assume_66]
    rw [Vermilion.Seq.index_update_same limbs_ssa_3 2 _ (by omega) assert_36.2]
    exact Int.emod_eq_of_lt assert_37.1 h37hi
  have hlimb2_5 : {L2_5} = ({E2}) := by
    rw [assume_68]
    rw [Vermilion.Seq.index_update_other limbs_ssa_4 2 _ 1 (by omega)]
    exact hlimb2_4
  have h2lo : 0 ≤ {L2_5} := by
    rw [hlimb2_5]
    exact assert_37.1
  have h2hi : {L2_5} < (2 : Int) ^ 64 := by
    rw [hlimb2_5]
    exact assert_37.2
  have h3eq : {L3_5} = {X3} := by
    rw [assume_68]
    rw [Vermilion.Seq.index_update_other limbs_ssa_4 3 _ 1 (by omega)]
    rw [assume_66]
    rw [Vermilion.Seq.index_update_other limbs_ssa_3 3 _ 2 (by omega)]
    rw [assume_61]
    rw [Vermilion.Seq.index_update_other limbs_ssa_2 3 _ 0 (by omega)]
    rw [assume_59]
    rw [Vermilion.Seq.index_update_other limbs_ssa 3 _ 1 (by omega)]
    rw [assume_52]
    exact Vermilion.Seq.index_update_other ({ORIG}) 3 _ 0 (by omega)
  have h3lo : 0 ≤ {L3_5} := by
    rw [h3eq]
    exact (call_reduce_ensures_1 3 ⟨by omega, by rw [hlen]; omega⟩).1
  have h3hi : {L3_5} < 4503599627370496 := by
    rw [h3eq]
    have h := call_reduce_ensures_3
    unfold layer_a.specs.field_specs.fe51_limbs_bounded
      layer_a.specs.field_specs.u64_5_bounded at h
    have hh := h 3 (by omega)
    have hconst : Vermilion.Bits.shl 64 1 52 = 4503599627370496 := by decide
    simpa only [hconst] using hh
  have hcarrylo : 0 ≤ Vermilion.Bits.shr 64 ({L2_5}) 51 :=
    Vermilion.Bits.shr_nonneg 64 ({L2_5}) 51
  have hcarryhi : Vermilion.Bits.shr 64 ({L2_5}) 51 ≤ 8191 := by
    rw [Vermilion.Bits.shr_eq_div 64 ({L2_5}) 51 h2lo h2hi]
    have hdenom : (2 : Int) ^ (51 : Int).toNat = 2251799813685248 := by decide
    rw [hdenom]
    norm_num only [Int.reducePow] at h2hi
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
    print("SSA_ASSERT42_PROOF_CANDIDATE", NAME)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("index", "modules", "output", "report"):
        parser.add_argument("--" + flag, type=Path, required=True)
    args = parser.parse_args()
    generate(args.index, args.modules, args.output, args.report)
