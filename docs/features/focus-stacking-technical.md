# Focus stacking: technical notes

> **Technical notes.** This page is the dense reference. For a readable introduction, start with [Focus stacking](focus-stacking.md).

Focus stacking takes a series of shots at different focus distances and merges them in the camera into one picture
that is sharp from front to back. The stock E-M5 III only allows it with a short list of Olympus lenses. This was the
project's first patch: remove the lens check so stacking works with any lens. This page also covers a follow-up study
on letting you choose how many shots go into a stack.

**Status: done, working on the camera.**

Tags: **[code]** read in the firmware, **[camera]** seen on a real E-M5 III, **[inferred]** not traced or tested.

## The lens check and the patch

**How to find it.** The check is the function that prints the debug string
`fcs_check_focus_stacking_enable stacking`. Search block0 for that string and follow the one function that references
it. It has a single caller, in the focus-stacking setup path. [code]

**What it does.** It starts with result = 0 and makes two calls. The first is a lens-type check shared with eight other
callers (the same lens-info field the Panasonic-lens test reads). The second returns 1 when the attached lens carries a
per-lens "supports stacking" flag. Each call is followed by a compare and a short forward `bne` to the return. Only if
both pass does it set result = 1. [code]

**The patch.** Turn the `bne` after the second call into two `nop`s. Any lens that passes the lens-type check is then
allowed. The first check stays, because eight other features use it. The original IDA patch, made before this project,
did the same. We recreated it on 2026-10-19, flashed it, and it works. [camera]


- **Other bodies** (2026-11-20): the same function, found by the same debug string, with the same two-call shape and the
  same branch, exists on the OM-5 1.2, OM-5 II 1.1, E-M1 III 1.6, OM-1 1.9 and OM-1 II 1.3. So the one-branch change
  would carry over. Not tried on any of them. The PEN-F 3.1 has no in-camera stacking. [code]
  [body comparison](../bodies/comparison-technical.md#our-features-on-the-other-bodies-2026-11-20)
- **As a card mod** (2026-11-22): the same change, applied in RAM at start-up by our mod loader, works without a
  patched firmware. [camera]

## How many shots go into a stack (2026-11-05, research)

**The count is a setting, not a constant.** When focus bracketing and stacking are both on, the shooting sequence reads
`_bracketMaxShootCount` from setting **1448** (saved property 0x9842). The OM-5 1.2 uses the same property as its
setting 1459 `MODE_FOCUS_STACKING_NUMBER`. The E-M5 III has the setting and its saved value, but no menu row. [code]
How to find it: the `_bracketMaxShootCount` symbol string leads to the sequence step. Setting 1448 has one getter, and
listing its callers gives every place that reads the count (12 reads, 10 through the getter and 2 in an interlock).

**What the OM-5 offers** (correction 2026-11-05): its menu offers **3-8** shots (six options), not 3-15 as first
thought. The row is row 2 of its Focus BKT page, titled "Set number of shots". The E-M5 III has that string and the
per-setting object for 1448 already. Adding the row is a data change to the E-M5 III's Focus BKT page record (and its
copy), one more row in the list, plus one case in that page's viewer function. [code]
How to find it: the page record is the one whose row list includes the Focus BKT rows. The viewer is the function that
greys out "Set number of shots" while stacking is on.

Other things that touch the count: [code]

- An interlock sets it to 8 for one particular value of setting 24, and to its default otherwise. The OM-5 has the
  identical function.
- Setting **1549** is the effective focus-bracketing shot count. An interlock copies 1448 into it when focus BKT and
  stacking are both on, and setting 858 otherwise. The Focus BKT viewer blanks "Set number of shots" (858) while stacking
  is on, which is why the count has to be set with stacking off.

**Going above 8** needs wider arrays. The combine controller keeps 9 buffer handles in its object (OM-5: 16), and
DevRec `recordMediaFocusStacking` clips to 9 (OM-5: 16). 9 = 8 frames + the composite. [code]+[inferred] So 3-8 shots
is a menu row (or a forced value) only, while 9-15 also needs those arrays, the compositor and the memory checked.
[inferred] Next step was to find the compositor behind `evTraCmpSts_StartCombine`.

**The merge itself** (2026-11-06): the native stack merge is request engine type 5 (shot kind 19). Its first step
accepts 3-15 frames plus a reference index, so the merge chain itself allows 15. It aligns each frame (motion vectors +
image-engine job 4 warp) and merges with jobs 5, 3, 6 and 7. The output is 4480×3360. See
[image engine](../hardware/image-engine.md). [code]/[inferred]


## Shot count 3-8 on the camera

A test build made stacking use "Set number of shots", clamped to 3-8. Every native read of setting 1448 goes to one small
routine that returns the clamped value. 1448 itself is never written. [code]

**Camera-proven as card mods (2026-11-22):** the same hooks as a card mod, together with the any-lens change as a
second card mod, loaded from the card by our mod loader with nothing else flashed. With 5 shots set (stacking off),
then stacking on, the camera takes 5 frames and the composite, and stacking works on a lens stock refuses. The native
menu greys out "Set number of shots" while stacking is on. An OM-5-style row was the next step. [camera]


## On the E-M5 II and E-M5 (Mark I) (2026-11-21)

- **E-M5 II 4.1:** in-camera stacking code is present (`MODE_FOCUS_STACKING_ONOFF`, `MODE_FOCUS_STACKING_ENABLED_LENS`, `DevRec_Rec::recordMediaFocusStacking`, "Wait For Combining Finish"). The E-M5 III-shaped `fcs_check_focus_stacking_enable` was not found by shape (best 13 of 25 instructions), so the lens gate needs its own trace before a patch; whether the stock menu offers stacking was not checked. [code]
- **E-M5 (Mark I) 2.3:** no stacking or focus-bracket strings; nothing to patch. [code]

Full comparison: [older bodies](../bodies/comparison-technical.md#older-bodies-e-m5-ii-and-e-m5-mark-i-2026-11-21).
