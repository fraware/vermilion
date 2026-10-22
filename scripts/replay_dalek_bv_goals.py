#!/usr/bin/env python3
"""Extract exact, source-keyed unsimplified Dalek BV goals and replay in Lean.

This is an isolated kernel certificate experiment, not a Verus source-level
soundness proof. The propositions come from pinned generated Lean; assertions
must be closed, nontrivial, and unmodified. Fail closed on any drift.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from audit_dalek_bv_provenance import HISTORICAL, PIN, START, parse_lean

ASSERT = re.compile(r"(?m)^@\[vrml_obligation\] theorem ([A-Za-z_][A-Za-z_0-9]*)\s*$")
END_HEADER = ":= by"
FINAL_BINDER = re.compile(r"\)\s*:\s*\n")
BINDER = re.compile(r"(?m)^\s*\(([A-Za-z_][A-Za-z_0-9]*)\s*:")


def extract_conclusion(path: Path, obligation: str, statement_hash: str) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8")
    markers = list(START.finditer(text))
    matches = [(index, m) for index, m in enumerate(markers)
               if m.group(1) == obligation and m.group(2) == statement_hash]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one goal marker at {path}: {obligation}")
    index, marker = matches[0]
    bound = markers[index + 1].start() if index + 1 < len(markers) else len(text)
    stop = text.find("-- vrml:end " + obligation, marker.end(), bound)
    if stop < 0:
        raise ValueError(f"Missing obligation closing marker {obligation}")
    block = text[marker.end():stop]
    theorems = list(ASSERT.finditer(block))
    if len(theorems) != 1:
        raise ValueError(f"Expected exactly one annotated theorem {obligation}")
    theorem = theorems[0]
    if theorem.group(1) != obligation.rsplit(".", 1)[-1]:
        raise ValueError(f"Declaration leaf does not match obligation: {obligation}")
    header_end = block.find(END_HEADER, theorem.end())
    if header_end < 0:
        raise ValueError(f"Missing theorem body separator in {obligation}")
    declaration = block[theorem.end():header_end]
    last_binder = list(FINAL_BINDER.finditer(declaration))
    if len(last_binder) != 1:
        raise ValueError(f"Cannot uniquely identify conclusion boundary in {obligation}")
    separator = last_binder[0]
    parameter_text = declaration[:separator.end()]
    goal = declaration[separator.end():].strip()
    if not goal or goal == "True":
        raise ValueError(f"Unexpected missing or trivial Lean conclusion: {obligation}")
    if "sorry" in goal or "admit" in goal:
        raise ValueError(f"Admitted or malformed extracted proposition: {obligation}")
    bound_names = BINDER.findall(parameter_text)
    if len(bound_names) == 0 or len(set(bound_names)) != len(bound_names):
        raise ValueError(f"Unexpected binder structure: {obligation}")
    # All six target propositions are closed arithmetic equalities/inequalities.
    # If a conclusion mentions a parameter, this isolated proof would
    # not establish the correct dependent theorem and must refuse.
    for name in bound_names:
        if re.search(r"(?<![\w])" + re.escape(name) + r"(?![\w])", goal):
            raise ValueError(f"Free binder {name} in supposedly closed goal: {obligation}")
    return goal, theorem.group(1)


def extract(generated: Path, report: Path) -> tuple[str, dict]:
    data = json.loads(report.read_text(encoding="utf-8"))
    if data.get("pinned_dalek_commit") != PIN:
        raise ValueError("Pinned dalek-lite source commit drift")
    rows = data.get("observations")
    if not isinstance(rows, list) or len(rows) != len(HISTORICAL):
        raise ValueError("Expected exactly six audited SST rows")
    parsed = parse_lean(generated)
    indexed = {}
    for row in rows:
        key = row["source"]
        if key in indexed:
            raise ValueError(f"Duplicate source key: {key}")
        indexed[key] = row
    expected_keys = {f"{filename}:{line}" for filename, line in HISTORICAL}
    if set(indexed) != expected_keys:
        raise ValueError(f"Source-keyed SST record drift: {sorted(indexed)}")

    lean = [
        "import Vermilion.Prelude",
        "",
        "/-! Replayed from the six exact native unsimplified dalek-lite goal",
        "    statements. This is a kernel-check experiment for their closed",
        "    mathematical propositions only; source-to-SST validity remains",
        "    an independent trust obligation. -/",
        "set_option maxRecDepth 16384",
        "set_option maxHeartbeats 0",
        "namespace DalekBvSourceReplay",
        "",
    ]
    receipts = []
    normalized_goals = set()
    root = generated.resolve()
    for filename, line in sorted(HISTORICAL):
        key = (filename, line)
        source_key = f"{filename}:{line}"
        trace = indexed[source_key]
        entry = parsed[key]
        if trace.get("generated_lean", {}).get("statement_hash") != entry["statement_hash"]:
            raise ValueError(f"Mismatch between provenance and actual Lean statement at {source_key}")
        if trace.get("generated_lean", {}).get("literal_true_goal") is not False:
            raise ValueError(f"Expected unsimplified non-True Lean goal at {source_key}")
        if trace.get("matches_historical_hash") is not False:
            raise ValueError(f"Expected changed historical statement hash at {source_key}")
        if trace.get("prepoly_SST_ensure_debug") == "Const(Bool(true))":
            raise ValueError(f"Preprocessing still erased the query at {source_key}")
        target = Path(entry["lean_file"]).resolve()
        if not target.is_relative_to(root):
            raise ValueError(f"Lean source escaped generated tree: {target}")
        goal, leaf = extract_conclusion(target, entry["obligation"], entry["statement_hash"])
        proof_name = f"source_{filename.removesuffix('.rs')}_{line}"
        clean = " ".join(goal.split())
        normalized_goals.add(clean)
        lean.extend([
            f"-- Source: {source_key}; generated hash: {entry['statement_hash']}",
            f"theorem {proof_name} :",
            f"    {goal} := by",
            "  decide",
            f"#print axioms {proof_name}",
            "",
        ])
        receipts.append({
            "source": source_key,
            "obligation": entry["obligation"],
            "generated_statement_hash": entry["statement_hash"],
            "logical_conclusion_sha256": hashlib.sha256(goal.encode("utf-8")).hexdigest(),
            "proof_name": proof_name,
            "proof_tactic": "decide",
        })
    if len(normalized_goals) != 4:
        raise ValueError(f"Expected four distinct exact formulas; found {len(normalized_goals)}")
    lean.extend(["end DalekBvSourceReplay", ""])
    output = "\n".join(lean)
    return output, {
        "claim": "Six exact unsimplified closed Lean propositions replayed; source translation and full case-study correctness are not certified",
        "pinned_source_commit": PIN,
        "six_source_keyed_goals": receipts,
        "distinct_formula_count": len(normalized_goals),
        "lean_module_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
        "verified": False,
        "verified_set_only_after_native_lean_exit": True,
    }


def main() -> int:
    cli = argparse.ArgumentParser()
    cli.add_argument("--generated", type=Path, required=True)
    cli.add_argument("--report", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--receipt", type=Path, required=True)
    opts = cli.parse_args()
    try:
        module, receipt = extract(opts.generated, opts.report)
        opts.output.parent.mkdir(parents=True, exist_ok=True)
        opts.receipt.parent.mkdir(parents=True, exist_ok=True)
        opts.output.write_text(module, encoding="utf-8")
        opts.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                                encoding="utf-8")
        print("Extracted six source-keyed goals, four distinct propositions; kernel check pending")
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f"FAIL CLOSED: could not extract six exact source-keyed formulas: {error}",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
