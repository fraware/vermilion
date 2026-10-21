# Targeted bit-vector assertion falsification

This branch extends the earlier three-case nested-query experiment with
two standalone bit-vector assertions. These tests exercise the specific
causal risk identified by the six-query dalek-lite source/SST/Lean trace:
the pinned middle-end represented six embedded bit-vector queries with
`requires=true`, `ensures=true`. The adapter translated those exact
expressions faithfully. An assertion query passing vacuously could lead
to false source verification if no distinct obligation protects it.

New cases:
- `c_research_bv_04_direct_false.rs`: false `0u64 == 1u64` proof
  asserted *only* by `bit_vector`, without an enclosing ordinary assertion.
  Expected: Verus and Lean both reject.
- `c_research_bv_05_direct_valid.rs`: true bit-shift arithmetic assertion.
  Expected: Verus and Lean both accept.

The two distinct per-mode comparison passes run real pinned Verus and
Lean and reject mismatch or unclassified infrastructure errors. A green
gate establishes results for five concrete programs, not a universal
soundness theorem. A red gate with a source-mapped Verus rejection and
Lean acceptance is retained as positive evidence of a discrepancy;
it must not be reclassified as a successful experiment.
