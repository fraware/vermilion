#!/usr/bin/env python3
"""Kernel-replay six original generated theorem signatures, including contexts.

Research only: do not replace original proof twins or claim source soundness.
Every theorem is reconstructed from a single source-keyed, hash-keyed
unsimplified generated declaration. Original binder/assumption types and
conclusion text are copied byte-for-byte. The declaration name and attribute
are changed solely to avoid collisions in the isolated research namespace.
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


def validate_original_imports(imports: str, stem: str, source_key: str) -> list[str]:
    """Require real generator imports, permitting only this unit's modules."""
    declared = re.findall(r"(?m)^import ([^\s]+)\s*$", imports)
    if "Vermilion.Obligations" not in declared:
        raise ValueError(f"missing original obligations import: {source_key}")
    allowed = {
        "Vermilion.Obligations",
        f"generated.{stem}.Specs",
        f"generated.{stem}.Evidence",
    }
    if len(declared) != len(set(declared)) or not set(declared).issubset(allowed):
        raise ValueError(f"unexpected/duplicate original import: {source_key}: {declared}")
    return declared


def source_declaration(path: Path, obligation: str, digest: str):
    source = path.read_text(encoding="utf-8")
    markers = list(START.finditer(source))
    matches = [(i, m) for i, m in enumerate(markers)
               if m.group(1) == obligation and m.group(2) == digest]
    if len(matches) != 1:
        raise ValueError(f"missing/duplicate exact obligation {obligation}: {path}")
    idx, marker = matches[0]
    end_bound = markers[idx + 1].start() if idx + 1 < len(markers) else len(source)
    stop = source.find("-- vrml:end " + obligation, marker.end(), end_bound)
    if stop < 0:
        raise ValueError(f"missing end marker for {obligation}")
    block = source[marker.end():stop]
    declarations = list(ASSERT.finditer(block))
    if len(declarations) != 1:
        raise ValueError(f"expected one attributed theorem for {obligation}")
    match = declarations[0]
    leaf = obligation.rsplit(".", 1)[-1]
    if match.group(1) != leaf:
        raise ValueError(f"theorem leaf does not match {obligation}")
    header_end = block.find(END_HEADER, match.end())
    if header_end < 0:
        raise ValueError(f"missing theorem header terminator for {obligation}")
    header = block[match.start():header_end]
    first_line = f"@[vrml_obligation] theorem {leaf}"
    if not header.startswith(first_line + "\n"):
        raise ValueError(f"unexpected theorem header for {obligation}")
    binder_count = len(re.findall(r"(?m)^    \([A-Za-z_][\w']*\s*:", header))
    if binder_count == 0:
        raise ValueError(f"missing original binders at {obligation}")
    preamble = source[:markers[0].start()]
    if "namespace " not in preamble:
        raise ValueError(f"original source has no namespace: {path}")
    import_section = preamble[:preamble.find("namespace ")]
    return header, import_section, binder_count


def replay(generated: Path, provenance: Path, output: Path):
    data = json.loads(provenance.read_text(encoding="utf-8"))
    if data.get("pinned_dalek_commit") != PIN:
        raise ValueError("pinned dalek-lite source identity drift")
    samples = data.get("observations")
    if not isinstance(samples, list) or len(samples) != 6:
        raise ValueError("expected exactly six native provenance observations")
    index = {row["source"]: row for row in samples}
    expected = {f"{name}:{line}" for name, line in HISTORICAL}
    if len(index) != 6 or set(index) != expected:
        raise ValueError("source-key coverage or uniqueness mismatch")
    parsed = parse_lean(generated)
    root = generated.resolve()
    grouped = {}
    receipt = []
    classes = set()
    for name, line in sorted(HISTORICAL):
        source_key = f"{name}:{line}"
        row = index[source_key]
        entry = parsed[(name, line)]
        if row.get("generated_lean", {}).get("statement_hash") != entry["statement_hash"]:
            raise ValueError(f"provenance-generated hash mismatch: {source_key}")
        if row.get("matches_historical_hash") is not False:
            raise ValueError(f"unexpected historical hash equality: {source_key}")
        if row.get("generated_lean", {}).get("literal_true_goal") is not False:
            raise ValueError(f"unsimplified goal still True: {source_key}")
        if row.get("prepoly_SST_ensure_debug") == "Const(Bool(true))":
            raise ValueError(f"SST goal remains simplified: {source_key}")
        target = Path(entry["lean_file"]).resolve()
        if not target.is_relative_to(root):
            raise ValueError(f"source file outside generated root: {target}")
        stem = target.parent.name
        if stem not in STEMS:
            raise ValueError(f"unexpected generated Specs module: {stem}")
        exact_conclusion, _ = extract_conclusion(target, entry["obligation"],
                                                   entry["statement_hash"])
        header, imports, binders = source_declaration(target, entry["obligation"],
                                                       entry["statement_hash"])
        if not header.rstrip().endswith(exact_conclusion):
            raise ValueError(f"original signature/conclusion mismatch: {source_key}")
        # The pinned per-function generator names shared modules
        # generated.<stem>.Specs and generated.<stem>.Evidence; an
        # obligation that does not reference a shared definition might
        # import neither. Preserve that *actual* header exactly.
        validate_original_imports(imports, stem, source_key)
        proof_name = f"source_{name.removesuffix('.rs')}_{line}"
        leaf = entry["obligation"].rsplit(".", 1)[-1]
        old = f"@[vrml_obligation] theorem {leaf}"
        new_header = header.replace(old, f"theorem {proof_name}", 1)
        if new_header.replace(f"theorem {proof_name}", old, 1) != header:
            raise ValueError(f"nonidentity signature rewrite: {source_key}")
        groups = grouped.setdefault(stem, {"imports": imports, "theorems": []})
        if groups["imports"] != imports:
            raise ValueError(f"different per-file preambles for {stem}")
        groups["theorems"].extend([
            f"-- pinned source: {source_key}; generated hash: {entry['statement_hash']}",
            new_header + " := by\n  decide",
            f"#print axioms {proof_name}",
            "",
        ])
        classes.add(" ".join(exact_conclusion.split()))
        receipt.append({
            "source": source_key,
            "generated_stem": stem,
            "generated_statement_hash": entry["statement_hash"],
            "original_signature_sha256": hashlib.sha256(header.encode()).hexdigest(),
            "retained_binder_count": binders,
            "logical_conclusion_sha256": hashlib.sha256(exact_conclusion.encode()).hexdigest(),
            "original_declaration_name": leaf,
            "replay_declaration_name": proof_name,
            "replay_proof": "decide",
        })
    if set(grouped) != STEMS or len(receipt) != 6 or len(classes) != 4:
        raise ValueError("expected exactly three generated modules, six goals, four formulas")
    output.mkdir(parents=True, exist_ok=True)
    written = {}
    for stem in sorted(STEMS):
        group = grouped[stem]
        lines = [
            group["imports"].rstrip(),
            "",
            "/-! Research-only original-context replay. Original theorem parameter",
            "    declarations and conclusion are unchanged; the theorem name",
            "    and the vrml_obligation attribute are isolated for this check. -/",
            "set_option maxRecDepth 16384",
            "set_option maxHeartbeats 0",
            "namespace DalekBvOriginalContextReplay",
            "",
            *group["theorems"],
            "end DalekBvOriginalContextReplay",
            "",
        ]
        contents = "\n".join(lines)
        path = output / f"{stem}.lean"
        path.write_text(contents, encoding="utf-8")
        written[stem] = hashlib.sha256(contents.encode()).hexdigest()
    return {
        "claim": "Six original generated Lean binders/hypotheses/conclusions replayed independently; not original VRML proof twins or a translation soundness theorem",
        "pinned_dalek_commit": PIN,
        "source_keyed_declarations": receipt,
        "three_replay_modules_sha256": written,
        "distinct_closed_conclusions": len(classes),
        "kernel_check_required": True,
    }


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--generated", type=Path, required=True)
    cli.add_argument("--report", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--receipt", type=Path, required=True)
    args = cli.parse_args()
    try:
        data = replay(args.generated, args.report, args.output)
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n",
                                encoding="utf-8")
        print("Retained six exact theorem parameter/assumption contexts across three modules")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"FAIL CLOSED: original-context replay extraction: {error}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    sys.exit(main())
