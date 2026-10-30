#!/usr/bin/env python3
"""Negative controls for source-pinned Lean first-limb axiom acceptance."""
import json
import tempfile
from pathlib import Path
from scripts.audit_dalek_limb_zero_auxiliary import (
    SOURCE_PIN,SPECS_PIN,ORIGINAL_HASH,UPDATES,NAME,check
)
with tempfile.TemporaryDirectory() as td:
    d=Path(td);src=d/"source.json";lean=d/"proof.lean";out=d/"out.json"
    data=dict(source_pin=SOURCE_PIN,specs_pin=SPECS_PIN,original_statement_hash=ORIGINAL_HASH,
      pinned_updates=UPDATES,diagnostic_only_limb=0,isolated_auxiliary_native_accepted=False,
      original_ensures_154_proven=False,source_to_lean_refinement_proven=False,
      whole_case_study_verified=False)
    theorem="theorem vermilion_limb_zero_diagnostic : True := by\\n  trivial\\n#print axioms "+NAME+"\\n"
    stdout="'"+NAME+"' depends on axioms: [propext, Classical.choice, Quot.sound]\\n"
    def run(meta=data,code=theorem,log=stdout):
        src.write_text(json.dumps(meta));lean.write_text(code)
        check(log,out,src,lean)
    def rejects(meta=data,code=theorem,log=stdout):
        try:run(meta,code,log)
        except ValueError:return
        raise AssertionError("forged native proof accepted")
    run();report=json.loads(out.read_text())
    assert report["isolated_auxiliary_native_accepted"] is True
    assert report["original_ensures_154_proven"] is False
    assert report["source_to_lean_refinement_proven"] is False
    rejects(log=stdout.replace("Quot.sound","sorryAx"))
    rejects(log=stdout+stdout)
    rejects(log="missing axiom report")
    rejects(log=stdout.replace("Quot.sound","unapproved.axiom"))
    rejects(code=theorem+"\\nsorry\\n")
    rejects(code=theorem.replace("#print axioms","#check"))
    rejects(meta=dict(data,source_pin="0"*64))
    rejects(meta=dict(data,specs_pin="0"*64))
    rejects(meta=dict(data,original_statement_hash="0"*16))
    rejects(meta=dict(data,pinned_updates=[]))
    rejects(meta=dict(data,isolated_auxiliary_native_accepted=True))
    rejects(meta=dict(data,original_ensures_154_proven=True))
    rejects(meta=dict(data,source_to_lean_refinement_proven=True))
print("LIMB_ZERO_AX_INPUT_NEGATIVE_CONTROLS_PASS",13)
