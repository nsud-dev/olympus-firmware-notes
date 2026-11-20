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

## What the boot stub does (2026-11-19)

Read off the stock disassembly from the entry point (static only). [code] unless marked.

- **Entry 0x60021020:** masks interrupts (`and 0xf0ff,psw`), calls two small set-up routines (0x600210e9, 0x600210de:
  sets bits 0-1 of the CPU register at 0x8070), writes eight half-words to 0x8000-0x801c with the low halves of
  0x60030020, 0x60030058 ... 0x60030080 (handler addresses in the always-ready range; that these are the interrupt
  vector registers is [inferred]), runs two RAM set-up calls 0x60021486 over 0x61f22900-0x61f27670 and
  0x62527100-0x626b0888 (probably clearing them, [inferred]), sets sp = 0x470007fc and jumps to 0x600210f9. [code]
- **Stub 0x600210f9** prints three-letter trace marks around each step: `RCS`/`RCE` (0x600213a9, writes registers at
  0x8ff0005c, 0x988001xx, 0x987000xx: memory/clock set-up, [inferred]); **`F0S`/`F0E`: six copies through 0x60022180**;
  `GIS`/`GIE` (0x6006783d); `DSS`/`DSE` (0x600547de); `OIS`, then `jmp` 0x6003009c → **0x60032696** in the always-ready
  code (OS start, [inferred]). [code]
- **The six copies (F0):** flash 0x4078f000 → 0xa0030000, 0xa0800 bytes (the always-ready code); four
  initialised-data blocks 0x409af000 → 0xa1e8b540 (0x32d10), 0x409e7000 → 0xa1ec3540 (0x48c4), 0x409ef000 →
  0xa1ecb540 (4), 0x409f3000 → 0xa1ecf540 (0x2d2c); and 0x41be2000 → 0xa1483000 (0x1800). The lengths come from end
  immediates (0x600d0800 at 0x600211af for the code). [code] That the four blocks are the program's initialised data
  is [inferred].
- **After F0E** the stub copies the 6 KB block once more, word by word (a `setlb`/`lcs` loop at 0x60021278, 1536
  words), from 0xa1483000 to **0x47000800**. That is where the stack starts (sp = 0x470007fc, growing down) and where
  memcpy 0x47001024, memset 0x47001130 and the watchdog kick 0x4700101b run, so 0x47000000-0x47002000 is a small
  memory that holds the boot stack and hot helper routines. [code] (2026-11-19) What kind of memory it is (on-chip
  SRAM?) is [inferred].

## Start-up stages 0 and 1 (2026-11-19)

Two always-ready functions print the `0_x` and `1_x` trace tags. [code]

- **Stage 0, 0x60045103** (`0_1` ... `0_*`, `0_v`): debug init (`dbg_init`), many driver inits, `QIS`/`QIE`
  (0x60051336), then starts the first tasks with `OlyTaStCpu` 0x6005185f: **PER_WDT** (id 25, watchdog kicker, set-up
  0x600741b2), **PER_PCONT** (power control), **BCHK_MAIN** (battery check), `PC1`/`PC2` marks, **PER_IN** (inputs).
  It ends by calling stage 1. [code] (task roles from their names, [inferred])
- **Stage 1, 0x60045841** (`1_1` ... `1_8`): logs the names USR_PCHG, USTART_L, USTART_L1 and USTART_L2 around three
  `OlyTaStCpu` task starts (ids from 0x60040b68, 0x60041132, 0x60041294; in stage 0 each name is logged just after its
  start, which would make them the three USTART_L tasks, [inferred]), then waits for section 1 with 0x60045eb3(1), then `1_6` (0x6005f868, `PWR_STANDBY`) and `1_7`/`1_8`. [code]
- The section loader runs in its own task: function 0x60045513 (trace `M_0`, `M_e`, `M_*`) calls
  `boot_ram_section_loader` twice and has no direct callers (a task entry). That it is one of the USTART_L tasks is
  [inferred].
- Stages 2-5 (`2_1` ... `5_5`) are in section 1 (0x6019c9b9, 0x6019cdfe); see the boot order below. [code]

## Sections load in the background

**The always-ready part.** The boot stub copies only **0x60030000-0x600d0800**, so that range is ready before anything
else runs. [code] The copy goes from flash 0x4078f000 to 0xa0030000 through 0x60022180, and its length comes from the end
immediate **0x600d0800 at 0x600211af**. The 54 KB after it (0x600d0800-0x600de000, up to section 1) is 0xFF in the image
and unreferenced, so raising that one immediate would make it always ready too (a second guard area). 2026-11-05 [code]


**The ten sections.** The rest of block0 is **10 sections**, read from flash by a loader task while boot continues:
loader 0x60045e2e, table 0x600272a4, ending in the switch at 0x60045dc5. They load in the order 1, 7, 2, 3, 4, 5, 6, 8,
9, 10. [code]
- **Correction 2026-11-19 [camera]: loaded is not usable.** Sections become *ready* in index order (2, 3, 4, 5, 6, then
  7-10 at `5_1`), and until section n+1 is finalised the access monitor covers **[start of section n+1 .. end of
  section 10]** (window built at 0x60045f0c..0x60045f40: start = table[n].+8, end = 0x60045dc5(10)). So section 7,
  though read second, may not be touched before section 6 is ready. A test build jumped from boot-time hooks in
  section 2 (getter 0x602e6a02, option hash 0x602d3f82) into the section-7 gap and boot-looped (stabiliser starts
  and dies); the card updater still recovered it. om-emu does not model the monitor, and an early version of our pre-flash check used the read order.
  Rule: a hook may jump only into sections with a lower index than its own, or through a ready-bit guard placed in its
  own section.

| section | range |
|---|---|
| 1 | 0x600de000-0x6022d800 |
| 2 | 0x60298000-0x6056c000 stock (0x60582000 since a looks test build, camera-proven 2026-11-19 [camera]) |
| 3 | 0x60582000-0x605d4000 |
| 4 | 0x605da800-0x6079d800 stock (0x607b6800 since cave test 2) |
| 5 | to 0x60bef800 |
| 6 | 0x60c17000-0x61124000 |
| 9 | 0x61209800-0x613bb000 stock (0x613d4000 since webcam test 1) |

Section 10 ends at **0x61478000** (immediate at 0x60045e24); after it the image is 0xFF padding to 0x61800fe0 and is
never loaded. 2026-11-05 [code]

- [code] 2026-11-05: stock and our Live ND test base both: 0x61478000-0x61480000 is in block0 and all 0xFF; no direct reference to it or its 0xa147 alias (35 byte matches, all coincidental call operands or unaligned overlaps; only `fc` hit = the end immediate); section-10 length is computed from the end helper 0x60045dc5 by the loader (0x60045e33) and two cache paths (0x60045f0c, 0x60045fc6), so raising the end constant moves all three. Source: private notes results/precheck/, results/REVIEW.md

**How to tell whether a section is ready.** Loaded bits are at 0xa26565c4 and **ready bits at 0xa26565c0**. The waiter
**0x60045eb3(n)** sets a ready bit after MMU/cache setup and section init, and **0x60045d92(n)** returns 1 when section n
is ready. Section n is bit n-1 (`1 << (n-1)`): section 4 is bit 3, section 9 is 0x100, section 10 is 0x200. [code] (2026-11-17 bit rule from 0x60045d92)
- 2026-11-19: after finalising section n < 10 the loader programs a hardware access monitor (0x99700040/44.., driver 0x60065a6a, window from section n+1 onward, built at 0x60045f0c..0x60045f40) and turns it off after section 10 (0x60065f63, 0x60045eed); then it sets the ready bit (0x60045f95..0x60045f9d). Same as the OM-5 II (caduceus-om5 research). What it traps is unknown: another reason never to touch a later section's range before its ready bit. [code]

**How we share section 4's spare space** (our Live ND test base): 0x6079d800..0x6079e000 free; **0x6079e000..0x6079e141 Starry Sky
AF test**; 0x6079e141..0x607a0000 free; 0x607a0000.. Live ND (0x607a0200..0x607a0400, 0x607a9cc0..0x607aa000,
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
builds (a hook at 0x601fce30, in section 1, was the prime suspect). The fix, used since then: guard code in the
always-ready range tests the ready bit and falls back to the original instructions if the section isn't there yet.
[code], fix confirmed by 10/10 boots [camera]

The stock firmware never makes such forward jumps without waiting. [code]

## Flashing

- Copy the build to the SD card as **`e1379999.bin`** (rename a copy; build files keep descriptive names) and **hold
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
