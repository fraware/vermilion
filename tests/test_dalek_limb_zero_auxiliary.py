#!/usr/bin/env python3
"""Fail-closed source mutation tests against exact native-generated original."""
import argparse,copy,importlib.util,json
from pathlib import Path

def main(module,index,module_lean,specs):
    spec=importlib.util.spec_from_file_location('limb_first',str(module.resolve()))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    raw=index.read_bytes();src=module_lean.read_bytes();sp=specs.read_bytes()
    def reject(i=raw,s=src,t=sp):
        try:m.generate(i,s,t)
        except (ValueError,KeyError,UnicodeDecodeError,TypeError):return
        raise AssertionError('tampered source accepted')
    lean,report=m.generate(raw,src,sp)
    assert 'theorem vermilion_limb_zero_diagnostic' in lean
    assert report['original_ensures_154_proven'] is False
    assert report['source_to_lean_refinement_proven'] is False
    assert len(report['pinned_updates'])==10
    assert "have masked_mod (x : Int)" in lean
    assert "Vermilion.Bits.band_nonneg 64 x 2251799813685247" in lean
    assert "Vermilion.Bits.band_lt 64 x 2251799813685247" in lean
    assert "have hlen" not in lean
    assert "have hreduce : tmp_.1 = layer_a.specs.field_specs_u64.spec_reduce self.1" in lean
    assert "exact call_reduce_ensures_2" in lean
    assert "[hreduce, " in lean
    count=1
    assert m.generate(raw,src,sp)==(lean,report);count+=1
    reject(s=src+b' ');count+=1
    reject(t=sp+b' ');count+=1
    original=json.loads(raw)
    for key,v in [('target_function','different'),('obligation_count',155)]:
        x=copy.deepcopy(original);x[key]=v;reject(i=json.dumps(x).encode());count+=1
    x=copy.deepcopy(original);x['obligations'][0]['name']=x['obligations'][1]['name']
    reject(i=json.dumps(x).encode());count+=1
    x=copy.deepcopy(original);x['obligations'][0]['module_sha256']='0'*64
    reject(i=json.dumps(x).encode());count+=1
    x=copy.deepcopy(original);next(r for r in x['obligations'] if r['name'].endswith('ensures_154'))['statement_hash']='0'*16
    reject(i=json.dumps(x).encode());count+=1
    x=copy.deepcopy(original);x['obligations'].pop()
    reject(i=json.dumps(x).encode());count+=1
    assert count==10
    print('FIRST_LIMB_SOURCE_CONTROLS_PASS',count,'NATIVE_PROOF_STILL_REQUIRED')
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ('module','index','module-lean','specs'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();main(a.module,a.index,a.module_lean,a.specs)
