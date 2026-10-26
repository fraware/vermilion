import Vermilion.Obligations

/-!
An independent kernel-level calibration of the experimental assignment rule.
This establishes the equivalence of a fresh universally bound variable with
an exact defining equality and substituting the assigned value in downstream
propositions. It does not certify SST extraction, symbol freshness, or the
full generated dalek-lite theorem bodies.
-/

namespace Vermilion.Calibration

theorem fresh_eq_exact {α : Type} (value : α) (goal : α → Prop) :
    (∀ next : α, next = value → goal next) ↔ goal value := by
  constructor
  · intro h
    exact h value rfl
  · intro h next hnext
    subst next
    exact h

theorem indexed_write_eq_exact {α : Type} (old : Vermilion.Seq α)
    (index : Int) (newValue : α) (goal : Vermilion.Seq α → Prop) :
    (∀ next, next = Vermilion.Seq.update old index newValue →
      goal next) ↔ goal (Vermilion.Seq.update old index newValue) :=
  fresh_eq_exact _ _

theorem two_indexed_writes_eq_exact {α : Type} (old : Vermilion.Seq α)
    (i j : Int) (a b : α) (goal : Vermilion.Seq α → Prop) :
    (∀ intermediate,
      intermediate = Vermilion.Seq.update old i a →
      ∀ final,
        final = Vermilion.Seq.update intermediate j b →
        goal final) ↔
      goal (Vermilion.Seq.update (Vermilion.Seq.update old i a) j b) := by
  constructor
  · intro h
    exact h _ rfl _ rfl
  · intro h intermediate hint final hfinal
    subst intermediate
    subst final
    exact h

end Vermilion.Calibration
