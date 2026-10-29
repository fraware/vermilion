#!/usr/bin/env python3
"""Fail-closed source-keyed VC reconciliation for opt-in SSA lowering.

Control is the exact 5835-VC experimental Verus acquisition at
https://github.com/fraware/vermilion/actions/runs/40264315710
(artifact 12625498679). This tests emitted statement stability, not
the source-to-Lean translation's semantic soundness or theorem discharge.
"""
import argparse
import hashlib
import json
from pathlib import Path

CONTROL_VCS = 5835
CONTROL_FINGERPRINT = "76dd7d9ce6cd675c27446f8bc5fae9297dce61e8151592ad87269a9da1ffb36d"
SOURCE_SHA = "de9ebf01599fedbbced28b938e2c36c538fe4ae5"
VERUS_SHA = "4b030e0a8268ed4c0fd3ee8cb2a5356e6535f248"
RECOVERED = "layer_a.backend.serial.u64.field.impl__16.as_bytes."


def fingerprint(table: dict[str, str]) -> str:
    if any("\t" in k or "\n" in k or "\n" in v for k, v in table.items()):
        raise ValueError("unexpected field delimiter in VC inventory")
    return hashlib.sha256(
        "".join(f"{k}\t{table[k]}\n" for k in sorted(table)).encode()
    ).hexdigest()


def load_receipt(content: str) -> dict:
    """Retain all evidence: reject duplicate JSON keys, including nested keys."""
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError(f"duplicate JSON key in acquisition receipt: {key}")
            obj[key] = value
        return obj
    doc = json.loads(content, object_pairs_hook=unique)
    if not isinstance(doc, dict):
        raise ValueError("expected object-valued acquisition receipt")
    return doc


def validate_acquisition(document: dict) -> dict:
    if document.get("source_sha") != SOURCE_SHA or document.get("verus_sha") != VERUS_SHA:
        raise ValueError("pinned source or Verus revision changed")
    if document.get("whole_case_study_verified") is not False:
        raise ValueError("experimental receipt must disclaim proof of full case study")
    if document.get("refused_functions") != {}:
        raise ValueError("experimental acquisition still has refused functions")
    all_vcs = document.get("source_keyed_obligations")
    if not isinstance(all_vcs, dict) or any(
        not isinstance(k, str) or not isinstance(v, str) for k, v in all_vcs.items()
    ):
        raise ValueError("missing or malformed source-keyed obligations")
    preserved = {k: v for k, v in all_vcs.items() if not k.startswith(RECOVERED)}
    added = {k: v for k, v in all_vcs.items() if k.startswith(RECOVERED)}
    if len(preserved) != CONTROL_VCS or fingerprint(preserved) != CONTROL_FINGERPRINT:
        raise ValueError("pre-existing obligation statement IDs/hashes altered")
    if not added:
        raise ValueError("as_bytes did not emit any VCs")
    return {
        "preexisting_vcs_exactly_preserved": len(preserved),
        "as_bytes_new_vcs": len(added),
        "total_vcs": len(all_vcs),
        "original_fingerprint": CONTROL_FINGERPRINT,
        "whole_case_study_verified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_acquisition(load_receipt(args.receipt.read_text()))
    if args.output:
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
