# Movie recording: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Movie recording](movie.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

Two movie questions are covered here. First, the E-M5 III stops recording at 29 minutes 59 seconds. Where is that
limit, and could it be lifted as on the OM-5? Second, the OM-5 has a flat "OM-Log400" picture profile for colour
grading. How much of it already exists on the E-M5 III?

The short answers follow. The time limit is a single constant. Much of the log-profile plumbing is already present,
but the part that picks the log curve is missing.

Status: read-only research, nothing built.[^fw2]

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred or seen in an emulator, amber = a correction.

## Movie pipeline

- **Sensor modes.** Each movie size has its own sensor mode, and a table sets the crop and scale. 4K is a 1:1 centre
  crop. C4K uses the full width. FHD is a 2 × 2 binned band.[^fw1][^inf1] See
  [sensor modes](../hardware/sensor-technical.md#sensor-modes).
- **Scaler.** The movie scaler is the fixed image pipeline set from that table. It already uses non-integer ratios such
  as 5184 → 4096. Image-engine job 10 is not part of it, because its caller is the still task.[^fw1][^inf1]
- **Encoder.** It is H.264 only, in a Panasonic-style AVpi framework (`CAvpiVenH264*`, `SAvScaEncVideoParam` with
  Hsize/Vsize/MaxHsize/MaxVsize). The rate-control level table stops at Level 5.1 (983040 macroblocks/s, 36864 per
  frame). There is no HEVC. The OM-1 adds it.[^fw1]
- **4K branches.** About 21 encoder branches test `height == 2160` for 4K special cases. Two test `>= 2160`.[^fw1]
- **Video-source sizes.** The encoder's video-source stage (`CAvpiVsoVideoSource`) knows a fixed size list. It runs
  from 720 × 480 to 1920 × 1088, then 2048 × 1536, 2560 × 1920, 3840 × 2160 and 4096 × 2160. Other sizes get a small
  default class.[^fw1]
- **Playback.** In-camera playback (`CAvpiVdeCodec`) rejects width > 4096 or height > 2160.[^fw1]
- **Movie YC pool.** The 4:2:0 pool `IMGBUFF_ALOC_MOV_YC420` has 9 slots of `0xca8000` bytes, which is
  4096 × 2160 × 1.5.[^fw1]
- **Pipeline load.** 4K30 needs about 288 Mpx/s today, and C4K24 about 350 Mpx/s. C4K has no 30p. The same tables are
  in the E-M1 III, so this looks like a processor limit, not segmentation.[^inf1]

### Recording size

The recording size is set by a switch in the record-init chain.[^fw1]

| resolution byte | size |
|---:|---|
| 5 | 4096 × 2160 |
| 6 | 3840 × 2160 |
| 2 | 1280 × 720 |
| 3 | 640 × 480 |
| 4 | 640 × 360 |
| anything else | 1920 × 1080 |

*The encoder's size switch. Read in the firmware.*

- The switch writes Hsize at +16, Vsize at +20 and the size word at +56.[^fw1]
- The max size at +24/+28 is 4096 × 2160 for 5 and 6, else 1920 × 1080.[^fw1]
- Bitrate rows are 80 bytes per code.[^fix1] The full table is in
  [movie encoder stack](../firmware/movie-stack-technical.md#bitrate-table-mbits).
- The same size constants recur in many other movie modules (pipeline setup, YC buffers, display, metadata).[^fw1]

## The 29:59 recording limit

The limit is a maximum recording time in milliseconds that the movie encoder is given when recording starts.

- **The parameter.** The encoder enforces it through the record-init parameter `ulMaxRecTime`. It sits at +68 of
  `SAvScaEncAVParam` and is in milliseconds.[^fw2]
- **The filler.** If the caller's max time (cfg+16) is 0 and the size code (cfg+22) is 3 or 4 (640 × 480, 640 × 360),
  the filler sets 7200000 (2 h).[^fix2] Otherwise it sets 1800000 (30:00).[^fw2]
- **The chain.** The record-init chain runs from `MovmidApi_cmd_rec_init` through two more functions to the
  filler.[^fw2]
- **The request.** The request is built as msg `0x1001`. cfg+16 = src+8, and the caller passes 0. cfg+22 comes from
  src+2 (4→4, unknown→3).[^fw3]
- **Who gets two hours.** cfg+22 is the movie size code (5 C4K, 6 4K, 1 FHD, 2 HD, 3 640 × 480, 4 640 × 360). So only
  the 640-wide sizes get 2 h.[^fw3] See
  [movie encoder stack](../firmware/movie-stack-technical.md#record-request-0x6033e00a).

### Other bodies

The OM-5 1.2 and OM-5 II 1.1 have no 30-minute branch. They always set 7200000 when the caller passes 0. The E-M5 III,
E-M1 III 1.6 and PEN-F 3.1 carry the 1800000 constant. The OM-1 and OM-1 II carry neither.[^fw2]

### Lifting the limit

- No second limit constant was found. The 1799 and 1800 hits are trace ids, error records and 90 kHz frame
  durations.[^fw2] The UI remaining-time display was not traced.[^inf2]
- The change is one immediate, set to 7200000 (the OM-5 value), with no hook.[^inf2]
- A card mod patches this immediate at run time and restores it when switched off. It works in om-emu. It has not yet
  run on the camera.[^emu1]

## OM-Log400

A log profile records a very flat tone curve to keep more highlight and shadow detail for grading later.

### On the OM-5

The OM-5 implements it as colortone (picture mode) 24 `M_LOG`. 23 is `SUPERFLAT`. Two settings go with it.[^fw2]

- `MODE_EXPANDED_CONTRAST_MODE` (HLG/SUPERFLAT/LOG)
- `MODE_EXPANDED_CONTRAST_LV` (View Assist)

The GUI strings are "OM-Log400" (OM-5 English 3846) and "View Assist" (3575).[^fw2]

### On the E-M5 III

- **Picture modes.** E-M5 III colortone values 0-22 match the OM-5. Values 23-60 print "NOT SUPPORTED!!" in a debug
  table. PLACAME is 61, against 62 on the OM-5.[^fw2]
- **Settings.** `MODE_EXPANDED_CONTRAST` has OFF and SUPERFLAT only.[^fw2]
- **Exposure plumbing.** It is already in the E-M5 III. The through-image exposure tag has `+82 mode_expanded_contrast`
  and `+83 mode_expanded_contrast_mode`. They are filled exactly as on the OM-5 (idle default 0/254).[^fw2]
- **Resource banks.** Image-engine resource banks 0-4 and 7 are byte-identical in E-M5 III 1.7, E-M1 III 1.6 and
  OM-5 1.2. Bank 5 of the E-M5 III equals the OM-5's. If the log tone data is resource data, the E-M5 III already has
  it.[^fw2]
- **No new curve table.** OM-5 block0 has no new tone-curve LUT (monotone u16/u32 scan, 63-entry picture-mode table
  test). The curve is parameters in the shared banks picked by code, or computed.[^fw2][^inf2]

### What is missing

- the selection of the log curve in the develop/movie parameter builder
- View Assist
- a setting and menu value (via the menu route)

An early guess put the log data in a block 2 sub-block that matches the OM-5's at 70%. That sub-block is bank 6
(image-engine jobs), and its difference is jobs 11-18.[^fix3]

### Picture-mode numbering

The OM-5 inserted `M_LOG` at 24. So E-M5 III values ≥ 24 equal the OM-5 value − 1 (see the icon switches in the address reference). The
E-M5 III already handles value 23 (likely SUPERFLAT). A port must give `M_LOG` another E-M5 number and map it in the
builder, not renumber.[^fw2][^inf2]

## Older bodies

- **Recording limit.** The 1800000 ms (30-minute) constant is present on both the E-M5 II 4.1 and the E-M5 Mark I 2.3,
  next to 7200000. Where it is used was not traced.[^fw1]
- **OM-Log400.** Neither has the `expanded_contrast` plumbing the E-M5 III kept. So the cheap route on this page
  doesn't exist there.[^fw1]
- **Movie code.** Their movie code is a different, older stack. The E-M5 II shares the PEN-F's `movp_*` files. The
  E-M5 Mark I has QuickTime/MJPEG writers. So nothing here carries over directly.[^fw1][^inf1]

See also: [older bodies](../bodies/comparison-technical.md#older-bodies-e-m5-ii-and-e-m5-mark-i).

## Open questions

- Whether the remaining-time display has its own cap, how a longer recording handles the 4 GB file split, and heat
  over a long recording.[^inf2]
- For OM-Log400, the next step is to follow the OM-5 frame_param `mode_colortone` (+32) into the develop-parameter
  builder and its resource-loader calls, to the bank entry chosen for 23/24. Then a cheap forced picture-mode-23 movie
  test on the E-M5 III.[^inf2]

## Address reference

E-M5 III 1.7 addresses unless a body is named. Functions are block0 addresses (base `0x60021020`).

| item | address |
|---|---|
| rate-control level table jump | `0x6117e4ba` |
| recording size switch | `0x603ecf4b` |
| bitrate rows | `0x6053da84` |
| `CAvpiVsoVideoSource` | `0x6118ce61` to `0x6118d0ff` |
| `CAvpiVdeCodec` playback size check | `0x6116ac26` |
| movie YC 4:2:0 pool | pool id `0x2f00` |

*Movie pipeline.*

| item | address |
|---|---|
| max-time filler | `0x603ecd04` |
| 1800000 (30:00) constant | `0x603ecdb3` |
| immediate to change | `0x603ecdb5` |
| record-init chain | `MovmidApi_cmd_rec_init` `0x603eb4a1` → `0x603ecb57` → `0x603ecc0f` → `0x603ecd04` |
| request builder (msg `0x1001`) | `0x6033e00a` |
| caller passing max time 0 | `0x6032b4a8` |
| OM-5 filler | `0x604034d4` (OM-5) |

*Recording limit.*

| item | address |
|---|---|
| colortone debug table | `0x60af9f14` |
| exposure tag fill | `0x60427b6a` (OM-5 `0x60440b8f`) |
| picture-mode icon switch | `0x60cb12d7` (OM-5 `0x60d722a4`) |
| OM-5 resource loader | `0x60178a66` (OM-5) |
| block 2 sub-block (bank 6) | `0x45b20000` (OM-5 `0x44860000`) |

*OM-Log400.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware, 2026-11-21.
[^inf1]: Inferred, not traced or tested, 2026-11-21.
[^fw2]: Read in the firmware, 2026-11-07.
[^inf2]: Inferred, not traced or tested, 2026-11-07.
[^fw3]: Read in the firmware, 2026-11-25.
[^emu1]: Seen in om-emu, 2026-11-22.
[^fix1]: Address corrected 2026-11-25. See [History](#history).
[^fix2]: Corrected 2026-11-25. cfg+22 was first read as a recording kind. See [History](#history).
[^fix3]: Corrected 2026-11-07. See [History](#history).

## History

- 2026-11-07: the log data was first thought to live in the block 2 sub-block (E-M5 `0x45b20000`, OM-5 `0x44860000`, 70% match). That sub-block is bank 6 (image-engine jobs).
- 2026-11-25: the bitrate rows were first placed at `0x6053a584`. They start at `0x6053da84`.
- 2026-11-25: cfg+22 was first read as a recording kind, and which kind gets 2 h was open. It is the movie size code.

