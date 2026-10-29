#!/usr/bin/env python3
"""Exact-source pinned first-limb final-serialization diagnostic; uncredited."""
import argparse, hashlib, json, re
from pathlib import Path

TARGET='layer_a.backend.serial.u64.field.impl__16.as_bytes'
NAME=TARGET+'.ensures_154'
HASH='7b0f306a4f86298e'
PIN='722ade88657f727b1e01ff1980cb95037cd8ca15c9134b757f56cd5e6b5b641c'
SPEC_PIN='96b92981ba2ebfa5803b482f0144418cf3b55b6c3c3324934c808fb594e54d7b'
ASSUMES=[52,59,61,66,68,73,75,80,82,84]
INDICES=[0,1,0,2,1,3,2,4,3,4]
BLOCK=re.compile(r'(?ms)^-- vrml:begin (?P<name>[^\n ]+) (?P<hash>[a-f0-9]{16})\n(?P<body>.*?)^-- vrml:end (?P=name)$')

def param(decl,name):
    m=re.search(r'\('+re.escape(name)+r'\s*:',decl)
    if not m:raise ValueError('original hypothesis absent: '+name)
    depth=0
    for i in range(m.start(),len(decl)):
        depth+=(decl[i]=='(')-(decl[i]==')')
        if depth==0:return decl[m.start():i+1]
    raise ValueError('unbalanced original hypothesis: '+name)

def generate(index_bytes,source_bytes,spec_bytes):
    if hashlib.sha256(source_bytes).hexdigest()!=PIN:raise ValueError('source pin mismatch')
    if hashlib.sha256(spec_bytes).hexdigest()!=SPEC_PIN:raise ValueError('specification pin mismatch')
    inventory=json.loads(index_bytes)
    rows=inventory.get('obligations',[])
    if inventory.get('target_function')!=TARGET or inventory.get('obligation_count')!=156 or len(rows)!=156 or len({r['name'] for r in rows})!=156:
        raise ValueError('source-keyed VC inventory mismatch')
    if any(r['module_sha256']!=PIN for r in rows):raise ValueError('module pin mismatch')
    original=source_bytes.decode('utf-8')
    blocks=list(BLOCK.finditer(original))
    if len(blocks)!=156 or {b['name']:b['hash'] for b in blocks}!={r['name']:r['statement_hash'] for r in rows}:
        raise ValueError('source statement identity/hash mismatch')
    match=[b for b in blocks if b['name']==NAME and b['hash']==HASH]
    if len(match)!=1:raise ValueError('missing exact original ensures_154')
    decl=match[0]['body'].split(' := by\n',1)[0]
    if not decl.endswith('layer_a.specs.core_specs.u8_32_as_nat s_ssa_32 = layer_a.specs.field_specs.fe51_as_canonical_nat self'):
        raise ValueError('final original statement conclusion changed')
    names=['self','tmp_']+['limbs_ssa']+[f'limbs_ssa_{i}' for i in range(2,11)]+['call_reduce_ensures_0','call_reduce_ensures_2']+[f'assume_{n}' for n in ASSUMES]
    args=[param(decl,n) for n in names]
    for n,i in zip(ASSUMES,INDICES):
        if not re.search(r'\= Vermilion\.Seq\.update .* '+str(i)+r' ',param(decl,f'assume_{n}')):
            raise ValueError(f'changed original update {n}')
    src='layer_a.backend.serial.u64.field.FieldElement51.get_FieldElement51_limbs self'
    reduced=f'layer_a.specs.field_specs_u64.spec_reduce ({src})'
    target=f'layer_a.specs.field_specs_u64.reduce_with_q_spec ({reduced}) (layer_a.specs.field_specs_u64.compute_q_spec ({reduced}))'
    goal=f'Vermilion.Seq.index limbs_ssa_10 0 = Vermilion.Seq.index ({target}) 0'
    writes=', '.join('assume_'+str(n) for n in reversed(ASSUMES))
    proof=f'''  have hlen : Vermilion.Seq.len limbs_ssa_10 = 5 := by
    simp [{writes}, call_reduce_ensures_0]
  simp (disch := omega) [←call_reduce_ensures_2, {writes},
    layer_a.specs.field_specs_u64.reduce_with_q_spec,
    layer_a.specs.field_specs_u64.compute_unmasked_limbs,
    layer_a.specs.field_specs_u64.compute_q_spec,
    layer_a.specs.field_specs_u64.compute_q_arr,
    layer_a.specs.field_specs_u64.mask51, Vermilion.Bits.shl] <;> omega
'''
    header=original.split('namespace '+TARGET,1)[0]
    if not header.startswith('import Vermilion.Obligations\nimport generated.field_u64.Specs\n'):
        raise ValueError('source Lean imports changed')
    lean=(header+'set_option maxHeartbeats 5000000\nnamespace '+TARGET+'\n\n'
          +'theorem vermilion_limb_zero_diagnostic\n    '+'\n    '.join(args)+' :\n    '+goal+' := by\n'+proof
          +'\nend '+TARGET+'\n\n#print axioms '+TARGET+'.vermilion_limb_zero_diagnostic\n')
    if len(re.findall(r'(?m)^theorem ',lean))!=1 or re.search(r'\b(sorry|admit|sorryAx)\b',lean):
        raise ValueError('admission or extra theorem')
    receipt={'source_pin':PIN,'specs_pin':SPEC_PIN,'original_statement_hash':HASH,
      'original_ensures_154_proven':False,'source_to_lean_refinement_proven':False,
      'whole_case_study_verified':False,'isolated_auxiliary_native_accepted':False,
      'diagnostic_only_limb':0,'pinned_updates':list(zip(ASSUMES,INDICES))}
    return lean,receipt

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ('index','module','specs','output','receipt'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args()
    lean,receipt=generate(a.index.read_bytes(),a.module.read_bytes(),a.specs.read_bytes())
    a.output.parent.mkdir(parents=True,exist_ok=True);a.receipt.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(lean);a.receipt.write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    print('FIRST_LIMB_SOURCE_PINNED_NATIVE_LEAN_CANDIDATE_NOT_YET_ACCEPTED')
