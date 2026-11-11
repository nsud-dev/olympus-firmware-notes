# Sensor, raw format and calibration

## Geometry
- Readout **5240 × 3912**, output 5184 × 3888 (20 MP, on-sensor PDAF). Raw-dim setup 0x60318eed uses widths
  5240/5248/5280. [code]
- Tripod High Res: 10368 × 7776 and 8160 × 6120. OM-5 adds **10416 × 7824** (HHHR planes). [code]
- Same geometry constants and same defect / PD-pixel maps in E-M5 III and OM-5 (same sensor). [code]

## Raw frame format in RAM (main pool slot)
- Packed **12-bit Bayer**: 16-byte groups of 10 pixels (5 × 3-byte pairs, LE 24 bits: px0 = low 12, px1 = high 12)
  + 1 pad byte. Slot 0x1f47600 = 5240 × 3912 × 1.6 B, **stride 8384 B/row**. [camera] (E3c; packing inferred from size)
- Black ≈ 0x100 (OB 1025 in job records = 256<<2). Saturation 4095. [camera]
- Raw is flipped vertically vs the picture (row 300 ≈ picture bottom). [camera] (E6b)
- Live-view frames for job 12: 1472 × 1456. [code]
- OB/WB are filled at the metadata step (0x6040c7f5), not at capture prep: WB R/B/Gr/Gb ≈ 140/564/128/128. [camera] (M3E0)

## Factory calibration (PRM_*)
- 173 entries on E-M5 III; 172 identical (offset/size) in OM-5, including defect maps
  (`PRM_CCD_FIRST_PIXELDEFECT_*`, PD pixel defects), OB levels, dark shading, saturation. [code]
- OM-5 adds 5 (eye-sensor distance, reference calibration gain/voltage, adjust flags); `PRM_ADJ_AUDIO_CORRECT` grows
  21 → 31 bytes. [code]

## Sensor mode requests
Type-7 requests via 0x601fce30: +4 exposure block (Tv +6, Sv +8, Av +10), +12 mode block (mode +0, fps +20).
Live view = mode 9 MSPD 120 fps; half-press = mode 0 HSSC 60 fps; shutter = mode 14 STILL. Kind 0x400 + fps 0 =
OM-5 Live ND long-frame request; E-M5 sensor side already handles it (0x6014f934, 0x60150322). [camera]+[code]
Details: [shooting sequencer](../firmware/shooting-sequencer.md), Live ND.
