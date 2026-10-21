#!/usr/bin/env python3
"""Real native single-source Verus-to-Lean verification in an external project.

The compiled SDK remains a separately built Vermilion checkout. This is an
external-project execution slice, not an installable distribution yet.
No stage is simulated, and no frontend SMT verdict is used for acceptance.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import hashlib

from vrml_external import BINARIES, PLUGIN_CANDIDATES, ContractError, check_sdk
from vrml_external_bindings import verify_bindings

PIN_RE = re.compile(r'(?m)^\s*channel\s*=\s*"([^"]+)"')
VSTD_RE = re.compile(r'(?m)^\s*use\s+vstd::')
HOLE_RE = re.compile(r'\b(?:sorry|admit|sorryAx)\b')


def execute(args: list[str], root: Path, env: dict[str, str], label: str,
            logdir: Path, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(args, cwd=root, env=env, capture_output=True,
                                text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ContractError(f"{label} could not execute: {exc}") from exc
    (logdir / (label + ".stdout")).write_text(result.stdout, encoding="utf-8")
    (logdir / (label + ".stderr")).write_text(result.stderr, encoding="utf-8")
    return result


def verified_manifest(path: Path, expected: str, root: Path) -> dict:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"generator did not emit a valid manifest: {exc}") from exc
    if not isinstance(obj, dict) or obj.get("rust_file") != expected:
        raise ContractError("manifest source identity mismatch")
    if obj.get("refused") or obj.get("refusals"):
        raise ContractError("manifest contains refused functions")
    obligations = obj.get("obligations")
    if not isinstance(obligations, list) or len(obligations) < 1:
        raise ContractError("manifest has no verifiable obligations")
    for item in obligations:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str) or (
            not isinstance(item.get("statement_hash"), str)
        ):
            raise ContractError("malformed obligation record")
        dest = root / item.get("lean_file", obj.get("lean_file", ""))
        if not dest.resolve().is_relative_to(root) or not dest.is_file():
            raise ContractError("manifest references absent or escaping Lean source")
    return obj


def verify(project: Path, sdk: Path, source_override: str | None = None) -> int:
    project = project.resolve(strict=True)
    sdk = sdk.resolve(strict=True)
    if project == sdk or project.is_relative_to(sdk) or sdk.is_relative_to(project):
        raise ContractError("external project and SDK must be disjoint directories")
    state = project / ".vermilion"
    if state.is_symlink() or not state.is_dir():
        raise ContractError("project is not initialized with an ordinary .vermilion directory")
    config = json.loads((state / "project.json").read_text(encoding="utf-8"))
    if config.get("version") != 1:
        raise ContractError("unsupported project config version")
    sources = config.get("sources")
    if not isinstance(sources, list) or len(sources) != 1:
        raise ContractError("this native slice supports exactly one Rust source")
    relative = source_override or sources[0]
    if relative != sources[0] or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ContractError("requested source differs from initialized project")
    source = (project / relative).resolve(strict=True)
    if not source.is_relative_to(project) or not source.is_file():
        raise ContractError("source escapes the project root")
    mode = config.get("emission")
    if mode not in ("per-file", "per-function"):
        raise ContractError("invalid project emission mode")
    for side in ("generated", "proofs"):
        folder = source.parent / side
        if folder.is_symlink():
            raise ContractError("generated/proofs paths must not be symlinks")
    doctor = check_sdk(sdk)
    if not doctor["ready_for_native_attempt"]:
        raise ContractError("SDK preflight failed: " + "; ".join(doctor["missing"]))
    plugin_rel = next(p for p in PLUGIN_CANDIDATES if (sdk / p).is_file())
    plugin = (sdk / plugin_rel).resolve(strict=True)
    verus_home = (sdk / ".verus-checkout").resolve(strict=True)
    verus_source = verus_home / "source"
    match = PIN_RE.search((verus_home / "rust-toolchain.toml").read_text())
    if not match:
        raise ContractError("Verus Rust toolchain pin is missing")
    toolchain = match.group(1)
    env = dict(os.environ)
    # The client project may have a different Lean pin. Enforce the SDK pin.
    env["ELAN_TOOLCHAIN"] = (sdk / "lean-toolchain").read_text().strip()
    if not env["ELAN_TOOLCHAIN"]:
        raise ContractError("empty Lean toolchain pin")
    logdir = state / "runs" / source.stem
    if logdir.is_symlink():
        raise ContractError("run log directory must not be a symlink")
    logdir.mkdir(parents=True, exist_ok=True)
    sysroot = execute(["rustup", "run", toolchain, "rustc", "--print", "sysroot"],
                      sdk, env, "sysroot", logdir, 60)
    if sysroot.returncode != 0 or not sysroot.stdout.strip():
        raise ContractError("pinned Rust sysroot could not be resolved")
    syslib = str(Path(sysroot.stdout.strip()) / "lib")
    for var in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
        env[var] = syslib + (os.pathsep + env[var] if env.get(var) else "")
    env["VERUS_ROOT"] = str(verus_source / "target-verus/release")
    env["VERUS_Z3_PATH"] = str(verus_source / "z3")
    env["VRML_CVC5_PLUGIN"] = str(plugin)
    # Use Lean libraries built with the pinned SDK, not with the user's project.
    lean_path = execute(["lake", "env", "printenv", "LEAN_PATH"], sdk, env,
                        "lean-path", logdir, 120)
    if lean_path.returncode != 0 or not lean_path.stdout.strip():
        raise ContractError("could not obtain pinned SDK Lean library path")
    entries = [p for p in lean_path.stdout.strip().split(os.pathsep) if p]
    env["LEAN_PATH"] = os.pathsep.join([str(project)] +
        [str((sdk / p).resolve()) for p in entries])
    # Fresh run identity. Old generator, proof and editor artifacts cannot
    # silently replace the obligations for newly updated Rust source.
    vir = state / ("external-" + source.stem + "-vir.bin")
    ir = state / ("external-" + source.stem + "-ir.sexp")
    vir.unlink(missing_ok=True)
    ir.unlink(missing_ok=True)
    source_data = source.read_text(encoding="utf-8")
    vstd = [] if VSTD_RE.search(source_data) else ["--no-vstd", "--cfg", "verus_no_vstd"]
    front = execute([str(sdk / BINARIES["frontend"]), relative,
                     "--crate-type=lib", *vstd, "--no-verify"],
                    project, env | {"VERUS_VIR_EXPORT": str(vir)},
                    "frontend", logdir)
    if front.returncode != 0 or not vir.is_file():
        raise ContractError("pinned Verus frontend failed; see frontend.stderr")
    lower = execute([str(sdk / BINARIES["lowerer"]), str(vir), "--out", str(ir)],
                    project, env, "lowering", logdir)
    if lower.returncode != 0 or not ir.is_file():
        raise ContractError("SST lowering failed/refused; see lowering.stderr")
    gen = execute([str(sdk / BINARIES["generator"]), "--mode", mode, str(ir)],
                  project, env, "generator", logdir)
    if gen.returncode != 0:
        raise ContractError("Lean VC generator failed; see generator.stderr")
    manifest_path = source.parent / "generated" / (source.stem + ".json")
    manifest = verified_manifest(manifest_path, relative, project)
    check = execute([str(sdk / BINARIES["checker"]),
                     str(manifest_path.relative_to(project))],
                    project, env, "checker", logdir)
    verdict = {
        "source": relative, "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "manifest": str(manifest_path.relative_to(project)),
        "obligations": len(manifest["obligations"]),
        "mode": mode, "checker_returncode": check.returncode,
        "verdict": "infrastructure",
    }
    if check.returncode == 1:
        errors = []
        for line in check.stdout.splitlines():
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(msg, dict) and msg.get("level") == "error" and (
                msg.get("$message_type") == "diagnostic"
            ):
                errors.append(msg)
        if not errors:
            raise ContractError("Lean check failed without source-mapped proof diagnostics")
        verdict["verdict"] = "rejected"
        verdict["failed_obligations"] = len(errors)
        result_code = 1
    elif check.returncode == 0:
        sync = execute([str(sdk / BINARIES["synchronizer"]),
                        str(manifest_path.relative_to(project))],
                       project, env, "synchronizer", logdir)
        if sync.returncode != 0:
            raise ContractError("proof twin reconciliation failed")
        proofs = source.parent / "proofs"
        twin_paths = ([proofs / (source.stem + ".lean")]
                      if mode == "per-file" else
                      sorted((proofs / source.stem).rglob("*.lean")))
        if not twin_paths or any(not p.is_file() for p in twin_paths):
            raise ContractError("proof twin is missing")
        if any(HOLE_RE.search(p.read_text(encoding="utf-8")) for p in twin_paths):
            raise ContractError("unresolved Lean proof hole in synchronized twin")
        # The kernel must check proofs of the exact freshly generated
        # statements, not a user-edited weaker theorem.
        verify_bindings(project, manifest)
        twin = execute([str(sdk / BINARIES["checker"]),
                        str(manifest_path.relative_to(project)), "--twin-check"],
                       project, env, "twin-check", logdir)
        if twin.returncode != 0:
            raise ContractError("native kernel checking of proof twins failed")
        verify_bindings(project, manifest)
        verdict["verdict"] = "verified"
        verdict["proof_twins"] = [str(p.relative_to(project)) for p in twin_paths]
        result_code = 0
    else:
        raise ContractError("Lean checker failed without a classified proof result")
    status_path = logdir / "verdict.json"
    status_path.write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps(verdict, sort_keys=True))
    return result_code


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--sdk", type=Path, required=True)
    opts = parser.parse_args()
    try:
        sys.exit(verify(opts.project_root, opts.sdk))
    except (ContractError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"native external verification failed: {exc}", file=sys.stderr)
        sys.exit(2)
