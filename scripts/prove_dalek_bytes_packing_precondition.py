#!/usr/bin/env python3
"""Exact-source-keyed bytes packing precondition candidate. Native Lean CI is required."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

TARGET = "layer_a.backend.serial.u64.field.impl__16.as_bytes"
NAME = TARGET + ".call_requires_7_1"
PIN = "722ade88657f727b1e01ff1980cb95037cd8ca15c9134b757f56cd5e6b5b641c"
HASH = "fab974571da9922d"
BLOCK = re.compile(
    r"(?ms)^-- vrml:begin (?P<name>[^\n ]+) (?P<hash>[a-f0-9]{16})\n"
    r"(?P<body>.*?)^-- vrml:end (?P=name)$"
)

def generate(index: Path, modules: Path, output: Path, report: Path) -> None:
    idx = json.loads(index.read_text())
    rows = idx["obligations"]
    if idx.get("target_function") != TARGET or idx.get("obligation_count") != 156:
        raise ValueError("pinned source inventory changed")
    if len(rows) != 156 or len({r["name"] for r in rows}) != 156:
        raise ValueError("source-keyed obligations changed or duplicated")
    paths = {r["module"] for r in rows}
    if len(paths) != 1:
        raise ValueError("unexpected generated module inventory")
    root = modules.resolve()
    source = (modules / next(iter(paths))).resolve()
    if not source.is_relative_to(root):
        raise ValueError("source path traverses outside proof root")
    content = source.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if digest != PIN or any(r["module_sha256"] != PIN for r in rows):
        raise ValueError("pinned source module SHA-256 changed")
    original = content.decode("utf-8")
    indexed = {r["name"]: r["statement_hash"] for r in rows}
    blocks = list(BLOCK.finditer(original))
    if len(blocks) != 156 or {b["name"] for b in blocks} != set(indexed):
        raise ValueError("source theorem inventory changed")
    if any(b["hash"] != indexed[b["name"]] for b in blocks):
        raise ValueError("source statement hashes changed")
    targets = [b for b in blocks if b["name"] == NAME]
    if len(targets) != 1 or targets[0]["hash"] != HASH or targets[0]["body"].count(" := by\n") != 1:
        raise ValueError("exact source-keyed target theorem missing")
    match = targets[0]
    decl, _old_proof = match["body"].split(" := by\n", 1)
    goal = decl.rsplit(" :\n", 1)[-1].strip()
    if ("@[vrml_obligation] theorem call_requires_7_1" not in decl
        or not goal.startswith("layer_a.lemmas.field_lemmas.limbs_to_bytes_lemmas.bytes_match_limbs_packing ")
        or "layer_a.specs.field_specs_u64.bit_arrange" not in goal):
        raise ValueError("original packing theorem statement changed")
    proof = """  unfold layer_a.lemmas.field_lemmas.limbs_to_bytes_lemmas.bytes_match_limbs_packing
    layer_a.specs.field_specs_u64.bit_arrange
  simp [Vermilion.Seq.index_push, Vermilion.Seq.len_push, Vermilion.Seq.len_empty]
"""
    header = original.split("namespace " + TARGET, 1)[0]
    if not header.startswith("import Vermilion.Obligations\nimport generated.field_u64.Specs\n"):
        raise ValueError("unexpected source import header")
    lean = (header + "namespace " + TARGET + "\n\n"
        + f'-- vrml:begin {NAME} {match["hash"]}\n'
        + decl + " := by\n" + proof
        + f"-- vrml:end {NAME}\n\nend {TARGET}\n")
    if lean.count("@[vrml_obligation] theorem ") != 1 or re.search(r"\b(sorry|admit|sorryAx)\b", lean):
        raise ValueError("admission or extra theorem in proof")
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(lean)
    report.write_text(json.dumps({
        "name": NAME, "statement_hash": match["hash"],
        "source_module_sha256": digest, "theorem_count": 1,
        "requires_lean_kernel_check": True, "whole_case_study_verified": False
    }, sort_keys=True, indent=2) + "\n")
    print("SSA_BYTES_PACKING_CANDIDATE_NOT_KERNEL_ACCEPTED", NAME)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("index", "modules", "output", "report"):
        parser.add_argument("--" + flag, type=Path, required=True)
    args = parser.parse_args()
    generate(args.index, args.modules, args.output, args.report)
