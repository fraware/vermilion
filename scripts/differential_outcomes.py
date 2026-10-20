"""Classify native proof outcomes independently of subprocess exit codes."""
from __future__ import annotations
from dataclasses import dataclass
import json
import re
from typing import Literal

Status = Literal["verified", "rejected", "infrastructure"]
_VERUS_SUMMARY = re.compile(
    r"\bverification results::\s*(\d+)\s+verified,\s*(\d+)\s+errors?\b"
)
_LOCATION = re.compile(r"(?m)^\s*-->\s+.+?:\d+:\d+(?::|\b)")
_REJECT_CODES = {"vermilion::obligation_failed", "vermilion::evidence_unresolved"}
_CRASH_MARKERS = re.compile(
    r"panicked at|internal compiler error|segmentation fault|stack overflow|"
    r"fatal runtime error|Traceback \(most recent call last\)", re.IGNORECASE
)
_RUST_ERROR_CODE = re.compile(r"(?m)^\s*error\[E\d{4}\]:")
_VERUS_INFRA_ERRORS = re.compile(
    r"(?im)^\s*error(?:\[[^]\n]+\])?:\s*(?:"
    r"unresolved import|cannot find|could not find|"
    r"failed to (?:load|compile|open|read|invoke|execute|import)|"
    r"unsupported (?:feature|syntax)|not implemented|"
    r"mismatched types|expected (?:type|identifier|expression|token)|"
    r"unknown (?:feature|attribute|type)|"
    r"cannot infer type)\b"
)
_LEAN_INFRA_ERRORS = re.compile(
    r"(?im)(?:^|\s)(?:error|fatal error):\s*(?:"
    r"cannot find module|failed to load|could not load|"
    r"unknown module|unknown constant|unknown identifier|"
    r"unexpected token|failed to compile|cannot execute|"
    r"no such file or directory|missing (?:olean|plugin|module))\b"
)

@dataclass(frozen=True)
class Outcome:
    status: Status
    reason: str

    @property
    def passed(self) -> bool:
        return self.status == "verified"


def classify_verus(returncode: int, stdout: str, stderr: str) -> Outcome:
    combined = stdout + "\n" + stderr
    if (_CRASH_MARKERS.search(combined) or _RUST_ERROR_CODE.search(combined)
            or _VERUS_INFRA_ERRORS.search(combined)):
        return Outcome("infrastructure", "Verus compiler or runtime error")
    matches = _VERUS_SUMMARY.findall(combined)
    if len(matches) != 1:
        return Outcome("infrastructure", "missing or ambiguous Verus summary")
    verified, errors = map(int, matches[0])
    if returncode == 0 and errors == 0:
        return Outcome("verified", f"{verified} verified")
    if returncode == 1 and errors > 0 and _LOCATION.search(combined):
        return Outcome("rejected", f"{errors} source-mapped verification errors")
    return Outcome("infrastructure", f"inconsistent Verus status {returncode}")


def classify_lean(returncode: int, stdout: str, stderr: str) -> Outcome:
    combined = stdout + "\n" + stderr
    if _CRASH_MARKERS.search(combined) or _LEAN_INFRA_ERRORS.search(combined):
        return Outcome("infrastructure", "Lean compiler or runtime error")
    failures = 0
    errors = 0
    for line in stdout.splitlines():
        if not line.lstrip().startswith("{"):
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            return Outcome("infrastructure", "malformed checker JSON")
        if not isinstance(message, dict):
            return Outcome("infrastructure", "non-object checker JSON")
        if message.get("$message_type") != "diagnostic" or message.get("level") != "error":
            continue
        errors += 1
        code = (message.get("code") or {}).get("code")
        spans = message.get("spans")
        obligation = (message.get("vermilion") or {}).get("obligation")
        if (code not in _REJECT_CODES or not isinstance(obligation, str)
                or not obligation or not isinstance(spans, list) or not spans
                or not any(isinstance(span, dict) and span.get("is_primary")
                           and isinstance(span.get("line_start"), int)
                           and span["line_start"] > 0 for span in spans)):
            return Outcome("infrastructure", f"unrecognized or unmapped checker error: {code}")
        failures += 1
    if returncode == 0 and errors == 0:
        return Outcome("verified", "all generated obligations accepted")
    if returncode == 1 and failures and failures == errors:
        return Outcome("rejected", f"{failures} source-mapped proof failures")
    return Outcome("infrastructure", f"inconsistent checker status {returncode}")
