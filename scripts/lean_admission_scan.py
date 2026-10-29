"""Lexically detect Lean admission terms outside comments and strings.

Conservative static guard only: this is not an axiom-dependency audit.
"""
from __future__ import annotations

import re

ADMISSION_TOKEN = re.compile(r"(?<![\w'])(?:sorryAx|sorry|admit)(?![\w'])")


def redact_noncode(source: str) -> str:
    """Blank comments and strings while retaining offsets and line numbers.

    Supports nested Lean block comments and rejects malformed unterminated
    constructs rather than silently assuming that they are safe.
    """
    out = list(source)
    i = 0
    block_depth = 0
    in_string = False
    in_line = False
    n = len(source)
    while i < n:
        if in_line:
            if source[i] == "\n":
                in_line = False
            else:
                out[i] = " "
            i += 1
            continue
        if block_depth:
            if source.startswith("/-", i):
                out[i:i + 2] = [" ", " "]
                block_depth += 1
                i += 2
            elif source.startswith("-/", i):
                out[i:i + 2] = [" ", " "]
                block_depth -= 1
                i += 2
            else:
                if source[i] != "\n":
                    out[i] = " "
                i += 1
            continue
        if in_string:
            if source[i] == "\\":
                out[i] = " "
                i += 1
                if i < n:
                    if source[i] != "\n":
                        out[i] = " "
                    i += 1
            elif source[i] == '"':
                out[i] = " "
                in_string = False
                i += 1
            else:
                if source[i] != "\n":
                    out[i] = " "
                i += 1
            continue
        if source.startswith("--", i):
            out[i:i + 2] = [" ", " "]
            in_line = True
            i += 2
        elif source.startswith("/-", i):
            out[i:i + 2] = [" ", " "]
            block_depth = 1
            i += 2
        elif source[i] == '"':
            out[i] = " "
            in_string = True
            i += 1
        else:
            i += 1
    if block_depth or in_string:
        raise ValueError("unterminated Lean comment or string literal")
    return "".join(out)


def admission_positions(source: str) -> list[tuple[int, str]]:
    """Return 1-based source lines and disallowed admission identifiers."""
    code = redact_noncode(source)
    return [(source.count("\n", 0, m.start()) + 1, m.group())
            for m in ADMISSION_TOKEN.finditer(code)]
