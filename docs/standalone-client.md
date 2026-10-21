# External-project verification — native SDK alpha

The `vrml` Python client verifies one Verus-annotated Rust source file in a
project directory independent of the Vermilion development checkout. Two
SDK arrangements are supported at the alpha stage:

1. A separately **built Vermilion source checkout** containing the compiled
   pinned verifier and its dependencies.
2. A **relocatable, precompiled native SDK archive** containing the pinned
   Verus frontend, Rust adapter, Lean checker/generator, compiled Lean
   dependency closure, and cvc5 plugin. The host installs matching Rust and
   Lean toolchains and required system libraries.

For the archive installation, integrity checks, platform prerequisites, and
tested commands, follow [native-sdk-install.md](native-sdk-install.md).
Do not confuse a source-checkout-backed installation with the
archive-only clean-host acceptance.

## Installed client usage

Install from a locally produced wheel:

```sh
python3 -m pip wheel . --no-build-isolation --no-deps -w dist
python3 -m pip install dist/vermilion_external_cli-*.whl
```

From an independent Rust project:

```sh
vrml init --project-root /absolute/project --source src/example.rs
vrml doctor --sdk /absolute/native-sdk
vrml verify --project-root /absolute/project --sdk /absolute/native-sdk
```

The native SDK may be a prepared checkout or the unpacked archive. The
current verifier handles **one source file per project**, not arbitrary
Cargo workspaces or crates. The source must use the Verus syntax supported
by the pinned compiler.

The `verify` pipeline runs frontend elaboration, SST lowering, Lean
obligation generation and checking, twin synchronization, statement-hash
and theorem-signature checks, and native Lean checking of the resulting
proof twins. Exit code `0` means verification succeeded for the tested
source; `1` means a source-mapped proof rejection; `2` means an
infrastructure or configuration error. A `doctor` success establishes
host/package prerequisites, not proof soundness.

## Exact evidence

- [Run 39541055922](https://github.com/fraware/vermilion/actions/runs/39541055922):
  checked an external project through a development-checkout-backed client.
- [Run 39543571463](https://github.com/fraware/vermilion/actions/runs/39543571463):
  clean Ubuntu 24.04 installation from a **downloaded precompiled artifact**
  without checking out the Vermilion repository on the consumer host.
  Its successful jobs covered packaging unit tests, relocated runtime, and
  artifact-only host execution. The clean-host program verified a valid
  two-obligation contract and rejected a deliberately false contract.
- [Run 39544185647](https://github.com/fraware/vermilion/actions/runs/39544185647):
  native correctness suite passed on fork `main` at
  `836a28d513f3a6463b0d2d48293466466c45ec0e`; both
  emission modes matched all 197 Verus verdicts, with a separate
  98/98 failure-location *predicate*, not exact span equivalence.

The distribution artifacts from run 39543571463 are **temporary**.
At the time of verification they were scheduled to expire on
**November 4, 2026 (UTC)**. This is evidence of a tested artifact-only
installation, **not** proof of a durable release channel.

## Known limits

The installer is currently Ubuntu 24.04-compatible Linux x86-64 alpha.
The package manifest verifies selected critical files; the distributed
archive has a separately verified SHA-256 checksum. The package manifest
does not individually hash the entire transitive Lean and Verus runtime
closure. General source-to-Lean translation soundness and complete
dalek-lite verification remain open research questions.

[Upstream issue #50](https://github.com/ilyasergey/vermilion/issues/50)
describes broader standalone acceptance, including identical statements,
hashes, verdicts and proof twins for a relocated representative case study.
The present single-source alpha does not discharge that full criterion.
