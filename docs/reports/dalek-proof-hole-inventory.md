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
