# Exposure and white balance: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Exposure and white balance](exposure.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

This page covers how the E-M5 III 1.7 main program meters, picks shutter, ISO and aperture, applies exposure
compensation and sets white balance. It is desk research, with no camera runs.[^fw1]

Values are APEX × 256. Tv 8 is 1/256 s and Sv 5 is ISO 100, so the base ISO 200 is Sv 6 = `0x600`. Addresses are
E-M5 III 1.7 block0 addresses unless the OM-5 II 1.1 is named.

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: blue = read in the firmware, grey = inferred, amber = a
correction.

## Layers

| layer | task or code | what |
|---|---|---|
| settings | properties `0x80a1`, `0x80ba`, `0x8121` and more (table below) | metering, compensation, WB, ISO limits, Exposure Shift, anti-flicker |
| AE input builder | one function | copies about 40 settings into one AE input record |
| live view and movie AE | task EXP_MOVIE (CPU0) and EXP_MOVIE2 (CPU2) | "through" AE: per-frame metering, program line, flicker |
| still AE | task TAKE_EXPOSE (CPU0) | still metering at half-press, still exposure context |
| program lines | a walk over 26 tables of 32 B | live-view Sv/Tv/Av curve, sensor mode and frame rate |
| AE parameter records | 167 records of 52 B, ids 257–2086 | per-situation limits and sensor mode/fps pairs ("AE ids") |
| results | properties Tv `0xa02a`, Av `0xa03a`, Sv `0xa04a`. Metered BVs `0xc0ba`, `0xc12a` and more | read by the shooting sequencer and the sensor request |
| live-view and movie WB | task WB_MOV (CPU2) | AWB with hysteresis and Keep warm colour |
| still WB | still record pipeline (`rec_cam_get_awb_exec`, `rec_cpu2_wb`) | AWB gains for the shot, written into the shot metadata |
| flash metering | `stb_seq_metering.c`, task STB_SEQ | pre-flash ("stae") metering, separate from ambient AE |
| debug | shell `exp` | read-only info printers and AE commands |

*The exposure and white balance layers. Roles come from names and neighbours.[^inf1]*

## Settings that feed AE and WB

The AE input builder reads these properties through the property getter. Setting ids and names come from the
[settings map](../bodies/settings-map-om5-technical.md).[^fw1]

| setting | property | name | note |
|---|---|---|---|
| 1 | `0x80a1` | MODE_AE | metering mode, 5 choices, default 2 |
| 103 | `0x8e81` | MODE_AE_AEL | metering used while AEL is held. `0xff` = same as MODE_AE |
| 2 | `0x80ba` | MODE_EXPREV | exposure compensation, ±5 EV (31 values in 1/3 steps) |
| 64 | `0x8bea` | MODE_EXPOSE_STEP | 85 / 128 / 256 = 1/3, 1/2, 1 EV |
| 272–274 | `0x30ea` / `0x30fa` / `0x310a` | MODE_AE_BASE_ADJUST_ESP / CENTER / SPOT | Exposure Shift, 13 values = ±1 EV in 1/6 steps |
| 112 | `0x949a` | MODE_ISO_LIMITER | Auto ISO upper limit, default `0xb00` (ISO 6400) |
| 172 | `0x9a9a` | MODE_ISO_STANDARD | Auto ISO default, `0x600` (ISO 200) |
| 459 | `0xdd51` | MODE_ANTI_FLICKER | live-view flicker setting, values 1, 2, 3, 0 |
| 1464 | `0x1d71` | (no E-M5 name) | still anti-flicker. The OM-5 calls it MODE_ANTI_FLICKER_STILL (setting 1611) |
| 9 | `0x8121` | MODE_WB | white balance, 13 choice records (OM-5: 12) |
| 427 | `0x76b1` | MODE_AUTO_WB_DENKYU_COLORED_LEAVING | Keep warm colour (Auto WB under tungsten) |
| 107 | | MODE_CUSTOM_WB_KELVIN_1 | custom Kelvin |
| 91–96, 212, 144, 213, 573, 575, 337 | | MODE_WB_REV_* | A-B fine tune per preset |
| 133–138, 214, 145, 215, 574, 576, 338 | | MODE_WB_REV_G_* | G-M fine tune per preset |
| 241 | `0x9121` | MODE_FACE_SCAN | face priority. Face BVs are copied when it is 1 |

*Settings read by the AE input builder.[^fw1]*

- **iAuto override.** When scene detection (`0x4501`) is 1 and live guide (`0x91b1` sub 1) is off, exposure
    compensation and WB come from the scene module instead of the settings. The scene module fields are +0x10 and
    +0xd. The scene module runs as task SDET on CPU2.[^fw1]
- Metering is forced to 2, the MODE_AE default, when the movie flag `0x8551` is not 1 and a check function returns
    non-zero.[^fw1] That 2 means ESP is inferred from the default.[^inf1]
- The Olympus API layer numbers metering 0 spot, 1 centre-weighted, 2 ESP, 3 spot highlight and 4 spot shadow, as its
    printer shows.[^fw1]

## Metering

**Data source.** The camera driver's `CAM_AE_SETTING` describes a hardware brightness grid.[^fw1]

- It holds the `bright_data` address, `update`, the area `hs/hdiv/vs/vdiv/hw/vw`, OB windows and Bayer-to-Y gains
    `ae_y shift/gain_rr/gr/gb/bb`. A printer shows it, and the driver files are `cam_bright.c` and `cam_aedrv.c`.
- The grid is **18 × 18** blocks. The strings `BV_18x18`, `y18x18` and `AF_BV_18x18` say so, and `bv_map` prints 18
    values per row.

**Block weights.** `[exp]:calc_w`, `calc_s`, `calc_obw`, `calc_t` and `table_calc_*` build area tables, corner weights,
OB subtraction and the face area. That is read from their names.[^fw2]

### Weighted average

The weighted average uses seven 18 × 18 byte maps, 324 B each, all symmetric.[^fw1]

| # | contents |
|---:|---|
| 0 | full frame, zone classes 1 (outer ring) to 6 (centre 2 × 2) |
| 1 | flat, every cell 2 |
| 2 | 8 × 8 centre, fine weights 51–197, ring of 2 |
| 3 | 14 × 14 centre, classes 2–6 |
| 4 | 8 × 8 centre, classes 2–6 |
| 5 | 14 × 14 centre, fine weights 64–208 |
| 6 | 8 × 8 centre, fine weights 51–197 |

*The seven metering weight maps. Map addresses are in the [address reference](#address-reference).[^fw1]*

- Each cell inside the metering window gets weight = zone weight + brightness term, clamped to 0.1 to 15
    (`0x1a` to `0xf00`).[^fw1]
- The zone weights for classes 6 to 2 are 13, 12, 8, 5 and 4. Class-1 cells and the window edge get a fixed
    0.1.[^fw1]
- The result is sum(cell × weight) / sum(weight).[^fw1]
- The brightness term is the cell Bv minus a reference Bv, looked up in thresholds (+3.2, +3.0, +2.8, +2.5, +2.2,
    +2.0, −2.0, −2.5, −2.8, −3.1 EV). It adds +10, +8, +6, +4, +2, +1, 0, −1, −2.5, −3.3 or −3.6.[^fw1]
- Within ±2 EV nothing changes. A cell over 3 EV brighter than the reference weighs about 3 times a centre
    cell.[^fw1] So bright areas pull the exposure down (highlight protection).[^inf1]
- Map 1 (flat) is used when input flag +0x1f is set.[^fw1]
- When flag +0xc is set and +0xe is over 100, a picker chooses a set by window width. 18 cells wide gives maps 3, 5
    and 5. 10 wide gives maps 4, 6 and 2. The fine maps weigh byte × 16 / 256.[^fw1] That +0xe is a zoom ratio in
    percent (digital tele-converter) is inferred.[^inf1]
- Which method property (`0xc0ba` ESP, `0xc2da` centre) each call feeds is inferred, not traced.[^inf1]
- The BV block reaches the property writer through a callback, which the metering request builder registers.[^fw1]
- The OM-5 II has all seven maps and both weight tables byte-identical.[^fw1]

### Results

There is one BV per method. One function writes them to properties and another reads them back.[^fw1]

| property | value | shell label |
|---|---|---|
| `0xc12a` | spot | `bv_spot` |
| `0xc0ba` | ESP (evaluative) | `bv_esp` |
| `0xc0ca` | average | `bv_ave` |
| `0xc2ea` | second average | `bv_ave2` |
| `0xc2da` | centre | `bv_cntr` |
| `0xc2ca` | surround | `bv_arnd` |
| `0xc57a` | ESP without faces | `bv_face_off_esp` |

*Metered BV properties.[^fw1]*

- Face BVs (8 faces) go to a RAM block when face scan is on.[^fw1]
- A backlight flag (`gyako`, 逆光) and a backlight face rule (`back_light_ae_face_on/off`) adjust the result.[^fw1]
- **Exposure Shift** (custom menu, per metering mode) enters as `ev_zero_calib exp / ave / spot` in the still mode
    block.[^fw1]
- **AF-linked AE.** `exp_af_ae_*` meters on the AF area (`afae_bv`). It is used for the "AF point spot metering" link
    and for contrast-AF exposure. That is read from the names.[^fw2]

## Live-view program lines

**Walk.** A table has up to 20 points {Sv, Tv, Av}, ending at `0x7fff`.[^fw1]

- The walk stops at the first point whose Av + Tv − Sv is below the target Bv. Then it solves the shutter (or ISO) on
    that segment.[^fw1]
- Av 0 means the open aperture. `0x8000` asks the lens, and `0x8002` takes an input value.[^fw1]

**Analog and digital gain.** Each table caps the sensor's analog Sv at +12. `0xa00` is ISO 3200, `0x900` ISO 1600 and
`0xb00` ISO 6400.[^fw1] Anything above the cap, up to 3 EV, is returned as a separate digital-gain value. This matches
`sv_analog` and `sv_digit` in the live-view exposure tag.[^fw1]

**Frame rate.** Each table also names the sensor mode and frame rate by shutter band. So live view slows down as the
scene gets darker.[^fw1] The common table af00 runs these modes.

| shutter band | sensor mode | fps |
|---|---|---:|
| Tv ≥ 8 (1/256 s) | LSSC | 240 |
| from Tv 7 | MSSC | 120 |
| below | HSSC | 60 |

*Sensor mode by shutter band in table af00.[^fw1]*

**The af00 curve.** Av is open throughout.[^fw1]

1. ISO 200 from 1/185,000 s down to 1/256 s.
2. ISO 800 at 1/256 s.
3. Up to ISO 25600 at 1/100 s.
4. ISO 12800 to 25600 at 1/50 s.
5. Ending at ISO 25600 1/30 s.

The values are read in the firmware. That the 1/100 s and 1/50 s steps suit 50 Hz lighting is our reading.[^inf1]

**Tables.** af00 to af19 sit in one block.[^fw1]

- The chooser picks a family by capture mode and other inputs. Then it picks one of three variants by inputs +0x5c and
    +0x60.[^fw1]
- The af0b to af10 family runs FULL_LQ (mode 13) at 30 fps with an ISO 1600 cap.[^fw1]
- The af11 to af13 tables run a fixed 240 fps.[^fw1]
- Which user setting selects which variant is inferred to be the anti-flicker and live-view frame-rate settings, not
    traced.[^inf1]

**Log.** A function prints `[P_Line] table_id/bv/sv/av/tv` when the `exp af 0 1` shell flag is set.[^fw1]

## AE parameter records ("AE ids")

There are 167 records of 52 bytes, ids 257 to 2086.[^fw1]

- A record is `{u32 id, 20 × u16 limits (APEX × 256, 0x80xx = special values), u32 flag, → {sensor mode, fps}
    pairs}`.[^fw1]
- Each record is copied by its own call site (memcpy `0x34`), so code chooses the id, not a lookup.[^fw1]
- These are the "AE ids" the Live ND work saw: 323 = live view MSPD 120 fps, 270 = half-press HSSC, 299 to 302 = Live
    ND.[^fw1] See also: [Live ND](../features/live-nd-technical.md).
- The field meanings are not decoded.[^fw1]

## Still exposure

The still exposure context is reached through a RAM pointer. Its blocks come from the `exp still info` printer.[^fw1]

| offset | block |
|---|---|
| +0 | mode inputs |
| +84 | the set values {tv, sv, av, cv, step, program_shift} |
| +100 | the BV block |
| +324 | the still result: bv, tv, sv, sv_target, av, cv, av_open, av_close, dev, dev_real, program_shift with min and max, tv_max_app / tv_min_app, focal_length, flash |

*Blocks of the still exposure context.[^fw1]*

Full offsets are in our working notes. `dev` is the exposure deviation shown in M mode, and `over` / `over_exp` are the
over-range flags. Both readings come from the names.[^inf1]

### Still program line

`exp_cal_still` runs three steps.[^fw1]

1. Limits.
2. A low-light limit.
3. The program (a separate one for normal modes).

There is no fixed curve. The line is built from a per-mode limit template.[^fw1]

**Templates.** There are 65 records of 70 B, with the mode id (u16) at +68, zero-terminated.[^fw1]

- A lookup finds a template, with error `0x0e004504` on a miss. Ids include `0x03` to `0x07`, `0x3a`, `0x45` to
    `0x4a` and `0xc6` to `0xdb`.[^fw1]
- Each of the 34 fields is an APEX value or a code that a resolver fills in at run time. `0x9e00` and `0x9d00` take the
    low and high bound of the current range (context +0x14 / +0x16). `0x9c00` takes a computed value.[^fw1] That the
    range is the Auto ISO limits is inferred.[^inf1]
- Fixed values seen are Sv `0x400` / `0x600` / `0x700` (ISO 50 / 200 / 400), Tv `0x45c` (about 1/20 s), Tv `0xd00`
    (1/8000 s) and Tv `0xfa00` (60 s).[^fw1]

**Program.** The normal-mode program turns the limits into 11 Bv breakpoints. It finds the segment for the metered Bv
and fills the result (+6, +8, +14).[^fw1]

- Segment 4 splits the remaining EV evenly between two outputs, the diagonal of the line.[^fw1]
- Segments 5 and 7 use helper functions.[^fw1]
- ISO is rounded to 1/3 EV (`0x55`, `0xaa`).[^fw1]

**Program shift** (input +14, from property `0x8e5a`) subtracts from one output and adds to the other. Then it clamps
both to the template limits.[^fw1]

- It applies only for a list of 27 mode ids, including `0x03`.[^fw1]
- The over and under margins at result +0x2c / +0x2e are capped at ±5 EV.[^fw1]
- Modes `0x06`, `0x3a` and `0xd2` take a fixed-value branch instead, with a 1/16-step rounding table.[^fw1]

**OM-5 II.** It has the same 65 ids in the same order. The ISO and aperture fields are identical.[^fw1]

- The shutter fields became run-time codes: `0xd00` to `0xa300`, `0xfa00` to `0xa400` and `0x45c` to
    `0xa200`.[^fw1]
- So the OM-5 II resolves its shutter range per body instead of fixing it.[^inf1]
- 63 of 65 records differ only that way.[^fw1]

### Output

The result goes to properties Tv `0xa02a`, Av `0xa03a` and Sv `0xa04a`, with `0xc55a` and `0xa05a`, copied together at
two sites.[^fw1]

The shooting sequencer copies them into the shot's exposure record at StlRdy1. That record feeds the type-7 still
sensor request (exposure block +4) and the lens aperture command.[^fw1] See also:
[shooting sequencer](shooting-sequencer.md#the-exposure-record),
[sensor](../hardware/sensor-technical.md#sensor-mode-requests) and
[lens communication](../hardware/lens-communication-technical.md).

## Flicker

- The live-view anti-flicker setting is `0xdd51` (Auto, 50 Hz, 60 Hz, Off by the menu). The value mapping is not
    traced.[^fw1]
- Detection results are `MOVE_FLICKER` and `STOP_FLICKER` (movie and still variants), `NO_FLICKER`, and the
    `100Hz FLICKER` and `120Hz FLICKER` debug lines.[^fw1]
- `exp movie flick` prints or forces the result.[^fw1]
- Still anti-flicker property `0x1d71` is read by the AE input builder and by one other function. The OM-5 offers it as
    a menu item (MODE_ANTI_FLICKER_STILL).[^fw1] Whether any E-M5 III menu row reaches it is open.

## White balance

**Statistics.** The camera driver has two AWB statistics blocks (`awb_setting`, `awb2_setting`, "AWB1/AWB2
depth/address").[^fw1]

- The image pipeline allocates AWB and luminance-AWB buffers (`E_adr_awb_alloc`, `E_AWBinit`,
    `E_awbFAll1/2`).[^fw1]
- The pre-process record carries an 8-bin AWB histogram and per-channel OB, as a printer shows.[^fw1]

**Gains.** Each frame has these gain sets, as a printer shows.[^fw1]

| offset | gains |
|---|---|
| +188 | `WbGain[4]` |
| +196 | `WbGainImgPro[4]` |
| +204 | `WbGainBayer[4]` |
| +212 | `WbGain5300K[4]`, reference set |
| +220 | `WbGain7500K[4]`, reference set |

*Per-frame white balance gains.[^fw1]*

The work struct `stWBGainWork` holds two candidate gain sets with a colour temperature each, the result, a thumbnail set
and the A-B and G-M shifts (`chWBShiftRB`, `chWBShiftGM`).[^fw1]

**Live view and movie** WB runs in task WB_MOV on CPU2, which also reads Keep warm colour. The task and its property
reads are read in the firmware. Its algorithm is not traced.[^fw1]

**Still** WB is finished in the still record pipeline.[^fw1]

- Its trace ids are `rec_cam_get_awb_exec` (`0x40`), `rec_precon_wb_exec` (`0x22`) and `rec_main_cpu2` /
    `rec_cpu2_wb` (`0xc4` / `0xc5`), in one table.[^fw1]
- The black level and WB values are filled at the metadata step
    ([sensor](../hardware/sensor-technical.md)).[^fw1]
- That the still AWB maths runs on CPU2 is inferred from the names.[^inf1]

The string `wb_detect_gain_shift(_art, _guide) is not supported for DC11 platform` shows that a WB-detect gain shift
that newer chips have is stubbed on this one.[^fw1]

### Live-view AWB call chain

1. WB_MOV waits on its CPU queue.
2. Two callers call the parameter builder.
3. The builder fills a parameter block: statistics buffer, WB mode `0x8121`, `0xc011`, `0x8131`, `0x8a61` / `0x8f22`,
   and Keep warm colour `0x76b1` only in auto.
4. It calls the AWB library.

The chain is read in the firmware.[^fw1]

**AWB library.** Its entry allocates a `0x3d98`-byte work area and initialises it.[^fw1]

- It runs the auto estimator for WB mode 0 or 4 (auto), or a second estimator for mode 2. Then a third function writes
    the gains.[^fw1]
- The parameter builder keeps two gain pairs per mode, one set for auto and one for mode 4.[^fw1]
- The estimator is about 15 KB of code that has no Ghidra C yet. It calls math helpers and reads 5-short records and
    small tables.[^fw1]
- On the OM-5 II the library entry points keep their shape. The init, the estimator and the WB_MOV glue
    changed.[^fw1]

### Auto estimator

The steps were decoded from a cloud Ghidra export.[^fw3] The meanings are inferred.[^inf1]

1. It rotates the reference white points (work +0x6a4, from 13-point sets) by about 43 degrees. One axis then follows
   the colour-temperature locus and the other is green-magenta.
2. It builds piecewise-linear locus bounds over 81 steps and an 81 × 81 colour histogram (work +0x72a).
3. It computes scene Bv from the mean statistics level, as 256 / ln 2 × ln(level / target) + exposure Bv (soft float).
4. For each locus step it finds the histogram peak and scores how concentrated it is.
5. It weights 8 colour-temperature zones by scene Bv, with full weight below a low Bv and 0.2 above a high Bv. Zone 0
   is 6.5 / 9 EV, zone 1 4 / 7, zones 2 to 4 4 / 5, zone 5 fixed 19, zone 6 9 / 11 and zone 7 6.5 / 9. So bright
   scenes discount some light-source zones.
6. It accumulates the weighted mean (R/G, B/G) and clamps it to the locus band. It compares two candidates when a
   target is set, and blends with the last result (hysteresis).
7. It writes the gains and a confidence code to the parameter block (+0xfc / +0xfe, +0x100).

Which light source each reference point stands for is still open.

## Flash metering is separate

`stb_seq_metering.c` and `stb_seq_expose.c` meter the pre-flash ("stae" = strobe AE). They cover normal and pre values,
AF and face areas and `stb_ae_ratio`, and they set the flash WB gain (`stb_expose_get_wb_gain`).[^fw1]

They run in task STB_SEQ, next to STB_CHARGE and STB_EXTERNAL. So **STB_SEQ is the strobe (flash) sequencer, not a
standby sequencer**.[^fix1] This corrects [OS and framework](os-and-framework.md) and [Boot](../guides/boot.md).

See also: [Flash and hot shoe](../hardware/flash-technical.md#a-flash-shot).

## Debug shell `exp`

Read-only printers are safe over the [Wi-Fi debug shell](../features/wifi-debug-shell-technical.md).[^fw4]

- Read-only: `exp dbginfo`, `exp still on` then `exp still info`, `exp movie mode`, `exp movie bv [flags]`,
    `exp movie bvmap`, `exp cam ae 1`, `exp cam exp 1`, `exp lens 1`, `exp af 0 1` (program-line log),
    `exp movie flick get` and `exp sconf 4` (shutter range).
- Commands that change state: `exp com`, `exp movie cap`, `exp movie flick move/stop`, `exp zoom` and `exp eye`.

## OM-5 II comparison

- The OM-5 II has the same tasks: EXP_MOVIE, TAKE_EXPOSE, EXP_MOVIE2 (CPU2), WB_MOV (CPU2) and STB_SEQ.[^fw1]
- 721 of the E-M5 III's 1,681 exposure-module functions keep their exact shape (43%), and 36 of 46 in the
    program-line code. The module was reworked, not replaced.[^fw1]
- Live-view program lines af00 to af19 are **byte-identical**.[^fw1]
- The OM-5 II adds af1a to af1d: FULL_LQ at 30 fps, analog cap ISO 1600, shutter down to 1/8 s.[^fw1] These look like
    a night live-view mode.[^inf1]
- The 52-byte AE parameter record table is not in the same layout. There is no run of ids 257, 258, 259 at any stride
    from 48 to 64.[^fw1]
- New on the OM-5 II are these.[^fw1] Their meanings come from the names.[^inf1]
    - A "CPU2 response wait: metering calculate" state, so part of metering is handed to CPU2.
    - Separate still ESP values (`bv_esp_still`), `force_full_area_metering` and `metering_type`.
    - A second AE grid (`ae2_expand`).
    - Detailed flicker detection for stills and movies (`flickS`, `flickM`).
    - Shell `exp pline`, `exp frame`, `exp anl` and `exp self`.
    - Movie one-touch WB (`TAKE_MOVIE_OTWB_*`), `WB_MOV_HYS_RESET` and `wb_bias_a/g`.
    - Flash metering that ignores overexposed areas (`stae_*_exclude_over`).


## Open questions

- The AE parameter record fields, and which program-line output is Tv and which is Av.
- Which metering property each weighted-average call feeds, and what the reference Bv is.
- The light source behind each AWB reference point, and what the two statistics blocks measure.
- Which setting value selects which live-view table variant.
- Whether any E-M5 III menu row reaches the still anti-flicker property.
- A read-only camera check with `exp still info` and `exp movie bv 1` would confirm the offsets.

## Address reference

E-M5 III 1.7 block0 addresses unless a body is named.

| item | address |
|---|---|
| AE input builder, its caller | `0x60448b2f`, from `0x60449487` |
| EXP_MOVIE entry, EXP_MOVIE2 entry | `0x6040fdaf`, `0x6040fdbc` |
| TAKE_EXPOSE entry | `0x60442be9` |
| still exposure context pointer | `*(0x621694b8)` |
| WB_MOV entry | `0x60352daf` |
| STB_SEQ entry | `0x6017dfc3` |
| `stb_seq_metering.c` | `0x6017ca1c` to `0x6017dc3d` |
| shell `exp` help | `0x61460000` to `0x61466c00` |
| OM-5 II tasks: EXP_MOVIE, TAKE_EXPOSE, EXP_MOVIE2 | `0x6042d776`, `0x60462052`, `0x6042d783` (OM-5 II) |
| OM-5 II tasks: WB_MOV, STB_SEQ | `0x60368ee3`, `0x601911a1` (OM-5 II) |
| property getter | `0x6005ce6b` |
| scene module, its WB and compensation reads | `0x603d73b4`, `0x6044bce8`, `0x6044bc40` |
| metering-forced check, its site | `0x6056359c`, `0x6044b736` |
| API metering printer | `0x6081c573` |

*Tasks, settings and the input builder.*

| item | address |
|---|---|
| `CAM_AE_SETTING` printer | `0x60411012` |
| block weight builders | `0x60413dbd` to `0x604141cf`, `0x60425f01` to `0x60426b95` |
| weighted average | `0x60415ad7` |
| weight maps 0 to 6 | `0x60543108`, `0x6054324c`, `0x60543390`, `0x605434d4`, `0x60543618`, `0x6054375c`, `0x605438a0` (end `0x605439e3`) |
| zone weights | `0x60543a02` |
| brightness term, thresholds, additions | `0x60415d06`, `0x60543a0c`, `0x60543a7a` |
| map set picker | `0x60413d4a` |
| BV property writer, read-back | `0x60448129`, `0x6044a2c3` |
| callback, request builder, registration | `0x6044933d`, `0x604489a3`, `0x604486ef` |
| OM-5 II maps, weight tables | `0x60581b02`, `0x605823fc` (OM-5 II) |
| face BVs | `0x62170990` to `0x621709d0` |
| backlight face rule | `0x60418812` |
| `exp_af_ae_*` | `0x6041192e` to `0x60412ae9` |

*Metering.*

| item | address |
|---|---|
| program line walk | `0x60418d8f` |
| program line tables af00–af19 (26 × 32 B) | `0x60544e70` |
| open aperture, lens aperture | `0x6043488f`, `0x604348a9` |
| table chooser, variant pick | `0x60419137`, `0x60419316` |
| `[P_Line]` log | `0x6042d13a` |
| AE parameter records | `0x605476cc` |
| example record copy site | `0x604228c0` |
| `exp still info` printer | `0x61429c00` to `0x6142a3a0` |
| `exp_cal_still` | `0x6041a92d` |
| limits, low-light limit | `0x6041b197`, `0x6041af81` |
| program, program for normal modes | `0x6041b8d9`, `0x6041bf30` |
| limit templates, lookup, resolver | `0x60545ad2`, `0x6041b504`, `0x6041b55e` |
| computed value | `0x6041d22e` / `0x604418b1` |
| segment 5 and 7 helpers | `0x6041c6d0`, `0x6041c849` |
| program shift mode list check | from `0x6041bb0a` |
| 1/16-step rounding table | `0x60545ab0` |
| OM-5 II limit templates | `0x605846ea` (OM-5 II) |
| result copy sites | `0x60449886`, `0x60439fc7` |
| exposure record fill at StlRdy1 | `0x602c0cb0` |

*Program lines and still exposure.*

| item | address |
|---|---|
| flicker debug lines | `0x6054bf04`, `0x6054c02b` |
| still anti-flicker reader | `0x6044c18f` |
| AWB buffer allocation | `0x6032509c` to `0x603296ec` |
| pre-process record printer | `0x603fc144` |
| per-frame gains printer, work struct printer | `0x6141c7ad`, `0x61424f9c` |
| still WB trace id table | `0x60540798` |
| metadata step | `0x6040c7f5` |
| DC11 stub string | `0x6044d62c` |
| WB_MOV callers of the builder | `0x603532ea`, `0x60353382` |
| parameter builder | `0x6035386a` |
| AWB library call | `0x60299139` |
| AWB library | `0x60298000` to `0x6029fd49` |
| library entry, init | `0x602992dc`, `0x60299360` |
| auto estimator, mode 2 estimator, gain writer | `0x6029af79`, `0x6029eb0c`, `0x6029ed3c` |
| auto gain pairs, mode 4 gain pairs | `0xa265e742` to `0xa265e74c`, `0xa265e754` to `0xa265e75e` |
| math helpers | `0x600e21cf` to `0x600e2311` |
| 5-short records (13-point white sets) | `0x6044d42c` |
| small tables | `0x6044d56c` to `0x6044d60c` |
| zone Bv tables | `0x6044d6f2` / `0x6044d6e2` |
| locus band clamps | `0x6029a5ff`, `0x6029aa9f` |
| candidate compare | `0x6029a378`, `0x6029a3fe` |
| OM-5 II library entry points | `0x602a09ef`, `0x602a0fdd` (OM-5 II) |

*Flicker and white balance.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware, 2026-11-25.
[^fw2]: Read from function names in the firmware, 2026-11-25.
[^fw3]: Read in the firmware through a Ghidra export of the AWB library, 2026-11-25.
[^fw4]: Read from the shell's help strings, 2026-11-25. Not run.
[^inf1]: Inferred, 2026-11-25.
[^fix1]: Corrected on 2026-11-25. The older reading is in [History](#history).

## History

- 2026-11-25: older notes, including [OS and framework](os-and-framework.md) and [Boot](../guides/boot.md), called
  STB_SEQ a standby sequencer. It is the strobe (flash) sequencer.

