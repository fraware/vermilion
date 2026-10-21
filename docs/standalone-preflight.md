# External Vermilion projects — initialization contract (development)

Vermilion's current verifier executes in its source checkout. The external
distribution and independent-project native verification described in
[upstream issue #50](https://github.com/ilyasergey/vermilion/issues/50)
are still open development work.

This isolated implementation establishes the first enforceable boundary:
project-scoped state and explicit, fail-closed preflight for an already-built SDK.

Use Python 3.10 or newer:

    python3 scripts/vrml_external.py init --project-root /path/to/project --source src/lib.rs
    python3 scripts/vrml_external.py doctor --sdk /path/to/built/vermilion

The initialization command records source files and the selected emission mode
in project-local \`.vermilion/project.json\`, preserving user files. It rejects
duplicate Lean module stems, source paths escaping the root, unsafe artifact
symlinks, nonexistent files, and configuration overwrite attempts.

The doctor command checks for the pinned Verus frontend, Rust lowering
adapter, Lean VC generator, checker, synchronizer, built Lean library,
native SMT plugin, and version pins. It also requires that the checker
support an explicitly resolved native plugin path. It does **not** execute
the proof checker, establish complete transitive toolchain integrity,
or issue a verification verdict.

The tool is intentionally named \`vrml_external.py\` while external-project
native verification is incomplete. Do not substitute successful setup
or mock-based tests for a kernel-checked independent-project proof.

To test:

    python3 -m unittest discover -s tests -p test_vrml_external.py -v

Next acceptance gate: install the compiled verifier and Lean dependency closure,
verify a valid Rust contract in a directory outside the repository, reject
a deliberately false contract, inspect current generated statements and
their source-span mappings, and confirm proof-twin and artifact freshness.
