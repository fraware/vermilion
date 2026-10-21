#!/usr/bin/env python3
"""Materialize a relocatable native Vermilion runtime from a pinned built checkout.

Produces a *runtime bundle*, not a redistributable promise: the matching
host's pinned Rust/Lean toolchains and platform libraries remain prerequisites.
Copies the pinned Verus executable/dependency tree, native adapter/checker,
Lean library and dependency trees without using checkout symlinks at runtime.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from vrml_external import BINARIES, LEAN_LIBRARY, PLUGIN_CANDIDATES, ContractError

FORMAT = "vermilion-native-sdk-v1"
CHECKED_FILES = ("lean-toolchain", "lakefile.lean", "lake-manifest.json",
                 ".verus-checkout/rust-toolchain.toml", LEAN_LIBRARY,
                 *tuple(BINARIES.values()))


def sha(path: Path) -> str:
    hash_value = hashlib.sha256()
    with path.open("rb") as reader:
        for chunk in iter(lambda: reader.read(1024 * 1024), b""):
            hash_value.update(chunk)
    return hash_value.hexdigest()


def _copy(src: Path, dest: Path) -> None:
    if not src.exists():
        raise ContractError(f"required build artifact is missing: {src}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        if dest.exists():
            raise ContractError(f"destination collision: {dest}")
        # Follow any symlink to copy its actual bytes. The packaged bundle
        # must not depend on source-checkout symlinks at verification time.
        shutil.copytree(src, dest, symlinks=False)
    else:
        shutil.copy2(src, dest, follow_symlinks=True)


def _safe_bundle(destination: Path) -> None:
    for path in destination.rglob("*"):
        if path.is_symlink():
            # A symlink might cross out of the SDK tree even when it was
            # copied from a precompiled transitive dependency tree.
            resolved = path.resolve()
            if not resolved.is_relative_to(destination):
                raise ContractError(f"bundle contains an external symlink: {path}")


def build(source: Path, output: Path) -> dict:
    source = source.expanduser().resolve(strict=True)
    output = output.expanduser().absolute()
    if not source.is_dir():
        raise ContractError("SDK build source is not a directory")
    if output == source or output.is_relative_to(source) or source.is_relative_to(output):
        raise ContractError("SDK output must be outside its build source")
    if output.exists() or output.is_symlink():
        raise ContractError(f"SDK output exists: {output}")
    if output.parent.exists() and output.parent.is_symlink():
        raise ContractError("refusing symlinked output parent")
    checkout = (source / ".verus-checkout").resolve(strict=True)
    if not (checkout / "source").is_dir():
        raise ContractError("pinned Verus checkout source tree missing")
    pin_cmd = subprocess.run(["git", "-C", str(checkout), "rev-parse", "HEAD"],
                             capture_output=True, text=True, check=False)
    if pin_cmd.returncode or len(pin_cmd.stdout.strip()) != 40:
        raise ContractError("cannot establish Verus source commit")
    source_cmd = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"],
                                capture_output=True, text=True, check=False)
    if source_cmd.returncode or len(source_cmd.stdout.strip()) != 40:
        raise ContractError("cannot establish Vermilion source commit")
    checks = [*CHECKED_FILES, next((name for name in PLUGIN_CANDIDATES
                                     if (source / name).is_file()), "")]
    if not checks[-1]:
        raise ContractError("compiled cvc5 plugin is missing")
    for name in checks:
        if name == ".verus-checkout/rust-toolchain.toml":
            path = checkout / "rust-toolchain.toml"
        elif name.startswith(".verus-checkout/"):
            path = checkout / name[len(".verus-checkout/"):]
        else:
            path = source / name
        if not path.is_file():
            raise ContractError(f"build artifact absent: {name}")
    output.mkdir(parents=True, exist_ok=False)
    try:
        # Lake config and sources are used to reconstruct LEAN_PATH in a
        # relocated runtime; precompiled oleans avoid dependency rebuilding.
        for name in ("lean-toolchain", "lakefile.lean", "lake-manifest.json"):
            _copy(source / name, output / name)
        for name in ("lean", ".lake/packages", ".lake/build"):
            _copy(source / name, output / name)
        # The checkout source compiler is unnecessary for executing the
        # pinned rust_verify binary. Preserve runtime binaries, deps and Z3.
        _copy(checkout / "rust-toolchain.toml",
              output / ".verus-checkout/rust-toolchain.toml")
        _copy(checkout / "source/target-verus/release",
              output / ".verus-checkout/source/target-verus/release")
        _copy(checkout / "source/z3", output / ".verus-checkout/source/z3")
        for name in BINARIES.values():
            if name.startswith(".verus-checkout/") or name.startswith(".lake/"):
                continue
            _copy(source / name, output / name)
        plugin = checks[-1]
        _safe_bundle(output)
        files = dict()
        for name in checks:
            files[name] = sha(output / name)
        metadata = {
            "format": FORMAT,
            "source_commit": source_cmd.stdout.strip(),
            "verus_commit": pin_cmd.stdout.strip(),
            "platform": sys.platform,
            "architecture": os.uname().machine if hasattr(os, "uname") else "unknown",
            "plugin": plugin,
            "files": files,
            "toolchain_policy": "matching host must install pinned rustup and elan toolchains",
            "proof_scope": "runtime packaging; no verification verdict",
        }
        state = output / ".vermilion"
        state.mkdir()
        (state / "native-sdk.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return metadata
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise


def main() -> int:
    cli = argparse.ArgumentParser()
    cli.add_argument("--source", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    arguments = cli.parse_args()
    try:
        obj = build(arguments.source, arguments.output)
        print(json.dumps({"output": str(arguments.output),
                          "source_commit": obj["source_commit"],
                          "verus_commit": obj["verus_commit"],
                          "checked_artifacts": len(obj["files"])}, sort_keys=True))
        return 0
    except (ContractError, OSError) as exc:
        print(f"native SDK packaging refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
