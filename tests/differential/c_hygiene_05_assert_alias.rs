// expect: fail
use verus_builtin::*;
use verus_builtin_macros::*;
verus! {
spec fn never(i: int) -> bool { false }

fn assert_alias(i: u32)
    requires i == 7,
{
    let m = i;
    assert(forall|i: int| 0 <= i < m ==> #[trigger] never(i));
}
} // verus!
