#!/usr/bin/env python3
"""Fail-closed dalek-lite full-cone audit; negative-control mode is not proof.

Full acceptance requires fresh manifests, no refusals, no tracked admissions,
native proof-twin checks, and a declaration-level Lean axiom-dependency audit.
This gate audits source-to-Lean obligations, not translator semantics.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

from lean_admission_scan import admission_positions
from audit_lean_axioms import audit_proof_unit


# Complete dalek-lite Layer Set A inventory, pinned from 27 tracked proof
# subdirectories. Any expansion or contraction needs an explicit review.
EXPECTED_MANIFEST_STEMS = frozenset([
    "add_lemmas",
    "as_bytes_lemmas",
    "bit_lemmas",
    "common_lemmas_mul_lemmas",
    "compute_q_lemmas",
    "div_mod_lemmas",
    "field_lemmas_mul_lemmas",
    "field_specs",
    "field_specs_u64",
    "field_u64",
    "from_bytes_lemmas",
    "layer_a",
    "limbs_to_bytes_lemmas",
    "load8_lemmas",
    "mask_lemmas",
    "negate_lemmas",
    "number_theory_lemmas",
    "pow2_51_lemmas",
    "pow2k_lemmas",
    "pow_lemmas",
    "primality_specs",
    "reduce_lemmas",
    "shift_lemmas",
    "sum_lemmas",
    "to_bytes_reduction_lemmas",
    "to_nat_lemmas",
    "u64_5_as_nat_lemmas",
])
BASELINE_OBLIGATIONS = 5215


def validate_full_scope(generated: Path, proofs: Path, result: dict) -> bool:
    actual = {p.stem for p in generated.glob("*.json")}
    if actual != EXPECTED_MANIFEST_STEMS:
        missing = sorted(EXPECTED_MANIFEST_STEMS - actual)
        extra = sorted(actual - EXPECTED_MANIFEST_STEMS)
        result["problems"].append(
            f"incomplete dalek-lite manifest inventory: missing={missing}; extra={extra}"
        )
        return False
    if result["obligation_count"] < BASELINE_OBLIGATIONS:
        result["problems"].append(
            f"dalek-lite obligation inventory shrank below {BASELINE_OBLIGATIONS}: "
            f"{result['obligation_count']}; review scope or the acquisition pipeline"
        )
        return False
    empty = [stem for stem in sorted(EXPECTED_MANIFEST_STEMS)
             if not (proofs / stem).is_dir()
             or not any((proofs / stem).glob("*.lean"))]
    if empty:
        result["problems"].append(f"missing dalek-lite tracked proof directories: {empty}")
        return False
    result["scope_checked"] = True
    return True


def audit(generated: Path, proofs: Path) -> dict:
    result = dict(accepted=False, kernel_checked=False, axiom_dependencies_audited=False,
                  status="INCOMPLETE",
                  manifest_count=0, obligation_count=0, refused_count=0, refused_records_count=0,
                  tracked_admission_count=0, refused_functions=[],
                  tracked_admissions=[], scope_checked=False, problems=[])
    if not generated.is_dir():
        result["problems"].append(f"missing generated directory: {generated}")
        return result
    manifests = sorted(generated.glob("*.json"))
    if not manifests:
        result["problems"].append("no generated manifests")
        return result
    result["manifest_count"] = len(manifests)
    distinct_refused = {}
    for file in manifests:
        try:
            doc = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as err:
            result["problems"].append(f"malformed manifest {file}: {err}")
            continue
        if not isinstance(doc, dict):
            result["problems"].append(f"nonobject manifest {file}")
            continue
        if doc.get("mode") != "per-function":
            result["problems"].append(f"unexpected emission mode in {file}")
        obligations = doc.get("obligations")
        refused = doc.get("refused", [])
        if not isinstance(obligations, list) or not isinstance(refused, list):
            result["problems"].append(f"malformed obligation/refusal collection: {file}")
            continue
        result["obligation_count"] += len(obligations)
        seen = set()
        for row in obligations:
            if not isinstance(row, dict):
                result["problems"].append(f"nonobject obligation: {file}")
                continue
            name, digest = row.get("name"), row.get("statement_hash")
            if (not isinstance(name, str) or not name
                or not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{16}", digest)):
                result["problems"].append(f"invalid obligation/hash: {file}")
                continue
            if name in seen:
                result["problems"].append(f"duplicate obligation identity in {file}: {name}")
            seen.add(name)
            unit = row.get("lean_file") or doc.get("lean_file")
            if not isinstance(unit, str) or not unit or not Path(unit).is_file():
                result["problems"].append(f"missing Lean obligation source {name}: {unit}")
        for refused_row in refused:
            result["refused_records_count"] += 1
            if (not isinstance(refused_row, dict)
                or not isinstance(refused_row.get("function"), str)
                or not isinstance(refused_row.get("message"), str)):
                result["problems"].append(f"invalid refusal: {file}")
                continue
            key = refused_row["function"]
            if key in distinct_refused:
                if distinct_refused[key]["message"] != refused_row["message"]:
                    result["problems"].append(f"conflicting refusal messages for {key}")
            else:
                distinct_refused[key] = {
                    "manifest": str(file),
                    "function": key,
                    "message": refused_row["message"],
                }
    result["refused_count"] = len(distinct_refused)
    result["refused_functions"] = sorted(distinct_refused.values(),
                                         key=lambda row: row["function"])
    if not proofs.is_dir():
        result["problems"].append(f"missing tracked proof twins: {proofs}")
        return result
    proof_files = sorted(proofs.rglob("*.lean"))
    if not proof_files:
        result["problems"].append("no tracked Lean proof twins")
        return result
    for proof in proof_files:
        try:
            source = proof.read_text(encoding="utf-8")
        except OSError as err:
            result["problems"].append(f"unreadable proof twin {proof}: {err}")
            continue
        try:
            admissions = admission_positions(source)
        except ValueError as error:
            result["problems"].append(f"cannot scan Lean proof {proof}: {error}")
            continue
        for line, token in admissions:
            result["tracked_admission_count"] += 1
            result["tracked_admissions"].append({
                "path": str(proof),
                "line": line,
                "token": token,
            })
    return result


def complete(generated: Path, proofs: Path, checker: Path | None,
             sync_probe: Path | None) -> dict:
    result = audit(generated, proofs)
    if result["problems"] or result["refused_count"] or result["tracked_admission_count"]:
        return result
    if generated.name != "generated":
        result["problems"].append("full twin certification requires canonical generated/ path")
        return result
    if not validate_full_scope(generated, proofs, result):
        return result
    if (checker is None or not checker.is_file()
        or sync_probe is None or not sync_probe.is_file()):
        result["problems"].append("full acceptance requires vrml_sync --probe and vrml_check --twin-check")
        return result
    for manifest in sorted(generated.glob("*.json")):
        try:
            freshness = subprocess.run(
                [str(sync_probe.resolve()), str(manifest), "--probe"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120,
            )
            if freshness.returncode != 0:
                result["problems"].append(
                    f"stale proof twin at {manifest}: exit={freshness.returncode}; stderr={freshness.stderr[:1000]}"
                )
                return result
            verdict = subprocess.run(
                [str(checker.resolve()), str(manifest), "--twin-check"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600,
            )
        except (OSError, subprocess.TimeoutExpired) as err:
            result["problems"].append(f"native checker failure at {manifest}: {err}")
            return result
        if verdict.returncode != 0:
            result["problems"].append(
                f"native twin failure at {manifest}: exit={verdict.returncode}; stderr={verdict.stderr[:1000]}"
            )
            return result
    # Lean accepts 'sorry' and axioms as proof terms; an exit-0 native
    # checker alone cannot certify the absence of unacceptable dependencies.
    # Retain its receipt but FAIL CLOSED until a declaration-level axiom audit
    # is implemented and independently validated.
    result["kernel_checked"] = True
    units: dict[Path, set[str]] = {}
    for manifest in sorted(generated.glob("*.json")):
        doc = json.loads(manifest.read_text(encoding="utf-8"))
        for row in doc["obligations"]:
            generated_unit = row.get("lean_file") or doc.get("lean_file")
            if not isinstance(generated_unit, str) or "/generated/" not in generated_unit:
                result["problems"].append(f"invalid generated unit path: {generated_unit}")
                return result
            twin = Path(generated_unit.replace("/generated/", "/proofs/", 1))
            if not twin.is_file():
                result["problems"].append(f"missing proof unit for axiom audit: {twin}")
                return result
            units.setdefault(twin, set()).add(row["name"])
    if not units:
        result["problems"].append("no theorem units for axiom audit")
        return result
    result["axiom_audited_units"] = 0
    for file, names in sorted(units.items()):
        passed, receipt = audit_proof_unit(file, sorted(names))
        if not passed:
            result["problems"].append(receipt)
            return result
        result["axiom_audited_units"] += 1
    result["axiom_dependencies_audited"] = True
    result["accepted"] = True
    result["status"] = "ALL_GENERATED_TWINS_NATIVE_AND_AXIOMS_CHECKED"
    return result


def main() -> int:
    cli = argparse.ArgumentParser()
    cli.add_argument("--generated", type=Path, required=True)
    cli.add_argument("--proofs", type=Path, required=True)
    cli.add_argument("--report-json", type=Path, required=True)
    cli.add_argument("--checker", type=Path)
    cli.add_argument("--sync-probe", type=Path)
    cli.add_argument("--expect-incomplete", action="store_true")
    options = cli.parse_args()
    if options.expect_incomplete and (options.checker or options.sync_probe):
        cli.error("negative control cannot request a positive checker verdict")
    result = (audit(options.generated, options.proofs) if options.expect_incomplete
              else complete(options.generated, options.proofs, options.checker,
                            options.sync_probe))
    options.report_json.parent.mkdir(parents=True, exist_ok=True)
    options.report_json.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                                   encoding="utf-8")
    print(f"STATUS={result['status']} manifests={result['manifest_count']} "
          f"obligations={result['obligation_count']} unique_refused={result['refused_count']} "
          f"raw_refusal_records={result['refused_records_count']} "
          f"tracked_admits={result['tracked_admission_count']} "
          f"schema_errors={len(result['problems'])}")
    if options.expect_incomplete:
        if not result["problems"] and (result["refused_count"] or result["tracked_admission_count"]):
            print("REJECTED_AS_EXPECTED -- NOT VERIFIED")
            return 0
        print("NEGATIVE_CONTROL_INVALID: missing blockers or malformed input", file=sys.stderr)
        return 2
    if result["accepted"]:
        print("ALL_GENERATED_TWINS_NATIVE_CHECKED")
        return 0
    print("FAIL CLOSED: whole-case-study acceptance NOT established", file=sys.stderr)
    return 2 if result["problems"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
