# Boot and section loading

<!-- house style -->
> **Technical reading.** The detailed version of [Boot](../guides/boot.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

When the camera powers on, its main program (block0) is not copied into RAM all at once. A small part is copied
straight away and the rest arrives in ten "sections" that load in the background while the camera is already starting
up. This page explains that process, because it is the main reason a patch can work most of the time and still fail to
boot now and then. It also covers how firmware is flashed from the SD card.

The rule that comes out of it is simple. A hook that jumps into code in a later section must first check that the
section has loaded. We call that check a "boot guard".

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred, amber = a correction.

## Addresses

The main program is analysed at **address = `0x60021020` + offset in the decoded block0 payload**. The base is the same
on every body.[^fw1] The boot stub runs first, from block0 in flash. On the OM-1 the header address is
different and the stub jumps to its own entry.[^fw1] Both are in the [address reference](#address-reference).

## Boot stub

Read off the stock disassembly from the entry point, statically.[^fw2]

1. **Entry.** It masks interrupts (`and 0xf0ff,psw`) and calls two small set-up routines, which set bits 0-1 of a CPU
   register.[^fw2]
2. **Vectors.** It writes eight half-words to the CPU registers `0x8000` to `0x801c`, with the low halves of handler
   addresses in the always-ready range.[^fw2] That these are the interrupt vector registers is inferred.[^inf1]
3. **RAM set-up.** It runs one RAM set-up routine over two ranges.[^fw2] It probably clears them.[^inf1]
4. **Stack.** It sets the stack pointer and jumps to the main stub.[^fw2]

The main stub prints three-letter trace marks around each step.[^fw2]

| marks | step |
|---|---|
| `RCS`, `RCE` | writes registers for the debug UART set-up[^fw3] |
| `F0S`, `F0E` | **six copies** through one copy routine |
| `GIS`, `GIE` | one call |
| `DSS`, `DSE` | one call |
| `OIS` | then a jump through the always-ready code to the OS start[^inf1] |

*Trace marks of the boot stub, in order. The functions are in the [address reference](#address-reference).*

See also: [OS and framework](os-and-framework.md#debug-serial-port).

### The six copies

| source in flash | destination | length | contents |
|---|---|---:|---|
| `0x4078f000` | `0xa0030000` | `0xa0800` | the always-ready code |
| `0x409af000` | `0xa1e8b540` | `0x32d10` | initialised data[^inf1] |
| `0x409e7000` | `0xa1ec3540` | `0x48c4` | initialised data[^inf1] |
| `0x409ef000` | `0xa1ecb540` | 4 | initialised data[^inf1] |
| `0x409f3000` | `0xa1ecf540` | `0x2d2c` | initialised data[^inf1] |
| `0x41be2000` | `0xa1483000` | `0x1800` | the 6 KB fast-memory block |

*The six F0 copies.[^fw2] The lengths come from end immediates, such as `0x600d0800` for the code.*

### Fast memory

After `F0E` the stub copies the 6 KB block once more, word by word, with a `setlb`/`lcs` loop of 1536 words. The copy
goes to the start of a small memory.[^fw2]

- The stack starts there and grows down.[^fw2]
- memcpy, memset and the watchdog kick run there.[^fw2]
- So that 8 KB memory holds the boot stack and hot helper routines.[^fw2]
- What kind of memory it is, perhaps on-chip SRAM, is inferred.[^inf1]

## Start-up stages 0 and 1

Two always-ready functions print the `0_x` and `1_x` trace tags.[^fw2]

**Stage 0** prints `0_1` to `0_*` and `0_v`.[^fw2]

1. Debug init (`dbg_init`) and many driver inits.
2. `QIS`, `QIE`.
3. It starts the first tasks with `OlyTaStCpu`: **PER_WDT** (id 25, watchdog kicker), **PER_PCONT** (power control),
   **BCHK_MAIN** (battery check), the `PC1` and `PC2` marks, and **PER_IN** (inputs). The task roles come from their
   names.[^inf1]
4. It ends by calling stage 1.

**Stage 1** prints `1_1` to `1_8`.[^fw2]

1. It logs the names USR_PCHG, USTART_L, USTART_L1 and USTART_L2 around three `OlyTaStCpu` task starts. In stage 0 each
   name is logged just after its start, which would make these the three USTART_L tasks.[^inf1]
2. It waits for section 1 with the section waiter.
3. `1_6` starts `PWR_STANDBY`.
4. `1_7`, `1_8`.

Stages 2 to 5 (`2_1` to `5_5`) are in section 1. See [Boot order](#boot-order-and-why-hooks-need-a-guard)
below.[^fw2]

### Section loader tasks

The section loader runs in its own tasks. The first loader function prints the trace `M_0`, `M_e` and `M_*`, calls
`boot_ram_section_loader` twice and has no direct callers, so it is a task entry.[^fw2]

- **USRSTART_LOAD_1**, a CPU1 task (id `0x1018`), loads sections 1 and 7.[^fix1]
- **USRSTART_LOAD_2**, a CPU2 task (id `0x2015`), loads sections 2 to 6 and 8 to 10.[^fix1]
- The two hand off through a progress word, gated by CPU0's stages.[^fix1]

See also: [CPU1 and CPU2](../hardware/cpu1-cpu2-technical.md#start-up).

## Sections load in the background

### The always-ready part

The boot stub copies only the range from block0's start code up to the end immediate `0x600d0800`, so that range is
ready before anything else runs.[^fw5] The copy goes from flash through the copy routine, and its length comes from
that one end immediate.

The 54 KB after it, up to section 1, is `0xff` in the image and unreferenced. Raising that one immediate would make it
always ready too, a second guard area.[^fw5]

### The ten sections

The rest of block0 is **10 sections**, read from flash by a loader task while boot continues. The loader uses a section
table and ends in an end-address switch.[^fw1]

- They are read in number order, 1 to 10.[^fix1]
- Sections 1 and 7 are read by CPU1, the rest by CPU2.[^fix1]
- CPU1 waits for CPU2's section 6 bit before reading section 7.[^fix1]

| section | stock range | end in our test builds |
|---:|---|---|
| 1 | `0x600de000`–`0x6022d800` | |
| 2 | `0x60298000`–`0x6056c000` | `0x60582000` since a looks test build[^cam1] |
| 3 | `0x60582000`–`0x605d4000` | |
| 4 | `0x605da800`–`0x6079d800` | `0x607b6800` since cave test 2 |
| 5 | to `0x60bef800` | |
| 6 | `0x60c17000`–`0x61124000` | |
| 9 | `0x61209800`–`0x613bb000` | `0x613d4000` since webcam test 1 |

*Section ranges in block0. The last column is the raised end some of our test builds use.[^fw1]*

**Section 10** ends at an end immediate. After it the image is `0xff` padding to near the end of block0, which is
never loaded.[^fw5]

- The first 32 KB after section 10 is in block0 and all `0xff`, in stock and in our Live ND test base.[^fw5]
- Nothing refers to it or its `0xa147` alias directly. A byte search found 35 matches. All were coincidental call
  operands or unaligned overlaps, and the only `fc` hit was the end immediate.[^fw5]
- The section 10 length is computed from the end helper by the loader and by two access-monitor paths. So raising the
  end constant moves all three.[^fw5][^fix3]

### Loaded is not usable

> [!WARNING]
> A hook that jumps into a later section before that section is ready can boot-loop the camera. A test build did
> exactly that. The card updater still brought it back.

Sections become *ready* in index order. Sections 2 to 6 come one by one, then 7 to 10 together at `5_1`.[^fix2] Until
section n+1 is finalised, the access monitor covers everything from the start of section n+1 to the end of section 10.
The window starts at section n+1's table entry and ends at the section 10 end.[^fix2] So section 7 may not be touched
before section 6 is ready.

A test build jumped from boot-time hooks in section 2 into the section 7 gap. The hooks were a getter and an option
hash. The build boot-looped, with the stabiliser starting and dying. The card updater still recovered it.[^cam1]
om-emu does not model the monitor, and an early version of our pre-flash check used the read order.[^cam1]

**The rule.** A hook may jump only into sections with a lower index than its own, or through a ready-bit guard placed
in its own section.[^cam1]

### Ready bits

There is a word of loaded bits and a word of ready bits.[^fw1]

- The waiter (argument n) sets a ready bit after MMU and cache set-up and section init.
- The ready test (argument n) returns 1 when section n is ready.
- Section n is bit n-1 (`1 << (n-1)`). Section 4 is bit 3, section 9 is `0x100` and section 10 is `0x200`.[^fw6]

### Access monitor

After finalising section n < 10, the loader programs a hardware access monitor. Its window runs from section n+1
onward. Then the loader sets the ready bit.[^fw2]

- The monitor's end is **inclusive**. The firmware's permanent table ends ranges at ...`fff`.[^fw7]
- The loader passes the section 10 end, the first byte after it, so the window also covers that next byte.[^fw7]
- After section 10, the monitor driver loads a permanent guard table for the unmapped gaps.[^fix3]
- The design is the same as the OM-5 II's, which caduceus-om5 research describes.[^fw2]

What the monitor traps is unknown. That is another reason never to touch a later section's range before its ready
bit.[^fw2]

See also: [Caches](../hardware/caches-technical.md#the-access-monitor-0x99700000).

### Section 4 spare space

Our Live ND test base shares section 4's spare space like this.[^fw5]

| range | use |
|---|---|
| `0x6079d800`–`0x6079e000` | free |
| `0x6079e000`–`0x6079e141` | **Starry Sky AF test** |
| `0x6079e141`–`0x607a0000` | free |
| from `0x607a0000` | Live ND (`0x607a0200`–`0x607a0400`, `0x607a9cc0`–`0x607aa000`, `0x607ab007`–`0x607b2000`, `0x607ad300`–`0x607ae000`, `0x607b3e80`–`0x607b4800`) |

*Use of section 4's spare space in our Live ND test base.*

Hooks inside section 4 that jump to section 4 code need no boot guard.[^fw5]

## Boot order, and why hooks need a guard

The firmware prints trace tags as it boots. The order is as follows.[^fw1]

1. `2_1`: section 2 ready. Tasks STB_SEQ, TAKE_EXPOSE, DSP0/DSP1, MVR and UI_OUT are created.
2. Section 3.
3. **`3_4`: section 4 ready.** FCS (focus), face detect, REC, USB (PC3/PC4) and ISEQ start.
4. Sections 5 and 6.
5. `5_1`: sections 7 to 10.

**The consequence.** A hook placed in an early section that jumps into section 4 or section 9 code can run before that
code is in RAM.[^fw1] That caused the intermittent "dead at power-on" and "live view then reset loop" failures on Live
ND builds. A hook in section 1 was the prime suspect.[^fw1]

**The fix**, used since then, is guard code in the always-ready range. It tests the ready bit and falls back to the
original instructions if the section isn't there yet.[^fw1] The fix was confirmed by 10 out of 10 boots.[^cam2]

The stock firmware never makes such forward jumps without waiting.[^fw1]

## Flashing

- Copy the build to the SD card as **`e1379999.bin`** and **hold OK while powering on**. The file is renamed for
  flashing, and build files keep their descriptive names. The AF/tally lamp stays on while flashing and blinks when done. There is no screen
  UI.[^cam2]
- The card updater checks every component before writing and writes block0 last.[^fw1] The full updater analysis, flash
  map, write order, recovery procedure and build safety rules are on [Recovery](recovery-technical.md).[^fw4]
- The SD updater lives in block0 itself, as on the E-P7 and PEN-F. It is task `FIRMUP_CLI`, with the strings
  `E137????BIN` and `DCOLYMP`. USB updates are also started by block0 (`start_usb_firmup`).[^fw1]
- So **recovery needs block0 to boot far enough**, and there's no proven independent loader. Keep the boot paths stock
  and hooks guarded.[^fw1]
- SD-updater code, the functions that use `E137????BIN`, `DCOLYMP` and `FIRMUP_CLI`, reaches 1,328 functions by direct
  calls. C builds must keep these, and the boot and USB-update paths, stock. Our playback C build (258 functions)
  touches none of them.[^fw5]

> [!WARNING]
> Block 3 is body-specific. Flashing another body's image could brick the camera.[^fw1]

Block 3 is very likely the **IS sub-CPU program "LUKE"**.[^inf2] See [Stabiliser](../hardware/stabiliser.md).

## Address reference

E-M5 III 1.7 block0 addresses (base `0x60021020`) unless a body is named.

| item | address |
|---|---|
| boot stub start | `0x40780020` |
| OM-1 header address, OM-1 entry | `0x50000000`, `0x600210c5` (OM-1) |
| entry | `0x60021020` |
| set-up routines (bits 0-1 of CPU register `0x8070`) | `0x600210e9`, `0x600210de` |
| vector registers, handler addresses | `0x8000`–`0x801c`. `0x60030020`, `0x60030058` ... `0x60030080` |
| RAM set-up routine, ranges | `0x60021486`. `0x61f22900`–`0x61f27670`, `0x62527100`–`0x626b0888` |
| initial stack pointer | `0x470007fc` |
| main stub | `0x600210f9` |
| `RCS`/`RCE` routine, registers written | `0x600213a9`. `0x8ff0005c`, `0x988001xx`, `0x987000xx` |
| copy routine (F0) | `0x60022180` |
| `GIS`/`GIE`, `DSS`/`DSE` calls | `0x6006783d`, `0x600547de` |
| OS start jump | `jmp 0x6003009c` → `0x60032696` |
| code end immediate | `0x600d0800`, at `0x600211af` |
| fast-memory copy loop | `0x60021278`, `0xa1483000` → `0x47000800` |
| fast memory, helpers in it | `0x47000000`–`0x47002000`. memcpy `0x47001024`, memset `0x47001130`, watchdog kick `0x4700101b` |

*Boot stub.*

| item | address |
|---|---|
| stage 0 | `0x60045103` |
| `QIS`/`QIE` | `0x60051336` |
| `OlyTaStCpu` | `0x6005185f` |
| PER_WDT set-up | `0x600741b2` |
| stage 1 | `0x60045841` |
| stage 1 task ids | from `0x60040b68`, `0x60041132`, `0x60041294` |
| `1_6` (`PWR_STANDBY`) | `0x6005f868` |
| USRSTART_LOAD_1 entry | `0x60045513` |
| USRSTART_LOAD_2 entry | `0x60045599` |
| loader hand-off progress word | `0xa265658c` |
| stages 2 to 5 | `0x6019c9b9`, `0x6019cdfe` |
| trace tag printer | `0x60023bbc` |
| `3_4`, section 4 ready | `0x6019cf48` |

*Start-up stages.*

| item | address |
|---|---|
| always-ready range | `0x60030000`–`0x600d0800`, copied from flash `0x4078f000` to `0xa0030000` |
| spare area after it | `0x600d0800`–`0x600de000` |
| section loader, section table | `0x60045e2e`, `0x600272a4` |
| loader's section 10 length use | `0x60045e33` |
| end-address switch (end helper) | `0x60045dc5` |
| section 10 end immediate | `0x61478000`, at `0x60045e24` |
| padding after section 10 | to `0x61800fe0`. Unused block `0x61478000`–`0x61480000` |
| CPU1 wait for section 6 | `0x60045543` |
| loaded bits, ready bits | `0xa26565c4`, `0xa26565c0` |
| section waiter, ready test | `0x60045eb3(n)`, `0x60045d92(n)` |
| access-monitor window built | `0x60045f0c`..`0x60045f40` (start = table[n].+8, end = `0x60045dc5(10)`) |
| access-monitor paths | `0x60045f0c`, `0x60045fc6` |
| access-monitor registers, driver | `0x99700040`/`44`.. (`0x997000xx`), `0x60065a6a` |
| after section 10 | `0x60065f63`, `0x60045eed`. `0x60065f63` → `0x60065991` loads the guard table `0x600c07f0` |
| ready bit set | `0x60045f95`..`0x60045f9d` |
| section 2 hooks of the boot-looping build | getter `0x602e6a02`, option hash `0x602d3f82` |
| section 1 hook, prime suspect for boot failures | `0x601fce30` |

*Section loading.*

| item | address |
|---|---|
| `start_usb_firmup` | `0x609ee601` |
| SD-updater code | `api_firmup.c` `0x602e50d8`..`0x602e53c8`, `0x60c3a1b3`, `0x60c3a482` |

*Updater.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware.
[^fw2]: Read in the firmware, 2026-11-19. Static reading of the stock disassembly.
[^fw3]: Read in the firmware, 2026-11-23.
[^fw4]: Analysed in the firmware, 2026-11-07.
[^fw5]: Read in the firmware, 2026-11-05.
[^fw6]: Read in the firmware, 2026-11-17. The bit rule comes from the ready test.
[^fw7]: Read in the firmware, 2026-11-22.
[^inf1]: Inferred, 2026-11-19.
[^inf2]: Inferred, 2026-11-06.
[^cam1]: Seen on our E-M5 III using test firmware, 2026-11-19.
[^cam2]: Seen on our E-M5 III.
[^fix1]: Corrected 2026-11-25, read in the firmware. The older reading is in [History](#history).
[^fix2]: Corrected 2026-11-19 after a camera test. The older reading is in [History](#history).
[^fix3]: Corrected 2026-11-22, read in the firmware. The older reading is in [History](#history).

## History

- 2026-11-04: an earlier note said card updates ran from a separate loader. Corrected: the SD updater lives in block0.
- 2026-11-06: block 3 was first taken for a loader or debug monitor. It is very likely the IS sub-CPU program "LUKE".
- 2026-11-19: the section loader task was thought to be one of the USTART_L tasks. Corrected 2026-11-25: it is
  USRSTART_LOAD_1, a CPU1 task.
- 2026-11-19: loaded was taken to mean usable. A camera test showed a section is usable only once its ready bit is
  set.
- 2026-11-22: the two access-monitor paths were first called "cache paths". They program the access monitor.
- 2026-11-22: the access monitor was read as switched off after section 10. It loads a permanent guard table instead.
- 2026-11-25: the sections were thought to load in the order 1, 7, 2, 3, 4, 5, 6, 8, 9, 10. They are read in number
  order, sections 1 and 7 by CPU1 and the rest by CPU2. The ready-bit rule is unchanged.

