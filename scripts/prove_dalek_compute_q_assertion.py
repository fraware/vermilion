#!/usr/bin/env python3
"""Exact source-keyed proof candidate for dalek-lite as_bytes.assert_5.

Retains the full generated declaration and hypothesis telescope. The goal is
the conjunction of three existing compute_q lemma postconditions. This tool
does not certify a proof; pinned Lean compilation is the acceptance gate.
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


def prepare(index_path: Path, root: Path, output: Path, report: Path) -> dict:
    index = json.loads(index_path.read_text())
    assert index["target_function"] == TARGET
    assert index["obligation_count"] == len(index["obligations"]) == 156
    expected = {item["name"]: item["statement_hash"] for item in index["obligations"]}
    modules = {item["module"] for item in index["obligations"]}
    assert len(modules) == 1
    source = (root / next(iter(modules))).resolve()
    assert source.is_relative_to(root.resolve()), "Generated module escapes root"
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    assert all(item["module_sha256"] == digest for item in index["obligations"])
    text = raw.decode("utf-8")
    blocks = list(BLOCK.finditer(text))
    assert len(blocks) == 156
    assert {block.group("name") for block in blocks} == set(expected)

    full_name = TARGET + ".assert_5"
    matches = [block for block in blocks if block.group("name") == full_name]
    assert len(matches) == 1
    block = matches[0]
    statement_hash = block.group("hash")
    assert expected[full_name] == statement_hash
    body = block.group("body")
    assert body.count(" := by\n") == 1
    declaration, _ = body.split(" := by\n", 1)
    assert "@[vrml_obligation] theorem assert_5" in declaration
    goal = declaration.rsplit(" :\n", 1)[-1].strip()
    facts = [f"call_lemma_compute_q_ensures_{i}" for i in range(3)]
    for fact in facts:
        assert f"({fact} :" in declaration
    assert " ∨ " in goal and " ↔ " in goal and " ∧ " in goal

    tactic = (
        "  exact ⟨⟨call_lemma_compute_q_ensures_0, "
        "call_lemma_compute_q_ensures_1⟩, "
        "call_lemma_compute_q_ensures_2⟩"
    )
    header = text.split("namespace " + TARGET, 1)[0]
    assert header.startswith(
        "import Vermilion.Obligations\nimport generated.field_u64.Specs\n"
    )
    candidate = (
        header
        + "namespace " + TARGET + "\n\n"
        + f"-- vrml:begin {full_name} {statement_hash}\n"
        + declaration + " := by\n" + tactic + "\n"
        + f"-- vrml:end {full_name}\n\n"
        + "end " + TARGET + "\n"
    )
    assert candidate.count("@[vrml_obligation] theorem ") == 1
    assert not re.search(r"\b(sorry|admit)\b", candidate)
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(candidate)
    record = {
        "name": full_name,
        "statement_hash": statement_hash,
        "source_module_sha256": digest,
        "precondition_facts": facts,
        "theorem_count": 1,
        "requires_lean_kernel_check": True,
        "whole_case_study_verified": False,
    }
    report.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print("SSA_COMPUTE_Q_ASSERTION_CANDIDATES", record["theorem_count"])
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for argument in ("index", "modules", "output", "report"):
        parser.add_argument("--" + argument, type=Path, required=True)
    args = parser.parse_args()
    prepare(args.index, args.modules, args.output, args.report)
