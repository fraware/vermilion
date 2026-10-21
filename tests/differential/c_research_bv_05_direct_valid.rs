// expect: pass
use verus_builtin::*;
use verus_builtin_macros::*;
verus! {
proof fn direct_valid() {
    assert((1u64 << 4) == 16u64) by (bit_vector);
}
}
