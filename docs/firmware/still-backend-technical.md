# Still image back end: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Still image back end](still-backend.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

This page covers what happens to a still photo after the exposure. That is development, JPEG and raw encoding, the
Exchangeable image file format (EXIF) header with Olympus's MakerNote, the Design rule for Camera File system (DCF) and
FAT file layers, and the SD host. Raw files are Olympus raw format (ORF). The EXIF header is a set of image file
directories (IFDs).

Everything here was read in the E-M5 III 1.7 firmware and compared with the OM-5 II 1.1. Nothing was run on the
camera.[^fw1] Addresses are E-M5 III 1.7 block0 addresses unless the OM-5 II 1.1 is named. They are listed in the
[address reference](#address-reference).

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: blue = read in the firmware, grey = inferred, amber = a
correction.

## Summary

- **The still record pipeline runs on CPU0.** REC_MAIN, REC_IMAGE, REC_FILE, REC_PREPRO, REC_VIEW and six more record
  tasks are CPU0 tasks.[^fw1] CPU2 has three helpers. REC_MAIN_CPU2 does white balance and work info. REC_PRE_V1_CPU2
  does pixel patch and pool data for the preview. REC_VIEW_CPU2 does the rec view.[^fw1] The roles come from the trace
  names.[^inf1]
- **Named functions.** The record layer logs through a trace table of 209 names (`rec_jpeg_make_header`,
  `rec_raw_cic_start`, `rec_media_write_start`, ...). Each log call passes its id, so every name maps to a
  function.[^fw1]
- **JPEG** comes out of the image-processing request engine as one destination of a develop request. The thumbnail,
  the screen-size preview and the rec-view image are other destinations of the same request. The encoder is the
  **JPEG codec block** (interrupt line 146). It uses the standard JPEG tables, scaled by a quality factor.[^fw1]
- **Raw (ORF)** is compressed by a separate hardware block, **CIC**, from a 5240 × 3912 12-bit frame.[^fw1]
- **One header writer** builds the TIFF header and every IFD for JPEG, TIFF and ORF from static tag tables. The layout
  is fixed per file type. The MakerNote has five sub-IFDs (Equipment, CameraSettings, RawDevelopment,
  ImageProcessing, FocusInfo). The Exif version is 0231.[^fw1]
- **Files.** A DCF layer (`dcf*.c`), a FAT layer with FAT12, FAT16, FAT32 and exFAT (`dosfat.c`, `dosfile.c`,
  `dospath*.c`), a logical-sector layer (`logsec.c`) and the SD driver (`sd_*.c`, `sdmem.c`, `sdphy.c`). The folder is
  `100OLYMP`.[^fw1]
- **SD host.** Two ports share one register layout.[^fw1] Port 0 is the card slot and has UHS-II registers and a UHS-II
  PHY. Port 1 is the SDIO bus of the Wi-Fi chip.[^fw1][^inf1]
- **OM-5 II** keeps the same pipeline, header writer, CIC block and SD host. It writes Exif 0300, a 16-byte
  `OM SYSTEM` MakerNote header, a Rating tag, ambient-condition tags and more MakerNote tags. It uses the folder
  `100OMSYS`. Its EXIF parameter block is 3,788 bytes larger.[^fw1]

## Tasks and cores

| core | task | id | entry | pri | stack | role |
|---|---|---|---|---:|---|---|
| 0 | REC_MAIN | `0x20` | `0x603faf98` | 54 | `0x1000` | record main loop, buffer pool, messages |
| 0 | REC_IMAGE | `0x1f` | `0x60401db1` | 54 | `0x3700` | make the image (develop, JPEG, raw) |
| 0 | REC_FILE | `0x1e` | `0x604002a4` | 54 | `0x1000` | make the file, hand it to the media layer |
| 0 | REC_PREPRO | `0x21` | `0x6040c52a` | 55 | `0x1000` | pre-conditioning (WB, black level, pixel patch) |
| 0 | REC_PRE_I1 / REC_PRE_V1 | `0x4d` / `0x57` | `0x6040c65b` / `0x6040c5ea` | 55 / 46 | `0x1000` | pre-processing for image and view |
| 0 | REC_VIEW | `0x6e` | `0x6040f12c` | 26 | `0x2000` | rec view (review image) |
| 0 | REC_EXT | `0x77` | `0x603ff7ff` | 26 | `0x1800` | face data and extra pre-steps |
| 0 | REC_SOUND / REC_PROGRESS | `0x22` / `0x89` | `0x6040f73c` / `0x6040d7ff` | 55 | `0x600` | voice memo, progress |
| 0 | IMG_PRECON | `0x14` | `0x603f9f13` | 55 | `0x6e0` | image pre-conditioning |
| 0 | FILEFGND / FILECLBK / DCFPROC_SUB | `0x11` / `0x10` / `0x2` | `0x60631a2a` / `0x6062cbed` / `0x6061a2e0` | 55 / 55 / 66 | | file foreground, file callbacks, DCF background |
| 2 | REC_MAIN_CPU2 | `0x2012` | `0x603fe951` | 55 | `0x2000` | `rec_main_cpu2`, `rec_cpu2_wb`, `rec_cpu2_set_work_info` |
| 2 | REC_PRE_V1_CPU2 | `0x2013` | `0x6040d414` | 26 | `0x2000` | `rec_pre_v1_cpu2`, `precon_cpu2_pixpatch` |
| 2 | REC_VIEW_CPU2 | `0x2014` | `0x6040f5aa` | 25 | `0x2000` | `rec_view_cpu2_exec` |

*Still record tasks on the E-M5 III, read from the task tables.[^fw1] The roles are inferred from the trace names.[^inf1]*

REC_MAIN_CPU2 waits on its mailbox and runs `rec_cpu2_wb` for message `0x2008`.[^fw1] The OM-5 II has the same tasks
on the same cores.[^fw1]

See also: [CPU1 and CPU2: technical notes](../hardware/cpu1-cpu2-technical.md).

## Record trace table

- The table is made of 8-byte records `{u32 id, char *name}`. The ids run from 0 ("ERROR TRACE ID") to `0xd4`, which
  is 209 names.[^fw1]
- The logger takes d0 = `0x31000000` | kind and **d1 = id << 16 | line**. Reading the `mov N,d1` before each call maps
  the ids to functions. 149 of the 209 were found in the code range given in the address reference.[^fw1]
- The OM-5 II table holds 192 names, and the ids are renumbered. It drops the 3D/MPO, photo story (`rec_ps_*`) and
  recipe (`rec_recipe_*`) entries. It adds six `rec_ImgPro_Dst_Set_Image_Vw*` entries.[^fw1]

The [address reference](#address-reference) lists the main record functions for both bodies. A function's start is the
nearest call target before its first log site.[^fw1] Where a function is only jumped to, the start is inferred.[^inf1]

## One photo through the back end

1. **Develop.** REC_IMAGE builds the develop parameters (`rec_ImgPro_CreateParam`, `rec_ImgPro_ImageParam`). It
   submits them to the request engine, the same engine focus stacking uses.[^fw1]
2. **Destinations.** One request can fill several outputs.[^fw1] Their names are trace ids `0x6c` to `0x75`.
    - `Dst_Prim`, the main JPEG
    - `Dst_Thum`, the thumbnail
    - `Dst_Playpic`, the screen-size preview
    - `Dst_View` / `Dst_ViewJpeg`, the rec view
    - `Dst_Yc` and `Dst_Bayer`
    - `Dst_OrfPlaypic`, for raw
3. **JPEG.** `rec_ImgPro_Ycc2Jpeg` calls the request builder once per destination. It reads back each encoded size at
   +36 of the destination record. The main JPEG is placed after the thumbnail plus a header gap,
   `(size + 0xa43f) & ~0x3f`, about 41 KB.[^fw1] What the gap is for is inferred.[^inf1]
4. **Raw.** `rec_raw_make_image` runs the same develop for the embedded previews. Then `rec_raw_cic_start` starts the
   CIC block and `rec_raw_cic_wait_for_end` waits for it.[^fw1]
5. **Header.** `rec_jpeg_make_header` or `rec_raw_make_header` fills the EXIF parameter block and calls the header
   writer.[^fw1]
6. **File.** REC_FILE runs `rec_make_file` → `rec_file_record` → `rec_media_entry` (DCF number and free space) →
   `rec_media_write_start` → `rec_media_close` → `rec_media_leave`. The writes themselves run in the **FILECLBK** task
   (see [card writes](#card-writes)).[^fw1]

## JPEG

### Quality and compression setting

- A JPEG test path (`IMGPRO JPEG Test : Hw=%d Vw=%d`) loops over scale factors and prints `SF(HEX),Size(HEX)`. So
  quality is a quantisation scale factor, and file size is measured per factor.[^fw1] The purpose of the test is
  inferred.[^inf1]
- The user settings carry `JpegCompressionRate[0]` and `[1]`.[^fw1] The two slots are likely the two image-quality
  presets.[^inf1]

### Codec block

The JPEG codec block is the same block, with the same tables, on the OM-5 II.[^fw1]

The set-up function is called from the request engine. Argument 0 turns the codec off (+0x00 = `0x8004`). Any other
argument programs one job.[^fw1]

| offset | value |
|---|---|
| `0x99900008` | 1 = enable (0 = off). `0x99900000` = interrupt acknowledge (write 1) |
| +0x00 | mode `0x8008` or `0x8028`, then bit 0 = start |
| +0x0c | `0x8200` |
| +0x14 | 224 or 96 (from the destination record) |
| +0x28 / +0x2c | buffer address low / high half (record +32 plus 64), or 24 / 0 |
| +0x58 / +0x5c | MCU count minus 1, low / high half |
| +0x60 / +0x64 | width / height |
| +0x68 | 2 |
| +0x70 | sampling: 16 = 4:2:2 (MCU 16 × 8), 17 = 4:2:0 (MCU 16 × 16) |
| +0x78 | stride from the destination record |
| +0xa0 / +0xa4 | 256 / quality scale factor |
| +0xb8 / +0xbc | `0x1100` / 17 |
| +0x200-0x2c0 | Huffman code-length counts (DC luma, DC chroma, AC luma, AC chroma), 16 each |
| +0x300 / +0x340 | DC symbol values, 12 each |
| +0x400 / +0x800 | AC symbol values, 162 each |
| +0xc00 / +0xc80 | quantisation tables, luma / chroma, two entries per word |

*JPEG codec registers written by the set-up function. Offsets are from the codec block base.[^fw1]*

- **Sampling.** Destination type `0x702` selects 4:2:2 and `0x703` selects 4:2:0. The minimum coded unit (MCU) count
  follows the same split. The SOF0 segment of the header template (below) is 4:2:2 (luma `0x21`).[^fw1]
- **Tables.** All six tables are the standard ones from the JPEG specification (Annex K). They are the luma and chroma
  quantisation tables and the four standard Huffman tables. Quantisation is stored column-major.[^fw1]
- **Quality.** The loader scales each quantisation entry as `min(255, (q × SF + 128) >> 8)`. SF = 256 gives the
  standard tables. The loader caches the last SF in a variable with a flag, and reloads only when SF changes. So the
  JPEG test above measures file size against SF.[^fw1]
- **Done interrupt.** Line 146 (level 5) is registered on all three cores. Its handler reads and clears the cause at
  +0x08, acknowledges at `0x99900000` and dispatches. On completion it reads the encoded size as
  `+0x24 << 16 | +0x20` and passes it to the request callback. On an error it writes +0x00 = `0x8000`.[^fw1]

### Header segments

Software writes the marker segments. One function builds DQT, DHT (all four tables, length `0x1a2`), SOF0
(3 components, 4:2:2), SOS and DRI from a template.[^fw1]

### Other image units

The same interrupt set-up registers the request engine's other units on all three cores.[^fw1] What the units at
`0x9ca00000` to `0x9cf00000` do is an open question.

| line | unit |
|---:|---|
| 133 | `0x9cc00000` |
| 136 | `0x9cf00000` |
| 137 | `0x9cd00000` |
| 147 | `0x9ca00000` |
| 152 | `0x9cb00000` |
| 148-151 | the image pipe, `0x9f000000` / `0x9f80a000` |

*Interrupt lines of the request engine's other units.[^fw1]*

### MPO

One function writes an APP2 `MPF` segment (`FF E2`, `MPF\0`, `II*\0`, tags `0xb000` to `0xb002`) for 3D/MPO files. Its
callers are `rec_3d_make_mpo` and the DCF edit code.[^fw1]

## Raw (ORF) and the CIC block

### Driver and job record

- The driver (`CIC_MUTEX`) is called by `rec_raw_cic_start` and by `rec_raw_pixshiftsr_cic_start` (tripod high res).
  It enables a clock bit and programs the CIC block at offsets +0x08, +0x44, +0x84 to +0x94 and +0xc0 to
  +0xe4.[^fw1]
- `rec_raw_cic_start` sets the job record.[^fw1]
    - width **5240**, height **3912**, **12** bits
    - output buffer **32,798,208** bytes, which is 1.6 bytes per pixel, a worst case above 12 bits per pixel. The 1.6
      reading is inferred.[^inf1]
    - raw data starting **101,376** bytes after the header area
- The driver also fills 14 halfwords at record +18 to +44 before the start. They are 0, 5, 0, 2, 5, 4, 3, 2, 3, 4, 7,
  15, 12, 5.[^fw1] They look like entropy-coder parameters. Their meaning is an open question.[^fix1]
- The OM-5 II has the same driver and the same CIC block writes.[^fw1]

### Register map

The map comes from the programming function. The job record field is in brackets.[^fw1]

| offset | value |
|---|---|
| `0x9880014c` / `0x988001c8` | bit 9 = CIC clock on / off (the set and clear registers of one gate word) |
| +0x00 | 2 while programming, then 0. Stop writes 14 then 15 |
| +0x08 | `0x1fc` (interrupt enables, inferred[^inf1]) |
| +0x44 / +0x48 | 0 / 1 = start |
| +0x84 | input address [+0] |
| +0x88 | 32-byte words per line, in both halves [+12 width ÷ pixels per word] |
| +0x8c | output address [+4] |
| +0x94 | output size ÷ 32 [+8] |
| +0xc0 / +0xe4 | size-limit mode and limit in bytes [+17 bit 1, +8] |
| +0xc4 | bit-depth code [+16]: 16 → 11, 14 → 10, 12 → 7, 10 → 4, 9 → 1, other → 0 |
| +0xc8 | parameter 1 [+18] |
| +0xcc | parameters 2, 3 [+20, +22] |
| +0xd0 / +0xd4 | parameters 4, 5 / 6, 7, one byte each [+24-+30] |
| +0xd8 | parameters 8, 9, 10 [+32-+36] |
| +0xdc / +0xe0 | parameters 11, 12 / 13 [+38-+42] |
| +0x100 | parameter 14 [+44] |
| +0x104 / +0x108 | height << 16 \| width / height [+14, +12] |

*CIC registers. Offsets are from the CIC block base, except the two clock gate registers.[^fw1]*

### Input packing and parameters

- **Pixels per word.** The words-per-line divisor is 16, 18, 20, 24 or 32 pixels for 16, 14, 12, 10 or 8 bits.[^fw1]
  That is the number of packed pixels that fit in 32 bytes (20 for 12 bits). So the input is the packed sensor
  format.[^inf1]
- **Parameters.** The published ORF decoder (dcraw `olympus_load_raw`) uses a 12-bit escape code, a running average
  updated with a factor 3 and a shift 5, and 2- and 3-bit fields. The values 12, 3, 5 and 2 appear in the list. Which
  register holds which constant is inferred at best, and needs a raw file to test.[^inf1]

## Header writer

The header writer is `img_header_make` (our name). Its callers are `rec_jpeg_make_header`, `rec_raw_make_header`,
playback edits and the movie EXIF code (`move_if_exif.c`).[^fw1]

- **File type** is at param +24816. 0 = JPEG and 1 = TIFF write `II*\0`. 2 = ORF writes **`IIRO`**. Offset 8 points
  to IFD0.[^fw1] That type 1 is TIFF is inferred from the IFD contents. The E-M5 III menus have no TIFF
  option.[^inf1]
- **IFD writer.** It takes d0 = count, d1 = next flag, a1 = output, (4,sp) = descriptor table and (8,sp) = base. It is
  called 28 times. A descriptor is `{u16 tag, u16 type, u32 bytes, u32 offset into the EXIF parameter block}`.[^fw1]
- **Fixed layout.** Each branch first stores constant offsets for the IFD positions (JPEG: 218, 968, 758, 3168, ...).
  So the header has a fixed size per file type.[^fw1]
- **MakerNote header.** `OLYMPUS\0` + `II` + `03 00` (12 bytes) at the start of the MakerNote value.[^fw1]
- **Defaults.** Exif version `0231`, FlashPix `0100`, Interop `R98` / `0100`.[^fw1]

| IFD | JPEG | ORF | TIFF |
|---|---|---|---|
| IFD0 | 17 (Adobe RGB) or 14 | 23 (adds image size, StripOffsets etc.) | 24 or 23 |
| Exif | 38 (Adobe RGB, adds Gamma `0xa500`) or 37 | 34 | 31 or 30 |
| GPS | 1, 2, 3, 4, 8 or 10 tags, by which GPS fields are set | same | none |
| Interop | 2 | none | none |
| IFD1 (thumbnail) | 6 | none | none |
| MakerNote main | 7 (`0x0200`, `0x0209`, `0x2010` to `0x2050`) | 8 (adds `0x0100` preview) | 8 |
| Equipment `0x2010` | 25 | 25 | 25 |
| CameraSettings `0x2020` | 90 | 88 | 61 |
| RawDevelopment `0x2030` | 14 | 14 | 14 |
| ImageProcessing `0x2040` | 133 | 180 | 89 |
| FocusInfo `0x2050` | 97 | 97 | 69 |

*Tag count per IFD and file type on the E-M5 III.[^fw1]*

- Each file type has its own descriptor tables, so the same tag can come from a different parameter offset per
  type.[^fw1]
- The 17-tag IFD0 adds WhitePoint, PrimaryChromaticities and YCbCrCoefficients. It is chosen when param +24946 is
  1.[^fw1] So +24946 is the Adobe RGB colour-space flag.[^inf1]
- **Parser.** A parser, reached through a check of `II`, `RO` and the MakerNote tag `0x927c`, has 28 callers in
  playback, DCF copy and Wi-Fi (`get_exif.cgi`).[^fw1]
- **EXIF parameter block** ("EXIFPARAM"). It is about 25.6 KB. In the JPEG branch the MakerNote IFDs read from +3180
  onwards. The writer stores the finished sizes at +25652, +25656 and +25660. `exif_param_tag_test` in the file test
  shell reads tags from a file.[^fw1]

## Files and the DCF layer

### Layers

The module names come from source strings.[^fw1]

1. `filewrap.c`, in two parts
2. `fileif.c` (tasks FILEFGND, FILECLBK)
3. DCF: `dcfnum.c` numbering, `dcfsearch.c`, `dcfremain.c` free space, `dcfedit.c` copy, delete and lock, `dcfroot.c`,
   `dcfscan.c`, `dcfmntply.c`
4. FAT: `dosfat.c` (196 functions), `dosfile.c`, `dospath.c`, `dospath_lfn.c` (long names)
5. `logsec.c`, logical sectors, with a semaphore
6. SD: `sd_mount.c`, `sdmem.c`, `sdmem_format.c`, `sdphy.c`, `sd_asic.c`

### Operations and file systems

- **Operations.** The file log names every request.[^fw1]
    - `DCFNUM_*` (mount, record number, record node, format)
    - `FILE_*` (find, create, delete, lock)
    - `FAT_*` (mount, chain read and write, format, remount)
    - `DOSFSTRM_*` (stream open, write, seek)
    - `DOSMEM_*`, `DCFSEARCH_*`, `DCFREMAIN_*`
    - `LOG_*` (logical-sector mount, read, write, power save)
- **File systems.** The boot-sector types are `FAT12`, `FAT16`, `FAT32` and `EXFAT`, and the volume label is
  `NO NAME`. The exFAT checks cover the valid-data length and the accessed timestamp
  (`filedbg_correct_dir`).[^fw1]
- **Names.** The folder is `DCIM\100OLYMP`. Files have `P1010001.JPG`-style names (P, month, day, number). Folders run
  100-999 and files 0001-9999 (test strings `999/9999 OBJECT`, `DIRECTORY FULL`, `NON OLYMP FOLDER`). There are DPOF
  `AUTPRINT.MRK` writer strings.[^fw1]
- **Allocation units.** The FAT layer tracks the card's SD allocation units (`sd_AU`, `[AU] free?`) and `CMD20`
  (speed-class recording) support. It has a `file sctest` speed-class test.[^fw1] This is read from strings. How the
  allocation units steer allocation is an open question.

### Card writes

REC_FILE prepares the file and FILECLBK does the writes.[^fw1]

1. `rec_media_write_start`, in REC_FILE, posts message `0x54` to a mailbox with a pointer to the media record.
2. FILECLBK (CPU0 task `0x10`) waits on that mailbox. Its handler maps messages `0x50` to `0x58` to FAT commands
   through a table. `0x54` becomes command 4, `FAT_CHAIN_WRITE`.
3. FILECLBK calls `dosfat_exec`. It takes the media number from bits 12-15 and the command from bits 0-11 of record
   +4.
4. The `dosfat_exec` table sends `FAT_CHAIN_READ`, `FAT_CHAIN_WRITE` and `FAT_CHAIN_WRITE_EX` to one chain handler.

| command | name |
|---:|---|
| 0 | mount |
| 1 | unmount |
| 2 | update |
| 3 | chain read |
| 4 | chain write |
| 5 | format |
| 6 | chain write ex |
| 7 | remount |
| 8 | chain read 2 |

*FAT command names, from the firmware's name table.[^fw1]*

The same mailbox carries about 230 other senders' requests.[^fw1] So FILECLBK serialises all card access.[^inf1] The
OM-5 II has the same tasks.[^fw1]

### Write size, logs and shell

- **UHS-II write size.** One function turns a byte count into sectors. On a UHS-II card it rounds up to 2 KB and counts
  in 4-sector units. Otherwise it counts in 512-byte sectors. It is called from `rec_media_write_start` and the movie
  writer.[^fw1]
- **Logs.** There is a command log and a DCF edit log (`RECORD`, `DELETE`, `JPEG-DELETE`, `RAW-DELETE`). An
  `[EEROM ERR LOG]` stores the state at the time of an error.[^fw1]
    - the SD host registers (125 pairs)
    - `SDPHY_INFO` (speed, bus, power, clock mode)
    - the volume info
    - the card's CID, CSD, SCR and SD status
- **Shell.** The user shell's `file` command has mount, umount, format, ls, cat, rm, rawread (sector or cluster),
  memdump, memload, perf, sctest, dbginfo and test commands (dcfcopy, volinfo, filetest, fullwritetest). `file dbginfo`
  prints the SD register dump.[^fw1]

## SD host

- **Ports.** A base table gives port 0 at `0x99000000` and port 1 at `0x9a300000`.[^fw1] Port 1's command block
  `0x9a302000` is the `mmc@9a302000` SDIO host (glue `0x9a300000`). The ARM device trees of the OM-5 and OM-5 II list
  it for the Wi-Fi chip.[^fw1] So port 0 is the card slot.[^inf1]
- **Register map.** The names come from the firmware's own table. Offsets are from the port base.[^fw1]
    - +0x000 to +0x05c: DMA (`DMAMODE`, `DMATRG`, `DMA_START_ADR`, `DMACNT`, `DMASTATUS`),
      `IRQ02_STATUS`/`_MASK_CLR`, `SDCORE`, `PHY_INIT`.
    - +0x2000 to +0x21fc: SD core (`CMD`, `PORTSEL`, `ARG0/1`, `STOP`, `SECCNT`, `RSP10`-`RSP7`, `INFO1/2` and masks,
      `CLK_CTRL`, `SIZE`, `OPTION`, `ERR_STS1/2`, `IO_MODE`, `CC_EXT_MODE`, `SOFT_RST`, `VERSION`, card-detect and
      write-protect `EXT_*`).
    - +0x2200 to +0x22c0: UHS-II link (`UHS2_GEN_SETS`, `_PHY_SETS`, `_LT_SETS`, `UHS2_CM_CMD`/`_RES`/`_PLD0-3`,
      interrupts, `UHS2_DP0_*` data port, buffers, `UHS2_APW_*`).
    - +0x6000 to +0x6054: UHS-II PHY (`PHY_D0LANE0-2`, `PHY_PLL`, `PHY_D1LANE0-2`, `PHY_SGCNTR`, `PHY_SGSTAT`, ...).
- **UHS-II.** A port query called with (port, 2) answers 1 only for port 0. Another function reads the card's UHS-II
  flag, at byte +336 of a per-port record of 340 bytes. So UHS-II is a port-0 feature that turns on per card. The
  register dump adds the UHS-II PHY rows only when that flag is set.[^fw1]
- **Interrupts** are lines 125, 127 and 129.[^fw1] See also:
  [Interrupts, timers and DMA: technical notes](../hardware/interrupts-timers-dma-technical.md).
- **OM-5 II.** It has the same port bases and an identical register table.[^fw1]

## OM-5 II 1.1 compared

| item | E-M5 III 1.7 | OM-5 II 1.1 |
|---|---|---|
| record tasks | as above | same tasks, same cores |
| trace table | 209 names | 192 names. No MPO, photo story or recipe |
| Exif version | 0231 | 0300 |
| MakerNote header | `OLYMPUS\0` `II` `03 00` (12 bytes) | `OM SYSTEM\0\0\0` `II` `04 00` (16 bytes) |
| IFD0 (JPEG) | 17 / 14 | 18 / 15. Adds Rating `0x4746` |
| IFD0 (ORF) | 23 | 25. Adds XMP `0x02bc` and Rating |
| Exif IFD (JPEG / ORF) | 38 or 37 / 34 | 42 or 41 / 38. Adds `0x9400`, `0x9402` to `0x9404` (temperature, pressure, water depth, acceleration) |
| MakerNote Equipment / CameraSettings / ImageProcessing / FocusInfo (JPEG) | 25 / 90 / 133 / 97 | 26 / 96 / 141 / 102 |
| MakerNote CameraSettings / ImageProcessing / FocusInfo (ORF) | 88 / 180 / 97 | 94 / 189 / 102 |
| EXIF parameter block | file type +24816, colour flag +24946 | +28604, +28734 (3,788 bytes larger) |
| XMP | none | XMP packet in the defaults (`<?xpacket begin=`) |
| DCF folder | `100OLYMP` | `100OMSYS` |
| CIC raw block | `0x9b700000` | same |
| SD host | `0x99000000` / `0x9a300000` | same |

*Still back end differences between the two programs.[^fw1] Function addresses for both are in the address reference.*

## Open questions

- What each CIC parameter register means. One ORF file decoded with the published algorithm against the 14 values would
  settle it.
- What the request engine's units at `0x9ca00000` to `0x9cf00000` do.
- How SD allocation units steer allocation.
- The full EXIF parameter-block map. The tag source offsets are known, but the producers are not traced.
- A camera check costs nothing new. `file dbginfo` and `file volinfo` over the Wi-Fi shell would confirm the port and
  register reading.

## Address reference

E-M5 III 1.7 addresses unless a body is named. Functions are block0 addresses (base `0x60021020`).

### Record layer

| item | E-M5 III | OM-5 II |
|---|---|---|
| record trace table | `0x605406a0` | |
| trace logger | `0x603fec95` | `0x6041a029` |
| code range of the 149 mapped ids | `0x603f0000` to `0x60420000` | |
| REC_MAIN entry | `0x603faf98` | `0x60416901` |
| REC_IMAGE entry | `0x60401db1` | `0x6041e2e0` |
| REC_FILE entry | `0x604002a4` | `0x6041b6a8` |
| REC_MAIN_CPU2 entry | `0x603fe951` | `0x60419ce2` |
| REC_MAIN_CPU2 mailbox wait, queue id | `0x6040b8ee`, `0x600412d6` | |
| `rec_ImgPro_CreateParam` / `rec_ImgPro_ImageParam` | `0x604022c5` / `0x60402497` | |
| request engine (also used by focus stacking) | `0x60373013` | |
| request builder (per destination) | `0x60370dc3` | |
| `rec_media_entry` DCF number and free space calls | `0x6061b8ce`, `0x6061b923` | |

*Record tasks, trace table and develop calls.[^fw1]*

| function | E-M5 III | OM-5 II |
|---|---|---|
| `rec_make_image` | `0x604020fa` | `0x6041e4a7` |
| `rec_ImgPro_Bayer2Ycc` | `0x6040309f` | `0x6041f6e5` |
| `rec_ImgPro_Ycc2Jpeg` | `0x60403133` | `0x6041f779` |
| `rec_jpeg_exec` | `0x60408072` | `0x60424d06` |
| `rec_jpeg_make_image` | `0x60408216` | |
| `rec_jpeg_make_header` | `0x604082bd` | `0x60424f6f` |
| `rec_raw_exec` / `rec_raw_make_image` | `0x6040d8f4` / `0x6040d9ce` | |
| `rec_raw_cic_start` | `0x6040dd7f` | `0x6042b47a` |
| `rec_raw_make_header` | `0x6040dfc8` | `0x6042b6f2` |
| `rec_make_file` / `rec_file_record` | `0x6040032b` / `0x6040043b` | `0x6041b72f` / `0x6041b8a3` |
| `rec_media_entry` / `_write_start` / `_close` / `_leave` | `0x60408cf8` / `0x60408f87` / `0x604090c6` / `0x60409245` | `0x60425ab3` / `0x60425d42` / `0x60425e81` / `0x60426000` |

*Record functions named by the trace table.[^fw1] A start is inferred where the function is only jumped to.[^inf1]*

### JPEG and image units

| item | E-M5 III | OM-5 II |
|---|---|---|
| JPEG codec block | `0x99901000` | same |
| codec common registers: interrupt acknowledge / enable | `0x99900000` / `0x99900008` | |
| JPEG test path | `0x60373a68` | |
| codec set-up | `0x603d6409` | |
| set-up callers in the request engine | `0x60365188`, `0x6036538f` | |
| quantisation table loader | | `0x603edbb2` |
| done interrupt handler | `0x6036e7a7` | `0x603851d5` |
| standard JPEG tables | `0x60537918` to `0x60537b33` | |
| last SF cache / flag | `0xa265fd80` / `0xa265fd82` | |
| marker segment builder / template | `0x6031acee` / `0x604e2704` | |
| interrupt set-up for the image units | `0x6036e970`, called from `0x6035470a` | |
| MPO APP2 writer | `0x6031c04b` | |
| MPO callers: `rec_3d_make_mpo` / DCF edit | `0x603fc3c8` / `0x6063645a` | |

*JPEG codec and image units.[^fw1]*

### Raw and header writer

| item | E-M5 III | OM-5 II |
|---|---|---|
| CIC driver | `0x60c22aed` to `0x60c22dc1` | `0x60ccb2af` |
| CIC programming function | `0x60c22c3b` | |
| CIC block | `0x9b700000` | same |
| CIC clock gate set / clear | `0x9880014c` / `0x988001c8` | |
| header writer `img_header_make` | `0x6031b712` | `0x6033085c` |
| header writer call in `rec_jpeg_make_header` / `rec_raw_make_header` | `0x60408c44` / `0x6040ebd2` | |
| header writer call in playback edits / movie EXIF | `0x612b1460` / `0x612e7602` | |
| IFD writer | `0x6031bdba` | `0x60330f04` |
| header defaults | `0x6031c812` | |
| descriptor tables JPEG / TIFF / ORF | from `0x604e4590` / `0x604e4d80` / `0x604e5380` | |
| EXIF parser / its `II`-`RO`-MakerNote check | `0x6031a8af` / `0x6031a025` | |

*Raw compressor and EXIF header writer.[^fw1]*

### Files and SD host

| item | E-M5 III | OM-5 II |
|---|---|---|
| `filewrap.c` | `0x6064113f` to `0x60646c86` | |
| `fileif.c` | `0x60631aa6` | |
| file operation strings | `0x60743e35` to `0x607442cc` | |
| boot-sector type strings | `0x607400b9` | |
| folder template `DCIM\100OLYMP` | `0x604daddc` | |
| DPOF writer strings | `0x607402e8` | |
| FILECLBK mailbox | `0x60040f5c` | |
| FILECLBK handler / message-to-command table | `0x6062cc7b` / `0x60740638` | |
| `dosfat_exec` / its command table | `0x6061e86c` / `0x6074015c` | `0x6069677d` |
| FAT command name table | `0x60744c2c` | |
| byte count to sectors (UHS-II rounding) | `0x6061e2a8` | |
| error log printer | `0x606388b3` | |
| `file` command help text | `0x60740abc` | |
| SD register dump | `0x606498ad` | |
| SD host port base table | `0x60746728` | `0x607cf110` |
| SD host port 0 / port 1 | `0x99000000` / `0x9a300000` | same |
| port 1 command block (SDIO host) | `0x9a302000` | |
| SD register name table | `0x60746f74` | |
| port query (port, 2) | `0x60647d71` | |
| UHS-II flag reader | `0x6064b21a` | |
| per-port record (+340 × port, flag at byte +336) | `0xa25c1304` | |

*File layers and SD host.[^fw1]*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware, 2026-11-25. E-M5 III 1.7 block0, compared with OM-5 II 1.1 block0. No camera runs.
[^inf1]: Inferred, not traced to the end, 2026-11-25.
[^fix1]: Corrected on 2026-11-25. The earlier count of 13 parameters missed the leading 0. See [History](#history).

## History

- 2026-11-25: the CPU1 and CPU2 page said CPU2 runs the still record pipeline. The task tables narrow that. The
  pipeline runs on CPU0, and CPU2 has three helpers.
- 2026-11-25: the CIC parameter list was first counted as 13 values. It has 14, because the leading 0 was missed.

