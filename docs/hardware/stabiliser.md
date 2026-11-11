# Stabiliser (IBIS)

Working notes, command table and per-idea verdicts:.

## How it is driven
- The IS servo (gyros, accelerometer, hall sensors, VCMs) runs on a **separate IS sub-CPU**, not on the MN103. The MN103 talks to
  it over a synchronous serial link (bc_sio: channel, master/slave, edge, up to 8 MHz) with reset/CS/RDY/RQ lines; the sub-CPU
  has SYS (boot) and USR (app) firmware with their own versions. [code] 2026-11-06
- MN103 host = **"bc" (Blurring Correction) module** 0x60103f21-0x6011f82f (bc_main, bc_stab, bc_stage, bc_blc, bc_blc_sync,
  bc_info, bc_scpu, bc_sio, bc_ssc, bc_adj, bc_interval, bc_ts_data); requests go through submit **0x60116bc5** (a0 = 104-byte
  packet, command id at +12, d0 = source line). Capture side: `CapBlc_BlurringCorrection.cpp` 0x60880f41. [code] 2026-11-06
- Actuators Y, X1, X2 (X1/X2 differential = roll); gyro yaw/pitch/roll + accelerometer; calibration in STAB_FLASH params
  (`PRM_BC_HALL_*`, `PRM_BC_GYRO_TEMPOFS_TABLE_*`, `PRM_BC_GYRO_SLOPE_MATRIX`). [code] 2026-11-06
- **57-entry command set** (labels are the firmware's own Shift-JIS names), decoded from the `bc com` parser 0x6010ee39 / jump table
  0x601b5d58. Useful ones: 8 set mode, 9 centering, 10 stop, **11 drive to target position (pos_x, pos_y, pos_roll)**, 12 tripod
  High Res drive, 13 start IS (det_mode, corr_mode, opt_param, image_mag, **ratio_yaw, ratio_pitch**, tv), 15 switch IS, 16 handheld
  High Res drive, 24-27 IS parameters, 28 step, 29/30 sine drives, **31 constant-speed drive (axis, speed)**, **35 rotation drive**,
  37-40 param set/get. Stock stores 11, 15, 16, 29, 31, 35 nowhere as immediates. Full table:,
  script. [code] 2026-11-06
- The user shell (table 0x601fbe38) has a **`bc` command** (handler 0x6010d41b): `version`, `dbginfo`, `getprm/getprm2 <tag>`,
  `tsdata`, `com <com> <rx> <data...>`, `exec/aexec`, `boot`, `rst`, `bps`, `tmo`. The read-only ones are a cheap way to read IS
  limits and versions from a future card-console round. [code]+[inferred] 2026-11-06
- **Block 3 ("LUKE") is very likely the IS sub-CPU program**: updater type LUKE = block type 0x10e, written by the same routine as
  BURE (ブレ, "shake") firmware (0x60c3b7ad); its strings are `luke_main\cpu0\ms\...` and `luke_main\cpu1\cmd\task_drive.c` with gyro
  and accelerometer reads. Present in all TruePic IX-era bodies; OM-5's differs in 42% of bytes. ISA not identified. [code]+[inferred] 2026-11-06

- **Body/lens split (Sync IS):** command 13 sends **lens shares** (128 = 100 %) from globals 0x620a8ffa (yaw) / 0x620a8ffb (pitch),
  computed by 0x6010658b (body share +24/+25, lens = 128 − body at +26/+27). Non-cooperative lens: body 128, lens 0. [code] 2026-11-06
- **No stock sender** for commands 11, 31, 35: the transport formatter (0x60117000-0x60118648) encodes them but only `bc com` sends
  them. Tripod HR uses 12, handheld HR 16. [code] 2026-11-06
- **Command ids differ by body:** same up to 18; above that OM-5 id = E-M5 III id − 1 (e.g. IS params 24 ↔ 23). [code] 2026-11-06

## Settings
- Existing: S-IS AUTO/1/2/3/Off, M-IS1/2/Off, IS focal length, panning modes, sequential IS speed/stability, Lens I.S. Priority,
  Half Way Rls With IS. [code] 2026-11-06
- Missing vs OM-5 1.2 / E-M1 III / OM-5 II: movie **"IS Level"** (`MODE_MOVIE_ANTI_SHAKE_STRENGTH`). [code] 2026-11-06
- OM-5 IS Level = setting 1477 → property 6569, read only by the IS host (4 sites); value −1/0/+1 gives gain 0.6/1.0/0.6-or-0 and
  picks one of three IS parameter tables in 0x6011aac6 (OM-5 VMA), which feeds the IS-parameter command. E-M5 III has neither the
  property nor that code. [code]+[inferred] 2026-11-06
- **Correction (2026-11-06, §8.5):** the three parameter sets are **property defaults in the firmware** (props 1394/1410/1602/1618/
  6130/6146: E-M5 III has 18 values = sets A+B, OM-5 has 27 = A+B+C, C = 9 × 128), copied to RAM pointers at init (OM-5 0x6011b6b3,
  E-M5 0x6010c70d). The E-M5 III **does** have the twin function 0x6010bc83 with the level +1 branch (× 0.6), but its 3 callers
  always pass level 0, so +1 is dormant; only −1 (set C) is missing. Property 6569 is free on the E-M5 III. [code] 2026-11-06
- **E-M5 level function in detail (2026-11-07):** 0x6010bc83 arg: +0 x, +2 table pair, +3 table, +4 0 = still / 1, 2 = movie
  variants (meaning of 1 vs 2 unknown), +5 must be 0, +6/+8 formula inputs, **+10 level**, outputs +12/+14. Movie: +2 == 0 ignores
  the level; level +1 gives gain 0.6, but **0 when +4 == 2**; a **direct path** (out = set B × gain) runs only for +4 == 1 and
  level 1; every other case uses the normal formula. OM-5 0x6011aac6: +1 = set B × 0.6 direct, −1 = set C × 0.6 direct. So E-M5
  +1 equals OM-5 +1 **only when +2 != 0 and +4 == 1**; E-M5 −1 is a different (formula) path, not OM-5's −1. The E-M5 never reads
  +11 (corrects the 2026-11-06 "+11 ≥ 64" note, which is OM-5 only). Callers 0x6010af2a (in 0x6010ac0a, rel16 call),
  0x6011ca8a (0x6011c8b8), 0x6011d445 (0x6011d377), frame [d2,d3,a2,a3],32, no indirect caller. [code] 2026-11-07
, check
- **ISL1 built 2026-11-07** (`c985514d…`, base P2b3,, not flashed; sim 1152/1152, check_addrs PASS). **Design:** letter M → gate at 0x600d00a0 writes +10 = 1 only when section 4 is ready, +2 != 0 and +4 == 1;
  ISL2 −1 can be a constant (OM-5 set C is all 128, so interpolation is constant). [code]+[inferred] 2026-11-07

## OM-5 vs E-M5 III
- bc host nearly the same; OM-5 drops commands 22 (ICT log) and 23 (level gauge / horizontal correction state, E-M5 III only) and
  adds body/lens ratio, per-axis max/min correction and "translational correction mode" parameters. So OM-5's LUKE is not drop-in. [code] 2026-11-06

