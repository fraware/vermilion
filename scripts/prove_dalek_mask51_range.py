#!/usr/bin/env python3
"""Exact source-keyed Lean proof candidate for as_bytes.assert_28.

Preserves the generated declaration and hypothesis telescope verbatim. This
candidate must pass the pinned Lean kernel compilation gate to count as proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

TARGET = "layer_a.backend.serial.u64.field.impl__16.as_bytes"
NAME = TARGET + ".assert_28"
MASK_DEF = "layer_a.specs.field_specs_u64.mask51"
EQ_HYP = "call_lemma_as_bytes_boundaries2_ensures_0"
GOAL = "Vermilion.inUnsignedRange 64 (Vermilion.Bits.shl 64 1 51 - 1)"
BLOCK = re.compile(
    r"(?ms)^-- vrml:begin (?P<name>[^\n ]+) (?P<hash>[0-9a-f]{16})\n"
    r"(?P<body>.*?)^-- vrml:end (?P=name)$"
)


def prepare(index_path: Path, root: Path, output: Path, report: Path) -> dict:
    index = json.loads(index_path.read_text())
    assert index["target_function"] == TARGET
    assert index["obligation_count"] == len(index["obligations"]) == 156
    indexed = {entry["name"]: entry["statement_hash"] for entry in index["obligations"]}
    modules = {entry["module"] for entry in index["obligations"]}
    assert len(modules) == 1
    source = (root / next(iter(modules))).resolve()
    assert source.is_relative_to(root.resolve())
    data = source.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    assert all(entry["module_sha256"] == digest for entry in index["obligations"])
    original = data.decode("utf-8")
    blocks = list(BLOCK.finditer(original))
    assert len(blocks) == 156
    assert {m.group("name") for m in blocks} == set(indexed)
    selected = [m for m in blocks if m.group("name") == NAME]
    assert len(selected) == 1
    m = selected[0]
    assert m.group("hash") == indexed[NAME]
    body = m.group("body")
    assert body.count(" := by\n") == 1
    theorem, _old_proof = body.split(" := by\n", 1)
    assert "@[vrml_obligation] theorem assert_28" in theorem
    assert theorem.rsplit(" :\n", 1)[1].strip() == GOAL
    assert (
        f"({EQ_HYP} : {MASK_DEF} = "
        "(Vermilion.Bits.shl 64 1 51 - 1))"
    ) in theorem

    proof = (
        f"  rw [← {EQ_HYP}]\n"
        f"  norm_num [Vermilion.inUnsignedRange, {MASK_DEF}]\n"
    )
    header = original.split("namespace " + TARGET, 1)[0]
    assert header.startswith(
        "import Vermilion.Obligations\nimport generated.field_u64.Specs\n"
    )
    result = (
        header + "namespace " + TARGET + "\n\n"
        + f'-- vrml:begin {NAME} {m.group("hash")}\n'
        + theorem + " := by\n" + proof
        + f"-- vrml:end {NAME}\n\n"
        + "end " + TARGET + "\n"
    )
    assert result.count("@[vrml_obligation] theorem ") == 1
    assert not re.search(r"\b(sorry|admit)\b", result)
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(result)
    record = {
        "target_function": TARGET,
        "name": NAME,
        "statement_hash": indexed[NAME],
        "source_module_sha256": digest,
        "theorem_count": 1,
        "requires_lean_kernel_check": True,
        "whole_case_study_verified": False,
    }
    report.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print("SSA_MASK51_RANGE_PROOF_CANDIDATES", record["theorem_count"])
    return record


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for k in ("index", "modules", "output", "report"):
        p.add_argument("--" + k, type=Path, required=True)
    args = p.parse_args()
    prepare(args.index, args.modules, args.output, args.report)
