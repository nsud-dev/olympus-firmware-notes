# Focus stacking lens check: patch (flashed and working on camera, 2026-10-19)

Function `fcs_check_focus_stacking_enable` at VMA 0x6065e5d6 (block0 payload offset 0x63d5b6),
called once, from 0x6065d2db:

    6065e5d6  clr  d2                    ; result = 0
    6065e5d7  call 0x60206a03            ; lens-type check (used in 9 places)
    6065e5df  cmp  d2,d0 / bne 0x6065e5f0 ; nonzero -> not allowed
    6065e5e2  call 0x60210c39            ; returns lens_info[+0x1bc9f] == 1 (per-lens "supports stacking" flag)
    6065e5ea  cmp  1,d0
    6065e5ec  bne  0x6065e5f0            ; <-- patched to NOP NOP
    6065e5ee  mov  1,d2                  ; result = 1
    ... debug print "fcs_check_focus_stacking_enable stacking", return d2

Patch: 0x6065e5ec `c9 04` -> `cb cb`. Stacking is allowed for any lens that passes the first
lens-type check (that check is shared with 8 other callers, so it's left alone).

| where | offset | stock | patched |
|---|---|---|---|
| block0 decoded payload | 0x63d5cc | c9 04 | cb cb |
| .BIN file (encoded) | 0x63d5ed, 0x63d5ee | 0x36 0xfb | 0x34 0x34 |
| block0 trailer checksum | file 0x17dfffc..ff | 4b 55 c1 27 | 49 8e c0 27 (last byte unchanged) |

Built with `olyfw.py repack`; `olyfw.py info` reports all block checksums OK.
Output: OLY_E_137_1700_focusstack_any_lens.BIN (same version number as stock).
