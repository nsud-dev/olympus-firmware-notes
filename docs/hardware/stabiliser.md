# Stabiliser (IBIS)

The E-M5 III's in-body image stabiliser (IBIS) moves the sensor to cancel camera shake. This page explains how the main
program controls it, the command set it uses, which IS settings exist, and how the OM-5's "IS Level" movie setting
compares with what the E-M5 III already has.

The key point: the stabiliser has its own small processor. The main program doesn't run the servo loop; it sends
commands to that processor over a serial link.

Terms used here:

- **IS** = image stabilisation; **Sync IS** = body and lens stabilisers working together.
- **Sub-CPU** = a separate microcontroller next to the main SoC.
- **VCM** = voice-coil motor, the actuators that move the sensor; **hall sensors** measure where it is.

Tags: **[code]** read in the firmware, **[camera]** seen on a real E-M5 III, **[inferred]** not traced or tested.


## How it is driven

**A separate IS sub-CPU.** The servo (gyros, accelerometer, hall sensors, VCMs) runs on a separate IS sub-CPU, not on
the MN103. The MN103 talks to it over a synchronous serial link (bc_sio: channel, master/slave, edge, up to 8 MHz) with
reset/CS/RDY/RQ lines. The sub-CPU has SYS (boot) and USR (application) firmware with their own versions. [code]
2026-11-06

**The host side is the "bc" module** ("Blurring Correction"), 0x60103f21-0x6011f82f, made of bc_main, bc_stab,
bc_stage, bc_blc, bc_blc_sync, bc_info, bc_scpu, bc_sio, bc_ssc, bc_adj, bc_interval and bc_ts_data. Requests go through
the submit function **0x60116bc5** (a0 = 104-byte packet, command id at +12, d0 = source line). On the capture side,
`CapBlc_BlurringCorrection.cpp` is at 0x60880f41. [code] 2026-11-06

**Hardware.** Actuators Y, X1 and X2 (X1/X2 differential = roll); gyro yaw/pitch/roll plus an accelerometer. Calibration
lives in the STAB_FLASH parameters (`PRM_BC_HALL_*`, `PRM_BC_GYRO_TEMPOFS_TABLE_*`, `PRM_BC_GYRO_SLOPE_MATRIX`). [code]
2026-11-06

**The firmware for the sub-CPU is very likely block 3 ("LUKE").** The updater writes LUKE (block type 0x10e) with the same
routine as the BURE (ブレ, "shake") firmware (0x60c3b7ad), and its strings are `luke_main\cpu0\ms\...` and
`luke_main\cpu1\cmd\task_drive.c`, with gyro and accelerometer reads. Every TruePic IX-era body has it; the OM-5's differs
in 42% of its bytes. Its instruction set isn't identified. [code]+[inferred] 2026-11-06

## The command set

The host sends numbered commands. There are **57**, decoded from the `bc com` parser 0x6010ee39 and jump table
0x601b5d58; the labels are the firmware's own Shift-JIS names. Full table:,
script. [code] 2026-11-06

The useful ones:

| id | what |
|---|---|
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

Notes: [code] 2026-11-06

- The stock firmware has **no sender** for commands 11, 31 and 35, and stores 11, 15, 16, 29, 31 and 35 nowhere as
  immediates. The transport formatter (0x60117000-0x60118648) can encode them, but only the `bc com` debug command sends
  them. Tripod HR uses 12, handheld HR 16. [code]
- **Body/lens split (Sync IS):** command 13 sends the **lens share** (128 = 100 %) from globals 0x620a8ffa (yaw) /
  0x620a8ffb (pitch), computed by 0x6010658b (body share +24/+25, lens = 128 − body at +26/+27). With a lens that
  doesn't cooperate, body = 128 and lens = 0. [code]
- **Command ids differ between bodies:** they match up to 18; above that, OM-5 id = E-M5 III id − 1 (for example IS
  parameters 24 ↔ 23).

The user shell (table 0x601fbe38) has a **`bc` command** (handler 0x6010d41b) with `version`, `dbginfo`,
`getprm/getprm2 <tag>`, `tsdata`, `com <com> <rx> <data...>`, `exec/aexec`, `boot`, `rst`, `bps` and `tmo`. The read-only
ones are a cheap way to read IS limits and versions in a future card-console session. [code]+[inferred] 2026-11-06

## IS settings

- The E-M5 III has: S-IS AUTO/1/2/3/Off, M-IS1/2/Off, IS focal length, panning modes, sequential-shooting IS
  speed/stability, Lens I.S. Priority, and Half Way Rls With IS. [code] 2026-11-06
- Compared with the OM-5 1.2, E-M1 III and OM-5 II it lacks the movie **"IS Level"** setting
  (`MODE_MOVIE_ANTI_SHAKE_STRENGTH`). [code] 2026-11-06

## How IS Level works, and what the E-M5 III already has

**On the OM-5:** IS Level is setting 1477, stored in property 6569, and only the IS host reads it (4 places). Its value
−1/0/+1 gives a gain of 0.6/1.0/0.6-or-0 and picks one of three IS parameter tables in 0x6011aac6 (OM-5 address), which
feeds the IS-parameter command. The E-M5 III has neither the property nor that code. [code]+[inferred] 2026-11-06

**Correction (2026-11-06, §8.5):** the three parameter sets are **property defaults in the firmware** (props
1394/1410/1602/1618/6130/6146). The E-M5 III has 18 values (sets A+B), the OM-5 has 27 (A+B+C, where C = 9 × 128). They
are copied to RAM pointers at init (OM-5 0x6011b6b3, E-M5 0x6010c70d). The E-M5 III **does** have the twin function
0x6010bc83 with the level +1 branch (× 0.6), but its 3 callers always pass level 0, so +1 is dormant; only −1 (set C) is
missing. Property 6569 is free on the E-M5 III. [code] 2026-11-06

**The E-M5 level function in detail (2026-11-07).** [code] 2026-11-07, check


- Its argument struct: +0 x, +2 table pair, +3 table, +4 0 = still / 1, 2 = movie variants (the meaning of 1 vs 2 is
  unknown), +5 must be 0, +6/+8 formula inputs, **+10 level**, outputs at +12/+14.
- For movie: if +2 == 0 the level is ignored. Level +1 gives gain 0.6, but **0 when +4 == 2**. A **direct path**
  (out = set B × gain) runs only for +4 == 1 and level 1; every other case uses the normal formula.
- The OM-5's 0x6011aac6 does: +1 = set B × 0.6 direct, −1 = set C × 0.6 direct. So the E-M5's +1 equals the OM-5's +1
  **only when +2 != 0 and +4 == 1**, and the E-M5's −1 is a different (formula) path, not the OM-5's −1. [code]
- The E-M5 never reads +11. (This corrects a 2026-11-06 note "+11 ≥ 64", which is OM-5 only.)
- Callers: 0x6010af2a (in 0x6010ac0a, rel16 call), 0x6011ca8a (0x6011c8b8), 0x6011d445 (0x6011d377); frame
  [d2,d3,a2,a3],32; no indirect caller. [code]

**Test build for level +1 (built 2026-11-07, not flashed).**
Design: a card request turns on a gate at 0x600d00a0 that writes +10 = 1 only when section 4 is
ready, +2 != 0 and +4 == 1. A later build could make −1 a constant (the OM-5's set C is all 128, so interpolation gives a
constant). [code]+[inferred] 2026-11-07

**OM-5 level conditions in full, and a −1 test (2026-11-12).** [code] OM-5 0x6011aac6: movie path when +4 != 0 and +5 == 0.
Level −1 always uses gain 0.6 and set C (all 128) on the direct path, for **both** +4 == 1 and +4 == 2, so its output is
f2u(128 × 0.6) = 76 (truncating f2u assumed [inferred]). Level +1 gets gain 0 only when +4 ≥ 2 and (+3 == 0, or +3 == 1 and
+11 ≥ 64); the E-M5 gives 0 for +4 == 2 with any +3. Direct path on the E-M5: `out = f2u(u2f(x) × gain)` with helpers
u2f 0x600e2350, fmul 0x600e225f, f2u 0x600e21de (`[],0` calls, use mdr); OM-5 0x600ef2a9 / 0x600ef1b8 / 0x600ef137.
Design of the level −1 test: wrapper calls 0x6010bc83 with level 0, then sets +12/+14 = 76 when +2 != 0, +4 != 0, +5 == 0;
needs ~80-100 B, more than the 0x600d00a0 slot). The level +1 test is built and waiting for a camera run.

## OM-5 vs E-M5 III

The bc host is nearly the same. The OM-5 drops commands 22 (ICT log) and 23 (level gauge / horizontal correction state,
E-M5 III only) and adds body/lens ratio, per-axis maximum/minimum correction and "translational correction mode"
parameters. So the OM-5's LUKE firmware is not a drop-in replacement. [code] 2026-11-06

