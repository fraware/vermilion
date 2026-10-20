// expect: fail
use verus_builtin::*;
use verus_builtin_macros::*;
verus! {
spec fn never(i: int) -> bool { false }

fn ret_param_ctrl(k: u32) -> (result: u32)
    requires k == 7,
    ensures forall|i: int| 0 <= i < result ==> #[trigger] never(i),
{
    k
}
} // verus!
