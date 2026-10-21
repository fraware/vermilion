# Native SDK alpha — independent external Rust verification

**Scope.** This workflow packages a built, pinned Vermilion runtime and
installs a separate Python client. The supported target is currently an
Ubuntu 24.04-compatible Linux x86-64 system with a pinned `rustup` Rust
toolchain and `elan` Lean toolchain. The native SDK is an **alpha**;
the case-study suite and general translation-soundness proof remain separate.

## Distribution contents

The artifact `linux-x86_64-native-sdk-alpha`, when produced by the
[clean-host acceptance workflow](https://github.com/fraware/vermilion/actions/workflows/native-sdk-distribution.yml),
contains `vermilion-native-sdk.tar.zst`, the Python client wheel, and
`SHA256SUMS`. Verification bundles include:

- Pinned Verus frontend, its runtime dependencies and Z3;
- The compiled SST lowering adapter, Lean obligation generator, checker,
  and proof synchronizer;
- Compiled Lean `.olean` dependency closure and the native cvc5 plugin;
- Build identity, toolchain pins, SHA-256 hashes of critical SDK files,
  and explicit Lean search paths.

The trimmed runtime is approximately **6.9 GB unpacked** in the initial
Ubuntu CI environment; archive size is a separate measurement. A successful
`vrml doctor` only validates filesystem integrity and host prerequisites.

## Install on a matching Ubuntu host

Obtain the named artifact from a **successful** release-validation run.
Place its contents in a temporary directory and use the following commands:

```bash
cd /path/to/artifact
sha256sum -c SHA256SUMS
mkdir -p "${HOME}/.local/share/vermilion"
tar -I zstd -xf vermilion-native-sdk.tar.zst \
  -C "${HOME}/.local/share/vermilion"
sdk="${HOME}/.local/share/vermilion/vermilion-native-sdk"

# On hosts with rustup and elan already installed:
elan toolchain install "$(cat "$sdk/lean-toolchain")"
rust_pin="$(sed -n 's/^channel = "\([^"]*\)"$/\1/p' "$sdk/.verus-checkout/rust-toolchain.toml")"
rustup toolchain install "$rust_pin" --profile minimal
python3 -m pip install ./vermilion_external_cli-*.whl
```

Native platform prerequisites include the matching libc++, libc++abi,
and GMP runtime libraries. The clean-host workflow provisions them
explicitly, alongside Rust and Lean; inspect that workflow for the
tested Ubuntu commands.

From a Rust project in a directory **outside** the native SDK:

```bash
vrml init --project-root /path/to/rust-project --source src/example.rs
vrml doctor --sdk "$sdk"
vrml verify --project-root /path/to/rust-project --sdk "$sdk"
```

The source must use the Verus syntax recognized by the pinned frontend.
The current client supports one source file per project. The runner
collects generated obligations, checks them with Lean, synchronizes
proof twins, checks statement hashes and theorem signatures, and then
kernel-checks the proof twins for a successful result. Verdict code
`0` signifies successful verification of the configured source;
`1` is reserved for a source-mapped proof rejection; `2` indicates
a configuration or infrastructure failure.

The project-local `.vermilion/runs/<stem>/` directory contains stage
logs, exact source hashes, and a machine-readable verdict when a
classified proof result is obtained.

## Acceptance and limitations

A source-checkout-backed external project was checked in
[run 39541055922](https://github.com/fraware/vermilion/actions/runs/39541055922).
A separately **relocated** native runtime accepted a valid contract
and rejected a false one in
[run 39543311700](https://github.com/fraware/vermilion/actions/runs/39543311700).

The stricter clean-host acceptance adds a source-free fresh GitHub runner,
artifact SHA-256 validation, independent host toolchain provisioning, and
native valid/invalid verification from the downloaded archive.
A completed, successful clean-host result is necessary before publishing
this artifact as independently installable.

The pinning and compiler safeguards are evidence for the tested cases,
not a universal soundness theorem. The trusted Rust-to-Lean translation,
Lean prelude, verifier completeness, and imported axioms remain explicit
assumptions. The full `dalek-lite` research case study retains open proof
holes and lowering refusals.
