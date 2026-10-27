#!/usr/bin/env python3
"""Independent structural audit of archived experimental indexed-SSA Lean VCs.

The checks establish provenance, binding order, and the syntactic SSA update
chain. They do not establish semantic refinement or Lean proof discharge.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

BEGIN = re.compile(r'^-- vrml:begin ([^ ]+) ([a-f0-9]{16})$', re.M)
END = re.compile(r'^-- vrml:end ([^\n]+)$', re.M)
BINDER = re.compile(r'^    \(([A-Za-z_][A-Za-z0-9_]*) : \(Vermilion\.Seq Int\)\)$')
EQUATION = re.compile(r'^    \(assume_([0-9]+) : ([A-Za-z_][A-Za-z0-9_]*) = (Vermilion\.Seq\.update .*)\)(?: :)?$')


def audit(index_path: Path, receipt_path: Path, modules_root: Path) -> dict:
    idx = json.loads(index_path.read_text())
    rec = json.loads(receipt_path.read_text())
    target = idx['target_function']
    items = idx['obligations']
    names = rec['binders']
    assert idx['obligation_count'] == len(items) == 156
    assert rec['executed_equations'] == rec['unique_binders'] == len(names) == len(set(names)) == 42
    assert len(set(x['name'] for x in items)) == len(items)
    assert all(x['name'].startswith(target+'.') for x in items)
    assert len(set(x['module'] for x in items)) == idx['module_count'] == 1
    assert all(re.fullmatch(r'[a-f0-9]{16}', x['statement_hash']) for x in items)
    module = next(iter(x['module'] for x in items))
    p = (modules_root / module).resolve()
    assert p.is_relative_to(modules_root.resolve()), 'Module escapes root'
    data = p.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    assert all(x['module_sha256'] == digest for x in items), 'Module hash mismatch'
    lines = data.decode('utf-8').splitlines()
    blocks = {}
    current = None
    for line in lines:
        match = BEGIN.fullmatch(line)
        if match:
            assert current is None, ('nested obligation', match.group(1))
            key, h = match.groups()
            assert key not in blocks
            current = {'name': key, 'hash': h, 'body': []}
        if current is not None:
            current['body'].append(line)
        end = END.fullmatch(line)
        if end:
            assert current is not None and end.group(1) == current['name']
            assert any('@[vrml_obligation] theorem ' in x for x in current['body'])
            blocks[current['name']] = current
            current = None
    assert current is None, 'Unclosed obligation'
    assert set(blocks) == set(x['name'] for x in items), 'Unindexed/absent blocks'
    assert all(blocks[x['name']]['hash'] == x['statement_hash'] for x in items), 'Statement hash mismatch'

    name_set = set(names)
    token = re.compile(r'(?<![A-Za-z0-9_])(?:' + '|'.join(re.escape(x) for x in sorted(names, key=len, reverse=True)) + r')(?![A-Za-z0-9_])')
    full = []
    for key, block in blocks.items():
        body = block['body']
        declaration = []
        equations = []
        for pos, line in enumerate(body):
            m = BINDER.fullmatch(line)
            if m and m.group(1) in name_set:
                declaration.append((pos, m.group(1)))
            e = EQUATION.fullmatch(line)
            if e and e.group(2) in name_set:
                equations.append((pos, e.group(2), e.group(3)))
        declared = [name for _, name in declaration]
        defined = [name for _, name, _ in equations]
        assert len(declared) == len(set(declared)), (key, 'duplicate SSA binder')
        assert len(defined) == len(set(defined)), (key, 'duplicate SSA equation')
        assert declared == defined, (key, 'missing/unpaired SSA equation', declared, defined)
        assert declared == [n for n in names if n in set(declared)], (key, 'SSA binder order drift')
        source = '\n'.join(body)
        referred = set(token.findall(source))
        assert referred == set(declared), (key, 'unbound SSA name', sorted(referred - set(declared)))
        prior = set()
        for (d_pos, name), (e_pos, eq_name, rhs) in zip(declaration, equations):
            assert name == eq_name and d_pos < e_pos, (key, 'equation without earlier binder', name)
            assert rhs.startswith('Vermilion.Seq.update '), (key, 'not a sequence update', name)
            uses = set(token.findall(rhs))
            assert uses.issubset(prior), (key, 'self/forward reference', name, sorted(uses-prior))
            prior.add(name)
        if len(declared) == len(names):
            full.append(key)
    assert full, 'No complete indexed SSA chain in emitted VCs'
    assert any(k.endswith('.ensures_154') for k in full), 'Final postcondition lacks complete chain'
    final = blocks[target+'.ensures_154']['body']
    eqs = [EQUATION.fullmatch(x) for x in final]
    eqs = [x for x in eqs if x and x.group(2) in name_set]
    assert [x.group(2) for x in eqs] == names, 'Receipt differs from emitted complete chain'
    limbs = [x for x in eqs if x.group(2).startswith('limbs_ssa')]
    bytes_ = [x for x in eqs if x.group(2).startswith('s_ssa')]
    assert len(limbs) == 10 and len(bytes_) == 32
    assert bytes_[0].group(3).startswith('Vermilion.Seq.update (Vermilion.Seq.fill 32 0) 0 '), 'Initial byte array mismatch'
    for i, e in enumerate(bytes_):
        rhs = e.group(3)
        assert i == 0 or rhs.startswith(f'Vermilion.Seq.update {bytes_[i-1].group(2)} {i} '), ('byte predecessor changed', i)
        assert '% 256' in rhs, ('byte narrowing absent', i)
    assert any('u8_32_as_nat s_ssa_32 =' in line for line in final), 'Final state absent from equality goal'
    return {
        'target_function': target, 'module': module, 'module_sha256': digest,
        'obligations': len(items), 'executed_indexed_ssa_updates': len(names),
        'limb_updates': len(limbs), 'byte_updates': len(bytes_),
        'all_obligations_have_paired_in_scope_ssa_equations': True,
        'all_rhs_use_only_preceding_ssa_names': True,
        'all_obligation_markers_match_source_keyed_index': True,
        'all_32_byte_indices_in_order': True,
        'last_postcondition_references_final_ssa_state': True,
        'complete_chain_obligations': len(full),
        'whole_case_study_proven': False,
        'translation_soundness_proven': False
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--index', type=Path, required=True)
    ap.add_argument('--receipt', type=Path, required=True)
    ap.add_argument('--modules', type=Path, required=True)
    ap.add_argument('--output', type=Path)
    args = ap.parse_args()
    report = audit(args.index, args.receipt, args.modules)
    content = json.dumps(report, indent=2, sort_keys=True)+'\n'
    if args.output:
        args.output.write_text(content)
    print(content)


if __name__ == '__main__':
    main()
