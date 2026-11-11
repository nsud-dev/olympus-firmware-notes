# Focus stacking with any lens

**Status: done, on camera.**
- `fcs_check_focus_stacking_enable` (0x6065e5d6) gates on a lens list. Patch: branch at **0x6065e5ec `c9 04` → `cb cb`**.
  The maintainer's original IDA patch (before the project) did the same; recreated 2026-10-19 and flashed: works. [camera]
- Later builds route the lens-flag call 0x6065e5e2 to a cave function returning 1 (0x600d0100, then 0x607a0000). [camera]
- The lens-type check reads lens_info+0x444 via 0x60206a03 (same field as the Panasonic-lens test). [code]

## Shot count (2026-11-05, research only)
- The stacking shot count is **not fixed in code**: the sequence takes `_bracketMaxShootCount` (0x61e9eb34) from setting
  **1448** (prop 0x9842) when focus BKT + stacking are on (0x609978a5). OM-5 1.2 uses the same property as setting 1459
  `MODE_FOCUS_STACKING_NUMBER`. E-M5 III has the setting and its saved property but no menu item. [code]
- **Correction 2026-11-05:** the OM-5 1.2 menu offers stack counts **3-8** (descriptor 0x612218ec, six kind-5 options), not 3-15; 1459 is row 2 of its Focus BKT page (record 0x61224258) with title string 0xa57 "Set number of shots", which E-M5 III also has. E-M5 III already has the per-setting class object for 1448 (0x608febd4). So the menu item is a data patch (Focus BKT page record 0x610d5e58 + copy 0x610e35e0, n 4→5) plus one case in viewer 0x60e096d7; plan stage M1. [code]
- Interlock 0x602cc024 sets it to 8 when setting 24 == 207, else to its default (OM-5 has the identical function). [code]
- Above 8 needs wider arrays: combine controller keeps 9 buffer handles at obj+192 (OM-5: 16), DevRec
  `recordMediaFocusStacking` clips to 9 (0x60a85944; OM-5: 16). 9 = 8 frames + composite. [code]+[inferred]
- So 3-8 shots looks like a menu item (or a forced value) only; 9-15 also needs those arrays, the compositor and memory
  checked. [inferred] Next: find the compositor behind `evTraCmpSts_StartCombine`.
- Setting **1549** is the effective focus-BKT shot count: interlock 0x602c7f18 copies 1448 into it when focus BKT +
  stacking are on, else 858. The Focus BKT menu viewer 0x60e096d7 blanks "Set number of shots" (858) while stacking is
  on. [code] 2026-11-05
- **FS1 build (2026-11-05, not flashed):** stacking takes "Set number of shots" clamped to 3-8. All 12 native reads of
  1448 (10 via getter 0x602e69f9, 2 via 0x602c782a in that interlock) go to a 164-byte routine at 0x600d0140; 1448 itself
  is never written. Variants on stock+any-lens and on E10f; address check PASS. [code]

- 2026-11-06: the native stack merge is the movie/still request engine type 5 (shot kind 19): step 1 `0x603804c6` accepts 3-15
  frames plus a reference index, so the merge chain allows 15; it aligns each frame (motion vectors + DSP job 4 warp) and merges
  with jobs 5/3/6/7; output 4480×3360. [code]/[inferred]

