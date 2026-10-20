// expect: fail
use verus_builtin::*;
use verus_builtin_macros::*;
verus! {
spec fn never(i: int) -> bool { false }

fn ret_param_exists(i: u32) -> (result: u32)
    requires i == 7,
    ensures exists|i: int| #[trigger] never(i) == false && i == result && i != 7,
{
    i
}
} // verus!
