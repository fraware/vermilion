#!/usr/bin/env python3
"""Generate 87 exact source-keyed sequence-index proof candidates.

This preserves each generated theorem declaration and its hypothesis telescope
verbatim. Proof candidates are not certified until separately elaborated and
kernel-checked by the pinned native CI. No SMT or admitted results are used.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

BLOCK = re.compile(r'(?ms)^-- vrml:begin (?P<name>[^\n ]+) (?P<hash>[0-9a-f]{16})\n(?P<body>.*?)^-- vrml:end (?P=name)$')
GOAL = re.compile(r'^\(0 ≤ (?P<index>[0-9]+)\) ∧ \((?P=index) < Vermilion\.Seq\.len (?P<seq>.+)\)$')
STATE = re.compile(r'^(limbs_ssa(?:_\d+)?|s_ssa(?:_\d+)?)$')
EQUATION = re.compile(r'^    \((assume_[0-9]+) : (?P<name>(?:limbs|s)_ssa(?:_[0-9]+)?) = Vermilion\.Seq\.update (?P<rest>.+)$', re.M)
TARGET = 'layer_a.backend.serial.u64.field.impl__16.as_bytes'
TMP = '(layer_a.backend.serial.u64.field.FieldElement51.get_FieldElement51_limbs tmp_)'
FILL = '(Vermilion.Seq.fill 32 0)'

def build(index_path: Path, root: Path, output: Path, report_path: Path) -> dict:
    index = json.loads(index_path.read_text())
    assert index['target_function'] == TARGET
    assert len(index['obligations']) == index['obligation_count'] == 156
    paths = {r['module'] for r in index['obligations']}
    assert len(paths) == 1
    path = (root / next(iter(paths))).resolve()
    assert path.is_relative_to(root.resolve())
    src_bytes = path.read_bytes()
    digest = hashlib.sha256(src_bytes).hexdigest()
    assert all(r['module_sha256'] == digest for r in index['obligations'])
    src = src_bytes.decode()
    known = {x['name']: x['statement_hash'] for x in index['obligations']}
    all_blocks = list(BLOCK.finditer(src))
    assert len(all_blocks) == 156
    assert set(known) == {m.group('name') for m in all_blocks}
    results = []
    audit = []
    groups = {'tmp': 0, 'fill': 0, 'limbs': 0, 'bytes': 0}
    for m in all_blocks:
        name, sha, content = m.group('name'), m.group('hash'), m.group('body')
        assert known[name] == sha
        assert ' := by\n' in content
        decl, _ = content.split(' := by\n', 1)
        goal = decl.rsplit(' :\n', 1)[-1].strip()
        gm = GOAL.fullmatch(goal)
        if not gm:
            continue
        num = int(gm.group('index'))
        seq = gm.group('seq')
        assert f'@[vrml_obligation] theorem {name.rsplit(".", 1)[-1]}' in decl
        assert 0 <= num <= 31
        statements = {x.group('name'): (x.group(1), x.group('rest'))
                      for x in EQUATION.finditer(decl)}
        lines = []
        if seq == TMP:
            assert num < 5 and 'call_reduce_ensures_0' in decl
            lines = ['  omega']
            group = 'tmp'
        elif seq == FILL:
            assert num < 32 and 'assume_85' in decl
            lines = ['  omega']
            group = 'fill'
        elif STATE.fullmatch(seq):
            root_name = seq.split('_ssa')[0]
            width = 5 if root_name == 'limbs' else 32
            assert num < width
            chain = []
            curr = seq
            while curr in statements:
                assumption, rhs = statements[curr]
                if rhs.startswith(TMP + ' '):
                    assert curr == 'limbs_ssa'
                    prev = TMP
                elif rhs.startswith(FILL + ' '):
                    assert curr == 's_ssa'
                    prev = FILL
                else:
                    prev = rhs.split(' ', 1)[0]
                    assert STATE.fullmatch(prev) and prev != curr, (name, curr, prev)
                chain.append((curr, assumption, prev))
                curr = prev
            assert curr in [TMP, FILL], (name, curr)
            assert 1 <= len(chain) < 33
            assert ('call_reduce_ensures_0' if curr == TMP else 'assume_85') in decl
            chain.reverse()
            for state, assumption, prev in chain:
                previous = ('call_reduce_ensures_0' if prev == TMP else
                            'assume_85' if prev == FILL else 'hlen_' + prev)
                lines += [
                    f'  have hlen_{state} : Vermilion.Seq.len {state} = {width} := by',
                    '    calc',
                    f'      Vermilion.Seq.len {state} = Vermilion.Seq.len {prev} := by rw [{assumption}, Vermilion.Seq.len_update]',
                    f'      _ = {width} := {previous}',
                ]
            lines.append('  omega')
            group = 'limbs' if root_name == 'limbs' else 'bytes'
        else:
            raise AssertionError(('unexpected index goal', name, goal))
        groups[group] += 1
        results.append(f'-- vrml:begin {name} {sha}\n' +
                       decl + ' := by\n' + '\n'.join(lines) + '\n' +
                       f'-- vrml:end {name}\n')
        audit.append({'name': name, 'hash': sha, 'source': seq,
                      'index': num, 'kind': group, 'proof_lines': len(lines)})
    assert len(results) == 87, groups
    assert groups == {'tmp': 6, 'fill': 1, 'limbs': 49, 'bytes': 31}, groups
    header = src.split('namespace ' + TARGET, 1)[0]
    assert header.startswith('import Vermilion.Obligations\nimport generated.field_u64.Specs\n')
    lean = header + 'namespace ' + TARGET + '\n\n' + '\n'.join(results) + '\nend ' + TARGET + '\n'
    assert lean.count('@[vrml_obligation] theorem ') == 87
    assert not re.search(r'\b(sorry|admit)\b', lean)
    output.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(lean)
    summary = {
        'source_module_sha256': digest,
        'target_function': TARGET,
        'theorem_count': 87,
        'class_counts': groups,
        'proofs': audit,
        'requires_lean_kernel_check': True,
        'whole_case_study_verified': False,
    }
    report_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n')
    return summary

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--index', type=Path, required=True)
    p.add_argument('--modules', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    r = build(a.index, a.modules, a.output, a.report)
    print('SSA_SEQUENCE_BOUND_CANDIDATES', r['theorem_count'], r['class_counts'])
