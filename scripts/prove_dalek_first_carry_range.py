#!/usr/bin/env python3
"""Build the exact source-keyed Lean proof candidate for as_bytes.assert_10.

The first carry addition has an upper bound from the original
lemma_as_bytes_boundaries1 postcondition and a lower bound from the
original reduce's 64-bit range contract. Retain the generated theorem
declaration verbatim; only a successful pinned Lean kernel check certifies
this candidate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

TARGET = "layer_a.backend.serial.u64.field.impl__16.as_bytes"
FULL_NAME = TARGET + ".assert_10"
BLOCK = re.compile(
    r"(?ms)^-- vrml:begin (?P<name>[^\n ]+) (?P<hash>[0-9a-f]{16})\n"
    r"(?P<body>.*?)^-- vrml:end (?P=name)$"
)
LIMBS = (
    "layer_a.backend.serial.u64.field.FieldElement51."
    "get_FieldElement51_limbs tmp_"
)
GOAL = (
    "Vermilion.inUnsignedRange 64 "
    "(Vermilion.Seq.index (" + LIMBS + ") 0 + 19)"
)


def prepare(index_file: Path, modules_root: Path, dest: Path, report_file: Path) -> dict:
    index = json.loads(index_file.read_text())
    assert index["target_function"] == TARGET
    assert index["obligation_count"] == len(index["obligations"]) == 156
    indexed = {item["name"]: item["statement_hash"] for item in index["obligations"]}
    modules = {item["module"] for item in index["obligations"]}
    assert len(modules) == 1
    source = (modules_root / next(iter(modules))).resolve()
    assert source.is_relative_to(modules_root.resolve())
    source_bytes = source.read_bytes()
    digest = hashlib.sha256(source_bytes).hexdigest()
    assert all(item["module_sha256"] == digest for item in index["obligations"])
    original = source_bytes.decode("utf-8")
    blocks = list(BLOCK.finditer(original))
    assert len(blocks) == 156
    assert {m.group("name") for m in blocks} == set(indexed)
    selected = [m for m in blocks if m.group("name") == FULL_NAME]
    assert len(selected) == 1
    block = selected[0]
    assert block.group("hash") == indexed[FULL_NAME]
    content = block.group("body")
    assert content.count(" := by\n") == 1
    decl, _prior = content.split(" := by\n", 1)
    assert "@[vrml_obligation] theorem assert_10" in decl
    assert decl.rsplit(" :\n", 1)[-1].strip() == GOAL
    # Each fact below must occur in the original theorem telescope.
    assert "(call_reduce_ensures_2 : " in decl
    assert "(call_reduce_ensures_1 : " in decl
    assert "(assert_9 : (0 ≤ 0) ∧ (0 < " in decl
    assert (
        "(call_lemma_as_bytes_boundaries1_ensures_0 : "
        "(Vermilion.Seq.index (layer_a.specs.field_specs_u64.spec_reduce "
    ) in decl
    assert "(call_lemma_as_bytes_boundaries1_ensures_0 :" in decl
    assert ") 0 + 19) < 18446744073709551615)" in decl

    proof = (
        "  have h_low : 0 ≤ Vermilion.Seq.index (" + LIMBS + ") 0 := by\n"
        "    exact (call_reduce_ensures_1 0 ⟨by omega, assert_9.2⟩).1\n"
        "  have h_high : Vermilion.Seq.index (" + LIMBS + ") 0 + 19"
        " < 18446744073709551615 := by\n"
        "    rw [call_reduce_ensures_2]\n"
        "    exact call_lemma_as_bytes_boundaries1_ensures_0\n"
        "  unfold Vermilion.inUnsignedRange\n"
        "  norm_num only [Int.reducePow]\n"
        "  constructor <;> omega\n"
    )
    header = original.split("namespace " + TARGET, 1)[0]
    assert header.startswith(
        "import Vermilion.Obligations\nimport generated.field_u64.Specs\n"
    )
    output_text = (
        header + "namespace " + TARGET + "\n\n"
        + f'-- vrml:begin {FULL_NAME} {block.group("hash")}\n'
        + decl + " := by\n" + proof
        + f"-- vrml:end {FULL_NAME}\n\n"
        + "end " + TARGET + "\n"
    )
    assert output_text.count("@[vrml_obligation] theorem ") == 1
    assert not re.search(r"\b(sorry|admit)\b", output_text)
    dest.parent.mkdir(parents=True, exist_ok=True)
    report_file.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(output_text)
    report = {
        "target_function": TARGET,
        "name": FULL_NAME,
        "statement_hash": indexed[FULL_NAME],
        "source_module_sha256": digest,
        "theorem_count": 1,
        "requires_lean_kernel_check": True,
        "whole_case_study_verified": False,
    }
    report_file.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("SSA_FIRST_CARRY_RANGE_PROOF_CANDIDATE", report["theorem_count"])
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for arg in ("index", "modules", "output", "report"):
        parser.add_argument("--" + arg, type=Path, required=True)
    args = parser.parse_args()
    prepare(args.index, args.modules, args.output, args.report)
