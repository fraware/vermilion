"""Adversarial tests of external project initialization and SDK preflight."""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from vrml_external import ContractError, check_sdk, init_project, main, BINARIES, LEAN_LIBRARY, PLUGIN_CANDIDATES


class StandaloneContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "src").mkdir()
        (self.root / "src/lib.rs").write_text("use verus_builtin::*;\n", encoding="utf-8")

    def test_initialization_and_schema(self):
        target = init_project(self.root, ["src/lib.rs"], "per-function")
        x = json.loads(target.read_text())
        self.assertEqual(x["version"], 1)
        self.assertEqual(x["source"], "src/lib.rs")
        self.assertEqual(x["sources"], ["src/lib.rs"])
        self.assertEqual(x["emission"], "per-function")
        self.assertFalse((self.root / ".vermilion/runs").is_symlink())

    def test_reinitialization_never_overwrites(self):
        target = init_project(self.root, ["src/lib.rs"], "per-file")
        before = target.read_bytes()
        with self.assertRaises(ContractError):
            init_project(self.root, ["src/lib.rs"], "per-function")
        self.assertEqual(target.read_bytes(), before)

    def test_escape_through_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as elsewhere:
            (self.root / "escape.rs").symlink_to(Path(elsewhere) / "outside.rs")
            (Path(elsewhere) / "outside.rs").write_text("fn x() {}", encoding="utf-8")
            with self.assertRaises(ContractError):
                init_project(self.root, ["escape.rs"], "per-function")

    def test_parent_traversal_rejected(self):
        with self.assertRaises(ContractError):
            init_project(self.root, ["../lib.rs"], "per-function")
        self.assertFalse((self.root / ".vermilion/project.json").exists())

    def test_symlinked_artifact_directory_rejected(self):
        with tempfile.TemporaryDirectory() as elsewhere:
            (self.root / "src/proofs").symlink_to(elsewhere)
            with self.assertRaises(ContractError):
                init_project(self.root, ["src/lib.rs"], "per-function")

    def test_duplicate_module_stems_rejected(self):
        (self.root / "other").mkdir()
        (self.root / "other/lib.rs").write_text("fn x() {}", encoding="utf-8")
        with self.assertRaises(ContractError):
            init_project(self.root, ["src/lib.rs", "other/lib.rs"], "per-function")

    def test_existing_state_file_rejected(self):
        (self.root / ".vermilion").write_text("occupied", encoding="utf-8")
        with self.assertRaises(ContractError):
            init_project(self.root, ["src/lib.rs"], "per-function")

    def test_sdk_missing_components_fails_closed(self):
        out = check_sdk(self.root)
        self.assertFalse(out["ready_for_native_attempt"])
        self.assertTrue(any("Lean library" in x for x in out["missing"]))

    def test_complete_simulated_sdk_preflight(self):
        for p in BINARIES.values():
            artifact = self.root / p
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            artifact.chmod(0o755)
        for p in [LEAN_LIBRARY, PLUGIN_CANDIDATES[0], "lean-toolchain",
                  ".verus-checkout/rust-toolchain.toml"]:
            path = self.root / p
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("pinned\n", encoding="utf-8")
        checker = self.root / "crates/vermilion_backend/src/bin/vrml_check.rs"
        checker.parent.mkdir(parents=True, exist_ok=True)
        checker.write_text('std::env::var_os("VRML_CVC5_PLUGIN")', encoding="utf-8")
        with patch("vrml_external.shutil.which", return_value="/usr/bin/verified"):
            result = check_sdk(self.root)
        self.assertTrue(result["ready_for_native_attempt"])
        self.assertIn("no native proof check", result["scope"])

    def test_cli_init_returns_success(self):
        with patch("builtins.print"):
            self.assertEqual(main(["init", "--project-root", str(self.root),
                                   "--source", "src/lib.rs"]), 0)

    def test_invalid_source_never_creates_config(self):
        with self.assertRaises(ContractError):
            init_project(self.root, ["src/nope.rs"], "per-function")
        self.assertFalse((self.root / ".vermilion/project.json").exists())


if __name__ == "__main__":
    unittest.main()
