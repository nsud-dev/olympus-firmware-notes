# Open gate video: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Open gate video](open-gate.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

Could the E-M5 III record video from the whole 4:3 sensor area instead of the 16:9 band? This is read-only research.
Nothing was built or run.

General facts found here now live on the shared pages. Sensor mode ids, readout records and the crop table are in
[sensor modes](../hardware/sensor-technical.md#sensor-modes). The encoder, size switch and playback limits are in
[movie pipeline](movie-technical.md#movie-pipeline). This page keeps the open-gate reasoning.

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred.

## Verdict

**Uncertain, medium-big.** No hard blocker was found. The sensor and the encoder can do it at reduced resolution. The
unknown is how many full-resolution pixels per second the image pipeline handles.[^inf1]

- **Best first target.** A 2 × 2-binned full-area mode, giving 2560 × 1920 at 30p or 1920 × 1440 at up to 60p.[^inf1]
- **Full resolution.** Full-resolution 4:3 (for example 2880 × 2160) probably works only at about 15-24 fps.[^inf1]

## Sensor readout

The sensor driver has 16 mode records of 104 bytes each, with a copy.[^fw1]

| readout | size | records |
|---|---|---|
| full 1:1 | 5248 × 3912 | 0, 12, 13 |
| full-width 16:9 band | 5248 × 2984 | 4, 7, 8 |
| 16:9 2 × 2 band | 2624 × 1504 | 5 |
| **full 4:3 area 2 × 2** | **2624 × 1960** | **11** |
| 3 × 3 and 4 × 4 | live-view and high-speed modes | |

*Sensor driver readout records. Read in the firmware.*

- A binned full-area 4:3 readout already exists.[^fw1]
- The OM-5 1.2 and E-M1 III 1.6 have the same records.[^fw1]
- **Sensor mode ids** (type-7 request): HSSC 0, MSSC 1, LSSC 2, CLIP 3, HSHR 4, MSHR 5, **4K 6, C4K 7**, PD 8, MSPD 9,
  LSPD 10, **HQ 11**, FULL 12, FULL_LQ 13, STILL 14, MOVIE_HS 16, STILL_HS 17, MSHDR 18, HSMR 19. They are printed by
  an enum printer.[^fw1]
- **Per-mode table.** It is 76 B, indexed by mode id.[^fw1][^inf1]
    - HQ is 2 × 2 with 1976 lines, the full-area 4:3 readout.
    - 4K and C4K are 1:1 with 3044 lines (the 16:9 band).
    - FULL, FULL_LQ and STILL are 1:1 with 3956 lines.

### Request types

A chooser and a table map the exposure (AE) request type to a mode. 35 → HQ, 37 → 4K, 38 → C4K, 52 → FULL.[^fw1]

Type 35 is sent from only one place, called from the Wi-Fi remote code. So HQ is in use today, likely for the OI.Share
remote live view.[^fw1][^inf1]

### Frame rate

The frame-rate estimate comes from lines × the line-time field. MSSC at 120 fps and 4K at 30 fps give the same
rate.[^inf1]

- HQ reaches up to about 80 fps.[^inf1]
- FULL reaches up to about 23.5 fps. That matches C4K being 24p only.[^inf1]
- This is not a measured limit.[^inf1]

## Image pipeline crop and scale

The geometry table has 24-byte entries, indexed by mode, with a getter. No entry gives a 4:3 video output.[^fw1][^inf1]

| mode | reads | output | final |
|---|---|---|---|
| 4K | 1:1 centre crop 4088 × 2348 | 4080 × 2295 | 3840 × 2160 (about 1.27x crop) |
| C4K | full width 5208 × 2800 | 5184 × 2734 | 4096 × 2160 |
| FHD | 2 × 2 16:9 band 2640 × 1522 | 2592 × 1458 | |

*Pipeline geometry per movie mode. Read in the firmware.*

The movie scaler is the fixed pipeline set from these tables, and it already uses non-integer ratios. Image-engine job
10 is not in the movie path, because its caller is the still task.[^fw1][^inf1]

## Encoder and playback

- **Codec.** H.264 only, in a Panasonic-style AVpi framework.[^fw1]
- **Level.** The rate-control level table tops at Level 5.1 (MaxMBPS 983040). That allows at most 36864 macroblocks per
  frame.[^fw1][^inf1]
    - 2560 × 1920 30p, 1920 × 1440 60p and 2880 × 2160 30p fit.
    - 3328 × 2496 fits only to 30 fps.
- **Height branches.** About 21 encoder branches test `height == 2160` (4K special cases). Two test `>= 2160`. Other
  heights take FHD branches. 2880 × 2160 would ride the 4K branches.[^fw1]
- **Video-source sizes.** The video-source size list (`CAvpiVsoVideoSource`) already has 2048 × 1536 and
  2560 × 1920, besides 3840 and 4096 × 2160. Unlisted sizes get a small default class.[^fw1]
- **Playback.** The playback decoder (`CAvpiVdeCodec`) rejects width > 4096 or height > 2160. So taller clips wouldn't
  play in camera.[^fw1]
- **Size switch.** The encoder size switch sits in the rec-init chain. Resolution byte 5 → 4096 × 2160, 6 → 3840 × 2160,
  2 → 1280 × 720, 3 → 640 × 480, 4 → 640 × 360, else 1920 × 1080. The max size is 4096 × 2160 only for 5 and 6.[^fw1]
- **Size constants.** There is one switch, but the width constants 4096, 3840 and 1920 and the height constants 2160 and 1080 recur across many
  movie modules (ISP setup, YC buffers, display, metadata).[^fw1]

## Memory and throughput

- **YC pool.** Movie YC pool slots are `0xca8000` bytes, which is 4096 × 2160 × 1.5. A 4:2:0 frame up to about
  3424 × 2568 fits.[^fw1]
- **Pipeline input today.** The 4K30 crop needs about 288 Mpx/s and C4K24 about 350 Mpx/s. C4K has no 30p.[^inf1]
- **Open gate needs.** Full 1:1 4:3 needs 489 Mpx/s at 24p. The 2 × 2 full-area mode needs 153 Mpx/s at 30p.[^inf1]
- **Where the limit is.** The sensor reads full frames at 30 fps for bursts. So the limit is the pipeline or DRAM, not
  the sensor.[^inf1]
- **Rolling shutter.** It is 1.31x that of the 4K band.[^inf1]
- **Stabilisation.** Electronic IS needs a crop margin (4K works at 4288 × 2416). So open gate means sensor-shift IS
  only.[^inf1]

## Other bodies

The OM-5 1.2 and E-M1 III 1.6 share every table above. The OM-1 has a new engine and HEVC. None has open gate,
anamorphic or 4:3 movie strings, so there is nothing to port. 10-bit would need a new encoder (OM-1 class), so it isn't
part of this.[^fw1][^inf1]

## Hardware limit or product limit

The limit is probably not product segmentation.[^inf1]

- The E-M1 III (flagship, same processor) has the same 4K crop, the same 24p-only C4K and the same Level 5.1 tables.
  Only the OM-1's new processor goes further.[^inf1]
- 4K30 uses a 1:1 crop instead of the full width. That only makes sense if full-width 30p doesn't fit the
  budget.[^inf1]
- The limit could still be thermal or bandwidth headroom rather than hard silicon. So a short-clip test might go
  further.[^inf1]

## Older bodies

This was not checked in depth. Both older bodies use the same sensor-mode names. But their recording stack, encoder
and sensor readout code are different code on a different chip (E-M5 II) or an older one (E-M5 Mark I). So none of
this page's tables apply.[^fw1][^inf1]

See also: [older bodies](../bodies/comparison-technical.md#older-bodies-e-m5-ii-and-e-m5-mark-i).

## Open questions

- The ISP geometry entry for HQ and each movie size.[^inf1]
- Whether movie raw frames sit in DRAM. A Wi-Fi shell peek while recording at each size would settle it without
  changing the firmware.[^inf1]
- The smallest experiment would reuse the 720p setting with sensor mode HQ (request type 35), ISP output 1920 × 1440
  and encoder code 2 → 1920 × 1440.[^inf1]

## Address reference

E-M5 III 1.7 block0 addresses (base `0x60021020`).

| item | address |
|---|---|
| sensor readout records (16 × 104 bytes) | `0x601b9428`, copy at `0x601b9c50` |
| sensor mode enum printer | `0x6015908e` |
| per-mode table (76 B, index = mode id) | `0x601de514` |
| AE request type to mode | chooser `0x60411219`, table `0x60542874` |
| only sender of request type 35 | `0x6044c385` |
| its caller in the Wi-Fi remote code | `0x61232f2f` |

*Sensor readout.*

| item | address |
|---|---|
| pipeline geometry table (24-byte entries) | `0x604f1444`, getter `0x6036e377` |
| encoder size switch | `0x603ecf4b` |
| encoder level table jump | `0x6117e4ba` |
| `CAvpiVsoVideoSource` size list | `0x6118ce61` to `0x6118d0ff` |
| `CAvpiVdeCodec` playback size check | `0x6116ac26` |
| movie YC pool | pool id `0x2f00` |

*Pipeline, encoder and memory.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware, 2026-11-21.
[^inf1]: Inferred, not traced or tested, 2026-11-21.

