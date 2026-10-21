// expect: fail
use verus_builtin::*;
use verus_builtin_macros::*;
verus! {
proof fn nested_false() {
    assert(0u64 == 1u64) by {
        assert(0u64 == 1u64) by (bit_vector);
    }
}
}
