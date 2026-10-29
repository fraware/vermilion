#!/usr/bin/env python3
"""Check exact native axiom report for an auxiliary (not original VC) theorem."""
import argparse,json,re
from pathlib import Path
NAME="layer_a.backend.serial.u64.field.impl__16.as_bytes.vermilion_exact_byte_state_bridge"
APPROVED={"Quot.sound","propext","Classical.choice"}
def check(stdout,receipt):
    pattern=re.compile(r"'(?P<name>[A-Za-z0-9_.]+)' (?:(?:depends on axioms: \[(?P<axioms>[^\]]*)\])|(?:does not depend on any axioms))")
    entries=list(pattern.finditer(stdout))
    ours=[m for m in entries if m["name"]==NAME]
    if len(ours)!=1 or len(entries)!=1:raise ValueError("missing, duplicate, or extra auxiliary proof axiom report")
    deps=set(x.strip() for x in (ours[0]["axioms"] or "").split(",") if x.strip())
    if not deps<=APPROVED:raise ValueError("unapproved auxiliary imported axioms: "+repr(sorted(deps-APPROVED)))
    if re.search(r"\b(sorryAx|sorry|admit)\b",stdout,re.I):raise ValueError("admission-related diagnostics in native output")
    receipt.write_text(json.dumps({"auxiliary_byte_state_proof_native_axioms_checked":True,
      "original_ensures_154_proven":False,"source_to_lean_refinement_proven":False,
      "whole_case_study_verified":False,"theorem":NAME,"transitive_axioms":sorted(deps)},sort_keys=True,indent=2)+"\n")
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--stdout",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True)
    a=p.parse_args();check(a.stdout.read_text(),a.receipt)
    print("AUXILIARY_BYTE_STATE_NATIVE_AXIOM_AUDIT_PASSED_NO_ORIGINAL_VC_CREDIT")
