#!/usr/bin/env python3
"""Exact source-keyed as_bytes.assert_16 candidate; acceptance requires pinned Lean."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

TARGET = "layer_a.backend.serial.u64.field.impl__16.as_bytes"
NAME = TARGET + ".assert_16"
PINNED_SOURCE_SHA256 = "722ade88657f727b1e01ff1980cb95037cd8ca15c9134b757f56cd5e6b5b641c"
M = "18446744073709551616"
L = "Vermilion.Seq.index (layer_a.backend.serial.u64.field.FieldElement51.get_FieldElement51_limbs tmp_)"
x0, x1, x2 = (f"{L} {i}" for i in range(3))
e0 = f"({x0} + 19)"
c0 = f"Vermilion.Bits.shr 64 ({e0} % {M}) 51"
e1 = f"({x1} + {c0})"
c1 = f"Vermilion.Bits.shr 64 ({e1} % {M}) 51"
e2 = f"({x2} + {c1})"
GOAL = "Vermilion.inUnsignedRange 64 " + e2
BLOCK = re.compile(
    r"(?ms)^-- vrml:begin (?P<name>[^\n ]+) (?P<hash>[0-9a-f]{16})\n"
    r"(?P<body>.*?)^-- vrml:end (?P=name)$"
)


def generate(indexpath: Path, modules: Path, dest: Path, report: Path) -> None:
    idx = json.loads(indexpath.read_text())
    assert idx["target_function"] == TARGET
    assert idx["obligation_count"] == len(idx["obligations"]) == 156
    sha_by_name = {r["name"]: r["statement_hash"] for r in idx["obligations"]}
    paths = {r["module"] for r in idx["obligations"]}
    assert len(paths) == 1
    source = (modules / next(iter(paths))).resolve()
    assert source.is_relative_to(modules.resolve())
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == PINNED_SOURCE_SHA256, "Pinned Lean module changed"
    assert all(r["module_sha256"] == digest for r in idx["obligations"])
    original = raw.decode("utf-8")
    blocks = list(BLOCK.finditer(original))
    assert len(blocks) == 156
    assert set(sha_by_name) == {m["name"] for m in blocks}
    assert all(m["hash"] == sha_by_name[m["name"]] for m in blocks)
    selected = [m for m in blocks if m["name"] == NAME]
    assert len(selected) == 1
    match = selected[0]
    assert match["body"].count(" := by\n") == 1
    decl, _old_proof = match["body"].split(" := by\n", 1)
    assert "@[vrml_obligation] theorem assert_16" in decl
    assert decl.rsplit(" :\n", 1)[-1].strip() == GOAL
    assert f"(assert_10 : Vermilion.inUnsignedRange 64 {e0})" in decl
    assert f"(assert_13 : Vermilion.inUnsignedRange 64 {e1})" in decl
    for name in (
        "assert_12", "assert_15", "call_reduce_ensures_1",
        "call_reduce_ensures_2", "call_reduce_ensures_3",
        "call_lemma_as_bytes_boundaries1_ensures_2",
    ):
        assert "(" + name + " :" in decl
    bound = (
        "(call_lemma_as_bytes_boundaries1_ensures_2 : "
        "(Vermilion.Seq.index (layer_a.specs.field_specs_u64.spec_reduce "
        "(layer_a.backend.serial.u64.field.FieldElement51.get_FieldElement51_limbs self)) "
        "2 + 2) < 18446744073709551615)"
    )
    assert bound in decl

    proof = f"""  have h0_nonneg : 0 ≤ {e0} := assert_10.1
  have h0_high : {e0} < (2 : Int) ^ 64 := assert_10.2
  have hlimb0 : {x0} < 4503599627370496 := by
    have h := call_reduce_ensures_3
    unfold layer_a.specs.field_specs.fe51_limbs_bounded
      layer_a.specs.field_specs.u64_5_bounded at h
    have h52 := h 0 (by omega)
    have hconst : Vermilion.Bits.shl 64 1 52 = 4503599627370496 := by decide
    simpa only [hconst] using h52
  have hcarry0 : {c0} ≤ 2 := by
    have hmod : {e0} % {M} = {e0} := by
      apply Int.emod_eq_of_lt h0_nonneg
      norm_num at h0_high ⊢
      omega
    rw [hmod, Vermilion.Bits.shr_eq_div 64 {e0} 51 h0_nonneg h0_high]
    norm_num only [Int.reducePow]
    omega
  have h1_nonneg : 0 ≤ {e1} := assert_13.1
  have h1_high : {e1} < (2 : Int) ^ 64 := assert_13.2
  have hlimb1 : {x1} < 4503599627370496 := by
    have h := call_reduce_ensures_3
    unfold layer_a.specs.field_specs.fe51_limbs_bounded
      layer_a.specs.field_specs.u64_5_bounded at h
    have h52 := h 1 (by omega)
    have hconst : Vermilion.Bits.shl 64 1 52 = 4503599627370496 := by decide
    simpa only [hconst] using h52
  have hcarry1 : {c1} ≤ 2 := by
    have hmod : {e1} % {M} = {e1} := by
      apply Int.emod_eq_of_lt h1_nonneg
      norm_num at h1_high ⊢
      omega
    rw [hmod, Vermilion.Bits.shr_eq_div 64 {e1} 51 h1_nonneg h1_high]
    norm_num only [Int.reducePow]
    omega
  have hlimb2_nonneg : 0 ≤ {x2} :=
    (call_reduce_ensures_1 2 ⟨by omega, assert_15.2⟩).1
  have hlimb2_max : {x2} + 2 < 18446744073709551615 := by
    rw [call_reduce_ensures_2]
    exact call_lemma_as_bytes_boundaries1_ensures_2
  unfold Vermilion.inUnsignedRange
  norm_num only [Int.reducePow]
  constructor
  · have h := Vermilion.Bits.shr_nonneg 64 ({e1} % {M}) 51
    omega
  · omega
"""
    header = original.split("namespace " + TARGET, 1)[0]
    assert header.startswith("import Vermilion.Obligations\nimport generated.field_u64.Specs\n")
    lean = (
        header + "namespace " + TARGET + "\n\n"
        + f'-- vrml:begin {NAME} {match["hash"]}\n'
        + decl + " := by\n" + proof
        + f"-- vrml:end {NAME}\n\nend {TARGET}\n"
    )
    assert lean.count("@[vrml_obligation] theorem ") == 1
    assert not re.search(r"\b(sorry|admit)\b", lean)
    dest.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(lean)
    rec = {
        "name": NAME,
        "statement_hash": match["hash"],
        "source_module_sha256": digest,
        "theorem_count": 1,
        "requires_lean_kernel_check": True,
        "whole_case_study_verified": False,
    }
    report.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n")
    print("SSA_THIRD_CARRY_RANGE_CANDIDATE", rec["theorem_count"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for field in ("index", "modules", "output", "report"):
        parser.add_argument("--" + field, type=Path, required=True)
    args = parser.parse_args()
    generate(args.index, args.modules, args.output, args.report)
