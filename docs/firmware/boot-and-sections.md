# Boot, section loading, flashing and recovery

When the camera powers on, its main program (block0) is not copied into RAM all at once. A small part is copied
straight away and the rest arrives in ten "sections" that load in the background while the camera is already starting
up. This page explains that process, because it is the main reason a patch can work most of the time and still fail to
boot now and then. It also covers how firmware is flashed from the SD card.

The rule that comes out of it: a hook that jumps into code in a later section must first check that the section has
loaded (a "boot guard").

Tags: **[code]** read in the firmware, **[camera]** seen on a real E-M5 III, **[inferred]** not traced or tested.

## Addresses

The main program is analysed at **address = 0x60021020 + offset in the decoded block0 payload** (the same on every
body). The boot stub runs first at 0x40780020 (on the OM-1 the header address is 0x50000000 and it jumps to
0x600210c5). [code]

## Sections load in the background

**The always-ready part.** The boot stub copies only **0x60030000-0x600d0800**, so that range is ready before anything
else runs. [code] The copy goes from flash 0x4078f000 to 0xa0030000 through 0x60022180, and its length comes from the end
immediate **0x600d0800 at 0x600211af**. The 54 KB after it (0x600d0800-0x600de000, up to section 1) is 0xFF in the image
and unreferenced, so raising that one immediate would make it always ready too (a second guard area). 2026-11-05 [code]


**The ten sections.** The rest of block0 is **10 sections**, read from flash by a loader task while boot continues:
loader 0x60045e2e, table 0x600272a4, ending in the switch at 0x60045dc5. They load in the order 1, 7, 2, 3, 4, 5, 6, 8,
9, 10. [code]

| section | range |
|---|---|
| 1 | 0x600de000-0x6022d800 |
| 2 | 0x60298000-0x6056c000 |
| 3 | 0x60582000-0x605d4000 |
| 4 | 0x605da800-0x6079d800 stock (0x607b6800 since cave test 2) |
| 5 | to 0x60bef800 |
| 6 | 0x60c17000-0x61124000 |
| 9 | 0x61209800-0x613bb000 stock (0x613d4000 since webcam test 1) |

Section 10 ends at **0x61478000** (immediate at 0x60045e24); after it the image is 0xFF padding to 0x61800fe0 and is
never loaded. 2026-11-05 [code]

- [code] 2026-11-05: stock and E10f both: 0x61478000-0x61480000 is in block0 and all 0xFF; no direct reference to it or its 0xa147 alias (35 byte matches, all coincidental call operands or unaligned overlaps; only `fc` hit = the end immediate); section-10 length is computed from the end helper 0x60045dc5 by the loader (0x60045e33) and two cache paths (0x60045f0c, 0x60045fc6), so raising the end constant moves all three. Source: private notes results/precheck/, results/REVIEW.md

**How to tell whether a section is ready.** Loaded bits are at 0xa26565c4 and **ready bits at 0xa26565c0**. The waiter
**0x60045eb3(n)** sets a ready bit after MMU/cache setup and section init, and **0x60045d92(n)** returns 1 when section n
is ready. Section 4 is bit 3; section 9 is 0x100. [code]

**How we share section 4's spare space** (E10f line): 0x6079d800..0x6079e000 free; **0x6079e000..0x6079e141 Starry Sky
AF S1**; 0x6079e141..0x607a0000 free; 0x607a0000.. Live ND (0x607a0200..0x607a0400, 0x607a9cc0..0x607aa000,
0x607ab007..0x607b2000, 0x607ad300..0x607ae000, 0x607b3e80..0x607b4800). Hooks inside section 4 that jump to section-4
code need no boot guard. 2026-11-05 [code]

## Boot order, and why hooks need a guard

The firmware prints trace tags as it boots (from 0x60023bbc). The order is: [code]

1. `2_1`: section 2 ready; tasks STB_SEQ, TAKE_EXPOSE, DSP0/DSP1, MVR and UI_OUT are created.
2. Section 3.
3. **`3_4`: section 4 ready (0x6019cf48)**; FCS (focus), face detect, REC, USB (PC3/PC4) and ISEQ start.
4. Sections 5 and 6.
5. `5_1`: sections 7-10.

**The consequence:** a hook placed in an early section that jumps into section-4 or section-9 code can run before that
code is in RAM. That caused the intermittent "dead at power-on" and "live view then reset loop" failures on Live ND
builds (E9b's hook at 0x601fce30, in section 1, was the prime suspect). The fix, used since E10b: guard code in the
always-ready range tests the ready bit and falls back to the original instructions if the section isn't there yet.
[code], fix confirmed by 10/10 boots on E10b [camera]

The stock firmware never makes such forward jumps without waiting. [code]

## Flashing (the maintainer's procedure)

- Copy the build to the SD card as **`e1379999.bin`** (the maintainer renames it; build files keep descriptive names) and **hold
  OK while powering on**. The AF/tally lamp stays on while flashing and blinks when done; there is no screen UI.
  [camera]
- The full updater analysis, flash map, write order, recovery procedure and build safety rules (2026-11-07) are on
  [Recovery](recovery.md). The card updater checks every component before writing and writes block0 last. [code]
- The SD updater lives in block0 itself (task `FIRMUP_CLI`, strings `E137????BIN`, `DCOLYMP`), as on the E-P7 and
  PEN-F. USB updates are also started by block0 (`start_usb_firmup` 0x609ee601). So **recovery needs block0 to boot far
  enough**; there's no proven independent loader. Keep the boot paths stock and hooks guarded. [code] (An earlier note
  that card updates ran from a separate loader was corrected 2026-11-04.)
- Block 3 is body-specific; cross-flashing another body's image could brick the camera. [code] We first took block 3
  for a loader/debug monitor; since 2026-11-06 it is very likely the **IS sub-CPU program "LUKE"**, see
  [stabiliser](../hardware/stabiliser.md). [inferred]
`em5iii-firmware-format`,.
