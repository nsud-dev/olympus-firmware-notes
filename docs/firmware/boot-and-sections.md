# Boot, section loading, flashing and recovery

## Load base
- Block0 analysis base **VMA = 0x60021020 + offset in the decoded block0 payload** (same on every body). The boot
  stub runs first at 0x40780020 (OM-1: header addr 0x50000000, jumps to 0x600210c5). [code]

## Sections load in the background (important for hooks)
- The boot stub copies only **0x60030000-0x600d0800**. That range is always ready. [code]
  The copy is flash 0x4078f000 → 0xa0030000 by 0x60022180, length from the end immediate **0x600d0800 at 0x600211af**. The
  54 KB after it (0x600d0800-0x600de000, up to section 1) is 0xFF in the image and unreferenced: raising that one immediate
  makes it always ready (second guard area). 2026-11-05 [code]
- Section 10 ends at **0x61478000** (immediate at 0x60045e24); the image after it is 0xFF padding to 0x61800fe0, never
  loaded. 2026-11-05 [code]
- The rest of block0 is **10 sections** read from flash by a loader task while boot continues: loader 0x60045e2e,
  table 0x600272a4, ends in the switch at 0x60045dc5. Load order 1, 7, 2, 3, 4, 5, 6, 8, 9, 10. [code]
- Loaded bits at 0xa26565c4; **ready bits at 0xa26565c0**, set by the waiter **0x60045eb3(n)** (MMU/cache setup +
  section init); **0x60045d92(n)** returns 1 when section n is ready. Section 4 = bit 3; section 9 = 0x100. [code]

| section | range |
|---|---|
| 1 | 0x600de000-0x6022d800 |
| 2 | 0x60298000-0x6056c000 |
| 3 | 0x60582000-0x605d4000 |
| 4 | 0x605da800-0x6079d800 stock (0x607b6800 since cave test 2) |
| 5 | to 0x60bef800 |
| 6 | 0x60c17000-0x61124000 |
| 9 | 0x61209800-0x613bb000 stock (0x613d4000 since webcam test 1) |

- Section-4 cave allocation (E10f line): 0x6079d800..0x6079e000 free; **0x6079e000..0x6079e141 Starry Sky AF S1**; 0x6079e141..0x607a0000
  free; 0x607a0000.. Live ND (0x607a0200..0x607a0400, 0x607a9cc0..0x607aa000, 0x607ab007..0x607b2000, 0x607ad300..0x607ae000,
  0x607b3e80..0x607b4800). Hooks inside section 4 that jump to section-4 code need no boot guard. 2026-11-05 [code]


- Boot order (trace tags from 0x60023bbc): `2_1` section 2 ready → tasks STB_SEQ, TAKE_EXPOSE, DSP0/DSP1, MVR,
  UI_OUT created → section 3 → **`3_4` section 4 ready (0x6019cf48)** → FCS, face detect, REC, USB (PC3/PC4),
  ISEQ → sections 5, 6 → `5_1` sections 7-10. [code]
- **Consequence:** a hook in an early section that jumps into section-4 or section-9 code can run before that code is
  in RAM. This caused the intermittent "dead at power-on" / "live view then reset loop" on Live ND builds
  (E9b's 0x601fce30 hook in section 1 was the prime suspect). Fix used since E10b: guards in always-ready code test
  the ready bit and fall back to the original instructions. [code], fix confirmed by 10/10 boots on E10b [camera].
- Stock never makes such forward jumps without waiting. [code]

## Flashing (the maintainer's procedure)
- 2026-11-07: full updater analysis, flash map, write order, recovery procedure and build safety rules are on
  [Recovery](recovery.md). The card updater validates every component before writing and writes block0 last. [code]
- Copy the build to the SD card as **`e1379999.bin`** (the maintainer renames; build files keep descriptive names), **hold OK
  while powering on**. The AF/tally lamp is solid while flashing and blinks when done; no screen UI. [camera]
- The SD updater is in block0 itself (task `FIRMUP_CLI`, strings `E137????BIN`, `DCOLYMP`), as on E-P7/PEN-F.
  USB update is also started by block0 (`start_usb_firmup` 0x609ee601). So **recovery needs block0 to boot far
  enough**; there's no proven independent loader. Keep boot paths stock and hooks guarded. [code]
  (An earlier note that card update ran from a separate loader was corrected 2026-11-04.)
- Block 3 (~~loader/debug monitor~~ 2026-11-06: very likely the **IS sub-CPU program "LUKE"**, see [stabiliser](../hardware/stabiliser.md) [inferred]) is body-specific; cross-flashing another body's image would risk a brick. [code]
`em5iii-firmware-format`,.
