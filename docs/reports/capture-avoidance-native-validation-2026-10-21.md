# Capture-avoiding lowering: native validation and trust boundary

Validation date: 2026-10-21 UTC. Repository: `fraware/vermilion`. Validated commit:
`1c7a3f66ec9b67e0606ae25929d0b6256e171ce9`.

## Evidence and results

The GitHub Actions run [39534343293](https://github.com/fraware/vermilion/actions/runs/39534343293)
finished with both jobs successful. Pinned Rust/Verus/Lean toolchain construction, native
Rust lowering tests, two independent differential execution modes, and the repository's
smoke and contract suite all passed.

- Protocol regressions: 11 differential-outcome tests and 8 generated-goal guard tests passed.
- Native binder unit tests: four capture-avoidance tests passed as part of the Rust lowering suite.
- Per-function mode: 197/197 verifier verdicts agreed with Verus and fixture expectations.
- Per-file mode: 197/197 verifier verdicts agreed with Verus and fixture expectations.
- Each mode reported a 98/98 failure-location *predicate* score. This is **not exact equality
  of the two tools' complete error-span sets**. The runner counts a negative case when its first
  Lean error line is present in Verus's error lines or equals the fixture's annotated expected
  line (see `scripts/run_differential.py`). Other lines can differ.
- Five deliberately invalid capture-sensitive programs failed verification, including a
  universal postcondition, existential postcondition, call precondition, and aliasing assertion;
  the positive shadowing control verified.
- `scripts/check_capture_goals.py` checked the generated Lean theorem bodies in both modes.
  In the inspected negative cases, the quantified variable was renamed (e.g. `i_vrml_0`)
  and outer `i` remained distinct.
- `./scripts/run_suite.sh --smoke` completed, including examples, generated-module
  determinism, source-movement incrementality, lowering refusals/isolation, and typeclass
  evidence contract tests.

The validation was executed against a pinned checkout on GitHub-hosted Ubuntu. The
resulting run logs and artifacts are the receipts. A CI cache hit was observed; the
native build remained executable after restoration.

## Scope and limitations

The run establishes strong regression evidence for the audited compiler change. It does
not establish a general translation-soundness theorem. The trusted path still includes:

1. The pinned Verus front/middle end and its choice/placement of verification conditions.
2. Rust SST-to-IR lowering (including substitutions, quantifier binders, callee contracts
   and state updates). This is the component corrected here.
3. IR-to-Lean theorem generation and the prelude's embedding conventions.
4. Complete, fail-closed checking and reporting of all generated statements and
   hand-written proof twins.
5. Lean kernel checking under each proof's imported axioms; source-level absence of
   `sorry` or `admit` does not establish axiom-free transitive dependencies.

These obligations are discussed in `docs/trust.md`. The focused run did not
independently prove all five trust obligations or audit the imported axiom closure.

The full research case-study suite was deliberately skipped in this focused gate. Upstream
`case-studies/dalek-lite/README.md` already describes incomplete verification:
two manual proof holes in `lemma_or_bit` and six more in other proof units, with
additional unsupported recursive-specification and substitution-budget cases. The
full-suite baseline remains incomplete and should be treated as a separate research
milestone, without weakening the mandatory correctness checks above.

## Integration policy

Promote the exact validated source onto the fork's default branch with the same focused
CI checks enabled on default-branch pushes. A passing default-branch run is a separate
acceptance receipt. Preserve per-mode generated Lean modules, reports, and SHA-256
manifests in run artifacts to support independent inspection. Do not represent the
still-open full research suite as passing.
