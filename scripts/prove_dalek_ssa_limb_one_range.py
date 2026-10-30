#!/usr/bin/env python3
"""First indexed-SSA limb one range candidate; native Lean CI alone accepts proofs."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

TARGET = "layer_a.backend.serial.u64.field.impl__16.as_bytes"
NAME = TARGET + ".assert_32"
PIN = "722ade88657f727b1e01ff1980cb95037cd8ca15c9134b757f56cd5e6b5b641c"
M = "18446744073709551616"
ORIG = "layer_a.backend.serial.u64.field.FieldElement51.get_FieldElement51_limbs tmp_"
L0 = "Vermilion.Seq.index limbs_ssa 0"
L1 = "Vermilion.Seq.index limbs_ssa 1"
X1 = f"Vermilion.Seq.index ({ORIG}) 1"
GOAL = f"Vermilion.inUnsignedRange 64 ({L1} + Vermilion.Bits.shr 64 ({L0}) 51)"
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
    if ("@[vrml_obligation] theorem assert_32" not in decl
        or decl.rsplit(" :\n", 1)[-1].strip() != GOAL):
        raise ValueError("original theorem statement or name changed")
    for required in (
        "(assert_26 : Vermilion.inUnsignedRange 64 ",
        "(assume_52 : limbs_ssa = Vermilion.Seq.update ",
        "(assert_31 : (0 ≤ 1) ∧ (1 < Vermilion.Seq.len limbs_ssa))",
        "(call_reduce_ensures_0 : Vermilion.Seq.len ",
        "(call_reduce_ensures_1 : (∀ (vrml_i0 : Int)",
        "(call_reduce_ensures_3 : layer_a.specs.field_specs.fe51_limbs_bounded tmp_ 52)",
    ):
        if required not in decl:
            raise ValueError("required original hypothesis missing: " + required)
    prior = [b for b in blocks if b["name"] == TARGET + ".assert_26"]
    if len(prior) != 1 or prior[0]["body"].count(" := by\n") != 1:
        raise ValueError("source-keyed predecessor missing or malformed")
    predecessor_decl = prior[0]["body"].split(" := by\n", 1)[0]
    predecessor_goal = predecessor_decl.rsplit(" :\n", 1)[-1].strip()
    prefix = "Vermilion.inUnsignedRange 64 "
    if not predecessor_goal.startswith(prefix):
        raise ValueError("source predecessor goal changed")
    newval = predecessor_goal[len(prefix):]
    update_binding = decl[decl.index("(assume_52 :"):decl.index("\n    (assert_27 :")]
    expected_update = f" 0 ({newval} % {M})"
    if expected_update not in update_binding:
        raise ValueError("updated limb differs from source-keyed assert_26 value")
    proof = f"""  have hlen : Vermilion.Seq.len ({ORIG}) = 5 := call_reduce_ensures_0
  have h26hi : {newval} < {M} := by
    have h := assert_26.2
    norm_num only [Int.reducePow] at h
    exact h
  have hlimb0 : {L0} = {newval} := by
    rw [assume_52]
    rw [Vermilion.Seq.index_update_same ({ORIG}) 0 _ (by omega) (by rw [hlen]; omega)]
    exact Int.emod_eq_of_lt assert_26.1 h26hi
  have h0lo : 0 ≤ {L0} := by
    rw [hlimb0]
    exact assert_26.1
  have h0hi : {L0} < (2 : Int) ^ 64 := by
    rw [hlimb0]
    exact assert_26.2
  have h1eq : {L1} = {X1} := by
    rw [assume_52]
    exact Vermilion.Seq.index_update_other ({ORIG}) 1 _ 0 (by omega)
  have h1lo : 0 ≤ {L1} := by
    rw [h1eq]
    exact (call_reduce_ensures_1 1 ⟨by omega, by rw [hlen]; omega⟩).1
  have h1hi : {L1} < 4503599627370496 := by
    rw [h1eq]
    have h := call_reduce_ensures_3
    unfold layer_a.specs.field_specs.fe51_limbs_bounded
      layer_a.specs.field_specs.u64_5_bounded at h
    have hh := h 1 (by omega)
    have hconst : Vermilion.Bits.shl 64 1 52 = 4503599627370496 := by decide
    simpa only [hconst] using hh
  have hcarrylo : 0 ≤ Vermilion.Bits.shr 64 ({L0}) 51 :=
    Vermilion.Bits.shr_nonneg 64 ({L0}) 51
  have hcarryhi : Vermilion.Bits.shr 64 ({L0}) 51 ≤ 8191 := by
    rw [Vermilion.Bits.shr_eq_div 64 ({L0}) 51 h0lo h0hi]
    have hdenom : (2 : Int) ^ (51 : Int).toNat = 2251799813685248 := by decide
    rw [hdenom]
    norm_num only [Int.reducePow] at h0hi
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
    print("SSA_LIMB_ONE_PROOF_CANDIDATE", NAME)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("index", "modules", "output", "report"):
        parser.add_argument("--" + flag, type=Path, required=True)
    args = parser.parse_args()
    generate(args.index, args.modules, args.output, args.report)
