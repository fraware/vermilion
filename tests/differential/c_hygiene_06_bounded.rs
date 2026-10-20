// expect: pass
use verus_builtin::*;
use verus_builtin_macros::*;
verus! {
fn bounded(i: u32) -> (result: u32)
    requires i == 7,
    ensures forall|i: int| 0 <= i < result ==> i < 10,
{
    i
}
} // verus!
