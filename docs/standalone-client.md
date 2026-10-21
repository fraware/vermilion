# External-project verification, alpha client

This branch implements an installable Python client that uses a separately
built Vermilion checkout as its pinned native SDK. The checkout and its
compiled Rust, Verus, Lean and cvc5 dependencies remain required.

Install the client only:

```sh
python3 -m pip wheel . --no-build-isolation --no-deps -w dist
python3 -m pip install dist/vermilion_external_cli-*.whl
```

In a Rust project outside Vermilion's source checkout:

```sh
vrml init --project-root /absolute/project --source src/example.rs
vrml doctor --sdk /absolute/built/vermilion
vrml verify --project-root /absolute/project --sdk /absolute/built/vermilion
```

The `verify` command requires a self-contained, Verus-annotated Rust source.
For now it supports one source per project. A successful verdict requires
fresh frontend elaboration, SST lowering, generated Lean VCs, Lean checker
acceptance, synchronization, statement-hash and theorem-signature matching
with the generated VC, and native Lean proof-twin checking. Invalid contracts
produce a source-mapped Lean error and a nonzero result. Toolchain failures
are classified separately.

This does not package the native compiler/runtime or their transitive
dependencies, and it is not a general Cargo-crate-wide verifier. See
[issue 50](https://github.com/ilyasergey/vermilion/issues/50) for the
remaining native distribution and project-local Lean workspace milestones.

Native acceptance: GitHub Actions runs 39540057266 and 39540644613
successfully verified a valid external Rust example and rejected a false
postcondition. Wheel-based execution is a separate, new acceptance gate and
must be checked independently before claiming installed-client success.
