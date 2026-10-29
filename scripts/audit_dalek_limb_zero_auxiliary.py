#!/usr/bin/env python3
"""Strict transitive-axiom audit for a single new auxiliary theorem."""
import argparse,json,re
from pathlib import Path
NAME="layer_a.backend.serial.u64.field.impl__16.as_bytes.vermilion_limb_zero_diagnostic"
APPROVED={"Classical.choice","Quot.sound","propext"}
def check(stdout,receipt):
    pattern=re.compile(r"'(?P<name>[A-Za-z0-9_.]+)' (?:(?:depends on axioms: \[(?P<axioms>[^\]]*)\])|(?:does not depend on any axioms))")
    entries=list(pattern.finditer(stdout))
    ours=[x for x in entries if x["name"]==NAME]
    if len(ours)!=1 or len(entries)!=1:raise ValueError('missing/extra/duplicate theorem axiom receipt')
    deps=set(x.strip() for x in (ours[0]["axioms"] or "").split(",") if x.strip())
    if not deps<=APPROVED:raise ValueError('unapproved transitive axioms: '+str(sorted(deps-APPROVED)))
    if re.search(r'\b(sorry|admit|sorryAx)\b',stdout,re.I):raise ValueError('admission diagnostic')
    receipt.write_text(json.dumps({"theorem":NAME,"transitive_axioms":sorted(deps),
      "auxiliary_index_0_native_axioms_checked":True,"original_ensures_154_proven":False,
      "source_to_lean_refinement_proven":False,"whole_case_study_verified":False},sort_keys=True,indent=2)+'\n')
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument('--stdout',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True)
    a=p.parse_args();check(a.stdout.read_text(),a.receipt)
    print('LIMB_ZERO_NATIVE_AXIOM_AUDIT_PASS_NOT_ORIGINAL_VC')
