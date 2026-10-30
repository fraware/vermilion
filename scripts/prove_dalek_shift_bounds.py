#!/usr/bin/env python3
"""Build exact source-keyed Lean proof candidates for concrete 64-bit shift VCs.

Reads the pinned generated as_bytes obligation module and its source-keyed
manifest, retains the original theorem declarations and hypotheses verbatim,
and substitutes a direct arithmetic tactic ONLY when the complete goal is
the closed proposition (0 ≤ k) ∧ (k < 64). The output is not considered
verified until the pinned Lean compiler accepts it without sorry/admit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

BLOCK = re.compile(
    r"(?ms)^-- vrml:begin (?P<name>[^\n ]+) (?P<hash>[0-9a-f]{16})\n"
    r"(?P<body>.*?)^-- vrml:end (?P=name)$"
)
GOAL = re.compile(r"(?m)^    \(0 ≤ (?P<width>[0-9]+)\) ∧ \((?P=width) < 64\) := by$")
EXPECTED_TARGET = "layer_a.backend.serial.u64.field.impl__16.as_bytes"


def prepare(index_path: Path, source_root: Path, dest: Path, report: Path) -> dict:
    index = json.loads(index_path.read_text())
    assert index["target_function"] == EXPECTED_TARGET
    assert index["obligation_count"] == len(index["obligations"]) == 156
    modules = {row["module"] for row in index["obligations"]}
    assert len(modules) == 1
    relative = next(iter(modules))
    source = (source_root / relative).resolve()
    assert source.is_relative_to(source_root.resolve())
    source_bytes = source.read_bytes()
    digest = hashlib.sha256(source_bytes).hexdigest()
    assert all(row["module_sha256"] == digest for row in index["obligations"])
    original = source_bytes.decode("utf-8")
    indexed = {row["name"]: row["statement_hash"] for row in index["obligations"]}
    all_blocks = list(BLOCK.finditer(original))
    assert len(all_blocks) == 156, ("Unexpected original theorem count", len(all_blocks))
    assert {m.group("name") for m in all_blocks} == set(indexed)

    proofs = []
    details = []
    for match in all_blocks:
        name, statement_hash = match.group("name"), match.group("hash")
        assert indexed[name] == statement_hash
        content = match.group("body")
        goal = GOAL.findall(content)
        if not goal:
            continue
        assert len(goal) == 1 and content.count(" := by\n") == 1, name
        shift = int(goal[0])
        assert 0 <= shift < 64, ("Unexpected nontrivial shift goal", name, shift)
        theorem, _tactic = content.split(" := by\n", 1)
        assert f"@[vrml_obligation] theorem {name.rsplit('.',1)[-1]}" in theorem
        proofs.append(
            f'-- vrml:begin {name} {statement_hash}\n'
            + theorem + " := by\n  norm_num\n"
            + f'-- vrml:end {name}\n'
        )
        details.append({"name": name, "hash": statement_hash, "shift": shift})
    assert len(proofs) == 45, ("Expected 45 exact bit-shift VCs", len(proofs))
    header = original.split("namespace " + EXPECTED_TARGET, 1)[0]
    assert header.startswith("import Vermilion.Obligations\nimport generated.field_u64.Specs\n")
    output = (
        header + "namespace " + EXPECTED_TARGET + "\n\n"
        + "\n".join(proofs)
        + "\nend " + EXPECTED_TARGET + "\n"
    )
    assert output.count("@[vrml_obligation] theorem ") == 45
    assert not re.search(r"\b(sorry|admit)\b", output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(output)
    record = {
        "target_function": EXPECTED_TARGET,
        "source_module_sha256": digest,
        "theorem_count": len(proofs),
        "proof_tactic": "norm_num",
        "propositions": details,
        "requires_lean_kernel_check": True,
        "whole_case_study_verified": False,
    }
    report.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--modules", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.index, args.modules, args.output, args.report)
    print("SSA_CONCRETE_SHIFT_PROOF_CANDIDATES", result["theorem_count"])


if __name__ == "__main__":
    main()
