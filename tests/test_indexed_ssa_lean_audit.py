#!/usr/bin/env python3
"""Negative controls for the pinned indexed-SSA generated-Lean audit.

Run after experimental dalek-lite generation, on the actual generated
module. Mutated fixture digests are updated deliberately to ensure the
auditor checks SSA structure rather than only rejecting stale hashes.
"""
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from audit_indexed_ssa_lean import audit  # noqa: E402

EVIDENCE = ROOT / ".vermilion/dalek-provenance"


class IndexedSSALeanAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = json.loads((EVIDENCE / "ssa-target-lean-index.json").read_text())
        cls.receipt = EVIDENCE / "ssa-index-execution.json"
        cls.module = cls.index["obligations"][0]["module"]
        cls.original = (EVIDENCE / "ssa-target-lean" / cls.module).read_text()

    def audit_mutation(self, mutated: str, *, corrupt_index_hash=False):
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder)
            dest = temp / "modules" / self.module
            dest.parent.mkdir(parents=True)
            dest.write_text(mutated)
            index = copy.deepcopy(self.index)
            digest = hashlib.sha256(dest.read_bytes()).hexdigest()
            for obligation in index["obligations"]:
                obligation["module_sha256"] = digest
            if corrupt_index_hash:
                index["obligations"][0]["statement_hash"] = "0000000000000000"
            index_path = temp / "index.json"
            index_path.write_text(json.dumps(index))
            with self.assertRaises(AssertionError):
                audit(index_path, self.receipt, temp / "modules")

    def test_unmutated_source_passes(self):
        report = audit(
            EVIDENCE / "ssa-target-lean-index.json",
            self.receipt,
            EVIDENCE / "ssa-target-lean")
        self.assertEqual(report["executed_indexed_ssa_updates"], 42)
        self.assertEqual(report["byte_updates"], 32)

    def test_self_referential_update_rejected_after_rehash(self):
        old = "s_ssa_32 = Vermilion.Seq.update s_ssa_31 31 "
        self.assertIn(old, self.original)
        self.audit_mutation(self.original.replace(
            old, "s_ssa_32 = Vermilion.Seq.update s_ssa_32 31 "))

    def test_missing_defining_update_rejected_after_rehash(self):
        old = "s_ssa_32 = Vermilion.Seq.update s_ssa_31 31 "
        self.assertIn(old, self.original)
        self.audit_mutation(self.original.replace(
            old, "s_ssa_32 = Vermilion.Seq.missing s_ssa_31 31 "))

    def test_mismatched_obligation_hash_rejected(self):
        self.audit_mutation(self.original, corrupt_index_hash=True)


if __name__ == "__main__":
    unittest.main()
