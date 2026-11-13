# Movie: recording limit and OM-Log400

Two movie questions are covered here. First, the E-M5 III stops recording at 29 minutes 59 seconds; where is that limit,
and could it be lifted as on the OM-5? Second, the OM-5 has a flat "OM-Log400" picture profile for colour grading; how
much of it already exists on the E-M5 III?

The short answers: the time limit is a single constant, and much of the log-profile plumbing is already present but
the part that picks the log curve is missing.

Tags: **[code]** read in the firmware, **[inferred]** not traced or tested.

Status: read-only research 2026-11-07, nothing built. Roadmap: recording limit,
OM-Log400.

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
