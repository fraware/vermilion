"""Verify proof twins retain exactly the generated VC statements.

This checks declared theorem text, statement hashes, and complete coverage;
it supplements, but does not replace, kernel checking or transitive axiom audit.
"""
from __future__ import annotations

from pathlib import Path
import re

from vrml_external import ContractError

BEGIN = re.compile(r"^-- vrml:begin (\S+) (\S+)$")
END = re.compile(r"^-- vrml:end (\S+)$")
DECL = re.compile(r"(?m)^@\[vrml_(?:obligation|evidence)\]")
UNSAFE = re.compile(r"\b(?:sorry|admit|sorryAx|axiom|constant)\b")


def strip_comments(source: str) -> str:
    """Conservative lexical filter for Lean nested block and line comments."""
    result = []
    offset = 0
    level = 0
    while offset < len(source):
        if level:
            if source.startswith("/-", offset):
                level += 1
                offset += 2
            elif source.startswith("-/", offset):
                level -= 1
                offset += 2
            else:
                if source[offset] == "\n":
                    result.append("\n")
                offset += 1
        elif source.startswith("/-", offset):
            level += 1
            offset += 2
        elif source.startswith("--", offset):
            nextline = source.find("\n", offset)
            if nextline < 0:
                break
            offset = nextline
        elif source[offset] == '"':
            # Exclude strings from proof-hole keyword scanning.
            offset += 1
            while offset < len(source):
                if source[offset] == "\\":
                    offset += 2
                elif source[offset] == '"':
                    offset += 1
                    break
                else:
                    offset += 1
            result.append('""')
        else:
            result.append(source[offset])
            offset += 1
    if level:
        raise ContractError("unclosed Lean block comment")
    return "".join(result)


def markers(source: str, file: Path) -> dict[str, tuple[str, str]]:
    """Map each obligation name to its hash and literal theorem declaration."""
    found: dict[str, tuple[str, str]] = {}
    current: tuple[str, str, list[str]] | None = None
    for line in source.splitlines():
        begin = BEGIN.fullmatch(line)
        end = END.fullmatch(line)
        if begin:
            if current is not None or begin.group(1) in found:
                raise ContractError(f"duplicate/nested VC marker in {file}")
            current = (begin.group(1), begin.group(2), [])
        elif end:
            if current is None or current[0] != end.group(1):
                raise ContractError(f"unmatched VC marker in {file}")
            name, digest, lines = current
            block = "\n".join(lines)
            decl = list(DECL.finditer(block))
            if len(decl) != 1:
                raise ContractError(f"expected one theorem declaration for {name}")
            declaration = block[decl[0].start():].splitlines()
            ends = [i for i, row in enumerate(declaration)
                    if row.rstrip().endswith(":= by")]
            if len(ends) != 1:
                raise ContractError(f"ambiguous theorem signature for {name}")
            signature = "\n".join(declaration[:ends[0]+1])
            found[name] = (digest, signature)
            current = None
        elif current is not None:
            current[2].append(line)
    if current is not None:
        raise ContractError(f"unterminated VC marker in {file}")
    return found


def verify_bindings(root: Path, manifest: dict) -> None:
    if not manifest.get("obligations"):
        raise ContractError("no proof obligations to bind")
    expected = {}
    generated = {}
    proofs = {}
    seen_paths: set[tuple[Path, Path]] = set()
    for item in manifest["obligations"]:
        name, digest = item.get("name"), item.get("statement_hash")
        if not isinstance(name, str) or not isinstance(digest, str) or not digest:
            raise ContractError("manifest has malformed obligation identity")
        if name in expected:
            raise ContractError(f"duplicate manifest obligation: {name}")
        expected[name] = digest
        rel = item.get("lean_file", manifest.get("lean_file", ""))
        if not isinstance(rel, str) or not rel or Path(rel).is_absolute():
            raise ContractError(f"unsafe generated obligation path for {name}")
        parts = list(Path(rel).parts)
        if parts.count("generated") != 1:
            raise ContractError(f"obligation does not belong to a generated root: {rel}")
        twin_parts = parts.copy()
        twin_parts[twin_parts.index("generated")] = "proofs"
        file = (root / rel).resolve()
        twin = (root / Path(*twin_parts)).resolve()
        if not file.is_relative_to(root) or not twin.is_relative_to(root):
            raise ContractError("VC path escapes the project")
        if file.is_symlink() or twin.is_symlink() or not file.is_file() or not twin.is_file():
            raise ContractError(f"missing/unsafe generated or proof file for {name}")
        seen_paths.add((file, twin))
    for file, twin in seen_paths:
        new = markers(file.read_text(encoding="utf-8"), file)
        old = markers(twin.read_text(encoding="utf-8"), twin)
        violation = UNSAFE.search(strip_comments(twin.read_text(encoding="utf-8")))
        if violation:
            raise ContractError(f"unresolved proof hole or unchecked declaration: {violation.group()}")
        for name, data in new.items():
            if name in generated:
                raise ContractError(f"duplicate generated theorem: {name}")
            generated[name] = data
        for name, data in old.items():
            if name in proofs:
                raise ContractError(f"duplicate twin theorem: {name}")
            proofs[name] = data
    if set(expected) != set(generated) or set(expected) != set(proofs):
        raise ContractError("proof/generated obligation coverage differs from manifest")
    for name, digest in expected.items():
        if generated[name][0] != digest or proofs[name][0] != digest:
            raise ContractError(f"stale or fabricated proof statement hash for {name}")
        if generated[name][1] != proofs[name][1]:
            raise ContractError(f"proof theorem statement changed for {name}")
