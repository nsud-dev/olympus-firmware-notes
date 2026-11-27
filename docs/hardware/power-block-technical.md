# Power and watchdog block: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Power and watchdog block](power-block.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

The E-M5 III has no separate power processor. Power-on, power-off, the clock and the watchdog are handled by a small
always-on block of the system-on-chip (SoC), driven by the main CPU through registers. This page covers how the
firmware talks to that block, its register map, the watchdog, the power-on cause, power-off and standby, and how the
same block looks in other bodies.

Addresses are E-M5 III 1.7 block0 addresses (base `0x60021020`) unless a body is named. The 6 KB fast-memory library at
`0x47000800` is copied there from flash by the boot stub.

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred or seen in an emulator.

## Summary

- **No power sub-CPU.** Earlier pages called the register window at `0x98e00000` "the power sub-CPU". The register use
  reads as a small always-on block instead. It has a seconds clock, 14 backup words, five wake inputs, two alarms, a
  watchdog, a power-off request and the power-on cause flags. The main CPU writes shadow registers and then commits
  them. Nothing is sent as a message, and nothing answers.[^fw1][^inf1]
- **No firmware for it.** No update file of the E144 family (E-M5 III, OM-5) has a sub-CPU block. Whether the block is
  plain logic or a tiny ROM-coded controller can't be seen from the main firmware.[^fw1][^inf1]
- **The same block in four bodies.** The E-M5 III, OM-5 and E-M1 III use the same layout of 35 offsets, with the commit
  at `+0xa4` and 19 commit sites each. The OM-1, a newer SoC, has a remapped layout of the same block. All four use the
  same keys.[^fw1]
- **The E-M1 III and OM-1 also have a real power microcontroller.** It is an STM32 on a serial link, served by the
  `PER_SCPU` task, with its firmware in update block 5. It owns the battery, charger and USB power delivery, and on the
  E-M1 III the keys and dials. The E-M5 III has none of it.[^fw1]
- The E-M5 III's only separate processor with its own firmware is the image stabilisation (IS) processor. Its driver
  calls it "scpu".[^fw1] See [Stabiliser](stabiliser-technical.md).

## Commit protocol

Every write to the slow registers (`+0x40` to `+0x9c`) is followed by writing `0x20041001` to `+0xa4` and polling until
`+0xa4` reads 0. Most writers also wait for `+0xa4` to be 0 before they start. Offsets `+0x00` to `+0x40` are written
without a commit. Reads are plain loads, with no commit.[^fw1]

So `0x20041001` is not a command with arguments. It copies the shadow registers into the always-on domain.[^inf1] The
values at `0x98e00080` to `0x98e000a0` look like arguments at first sight. They are the alarm and watchdog registers
below.

## Register map

Offsets from `0x98e00000`, for the E144 family (E-M5 III, OM-5, E-M1 III).[^fw1]

| offset | role |
|---|---|
| `+0x00` | control. Bit 1 = the firmware powered off cleanly (set just before power-off, clear after a battery pull). Bits 2-7 = clock-valid signature, 42 after a clock set that reads back within 5 s, otherwise 0. Bit 9 is set before power-off when setting `0xa011` is 9. Bit 10 is a flag. Bits 24-31 are a byte cleared on read. |
| `+0x04` | a word the firmware writes and compares with `0x01000006` at the next start, then clears. A software wake reason.[^inf1] |
| `+0x08` to `+0x3c` | 14 backup words, kept across power-off |
| `+0x40` | three byte fields, set to 100, 100 and 200 at init. Timing values, meaning open.[^inf1] |
| `+0x44` | power-off request. Writing `0x19721030` and committing turns the camera off. |
| `+0x48` | power-on cause flags. Bits 0-6 and 7 or 8 decode to cause codes 1 to 9. Written -1 to clear. |
| `+0x4c` | alarm bits. Bit 0 = alarm A, bit 1 = alarm B, set when an alarm starts or fires. |
| `+0x50` | wake-input pending bits (5), written back to clear. IRQ 166. |
| `+0x54` | wake-input enable mask (5 bits). Power-off writes 31, all inputs. |
| `+0x58` to `+0x68` | wake inputs 0 to 4. Bit 31 = current level. The low bits are a packed configuration word, probably polarity, edge and a filter count in bits 8-15.[^inf1] |
| `+0x6c` to `+0x78` | alarm A: compare, counter, control (bit 0 run, bit 2 mode, bit 4), status |
| `+0x7c` to `+0x88` | alarm B, the same layout. IRQ 167 serves both alarms. |
| `+0x8c` | watchdog. Bits 0-5 = time-out, 0 = off. Bit 8 is set at init (`0x10a`). Bit 7 is set by the flash guard (`0x81`). |
| `+0x90` | watchdog kick from CPU 0, key `0x19191012` |
| `+0x94` | watchdog kick from the other cores, key `0x19450815` |
| `+0x98` | clock seconds, local time since 1970[^emu1] |
| `+0x9c` | clock phase, a sub-second count in bits 5 and up (1/1024 s on the OM-1)[^emu1] |
| `+0xa0` | bit 0 = enable, set at init |
| `+0xa4` | commit. Write `0x20041001`, poll until 0. |

*Registers of the always-on block. The functions that read and write each one are in the [address reference](#address-reference).*

## Watchdog

The watchdog resets the camera unless it is kicked. The firmware sets its time-out in bits 0-5 of `+0x8c` and commits.
Init writes `0x10a`, which is bit 8 plus a time-out of 10.[^fw1]

- **Kick.** The kick function reads the core number. Core 0 writes `0x19191012` to `+0x90`, and any other core writes
  `0x19450815` to `+0x94`. Then it commits.[^fw1]
- **Who kicks.** Only the `PER_WDT` task on core 0 and the standby loop call the kick. No kicker on CPU 1 or 2 was
  found, so `+0x94` looks unused on this body.[^fw1][^inf1]
- **PER_WDT** is task 25. While the watchdog is on, it waits on its queue with a 3,000 ms time-out, then kicks. It also
  serves the `wdt` shell commands (off, on, time, rbt1, rbt2). On sets 10, off sets 0.[^fw1]

| path | time-out |
|---|---|
| normal running | 10, kicked every 3 s |
| flash erase or program | 0 (off), then 10 |
| standby (sleep) | 1, kicked on every loop pass |
| fatal error ("COMMON Reboot") | 1, then spin |
| NMI dump | 1, then dump and spin |
| reboot request | 1, bit 8 set again, spin |
| flash write guard | `0x81` (bit 7 + 1), backup words 12 and 13 = the blocked address, spin |

*Watchdog time-out set on each path.[^fw1]*

The unit is probably seconds. A kick every 3 s against 10 fits, and the fault paths reset about a second after setting
1. It has not been timed on the camera.[^inf1] See also: [Recovery](../firmware/recovery-technical.md).

A watchdog reset sets `+0x48` bit 7 or 8. The next start decodes that as cause 8, power-on factor `0x1000002`. The
OM Firmware Atlas records the same value after a watchdog reset on the E-M10 II.[^fw1]

The non-maskable interrupt (NMI) handler reads two CPU-local registers, NMIINTREG and SYSERRREG. NMIINTREG bit 2 prints
`[SYS WANA]WATCHDOG_TIMEROVER`, so the core can also take a watchdog NMI before the reset.[^inf1]

> [!NOTE]
> A task that only hangs doesn't trigger the watchdog. `PER_WDT` keeps kicking it, so the camera freezes until the
> battery comes out.

## Power-on cause

At init the firmware decides why the camera woke.[^fw1]

- If `+0x00` bit 1 is clear, there was no clean power-off before, so a battery was inserted. The cause code is 0.
- Otherwise the lowest set bit of `+0x48` picks the code.

A table then maps the code to the power-on factor word that the rest of the firmware reads. The table is picked per
board variant. The OM-5 1.2 has a byte-identical table.[^fw1] The E-M1 III and OM-1 images don't contain it. Their
causes may come from the power microcontroller.[^inf1]

| code | from | factor | meaning |
|---:|---|---|---|
| 0 | `+0x00` bit 1 clear | `0x1000001` | battery inserted |
| 1 | `+0x48` bit 0, wake input 0 | `0xc` | power switch |
| 2 | bit 1, input 1 | `0x100` | input 1, probably the USB cable[^inf1] |
| 3 | bit 2, input 2 | 0 | handled by a separate function instead |
| 4 | bit 3, input 3 | `0x1506` | card inserted (the Atlas has the same value on the E-M10 II) |
| 5 | bit 4, input 4 | `0x1229` | input 4, meaning open |
| 6, 7 | bit 5 or 6, alarms | `0x1000003`, or `0x1000006` when `+0x04` holds `0x01000006` | timed wake |
| 8 | bit 7 or 8 | `0x1000002` | watchdog reset |
| 9 | no flag | `0x1000001` | none |

*Power-on cause codes and the factor each becomes.[^fw1]*

The wake-input set-up table has five 12-byte rows. A second table pairs each factor with an enable flag. The Atlas
lists `0x400` as "USB cable" on the E-M10 II, so the `0x100` guess above is unconfirmed.[^fw1]

## Power-off and standby

**Power-off** runs from the fast memory.[^fw1]

1. Clear the causes, optionally arm alarm A for a timed wake, and enable all five wake inputs. Set `+0x00` bit 9 if
   setting `0xa011` is 9.
2. Lock interrupts and set `+0x00` bit 1, the clean power-off mark.
3. Write the inverted mask to `+0x48`.
4. Put main memory in a safe state, likely self-refresh.[^inf1]
5. Write `0x19721030` to `+0x44`, commit and spin.

**Standby** runs from task `PWR_STANDBY`. It prints `pwr standby enter`, stops devices and sets the watchdog to 1. Then
it loops: wait for wake events, compare the seconds clock with the deadline, kick. On exit it restarts devices and
prints `pwr standby return`.[^fw1] The whole loop runs from the fast memory at `0x47000800`, likely so it works with
main memory paused.[^inf1]

## Clock and operating time

**Setting the clock** writes `+0x98` (and 0 to `+0x9c` when asked), commits and reads `+0x98` back. If the read-back is
within 5 s, it writes the signature 42 to `+0x00` bits 2-7. Otherwise it writes 0 and logs `0x19001005`, for up to 10
tries.[^fw1] The OM-1 uses the same signature 42. An emulator log of both programs shows each writing `0xa8` (42 << 2)
to `+0x00`.[^emu1]

**Operating time** is kept in seconds in RAM, and the difference is added to a record in flash. Errors log
`0x19001001` to `0x19001003`.[^fw1]

## Other bodies

| | E-M5 III 1.7 | OM-5 1.2 | E-M1 III 1.6 | OM-1 1.9 |
|---|---|---|---|---|
| always-on block, commit offset | `+0xa4` | `+0xa4` | `+0xa4` | `+0xf4` |
| the four keys | yes | yes | yes | yes |
| power-on cause table | yes | identical | not found | not found |
| external power microcontroller (`PER_SCPU` task) | no | names only, no code | yes (STM32) | yes (STM32) |
| its firmware in the update file | none | none | block 5 | block 5 |
| watchdog task name | PER_WDT | PER_WDT and SYS_WDT names | SYS_WDT | SYS_WDT |

*The block across four bodies. Byte scans of each body's firmware.[^fw1]*

- **Keys.** The four constants `0x19191012`, `0x19450815`, `0x19721030` and `0x20041001` read as dates. 1919-10-12 is
  the founding date of Olympus and 2004-10-01 the start of Olympus Imaging.[^inf1] They are fixed keys, the same in
  every body, so they are no per-model check.[^fw1]
- **No version or model check** anywhere in this path. No firmware is loaded into the block, and the main program
  never reads a version from it.[^fw1]
- **Same on the OM-5.** The OM-5 drives this block exactly as the E-M5 III does, with the same driver, keys and cause
  table. No boot step can wait for a sub-CPU answer, because there is no answering processor. The OM-5's `PER_SCPU_*`
  names have no driver behind them.[^fw1][^inf1]
- **OM-1 layout.** The OM-1 commits at `+0xf4` and keeps the clock at `+0xe8` and `+0xec`. Its port words `+0xa0` to
  `+0xb8` correspond to the E144 family's `+0x58` to `+0x68`.[^emu1]

## Emulator

om-emu models the window as storage with the E144 offsets. A stock run of its model check printed no window commit.
The emulator starts after the stage-0 init, so the watchdog and wake set-up never run there.[^emu2]

## Open questions

- What wake inputs 1, 2 and 4 are wired to, such as USB, a key or the hot shoe. A Wi-Fi shell read of `+0x58` to
  `+0x68` with the switch, cable and card in different states would settle it.
- The exact meaning of `+0x8c` bits 7 and 8, and the time-out unit. A timed camera test (`wdt time`, then a hang) would
  settle it.
- The three bytes at `+0x40`, and `+0x00` bits 10 and 24-31.
- Whether the block is pure logic or a small ROM controller.

## Address reference

E-M5 III 1.7 block0 addresses unless a body is named.

| item | address |
|---|---|
| register window | `0x98e00000` to `0x98e000a4` |
| driver cluster | `0x60063b57` to `0x6006442d` (OM-5 `0x600688f0` to `0x60069103`) |
| driver init, called at stage 0 | `0x60063b57`, from `0x600451a2` |
| control word readers and writers | signature `0x600641b0`, `0x600641c7`. Bit 10 `0x600641d7`, `0x600641f4`. Bit 9 `0x6006423a`. Byte `0x60064208`, `0x60064221`. Bit 1 `0x47000b0c` |
| software wake word (`+0x04`) | `0x60064332`, `0x60064340`, `0x60121eaf` |
| backup words | write `0x60064308`, read `0x6006431d`, copy loops `0x6005ad74`, `0x6005ad8c`, `0x6005ada4` |
| `+0x40` bytes | init `0x60063b9e`, setters `0x60064168`, `0x6006417e`, `0x60064197` (from `0x6006ccb0`) |
| cause flags (`+0x48`) | init `0x60063c0b`, clear `0x60064349`, power-off `0x47000b29` |
| alarm bits (`+0x4c`) | `0x60063f0f`, `0x60063f65` |
| wake-input pending, enable, levels, config | `0x6006401c`. `0x60063def`, `0x60063e1b`, `0x60063e4b`. `0x60063d81`. `0x6006425b` |
| alarm A | `0x60063e5d`, `0x60063ee7`, `0x60063f93`, `0x60063ff7` |
| alarm B | `0x60063ea2`, `0x60063f3d`, `0x60063fc5`, `0x60064000`, `0x60064062` |
| enable (`+0xa0`) | `0x60063c01` |

*Register readers and writers.*

| item | address |
|---|---|
| watchdog set | `0x600226e1` |
| watchdog kick | `0x4700101b`, then `0x47000abf`. Core 0 at `0x47000ad1`, others at `0x47000adf` |
| core number register | `0x8050` |
| `PER_WDT` entry, started by | `0x600741c0`, `0x600741b2` (at `0x60045200`) |
| `wdt` command handler, on, off | `0x60074251`, `0x6007416b`, `0x6007417d` |
| watchdog paths: flash, standby, fatal, NMI, reboot, guard | `0x6005a177`, `0x47000994`, `0x6005849f`, `0x60069f5f`, `0x60058abc`, `0x600c464b` |
| other watchdog writers | init `0x60063bfb`, `0x600c466b`, `0x60058ad7` |
| NMI handler | `0x60069f5a`, reads `0x8900` (NMIINTREG) and `0x8044` (SYSERRREG) |
| cause code, getter | `0xa263bbce`, `0x60063d0a` |
| cause to factor | `0x60121d84`, table `0x601b7e54`, variant pick `0x61e8c940` |
| power-on factor word | `0xa2652ccc` |
| cause 3 handler | `0x6006a3c5` |
| wake-input set-up table, factor and enable tables | `0x601b7ecc`, `0x601b7e7c` or `0x601b7ea4` |
| power-off, called from | `0x47000afa`, from `0x6005f203` and `0x601fcc2d` |
| power-off request write (`+0x44`) | `0x47000b34` |
| power-off helpers | `0x6006d64e`, memory safe state `0x47000eab` (writes `0x98100000`, `0x98b00850`), timed wake `0x6006e464` |
| standby loop, task, wait | `0x470008fa`, `PWR_STANDBY` `0x6005f871`, `0x470011b7`, `0x470011a7` |
| clock set, read, phase, delay loop | `0x6006e699` (writes at `0x60064132`), `0x47000ca6`, `0x6006e50b`, `0x47000fe8` |
| operating time | `0x6006e541` (seconds at `0x61f275f4`), `0x6006e551` (record at flash `0x40680000` +16) |
| IS processor driver names | `bc_scpu`, `SUB_CPU_FW_VER`, `0x601b6998`, `0x601b7094` |
| fast-memory library | `0x47000800`, from block0 file offset `0x1461fe0` (flash `0x41be2000`) |

*Functions, tables and variables.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware, 2026-11-23, with byte scans of the E-M5 III, OM-5, E-M1 III and OM-1 images.
[^inf1]: Inferred, 2026-11-23.
[^emu1]: From om-emu's documentation and board model (MIT), facts only, read at commit 3158147, 2026-11-23.
[^emu2]: Seen in om-emu at commit 3158147, 2026-11-23.

Other sources: the OM Firmware Atlas power-on factor record for the E-M10 II, from atx's fenykl SDK.

See also: [Boot and section loading](../firmware/boot-and-sections.md), [SoC overview](soc-overview-technical.md).

