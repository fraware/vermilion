// expect: fail
use verus_builtin::*;
use verus_builtin_macros::*;
verus! {
spec fn never(i: int) -> bool { false }

fn callee(x: u32)
    requires forall|i: int| 0 <= i < x ==> #[trigger] never(i),
{
}
fn call_param(i: u32)
    requires i == 7,
{
    callee(i);
}
} // verus!
