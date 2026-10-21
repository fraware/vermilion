# dalek-lite residual proof backlog: semantic audit

The tracked `dalek-lite` field-cone case study currently records eight explicit
`sorry` bodies in four Lean proof units. A fresh static audit is provided by
`python3 scripts/audit_dalek_holes.py`. It checks source-level markers and
statement hashes; **it does not kernel-check or discharge any obligation**.

The eight holes comprise:

| Unit | Holes | Emitted goal |
| --- | ---: | --- |
| `square2` | 2 | literally `True` |
| `lemma_pow2k_loop_boundary` | 2 | literally `True` |
| `lemma_mul_boundary` | 2 | literally `True` |
| `lemma_or_bit` | 2 | substantive eight-bit vector identities |

The literal-`True` goals arise at source constructs tagged as bit-vector
assertions. Although the Lean proposition itself admits `trivial`, replacing
`sorry` with `trivial` would make the accounting appear better without
demonstrating the corresponding source-level semantics. This is a **translation
provenance question**: each source assertion must be traced through the pinned
Verus export, SST lowering, IR and generated Lean before classifying it as an
intentional proof-script marker or a lost logical assertion.

The two substantive `lemma_or_bit` goals concern bitwise OR, shifted
single-bit masks, and a case distinction `val ∈ {0,1}`. The existing
file contains `BitVec 8` helper lemmas that provide candidates for explicit
proof terms. No claim of closure is justified without kernel-checking the
unaltered generated statements and auditing their imported axioms.

## Separate engineering queues

1. Trace literal-`True` obligations to source and IR and rule out erased
   logical predicates; preserve generated-statement hashes.
2. Isolate each of the two substantive bitwise theorems and develop proof
   terms without theorem weakening or new axioms.
3. Test the declaration-collision defect that creates repeated
   `assert_bv_5_0` identifiers under separate loop contexts. Avoid
   identifying the two obligations by their nonunique short names.
4. Handle the 37 cross-module recursive-specification refusals and one
   substitution-budget refusal as distinct translation problems.
5. Re-run the entire pinned acquisition and produce kernel-level results
   for every accepted function before claiming case-study acceptance.

All eight proof holes, 38 refused functions, and the upstream trusted
assumption floor remain open unless independently discharged.

## Pinned-source comparison (2026-10-21)

A manual source-to-proof inspection traced the six `True` goals to their recorded
bit-vector assertion locations in pinned
[`Beneficial-AI-Foundation/dalek-lite`](https://github.com/Beneficial-AI-Foundation/dalek-lite/tree/de9ebf01599fedbbced28b938e2c36c538fe4ae5)
(commit `de9ebf01599fedbbced28b938e2c36c538fe4ae5`) and the tracked
[`field_u64.rs`](../../case-studies/dalek-lite/field_u64.rs).
The line references below come from the recorded Lean metadata; file locations
in the original pinned source were checked separately for the two lemma files.

| Proof unit | `True` obligation source spans | Source operation |
| --- | --- | --- |
| `lemma_mul_boundary` | `mul_lemmas.rs:227`, `:231` | Two nested `by (bit_vector)` constant-shift/multiplication assertions |
| `lemma_pow2k_loop_boundary` | `pow2k_lemmas.rs:236`, `:240` | Corresponding two nested `by (bit_vector)` assertions |
| `square2` | tracked `field_u64.rs:1431`, `:1446` | Bit-vector assertions in loop and proof code relating powers-of-two bounds |

The two pinned lemma sources are:
[`mul_lemmas.rs`](https://github.com/Beneficial-AI-Foundation/dalek-lite/blob/de9ebf01599fedbbced28b938e2c36c538fe4ae5/curve25519-dalek/src/lemmas/field_lemmas/mul_lemmas.rs)
and
[`pow2k_lemmas.rs`](https://github.com/Beneficial-AI-Foundation/dalek-lite/blob/de9ebf01599fedbbced28b938e2c36c538fe4ae5/curve25519-dalek/src/lemmas/field_lemmas/pow2k_lemmas.rs).

This inspection identifies a more exact question than a literal-`True` count.
In both lemma proof units, a nested bit-vector query has a `True` Lean
conclusion. Separately, a later `assert_1` obligation checks the relevant
outer arithmetic equality **under an `assume` hypothesis representing the
nested assertion**. In `lemma_mul_boundary`, for example, the inner query
`assert_bv_3_0` at line 227 states `True`; the later `assert_1`
includes `assume_8` for the u128 multiplication equality. This
correspondence is a statement-level observation only: it does **not**
establish that the nested source assertion was independently discharged.

The Rust adapter's
[`StmX::AssertBitVector` lowering](../../crates/vermilion_direct/src/lower.rs)
places `ensures` expressions into an isolated loop. The
[VC policy](../vcgen.md) intentionally isolates assertion queries to avoid
circular assumptions from the enclosing context. A `True` query in these
specific generated twins could therefore reflect source-to-SST query
construction, proof-script handling, or a missing verification condition.
The current static evidence does not distinguish those explanations.

**Required experiment before any soundness conclusion:** reconstruct the exact
pinned Verus-exported `AssertBitVector` `requires`/`ensures` payloads
and the corresponding pre-/post-query assumptions for these six locations.
Then execute a controlled negative nested-query fixture with identical
source and pins under Verus and Vermilion, retaining VIR/SST export, neutral
IR, generated Lean, verdicts, and statement hashes. A failed native query
must neither become an accepted `True` obligation nor authorize an
unchecked downstream assumption. This has **not yet been demonstrated or
refuted** by the static inspection.

This evidence is separate from the two substantive `lemma_or_bit`
bitwise theorems; those also remain open. The eight source-level `sorry`
markers, statement-hash identities, 38 lowering refusals, and full-suite
acceptance status remain unchanged.

## Native pinned-SST origin established (2026-10-21)

The six previously ambiguous literal-`True` clauses were regenerated
from the pinned dalek-lite repository at commit
`de9ebf01599fedbbced28b938e2c36c538fe4ae5` using the
Verus/Vermilion native pipeline, with no Lean verification step.
Successful exact-head
[CI run 39669741271](https://github.com/fraware/vermilion/actions/runs/39669741271)
retained [a machine-readable source/SST/IR/Lean evidence artifact](https://github.com/fraware/vermilion/actions/runs/39669741271).
The independently downloaded artifact’s `provenance.json` SHA-256 is
`ed832aa2e4c49c1477b1b5eea04d9a7dd3ee0703532c38230731725ed383e893`,
matching its CI `SHA256SUMS`.

For each of the six source positions
(`mul_lemmas.rs:227,231`, `pow2k_lemmas.rs:236,240`,
and tracked `field_u64.rs:1431,1446`), native instrumentation observed:

- Pinned pre-poly SST bit-vector **require**: `Const(Bool(true))`;
- Pinned pre-poly SST bit-vector **ensure**: `Const(Bool(true))`;
- Vermilion neutral lowered ensure: `True`;
- Fresh generated Lean conclusion: literal `True`;
- Fresh statement hash: equal to the tracked historical twin hash.

This locates the original simplification **before** Vermilion’s expression
lowerer. The pinned Verus source identifies a mechanism: in
[`sst_elaborate.rs`](https://github.com/ilyasergey/verus/blob/48600836424a79420589c56d86e720236a029811/source/vir/src/sst_elaborate.rs),
`elaborate_one_exp` handles `StmX::AssertBitVector` by running
`interpreter::eval_expr` on both explicit `requires` and `ensures`
unless `ctx.global.no_bv_simplify` is set. The
[`ast_to_sst_crate`](https://github.com/ilyasergey/verus/blob/48600836424a79420589c56d86e720236a029811/source/vir/src/ast_to_sst_crate.rs)
pipeline calls `elaborate_function_bv` before exposing
`FunctionSst` to Vermilion. This establishes the preprocessing boundary
for the observed six cases; the interpreter’s semantic correctness is not
certified by the generated trivial Lean theorems.

A separate native five-fixture falsification suite
[passed in run 39670574634](https://github.com/fraware/vermilion/actions/runs/39670574634):
three previous nested controls and new direct valid/invalid bit-vector
assertions produced matching expected Verus/Lean verdicts in both emission
modes. These tests did **not** reproduce a false acceptance, and their scope
does not establish generalized translation soundness.

A research switch sets Verus `no_bv_simplify` on an isolated branch
[`research/dalek-bv-sst-provenance`](https://github.com/fraware/vermilion/tree/research/dalek-bv-sst-provenance).
In a second native pass in
[run 39671295480](https://github.com/fraware/vermilion/actions/runs/39671295480),
all six source-keyed un-simplified Lean conclusions were **non-`True`**,
and all six hashes changed. The overall workflow failed subsequently
because the Python comparison command had malformed arguments; this
is an orchestration failure, not evidence that the formula comparison
failed. A corrected exact-head re-run is required.

**Assurance boundary:** default-mode Lean proofs of `True` follow a
Verus interpretation step; these six historical proof placeholders are
a provenance/trust question rather than six substantive Lean goals.
To eliminate that interpreter step from the trusted correctness boundary,
retain the un-simplified formulas, kernel-check their actual proofs,
and justify their faithful association to each source assertion.
The two `lemma_or_bit` proof holes, the 38 lowering refusals, and
the full case-study verification gate remain open.
