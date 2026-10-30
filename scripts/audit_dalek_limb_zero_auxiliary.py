#!/usr/bin/env python3
"""Strict transitive-axiom audit for a single new auxiliary theorem."""
import argparse,json,re
from pathlib import Path
NAME="layer_a.backend.serial.u64.field.impl__16.as_bytes.vermilion_limb_zero_diagnostic"
APPROVED={"Classical.choice","Quot.sound","propext"}
SOURCE_PIN="722ade88657f727b1e01ff1980cb95037cd8ca15c9134b757f56cd5e6b5b641c"
SPECS_PIN="96b92981ba2ebfa5803b482f0144418cf3b55b6c3c3324934c808fb594e54d7b"
ORIGINAL_HASH="7b0f306a4f86298e"
UPDATES=[[52,0],[59,1],[61,0],[66,2],[68,1],[73,3],[75,2],[80,4],[82,3],[84,4]]
def validate_native_inputs(source_receipt, lean):
    import hashlib
    meta=json.loads(source_receipt.read_text())
    for k,v in {"source_pin":SOURCE_PIN,"specs_pin":SPECS_PIN,
                "original_statement_hash":ORIGINAL_HASH,
                "pinned_updates":UPDATES,"diagnostic_only_limb":0,
                "isolated_auxiliary_native_accepted":False,
                "original_ensures_154_proven":False,
                "source_to_lean_refinement_proven":False,
                "whole_case_study_verified":False}.items():
        if meta.get(k)!=v: raise ValueError("invalid source-pinned receipt: "+k)
    content=lean.read_text()
    if len(re.findall(r"(?m)^theorem vermilion_limb_zero_diagnostic\b",content))!=1:
        raise ValueError("missing or duplicate theorem")
    if "#print axioms "+NAME not in content:
        raise ValueError("missing axiom query")
    if re.search(r"\b(sorry|admit|sorryAx)\b",content,re.I):
        raise ValueError("admitted Lean source")
    return {"lean_sha256":hashlib.sha256(lean.read_bytes()).hexdigest(),
            "pre_native_receipt_sha256":hashlib.sha256(source_receipt.read_bytes()).hexdigest()}

def check(stdout,receipt,source_receipt=None,lean=None):
    pinned = validate_native_inputs(source_receipt,lean) if source_receipt is not None and lean is not None else None
    pattern=re.compile(r"'(?P<name>[A-Za-z0-9_.]+)' (?:(?:depends on axioms: \[(?P<axioms>[^\]]*)\])|(?:does not depend on any axioms))")
    entries=list(pattern.finditer(stdout))
    ours=[x for x in entries if x["name"]==NAME]
    if len(ours)!=1 or len(entries)!=1:raise ValueError('missing/extra/duplicate theorem axiom receipt')
    deps=set(x.strip() for x in (ours[0]["axioms"] or "").split(",") if x.strip())
    if not deps<=APPROVED:raise ValueError('unapproved transitive axioms: '+str(sorted(deps-APPROVED)))
    if re.search(r'\b(sorry|admit|sorryAx)\b',stdout,re.I):raise ValueError('admission diagnostic')
    receipt.write_text(json.dumps({"theorem":NAME,"transitive_axioms":sorted(deps),
      "auxiliary_index_0_native_axioms_checked":True,"isolated_auxiliary_native_accepted":pinned is not None,
      "pinned_evidence":pinned,"original_ensures_154_proven":False,
      "source_to_lean_refinement_proven":False,"whole_case_study_verified":False},sort_keys=True,indent=2)+'\n')
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument('--stdout',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);p.add_argument('--source-receipt',type=Path,required=True);p.add_argument('--lean',type=Path,required=True)
    a=p.parse_args();check(a.stdout.read_text(),a.receipt,a.source_receipt,a.lean)
    print('LIMB_ZERO_NATIVE_AXIOM_AUDIT_PASS_NOT_ORIGINAL_VC')
