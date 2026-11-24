# Any-lens focus stacking patch

This page describes the "focus stacking with any lens" patch. It covers which function decides whether a lens may be
used for in-camera focus stacking, how to find it, and which instruction we change. The background and the follow-up work are on the focus stacking page of the knowledge base (`features/focus-stacking.md`).

The patch has been flashed and working on our camera since 19 October 2026.

In short: the function first checks the lens type, then checks a per-lens "supports stacking" flag. We turn the branch
after the second check into two no-op instructions, so any lens that passes the first check is allowed.

## The function

**How to find it.** Search the decoded main program (block 0) for the debug string
`fcs_check_focus_stacking_enable stacking`. The one function that references it is the check. It has a single caller.

**What it does,** in order:

1. Set the result to 0.
2. Call the lens-type check (shared with eight other callers). If it fails, branch to the return.
3. Call the per-lens flag check. It returns 1 when the lens is on the "supports stacking" list.
4. Compare with 1 and branch to the return if not equal. **This is the branch we change.**
5. Set the result to 1, print the debug string and return.

## The patch

Replace that last `bne` (a two-byte short branch) with two `nop` instructions. Stacking is then allowed for any lens
that passes the lens-type check. That first check is left alone, because eight other features use it.

Then repack the update file so the block and file checksums are correct again (see the firmware file guide and the
container format page). The camera accepts the repacked file through its normal card update, even with the same
version number as the installed firmware.

