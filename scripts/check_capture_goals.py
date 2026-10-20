#!/usr/bin/env python3
"""Fixture-specific guard against vacuous quantified Lean statements."""
import json
import re
import sys
from pathlib import Path

CASES = (
    ("c_hygiene_01_ret_param", "ret_param", "forall", "<"),
    ("c_hygiene_03_ret_param_exists", "ret_param_exists", "exists", "="),
    ("c_hygiene_04_call_param", "call_param", "forall", "<"),
    ("c_hygiene_05_assert_alias", "assert_alias", "forall", "<"),
    ("c_hygiene_06_bounded", "bounded", "forall", "<"),
)

def inspect(root: Path) -> list[str]:
    errors = []
    root = root.resolve()
    for stem, function, quantifier, relation in CASES:
        path = root / "tests/differential/generated" / f"{stem}.json"
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            if manifest.get("refused") or manifest.get("refusals"):
                raise ValueError("unsupported lowering, not a proof result")
            obligations = manifest["obligations"]
            matches = [rec for rec in obligations
                       if isinstance(rec, dict)
                       and re.search(rf"(?<![A-Za-z_0-9]){re.escape(function)}(?![A-Za-z_0-9])",
                                     str(rec.get("name", "")))]
            if not matches:
                raise ValueError(f"no obligation found for {function}")
            found = False
            for rec in matches:
                name, statement_hash, filename = (
                    rec["name"], rec["statement_hash"], rec["lean_file"]
                )
                if not all(isinstance(x, str) and x for x in (name, statement_hash, filename)):
                    raise ValueError("invalid obligation metadata")
                file = (root / filename).resolve()
                if not file.is_relative_to(root) or not file.is_file():
                    raise ValueError(f"missing or escaping Lean source: {filename}")
                lean = file.read_text(encoding="utf-8")
                block = re.search(
                    rf"(?ms)^-- vrml:begin {re.escape(name)} {re.escape(statement_hash)}\s*$\n"
                    rf"(.*?)^-- vrml:end {re.escape(name)}\s*$", lean
                )
                if block is None:
                    raise ValueError(f"statement/hash binding missing: {name}")
                body = block.group(1)
                symbol = "∀" if quantifier == "forall" else "∃"
                if not re.search(rf"{symbol}\s*\(i_vrml_\d+\s*:\s*Int\)", body):
                    continue
                if not re.search(r"i_vrml_\d+\s*" + re.escape(relation) + r"\s*i\b", body):
                    continue
                if re.search(r"\bi\s*(?:<|=)\s*i\b", body):
                    raise ValueError("self-captured outer symbol")
                found = True
            if not found:
                raise ValueError(f"noncapturing {quantifier} relation not found")
        except (OSError, KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
            errors.append(f"{stem}: {exc}")
    return errors

if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) == 2 else Path.cwd()
    errors = inspect(root)
    for e in errors:
        print(e, file=sys.stderr)
    if errors:
        sys.exit(1)
    print("capture goals preserve distinct bound and outer variables")
