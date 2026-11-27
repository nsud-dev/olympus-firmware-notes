# Image stabiliser: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Image stabiliser](stabiliser.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

The E-M5 III's in-body image stabiliser (IBIS) moves the sensor to cancel camera shake. This page explains how the main
program controls it, the command set it uses, which image stabilisation (IS) settings exist, and how the OM-5's "IS
Level" movie setting compares with what the E-M5 III already has.

The key point is that the stabiliser has its own small processor. The main program doesn't run the servo loop. It sends
commands to that processor over a serial link.

Terms used here:

- **IS** is image stabilisation. **Sync IS** is the body and lens stabilisers working together.
- A **sub-CPU** is a separate microcontroller next to the main system-on-chip (SoC).
- A **voice-coil motor (VCM)** is one of the actuators that move the sensor. **Hall sensors** measure where it is.

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred.

## Stabiliser processor

The servo runs on a separate IS sub-CPU, not on the MN103. That covers the gyros, the accelerometer, the hall sensors
and the VCMs. The MN103 talks to the sub-CPU over a synchronous serial link, `bc_sio`, with a channel, master or slave
mode, an edge setting and up to 8 MHz. Reset, CS, RDY and RQ lines go with it. The sub-CPU has SYS (boot) and USR
(application) firmware, each with its own version.[^fw1]

## Host module

The host side is the "bc" module, short for "Blurring Correction". It is made of `bc_main`, `bc_stab`, `bc_stage`,
`bc_blc`, `bc_blc_sync`, `bc_info`, `bc_scpu`, `bc_sio`, `bc_ssc`, `bc_adj`, `bc_interval` and `bc_ts_data`.[^fw1]

Requests go through one submit function. It takes a 104-byte packet in a0, with the command id at +12, and the source
line in d0. On the capture side the module is `CapBlc_BlurringCorrection.cpp`.[^fw1]

## Hardware

- The actuators are Y, X1 and X2. X1 and X2 driven differentially give roll.[^fw1]
- The gyro measures yaw, pitch and roll, and there is an accelerometer.[^fw1]
- The calibration lives in the STAB_FLASH parameters (`PRM_BC_HALL_*`, `PRM_BC_GYRO_TEMPOFS_TABLE_*`,
  `PRM_BC_GYRO_SLOPE_MATRIX`).[^fw1]

## LUKE firmware

The firmware for the sub-CPU is very likely block 3, named "LUKE".[^fw1][^inf1]

- The updater writes LUKE (block type `0x10e`) with the same routine as the BURE (ブレ, "shake") firmware.[^fw1]
- Its strings are `luke_main\cpu0\ms\...` and `luke_main\cpu1\cmd\task_drive.c`, with gyro and accelerometer
  reads.[^fw1]
- Every TruePic IX-era body has it. The OM-5's LUKE differs in 42% of its bytes.[^fw1]

### Instruction set

LUKE is MN10300-family code. It disassembles cleanly with mn10300-elf objdump (`-b binary -m mn10300`, with the code
starting at the file offset in the [address reference](#address-reference)). Don't use `-m am33-2`, which misreads its
extension ops. A few hundred user-defined-function (`udf`) instructions sit on top.[^fw2]

LUKE runs on two cores, with a maths extension unit for multiply, divide and multiply-accumulate.[^fw2]

### Compared with the OM-5

- The OM-5's LUKE uses 202 of the E-M5 III's 203 peripheral addresses.[^fw2]
- About 96% of the E-M5 III's instructions line up with the OM-5's once addresses are masked. Most of the 42% byte
  difference is shifted addresses.[^fw2][^inf2]
- The OM-5 drops code for early prototype phases, selected by a byte the main program sends with command 2. That
  includes two large filter blocks in the second core.[^fw2][^inf2]

### Commands LUKE handles

The main program's packet table maps each `bc` id to a wire byte. LUKE's 248-entry handler table has 49 of
them.[^fw2]

- Wire `0x22` (id 11, drive to a target position) and `0x36` (id 23) reach an empty default handler, so LUKE ignores
  them.[^fw2]
- The constant-speed drive (`0x73`, id 31) and the rotation drive (`0x77`, id 35) are handled.[^fw2]

## Command set

The host sends numbered commands. There are **57**. They were decoded from the `bc com` parser and its jump table, and
the labels are the firmware's own Shift-JIS names.[^fw1]

| id | what |
|---:|---|
| 8 | set mode |
| 9 | centering |
| 10 | stop |
| **11** | drive to a target position (pos_x, pos_y, pos_roll) |
| 12 | tripod High Res drive |
| 13 | start IS (det_mode, corr_mode, opt_param, image_mag, **ratio_yaw, ratio_pitch**, tv) |
| 15 | switch IS |
| 16 | handheld High Res drive |
| 24-27 | IS parameters |
| 28 | step |
| 29 / 30 | sine drives |
| **31** | constant-speed drive (axis, speed) |
| **35** | rotation drive |
| 37-40 | parameter set / get |

*The useful stabiliser commands on the E-M5 III.[^fw1]*

### Senders

The stock firmware has **no sender** for commands 11, 31 and 35. It stores 11, 15, 16, 29, 31 and 35 nowhere as
immediates. The transport formatter can encode them, but only the `bc com` debug command sends them. Tripod High Res
uses 12, and handheld High Res uses 16.[^fw1]

### Body and lens split

Command 13 sends the **lens share** for Sync IS, where 128 = 100%. The yaw and pitch shares come from two globals. A
helper computes them, with the body share at +24/+25 and the lens share = 128 − body at +26/+27. With a lens that
doesn't cooperate, body = 128 and lens = 0.[^fw1]

### Ids across bodies

The command ids differ between bodies. In the packet tables they match up to 22. From 23 up, the OM-5 id is the
E-M5 III id − 1, for example IS parameters 24 ↔ 23, because the OM-5 has no wire `0x36`.[^fix1]

### Debug command

The user shell has a **`bc` command** with `version`, `dbginfo`, `getprm/getprm2 <tag>`, `tsdata`,
`com <com> <rx> <data...>`, `exec/aexec`, `boot`, `rst`, `bps` and `tmo`.[^fw1] The read-only ones are a cheap way to
read IS limits and versions in a future card-console session.[^inf1]

## Movement reports

During live view the main program asks the stabiliser for a status report once per frame, with bc command 50. The
reply carries two signed movement values, at reply +30 and +32.[^fw3]

The OM-5 turns them into live-view pixels every frame. It uses them to restart its Live ND preview when the camera
moves.[^fw3]

### Running sums

The E-M5 III has the same code, including running sums of the two values. But the sums only run while a stabiliser
flag byte is 1.[^cam1] On the camera, in live view, that flag was 0. Both sums stayed 0 whether the camera was still,
hand-held or panning. So the sums can't be read as a movement signal in live view.[^cam1]

### Reply values

Using the reply values directly works. On the camera a reply arrives once per live-view frame. The E-M5 III's reply
handler has the same two conversion routines as the OM-5, but never calls them in live view. Called from a small hook
on each reply, they give movement in live-view pixels per frame.[^cam1]

| situation | movement per frame |
|---|---:|
| camera on a table | 0 |
| held still in the hand | about 13 |
| picked up | about 250 |
| panned | about 360 |

*Rough readings on our E-M5 III, the larger of the two numbers.[^cam1]*

A hand waved in front of the lens doesn't change them, so they measure the camera, not the picture. We use them, with
the OM-5's limits, to restart the Live ND preview when the camera moves.[^cam1] Whether the values are the raw shake or
what is left after the sensor shift is still open.

See also: [Live ND](../features/live-nd-technical.md#live-view-preview).

## IS settings

- The E-M5 III has S-IS AUTO/1/2/3/Off, M-IS1/2/Off, IS focal length, panning modes, sequential-shooting IS
  speed/stability, Lens I.S. Priority, and Half Way Rls With IS.[^fw1]
- Compared with the OM-5 1.2, E-M1 III and OM-5 II it lacks the movie **"IS Level"** setting
  (`MODE_MOVIE_ANTI_SHAKE_STRENGTH`).[^fw1]

## IS Level

### On the OM-5

IS Level is setting 1477, stored in property 6569. Only the IS host reads it, in 4 places. Its value −1, 0 or +1 gives
a gain of 0.6, 1.0, or 0.6 or 0. It picks one of three IS parameter tables in the OM-5's level function, which feeds the
IS-parameter command.[^fw1][^inf1] The E-M5 III doesn't have property 6569. It is free.[^fw1]

### Parameter sets

The three parameter sets are **property defaults in the firmware** (props 1394/1410/1602/1618/6130/6146).[^fw1]

- The E-M5 III has 18 values, sets A and B.
- The OM-5 has 27, sets A, B and C, where C = 9 × 128.
- Both copy them to RAM pointers at init.

The E-M5 III **does** have a twin of the level function, with the level +1 branch (× 0.6). But its 3 callers always
pass level 0, so +1 is dormant. Only −1 (set C) is missing.[^fw1]

### The E-M5 III level function

Its argument struct has these fields.[^fw4]

- +0 x.
- +2 table pair.
- +3 table.
- +4 0 = still, 1 and 2 = movie variants. The meaning of 1 against 2 is unknown.
- +5 must be 0.
- +6 and +8 formula inputs.
- **+10 level.**
- Outputs at +12 and +14.

How it uses them:[^fw4]

- For movie, if +2 == 0 the level is ignored.
- Level +1 gives gain 0.6, but **0 when +4 == 2**.
- A **direct path** (out = set B × gain) runs only for +4 == 1 and level 1. Every other case uses the normal formula.
- The E-M5 III never reads +11.[^fix2]
- It has three callers. One is a rel16 call. There is no indirect caller. The call frame is `[d2,d3,a2,a3],32`.

The OM-5's level function does +1 = set B × 0.6 direct and −1 = set C × 0.6 direct. So the E-M5 III's +1 equals the
OM-5's +1 **only when +2 != 0 and +4 == 1**. The E-M5 III's −1 is a different path through the formula, not the OM-5's
−1.[^fw4]

### OM-5 level conditions in full

The OM-5 takes the movie path when +4 != 0 and +5 == 0.[^fw5]

- Level −1 always uses gain 0.6 and set C (all 128) on the direct path, for **both** +4 == 1 and +4 == 2. So its output
  is f2u(128 × 0.6) = 76.[^fw5] That assumes a truncating f2u.[^inf4]
- Level +1 gets gain 0 only when +4 ≥ 2 and (+3 == 0, or +3 == 1 and +11 ≥ 64). The E-M5 III gives 0 for +4 == 2 with
  any +3.[^fw5]

The direct path on the E-M5 III is `out = f2u(u2f(x) × gain)`. It uses three float helpers, u2f, fmul and f2u. They are
called with `[],0` and use mdr. The OM-5 has the same three helpers.[^fw5]

### Test builds

A test build for level +1 was made and is waiting for a camera run. It has not been flashed.[^fw4] Its design is a card request that turns on a gate. The gate writes +10 = 1
only when section 4 is ready, +2 != 0 and +4 == 1.[^fw4][^inf3]

A later build could make −1 a constant, because the OM-5's set C is all 128, so interpolation gives a
constant.[^inf3]

The level −1 test has a design. A wrapper calls the E-M5 III level function with level 0. Then it sets
+12 and +14 = 76 when +2 != 0, +4 != 0 and +5 == 0. It needs about 80 to 100 bytes, more than the gate slot the +1
build uses.[^fw5]

## Other bodies

The bc host is nearly the same on the OM-5. The OM-5 drops command 23, the level gauge and horizontal correction state,
which is E-M5 III only. Its packet table keeps 22, the ICT log.[^fix1] It adds body/lens ratio, per-axis maximum and
minimum correction, and "translational correction mode" parameters. So the OM-5's LUKE firmware is not a drop-in
replacement.[^fw1]

The IS tuning property defaults have the same values on the E-M5 III, OM-5 and OM-5 II. That covers 1378-3082,
6130/6146, 7057/7073 and the others the bc module reads. The OM-5 lines only add the movie IS Level set.[^fw6]

The stabiliser controller's servo code and filter tables are also the same. The OM-5 II adds an unused gyro filter bank
and wire `0x37`.[^fw6] See also: [Stabiliser controller: technical notes](is-controller-technical.md#across-bodies-e-m5-iii-om-5-om-5-ii).

## Open questions

- Whether the movement values are the raw shake or what is left after the sensor shift.
- What separates the two movie variants, 1 and 2, in the level function's +4 field.

## Address reference

E-M5 III 1.7 block0 addresses unless the OM-5 is named.

| item | address |
|---|---|
| bc module | `0x60103f21`–`0x6011f82f` |
| submit function | `0x60116bc5` |
| `CapBlc_BlurringCorrection.cpp` | `0x60880f41` |
| updater routine for LUKE and BURE | `0x60c3b7ad` |
| packet table (`bc` id to wire byte) | `0x601b6598` |
| `bc com` parser, jump table | `0x6010ee39`, `0x601b5d58` |
| transport formatter | `0x60117000`–`0x60118648` |
| lens share globals, yaw and pitch | `0x620a8ffa`, `0x620a8ffb` |
| share helper | `0x6010658b` |
| user shell table, `bc` handler | `0x601fbe38`, `0x6010d41b` |

*Host module, commands and shell.*

| item | address |
|---|---|
| status request (bc command 50) | `0x6055b901` |
| reply handler | `0x601146f2` |
| running sums | `0x620b0e14`, `0x620b0e18` |
| stabiliser flag byte | `0x6210944d` |
| conversion routines | `0x60129190`, `0x601291bc` |

*Movement reports.*

| item | address |
|---|---|
| OM-5 level function | `0x6011aac6` (OM-5) |
| parameter sets copied to RAM | OM-5 `0x6011b6b3`, E-M5 III `0x6010c70d` |
| E-M5 III level function | `0x6010bc83` |
| callers (in function) | `0x6010af2a` (`0x6010ac0a`, rel16 call), `0x6011ca8a` (`0x6011c8b8`), `0x6011d445` (`0x6011d377`) |
| u2f, fmul, f2u | `0x600e2350`, `0x600e225f`, `0x600e21de` |
| OM-5 u2f, fmul, f2u | `0x600ef2a9`, `0x600ef1b8`, `0x600ef137` |
| gate slot of the +1 test build | `0x600d00a0` |

*IS Level.*

| item | address |
|---|---|
| LUKE code start, file offset | `0x400` |
| LUKE peripherals | `0x98000000`, `0x99000000`, `0x9c000000`–`0x9c110000` |

*LUKE firmware, in its own address space.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware, 2026-11-06.
[^inf1]: Inferred, 2026-11-06.
[^fw2]: Read in the firmware, 2026-11-23, comparing the E-M5 III and OM-5 LUKE blocks.
[^inf2]: Inferred, 2026-11-23.
[^fw3]: Read in the firmware, 2026-11-15.
[^cam1]: Seen on our E-M5 III using test firmware and read in the firmware, 2026-11-17.
[^fw4]: Read in the firmware, 2026-11-07.
[^inf3]: Inferred, 2026-11-07.
[^fw5]: Read in the firmware, 2026-11-12.
[^inf4]: Assumed, 2026-11-12.
[^fw6]: Read in the firmware, 2026-11-25.
[^fix1]: Corrected on 2026-11-23 from the packet tables. The older reading is in [History](#history).
[^fix2]: Corrected on 2026-11-07. The older reading is in [History](#history).

## History

- 2026-11-06: command ids were thought to differ between bodies above 18, from the `bc com` parser. The packet tables
  show they match up to 22. Corrected 2026-11-23.
- 2026-11-06: the OM-5's missing command was corrected on 2026-11-23. It drops command 23 only, and its packet table
  keeps 22 (ICT log).
- 2026-11-06: we first read the E-M5 III as having neither the IS Level property nor its code. The parameter sets
  turned out to be property defaults, and the E-M5 III has a twin of the level function. Corrected the same day.
- 2026-11-06: a note said the E-M5 III level function needs +11 ≥ 64. That condition is OM-5 only. Corrected
  2026-11-07.
- 2026-11-23: the code the OM-5's LUKE drops was first read as likely the E-M5 III-only commands 22 and 23. It is
  filter code, and neither LUKE handles command 23. Corrected the same day.

