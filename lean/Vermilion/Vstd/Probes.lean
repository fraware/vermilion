import Vermilion.Vstd
import Lean

/-! Registry honesty check: every Lean name the vstd mirror's registries
reference must exist in the environment, so a typo (or a renamed prelude
lemma) breaks the BUILD instead of silently weakening hint resolution.
Compile-time only — nothing here ships into the Obligations closure. -/

open Lean Elab Command in
#eval show CommandElabM Unit from do
  let env ← getEnv
  for (path, names) in Vermilion.Vstd.lemmaRegistry do
    for name in names do
      unless env.contains name.toName do
        throwError "vstd mirror: `{path}` references unknown lemma `{name}`"
  for (path, name) in Vermilion.Vstd.specFnRegistry do
    unless env.contains name.toName do
      throwError "vstd mirror: `{path}` references unknown definition `{name}`"

/- Regression: Verus Seq::map calls `f(index, element)`; ordinary
element-only List.map would incorrectly produce [10, 20]. -/
example :
    Vermilion.Seq.mapWithIndex ([10, 20] : Vermilion.Seq Int)
      (fun i x => i + x) = ([10, 21] : Vermilion.Seq Int) := by decide

example :
    Vermilion.Seq.mapWithIndex ([] : Vermilion.Seq Int)
      (fun i x => i + x) = ([] : Vermilion.Seq Int) := by decide

/- Reordering or losing the index would change the callback's result. -/
example :
    Vermilion.Seq.mapWithIndex ([5, 2, 9] : Vermilion.Seq Int)
      (fun i x => 2 * i + x) = ([5, 4, 13] : Vermilion.Seq Int) := by decide

/- The mirror supports a result type distinct from the element type. -/
example :
    Vermilion.Seq.mapWithIndex ([true, false] : Vermilion.Seq Bool)
      (fun i x => if i = 0 then x else !x) =
      ([true, true] : Vermilion.Seq Bool) := by decide

/- Kernel-checked recursive subrange-tail decrease used by dalek load8. -/
example (xs : Vermilion.Seq Int) (h : xs.len ≠ 0) :
    (xs.subrange 1 xs.len).len < xs.len :=
  Vermilion.Seq.tail_subrange_strict xs h
