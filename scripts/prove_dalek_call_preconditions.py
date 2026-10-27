#!/usr/bin/env python3
"""Nine exact source-keyed call-precondition proof candidates for dalek-lite.

Preserves complete generated theorem declarations and hypothesis telescopes.
The candidates are accepted only after pinned Lean compilation without
admissions; this generator alone establishes no proof-discharge result.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

TARGET = "layer_a.backend.serial.u64.field.impl__16.as_bytes"
BLOCK = re.compile(
    r"(?ms)^-- vrml:begin (?P<name>[^\n ]+) (?P<hash>[0-9a-f]{16})\n"
    r"(?P<body>.*?)^-- vrml:end (?P=name)$"
)
TACTICS = {
    "call_requires_4_0": "exact call_proof_reduce_ensures_0",
    "call_requires_4_1": "exact call_lemma_reduce_bound_2p_ensures_0",
    "call_requires_4_2": "rfl",
    "call_requires_6_0": "exact call_proof_reduce_ensures_0",
    "call_requires_6_1": "exact (assume_22 trivial).1.1",
    "call_requires_6_2": "exact (assume_22 trivial).1.2",
    "call_requires_6_3": "exact call_lemma_reduce_bound_2p_ensures_0",
    "call_requires_6_4": "rfl",
    "call_requires_7_0": "exact call_lemma_to_bytes_reduction_ensures_0",
}

def generate(index_path: Path, root: Path, dest: Path, report: Path) -> dict:
    index = json.loads(index_path.read_text())
    assert index["target_function"] == TARGET
    assert index["obligation_count"] == len(index["obligations"]) == 156
    modules = {r["module"] for r in index["obligations"]}
    assert len(modules) == 1
    source = (root / next(iter(modules))).resolve()
    assert source.is_relative_to(root.resolve()), "Module escapes generated root"
    data = source.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    assert all(r["module_sha256"] == digest for r in index["obligations"])
    named = {r["name"]: r["statement_hash"] for r in index["obligations"]}
    text = data.decode("utf-8")
    blocks = list(BLOCK.finditer(text))
    assert len(blocks) == 156
    assert {m.group("name") for m in blocks} == set(named)

    proofs = []
    selected = []
    for match in blocks:
        name = match.group("name")
        suffix = name.rsplit(".", 1)[-1]
        if suffix not in TACTICS:
            continue
        assert named[name] == match.group("hash")
        body = match.group("body")
        assert body.count(" := by\n") == 1, name
        declaration, _prior_tactic = body.split(" := by\n")
        assert f"@[vrml_obligation] theorem {suffix}" in declaration
        goal = declaration.rsplit(" :\n", 1)[1].strip()
        tactic = TACTICS[suffix]
        if tactic == "rfl":
            assert " = " in goal, suffix
            left, right = goal.split(" = ", 1)
            assert left == right, suffix
        elif tactic.startswith("exact call_"):
            witness = tactic.removeprefix("exact ")
            assert f"({witness} : {goal})" in declaration, suffix
        else:
            assert suffix in {"call_requires_6_1", "call_requires_6_2"}
            assert "(assume_22 : True → " in declaration
        proofs.append(
            f'-- vrml:begin {name} {match.group("hash")}\n'
            + declaration + " := by\n  " + tactic + "\n"
            + f"-- vrml:end {name}\n"
        )
        selected.append({"name": name, "hash": match.group("hash"),
                         "tactic": tactic})
    assert len(proofs) == len(selected) == len(TACTICS) == 9
    header = text.split("namespace " + TARGET, 1)[0]
    assert header.startswith(
        "import Vermilion.Obligations\nimport generated.field_u64.Specs\n")
    output = (header + "namespace " + TARGET + "\n\n"
              + "\n".join(proofs) + "\nend " + TARGET + "\n")
    assert output.count("@[vrml_obligation] theorem ") == 9
    assert not re.search(r"\b(sorry|admit)\b", output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(output)
    result = {
        "target_function": TARGET,
        "source_module_sha256": digest,
        "theorem_count": 9,
        "theorems": selected,
        "requires_lean_kernel_check": True,
        "whole_case_study_verified": False,
    }
    report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--modules", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    result = generate(args.index, args.modules, args.output, args.report)
    print("SSA_9_PRECONDITION_PROOF_CANDIDATES", result["theorem_count"])
