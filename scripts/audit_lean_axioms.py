#!/usr/bin/env python3
"""Use Lean's transitive axiom collector to audit a complete proof unit.

The source module is preserved. A temporary audit copy appends a Lean command
checking every expected obligation theorem and its transitive axioms.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import tempfile

DECL = re.compile(r"[A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*")


def make_audit_source(source: str, names: list[str]) -> str:
    if not names or len(set(names)) != len(names):
        raise ValueError("empty or duplicate axiom-audit declarations")
    if any(DECL.fullmatch(n) is None for n in names):
        raise ValueError("invalid Lean declaration name")
    literals = ", ".join(chr(96) + n for n in names)
    auditor = """
open Lean Elab Command
run_cmd do
  let names : Array Lean.Name := #[%s]
  for n in names do
    let env ← getEnv
    match env.find? n with
    | some (.thmInfo _) => pure ()
    | some _ => throwError m!"VRML_AXIOM_AUDIT_NOT_THEOREM {n}"
    | none => throwError m!"VRML_AXIOM_AUDIT_MISSING {n}"
    let axioms ← Lean.collectAxioms n
    for ax in axioms do
      unless ax == `propext || ax == `Classical.choice || ax == `Quot.sound do
        throwError m!"VRML_AXIOM_AUDIT_FORBIDDEN {n}: {ax}"
  logInfo m!"VRML_AXIOM_AUDIT_PASS {names.size}"
""" % literals
    return "import Lean\n" + source.rstrip() + "\n" + auditor


def audit_proof_unit(
    unit: Path, declarations: list[str], *, lean: str = "lean", timeout: int = 600
) -> tuple[bool, str]:
    try:
        audited = make_audit_source(unit.read_text(encoding="utf-8"), declarations)
        with tempfile.TemporaryDirectory(prefix="vrml-axiom-audit-") as directory:
            copy = Path(directory) / "Audit.lean"
            copy.write_text(audited, encoding="utf-8")
            outcome = subprocess.run(
                [lean, str(copy)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=timeout, check=False, env=os.environ.copy(),
            )
        if outcome.returncode != 0:
            return False, (f"axiom audit rejected {unit} (exit {outcome.returncode}): "
                           f"{outcome.stdout[-2000:]} {outcome.stderr[-800:]}")
        marker = f"VRML_AXIOM_AUDIT_PASS {len(declarations)}"
        if outcome.stdout.count(marker) != 1 or outcome.stderr.strip():
            return False, f"axiom audit missing or ambiguous receipt for {unit}"
        return True, marker
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        return False, f"axiom audit unavailable for {unit}: {error}"
