#!/usr/bin/env python3
"""Audit transitive axioms in pinned, source-keyed dalek-lite Lean proofs.

Prepare appends Lean's native #print axioms commands to freshly generated
proof modules without changing declarations. Verify rejects missing reports,
duplicate proof IDs, and dependencies outside Lean's three standard axioms.
This audit supplements, and does not replace, native Lean compilation.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

TARGET = "layer_a.backend.serial.u64.field.impl__16.as_bytes"
APPROVED = frozenset({"propext", "Classical.choice", "Quot.sound"})
STAGES = {
    "ssa-shift-bounds": (45, "ssa-shift-proofs.stdout"),
    "ssa-sequence-bounds": (87, "ssa-sequence-proofs.stdout"),
    "ssa-call-preconditions": (9, "ssa-preconditions.stdout"),
    "ssa-compute-q-assertion": (1, "ssa-compute-q-assertion.stdout"),
    "ssa-mask51-range": (1, "ssa-mask51-range.stdout"),
    "ssa-first-carry-range": (1, "ssa-first-carry-range.stdout"),
    "ssa-second-carry-range": (1, "ssa-second-carry-range.stdout"),
    "ssa-third-carry-range": (1, "ssa-third-carry-range.stdout"),
    "ssa-fourth-carry-range": (1, "ssa-fourth-carry-range.stdout"),
}
BLOCK = re.compile(
    r"(?ms)^-- vrml:begin (?P<name>[A-Za-z0-9_.]+) (?P<hash>[0-9a-f]{16})\n"
    r"(?P<body>.*?)^-- vrml:end (?P=name)$"
)
AXIOM_REPORT = re.compile(
    r"'(?P<name>[A-Za-z0-9_.]+)' "
    r"(?:(?:depends on axioms: \[(?P<axioms>[^\]]*)\])|"
    r"(?P<none>does not depend on any axioms))"
)


def inventory(index_path: Path) -> dict[str, str]:
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if index.get("target_function") != TARGET or index.get("obligation_count") != 156:
        raise ValueError("unexpected pinned target or VC count")
    rows = index.get("obligations")
    if not isinstance(rows, list) or len(rows) != 156:
        raise ValueError("malformed pinned VC inventory")
    result = {}
    for row in rows:
        name, statement_hash = row["name"], row["statement_hash"]
        if not name.startswith(TARGET + ".") or name in result:
            raise ValueError(f"duplicate or out-of-scope obligation: {name}")
        if not re.fullmatch(r"[a-f0-9]{16}", statement_hash):
            raise ValueError(f"invalid source statement hash: {name}")
        result[name] = statement_hash
    return result


def prepare(index: Path, source: Path, manifest: Path) -> None:
    expected = inventory(index)
    if source.stem not in STAGES:
        raise ValueError(f"unexpected proof module: {source.name}")
    original = source.read_text(encoding="utf-8")
    if "-- vrml:axiom-audit" in original or "#print axioms" in original:
        raise ValueError("already instrumented source")
    blocks = list(BLOCK.finditer(original))
    count, _ = STAGES[source.stem]
    if len(blocks) != count:
        raise ValueError(f"{source.name}: expected {count} theorems, got {len(blocks)}")
    proofs = {}
    for block in blocks:
        name, statement_hash = block.group("name"), block.group("hash")
        if name in proofs or expected.get(name) != statement_hash:
            raise ValueError(f"duplicate or changed theorem: {name}")
        declaration = block.group("body").split(" := by\n", 1)[0]
        if f"@[vrml_obligation] theorem {name.rsplit('.', 1)[-1]}" not in declaration:
            raise ValueError(f"theorem declaration/name mismatch: {name}")
        proofs[name] = statement_hash
    source.write_text(
        original + "\n-- vrml:axiom-audit\n"
        + "\n".join(f"#print axioms {name}" for name in sorted(proofs)) + "\n",
        encoding="utf-8",
    )
    manifest.write_text(
        json.dumps({"stage": source.stem, "proofs": proofs}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"AXIOM_AUDIT_PREPARED {source.stem} {len(proofs)}")


def parse_report(output: str, expected: set[str]) -> dict[str, list[str]]:
    observed = {}
    for match in AXIOM_REPORT.finditer(output):
        name = match.group("name")
        if name not in expected:
            raise ValueError(f"unexpected axiom report for {name}")
        if name in observed:
            raise ValueError(f"duplicate axiom report for {name}")
        axioms = [] if match.group("none") else [
            item.strip() for item in match.group("axioms").split(",")
        ]
        if any(not item for item in axioms):
            raise ValueError(f"malformed axiom listing for {name}")
        unapproved = sorted(set(axioms) - APPROVED)
        if unapproved:
            raise ValueError(f"{name} has unapproved transitive axioms: {unapproved}")
        observed[name] = sorted(set(axioms))
    missing = expected - observed.keys()
    if missing:
        raise ValueError(f"missing axiom reports: {sorted(missing)}")
    return observed


def verify(index: Path, root: Path, receipt: Path) -> dict:
    originals = inventory(index)
    observed = {}
    reports = {}
    for stage, (count, stdout_name) in STAGES.items():
        manifest = json.loads(
            (root / f"{stage}-axioms-expected.json").read_text(encoding="utf-8")
        )
        if manifest.get("stage") != stage:
            raise ValueError(f"unexpected stage manifest: {stage}")
        proofs = manifest.get("proofs")
        if not isinstance(proofs, dict) or len(proofs) != count:
            raise ValueError(f"incorrect theorem count for {stage}")
        if any(originals.get(name) != sha or name in observed
               for name, sha in proofs.items()):
            raise ValueError(f"duplicated or changed original statements in {stage}")
        observed.update(proofs)
        reports[stage] = parse_report(
            (root / stdout_name).read_text(encoding="utf-8"), set(proofs)
        )
    if len(observed) != 147:
        raise ValueError(f"expected 147 distinct accepted proofs, got {len(observed)}")
    result = {
        "approved_axioms": sorted(APPROVED),
        "source_keyed_proofs_audited": len(observed),
        "proof_counts_by_stage": {stage: len(proofs) for stage, proofs in reports.items()},
        "axioms_by_proof": {
            name: dependencies for proofs in reports.values()
            for name, dependencies in proofs.items()
        },
        "transitive_imported_axioms_checked": True,
        "whole_case_study_verified": False,
        "source_to_lean_refinement_proven": False,
    }
    receipt.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                       encoding="utf-8")
    print(f"AXIOM_AUDIT_PASSED {len(observed)} SOURCE_KEYED_THEOREMS")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--index", type=Path, required=True)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    v = sub.add_parser("verify")
    v.add_argument("--index", type=Path, required=True)
    v.add_argument("--root", type=Path, required=True)
    v.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.index, args.source, args.manifest)
    else:
        verify(args.index, args.root, args.receipt)


if __name__ == "__main__":
    main()
