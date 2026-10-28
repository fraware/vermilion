#!/usr/bin/env python3
"""Source-keyed candidate for as_bytes.assert_13; Lean CI certifies, not this script."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

TARGET = "layer_a.backend.serial.u64.field.impl__16.as_bytes"
PINNED_SOURCE_SHA256 = "722ade88657f727b1e01ff1980cb95037cd8ca15c9134b757f56cd5e6b5b641c"
NAME = TARGET + ".assert_13"
BLOCK = re.compile(
    r"(?ms)^-- vrml:begin (?P<name>[^\n ]+) (?P<hash>[0-9a-f]{16})\n"
    r"(?P<body>.*?)^-- vrml:end (?P=name)$"
)
L = "Vermilion.Seq.index (layer_a.backend.serial.u64.field.FieldElement51.get_FieldElement51_limbs tmp_)"
X0, X1 = f"{L} 0", f"{L} 1"
BASE = f"({X0} + 19)"
GOAL = (
    f"Vermilion.inUnsignedRange 64 ({X1} + "
    f"Vermilion.Bits.shr 64 ({BASE} % 18446744073709551616) 51)"
)


def generate(index_path: Path, modules: Path, output: Path, report: Path):
    index = json.loads(index_path.read_text())
    assert index["target_function"] == TARGET
    assert len(index["obligations"]) == index["obligation_count"] == 156
    records = {item["name"]: item["statement_hash"] for item in index["obligations"]}
    paths = {item["module"] for item in index["obligations"]}
    assert len(paths) == 1
    source = (modules / next(iter(paths))).resolve()
    assert source.is_relative_to(modules.resolve())
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == PINNED_SOURCE_SHA256, "Pinned Lean module changed"
    assert all(item["module_sha256"] == digest for item in index["obligations"])
    original = raw.decode("utf-8")
    blocks = list(BLOCK.finditer(original))
    assert len(blocks) == 156
    assert set(records) == {m["name"] for m in blocks}
    assert all(m["hash"] == records[m["name"]] for m in blocks)
    matching = [m for m in blocks if m["name"] == NAME]
    assert len(matching) == 1
    match = matching[0]
    assert match["hash"] == records[NAME]
    assert match["body"].count(" := by\n") == 1
    decl, _old = match["body"].split(" := by\n", 1)
    assert "@[vrml_obligation] theorem assert_13" in decl
    assert decl.rsplit(" :\n", 1)[-1].strip() == GOAL
    assert "(assert_10 : Vermilion.inUnsignedRange 64 (" in decl
    assert "(assert_12 : (0 ≤ 1) ∧ (1 < Vermilion.Seq.len " in decl
    assert "(call_reduce_ensures_3 : layer_a.specs.field_specs.fe51_limbs_bounded tmp_ 52)" in decl
    assert "(call_reduce_ensures_1 : (∀ (vrml_i0 : Int)" in decl
    assert "(call_reduce_ensures_2 : layer_a.backend.serial.u64.field.FieldElement51.get_FieldElement51_limbs tmp_" in decl
    assert (
        "(call_lemma_as_bytes_boundaries1_ensures_1 : "
        "(Vermilion.Seq.index (layer_a.specs.field_specs_u64.spec_reduce "
        "(layer_a.backend.serial.u64.field.FieldElement51.get_FieldElement51_limbs self)) "
        "1 + 2) < 18446744073709551615)"
    ) in decl

    proof = f"""  have hbase : 0 ≤ {BASE} := assert_10.1
  have hbase_high : {BASE} < (2 : Int) ^ 64 := assert_10.2
  have hlimb0 : {X0} < 4503599627370496 := by
    have h := call_reduce_ensures_3
    unfold layer_a.specs.field_specs.fe51_limbs_bounded
      layer_a.specs.field_specs.u64_5_bounded at h
    have h52 := h 0 (by omega)
    have hconst : Vermilion.Bits.shl 64 1 52 = 4503599627370496 := by decide
    simpa only [hconst] using h52
  have hshift : Vermilion.Bits.shr 64 ({BASE} % 18446744073709551616) 51 ≤ 2 := by
    have hmod : {BASE} % 18446744073709551616 = {BASE} := by
      apply Int.emod_eq_of_lt hbase
      norm_num only [Int.reducePow] at hbase_high
      exact hbase_high
    rw [hmod, Vermilion.Bits.shr_eq_div 64 {BASE} 51 hbase hbase_high]
    have hdenom : (2 : Int) ^ (51 : Int).toNat = 2251799813685248 := by decide
    rw [hdenom]
    omega
  have hlimb1_nonneg : 0 ≤ {X1} :=
    (call_reduce_ensures_1 1 ⟨by omega, assert_12.2⟩).1
  have hlimb1_max : {X1} + 2 < 18446744073709551615 := by
    rw [call_reduce_ensures_2]
    exact call_lemma_as_bytes_boundaries1_ensures_1
  unfold Vermilion.inUnsignedRange
  norm_num only [Int.reducePow]
  constructor
  · have h := Vermilion.Bits.shr_nonneg 64 ({BASE} % 18446744073709551616) 51
    omega
  · omega
"""
    header = original.split("namespace " + TARGET, 1)[0]
    assert header.startswith("import Vermilion.Obligations\nimport generated.field_u64.Specs\n")
    lean = (
        header + "namespace " + TARGET + "\n\n"
        + f'-- vrml:begin {NAME} {match["hash"]}\n'
        + decl + " := by\n" + proof
        + f"-- vrml:end {NAME}\n\n"
        + "end " + TARGET + "\n"
    )
    assert lean.count("@[vrml_obligation] theorem ") == 1
    assert not re.search(r"\b(sorry|admit)\b", lean)
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(lean)
    result = {
        "name": NAME, "statement_hash": match["hash"], "source_module_sha256": digest,
        "theorem_count": 1, "requires_lean_kernel_check": True,
        "whole_case_study_verified": False,
    }
    report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("SSA_SECOND_CARRY_RANGE_PROOF_CANDIDATE", result["theorem_count"])


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for arg in ("index", "modules", "output", "report"):
        p.add_argument("--" + arg, type=Path, required=True)
    args = p.parse_args()
    generate(args.index, args.modules, args.output, args.report)
