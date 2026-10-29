#!/usr/bin/env python3
"""Fail-closed source mutation controls for the uncredited final byte-state helper."""
import argparse,copy,importlib.util,json
from pathlib import Path

def main(index,module,specs):
    spec=importlib.util.spec_from_file_location(
        "byte_auxiliary",str(Path("scripts/prove_dalek_byte_state_auxiliary.py").resolve()))
    if spec is None or spec.loader is None:raise ValueError("generator unavailable")
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    raw=index.read_bytes();src=module.read_bytes();definitions=specs.read_bytes()
    def reject(i,s,t):
        try:m.make(i,s,t)
        except (ValueError,KeyError,TypeError,UnicodeDecodeError):return
        raise AssertionError("mutated source / inventory unexpectedly accepted")
    generated,receipt=m.make(raw,src,definitions)
    assert generated.count("  have hbyte_")==32
    assert receipt["native_lean_accepted"] is False
    assert receipt["original_ensures_154_proven"] is False
    assert generated.count("#print axioms")==1
    count=1
    assert m.make(raw,src,definitions)==(generated,receipt);count+=1
    reject(raw,src+b"\n",definitions);count+=1
    reject(raw,src,definitions+b"\n");count+=1
    doc=json.loads(raw)
    mutated=copy.deepcopy(doc);mutated["obligations"][1]["name"]=mutated["obligations"][0]["name"]
    reject(json.dumps(mutated).encode(),src,definitions);count+=1
    mutated=copy.deepcopy(doc);next(row for row in mutated["obligations"] if row["name"].endswith(".ensures_154"))["statement_hash"]="0"*16
    reject(json.dumps(mutated).encode(),src,definitions);count+=1
    mutated=copy.deepcopy(doc);mutated["obligations"][0]["statement_hash"]="0"*16
    reject(json.dumps(mutated).encode(),src,definitions);count+=1
    mutated=copy.deepcopy(doc);mutated["obligations"].pop()
    reject(json.dumps(mutated).encode(),src,definitions);count+=1
    mutated=copy.deepcopy(doc);mutated["obligations"][0]["module_sha256"]="0"*64
    reject(json.dumps(mutated).encode(),src,definitions);count+=1
    mutated=copy.deepcopy(doc);mutated["target_function"]="changed"
    reject(json.dumps(mutated).encode(),src,definitions);count+=1
    assert count==10
    print("FINAL_BYTE_STATE_AUXILIARY_SOURCE_CONTROLS_PASSED",count,
          "native theorem acceptance separately required")

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for key in ("index","module","specs"):p.add_argument("--"+key,type=Path,required=True)
    a=p.parse_args();main(a.index,a.module,a.specs)
