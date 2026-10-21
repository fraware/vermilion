#!/usr/bin/env python3
"""Conservative external-project setup and SDK preflight for Vermilion.

This module intentionally does not return a verification verdict. A successful
doctor check establishes only that the *inputs* for external verification are
present. Native proof acceptance has its own independent gate.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile


VERSION = 1
STEM = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
BINARIES = {
    "frontend": ".verus-checkout/source/target-verus/release/rust_verify",
    "lowerer": "crates/vermilion_direct/target/release/vermilion_direct",
    "generator": ".lake/build/bin/vrml_gen",
    "checker": "target/debug/vrml_check",
    "synchronizer": "target/debug/vrml_sync",
}
LEAN_LIBRARY = ".lake/build/lib/lean/Vermilion.olean"
PLUGIN_CANDIDATES = (
    ".lake/packages/cvc5/.lake/build/lib/libcvc5_cvc5.so",
    ".lake/packages/cvc5/.lake/build/lib/libcvc5_cvc5.dylib",
    ".lake/packages/cvc5/.lake/build/lib/cvc5_cvc5.dll",
)


class ContractError(Exception):
    pass


def _ordinary_dir(path: Path, label: str) -> None:
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise ContractError(f"{label} must be an ordinary directory: {path}")


def _safe_source(root: Path, raw: str) -> str:
    path = Path(raw)
    if path.is_absolute() or not path.parts or any(
        item in (".", "..") for item in path.parts
    ):
        raise ContractError(f"source must be project-relative: {raw}")
    destination = root / path
    if not destination.resolve().is_relative_to(root):
        raise ContractError(f"source escapes project root: {raw}")
    if not destination.is_file() or destination.suffix != ".rs":
        raise ContractError(f"source must exist and be a Rust file: {raw}")
    if not STEM.fullmatch(destination.stem):
        raise ContractError(f"source stem is invalid as a Lean module: {raw}")
    for parent in (destination.parent / "generated", destination.parent / "proofs"):
        _ordinary_dir(parent, "verification artifact directory")
    return destination.relative_to(root).as_posix()


def _write_json_new(path: Path, value: dict) -> None:
    """Create exactly once; never clobber another tool's or user's config."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as error:
        raise ContractError(f"configuration exists; refusing overwrite: {path}") from error


def init_project(root: Path, source_paths: list[str], mode: str) -> Path:
    if mode not in ("per-function", "per-file"):
        raise ContractError(f"unsupported emission mode: {mode}")
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ContractError(f"project root is not a directory: {root}")
    if not source_paths:
        raise ContractError("at least one source file is required")
    state = root / ".vermilion"
    _ordinary_dir(state, "project state")
    _ordinary_dir(state / "runs", "verification run state")
    selections = [_safe_source(root, name) for name in source_paths]
    if len(set(selections)) != len(selections):
        raise ContractError("duplicate Rust source paths")
    stems = [Path(path).stem for path in selections]
    if len(set(stems)) != len(stems):
        raise ContractError("Lean module-name collision across Rust sources")
    # Finish preflight before writing any state.
    if (state / "project.json").exists() or (state / "project.json").is_symlink():
        raise ContractError("project configuration already exists")
    state.mkdir(exist_ok=True)
    (state / "runs").mkdir(exist_ok=True)
    path = state / "project.json"
    _write_json_new(path, {
        "version": VERSION,
        "source": selections[0],
        "sources": selections,
        "emission": mode,
    })
    ignore = state / ".gitignore"
    if not ignore.exists() and not ignore.is_symlink():
        with ignore.open("x", encoding="utf-8") as stream:
            stream.write("*\n!.gitignore\n!project.json\n")
    return path


def check_sdk(sdk: Path) -> dict:
    """Pure filesystem-level preflight; never claims proof acceptance."""
    sdk = sdk.expanduser().resolve(strict=True)
    if not sdk.is_dir():
        raise ContractError("SDK path must be a directory")
    missing = []
    for label, value in BINARIES.items():
        path = sdk / value
        if not path.is_file() or not os.access(path, os.X_OK):
            missing.append(f"{label}: {value}")
    if not (sdk / LEAN_LIBRARY).is_file():
        missing.append(f"Lean library: {LEAN_LIBRARY}")
    plugin = next((name for name in PLUGIN_CANDIDATES if
                   (sdk / name).is_file()), None)
    if plugin is None:
        missing.append("native cvc5 plugin")
    pin = sdk / "lean-toolchain"
    if not pin.is_file() or not pin.read_text(encoding="utf-8").strip():
        missing.append("Lean version pin: lean-toolchain")
    rust_pin = sdk / ".verus-checkout/rust-toolchain.toml"
    if not rust_pin.is_file():
        missing.append("Verus Rust toolchain pin")
    checker_src = sdk / "crates/vermilion_backend/src/bin/vrml_check.rs"
    if not checker_src.is_file() or (
        'std::env::var_os("VRML_CVC5_PLUGIN")'
        not in checker_src.read_text(encoding="utf-8")
    ):
        missing.append("checker external native-plugin path support")
    for executable in ("lean", "lake", "rustup"):
        if shutil.which(executable) is None:
            missing.append(f"PATH tool: {executable}")
    return {
        "sdk": str(sdk),
        "ready_for_native_attempt": not missing,
        "missing": missing,
        "plugin": plugin,
        "scope": "filesystem and PATH preflight only; no native proof check",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vrml-external")
    cmd = parser.add_subparsers(dest="command", required=True)
    init = cmd.add_parser("init", help="initialize an external Verus project")
    init.add_argument("--project-root", type=Path, default=Path.cwd())
    init.add_argument("--source", dest="sources", action="append", required=True)
    init.add_argument("--mode", choices=("per-function", "per-file"),
                      default="per-function")
    doctor = cmd.add_parser("doctor", help="inspect a prebuilt Vermilion SDK")
    doctor.add_argument("--sdk", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            path = init_project(args.project_root, args.sources, args.mode)
            print(f"initialized {path}")
            return 0
        result = check_sdk(args.sdk)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["ready_for_native_attempt"] else 2
    except (ContractError, OSError, ValueError, UnicodeError) as error:
        print(f"vermilion external-project setup: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
