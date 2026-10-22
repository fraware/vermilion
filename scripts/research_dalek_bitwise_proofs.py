#!/usr/bin/env python3
"""Experimental proof candidates for two existing bit-vector obligations.

Does not modify tracked twins. Copies exactly two historical theorem signatures
from their source/hash-keyed original blocks, renaming declarations only to
avoid legacy duplicate assertId collision, and tries native Lean proofs.
No claims are made before native Lean exits zero and prints axiom receipts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SOURCE = Path("case-studies/dalek-lite/proofs/bit_lemmas/layer_a_lemmas_common_lemmas_bit_lemmas_lemma_or_bit.lean")
ORIGINAL = [
    ("0a4e09fc4eccff1f", "nonoverlap"),
    ("635d62c1edcb1059", "same_position"),
]
NAME = "layer_a.lemmas.common_lemmas.bit_lemmas.lemma_or_bit.assert_bv_5_0"
START = re.compile(r"(?m)^-- vrml:begin (\S+) ([0-9a-f]{16})\s*$")

PROOF_NONOVERLAP = r'''
  have hpos0 : 0 ≤ pos := by
    unfold Vermilion.inUnsignedRange at loop_0_iteration_2
    omega
  have hj0 : 0 ≤ j := by
    unfold Vermilion.inUnsignedRange at loop_0_iteration_3
    omega
  have hp : pos.toNat < 8 := by omega
  have hq : j.toNat < 8 := by omega
  have hne : j.toNat ≠ pos.toNat := by omega
  have hv : BitVec.ofInt 8 val = 0#8 ∨ BitVec.ofInt 8 val = 1#8 := by
    rcases loop_0_iteration_6 with h | h
    · left; simp [h]
    · right; simp [h]
  have h := bv_or_and_ne8 (BitVec.ofInt 8 mask) (BitVec.ofInt 8 val)
    pos.toNat j.toNat hp hq hne hv
  simpa only [Vermilion.Bits.band, Vermilion.Bits.bor,
    Vermilion.Bits.shl, ofInt_toNat8] using
      congrArg (fun (v : BitVec 8) => (v.toNat : Int)) h
'''

PROOF_SAME = r'''
  have hpos0 : 0 ≤ pos := by
    unfold Vermilion.inUnsignedRange at loop_1_iteration_2
    omega
  have hp : pos.toNat < 8 := by omega
  have hposition : j = pos := loop_1_iteration_7
  subst j
  rcases loop_1_iteration_6 with hzero | hone
  · subst val
    simp only [Vermilion.Bits.band, Vermilion.Bits.bor,
      Vermilion.Bits.shl, ofInt_toNat8] at ⊢
    simp
  · subst val
    have h := bv_or_self_bit8 (BitVec.ofInt 8 mask) pos.toNat hp
    have hleft :
        ¬ (Vermilion.Bits.band 8
          (Vermilion.Bits.bor 8 mask (Vermilion.Bits.shl 8 1 pos))
          (Vermilion.Bits.shl 8 1 pos) = 0) := by
      simpa only [Vermilion.Bits.band, Vermilion.Bits.bor,
        Vermilion.Bits.shl, ofInt_toNat8] using h
    simp [hleft]
'''


def extract(source: str, digest: str, newname: str):
    matches = [(i, m) for i, m in enumerate(START.finditer(source))
               if m.group(1) == NAME and m.group(2) == digest]
    if len(matches) != 1:
        raise ValueError(f"missing or ambiguous original bitvector block: {digest}")
    i, match = matches[0]
    later = list(START.finditer(source))
    next_begin = later[i + 1].start() if i + 1 < len(later) else len(source)
    ending = source.find("-- vrml:end " + NAME, match.end(), next_begin)
    if ending < 0:
        raise ValueError(f"unclosed source block {digest}")
    block = source[match.start():ending]
    if f'statementHash := "{digest}"' not in block:
        raise ValueError(f"source hash drift at {digest}")
    match = re.search(r"(?m)^@\[vrml_obligation\] theorem assert_bv_5_0\n", block)
    if not match:
        raise ValueError(f"missing exact source declaration at {digest}")
    pos = block.find(":= by", match.end())
    if pos < 0:
        raise ValueError("original theorem proof missing")
    header = block[match.start():pos + 5]
    if "sorry" in header or "True := by" in header:
        raise ValueError("unacceptable theorem header")
    replacement = header.replace(
        "@[vrml_obligation] theorem assert_bv_5_0", f"theorem {newname}", 1)
    if replacement.replace(f"theorem {newname}",
                           "@[vrml_obligation] theorem assert_bv_5_0", 1) != header:
        raise ValueError("nonidentity theorem rename")
    return replacement, hashlib.sha256(header.encode()).hexdigest()


def build(path: Path, dest: Path, receipt: Path):
    text = path.read_text(encoding="utf-8")
    blocks = re.findall(r"(?s)-- vrml:user:begin\n(.*?)-- vrml:user:end", text)
    if not blocks or "private theorem bv_or_and_ne8" not in blocks[0]:
        raise ValueError("missing existing kernel-proven BitVec helpers")
    if "private theorem bv_or_self_bit8" not in blocks[0]:
        raise ValueError("missing second BitVec helper")
    statements = [
        "import Vermilion.Obligations",
        "set_option maxRecDepth 16384",
        "set_option maxHeartbeats 0",
        "",
        blocks[0].rstrip(),
        "",
        "namespace DalekBitwiseTrial",
        "",
    ]
    receipts = []
    for (digest, label), proof in zip(ORIGINAL, [PROOF_NONOVERLAP, PROOF_SAME]):
        original_header, sha = extract(text, digest, label)
        statements.extend([
            "-- Tracked source assertion; proof remains experimental until Lean succeeds.",
            original_header + proof,
            f"#print axioms {label}",
            "",
        ])
        receipts.append({"historical_statement_hash":digest,
                         "original_theorem_header_sha256":sha,
                         "candidate":label, "source_proof_rewritten":False})
    statements.extend(["end DalekBitwiseTrial", ""])
    out = "\n".join(statements)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(out, encoding="utf-8")
    receipt.write_text(json.dumps({"original":str(path),"candidates":receipts,
                                   "experimental":True},indent=2)+"\n",encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        build(args.source, args.output, args.receipt)
        print("Two source-keyed trial theorems extracted; proofs not yet verified")
        return 0
    except (OSError, ValueError) as e:
        print("FAIL CLOSED:",e,file=sys.stderr)
        return 2

if __name__=="__main__":
    sys.exit(main())
