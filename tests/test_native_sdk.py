"""Packaging and tamper-detection tests; never substitute for native execution."""
from pathlib import Path
import json
from unittest.mock import patch
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from pack_native_sdk import build
from vrml_external import BINARIES, LEAN_LIBRARY, PLUGIN_CANDIDATES, (
    ContractError, check_sdk, native_sdk_manifest
)


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "working-tree"
        self.source.mkdir()
        self.output = self.root / "native-sdk"
        for name in [
            "lean-toolchain", "lakefile.lean", "lake-manifest.json",
            ".verus-checkout/rust-toolchain.toml",
            ".verus-checkout/source/z3",
            LEAN_LIBRARY, PLUGIN_CANDIDATES[0],
            "crates/vermilion_backend/src/bin/vrml_check.rs",
            *list(BINARIES.values()),
        ]:
            item = self.source / name
            item.parent.mkdir(parents=True, exist_ok=True)
            item.write_text("pinned content\n", encoding="utf-8")
            if name in BINARIES.values():
                item.chmod(0o755)
        for name in ("lean", ".lake/packages", ".lake/build"):
            (self.source / name).mkdir(parents=True, exist_ok=True)
        checker = self.source / "crates/vermilion_backend/src/bin/vrml_check.rs"
        checker.write_text('std::env::var_os("VRML_CVC5_PLUGIN")', encoding="utf-8")
        self.source_sha = "a" * 40
        self.verus_sha = "b" * 40

    def assemble(self):
        def fake_git(command, **kwargs):
            class Fake:
                returncode = 0
                stdout = self.verus_sha if "verus" in command[2] else self.source_sha
            return Fake()
        with patch("pack_native_sdk.subprocess.run", side_effect=fake_git):
            return build(self.source, self.output)

    def test_copies_runtime_and_marks_source(self):
        manifest = self.assemble()
        self.assertEqual(manifest["format"], "vermilion-native-sdk-v1")
        self.assertEqual(manifest["source_commit"], self.source_sha)
        self.assertTrue((self.output / LEAN_LIBRARY).is_file())
        self.assertFalse((self.output / "crates/vermilion_backend/src/bin/vrml_check.rs").exists())
        present, errors = native_sdk_manifest(self.output)
        self.assertTrue(present)
        self.assertEqual(errors, [])

    def test_binary_tamper_fails(self):
        self.assemble()
        (self.output / BINARIES["checker"]).write_text("replaced", encoding="utf-8")
        _, errors = native_sdk_manifest(self.output)
        self.assertTrue(any("digest mismatch" in error for error in errors))

    def test_missing_manifest_file_fails(self):
        self.assemble()
        path = self.output / ".vermilion/native-sdk.json"
        data = json.loads(path.read_text())
        data["files"].pop("lean-toolchain")
        path.write_text(json.dumps(data))
        _, errors = native_sdk_manifest(self.output)
        self.assertTrue(any("omits mandatory" in error for error in errors))

    def test_bundle_cannot_replace_existing_output(self):
        self.assemble()
        with self.assertRaises(ContractError):
            self.assemble()

    def test_sdk_preflight_with_bundle_no_source_checkout_needed(self):
        self.assemble()
        with patch("vrml_external.shutil.which", return_value="/usr/bin/lean"):
            result = check_sdk(self.output)
        self.assertTrue(result["ready_for_native_attempt"], result["missing"])
        self.assertTrue(result["native_bundle"])

    def test_no_malformed_manifest_fallback(self):
        self.assemble()
        file = self.output / ".vermilion/native-sdk.json"
        file.write_text("{bad")
        with patch("vrml_external.shutil.which", return_value="/usr/bin/lean"):
            result = check_sdk(self.output)
        self.assertFalse(result["ready_for_native_attempt"])

    def test_declines_nested_sdk_output(self):
        with self.assertRaises(ContractError):
            build(self.source, self.source / "install")

    def test_bundle_excludes_source_checker(self):
        self.assemble()
        self.assertFalse((self.output / "crates/vermilion_backend/src/bin/vrml_check.rs").exists())


if __name__ == "__main__":
    unittest.main()
