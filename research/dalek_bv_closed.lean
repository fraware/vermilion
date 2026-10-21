import Vermilion.Prelude

/-!
# Closed bit-vector arithmetic obligations from pinned dalek-lite

These four statements are literal duplicates of the four distinct closed
conclusions found among the six UNSIMPLIFIED generated Lean obligations in
native run 39671923404 (commit 69387784). Identical source-level obligations
occur in lemma_mul_boundary and lemma_pow2k_loop_boundary.

This module is an independently compiled, kernel-adjudicated research check.
Its Lean elaboration does not establish source-to-Lean translation soundness.
No axiom, sorry, or trusted Verus evaluation is introduced.
-/

set_option maxRecDepth 16384
set_option maxHeartbeats 0

namespace DalekBvResearch

theorem square_limb_pow2 :
    (2 * Vermilion.Bits.shl 64 1 52) = Vermilion.Bits.shl 64 1 53 := by
  decide

theorem square_limb_shift_monotone :
    Vermilion.Bits.shl 64 1 53 < Vermilion.Bits.shl 64 1 54 := by
  decide

theorem lemma_pow2k_square :
    (((Vermilion.Bits.shl 64 1 54) % 340282366920938463463374607431768211456)
      * ((Vermilion.Bits.shl 64 1 54) % 340282366920938463463374607431768211456))
      = Vermilion.Bits.shl 128 1 108 := by
  decide

theorem lemma_pow2k_scaled_square :
    (Vermilion.Bits.shl 64 1 54 *
      ((19 * Vermilion.Bits.shl 64 1 54) % 18446744073709551616))
      = (19 * Vermilion.Bits.shl 128 1 108) := by
  decide

end DalekBvResearch
