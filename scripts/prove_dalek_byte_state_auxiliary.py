#!/usr/bin/env python3
"""Source-pinned auxiliary byte-state theorem. Native Lean check is separate."""
from __future__ import annotations
import argparse,hashlib,json,re
from pathlib import Path

TARGET="layer_a.backend.serial.u64.field.impl__16.as_bytes"
NAME=TARGET+".ensures_154"
STMT="7b0f306a4f86298e"
SOURCE="722ade88657f727b1e01ff1980cb95037cd8ca15c9134b757f56cd5e6b5b641c"
SPECS="96b92981ba2ebfa5803b482f0144418cf3b55b6c3c3324934c808fb594e54d7b"
ASSUMES=[89,93,97,101,105,109,115,119,123,127,131,135,141,145,149,153,157,161,165,171,175,179,183,187,191,197,201,205,209,213,217,221]
BLOCK=re.compile(r"(?ms)^-- vrml:begin (?P<name>[^\n ]+) (?P<hash>[a-f0-9]{16})\n(?P<body>.*?)^-- vrml:end (?P=name)$")
SYMB="layer_a.specs.field_specs_u64.bit_arrange limbs_ssa_10"

def param(decl,name):
    match=re.search(r"\("+re.escape(name)+r"\s*:",decl)
    if match is None: raise ValueError("missing source parameter: "+name)
    begin=match.start()
    depth=0
    for i in range(begin,len(decl)):
        depth += (decl[i]=="(")-(decl[i]==")")
        if depth==0:return decl[begin:i+1]
    raise ValueError("unbalanced original parameter: "+name)

def make(index,source,specs):
    if hashlib.sha256(source).hexdigest()!=SOURCE:raise ValueError("changed source SHA")
    if hashlib.sha256(specs).hexdigest()!=SPECS:raise ValueError("changed specs SHA")
    inventory=json.loads(index)
    if inventory.get("target_function")!=TARGET or inventory.get("obligation_count")!=156:raise ValueError("target or count mismatch")
    rows=inventory.get("obligations")
    if not isinstance(rows,list) or len(rows)!=156:raise ValueError("invalid original inventory")
    if len({r["name"] for r in rows})!=156 or any(r["module_sha256"]!=SOURCE for r in rows):raise ValueError("invalid identity or source pin")
    original=source.decode("utf-8")
    blocks=list(BLOCK.finditer(original))
    if len(blocks)!=156 or {x["name"]:x["hash"] for x in blocks}!={r["name"]:r["statement_hash"] for r in rows}:raise ValueError("changed original statement inventory")
    matches=[b for b in blocks if b["name"]==NAME and b["hash"]==STMT]
    if len(matches)!=1:raise ValueError("final VC changed")
    decl=matches[0]["body"].split(" := by\n",1)[0]
    if not decl.rstrip().endswith("layer_a.specs.core_specs.u8_32_as_nat s_ssa_32 = layer_a.specs.field_specs.fe51_as_canonical_nat self"):
        raise ValueError("final VC conclusion changed")
    names=["limbs_ssa_10"]+["s_ssa" if i==1 else f"s_ssa_{i}" for i in range(1,33)]
    assumptions=[f"assume_{n}" for n in ASSUMES]
    params=[param(decl,name) for name in names+assumptions]
    for k,p in enumerate(params[33:]):
        target="s_ssa" if k==0 else f"s_ssa_{k+1}"
        if not p.startswith(f"(assume_{ASSUMES[k]} : {target} = Vermilion.Seq.update "):raise ValueError("byte write identity or order changed")
    header=original.split("namespace "+TARGET,1)[0]
    if not header.startswith("import Vermilion.Obligations\nimport generated.field_u64.Specs\n"):raise ValueError("unexpected source imports")
    rew=", ".join(reversed(assumptions))
    proof=(f"  have hlen : Vermilion.Seq.len s_ssa_32 = 32 := by\n    simp [{rew}]\n"
           f"  have hspec : Vermilion.Seq.len ({SYMB}) = 32 := by\n    simp [layer_a.specs.field_specs_u64.bit_arrange]\n")
    for i in range(32):
        proof+=(f"  have hbyte_{i} : Vermilion.Seq.index s_ssa_32 {i} = Vermilion.Seq.index ({SYMB}) {i} := by\n"
                f"    simp [{rew}, layer_a.specs.field_specs_u64.bit_arrange] <;> omega\n")
    # IntervalCases is already imported by Vermilion.Obligations.
    # Avoid a deeply nested 32-way disjunction and repeated subst
    # elaboration, the native run 40793779763 heartbeat bottleneck.
    proof+=("  apply Vermilion.Seq.ext\n  · omega\n  · intro i hlo hhi\n"
            "    rw [hlen] at hhi\n"
            "    interval_cases i <;> assumption\n")
    fq=TARGET+".vermilion_exact_byte_state_bridge"
    # Bounded elaboration budget for one 32-case auxiliary diagnostic.
    # No change to imported axioms, original VCs, or their axiom audit.
    lean=(header+"set_option maxHeartbeats 2000000\n\n"+"namespace "+TARGET+"\n\n"
          +"theorem vermilion_exact_byte_state_bridge\n    "
          +"\n    ".join(params)+f" :\n    s_ssa_32 = {SYMB} := by\n"
          +proof+"\nend "+TARGET+"\n\n#print axioms "+fq+"\n")
    if lean.count("theorem vermilion_exact_byte_state_bridge")!=1 or re.search(r"\b(sorry|admit|sorryAx)\b",lean):
        raise ValueError("extra or admitted helper")
    receipt={"source_to_lean_refinement_proven":False,"whole_case_study_verified":False,
             "native_lean_accepted":False,"original_ensures_154_proven":False,
             "original_statement_hash":STMT,"source_module_sha256":SOURCE,"specifications_sha256":SPECS,
             "byte_write_hypotheses":32,"theorem":fq}
    return lean,receipt

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for name in ("index","module","specs","output","report"):p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args()
    result,receipt=make(a.index.read_bytes(),a.module.read_bytes(),a.specs.read_bytes())
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(result)
    a.report.write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    print("BYTE_STATE_AUXILIARY_SOURCE_PINNED_NATIVE_LEAN_PENDING")
