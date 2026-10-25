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

## Exact native follow-up receipts (2026-10-22)

The description above applies to the *initial tracing stage*. Subsequent
isolated experiments **did** kernel-check the six source-keyed, unsimplified
Lean arithmetic theorems. Those experiments are different from a complete
case-study or translation-soundness proof.

The [exact-head native run 39838589992](https://github.com/fraware/vermilion/actions/runs/39838589992)
at commit `24acfcf1fbdb56d35ba438997178c478395c2efd` passed
all of the following gates, in order:

1. Pin-matched source/VIR/SST/IR/Lean regeneration with the Verus BV
   interpreter enabled and disabled.
2. Exactly six source-keyed normal-mode SST `Const(Bool(true))` conclusions,
   with original tracked `True` statement hashes.
3. Exactly six *non-`True`* unsimplified SST/Lean conclusions, with six
   distinct changed statement hashes and matching source positions.
4. Reproduction and Lean kernel checking of all six unsimplified mathematical
   conclusions in an isolated proof module (four distinct formulas).
5. Lean kernel checking of all six **original generated theorem signatures**,
   preserving their full source binders, hypotheses and conclusions, under
   the corresponding pinned `Specs` definitions.
6. Lean kernel checking of all six **exact generated obligation blocks**:
   original `-- vrml:begin/end` markers, `ObligationMeta` definitions,
   `statementHash` fields, `@[vrml_obligation]` attributes, names,
   namespace and theorem signatures are retained. Only each generated
   proof body is replaced with the independent `decide` proof. These
   six blocks are extracted into three subset modules; **the other obligations
   from the three original source units are NOT included**.

The six unsimplified statement hashes, independently recorded in the
generated-block receipt, are:

| Pinned source key | Historical `True` hash | Unsimplified checked hash |
| --- | --- | --- |
| `mul_lemmas.rs:227` | `aba44725bf1d8c44` | `23bd4dcaa3a95e17` |
| `mul_lemmas.rs:231` | `3c8ee05bd5d51b4d` | `4d348042e2b3248a` |
| `pow2k_lemmas.rs:236` | `f9cc1a09afee1240` | `97d0c9f59036b223` |
| `pow2k_lemmas.rs:240` | `bfae7daeb21f67ff` | `bcce1f43a714b04c` |
| `field_u64.rs:1431` | `bea6232ee1a2aab0` | `cc56f090ceae3457` |
| `field_u64.rs:1446` | `4b5d62519b846699` | `6a8c772f1b979364` |

Each of the six subset-block Lean checks exited successfully with empty
Lean stderr. For each specific theorem, Lean's `#print axioms` reported
`[propext]`, one of Lean's standard logical axioms. The recorded proof
modules contain zero `sorry` statements. **These are not axiom-free
proofs**; they are also not proof of the other obligations in those units.
The generated-block evidence artifact expires by approximately
**2026-11-05 19:22 UTC**, subject to GitHub artifact retention.

### Precisely located remaining trust boundary

At the pinned Verus fork commit `48600836424a79420589c56d86e720236a029811`,
[`source/vir/src/sst_elaborate.rs`](https://github.com/ilyasergey/verus/blob/48600836424a79420589c56d86e720236a029811/source/vir/src/sst_elaborate.rs)
handles `StmX::AssertBitVector` in `elaborate_one_stm` by calling
`interpreter::eval_expr` on *both* explicit `requires` and `ensures`,
unless `ctx.global.no_bv_simplify` is enabled. The
[`ast_to_sst_crate` pipeline](https://github.com/ilyasergey/verus/blob/48600836424a79420589c56d86e720236a029811/source/vir/src/ast_to_sst_crate.rs)
runs `elaborate_function_bv` before the resulting `FunctionSst` reaches
Vermilion.

The
[`interpreter::eval_expr_top` decision](https://github.com/ilyasergey/verus/blob/48600836424a79420589c56d86e720236a029811/source/vir/src/interpreter.rs)
can replace a computed constant-true expression with
`SimplificationResult::True`. That identifies *where* the six proof
statements were simplified but does not provide a kernel-certified
equivalence between arbitrary source bit-vector assertions and the
interpreter's output.

For these six individual assertions, the unsimplified translated arithmetic
propositions have now been proved in Lean with their original generated
theorem contexts. This independently witnesses the truth of these six
propositions **under the pinned Lean bit-vector model**. The correspondence
from original Verus semantics to that model, and the interpreter's behavior
on other inputs, remain trusted assumptions. To shrink that boundary
systematically, use unsimplified queries under a complete fail-closed
differential gate and/or introduce a checkable Verus-to-Lean simplification
certificate; neither has been established for the entire corpus.

**Other open work:** two substantive `lemma_or_bit` bitwise obligations,
38 documented lowering refusals, source-to-target effect correspondence
beyond these cases, and full original dalek-lite proof-twin verification.
The original tracked `sorry` markers have **not** been silently replaced,
and the full case study has **not** been declared verified.
