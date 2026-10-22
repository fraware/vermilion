#!/usr/bin/env python3
"""Select the six unsimplified pinned Dalek BV proof blocks, without weakening.

Copy exact generated obligation markers, metadata, names and signatures;
replace only the proof tactic with "decide" in an isolated source subset.
This is NOT a whole-original-unit verification. Other generated obligations
are intentionally excluded and remain unadjudicated by this experiment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from audit_dalek_bv_provenance import HISTORICAL, PIN, START, parse_lean
from replay_dalek_bv_goals import ASSERT, END_HEADER, extract_conclusion

STEMS = {"field_u64", "field_lemmas_mul_lemmas", "pow2k_lemmas"}


def select_exact_block(path: Path, obligation: str, expected_hash: str):
    source = path.read_text(encoding="utf-8")
    matches = list(START.finditer(source))
    selected = [(i, m) for i, m in enumerate(matches)
                if m.group(1) == obligation and m.group(2) == expected_hash]
    if len(selected) != 1:
        raise ValueError(f"missing or duplicated exact generated block: {obligation}")
    i, marker = selected[0]
    boundary = matches[i + 1].start() if i + 1 < len(matches) else len(source)
    end = "-- vrml:end " + obligation
    end_pos = source.find(end, marker.end(), boundary)
    if end_pos < 0 or source.find(end, end_pos + 1, boundary) >= 0:
        raise ValueError(f"missing/duplicated end marker: {obligation}")
    block = source[marker.start():end_pos + len(end)]
    thms = list(ASSERT.finditer(block))
    if len(thms) != 1 or thms[0].group(1) != obligation.rsplit(".", 1)[-1]:
        raise ValueError(f"generated theorem declaration mismatch: {obligation}")
    split = block.find(END_HEADER, thms[0].end())
    if split < 0 or block.find(END_HEADER, split + 1) >= 0:
        raise ValueError(f"ambiguous theorem proof boundary: {obligation}")
    old_header = block[:split + len(END_HEADER)]
    if not re.search(r'(?m)^\s*statementHash := "' + expected_hash + r'"\s*$', old_header):
        raise ValueError(f"metadata statement hash mismatch: {obligation}")
    if not re.search(r"(?m)^-- vrml:begin " + re.escape(obligation) +
                     r" " + expected_hash + r"$", old_header):
        raise ValueError(f"unmatched begin marker: {obligation}")
    if old_header.count("@[vrml_obligation] theorem ") != 1:
        raise ValueError(f"unexpected obligation attribute: {obligation}")
    # Never copy original automation (which may be unsolved), nor alter the
    # original theorem signature or metadata. Only the proof body changes.
    patched = old_header + "\n  decide\n" + end + "\n"
    leaf = obligation.rsplit(".", 1)[-1]
    patched += f"#print axioms {leaf}\n"
    return {
        "patched_block": patched,
        "original_block_sha256": hashlib.sha256(block.encode()).hexdigest(),
        "unmodified_header_sha256": hashlib.sha256(old_header.encode()).hexdigest(),
        "proof_tactic": "decide",
        "leaf": leaf,
    }


def build(generated: Path, provenance: Path, output: Path):
    original = json.loads(provenance.read_text(encoding="utf-8"))
    if original.get("pinned_dalek_commit") != PIN:
        raise ValueError("pinned source drift")
    rows = original.get("observations")
    if not isinstance(rows, list) or len(rows) != 6:
        raise ValueError("six SST rows required")
    index = {r["source"]: r for r in rows}
    expected = {f"{fn}:{ln}" for fn, ln in HISTORICAL}
    if set(index) != expected or len(index) != len(rows):
        raise ValueError("SST source coverage mismatch")
    lean = parse_lean(generated)
    groups = {}
    receipts = []
    for file, line in sorted(HISTORICAL):
        key = (file, line)
        source_key = f"{file}:{line}"
        row = index[source_key]
        entry = lean[key]
        if row["generated_lean"]["statement_hash"] != entry["statement_hash"]:
            raise ValueError(f"provenance hash drift at {source_key}")
        if row["generated_lean"]["literal_true_goal"] is not False:
            raise ValueError(f"nontrivial proposition disappeared at {source_key}")
        if row.get("matches_historical_hash") is not False:
            raise ValueError(f"unexpected historical signature at {source_key}")
        path = Path(entry["lean_file"]).resolve()
        if not path.is_relative_to(generated.resolve()):
            raise ValueError("input path escapes generated source")
        stem = path.parent.name
        if stem not in STEMS:
            raise ValueError(f"unexpected stem {stem}")
        goal, _ = extract_conclusion(path, entry["obligation"], entry["statement_hash"])
        if goal == "True":
            raise ValueError("trivialized obligation not allowed")
        picked = select_exact_block(path, entry["obligation"], entry["statement_hash"])
        source = path.read_text(encoding="utf-8")
        markers = list(START.finditer(source))
        preamble = source[:markers[0].start()]
        if preamble.count("namespace ") != 1:
            raise ValueError(f"ambiguous source namespace: {stem}")
        namespace = re.search(r"(?m)^namespace ([A-Za-z_][\w.]*)$", preamble)
        if namespace is None:
            raise ValueError(f"missing namespace: {stem}")
        tail_match = re.search(r"(?m)^end " + re.escape(namespace.group(1)) +
                               r"\s*$", source)
        if not tail_match:
            raise ValueError(f"missing original namespace terminator: {stem}")
        group = groups.setdefault(stem, {"preamble": preamble,
                                          "tail": source[tail_match.start():],
                                          "selected": []})
        if group["preamble"] != preamble:
            raise ValueError(f"module preamble drift: {stem}")
        if any(q["leaf"] == picked["leaf"] for q in group["selected"]):
            raise ValueError(f"colliding original theorem leaf: {picked['leaf']}")
        group["selected"].append(picked)
        receipts.append({
            "source": source_key,
            "obligation": entry["obligation"],
            "generated_statement_hash": entry["statement_hash"],
            "original_block_sha256": picked["original_block_sha256"],
            "unmodified_header_sha256": picked["unmodified_header_sha256"],
            "proof_tactic": "decide",
            "original_metadata_preserved": True,
            "all_other_original_unit_obligations_checked": False,
        })
    if set(groups) != STEMS or len(receipts) != 6:
        raise ValueError("three source units and six obligations required")
    output.mkdir(parents=True, exist_ok=True)
    output_hashes = {}
    for stem, group in sorted(groups.items()):
        content = group["preamble"] + "\n" + "\n".join(
            block["patched_block"] for block in group["selected"]
        ) + "\n" + group["tail"]
        path = output / (stem + ".lean")
        path.write_text(content, encoding="utf-8")
        output_hashes[stem] = hashlib.sha256(content.encode()).hexdigest()
    return {
        "claim": "Six original generated obligation blocks, metadata and names preserved; only proof bodies replaced. This is not full-unit acceptance.",
        "pinned_dalek_commit": PIN,
        "receipts": receipts,
        "subset_module_sha256": output_hashes,
        "subset_modules_native_kernel_check_required": True,
    }


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--generated", type=Path, required=True)
    cli.add_argument("--report", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--receipt", type=Path, required=True)
    args = cli.parse_args()
    try:
        report = build(args.generated, args.report, args.output)
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n",
                                encoding="utf-8")
        print("Selected six original metadata-preserving generated blocks; kernel-check pending")
        return 0
    except (KeyError, ValueError, TypeError, OSError) as error:
        print(f"FAIL CLOSED: generated BV block replay: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
