# Focus stacking with any lens

Focus stacking takes a series of shots at different focus distances and merges them in the camera into one picture
that is sharp from front to back. The stock E-M5 III only allows it with a short list of Olympus lenses. This was the
project's first patch: remove the lens check so stacking works with any lens. This page also covers a follow-up study
on letting you choose how many shots go into a stack.

**Status: done, working on the camera.**

Tags: **[code]** read in the firmware, **[camera]** seen on a real E-M5 III, **[inferred]** not traced or tested.

## The lens check and the patch

`fcs_check_focus_stacking_enable` (0x6065e5d6) only allows stacking for lenses on a list. The patch changes one branch
at **0x6065e5ec from `c9 04` to `cb cb`**, so the check always passes. The maintainer's original IDA patch, made before this
project, did the same; we recreated it on 2026-10-19 and flashed it, and it works. [camera]

- Later builds route the lens-flag call at 0x6065e5e2 to a small cave function that returns 1 (first at 0x600d0100,
  then 0x607a0000). [camera]
- The lens-type check reads lens_info+0x444 via 0x60206a03 (the same field as the Panasonic-lens test). [code]

## How many shots go into a stack (2026-11-05, research)

**The count is a setting, not a constant.** When focus bracketing and stacking are both on (0x609978a5), the sequence
takes `_bracketMaxShootCount` (0x61e9eb34) from setting **1448** (property 0x9842). The OM-5 1.2 uses the same property
as its setting 1459 `MODE_FOCUS_STACKING_NUMBER`. The E-M5 III has the setting and its saved property, but no menu item.
[code]

**What the OM-5 offers** (correction 2026-11-05): its menu offers stack counts **3-8** (descriptor 0x612218ec, six kind-5
options), not 3-15 as first thought. Setting 1459 is row 2 of its Focus BKT page (record 0x61224258), titled with string
0xa57 "Set number of shots", which the E-M5 III also has. The E-M5 III already has the per-setting class object for 1448
(0x608febd4). So adding the menu item is a data patch (Focus BKT page record 0x610d5e58 + copy 0x610e35e0, n 4→5) plus
one case in viewer 0x60e096d7; that is plan stage M1. [code]

Other things that touch the count: [code]

- An interlock at 0x602cc024 sets it to 8 when setting 24 == 207, and otherwise to its default (the OM-5 has the
  identical function). [code]
- Setting **1549** is the effective focus-bracketing shot count: interlock 0x602c7f18 copies 1448 into it when focus
  BKT + stacking are on, and 858 otherwise. The Focus BKT menu viewer 0x60e096d7 blanks "Set number of shots" (858)
  while stacking is on. 2026-11-05 [code]

**Going above 8** needs wider arrays: the combine controller keeps 9 buffer handles at obj+192 (OM-5: 16), and DevRec
`recordMediaFocusStacking` clips to 9 (0x60a85944; OM-5: 16). 9 = 8 frames + the composite. [code]+[inferred] So 3-8
shots looks like a menu item (or a forced value) only, while 9-15 also needs those arrays, the compositor and the memory
checked. [inferred] Next step: find the compositor behind `evTraCmpSts_StartCombine`.

**The merge itself** (2026-11-06): the native stack merge is request engine type 5 (shot kind 19). Step 1 `0x603804c6`
accepts 3-15 frames plus a reference index, so the merge chain itself allows 15. It aligns each frame (motion vectors +
image-engine job 4 warp) and merges with jobs 5/3/6/7; the output is 4480×3360. See
[image engine](../hardware/image-engine.md). [code]/[inferred]

## Test build FS1 (2026-11-05, not flashed)

FS1 makes stacking use "Set number of shots", clamped to 3-8. All 12 native reads of 1448 (10 via the getter
0x602e69f9, 2 via 0x602c782a in that interlock) go to a 164-byte routine at 0x600d0140; 1448 itself is never written.
There are variants on stock + any-lens and on E10f; the address check passed. [code]


