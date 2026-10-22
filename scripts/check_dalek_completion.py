#!/usr/bin/env python3
"""Fail-closed dalek-lite full-cone acceptance; negative-control mode is NOT proof.

A source-to-Lean proof requires a fresh manifest set, no refused functions,
no 'sorry' / 'admit' in tracked twin files, and independent successful
vrml_check --twin-check on *every* manifest. Do not equate an isolated
six- or two-theorem research certificate with this acceptance gate.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

ADMIT = re.compile(r"(?m)^\s*(?:sorry|admit)\s*(?:--[^\n]*)?$")


def audit(generated: Path, proofs: Path) -> dict:
    result = dict(accepted=False, kernel_checked=False, status="INCOMPLETE",
                  manifest_count=0, obligation_count=0, refused_count=0, refused_records_count=0,
                  tracked_admission_count=0, refused_functions=[],
                  tracked_admissions=[], problems=[])
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
        for marker in ADMIT.finditer(source):
            result["tracked_admission_count"] += 1
            result["tracked_admissions"].append({
                "path": str(proof),
                "line": source.count("\n", 0, marker.start()) + 1,
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
    result["accepted"] = True
    result["kernel_checked"] = True
    result["status"] = "ALL_GENERATED_TWINS_NATIVE_CHECKED"
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
