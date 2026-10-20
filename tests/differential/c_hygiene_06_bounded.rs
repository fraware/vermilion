// expect: pass
use verus_builtin::*;
use verus_builtin_macros::*;
verus! {
spec fn never(i: int) -> bool { false }

fn bounded(i: u32) -> (result: u32)
    requires i == 7,
    ensures forall|i: int| 0 <= i < result ==> #[trigger] never(i) == false,
{
    i
}
} // verus!
