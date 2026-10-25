#!/usr/bin/env python3
"""Fail-closed source/SST/lowered-IR/generated-Lean provenance audit.

This is a research observation, NOT a verification or soundness assertion.
"""
import argparse
import json
import re
import sys
from pathlib import Path

PIN = "de9ebf01599fedbbced28b938e2c36c538fe4ae5"
HISTORICAL = {
    ("mul_lemmas.rs", 227): "aba44725bf1d8c44",
    ("mul_lemmas.rs", 231): "3c8ee05bd5d51b4d",
    ("pow2k_lemmas.rs", 236): "f9cc1a09afee1240",
    ("pow2k_lemmas.rs", 240): "bfae7daeb21f67ff",
    ("field_u64.rs", 1431): "bea6232ee1a2aab0",
    ("field_u64.rs", 1446): "4b5d62519b846699",
}
START = re.compile(r"(?m)^-- vrml:begin ([^\s]+) ([0-9a-f]{16})\s*$")
RUST_FILE = re.compile(r'(?m)^\s*rustFile := "([^"]+)"\s*$')
RUST_LINE = re.compile(r"(?m)^\s*startLine := (\d+)\s*$")
HASH = re.compile(r'(?m)^\s*statementHash := "([0-9a-f]{16})"\s*$')
TRUE_GOAL = re.compile(r"(?m)^\s+True := by\s*$")


def source_key(path, line):
    return (Path(path.replace("\\", "/")).name, int(line))


def parse_traces(log):
    evidence = {}
    count_requires = {}
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("VRML_BV_REQUIRE\t"):
            fields = dict(field.split("=", 1) for field in line.split("\t")[1:])
            key = source_key(fields["file"], fields["line"])
            count_requires[key] = count_requires.get(key, 0) + 1
            continue
        if not line.startswith("VRML_BV_PROVENANCE\t"):
            continue
        parts = line.split("\t")[1:]
        if any("=" not in field for field in parts):
            raise ValueError("Malformed trace field")
        fields = dict(field.split("=", 1) for field in parts)
        expected = {"file", "line", "column", "index", "requires", "ensures", "raw", "lowered"}
        if len(parts) != len(expected) or set(fields) != expected:
            raise ValueError("Incomplete/duplicate SST trace fields")
        key = source_key(fields["file"], fields["line"])
        if key not in HISTORICAL or key in evidence:
            raise ValueError(f"Unexpected/duplicate SST query: {key}")
        if int(fields["index"]) != 0 or int(fields["ensures"]) != 1:
            raise ValueError(f"Query with unsupported ensure cardinality at {key}")
        if not fields["raw"] or not fields["lowered"]:
            raise ValueError(f"Missing actual SST or lowered term at {key}")
        evidence[key] = fields
    if set(evidence) != set(HISTORICAL):
        raise ValueError(f"SST trace target coverage: {sorted(evidence)}")
    for key, value in evidence.items():
        if count_requires.get(key, 0) != int(value["requires"]):
            raise ValueError(f"Requires payload count disagreement at {key}")
    return evidence


def parse_lean(generated):
    result = {}
    n = 0
    for path in generated.rglob("*.lean"):
        n += 1
        source = path.read_text(encoding="utf-8")
        matches = list(START.finditer(source))
        for i, match in enumerate(matches):
            finish = matches[i + 1].start() if i + 1 < len(matches) else len(source)
            stop = source.find("-- vrml:end " + match.group(1), match.end(), finish)
            if stop < 0:
                raise ValueError(f"Missing end marker for {match.group(1)} in {path}")
            body = source[match.end():stop]
            file_match, line_match, hash_match = (
                RUST_FILE.search(body), RUST_LINE.search(body), HASH.search(body))
            if not all((file_match, line_match, hash_match)):
                raise ValueError(f"Missing source/hash metadata in {path}")
            key = source_key(file_match.group(1), line_match.group(1))
            if key not in HISTORICAL or ".assert_bv_" not in match.group(1):
                continue
            if key in result:
                raise ValueError(f"Multiple generated goals for {key}")
            if match.group(2) != hash_match.group(1):
                raise ValueError(f"Marker and metadata hash differ: {key}")
            result[key] = {
                "lean_file": str(path),
                "obligation": match.group(1),
                "statement_hash": match.group(2),
                "literal_true_goal": bool(TRUE_GOAL.search(body)),
                "rust_file_in_metadata": file_match.group(1),
            }
    if n == 0 or set(result) != set(HISTORICAL):
        raise ValueError(f"Generated goals: {n} files, targets {sorted(result)}")
    return result


def source_text(root):
    base = root / "case-studies" / "dalek-lite"
    paths = {
        "field_u64.rs": base / "field_u64.rs",
        "mul_lemmas.rs": base / "upstream/curve25519-dalek/src/lemmas/field_lemmas/mul_lemmas.rs",
        "pow2k_lemmas.rs": base / "upstream/curve25519-dalek/src/lemmas/field_lemmas/pow2k_lemmas.rs",
    }
    rows = {}
    for key in HISTORICAL:
        file = paths[key[0]]
        content = file.read_text(encoding="utf-8").splitlines()
        if len(content) < key[1] or "by (bit_vector)" not in content[key[1] - 1]:
            raise ValueError(f"Pinned source assertion absent at {file}:{key[1]}")
        rows[key] = {"file": str(file.relative_to(root)),
                     "line": content[key[1] - 1].strip()}
    return rows


def audit(repo, generated, trace):
    native = parse_traces(trace)
    lean = parse_lean(generated)
    original = source_text(repo)
    rows = []
    for key, previous_hash in HISTORICAL.items():
        row = native[key]
        goal = lean[key]
        rows.append({
            "source": f"{key[0]}:{key[1]}",
            "pinned_source": original[key],
            "prepoly_SST_ensure_debug": row["raw"],
            "neutral_lowered_ensure_debug": row["lowered"],
            "SST_explicit_requires_count": int(row["requires"]),
            "SST_ensures_count": int(row["ensures"]),
            "generated_lean": goal,
            "historical_twin_hash": previous_hash,
            "matches_historical_hash": goal["statement_hash"] == previous_hash,
        })
    return {
        "pinned_dalek_commit": PIN,
        "stage": "Verus --no-verify -> pinned SST -> Vermilion neutral IR -> Lean generation",
        "claim": "Six provenance observations; proof validity and source-level soundness are NOT established",
        "observations": rows,
    }


def main():
    arg = argparse.ArgumentParser()
    arg.add_argument("--repo", type=Path, required=True)
    arg.add_argument("--generated", type=Path, required=True)
    arg.add_argument("--trace", type=Path, required=True)
    arg.add_argument("--output", type=Path, required=True)
    opts = arg.parse_args()
    try:
        result = audit(opts.repo.resolve(), opts.generated.resolve(), opts.trace.resolve())
        opts.output.parent.mkdir(parents=True, exist_ok=True)
        opts.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        for item in result["observations"]:
            goal = item["generated_lean"]
            print(f'{item["source"]}: literal True={goal["literal_true_goal"]}, '
                  f'matches old hash={item["matches_historical_hash"]}, '
                  f'query requires={item["SST_explicit_requires_count"]}')
        print("Six source-keyed provenance records captured; proof discharge remains OPEN.")
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(f"INCOMPLETE/FAILED provenance: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
