# Power and watchdog block: technical notes

> **Technical notes.** This page is the dense reference. For a readable introduction, start with [Power and watchdog block](power-block.md).

Addresses are E-M5 III 1.7 block0 VMAs unless a body is named. Written 2026-11-23. Disassembly: mn10300-elf objdump on
(`--adjust-vma=0x60021020`). The 6 KB fast-memory library at 0x47000800 is block0 file offset 0x1461fe0
(flash 0x41be2000, copied there by the boot stub).

## Summary

- **No power sub-CPU on the E-M5 III** [code]+[inferred] 2026-11-23. Earlier pages called the window 0x98e00000 "the
  power sub-CPU". The register use reads as a small always-on block of the SoC: a seconds clock, 14 backup words, five
  wake inputs, two alarms, a watchdog, a power-off request and the power-on cause flags. The main CPU writes shadow
  registers and then commits them with 0x20041001 at +0xa4. Nothing is sent as a message, and nothing answers.
- **No firmware for it** [code]. No update file of the E144 family (E-M5 III, OM-5) has a sub-CPU block (om-emu
  `docs/om1-scpu-spec.md` section 2, and our own block lists). Whether the block is plain logic or a tiny ROM-coded
  controller can't be seen from the main firmware [inferred].
- **The same block in four bodies** [code]. E-M5 III, OM-5 and E-M1 III use the same 35-offset layout, commit at
  +0xa4, 19 commit sites each. The OM-1 (newer SoC) has a remapped layout of the same block (commit +0xf4, clock
  +0xe8/+0xec, om-emu `emu/src/fw/board.mjs` E144 entry). All four use the same keys (below).
- **The E-M1 III and OM-1 have a real power MCU as well** [code]. That one is an STM32 on a serial link (task
  `PER_SCPU`, firmware in update block 5 at 0x08000000) and owns battery, charger, USB-PD and on the E-M1 III keys and
  dials (om-emu `docs/om1-scpu-spec.md`). The E-M5 III has none of it. Its only separate processor with firmware is the
  IS processor (LUKE), which the stabiliser driver calls "scpu" (`bc_scpu`, `SUB_CPU_FW_VER`, 0x601b6998,
  0x601b7094). See [Stabiliser](stabiliser-technical.md).

## Commit protocol [code]

- [code] Every write to the slow registers (0x40-0x9c) is followed by `mov 0x20041001,(0x98e000a4)` and a poll until +0xa4
  reads 0. Most writers also wait for +0xa4 to be 0 before they start. +0x00-+0x3c and +0x40 are written without a
  commit.
- Reads are plain loads, with no commit.
- So 0x20041001 is not a command with arguments. It copies the shadow registers into the always-on domain
  [inferred]. The values 0x98e00080-0x98e000a0 look like arguments at first sight. They are the alarm and watchdog
  registers below.

## Register map (E144 family) [code] unless tagged

| offset | role | readers / writers |
|---|---|---|
| +0x00 | control. Bit 1 = firmware powered off cleanly (set just before power-off, clear after a battery pull). Bits 2-7 = clock-valid signature, 42 after a clock set that reads back within 5 s (0 otherwise). Bit 9 set before power-off when setting 0xa011 is 9. Bit 10 a flag (get/set). Bits 24-31 a byte cleared on read. | 0x600641b0/c7 (sig), 0x600641d7/f4 (bit 10), 0x6006423a (bit 9), 0x60064208/21 (byte), 0x47000b0c (bit 1) |
| +0x04 | a word the firmware writes and compares with 0x01000006 at the next start, then clears. A software wake reason [inferred] | 0x60064332, 0x60064340, 0x60121eaf |
| +0x08-+0x3c | 14 backup words, kept across power-off | 0x60064308 (write, index clamped to 13), 0x6006431d (read), copy loops 0x6005ad74/8c/a4 |
| +0x40 | three byte fields, set 100, 100, 200 at init. Timing values, meaning open [inferred] | init 0x60063b9e, setters 0x60064168/7e/97 (from 0x6006ccb0) |
| +0x44 | power-off request. Writing 0x19721030 and committing turns the camera off | 0x47000b34 |
| +0x48 | power-on cause flags. Bits 0-6 and 7/8 decode to cause codes 1-9 (table below). Written -1 to clear | init 0x60063c0b, clear 0x60064349, power-off 0x47000b29 |
| +0x4c | alarm bits, bit 0 = alarm A, bit 1 = alarm B (set when an alarm starts or fires) | 0x60063f0f, 0x60063f65 |
| +0x50 | wake-input pending bits (5), written back to clear. IRQ 166 | 0x6006401c |
| +0x54 | wake-input enable mask (5 bits). Power-off writes 31 (all) | 0x60063def, 0x60063e1b, 0x60063e4b |
| +0x58-+0x68 | wake inputs 0-4. Bit 31 = current level. Low bits a packed configuration word (polarity, edge, filter count in bits 8-15, [inferred]) | levels 0x60063d81, config 0x6006425b |
| +0x6c, +0x70, +0x74, +0x78 | alarm A: compare, counter, control (bit 0 run, bit 2 mode, bit 4), status | 0x60063e5d, 0x60063ee7, 0x60063f93, 0x60063ff7 |
| +0x7c, +0x80, +0x84, +0x88 | alarm B: the same layout. IRQ 167 serves both alarms | 0x60063ea2, 0x60063f3d, 0x60063fc5, 0x60064000, 0x60064062 |
| +0x8c | watchdog. Bits 0-5 timeout, 0 = off. Bit 8 set at init (0x10a), bit 7 set by the flash guard (0x81) | 0x600226e1, init 0x60063bfb, 0x600c466b, 0x60058ad7 |
| +0x90 | watchdog kick, CPU 0. Key 0x19191012 | 0x47000ad1 |
| +0x94 | watchdog kick, other cores. Key 0x19450815 | 0x47000adf |
| +0x98 | clock seconds (local time since 1970, om-emu) | read 0x47000ca6, set 0x60064132 |
| +0x9c | clock phase, sub-second count in bits 5 and up (1/1024 s on the OM-1, om-emu) | 0x6006e50b, delay loop 0x47000fe8 |
| +0xa0 | bit 0 enable, set at init | 0x60063c01 |
| +0xa4 | commit: write 0x20041001, poll until 0 | 19 sites |

Driver cluster 0x60063b57-0x6006442d (init 0x60063b57, called at stage 0 from 0x600451a2). The OM-5 twin is
0x600688f0-0x60069103.

## Watchdog [code] 2026-11-23

- [code] **Set:** 0x600226e1(n) keeps the upper bits of +0x8c, writes n & 63 into bits 0-5 and commits. Init writes 0x10a
  (bit 8 plus 10).
- **Kick:** 0x4700101b → 0x47000abf. It reads the core number (0x8050). Core 0 writes 0x19191012 to +0x90, any other
  core writes 0x19450815 to +0x94, then it commits. Only PER_WDT (core 0) and the standby loop call it. No kicker on
  CPU 1/2 was found, so +0x94 looks unused on this body [inferred].
- [code] **PER_WDT** (task id 25, entry 0x600741c0, started by 0x600741b2 at 0x60045200): waits on its queue with a 3000 ms
  timeout while the watchdog is on, kicks, and serves `wdt` shell commands (off, on, time, rbt1, rbt2, handler
  0x60074251). On sets 10 (0x6007416b), off sets 0 (0x6007417d).
- **Timeouts by path:**

| path | value | where |
|---|---|---|
| normal running | 10, kicked every 3 s | 0x6007416b |
| flash erase/program | 0 (off), then 10 | 0x6005a177 |
| standby (sleep) | 1, kicked on every loop pass | 0x47000994 |
| fatal error ("COMMON Reboot") | 1, then spin | 0x6005849f |
| NMI dump | 1, then dump and spin | 0x60069f5f |
| reboot request | 1, bit 8 set again, spin | 0x60058abc |
| flash write guard | 0x81 (bit 7 + 1), backup words 12/13 = blocked address, spin | 0x600c464b |

- **Unit:** probably seconds [inferred]. A kick every 3 s against 10 fits, and the fault paths reset "about a second"
  after setting 1 ([recovery](../firmware/recovery-technical.md)). Not timed on the camera.
- [code] **Cause after the reset:** a watchdog reset sets +0x48 bit 7 or 8. The next start decodes that as cause 8, power-on
  factor 0x1000002. The atlas records the same value after a watchdog reset on the E-M10 II (fenykl SDK).
- **The NMI handler** (0x60069f5a) reads two CPU-local words: 0x8900 (NMIINTREG) and 0x8044 (SYSERRREG). 0x8900 bit 2
  prints `[SYS WANA]WATCHDOG_TIMEROVER`, so the core can also take a watchdog NMI before the reset [inferred].

## Power-on cause [code] 2026-11-23

- [code] At init (0x60063b57), if +0x00 bit 1 is clear (no clean power-off before, so a battery was inserted) the cause code
  is 0. Otherwise the lowest set bit of +0x48 picks the code. The code is kept at 0xa263bbce (getter 0x60063d0a).
- 0x60121d84 maps the code to the **power-on factor** word 0xa2652ccc through table 0x601b7e54 (picked per board
  variant through 0x61e8c940). The OM-5 1.2 has a byte-identical table. The E-M1 III and OM-1 images don't contain it (their causes may come from the power MCU) [inferred].

| code | from | factor | meaning |
|---|---|---|---|
| 0 | +0x00 bit 1 clear | 0x1000001 | battery inserted |
| 1 | +0x48 bit 0, wake input 0 | 0xc | power switch |
| 2 | bit 1, input 1 | 0x100 | input 1 (USB cable [inferred]) |
| 3 | bit 2, input 2 | 0 | handled by 0x6006a3c5 instead |
| 4 | bit 3, input 3 | 0x1506 | card inserted (atlas: same value on the E-M10 II) |
| 5 | bit 4, input 4 | 0x1229 | input 4, meaning open |
| 6, 7 | bit 5 / bit 6, alarms | 0x1000003, or 0x1000006 when +0x04 holds 0x01000006 | timed wake |
| 8 | bit 7 or 8 | 0x1000002 | watchdog reset |
| 9 | no flag | 0x1000001 | none |

- [code] The wake-input set-up table 0x601b7ecc gives five 12-byte rows. A second table (0x601b7e7c, or 0x601b7ea4 on the
  other board variant) pairs each factor with an enable flag. The atlas lists 0x400 as "USB cable" on the E-M10 II, so
  the 0x100 guess above is unconfirmed.

## Power-off and standby [code] 2026-11-23

- **Power-off** 0x47000afa(mask), from the power-off task path 0x6005f203 and from 0x601fcc2d: lock interrupts,
  0x6006d64e, set +0x00 bit 1, write ~mask to +0x48, put main memory in a safe state (0x47000eab, writes to
  0x98100000/0x98b00850, likely self-refresh [inferred]), write 0x19721030 to +0x44, commit, spin.
- [code] Before that, 0x6005f203 clears the causes, optionally arms alarm A for a timed wake (seconds from its argument,
  0x6006e464), enables all five wake inputs (0x60063def) and sets +0x00 bit 9 if setting 0xa011 is 9.
- **Standby** 0x470008fa(ms), from task PWR_STANDBY (0x6005f871): prints `pwr standby enter`, stops devices, sets the
  watchdog to 1, then loops: wait for wake events (0x470011b7, 0x470011a7), compare the seconds clock with the deadline,
  kick. On exit it restarts devices and prints `pwr standby return`. The whole loop runs from the fast memory at
  0x47000800, likely so it works with main memory paused [inferred].

## Clock and operating time [code] 2026-11-23

- [code] **Set** 0x6006e699(seconds, flag): writes +0x98 (and 0 to +0x9c when flag is 1), commits, reads +0x98 back. Within
  5 s it writes the signature 42 to +0x00 bits 2-7, otherwise 0 and log 0x19001005, up to 10 tries. The OM-1 has the
  same 42 signature (om-emu `docs/om1-settings-spec.md` section 3). An emulator log of both programs shows each
  writing 0xa8 (42 << 2) to +0x00 [emu].
- [code] **Operating time:** 0x6006e541 keeps the seconds at 0x61f275f4. 0x6006e551 adds the difference to the record at
  flash 0x40680000 (+16). Errors log 0x19001001-0x19001003.

## Comparison

| | E-M5 III 1.7 | OM-5 1.2 | E-M1 III 1.6 | OM-1 1.9 |
|---|---|---|---|---|
| always-on block, commit offset | +0xa4 | +0xa4 | +0xa4 | +0xf4 |
| keys 0x19191012 / 0x19450815 / 0x19721030 / 0x20041001 | yes | yes | yes | yes |
| power-on cause table 0x1000001, 0xc, 0x100 ... | yes | identical | not found | not found |
| external power MCU (`PER_SCPU` task) | no | names only, no code | yes (STM32) | yes (STM32) |
| its firmware in the update file | none | none | block 5 | block 5 |
| watchdog task name | PER_WDT | PER_WDT + SYS_WDT names | SYS_WDT | SYS_WDT |

[code] 2026-11-23, byte scans of.

- The four constants read as dates. 1919-10-12 is the founding date of Olympus and 2004-10-01 the start of Olympus
  Imaging [inferred]. They are fixed keys, the same in every body, so they are no per-model check.
- **No version or model check** anywhere in this path [code]. No firmware is loaded into the block, and the main
  program never reads a version from it.
- **Same on the OM-5** [code]+[inferred]: the OM-5 drives this block exactly as the E-M5 III does (same
  driver, same keys, same cause table). No boot step can wait for a sub-CPU answer, because there is no answering
  processor. The OM-5's `PER_SCPU_*` names have no driver behind them.

## om-emu

- [code] om-emu models the window as storage with the E144 offsets (`scpu: { command: 0xa4, clock: [0x98, 0x9c] }`) and maps
  the OM-1's port words 0xa0-0xb8 to the E144 family's 0x58-0x68 (om-emu `emu/src/fw/board.mjs`, read at 3158147).
- A stock `modelcheck.mjs E137 --no-port` run (om-emu 3158147, node 26.12.1) printed no window commit [emu]
  2026-11-23. The lab starts after the stage-0 init, so the watchdog and wake set-up never run there.

## Open

- [open] What wake inputs 1, 2 and 4 are wired to (USB, a key, the hot shoe?). A Wi-Fi shell read of +0x58-+0x68 with the
  switch, cable and card in different states would settle it.
- [open] The exact meaning of +0x8c bits 7 and 8, and the timeout unit (a timed camera test: `wdt time` then a hang).
- [open] +0x40's three bytes and +0x00 bits 10 and 24-31.
- Whether the block is pure logic or a small ROM controller.

## Sources

- E-M5 III block0 addresses above,.
- om-emu (MIT) docs `docs/om1-scpu-spec.md`, `docs/om1-settings-spec.md` section 3, `docs/hle-gaps.md` 4.7 (facts only).
- Atlas power-on factor record (E-M10 II, from atx's fenykl SDK): xulfr/om-firmware-atlas
  `views/reference/em10-ii-1400.power-on-factor.md`.
- Related: [Recovery](../firmware/recovery-technical.md), [Boot and section loading](../firmware/boot-and-sections.md),
  [SoC overview](soc-overview-technical.md).
