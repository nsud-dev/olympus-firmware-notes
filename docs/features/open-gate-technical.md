# Open gate video: technical notes

> **Technical notes.** This page is the dense reference. For a readable introduction, start with [Open gate video](open-gate.md).

Could the E-M5 III record video from the whole 4:3 sensor area instead of the 16:9 band? Read-only research, nothing
built or run. Addresses are E-M5 III 1.7 block0 VMAs.

Tags: **[code]** read in the firmware, **[inferred]** not traced or tested.

General facts found here now live on the shared pages: sensor mode ids, readout records and the crop table in
[sensor modes](../hardware/sensor-technical.md#sensor-modes-2026-11-21); encoder, size switch and playback limits in
[movie pipeline](movie-technical.md#how-a-movie-is-made-pipeline-facts-2026-11-21). This page keeps the open-gate reasoning.

**Verdict (2026-11-21): Uncertain, medium-big.** No hard blocker found. The sensor and the encoder can do it at
reduced resolution; the unknown is how many full-resolution pixels per second the image pipeline handles. Best first
target: a 2x2-binned full-area mode (2560 x 1920 at 30p or 1920 x 1440 at up to 60p). Full-resolution 4:3 (e.g.
2880 x 2160) probably only at about 15-24 fps. [inferred]

## Sensor readout

- The sensor driver has 16 mode records (104 bytes, 0x601b9428; copy at 0x601b9c50). Readouts: full 1:1 5248 x 3912
  (records 0, 12, 13), full-width 16:9 band 5248 x 2984 (4, 7, 8), 16:9 2x2 band 2624 x 1504 (5), **full 4:3 area 2x2
  2624 x 1960 (record 11)**, 3x3 and 4x4 live-view/high-speed modes. A binned full-area 4:3 readout already exists. [code] 2026-11-21
- Same records in OM-5 1.2 and E-M1 III 1.6. [code] 2026-11-21
- Sensor mode ids (type-7 request): HSSC 0, MSSC 1, LSSC 2, CLIP 3, HSHR 4, MSHR 5, **4K 6, C4K 7**, PD 8, MSPD 9, LSPD 10,
  **HQ 11**, FULL 12, FULL_LQ 13, STILL 14, MOVIE_HS 16, STILL_HS 17, MSHDR 18, HSMR 19 (enum printer 0x6015908e). [code] 2026-11-21
- Per-mode table 0x601de514 (76 B, index = id): **HQ = 2x2, 1976 lines = the full-area 4:3 readout**; 4K/C4K 1:1, 3044 lines
  (the 16:9 band); FULL/FULL_LQ/STILL 1:1, 3956 lines. [code]+[inferred] 2026-11-21
- AE request type to mode (chooser 0x60411219, table 0x60542874): 35 → HQ, 37 → 4K, 38 → C4K, 52 → FULL. Type 35 is sent
  only from 0x6044c385, called from the Wi-Fi remote code (0x61232f2f): HQ is in use today, likely the OI.Share remote
  live view. [code]+[inferred] 2026-11-21
- Frame-rate estimate from lines × line-time field (MSSC 120 fps and 4K 30 fps give the same rate): HQ up to ~80 fps,
  FULL up to ~23.5 fps. That matches C4K being 24p only. Not a measured limit. [inferred] 2026-11-21

## Image pipeline crop and scale

- Geometry table 0x604f1444 (24-byte entries, index = mode, getter 0x6036e377): **4K reads a 1:1 centre crop 4088 x 2348**
  (out 4080 x 2295, then to 3840 x 2160, about 1.27x crop); **C4K reads the full width 5208 x 2800** (out 5184 x 2734, scaled to
  4096 x 2160); FHD uses a 2x2 16:9 band 2640 x 1522 (out 2592 x 1458). No entry gives a 4:3 video output. [code]+[inferred] 2026-11-21
- The movie scaler is the fixed pipeline set from these tables (non-integer ratios already used). DSP job 10 is not in
  the movie path (caller is the still task). [code]+[inferred] 2026-11-21

## Encoder and playback

- H.264 only (Panasonic-style AVpi framework). **Rate-control level table tops at Level 5.1** (MaxMBPS 983040, jump at
  0x6117e4ba): at most 36864 macroblocks per frame. 2560 x 1920 30p, 1920 x 1440 60p, 2880 x 2160 30p fit; 3328 x 2496
  only to 30 fps. [code]+[inferred] 2026-11-21
- About 21 encoder branches test `height == 2160` (4K special cases), two test `>= 2160`; other heights take FHD
  branches. 2880 x 2160 would ride the 4K branches. [code] 2026-11-21
- The video-source size list (CAvpiVsoVideoSource, 0x6118ce61..0x6118d0ff) already has **2048 x 1536 and 2560 x 1920**
  besides 3840/4096 x 2160; unlisted sizes get a small default class. [code] 2026-11-21
- The playback decoder (CAvpiVdeCodec, 0x6116ac26) rejects width > 4096 or height > 2160, so taller clips wouldn't
  play in camera. [code] 2026-11-21

- Encoder size switch 0x603ecf4b (rec-init chain): resolution byte 5 → 4096 x 2160, 6 → 3840 x 2160, 2 → 1280 x 720,
  3 → 640 x 480, 4 → 640 x 360, else 1920 x 1080; max size 4096 x 2160 only for 5/6. One switch, but 4096/3840/1920 ×
  2160/1080 constants recur across many movie modules (ISP setup, YC buffers, display, metadata). [code] 2026-11-21

## Memory and throughput

- Movie YC pool 0x2f00 slots are 0xca8000 = 4096 x 2160 x 1.5: a 4:2:0 frame up to about 3424 x 2568 fits. [code] 2026-11-21
- Pipeline input today: 4K30 crop about 288 Mpx/s, C4K24 about 350 Mpx/s (C4K has no 30p). Full 1:1 4:3 needs 489 Mpx/s at
  24p; the 2x2 full-area mode needs 153 Mpx/s at 30p. The sensor reads full frames at 30 fps for bursts, so the limit
  is the pipeline/DRAM, not the sensor. Rolling shutter is 1.31x the 4K band. [inferred] 2026-11-21
- Electronic IS needs a crop margin (4K works at 4288 x 2416), so open gate means sensor-shift IS only. [inferred] 2026-11-21

## Other bodies

- OM-5 1.2 and E-M1 III 1.6 share every table above; OM-1 has a new engine and HEVC. None has open gate, anamorphic or
  4:3 movie strings: nothing to port. 10-bit would need a new encoder (OM-1 class), so it isn't part of this. [code]+[inferred] 2026-11-21

## Is the limit deliberate? (2026-11-21)

Probably not product segmentation: the E-M1 III (flagship, same processor) has the same 4K crop, C4K 24p-only and
Level 5.1 tables; only the OM-1's new processor goes further. 4K30 uses a 1:1 crop instead of full width, which only
makes sense if full-width 30p doesn't fit the budget. The limit could still be thermal or bandwidth headroom rather
than hard silicon, so a short-clip test might go further. [inferred] 2026-11-21

## Next

Still open: the ISP geometry entry for HQ and each movie size, and whether movie raw frames sit in DRAM (a Wi-Fi shell
peek while recording at each size would settle it without changing the firmware). The smallest experiment would
reuse the 720p setting with sensor mode HQ (request type 35), ISP output 1920 x 1440 and encoder code 2 →
1920 x 1440. [inferred] 2026-11-21

## On the E-M5 II and E-M5 (Mark I) (2026-11-21)

- Not checked in depth. Both older bodies use the same sensor-mode names, but their recording stack, encoder and sensor readout code are different code on a different chip (E-M5 II) or an older one (E-M5 Mark I), so none of this page's tables apply. [code]+[inferred]

Full comparison: [older bodies](../bodies/comparison-technical.md#older-bodies-e-m5-ii-and-e-m5-mark-i-2026-11-21).
