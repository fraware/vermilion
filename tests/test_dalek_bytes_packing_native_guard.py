#!/usr/bin/env python3
"""Negative-control tests for source-keyed byte-packing proof generation.

Executed against exactly the native-generated Lean module and VC inventory.
Does not prove the Lean theorem. The generated theorem still needs kernel CI.
"""
from __future__ import annotations
import argparse
import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

TARGET = "layer_a.backend.serial.u64.field.impl__16.as_bytes.call_requires_7_1"

def exercise(script: Path, index: Path, modules: Path):
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        index_data = json.loads(index.read_text(encoding="utf-8"))
        source = modules / index_data["obligations"][0]["module"]
        raw = source.read_bytes()
        dest = d / "src" / index_data["obligations"][0]["module"]
        dest.parent.mkdir(parents=True)
        dest.write_bytes(raw)

        def run(data, mutate_source=None):
            (d / "index.json").write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
            dest.write_bytes(raw if mutate_source is None else mutate_source)
            return subprocess.run(
                [sys.executable, str(script), "--index", str(d / "index.json"),
                 "--modules", str(d / "src"), "--output", str(d / "proof.lean"),
                 "--report", str(d / "proof.json")],
                capture_output=True, text=True,
            )

        passed = 0
        baseline = run(index_data)
        assert baseline.returncode == 0, ("valid original input rejected", baseline.stderr)
        payload = (d / "proof.lean").read_bytes()
        receipt = json.loads((d / "proof.json").read_text())
        assert receipt["name"] == TARGET and receipt["requires_lean_kernel_check"] is True
        assert receipt["whole_case_study_verified"] is False
        assert receipt["statement_hash"] == "fab974571da9922d"
        assert b"theorem call_requires_7_1" in payload and b" := by\n" in payload
        assert b"sorry" not in payload and b"admit" not in payload
        again = run(index_data)
        assert again.returncode == 0 and (d / "proof.lean").read_bytes() == payload
        passed += 2

        mutated = copy.deepcopy(index_data)
        mutated["obligations"][1]["name"] = mutated["obligations"][0]["name"]
        assert run(mutated).returncode != 0
        passed += 1

        mutated = copy.deepcopy(index_data)
        next(r for r in mutated["obligations"] if r["name"] == TARGET)["statement_hash"] = "0000000000000000"
        assert run(mutated).returncode != 0
        passed += 1

        mutated = copy.deepcopy(index_data)
        mutated["obligations"].pop()
        assert run(mutated).returncode != 0
        passed += 1

        mutated = copy.deepcopy(index_data)
        mutated["target_function"] = "different.target"
        assert run(mutated).returncode != 0
        passed += 1

        mutated = copy.deepcopy(index_data)
        mutated["obligations"][0]["module_sha256"] = "0" * 64
        assert run(mutated).returncode != 0
        passed += 1

        assert run(index_data, raw.replace(b"-- vrml:begin ", b"-- modified:begin ", 1)).returncode != 0
        passed += 1

        mutated = copy.deepcopy(index_data)
        for row in mutated["obligations"]:
            row["module"] = "../../outside.lean"
        assert run(mutated).returncode != 0
        passed += 1

        assert passed == 9
        print(f"BYTE_PACKING_GENERATOR_SOURCE_CONTROLS_PASS {passed} (no Lean proof acceptance)")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--script", type=Path, required=True)
    p.add_argument("--index", type=Path, required=True)
    p.add_argument("--modules", type=Path, required=True)
    a = p.parse_args()
    exercise(a.script.resolve(), a.index.resolve(), a.modules.resolve())
