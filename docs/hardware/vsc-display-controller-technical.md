# Display controller registers: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Display controller](vsc-display-controller.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

The VSC is the display controller. It reads the live-view picture and the GUI layers from memory and mixes them. It
runs the display-side picture blocks (gamma, colour, highlight and shadow, peaking, histogram) and sends the result to
the rear screen (TFT), the electronic viewfinder (EVF) or HDMI. This page is the register-level map. For the big
picture start with [Graphics pipeline](graphics-pipeline.md). For the on-screen display (OSD) layers and the live-view
frame pointer see [Display and OSD](display.md).

Everything you see on the rear screen or in the viewfinder passes through this one block last. That makes it the place
for "view assists" that change only what you see, not the photo. Examples are a red night view, zebra stripes on bright
areas, an RGB clipping view and peaking colours. The [Summary](#summary) sums up the findings,
[View assists](#view-assists) lists which assist needs which registers, and [Camera results](#camera-results) says what
our own display mods showed on the camera. The sections from [Address space](#address-space) to
[Console commands](#console-commands) are the register-by-register reference.

Most of the page is read from the code. The sources are the stock block0 disassembly, with every VSC register access
listed per function, the firmware's own register name tables, and om-emu's source.

Addresses are E-M5 III 1.7 block0 addresses (base `0x60021020`) unless a body is named. Register offsets (`+0x...`)
are per channel. Function and table addresses are in the [Address reference](#address-reference).

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred or seen in an emulator.

## Summary

- **Same chip on four bodies.** The E-M5 III, OM-5, E-M1 III and OM-5 II carry the identical 422-entry register name
  table, with the same names and the same offsets. om-emu calls this "VSC kind 2". The OM-1 and OM-1 II have a newer
  VSC with 503 names at different offsets, which adds native zebras, night vision and colour management. The E-M5 II
  and PEN-F have an older one (om-emu "kind 3").[^fw2]
- **The E-M5 III driver names its own functions.** 67 `[DISP] <DRV> :display_vscdrv_*` debug strings map to 62 driver
  functions in block0 (sections 0 and 1). So most registers now have a named writer (see
  [Driver functions](#driver-functions)).[^fw1]
- **Corrections to older pages.** ROT1-4 are a **colour** block, saturation gains for the Vivid and Natural display
  colour mode, not picture rotation. The highlight and shadow unit is also the **zebra** unit, with two thresholds, two
  colours, a window and a blink rate. COLMAT (the 3 × 3 colour matrix) is **never written** by stock code.[^fw1][^fix2]
- **What this gives view assists.** A red night view is two zeroed gamma tables and one GAM1 write on the EVF. Zebras
  and their colours are set by `set_hi_sh`. Peaking colours are four fixed YCbCr words. Mirror and desqueeze have no
  obvious register yet. See [View assists](#view-assists).[^inf2]

## Address space

The registers start at the VSC base, with `0x4000` bytes per channel. Channel 0 is the TFT or the EVF (one at a time),
and channel 1 is HDMI. A selector function picks the channel.[^fw1]

| range (per channel) | what | evidence |
|---|---|---|
| `+0x000` to `+0x3f4` | the registers (422 names including `_VL`, index × 4 = offset) | name table[^fw1] |
| `+0x400` to `+0x7e8` | latched copies `*_VL` (`+0x400` of the live register), read-only, take effect at the frame boundary | names[^fw1], behaviour[^emu1] |
| `+0x800` to `+0x1fff` | OSD palettes. Plane q at `+0x800 + 0x800 × q`, 128 words, second bank `+0x200` (bit 4 of OSD14/16/18) | writer[^fw1], layout[^emu1] |
| `+0x2000` to `+0x2bff` | **gamma tables**: 3 components × 2 banks × 128 words (see [Gamma](#gamma)) | `gamma_data_set`, dump `GMA_TBL.bin`[^fw1] |
| `+0x2c00` on | histogram bins (64, 128 or 256) | `hist_get_calc_result`[^fw1] |
| `+0x2e00` on | external-OSD copy data | `extosd_cpdata_set`[^fw1] |
| `+0x3200` to `+0x323c` of channel 0 | panel **serial engine** (start = `+0x3214` bit 0, done = INTST1 bit 15), command words at `+0x3800` | serial functions[^fw1], role[^emu1] (`vsc.mjs` SERIAL_START) |
| separate block | OSD draw engine | [graphics pipeline](graphics-pipeline.md) |

*The VSC address space. Absolute addresses are in the [Address reference](#registers-and-memory).*

- The `0x3200` block is only reached at channel 0's base (absolute addresses), so it is one shared engine, not per
  channel.[^fw1]
- Most driver code addresses a register as base + offset + ch × `0x4000` directly. Plane-indexed blocks (AREA, RSZ,
  DMA) are addressed as base + index × 4, with the index from small tables. Only DMA7 (plane enables) has a helper,
  which takes d0 = ch and d1 = value.[^fw1]
- No block0 code ever writes COLMAT and COLMAT_K12 to K9, REQ1-6, FIFOMIN1-5, MONI1-2, RAND1-2, OSR, FRM1-2, AREA19-21
  apart from the histogram window, or DENC apart from output init. No load of their addresses appears anywhere in
  block0. The only reference to COLMAT is the dump list.[^fw1]

## Register groups

Offsets are per channel. The "written by" column names the stock writer. [Picture blocks](#picture-blocks) has the bit
fields we could read.

| group | registers | role | written by |
|---|---|---|---|
| core | CTRL1-3 `+0x0` to `+0x8`, INTEN1 `+0xc`, INTST1 `+0x14`, INTEN2/INTST2 `+0x3c0`/`+0x3c4` | control, interrupts (INTST1 bit 0 frame, bit 15 serial engine) | initialize, sync_init, finalize |
| plane DMA | DMA1-3 `+0x18` to `+0x20` (IMG1-3 DMA mode), DMA7 `+0x30` (enables, bit 5-p), DMA9-11 `+0x38` to `+0x40` (IMG1-3 address), DMA12-14 (OSD1-3 address), DMA15-17 (IMG strides), DMA18-20 (OSD strides, 64-byte units), DMA21-29 | which buffers are shown | update_set_through_addr, set_imgformat, image_init, osd_init |
| areas | AREA1-9 (IMG1-3, three words each), AREA10-18 (OSD1-3), AREA19-21 (histogram window), AREA22-24 (video area), AREA25-27 (peaking window), AREA28-30 (hi/sh window) | where each plane and feature sits | image_init, osd_init, hist_prm_set, set_peak_area, set_hi_sh |
| resize | RSZ1-35 `+0x104` to `+0x18c` | scalers (IMG and OSD, EVF OSD 640 → 1024 via RSZ18/24/30) | image_init, h/v_rsz_*_custom |
| planes | BG1 `+0x190`, IMGPLANE1-4 `+0x194` to `+0x1a0`, OSD1/2/4 `+0x1a4` to `+0x1b0`, OSD7-18 | background colour, plane format and level, OSD order, mix, level and palette bank | background_set, set_imgformat, layeroff, osd_mixorder |
| test | TEST1 `+0x1bc` | test pattern | test_pattern |
| output | TVTFT1-17, DENC, TFTOUT1-4, HDMI1-2, DAC, SYNC1-12, SYNCV1-2, VSRST1-2, VMASK1, CLKPATHSEL, DATAPATHSEL1-3, CYCLE1 | panel and HDMI timing and routing | output_init, sync_init |
| filter | LPF1-6 `+0x268` to `+0x27c` | low-pass filters (output init only)[^inf1] | output_init |
| **gamma** | GAM1 `+0x204`, GAM2 `+0x208`, tables `+0x2000` | per-component LUTs, double-buffered | gamma_select, gamma_read_switch, gamma_data_set |
| **histogram** | HIST1-3 `+0x244` to `+0x24c`, bins `+0x2c00` | Y/R/G/B histogram of the shown image | hist_* |
| **hi/sh, zebra** | HILIGHT1-4 `+0x250` to `+0x25c`, AREA28-30, BC3 `+0x350` | highlight and shadow warning = zebra | set_hi_sh, exec_hi_sh, set_hi_sh_blink |
| **colour** | ROT1-4 `+0x288` to `+0x294` | saturation gains (display colour mode)[^inf1] | set_rot |
| **chroma** | CRM1-7 `+0x298` to `+0x2b0` | chroma conversion, set once at init[^inf1] | set_chroma |
| **colour matrix** | COLMAT `+0x2ec`, COLMAT_K12 to K9 `+0x2f0` to `+0x300` | 3 × 3 matrix (K1 to K9, two per word) | **none**, never written |
| **peaking** | PEAK1-14 `+0x32c` to `+0x3e8` (PEAK6-14 from `+0x3c8`) | focus-peaking edge detector, threshold, colour | set_peak_*, exe_peaking |
| blink | BC1-2 `+0x348`/`+0x34c` (IMG), BC3 `+0x350` (hi/sh) | blink cycles | set_img_blink, set_hi_sh_blink |

*Register groups at a glance. Writers read in block0.[^fw1] Roles marked with an inferred note are not traced.*

## Picture blocks

### Planes, format, order and background

- **IMGPLANEp** (`+0x194 + 4p`, p = 0 to 2 for IMG1 to IMG3). Bits 20-23 = format − 1, bit 12 = per-pixel alpha
  (formats with alpha), bits 0-8 = plane level (`0x100` = full).[^fw1]
- `set_imgformat` takes format 1 to 10, and the `disp` console names them in order: **0 YC, 1 YC/YP, 2 OSD,
  3 R8G8B8a8, 4 R8G8B8X8, 5 R5G5B5a1, 6 R5G5B5X1, 7 R4G4B4a4, 8 R4G4B4X4, 9 R5G6B5**. This confirms the c3d layer's
  IMGPLANE2 format 3 = R8G8B8a8 ([c3d GPU](c3d-gpu.md)).[^fw1]
- IMG1 takes only bits 12-13 and 20 (YC formats). The matching DMA1-3 byte gets bit 4 for some formats.[^fw1]
- `display_vscdrv_layeroff` writes `0x100` into bits 0-8 of IMGPLANE1-3. So "layer off" is not level 0.[^fw1] The
  meaning of `0x100` there is open.[^inf1]
- **OSD1** (`+0x1a4`) bits 0-3 = OSD mix order code 0 to 5 (`osd_mixorder`, a read-modify-write of the low nibble).
  Stock is 3.[^fw1]
- **BG1** (`+0x190`) = Cr << 16 | Cb << 8 | Y (`background_set`, arguments a1 = Cr, a0 = Cb, d1 = Y). Stock is
  `0x80800b` (black). It is written at boot, by `disp bg` and by the test pattern.[^fw1]
- **TEST1** (`+0x1bc`) = (width / n) << 4 | mode. `test_pattern` first writes DMA7 = 0 (all planes off). It then picks
  mode 6 (n 8), 2 (n 17) or 3 (n 7) from a 15-entry jump table. The console offers 0 off, 1 colour bar and
  2 7 steps.[^fw1]

### Gamma

- **Tables.** Component c (0 to 2), bank b (1 or 2) is 128 words at `+0x2000 + 0x400 × c + 0x200 × (b − 1)`. Each word
  holds two entries of 10 bits each. Word i = (t[2i+1] << 2) << 16 | (t[2i] << 2), from an 8-bit table t of 256 entries
  (`gamma_data_set`, a0 = table, a1 = bank, d1 = component).[^fw1]
- **GAM1** (`+0x204`) = comp2 bank << 8 | comp1 bank << 4 | comp0 bank (`gamma_select`). 0 = gamma off (bypass),
  `0x111` = bank 1, `0x222` = bank 2. GAM1 has a latched copy GAM1_VL.[^fw1]
- **GAM2** (`+0x208`) bit 0 = CPU read access to the tables (`gamma_read_switch`). The `disp dump` reader sets it to
  read, then clears it.[^fw1]
- **The writer** is called from the DISP gamma request. It takes a gamma id 0 to 19 and picks the device's table set
  (0 = TFT, 1 = EVF). It writes the three components into the bank that is **not** shown, clears GAM2 and flips GAM1
  (`0x111` ↔ `0x222`). Id 16 = gamma off (GAM1 = 0). The id table has 2 × 20 entries of 16 bytes, each
  {u8 id, ptr c0, ptr c1, ptr c2}.[^fw1]
- **What the stock tables do.** All TFT tables are identity, because the rear screen's colour adjust happens in the
  panel. The EVF set holds the **EVF colour temperature** steps. Ids 4-6 cut c1 and most of all c2 (warm: c2 ends at
  180, 210, 235). Id 7 is neutral. Ids 8-10 cut c0 most (cool: c0 ends at 240, 225, 210).[^fw1] So **c0 = R, c1 = G,
  c2 = B** is the natural reading, which also makes the block an RGB gamma after the YCbCr → RGB step.[^inf1] The camera
  later confirmed c0 = R (see [Camera results](#camera-results)).
- The firmware rewrites gamma only on a DISP gamma request (device change, EVF colour temperature), not per frame. There
  is a single caller chain.[^fw1]
- **Bank choice.** The writer picks the hidden bank **from the GAM1 register itself**, not from a RAM copy.
  `get_gamma_table` reads GAM1 and picks bank 1 when it reads `0x222` or 0, else bank 2. So a third party may flip GAM1
  too. The next stock request then writes the other bank and leaves GAM1 different from the third party's value. Our
  display mods use that as their "driver changed it" signal.[^fw1]
- **Devices.** The device argument is 1 = rear TFT (table set 0) or 2 = EVF (set 1, after a check). The channel
  selector maps device bits 1 and 2 to channel 0 and 4 to channel 1.[^fw1]
- **Active screens.** One RAM word holds the DISP code's active device bits (1 TFT, 2 EVF, 4 HDMI). It is OR'd in one
  place and read before `display_update_through_image`.[^fw1]

### Histogram

- The element (Y, R, G or B) is HIST2 bits 24-25 (`hist_targetelement_set`). HIST1 = run and enable
  (`hist_calc_enable`). The window is AREA19-21. The bins are at `+0x2c00`, and `hist_get_calc_result` reads HIST3_VL
  first.[^fw3]
- `hist_prm_set` always sets HIST2 bit 20, sets bit 12 when the device is not active, and takes the low bits from the
  bin count (64 → 0, 128 → 1 or 2). The compare chain is not fully decoded.[^fw3] More in
  [Display and OSD](display.md).

**How live view uses it, and where RGB lives.**[^fw3]

- **Driver request.** It is 6 words: `+4` Y main, `+8` Y sub-area, `+0xc` R, `+0x10` G, `+0x14` B buffer, `+0x18`
  event. A driver mode byte selects the behaviour.
    - **Mode 1** = continuous Y on main and sub area (element 1, then "element 5" = sub buffer).
    - **Mode 3** = one-shot. The first non-zero slot of `+4`, `+0xc`, `+0x10` and `+0x14` → element 1, 2, 3 or 4
      (= Y, R, G, B, confirmed by the slot order).
- **App layer.** `CapHis_Histogram` does the calculation. Its facade `CapHis_HistogramFacade` has slot 17 start, slot 18
  stop and slot 14 = setParam(calcMode, Y, R, G, B enable flags, ...). A global holds the calc mode.
    - **`0x11` = live view "through".** One continuous request with all five buffers (Y, Ysub, R, G, B, `0x400` bytes
      each), which runs only Y main and sub.
    - **`0x20` = Rec View.** Four one-shots Y → R → G → B, stopping between them.
    - Four enable flags (Y, R, G, B) sit next to the calc mode.
- **Plumbing.** `CmpSqp_SequencePartsBase::startThroughHistogram` already passes per-channel R, G and B flags into
  setParam with calcMode `0x11`. `getHistogramData` returns all four channels (`0x404` bytes each: valid flag, main
  bins, sub bins) when the flags are set. So RGB is plumbed end to end. Only the through mode never measures it.
- **Drawing.** `guiDrawHistogram::draw_shooting` and `draw_play_detail` call `draw_Histogram_Parts` per channel, with a
  colour index set through a helper.
- **An RGB live-view histogram.** The unit must be time-shared (stop through, three one-shots R, G and B, restart
  through), like Rec View does. All of this is app code inside the loader patch range, so it can be a card mod.[^inf2]
- **Driving it without CapHis.** The histogram API start (a0 = {Y, Ysub, R, G, B, device}) and stop (d0 = device from a
  helper called with 1, 1) send DISP COM commands 14 and 15. 13 = set and 16 = calc end. The dispatcher table is indexed
  by cmd − 2. The driver state holds the mode, the element, the buffer (cleared when a one-shot ends), the sub buffer
  and an event divider and counter.[^fw1][^emu2] Details: Live RGB histogram.

> [!WARNING]
> The stock Rec View histogram pass waits for its end event with no time-out (message 443). Calling it from a mod task
> hung the camera.[^cam2]

### Highlight and shadow (zebra)

`display_vscdrv_set_hi_sh` is called from the DISP request switch (`SET_HISH`). It takes a record and two colour
pointers (a1 highlight, d1 shadow).[^fw1] The record holds:

- `+4` → {x, y}
- `+8` → {w, h}
- `+12` → attr_hilight {layer, hi_thresh}
- `+16` → attr_shadow {sh_thresh}
- `+20` blink cycle
- `+24` byte

| register | content |
|---|---|
| AREA28 `+0x320` | first get_size output word 0 << 16 \| second output word 0. om-emu full screen on the TFT: **`0x1e02d0`** (30, 720), so most likely x << 16 \| w[^fix1] |
| AREA29 `+0x324` | the same for word 1. om-emu **`0x801e0`** (8, 480), likely y << 16 \| h |
| AREA30 `+0x328` | second output word 1, halved for an interlaced device. om-emu `0x1e0` (480), likely the height |
| HILIGHT1 `+0x250` | bit 0 = target layer (attr_hilight byte 0). Bits 8-9 = highlight on, bits 4-5 = shadow on (`exec_hi_sh`, mask `0x330`, `EXE_HISH`) |
| HILIGHT2 `+0x254` | byte at `+24` << 16 \| hi_thresh << 8 \| sh_thresh |
| HILIGHT3 `+0x258` | highlight colour, 3 bytes (c[2] << 16 \| c[1] << 8 \| c[0]) |
| HILIGHT4 `+0x25c` | shadow colour, the same form |
| BC3 `+0x350` bits 0-7 | blink field from the blink cycle in ms (default 1000, `set_hi_sh_blink`) |

*Highlight and shadow registers as `set_hi_sh` fills them.[^fw1] Window values from om-emu.[^emu2]*

- **Two-level zebras in hardware.** One threshold marks highlights and the other shadows, each with its own colour, in
  a window, optionally blinking.[^fw1] The OM-1's newer VSC uses the same HILIGHT1 bits `0x330` for its zebra. It adds
  ZEBRA1_1 to 7 and ZEBRA2_1 to 7 pattern registers (zebra record {onoff, 200, 100}).[^emu1]
- **Colours are YCbCr** (Cr << 16 | Cb << 8 | Y). The DISP hi/sh request converts the GUI's RGB colours with BT.601
  before calling `set_hi_sh`. Y = 0.299R + 0.587G + 0.114B, with Cb and Cr + 128 (constants 19595, 38470, 7471,
  −11056, −21712, −27440, −5328). The same formula gives the stock peaking words exactly (red `0xff544c`, yellow
  `0x9400e1`).[^fw1]
- **Window.** When the record's window is 0, `set_hi_sh` calls `get_size` (d0 = device, a0 and a1 → two {u16, u16}
  outputs, d1 → 4 bytes). It takes the AREA28/29 high halves from the a0 output and the low halves from a1. In om-emu
  (TFT) that gives (30, 8) and (720, 480), which are offset and size.[^fw1][^emu2]
- **Mode 1 in the 2-bit on fields draws a flat colour, not stripes.** Our zebra card mod showed solid red highlights and
  solid blue shadows. Value 2 looks about the same as 1, perhaps slower to respond. Value 3 shows nothing
  visible.[^cam1]
- This VSC has no zebra pattern registers, unlike the OM-1's newer VSC. So true stripes are likely not available in
  hardware.[^inf2]
- **Who writes hi/sh, and a hook for it.** `set_hi_sh` has one caller, in the DISP hi/sh request (the `SET_HISH` case
  of the DISP request switch, one call per active device). `exec_hi_sh` has one caller (the `EXE_HISH` case). Both calls
  are 5-byte `call` instructions followed by the caller's own `ret`, in task context. So each can become `dc rel32` to a
  wrapper that makes the same call in the same frame and then writes its own values.[^fw1] Our zebra card mod does
  this. om-emu runs it, and a stock `SET_HISH` or `EXE_HISH` is recorded and overwritten in the same request.[^emu2]
- The console reads all of this. `disp hish get` prints the fields ("hish exec hi/sh, layer, coord_x/y, size_w/h,
  blink_cycle").[^fw1]

### Peaking

- **Window and enable.** `set_peak_area`/`set_peak_ctrl` copies the chosen IMG plane's area into AREA25-27 (`+0x314` to
  `+0x31c`) and writes PEAK1 (`+0x32c`) bit 0 = on.[^fw1]
- **Colour.** `set_peak_color_palette` writes the same word to PEAK4 and PEAK5 (`+0x340`/`+0x344`), as
  Cr << 16 | Cb << 8 | Y. The camera's four peaking colours are 1 white `0x8080ff`, 2 black `0x808000`, 3 red
  `0xff544c` and 4 yellow `0x9400e1`. PEAK9 (`+0x3d4`) = 472 (white, yellow) or 40 (black, red) when the first
  argument is 1, else 0.[^fw1]
- **Edge detector.** `set_peaking_edge_detect` writes 9 signed bytes into PEAK6-8 (`+0x3c8` to `+0x3d0`). They come from
  adjustment value `0xc21` when present, else from defaults (mode 1: `0xf80c0c18`, `0x00faf804`, `0xfefa`, else
  `0xfefafa24`, `0xfeff`, ...). Then PEAK10 = 154, PEAK11 = `0x7ed1002c` and PEAK12-14 = `0x86ff0086`.[^fw1] A 3 × 3
  kernel is the likely reading.[^inf1]
- **Threshold.** `set_peaking_thresh` writes PEAK2 = t & `0xfffff` and PEAK3 = t ^ `0x1fffff`, with t from a table by
  peaking level (low, standard, high) and magnification. It runs from `display_update_through_image`, so the firmware
  **re-writes the threshold every live-view update**. Our own value would be overwritten.[^fw1]
- **Colour too.** `exe_peaking` (which calls `set_peak_color_palette` and `set_peak_area`) is also called from
  `display_update_through_image`, at two sites. So PEAK4/5 are probably rewritten per update as well. A custom peaking
  colour needs a hook at `set_peak_color_palette`, not a polling task.[^fw1]
- Console: `disp pkg` (`tl <level>`, `on`, `off`) and `disp dl ep` (debug level).[^fw1]

### Colour, chroma and colour matrix

- **ROT1-4** (`+0x288` to `+0x294`) are written as one 4-word record by `set_rot`. The only callers are the display
  colour-mode setter ("INVALID_COLOR MODE PRM") and one other function.[^fw1]
    - Mode 1 writes {`0x100`, `0x14000`, `0x1300000`, `0x111`}. Mode 2 writes {`0x100`, `0x10000`, `0x1000000`,
      `0x111`}.[^fw1]
    - Mode 2 is plain 1.0 gains, and mode 1 raises two of them to 1.25 and 1.1875. These are **colour saturation
      gains** for the Vivid and Natural display colour setting, not rotation.[^fw1]
    - The field layout is inferred. 1.0 = `0x100` at bit 0 of ROT1, bit 8 of ROT2 and bit 16 of ROT3, and ROT4 holds
      the enables.[^inf1]
    - It is probably what the firmware calls "color rotate". The `display_vscdrv_color_rotate_set`/`_exec` strings exist
      but nothing references them.[^inf1]
    - On the OM-1 the EVF writes non-identity ROT1-4 too (om-emu A14).[^emu1]
- **CRM1-7** (`+0x298` to `+0x2b0`). `set_chroma` writes a 7-word record once, from `display_vscdrv_initialize`. Mode 2
  fills {0, 0, `0xc03e0`, `0xc0000`, `0x3f4`, `0xc0000`, 0}, and other modes write zeros.[^fw1] The role is open. An
  output colour-space or chroma-limit stage is likely.[^inf1]
- **COLMAT** (`+0x2ec`) and **COLMAT_K12, K34, K56, K78, K9** (`+0x2f0` to `+0x300`) hold nine coefficients, two per
  word, with latched copies. **No block0 code writes them** on the E-M5 III.[^fw1] om-emu found the same on the OM-1:
  "COLMAT never written on these paths".[^emu1] So the matrix sits at its reset value, which is unknown. Bypass is the
  obvious guess. It is the most direct register for false colour, inverted or red views, if it works. The first step is
  to read it on the camera.[^inf1]
- `display_vscdrv_set_knee` has a string but no code, and this family's name table has no KNEE register. The OM-1's VSC
  has KNEE1-13. So this is dead driver code shared with the newer body.[^fw1]

## Driver functions

The driver functions are named from their own debug strings (`[DISP] <DRV> :name`). Their addresses and the registers
each one writes are in the [driver function table](#driver-function-table). The full register list per function is in
our access list.[^fw1]

Some strings have no code reference and are dead in this body. They are color_rotate_set/exec, set_knee,
get_dmatransfer_addr, get_img3_addr, get_img/osd_active_area_offset and dmaerr_clear_intr_status.[^fw1]

## Console commands

The user shell's `disp` command has a table of {name, handler} pairs. These sub-commands touch the VSC.[^fw1]

| command | what it does |
|---|---|
| `disp vsc r` | prints every named register (both channels when both are active) by walking the name table. `r 1`/`r 2` snapshot, `r 3` compares the snapshots. Also `check`, `info` (plane enables, sync), `clk`, `set_th_time`, `get_th_line` |
| `disp dump` | writes to the card: `OSD%d.RAW` (OSD planes), `VSC_REG.bin` (channel 0, `+0x000` to `+0x3ff` only, so no `_VL` and no channel 1), `GMA_TBL.bin` (`+0x2000` to `+0x2bff`, with GAM2 = 1 during the read), `VSC_OSD.bin` (palettes) |
| `disp hish get` / `disp hish exe tft\|bievf ...` | `get` prints the hi/sh fields (HILIGHT1, AREA28-30, BC3 and their `_VL`). `exe` posts hi/sh requests through the normal display request path (arguments not decoded) |
| `disp pkg` | peaking test. Writes PEAK1-14 and AREA25-27 (`tl <level>`, `on`, `off`) |
| `disp bg X Y Z` | sets BG1 |
| `disp test N` | test pattern: 0 off, 1 colour bar, 2 7 steps |
| `disp histogram`, `disp hst` | **empty stub** (`retf`) in this build, although the help text offers `show` / `set PRM VAL` |
| `disp es` (`upds`, `updi`, `updo`, `setcp`, `setlc`) | loads test pictures from the card (`C:\test.raw`, `C:\osd.raw`, ...) into planes |

*`disp` sub-commands that touch the VSC. Handler addresses are in the [Address reference](#console-handlers).*

- `disp vsc r` reads INTST1, INTST2 and SRAM1/2 too. Older notes say reading them has side effects. Olympus's own debug
  command does it anyway, but it is the one risk of a read-only dump.[^fw1][^inf1] `disp dump` avoids INTST2 and SRAM.
  It reads only up to `+0x3ff`, which still includes INTST1.[^fw1]
- No `disp` sub-command writes an arbitrary VSC register. `wm`, `lut`, `histogram`/`hst` and `hd` are empty stubs. A
  register poke needs a memory-write command (the system shell's `mem_put*`, untested, see
  [Wi-Fi debug shell](../features/wifi-debug-shell.md)) or a build.[^fw1]

## Other bodies and om-emu

- **Identical register table** (422 names, same offsets) in the OM-5 1.2, E-M1 III 1.6 and OM-5 II 1.1. Their driver
  debug strings are not in the images we read (compressed or stripped), so function addresses must be found by
  pattern. The dump file names (`VSC_REG.bin`, `GMA_TBL.bin`) and the format names are present in all of them.[^fw2]
- **OM-1 1.9 and OM-1 II 1.3** have a different, larger VSC with 503 names. It has per-plane DMASETn blocks, IMGnFMT,
  and its own HIST, PEAK, HILIGHT and COLMAT at new offsets. It adds **ZEBRA1_1-7/ZEBRA2_1-7, KNEE1-13, YGAIN, RGBCNV,
  CMM (colour management, 64 knee points), NVEN and NV11 to NV23 (night vision)** and YCEXT.[^fw2] So the OM-1's red
  night-vision view is a dedicated block, and the E-M5 III family has to do it with gamma. That NV means night vision is
  inferred.[^inf1]
- **PEN-F and E-M5 II.** No name table was found. om-emu's "kind 3" has the offsets of kind 2 and two channels of
  `0x2000`.[^emu1]
- **om-emu** models kind 2 as register storage with latches. It composes OSD planes (and IMG planes with our patch),
  BG1, plane levels and OSD order. It does not apply gamma, COLMAT, ROT, CRM, hi/sh, peaking or the histogram to the
  picture. So none of the view assists can be checked for looks in om-emu, but the register writes themselves can be
  logged there.[^emu1]

## View assists

| assist | registers | how | open |
|---|---|---|---|
| red night view (EVF) | gamma c1, c2 (`+0x2400`/`+0x2800` banks), GAM1 | write zeros to the G and B tables in the hidden bank and identity to R, then flip GAM1. It stays until the next gamma request. | **works on the camera** on both screens as a card mod. c0 = R, and gamma applies on the rear screen too. It tints menus too. |
| red night view (any screen) | COLMAT | Y-only matrix into R | reset value, whether COLMAT is active at all |
| two-level zebras | HILIGHT1-4, AREA28-30, BC3 | `set_hi_sh` with chosen thresholds and colours, then `exec_hi_sh` | stripes or flat fill (colours are YCbCr). The camera rewrites these all the time, so zebras need a hook at `set_hi_sh`/`exec_hi_sh`. |
| RGB clipping view | gamma (3 LUTs) | each channel dimmed to 50%, values ≥ 250 at full | **works on the camera** as a card mod. It tints menus too. |
| peaking colours | PEAK4/5 | any YCbCr word instead of the four stock ones | threshold and probably colour rewritten each update, so it needs a hook at `set_peak_color_palette` |
| false colour | gamma (3 LUTs) or COLMAT | stepped LUTs per channel give a crude false colour on luminance only if the matrix can feed Y to all three | needs COLMAT |
| mirror, desqueeze | RSZ, AREA, DMA stride | desqueeze = IMG1 horizontal scale (RSZ1-5). Mirror has no known register (the swivel command talks to the panel). | RSZ field layout for IMG1 |
| brightness boost | gamma, BG1 | curve | none |

*Which registers each view assist needs. Inferred from the register map,[^inf2] with the camera results below.*

## Camera results

We built small card mods that write these registers, loaded by our mod loader with nothing flashed, and ran them on one
E-M5 III. They showed the following.[^cam1]

- **Red night view works.** Zeroing the G and B gamma tables turns the picture red. So gamma table c0 is red, and the
  gamma block acts on the rear screen as well as the EVF.
- **RGB clipping view works.** Per-channel gamma curves show clipped channels in their own colour.
- **Gamma acts on everything shown**, menus and info included, so a curve-based view also tints the menus. A view that
  leaves the menus alone needs its own overlay made from the live frame.
- **The camera rewrites the highlight and shadow (zebra) registers constantly** (HILIGHT1-4, AREA28-30), even when its
  own Highlight & Shadow view is off. A mod that polls and rewrites them only fights the camera. Zebras need a hook
  where the driver sets them (`set_hi_sh`/`exec_hi_sh`).
- **A register change needs an update request.** Every stock change ends with a call to the update-request function
  (d0 = device bits), which sets INTST1 = 1 and INTEN1 bit 0. The next frame interrupt applies the change and sets the
  waiters' event flag.[^fw1] A write without the request appears only at the camera's next own update, for example when
  you move in a menu.
- **A request made during start-up can be lost** while live view comes up. So a mod that applies at power-on should
  repeat it for a while.[^inf2]
- **Two mods that both swap the gamma bank must coordinate.** Otherwise one saves the other's curves as the camera's
  and leaves the screen darker after Off.[^inf2]
- om-emu stores and logs VSC register writes but does not draw gamma or zebras. So the look of a view assist can only
  be judged on the camera. om-emu also faults on reads of unnamed VSC offsets, so probes should read named registers
  only.[^emu2]

## Proposed camera tests

None of these has been run. Each is read-only or undoes itself at power-off.

1. **VSC read in live view** (read-only). Over the Wi-Fi shell, run `disp vsc r` on the TFT, then on the EVF, then with
   peaking on, the hi/sh warning on, and the EVF colour temperature at −3 and +3. This answers the COLMAT reset value,
   the live IMGPLANE1 and DMA1 values, the HIST2 field use, the PEAK and HILIGHT values per setting and GAM1 per
   device. Then `disp dump` gives `GMA_TBL.bin` (EVF) to confirm c0/c1/c2 = R/G/B against the EVF tables in the
   firmware. The risk is that the read touches INTST1, INTST2 and SRAM (see [Console commands](#console-commands)).
2. **Peaking colour and kernel check** (writes, undone by `disp pkg off` or power-off). Run `disp pkg on` / `tl N` and
   watch what changes.
3. **Hi/sh as zebra.** In the stock menu, set the highlight and shadow warning thresholds and look at the screen
   (stripes or flat colour). Then `disp hish get` reads the fields. No writes.
4. **COLMAT and gamma pokes** need a memory write. Run them only after test 1, and only through a reviewed build or the
   system shell's `mem_put4` once it is checked, never blind.

## Open questions

- The field layout inside RSZ, CRM, ROT and COLMAT.
- What LPF1-6 filter.
- The meaning of DMA22 and DMA27-29.
- Whether gamma acts on the TFT path.
- The COLMAT reset value, and whether COLMAT is active at all.
- The meaning of `0x100` in IMGPLANE1-3 after `layeroff`.

## Address reference

E-M5 III 1.7 block0 addresses unless a body is named.

### Registers and memory

| item | address |
|---|---|
| VSC base, channel 0 | `0x9c000000` (channel 1 at `+0x4000`). Driver code uses `0x9c0000xx + ch × 0x4000` directly. |
| plane-indexed blocks | `0x9c000000 + index × 4` |
| serial engine, command words | `0x9c003200` to `0x9c00323c`, `0x9c003800` |
| OSD draw engine | `0x9c100000` |
| active device bits (1 TFT, 2 EVF, 4 HDMI) | `0xa2653720`, OR'd at `0x6017fb51`, read at `0x60181223` |
| histogram driver mode, element, buffer, sub buffer | `0x62105acc`, `0x62105acd`, `0x62105ad0`, `0x62105ad4` |
| histogram event divider, counter | `0x62105ad8`, `0x62105ad9` |
| histogram calc mode global, enable flags Y/R/G/B | `0x621c7cec`, `0x621c7cf0`, `0x621c7cf4`, `0x621c7cf8`, `0x621c7cfc` |
| histogram buffers Y, Ysub, R, G, B (`0x400` bytes each) | `0x621c7d00`, `0x621c8100`, `0x621c8500`, `0x621c8900`, `0x621c8d00` |
| interlace flag per channel (used for AREA30) | `0xa26564b0[ch]` (halved when ≠ 1) |
| update-request waiters' event flag id | `0x60040e24` / `0x60040eaa` |

*Registers, RAM words and buffers.*

### Tables

| item | address |
|---|---|
| register name table | `0x60253888` |
| COLMAT dump list (only reference to COLMAT) | `0x602545c0` |
| format name strings | `0x601f0070` on |
| gamma id table (2 × 20 × 16 bytes) | `0x601f7cf8` |
| gamma tables | `0x601f22f8` to `0x601f7bf8` |
| EVF gamma tables cited by test 1 | `0x601f6df8` on |
| CRM mode 2 record | `0x600420c8` |
| DISP COM dispatcher table (index cmd − 2) | `0x601e7fe0` |
| `CapHis_HistogramFacade` vtable | `0x60b26274` |
| `disp` command table | `0x60253784` |
| histogram drawing strings `draw_shooting`, `draw_play_detail` | `0x611007f1`, `0x611008fb` |

*Tables and strings.*

### Driver function table

| address | name | registers |
|---|---|---|
| `0x60042a56` / `0x60042ec6` | display_vscdrv_initialize | palettes, CRM1-7, DMA8, INTEN1/2, INTST1, DMA29 |
| `0x600430a7` / `0x60043147` | display_vscdrv_h/v_rsz_osd_custom | OSD RSZ (indexed) |
| `0x60043208` | (helper) | DMA7 |
| `0x6004323d` | vscdrv_output_init | TVTFT, DENC, LPF1-6, AREA22-24, HDMI, TFTOUT, DAC, CLK/DATAPATHSEL, ROT1-4 |
| `0x60043748` / `0x601934ef` | vscdrv_image_init (/ _without_img3) | IMGPLANE1-4, DMA15-27, AREA1-9, RSZ1/6/12, BC1-2 |
| `0x6004392e` | vscdrv_osd_init | OSD1/2/4/7-18, AREA10-18, DMA18-26 |
| `0x60043bd2` | vscdrv_sync_init | SYNC1-12, DMA1-3, CTRL2/3, VMASK1, VSRST1/2, SYNCV1/2, INTST1 |
| `0x60043fee` / `0x60044a6f` | vscdrv_get_size / display_vscdrv_get_size | (RAM) |
| `0x6004404f` | channel selector (device bits 1/2 → channel 0, 4 → channel 1) | |
| `0x600440d9` | OSD palette writer | palettes |
| `0x60044181` | display_vscdrv_extosd_cpdata_set | `+0x2e00` |
| `0x600441e9` | display_vscdrv_background_set | BG1 |
| `0x60044226` / `0x600445ba` / `0x6004480e` | display_vscdrv_fwd_imgaddr / imgsize / extosdaddr_custom | IMG addresses, sizes (indexed), DMA17/23 |
| `0x6004486d` / `0x600449c2` | display_vscdrv_h_rsz_img_custom | IMG RSZ (indexed) |
| `0x60044a92` / `0x60044bcb` / `0x60044bf9` / `0x60044c41` | sync_sig_mask / d_sig_mask / tftdata_mask / hdmi_data_mask | TFTOUT2/3, SYNC7 |
| `0x60044c8c` / `0x601943ec` | display_vscdrv_ext_osd_enable / disable | DMA3 |
| `0x60044cf2` | display_vscdrv_get_blink_field | (computes BC fields) |
| `0x60044d23` / `0x60044da6` | display_vscdrv_set_img_blink / set_osd_blink | BC1-2 / OSD10-12 |
| `0x60044e69` | display_vscdrv_set_chroma | CRM1-7 |
| `0x60193788` | display_vscdrv_layeroff | IMGPLANE1-3 |
| `0x6019385f` | display_vscdrv_finalize | GAM1, ROT1-3, CTRL2 |
| `0x60193afe` / `0x60193b3f` / `0x60193b75` / `0x60194889` | gamma_select / gamma_read_switch / gamma_data_set / get_gamma_table | GAM1 / GAM2 / `+0x2000` / GAM1 |
| `0x60193c0d` / `0x60193d8a` | display_vscdrv_fwd_osdaddr / osdsize_custom | OSD addresses, sizes (indexed) |
| `0x60193f6f`, `0x60194425`, `0x6019445a`, `0x601944a1`, `0x601944e0`, `0x6019450a` | hist_prm_set, hist_targetelement_set, hist_calc_enable/disable, hist_clear_intr_status, hist_get_calc_result | HIST1-3, AREA19-21, INTEN1, INTST1, `+0x2c00` |
| `0x60194208` | display_vscdrv_dac_out_mask | DAC |
| `0x60194241` | display_vscdrv_test_pattern | DMA7, TEST1 |
| `0x6019458a` | display_vscdrv_osd_mixorder | OSD1 |
| `0x60194600` / `0x60194665` / `0x6019484b` | set_hi_sh_blink / set_hi_sh / exec_hi_sh | BC3 / AREA28-30, HILIGHT1-4 / HILIGHT1 |
| `0x601948b0` / `0x601949dd` | display_vscdrv_set_imgformat / get_imgformat | IMGPLANE1-3, DMA1-3 |
| `0x60194993` | display_vscdrv_set_rot | ROT1-4 |
| `0x60194a64` / `0x60194be8` / `0x60194c1c` | get_img1/2/3_dmatransfer_addr | DMA9-11 and `_VL` |
| `0x60194e50` / `0x60194f25` | update_set_through_addr / update_set_face_addr | DMA9/10 / DMA11 |
| `0x60194fa0`, `0x601950c0`, `0x6019511b`, `0x6019519b` | get_vdline, get_vdline_reg, get_hdline, set_hdline | MONI3, SYNC2/6/8/12 and `_VL` |
| `0x60195629` | display_vscdrv_ctrl_dma | DMA7 |
| `0x60195bf0`, `0x60195e45`, `0x60195ecd`, `0x60196078`, `0x60196869` | set_peak_area/ctrl, set_peak_color_palette, set_peaking_edge_detect, set_peaking_thresh, exe_peaking | PEAK1-14, AREA25-27 |
| `0x60196d71` to `0x601971a9` | serial engine functions | `0x3200` block |

*VSC driver functions in E-M5 III 1.7, named from their debug strings.[^fw1]*

### Other functions

| item | address |
|---|---|
| DISP request switch | `0x6017f904` |
| `SET_HISH` case, `EXE_HISH` case | `0x601802ee`, `0x60180306` |
| DISP gamma request, gamma writer | `0x60191898`, `0x60192a18` |
| gamma writer's wait (example of a stock update wait) | `0x60192c60` |
| EVF device check | `0x601918ee` |
| display colour-mode setter, other `set_rot` caller | `0x6018f912`, `0x60193234` |
| DISP hi/sh request (BT.601 conversion) | `0x6019215a` |
| `set_hi_sh` call site, `exec_hi_sh` call site and its function | `0x6019229f`, `0x601922b0` in `0x601922a7` |
| update request, frame interrupt apply | `0x601939ec`, `0x60193a4b` |
| update request helpers: critical-section check, clear flag, wait | `0x600386ae`, `0x6005123a`, `0x60051143` |
| `display_update_through_image` | `0x601907cb` |
| `exe_peaking` call sites in it | `0x601909f7`, `0x60190a53` |
| boot write of BG1, test pattern write | `0x60042e39`, `0x60194306` |
| histogram driver mode dispatch | `0x6018ebbe` |
| `CapHis_Histogram` calc (slot 17 start) | `0x608b1570` |
| facade slot 18 stop, slot 14 setParam | `0x608b1f13`, `0x608b27b6` |
| Rec View one-shot sequence | `0x608b1b98` to `0x608b1eaa` |
| `startThroughHistogram`, `getHistogramData` | `0x6098d258`, `0x608b25af` |
| `draw_Histogram_Parts`, colour index helper | `0x60e1ae5b`, `0x60c92389` |
| histogram API start, stop | `0x602e611a`, `0x602e638e` |
| stop's device helper (called with 1, 1) | `0x607c5ad9` |
| Rec View wait (event `0x04020301`, message 443) | `0x607c637b` |
| request path used by `disp hish exe` | `0x600548f7` |

*Other functions the page names.*

### Console handlers

| command | handler |
|---|---|
| `disp vsc r` | `0x60188867` |
| `disp dump` | `0x60189a66` |
| `disp hish` | `0x601870f4` |
| `disp pkg` | `0x6018989e` |
| `disp bg` | `0x60186c60` |
| `disp test` | `0x6018847c` |
| `disp histogram`, `disp hst` (empty stub) | `0x601870ee` |
| `disp es` | `0x60189d2b` |
| empty stubs `wm`, `lut`, `histogram`/`hst`, `hd` | `0x60184327`, `0x6018432a`, `0x601870ee`, `0x601870f1` |

*`disp` handlers.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the stock E-M5 III 1.7 block0, 2026-11-22.
[^fw2]: Read in the firmware by comparing the register name tables of six block0 images, 2026-11-22.
[^fw3]: Read in the firmware, 2026-11-20 and 2026-11-22.
[^emu1]: Read in om-emu's source, facts only.
[^emu2]: Seen in om-emu, 2026-11-22.
[^cam1]: Seen on our E-M5 III with our display card mods, 2026-11-22.
[^cam2]: Seen on our E-M5 III, 2026-11-22. The camera hung when a mod task called the stock Rec View pass.
[^inf1]: Inferred, not traced or tested.
[^inf2]: Inferred, 2026-11-22.
[^fix1]: Corrected 2026-11-22. It was read as w << 16 | x before.
[^fix2]: Corrected 2026-11-22 against older pages, see [History](#history).

## History

- 2026-11-22: ROT1-4 were read as picture rotation on older pages. They are colour saturation gains.
- 2026-11-22: the highlight and shadow unit was not known to be the zebra unit until its fields were traced.
- 2026-11-22: AREA28 was read as w << 16 | x. It is most likely x << 16 | w.

