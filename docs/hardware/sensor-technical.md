# Sensor and calibration: technical notes

> **Technical notes.** This page is the dense reference. For a readable introduction, start with [Sensor and calibration](sensor.md).

This page describes the image sensor as the firmware sees it: its size, how a raw frame is laid out in memory, the
factory calibration values stored for it, and how the firmware asks the sensor to switch modes (live view, half-press,
still capture). The E-M5 III and OM-5 use the same sensor, which is one reason OM-5 features port well.

A **raw frame** is the unprocessed sensor data, one value per pixel in a Bayer colour pattern, before the image engine
turns it into a picture.

Tags: **[code]** read in the firmware, **[camera]** seen on a real E-M5 III, **[inferred]** not traced or tested.

## Size

- The sensor reads out **5240 × 3912** pixels and outputs 5184 × 3888 (20 MP, with on-sensor phase-detect AF pixels).
  The raw-size setup 0x60318eed uses widths 5240/5248/5280. [code]
- Tripod High Res produces 10368 × 7776 and 8160 × 6120. The OM-5 adds **10416 × 7824** (the HHHR planes). [code]
- The E-M5 III and OM-5 share the same geometry constants and the same defect and PD-pixel maps (same sensor). [code]

## How a raw frame is stored in RAM (one main-pool slot)

- **Packed 12-bit Bayer:** 16-byte groups of 10 pixels (5 × 3-byte pairs, 24 bits little-endian: px0 = low 12 bits,
  px1 = high 12) plus 1 pad byte. A slot of 0x1f47600 bytes = 5240 × 3912 × 1.6 bytes, a **stride of 8384 bytes per
  row**. [camera] (the packing is inferred from the size)
- Black level ≈ 0x100 (OB 1025 in job records = 256<<2). Saturation is 4095. [camera]
- The raw is flipped vertically compared with the picture (row 300 ≈ bottom of the picture). [camera]
- Live-view frames for job 12 are 1472 × 1456. [code]
- Black level (OB) and white balance (WB) are filled in at the metadata step (0x6040c7f5), not when the capture is
  prepared: WB R/B/Gr/Gb ≈ 140/564/128/128. [camera]

## Factory calibration (PRM_* entries)

Each camera stores calibration measured at the factory, under names starting `PRM_`.

- The E-M5 III has 173 entries. 172 are identical (offset and size) in the OM-5, including the defect maps
  (`PRM_CCD_FIRST_PIXELDEFECT_*`, PD pixel defects), black levels, dark shading and saturation. [code]
- The OM-5 adds 5 (eye-sensor distance, reference calibration gain/voltage, adjust flags), and `PRM_ADJ_AUDIO_CORRECT`
  grows from 21 to 31 bytes. [code]

## Sensor mode requests

The firmware switches sensor modes by sending a "type-7" request through 0x601fce30. The request has an exposure block
at +4 (Tv +6, Sv +8, Av +10) and a mode block at +12 (mode +0, fps +20). [camera]+[code]

- Live view = mode 9 MSPD, 120 fps.
- Half-press = mode 0 HSSC, 60 fps.
- Shutter = mode 14 STILL.
- Kind 0x400 with fps 0 is the OM-5 Live ND long-frame request; the E-M5's sensor side already handles it (0x6014f934,
  0x60150322). [camera]+[code]

## Sensor modes (2026-11-21)

Every type-7 request names one of these mode ids. The names come from the firmware's own debug enum (printer
0x6015908e); binning and lines per frame come from the per-mode table 0x601de514 (76-byte entries, index = id).
[code], with the binning and lines columns read from the table values [inferred].

| id | name | binning | lines per frame | readout area | known user |
|---|---|---|---|---|---|
| 0 | HSSC | 3/3 | 1318 | full area | half-press (60 fps) |
| 1 | MSSC | 3/3 | 1318 | full area | 120 fps |
| 2 | LSSC | 3/5 | 790 | full area, short | 240 fps |
| 3 | CLIP | 1/1 | 2352 | crop | |
| 4 | HSHR | 2/2 | 1522 | 16:9 band | FHD movie (inferred) |
| 5 | MSHR | 2/2 | 1166 | 16:9 crop | |
| 6 | MOVIE_4K | 1/1 | 3044 | 16:9 band, full width | 4K movie |
| 7 | MOVIE_C4K | 1/1 | 3044 | 16:9 band, full width | C4K movie |
| 8 | PD | 1/1 | 1456 | | phase-detect |
| 9 | MSPD | 3/3 | 1318 | full area | live view (120 fps) |
| 10 | LSPD | 3/5 | 790 | full area, short | |
| 11 | MOVIE_HQ | 2/2 | 1976 | **full 4:3 area** | Wi-Fi remote path (likely OI.Share live view) |
| 12 | FULL | 1/1 | 3956 | full 4:3 area | |
| 13 | FULL_LQ | 1/1 | 3956 | full 4:3 area | |
| 14 | STILL | 1/1 | 3956 | full 4:3 area | shutter |
| 16-19 | MOVIE_HS, STILL_HS, MSHDR, HSMR | | | | |

- Lines per frame = readout lines plus overhead: 3956 = 3912 + 44 (full), 3044 = 2984 + 60 (16:9 band), 1976 = 1960 + 16
  (2x2 full area). The table has a second per-mode field, 20 for binned modes and 34 for 1:1 modes, that reads like a line
  time: lines x that field gives the same rate for MSSC at 120 fps and 4K at 30 fps, which puts the full 1:1 readout at
  about 23.5 fps and the 2x2 full area at about 80 fps. Estimate only. [inferred] 2026-11-21
- **Which AE request picks which mode:** chooser 0x60411219, jump table 0x60542874, indexed by the AE request u16 at +2:
  1 → 19, 3 → 0, 4 → 3 (with exposure), 10 → 4, 11 → 1, 12 → 2, 35 → 11 (HQ), 36 → 13, 37 → 6 (4K), 38 → 7 (C4K), 39 → 5,
  40 → 9, 41 → 10, 52 → 12. Type 35 is built only at 0x6044c385, called from the Wi-Fi remote code (0x61232f2f). [code] 2026-11-21
- **Sensor driver readout records** (104 bytes, 0x601b9428, second copy 0x601b9c50): full 1:1 5248 x 3912 (eff. 5208 x 3912),
  16:9 band 5248 x 2984, 2x2 16:9 band 2624 x 1504, 2x2 full area 2624 x 1960, 3x3 1792 x 1306/1310 and 1792 x 786,
  crop 2048 x 1132, 4x4 1344 x 978. [code] 2026-11-21
- **Image pipeline crop per mode** (table 0x604f1444, 24-byte entries, getter 0x6036e377, index held at byte +1630 of the
  pipeline context): 4K reads a **1:1 centre crop 4088 x 2348** (out 4080 x 2295, then 3840 x 2160, about 1.27x crop);
  C4K reads the **full width 5208 x 2800** (out 5184 x 2734, scaled to 4096 x 2160); FHD a 2x2 band 2640 x 1522 (out 2592 x
  1458); live view 1456 x 1088 (out 1440 x 1080); Tripod High Res 10400 x 7792. Which entry each movie size uses is
  inferred from the sizes. [code]+[inferred] 2026-11-21
- OM-5 1.2 and E-M1 III 1.6 have identical records and geometry.
  [code] 2026-11-21

Details: [shooting sequencer](../firmware/shooting-sequencer.md), [Live ND](../features/live-nd.md).
