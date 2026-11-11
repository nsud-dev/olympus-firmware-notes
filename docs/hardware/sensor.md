# Sensor, raw format and calibration

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
  row**. [camera] (E3c; the packing is inferred from the size)
- Black level ≈ 0x100 (OB 1025 in job records = 256<<2). Saturation is 4095. [camera]
- The raw is flipped vertically compared with the picture (row 300 ≈ bottom of the picture). [camera] (E6b)
- Live-view frames for job 12 are 1472 × 1456. [code]
- Black level (OB) and white balance (WB) are filled in at the metadata step (0x6040c7f5), not when the capture is
  prepared: WB R/B/Gr/Gb ≈ 140/564/128/128. [camera] (M3E0)

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

Details: [shooting sequencer](../firmware/shooting-sequencer.md), [Live ND](../features/live-nd.md).
