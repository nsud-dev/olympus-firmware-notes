# Movie recording: technical notes

> **Technical notes.** This page is the dense reference. For a readable introduction, start with [Movie recording](movie.md).

Two movie questions are covered here. First, the E-M5 III stops recording at 29 minutes 59 seconds; where is that limit,
and could it be lifted as on the OM-5? Second, the OM-5 has a flat "OM-Log400" picture profile for colour grading; how
much of it already exists on the E-M5 III?

The short answers: the time limit is a single constant, and much of the log-profile plumbing is already present but
the part that picks the log curve is missing.

Tags: **[code]** read in the firmware, **[inferred]** not traced or tested.

Status: read-only research 2026-11-07, nothing built. Roadmap: recording limit,
OM-Log400.

## How a movie is made (pipeline facts, 2026-11-21)

- Sensor modes per movie size and the crop/scale table: see [sensor modes](../hardware/sensor-technical.md#sensor-modes-2026-11-21).
  4K = 1:1 centre crop, C4K = full width, FHD = 2x2 binned band. [code]+[inferred]
- The movie scaler is the fixed image pipeline set from that table (non-integer ratios such as 5184 → 4096). DSP job 10 is
  not part of it (its caller is the still task). [code]+[inferred]
- **Encoder:** H.264 only, Panasonic-style AVpi framework (`CAvpiVenH264*`, `SAvScaEncVideoParam` with Hsize/Vsize/MaxHsize/
  MaxVsize). Rate control's level table (jump at 0x6117e4ba) stops at **Level 5.1** (983040 macroblocks/s, 36864 per
  frame). No HEVC (the OM-1 adds it). [code]
- **Where the recording size is set:** switch at 0x603ecf4b in the record-init chain. Resolution byte 5 → 4096 x 2160,
  6 → 3840 x 2160, 2 → 1280 x 720, 3 → 640 x 480, 4 → 640 x 360, anything else → 1920 x 1080 (Hsize +16, Vsize +20, size
  word +56). Max size +24/+28 is 4096 x 2160 for 5 and 6, else 1920 x 1080. Bitrate rows of 80 bytes per code from
  0x6053a584. The same size constants recur in many other movie modules (pipeline setup, YC buffers, display, metadata). [code]
- About 21 encoder branches test `height == 2160` for 4K special cases; two test `>= 2160`. [code]
- The encoder's video-source stage (CAvpiVsoVideoSource 0x6118ce61..0x6118d0ff) knows a fixed size list: 720 x 480 to
  1920 x 1088, **2048 x 1536, 2560 x 1920**, 3840 x 2160, 4096 x 2160; other sizes get a small default class. [code]
- In-camera playback (CAvpiVdeCodec 0x6116ac26) rejects width > 4096 or height > 2160. [code]
- Movie YC 4:2:0 pool 0x2f00 (`IMGBUFF_ALOC_MOV_YC420`): 9 slots of 0xca8000 = 4096 x 2160 x 1.5. [code]
- Pipeline load today: 4K30 about 288 Mpx/s, C4K24 about 350 Mpx/s; C4K has no 30p. Same tables in the E-M1 III, so this
  looks like a processor limit, not segmentation. [inferred]

## The 29:59 recording limit

The limit is a maximum recording time in milliseconds that the movie encoder is given when recording starts.

- Enforced by the encoder record-init parameter `ulMaxRecTime` (+68 of `SAvScaEncAVParam`, **milliseconds**). Filler
  **0x603ecd04**: if the caller's max time (cfg+16) is 0, kind (cfg+22) 3 or 4 → 7200000 (2 h), else **1800000 (30:00) at
  0x603ecdb3** (`fc cc 40 77 1b 00`). Chain: `MovmidApi_cmd_rec_init` 0x603eb4a1 → 0x603ecb57 → 0x603ecc0f → 0x603ecd04. [code] 2026-11-07
- Request built at 0x6033e00a (msg 0x1001): cfg+16 = src+8 (caller 0x6032b4a8 passes 0), cfg+22 from src+2 (4→4, unknown→3).
  Which recording kind already gets 2 h is open. [code]/[inferred] 2026-11-07
- OM-5 1.2 / OM-5 II 1.1 have **no 30-minute branch** (always 7200000 when the caller passes 0; OM-5 0x604034d4). E-M5 III,
  E-M1 III 1.6 and PEN-F 3.1 carry the 1800000 constant; OM-1/OM-1 II neither. [code] 2026-11-07
- No second limit constant found (1799/1800 hits are trace ids, error records, 90 kHz frame durations). UI remaining-time
  display not traced. [code]/[inferred] 2026-11-07
- A card mod that patches this immediate at run time (and restores it when switched off) works in om-emu; not yet run on
  the camera. [emu] 2026-11-22

## OM-Log400

A log profile records a very flat tone curve to keep more highlight and shadow detail for grading later.

- OM-5 implements it as **colortone (picture mode) 24 `M_LOG`** (23 = `SUPERFLAT`), plus settings `MODE_EXPANDED_CONTRAST_MODE`
  (HLG/SUPERFLAT/LOG) and `MODE_EXPANDED_CONTRAST_LV` (View Assist); GUI "OM-Log400" (OM-5 English 3846), "View Assist" (3575). [code] 2026-11-07
- E-M5 III colortone values 0-22 match OM-5; 23-60 print "NOT SUPPORTED!!" (debug table 0x60af9f14), PLACAME = 61 vs OM-5 62.
  E-M5 III settings: `MODE_EXPANDED_CONTRAST` = OFF/SUPERFLAT only. [code] 2026-11-07
- **AE plumbing already in E-M5 III:** the through-image exposure tag has `+82 mode_expanded_contrast` and `+83
  mode_expanded_contrast_mode`, filled at 0x60427b6a exactly like OM-5 0x60440b8f (idle default 0/254). [code] 2026-11-07
- Missing on E-M5 III: the selection of the log curve in the develop/movie parameter builder, View Assist, a setting/menu
  value (via the menu route). We first thought the data might live in block 2 sub E-M5 0x45b20000 ↔ OM-5 0x44860000 (70 % match);
  corrected 2026-11-07: that sub is bank 6 (DSP jobs), and its difference is jobs 11-18. [code]
- **Image-engine resource banks 0-4 and 7 are byte-identical in E-M5 III 1.7, E-M1 III 1.6 and OM-5 1.2** (bank 5 E-M5 = OM-5).
  If the log tone data is resource data, E-M5 III already has it. [code] 2026-11-07
- No new tone-curve LUT in OM-5 block0 (monotone u16/u32 scan, 63-entry picture-mode table test): the curve is parameters in
  the shared banks picked by code, or computed. [code]/[inferred] 2026-11-07
- Picture-mode values: OM-5 inserted M_LOG at 24, so E-M5 III values ≥ 24 = OM-5 − 1 (icon switches E-M5 0x60cb12d7, OM-5
  0x60d722a4). E-M5 III already handles value 23 (likely SUPERFLAT). A port must give M_LOG another E-M5 number and map it in
  the builder, not renumber. [code]/[inferred] 2026-11-07
- Next: follow OM-5 frame_param `mode_colortone` (+32) into the develop-parameter builder and its resource-loader calls
  (OM-5 loader 0x60178a66) to the bank entry chosen for 23/24; then a cheap forced picture-mode-23 movie test on E-M5 III.
  [inferred] 2026-11-07

## On the E-M5 II and E-M5 (Mark I) (2026-11-21)

- **Recording limit:** the 1800000 ms (30-minute) constant is present on both the E-M5 II 4.1 and the E-M5 Mark I 2.3, next to 7200000; where it is used was not traced. [code]
- **OM-Log400:** neither has the `expanded_contrast` plumbing the E-M5 III kept, so the cheap route on this page doesn't exist there. [code]
- Their movie code is a different, older stack (the E-M5 II shares the PEN-F's `movp_*` files; the E-M5 Mark I has QuickTime/MJPEG writers), so nothing here carries over directly. [code]+[inferred]

Full comparison: [older bodies](../bodies/comparison-technical.md#older-bodies-e-m5-ii-and-e-m5-mark-i-2026-11-21).
