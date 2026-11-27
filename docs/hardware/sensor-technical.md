# Sensor and calibration: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Sensor and calibration](sensor.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

This page describes the image sensor as the firmware sees it. It covers the sensor's size, how a raw frame is laid out
in memory, the factory calibration values stored for it, and how the firmware asks the sensor to switch modes, for
example for live view, half-press and still capture. The E-M5 III and OM-5 use the same sensor, which is one reason
OM-5 features port well.

A raw frame is the unprocessed sensor data, one value per pixel in a Bayer colour pattern, before the image engine
turns it into a picture.

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred.

## Size

- The sensor reads out 5240 × 3912 pixels and outputs 5184 × 3888. That is 20 MP, with on-sensor phase-detect AF
  pixels. The raw-size set-up uses widths 5240, 5248 and 5280.[^fw1]
- Tripod High Res produces 10368 × 7776 and 8160 × 6120. The OM-5 adds 10416 × 7824, the Handheld High Res (HHHR)
  planes.[^fw1]
- The E-M5 III and OM-5 share the same geometry constants and the same defect and PD-pixel maps. They have the same
  sensor.[^fw1]

## How a raw frame is stored in RAM (one main-pool slot)

- **Packed 12-bit Bayer.** Each 16-byte group holds 10 pixels plus 1 pad byte. The 10 pixels are 5 pairs of 3 bytes.
  Each pair is 24 bits little-endian, with px0 in the low 12 bits and px1 in the high 12.[^cam1][^inf1]
- **Slot size and stride.** A slot is `0x1f47600` bytes, which is 5240 × 3912 × 1.6 bytes. That gives a stride of
  8,384 bytes per row.[^cam1]
- **Levels.** Black level is about `0x100`. Job records give OB 1025, which is 256 << 2. Saturation is 4095.[^cam1]
- **Orientation.** The raw is flipped vertically compared with the picture. Row 300 is near the bottom of the
  picture.[^cam1]
- **Live-view frames** for job 12 are 1472 × 1456.[^fw1]
- **Black level and white balance.** The black level (OB) and white balance (WB) are filled in at the metadata step,
  not when the capture is prepared. WB R/B/Gr/Gb is about 140/564/128/128.[^cam1]

## Factory calibration (PRM_* entries)

Each camera stores calibration measured at the factory, under names starting `PRM_`.

- The E-M5 III has 173 entries. 172 are identical in offset and size in the OM-5. They include the defect maps
  (`PRM_CCD_FIRST_PIXELDEFECT_*`, PD pixel defects), black levels, dark shading and saturation.[^fw1]
- The OM-5 adds 5 entries, for the eye-sensor distance, a reference calibration gain and voltage, and adjust flags.
  `PRM_ADJ_AUDIO_CORRECT` grows from 21 to 31 bytes.[^fw1]

## Sensor mode requests

The firmware switches sensor modes by sending a "type-7" request. The request has an exposure block at +4, with Tv at
+6, Sv at +8 and Av at +10. It has a mode block at +12, with the mode at +0 and fps at +20.[^cam1][^fw1]

- Live view is mode 9, MSPD, at 120 fps.
- Half-press is mode 0, HSSC, at 60 fps.
- The shutter is mode 14, STILL.
- Kind `0x400` with fps 0 is the OM-5 Live ND long-frame request. The E-M5 III's sensor side already handles
  it.[^cam1][^fw1]

## Sensor modes

Every type-7 request names one of these mode ids. The names come from the firmware's own debug enum. Binning and lines
per frame come from the per-mode table, which has 76-byte entries indexed by id.[^fw2] The binning and lines columns
are read from the table values.[^inf2]

| id | name | binning | lines per frame | readout area | known user |
|---:|---|---|---:|---|---|
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

*Sensor modes by id. Names from the firmware's debug enum, binning and line counts from the per-mode table.*

### Lines and readout rate

Lines per frame are the readout lines plus overhead.[^inf2]

- 3956 = 3912 + 44 for the full area.
- 3044 = 2984 + 60 for the 16:9 band.
- 1976 = 1960 + 16 for the 2 × 2 full area.

The table has a second per-mode field, 20 for binned modes and 34 for 1:1 modes, that reads like a line time. Lines
times that field gives the same rate for MSSC at 120 fps and 4K at 30 fps. That puts the full 1:1 readout at about
23.5 fps and the 2 × 2 full area at about 80 fps. This is an estimate only.[^inf2]

### Which AE request picks which mode

A chooser function picks the mode through a jump table, indexed by the AE request u16 at +2.[^fw2]

| AE request | mode |
|---:|---:|
| 1 | 19 |
| 3 | 0 |
| 4 | 3 (with exposure) |
| 10 | 4 |
| 11 | 1 |
| 12 | 2 |
| 35 | 11 (HQ) |
| 36 | 13 |
| 37 | 6 (4K) |
| 38 | 7 (C4K) |
| 39 | 5 |
| 40 | 9 |
| 41 | 10 |
| 52 | 12 |

*AE request type and the sensor mode id it selects.[^fw2]*

Type 35 is built in only one place, which is called from the Wi-Fi remote code.[^fw2]

### Sensor driver readout records

The sensor driver keeps 104-byte readout records, with a second copy of the set.[^fw2]

| readout | size |
|---|---|
| full 1:1 | 5248 × 3912 (effective 5208 × 3912) |
| 16:9 band | 5248 × 2984 |
| 2 × 2 16:9 band | 2624 × 1504 |
| 2 × 2 full area | 2624 × 1960 |
| 3 × 3 | 1792 × 1306/1310 and 1792 × 786 |
| crop | 2048 × 1132 |
| 4 × 4 | 1344 × 978 |

*Readout sizes in the sensor driver's records.[^fw2]*

### Image pipeline crop per mode

The image pipeline has a crop table with 24-byte entries. Its index is held at byte +1630 of the pipeline
context.[^fw2] Which entry each movie size uses is inferred from the sizes.[^inf2]

| use | read | out |
|---|---|---|
| 4K | **1:1 centre crop 4088 × 2348** | 4080 × 2295, then 3840 × 2160, about a 1.27× crop |
| C4K | **full width 5208 × 2800** | 5184 × 2734, scaled to 4096 × 2160 |
| FHD | 2 × 2 band 2640 × 1522 | 2592 × 1458 |
| live view | 1456 × 1088 | 1440 × 1080 |
| Tripod High Res | 10400 × 7792 | |

*Crop and output size per use, from the pipeline crop table.[^fw2][^inf2]*

### Other bodies

The OM-5 1.2 and E-M1 III 1.6 have identical records and geometry.[^fw2]

See also: [Sensor control link](sensor-link-technical.md), [shooting sequencer](../firmware/shooting-sequencer.md),
[Live ND](../features/live-nd.md).

## Address reference

E-M5 III 1.7 block0 addresses (base `0x60021020`).

| item | address |
|---|---|
| raw-size set-up | `0x60318eed` |
| metadata step (OB and WB filled in) | `0x6040c7f5` |
| type-7 request send | `0x601fce30` |
| Live ND long-frame handling on the sensor side | `0x6014f934`, `0x60150322` |
| mode debug enum printer | `0x6015908e` |
| per-mode table (76-byte entries) | `0x601de514` |
| AE request mode chooser, jump table | `0x60411219`, `0x60542874` |
| type 35 builder, its Wi-Fi remote caller | `0x6044c385`, `0x61232f2f` |
| sensor driver readout records, second copy | `0x601b9428`, `0x601b9c50` |
| pipeline crop table, getter | `0x604f1444`, `0x6036e377` |

*Functions and tables used on this page.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware.
[^fw2]: Read in the firmware, 2026-11-21.
[^cam1]: Seen on our E-M5 III.
[^inf1]: Inferred. The packing is worked out from the slot size.
[^inf2]: Inferred, 2026-11-21.

