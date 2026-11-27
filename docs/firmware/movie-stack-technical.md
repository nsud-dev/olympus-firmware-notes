# Movie encoder stack: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Movie encoder stack](movie-stack.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

This page covers how the E-M5 III 1.7 records a movie. That is the tasks on each core, the record request, the H.264
and container settings, the bitrate table and the codec hardware. The OM-5 II 1.1 program is compared at the end.

Everything here was read in the firmware. Nothing was run on the camera.[^fw1] Addresses are E-M5 III 1.7 block0
addresses unless the OM-5 II is named. They are listed in the [address reference](#address-reference). Earlier movie
facts, such as the 29:59 limit, the Level 5.1 cap, the sensor modes and OM-Log400, are on
[Movie recording: technical notes](../features/movie-technical.md).

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: blue = read in the firmware, grey = inferred, amber = a
correction.

## Layers at a glance

| layer | core | parts | what |
|---|---|---|---|
| shooting side | CPU0 | `CapMov_MovieRecorderSLR.cpp`, `CmpMov_*` observers | start and stop, buffer-full and media-fail notices |
| movie recorder (MVR) | CPU2 | MVR_MAIN, MVR_MOVIE, MVR_IMG1/IMG2/IMG_POST, MVR_CALC, MVR_ENC, MVR_EXEC, AVM_IF_VIDEO | builds the record request and feeds YC 4:2:0 frames |
| record requests | CPU2 | REC_INIT (`0x1001`), START (`0x1002`), STOP (`0x1003`), FREE (`0x1004`) | 36-byte request (below) |
| AVM command task | CPU1 | AVM_COM, its dispatcher and hash table | record `0x1001` to `0x1004`, chapter `0x1007`, maker info `0x1008`, playback `0x2001` to `0x200e`, `0x5001` to `0x5003` |
| record init | CPU1 | `MovmidApi_cmd_rec_init` and two inner calls | fills `SAvScaInit` and `SAvScaEncAVParam` |
| parameter fillers | CPU1 | AV, video and audio fillers | all encoder and container settings |
| parameter dump | CPU1 | one dump function | prints every field by name (source of the offsets here) |
| file layer | CPU1 | AVM_FILE_MAIN, `[AVM_FM]` / `[AVM_FILE_IF]` strings | DCF names, 64-bit positions, file division |
| AV framework | CPU1 | AVMDL_THREAD00-20, `CAvfw*`, `CAvpi*` | encoder classes, MP4/MOV mux (`CAvpiM4m*`), file sink |
| H.264 drivers | CPU1 | `CAvpiVenH264Driver.cpp` (encode), `CAvpiVdeH264Driver.cpp` (decode) | both call the codec library |
| codec library | CPU1 | one code range, no strings | programs the codec block |

*Movie recording layers on the E-M5 III, read in the firmware.[^fw1] Addresses for each part are in the address reference.*

The task entries and cores come from [CPU1 and CPU2](../hardware/cpu1-cpu2-technical.md). MVR posts the request with
a send function that was not traced to the mailbox. So that MVR reaches AVM_COM by a cross-core message is
inferred.[^inf1]

## Codec hardware

### One block for encode and decode

The H.264 encoder and decoder drivers both call one low-level library. It is the only code that touches the codec
registers.[^fw1]

- `0x99400000`: control, +4, +8 and +0x100 to +0x164
- `0x99404000`: channel select in bits 13-14, start and reset bits, and +0x14, +0x1c, +0x214
- `0x99408000`

So `0x99400000` is the H.264 codec block, shared by recording and playback.[^fw1]

### Register layout

The block has three sub-blocks.[^fw1]

- `0x99404000` and `0x99408000` each take a channel number in bits 13-14. The write is read-modify-write with mask
  `0x9fff`, so there can be up to 4 channels.
- The library keeps a 256-byte context per channel (+76, +180, +184, +188 and +196 hold buffer pointers).
- The functions that use `0x99408000` are called only by the decoder driver.
- The functions that use `0x99404000` are called by the encoder driver. Two of them are called by both drivers.
- The shared start routine sets `0x99400000` +0 bit 0 and +4 bit 15.
- The library picks per-core tables by the core id at `0x8050`.

So `0x99404000` is most likely the encode side, `0x99408000` the decode side and `0x99400000` the common
control.[^inf1]

### Interrupts

The [interrupts page](../hardware/interrupts-timers-dma-technical.md) lists lines 138, 140, 141 and 143 on this block.
They are set up during the movie task start-up, so they are the codec's interrupts.[^fw1] Which line signals what is an
open question.

### Memory

| use | address |
|---|---|
| codec work memory, `ulWorkAddress` | `0xb8000000` |
| codec CPU work memory, `ulCpuWorkAddress` | `0xbb119000` |
| AV framework memory (`SAvScaMemInfo`) | `0xb0000000` + 128 MB |
| maker-note staging (100 KB max) | `0xbb100000` |

*Movie memory areas.[^fw1]*

These overlap the still pool's first block (`0xb0000000`).[^fw1] So the movie and still layouts take turns.[^inf1]

## Record request (0x6033e00a)

| off | meaning | values |
|---|---|---|
| +1 | recording type | 1 normal. 3 when the recorder passes a capture frame rate (high speed, inferred[^inf1]). 2 exists in the tables but is never set (see below) |
| +8 | capture frame rate (u16) | the source's capture rate, else the record rate |
| +10 | record frame rate (u16) | 24, 25, 30, 50, 60 |
| +12 | percent (u16) | bitrate × value / 100 when below 100. From movie settings record +8, forced to 100 for high speed |
| +16 | max recording time (ms) | 0 from the recorder, so the filler default applies |
| +21 | compression | low nibble 1 All-Intra, 2 Super Fine, 4 Fine, 8 Normal. High nibble `0x20` = ×3 initial complexity |
| +22 | **size code** | 5 C4K, 6 4K, 1 FHD, 2 HD (720p), 3 640 × 480, 4 640 × 360 |
| +25 | picture structure | 1 All-Intra, 3 IPB |
| +27 | timecode mode | 0 off, 1 or 2 |
| +28 | audio sample bits | |

*The 36-byte record request built by the request builder.[^fw1]*

### Senders

`MovmidApi_cmd_rec_init` has one caller, the AVM_COM REC_INIT case. The request builder is the only builder of REC_INIT
requests. It is called from two MVR handlers, both in one event table.[^fw1]

- The normal path passes the high-speed capture rate, the percent field and the audio format. The audio format is
  48 kHz 16-bit, or 96 kHz 24-bit when a settings flag is set.[^fw1]
- The second path passes the record rate as the capture rate, so its clips are type 3 at percent 100. Which mode uses
  it is an open question.[^fw1]

The builder always writes +2 = 1, and only 1 or 3 into +1 and +25. So recording type 2, picture structure 2 and the
"+2 == 6" branches in the fillers are unreachable on the E-M5 III. They come from code shared with other bodies.[^fw1]

The OM-5 II builder is the same apart from two mappings. Record rate 23 becomes 24, and compression code 8 also gives
Fine.[^fw1]

### Size code and time limit

+22 is the size code.[^fix1] The filler gives 7200000 ms only for 640 × 480 and 640 × 360. Every other size gets
1800000 ms.[^fw1]

## Container and stream settings (`SAvScaEncAVParam`)

- **Container.** QuickTime MOV, with major brand `qt  `, minor version `0x20110700` and compatible brand `qt  `. There
  are three bytes "jpn" at +60. The track header flags are 15 and the track language is "und".[^fw1]
- **Atoms.** The muxer's atom names are moov, mvhd, trak, tkhd, edts, elst, mdia, mdhd, hdlr, minf, vmhd, smhd, dinf,
  dref, stbl, stsd, stts, stss, stsc, stsz and stco. The timecode track class is `CAvpiM4mMp4TrakTmcd`.[^fw1]
- **Maker atom.** "OLYM" with "OLYMPUS DIGITAL CAMERA". Private maker data is limited to `0x19000` bytes.[^fw1]
- **Write settings.** Write unit 4 MB, stream buffer 72 MB, thread priority 10, header mode 5.[^fw1]
- **File-size limit.** `ulUpper`/`ulLower` = 0 / `0xffffffff`. Read as a 64-bit file-size limit that is 4 GiB - 1. That
  fits the E-M5 III's 4 GB file split. It was not traced into the muxer.[^inf1]
- **Time limit.** `ulMaxRecTime` (+68) is 1800000 ms, or 7200000 for sizes 3 and 4 (see the record request).[^fw1]
- **Timecode.** Frames per second (half for 50p/60p), with the drop-frame flag from request +27.[^fw1]

## H.264 settings (`SAvScaEncVideoParam`)

`SAvScaEncVideoParam` sits at AV param + 96.[^fw1]

| field | value |
|---|---|
| bitrate | bitrate table, row × 80 + rate × 16 + column × 4 (table below) |
| max bitrate | 250 Mbit/s for C4K, 200 Mbit/s for FHD All-Intra, 105 Mbit/s otherwise |
| entropy coding | CAVLC for C4K and FHD All-Intra, CABAC for everything else |
| picture structure | All-Intra (I only) or IPB |
| GOP (`ulIvopInterval`) | 12 at 24p/25p, 15 at 30p, 24 at 50p, 30 at 60p. Half a second |
| frame rates (× 100) | 24p is 2397 except C4K at 2400. Then 2500, 2997, 5000, 5994. Capture rates up to 47952 |
| slices | C4K 8 slices, else 1 |
| max frame size | width × height × 3/8 |
| colour | BT.709 primaries, transfer and matrix (BT.601 for the 640-wide sizes). Full-range flag set |
| quantiser matrices | adaptive, copied from flash into RAM |
| initial complexity | 256. 384 for 4K. 160 or 80 for 50p/60p IPB |
| sizes | see [movie recording](../features/movie-technical.md#movie-pipeline) |

*H.264 encoder settings set by the video filler.[^fw1]*

## Bitrate table (Mbit/s)

The columns are All-Intra / Super Fine / Fine / Normal. A blank cell is 0, a combination that is not offered.

| row | 60p | 50p | 30p | 25p | 24p |
|---|---|---|---|---|---|
| C4K 4096 × 2160 | | | | | F 235 |
| 4K 3840 × 2160 | | | F 100 | F 100 | F 100 |
| FHD 1920 × 1080 | 200 / 50 / 28 / 16 | same | same | same | same |
| HD 1280 × 720 | 100 / 24 / 12 / 8 | same | same | same | same |
| 640 wide | 12 / 12 / 8 / 6 | same | same | same | same |
| type 2 FHD and HD | | | 24 / 24 / 16 / 12 | same | same |
| high speed FHD | F 48 | F 48 | F 24 | F 24 | F 24 |
| high speed HD | F 24 | F 24 | F 12 | F 12 | F 12 |

*Video bitrates in the firmware's bitrate table, in Mbit/s. F marks a single fixed rate.[^fw1]*

These are video rates only. Which rows the E-M5 III menus actually offer (C4K, All-Intra, the 640-wide sizes) was not
checked here. The table carries them because the code is shared with other bodies.[^inf1]

## Audio (filler 0x603ed33a)

The audio is linear PCM in stereo. The sampling rate comes from the request (48 kHz, inferred[^inf1]). The bitrate is
bits × rate × 2. There are 45 buffers, and a 24-bit packing flag is set when 32-bit samples are asked for.[^fw1]

See also: [Audio: technical notes](../hardware/audio-technical.md#sample-rates-and-formats), for where the samples come
from (codec, serial audio port, 48 kHz / 96 kHz switch).

## Debug commands

The shell has these movie debug commands.[^fw1]

- `avm debug [MODE] [OPTIONS]`. Mode 0 shows errors only and 1 shows all. Option 5 (`AVM_DBG_AVSCA_API`) prints the
  full parameter dump.
- `avm history`, the per-CPU command history.
- `mvr dbgall`, `move dbgall` and `movp dbgall`.

A live check over the [Wi-Fi shell](../features/wifi-debug-shell-technical.md) needs no build. `mcon` is not a movie
module.[^fix1] It is the mode-conflict and user-setting tool (`mcon show modeinfo`, `mcon usersetting ...`).[^fw1]

## OM-5 II 1.1 compared

| item | E-M5 III 1.7 | OM-5 II 1.1 |
|---|---|---|
| layers, tasks, codec registers | as above | same. The codec library is relocated, otherwise identical |
| bitrate table | as above | identical except the 640-wide row: 25 / 6 / 3 / 2 |
| max recording time | 30 min (2 h for 640-wide sizes) | 2 h always |
| `ulUpper` (file-size high word) | 0 | 511 (about 2 TiB, inferred meaning[^inf1]) |
| 23.98p | 24 maps to 23.976 | separate record rate code 2398 |
| percent bitrate scaling | yes | removed |
| max frame size | uses 1080 / 360 lines | uses 1088 / 368 lines |
| maker atom | OLYM, OLYMPUS DIGITAL CAMERA | OMDS, OM SYSTEM CAMERA |
| extra code | none | movie RAW debug (`mvr r_raw`, MovieRaw FIFO tables), `IMGBUFF_ALOC_STREAMING_MOV_YC422`, `Movie_Quality_Manage::getBitrate`, `check_highspeed_movie` |

*Movie stack differences between the two programs.[^fw1] OM-5 II addresses are in the address reference.*

The codec choice, profile limits, GOP, CABAC rules and bitrates for 4K, C4K, FHD and HD are the same.[^fw1]

## Open questions

- Which mode uses the second request path.
- What the movie settings record +8, the source of the percent field, is in the menus.
- The codec block's register meanings beyond the channel select, and which interrupt line signals what.
- A live parameter dump with `avm debug 1 5` while recording, to confirm the tables on the camera.

## Address reference

E-M5 III 1.7 addresses unless a body is named. Functions are block0 addresses (base `0x60021020`).

### Layers and tasks

| item | address |
|---|---|
| `CapMov_MovieRecorderSLR.cpp` | `0x608ec8a0` |
| MVR_MAIN | `0x6034804e` |
| MVR_IMG1/IMG2/IMG_POST | `0x60346021` |
| MVR_ENC | `0x60344f67` |
| AVM_IF_VIDEO | `0x603f4664` |
| REC_INIT / START / STOP / FREE request functions | `0x6033e00a` / `0x6033e13b` / `0x6033e15e` / `0x6033e177` |
| MVR request send function | `0x60320515` |
| AVM_COM / dispatcher / hash table | `0x603ef79e` / `0x603ef7d5` / `0x6053c640` |
| `MovmidApi_cmd_rec_init` → inner calls | `0x603eb4a1` → `0x603ecb57` → `0x603ecc0f` |
| AV / video / audio filler | `0x603ecd04` / `0x603ece43` / `0x603ed33a` |
| parameter dump | `0x603eef61` |
| AVM_FILE_MAIN | `0x603f1fa5` |
| `[AVM_FM]` / `[AVM_FILE_IF]` strings | `0x6053cc60` to `0x6053d7b4` |
| AVMDL_THREAD00-20 | `0x6112572f` |
| `CAvfw*`, `CAvpi*` code | `0x6112..` to `0x6118b7c8` |
| `CAvpiVenH264Driver.cpp` / `CAvpiVdeH264Driver.cpp` | `0x61172aa9` / `0x6116c3ac` |
| codec library | `0x6118b800` to `0x6118e200` |

*Movie layers and tasks.[^fw1]*

### Codec block

| item | address |
|---|---|
| codec common control | `0x99400000` (control, +4, +8, +0x100 to +0x164) |
| encode side (likely) | `0x99404000` (+0x14, +0x1c, +0x214) |
| decode side (likely) | `0x99408000` |
| decoder-only functions | `0x6118de91` to `0x6118dfd9` |
| functions called by both drivers | `0x6118da21` (shared start routine), `0x6118da71` |
| per-channel context | `0x61ec7300` + channel × 256 |
| core id | `0x8050` |
| codec interrupt set-up | `0x603eb1ae` |
| AV framework memory set-up (`SAvScaMemInfo`) | `0x603ecb9d` |

*Codec block, library and memory set-up.[^fw1]*

### Request, settings and tables

| item | address |
|---|---|
| MVR event table | `0x604ec734` |
| normal request path (called from) | `0x603358f7` (`0x60350ddf`) |
| second request path (called from) | `0x6032b4a8` (`0x60350631`) |
| percent source (movie settings record +8) | `0x60339922` |
| MOV track language | `0x603ed3a2` |
| muxer atom names | `0x6053d8d9` |
| maker string "OLYMPUS DIGITAL CAMERA" | `0x6053b27f` |
| bitrate table | `0x6053da84` |
| quantiser matrices, flash / RAM | `0x6053a7b0`.. / `0x625303e2`.. |

*Record request senders, settings and tables.[^fw1]*

| item | E-M5 III | OM-5 II |
|---|---|---|
| request builder | `0x6033e00a` | `0x60352a60` |
| AV / video fillers | `0x603ecd04` / `0x603ece43` | `0x60407efd` / `0x6040802b` |
| max recording time setting | | `0x60407f99` |
| bitrate table | `0x6053da84` | `0x6057ca00` |
| codec library | `0x6118b800` | `0x613ac221` |

*Addresses in both programs.[^fw1]*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware, 2026-11-25. E-M5 III 1.7 block0, compared with OM-5 II 1.1. No camera runs.
[^inf1]: Inferred, not traced to the end, 2026-11-25.
[^fix1]: Corrected on 2026-11-25. The older reading is in [History](#history).

## History

- 2026-11-07: notes called request +22 the recording "kind" and said which kind gets two hours was open. It is the
  size code, and only the two 640-wide sizes get two hours. Corrected 2026-11-25.
- Earlier pages put the bitrate rows at `0x6053a584`. The table is at `0x6053da84`. Corrected 2026-11-25.
- `mcon` was taken for a movie module. It is the mode-conflict and user-setting tool. Corrected 2026-11-25.
- 2026-11-25: what recording type 2 and request +2 == 6 are for was an open question. They are unreachable on the
  E-M5 III and OM-5 II.
- 2026-11-25: where request +12 (percent) comes from was an open question. It comes from movie settings record +8.

