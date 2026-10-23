#!/usr/bin/env python3
"""Migrate only two source-hash-keyed theorem proofs into a COPY of the tracked twin.

The source file, original assertion metadata, theorem headers, every other
proof obligation, and the historical short-ID collision wrapper remain
untouched. The output is an integration experiment, not a verified full-cone
proof or a replacement for fresh manifest/twin reconciliation.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from research_dalek_bitwise_proofs import (
    SOURCE, ORIGINAL, NAME, START, PROOF_NONOVERLAP, PROOF_SAME,
)

ADMISSION_BODY = "  -- TODO(vermilion): automation failed; prove this obligation.\n  sorry\n"
HELPER_CHANGE = [
    ("  bv_decide\n", "  exact BitVec.and_or_distrib_right\n"),
    (
        "  interval_cases p <;> bv_decide\n",
        "  rw [BitVec.and_or_distrib_right, BitVec.and_self]\n"
        "  have hnonzero : (1#8 <<< p) ≠ 0#8 := by\n"
        "    interval_cases p <;> decide\n"
        "  intro h\n"
        "  exact hnonzero (BitVec.or_eq_zero_iff.mp h).2\n"
    ),
]


def migrate(source: str) -> tuple[str, dict]:
    if source.count("namespace collision_635d62c1") != 1:
        raise ValueError("historical assertion-ID collision namespace drift")
    if source.count("end collision_635d62c1") != 1:
        raise ValueError("historical assertion-ID collision end drift")

    m = re.search(r"(?s)-- vrml:user:begin\n(.*?)-- vrml:user:end", source)
    if m is None:
        raise ValueError("missing original proof-helpers user block")
    original_helpers = m.group(1)
    helpers = original_helpers
    for before, after in HELPER_CHANGE:
        if helpers.count(before) != 1:
            raise ValueError(f"missing or duplicated exact helper tactic: {before.strip()}")
        helpers = helpers.replace(before, after, 1)
    if "bv_decide" in helpers:
        raise ValueError("unexpected native BV tactic in proof helper")
    output = source[:m.start(1)] + helpers + source[m.end(1):]

    receipts = []
    for (digest, label), proof in zip(ORIGINAL, (PROOF_NONOVERLAP, PROOF_SAME)):
        markers = list(START.finditer(output))
        selected = [(idx, item) for idx, item in enumerate(markers)
                    if item.group(1) == NAME and item.group(2) == digest]
        if len(selected) != 1:
            raise ValueError(f"historical source hash not unique: {digest}")
        i, mark = selected[0]
        boundary = markers[i + 1].start() if i + 1 < len(markers) else len(output)
        end_marker = "-- vrml:end " + NAME
        end_at = output.find(end_marker, mark.end(), boundary)
        if end_at < 0:
            raise ValueError("missing original proof-block end marker")
        block = output[mark.start():end_at]
        if block.count('statementHash := "' + digest + '"') != 1:
            raise ValueError(f"statement metadata drift at {digest}")
        theorem = "@[vrml_obligation] theorem assert_bv_5_0\n"
        if block.count(theorem) != 1:
            raise ValueError(f"original theorem declaration drift at {digest}")
        start = block.find(theorem)
        proof_intro = block.find(":= by\n", start)
        if proof_intro < 0:
            raise ValueError(f"missing theorem proof introduction: {digest}")
        header = block[:proof_intro + len(":= by\n")]
        body = block[proof_intro + len(":= by\n"):]
        if body != ADMISSION_BODY:
            raise ValueError(f"expected exactly one tracked admission at {digest}")
        replacement = header + proof.strip("\n") + "\n"
        output = output[:mark.start()] + replacement + output[end_at:]
        receipts.append({
            "hash": digest, "label": label,
            "original_theorem_header_sha256": hashlib.sha256(header.encode()).hexdigest(),
            "original_proof_body_sha256": hashlib.sha256(body.encode()).hexdigest(),
            "replaced_only_proof_body": True,
        })
    if len(receipts) != 2:
        raise ValueError("expected exactly two migrated proofs")
    for digest, _ in ORIGINAL:
        if output.count('statementHash := "' + digest + '"') != 1:
            raise ValueError("theorem hash disappeared after migration")
    if output.count(ADMISSION_BODY) != source.count(ADMISSION_BODY) - 2:
        raise ValueError("unexpected change in admission count")
    return output, {
        "claim": "two historical Lean proofs migrated in tracked-twin COPY only",
        "original_file_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "migrated_file_sha256": hashlib.sha256(output.encode()).hexdigest(),
        "original_helper_sha256": hashlib.sha256(original_helpers.encode()).hexdigest(),
        "new_helper_sha256": hashlib.sha256(helpers.encode()).hexdigest(),
        "migrated_obligations": receipts,
        "whole_case_study_verified": False,
        "full_twin_sync_and_kernel_acceptance_pending": True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    migrated, receipt = migrate(args.source.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(migrated, encoding="utf-8")
    args.receipt.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("MIGRATED_TWO_ORIGINAL_TWIN_PROOF_BODIES -- NATIVE CHECK PENDING")


if __name__ == "__main__":
    main()
