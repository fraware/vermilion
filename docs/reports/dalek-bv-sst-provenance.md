# Dalek-lite source-to-SST-to-Lean bit-vector provenance

This is a **research tracing experiment**, not a verification result.

On an isolated GitHub Actions runner, the workflow rebuilds Vermilion's
pinned native toolchain, checks out dalek-lite at its documented pin
`de9ebf01599fedbbced28b938e2c36c538fe4ae5`, and produces the
real Verus VIR export with `--no-verify`. The pinned Rust middle-end
reconstructs pre-poly `FunctionSst`. The optional trace logs the
corresponding original SST assertion expressions and their neutral
lowered form for six recorded bit-vector assertions. The existing Lean
generator renders the associated obligations; a fail-closed Python
matcher records source spans and statement hashes.

The six source-keyed targets are:
- `mul_lemmas.rs:227`, `mul_lemmas.rs:231`
- `pow2k_lemmas.rs:236`, `pow2k_lemmas.rs:240`
- `field_u64.rs:1431`, `field_u64.rs:1446`

The experiment does **not** run an SMT verifier, discharge the generated
Lean theorems, or validate that all downstream assumptions are
authorized by independent proof. A statement whose Lean conclusion is
`True` is recorded explicitly; it is not closed by `trivial`.
Hash deviations from previously checked-in twins are reported
separately, with no automatic alignment.

The run keeps pinned source, command invocation, fresh generated
Lean modules, full trace, SHA-256 digests of the VIR binary and neutral
IR, and a machine-readable report. The full native VIR and IR files
are intentionally excluded from the CI artifact to avoid a large
artifact, but their content digests permit deterministic matching
when reproducing the commands against the same pins. Artifacts are
retained for 14 days; no release or permanent archival guarantee is
claimed.

Review gate: inspect all six actual traces, the generated logical
statements, and the source-to-query/outer-assumption pairing. Only
then decide whether the tracked proof holes are harmless annotations,
missing semantic obligations, or something else. This trace is
evidence toward that decision, not the decision itself.
