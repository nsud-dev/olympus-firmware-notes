# Display controller registers: technical notes

> **Technical notes.** This page is the dense reference. For a readable introduction, start with [Display controller registers](vsc-display-controller.md).

The VSC is the display controller: it reads the live-view picture and the GUI layers from memory, mixes them, runs
the display-side picture blocks (gamma, colour, highlight/shadow, peaking, histogram) and sends the result to the rear
screen (TFT), the EVF or HDMI. This page is the register-level map. For the big picture start with
[Graphics pipeline](graphics-pipeline.md); for the OSD layers and the live-view frame pointer see [Display and OSD](display.md).

In plain words: everything you see on the rear screen or in the viewfinder passes through this one block last. That
makes it the place for "view assists" that change only what you see, not the photo: a red night view, zebra stripes on
bright areas, an RGB clipping view, peaking colours. Section 1 sums up what we found, section 8 lists which assist
needs which registers, and section 10 says what our own display mods showed on the camera. Sections 2-6 are the
register-by-register reference.

Tags: **[code]** read in the stock E-M5 III 1.7 block0, **[code] (om-emu)** read in om-emu's source, **[camera]** seen
on a camera, **[inferred]** reasoned, not traced or tested. Most of the page is read from the code (2026-11-22); the
camera results of our display card mods are in section 10.

Sources: the stock block0 disassembly, with every VSC register access listed per function, the firmware's own register
name tables, and om-emu's source.

## 1. Summary

- **Same chip on four bodies.** The E-M5 III, OM-5, E-M1 III and OM-5 II carry the identical 422-entry register name
  table (same names, same offsets). om-emu calls this "VSC kind 2". The OM-1 and OM-1 II have a newer VSC (503
  names, different offsets, adds native zebras, night vision, colour management); the E-M5 II/PEN-F have an older one
  (om-emu "kind 3"). [code] 2026-11-22 (name-table compare of the six block0 images)
- **The E-M5 III driver names its own functions.** 67 `[DISP] <DRV> :display_vscdrv_*` debug strings map to 62 driver
  functions in block0 (sections 0 and 1), so most registers now have a named writer (section 5). [code] 2026-11-22
- **Corrections to older pages.** ROT1-4 are a **colour** block (saturation gains for the Vivid/Natural display colour
  mode), not picture rotation. The highlight/shadow unit is also the **zebra** unit, with two thresholds, two colours,
  a window and a blink rate (section 4.4). COLMAT (the 3 × 3 colour matrix) is **never written** by stock code. [code] 2026-11-22
- **What this gives view assists:** a red night view
  is two zeroed gamma tables and one GAM1 write on the EVF; zebras and their colours are set_hi_sh; peaking colours are
  four fixed YCbCr words. Mirror and desqueeze have no obvious register yet. Section 8. [inferred]

## 2. Address space

Base **0x9c000000**, **0x4000 bytes per channel**: channel 0 = TFT or EVF (one at a time), channel 1 = HDMI (selector
0x6004404f). Inside a channel: [code] 2026-11-22 unless marked

| range (per channel) | what | evidence |
|---|---|---|
| +0x000..+0x3f4 | the registers (422 names incl. _VL; index ×4 = offset) | name table 0x60253888 [code] |
| +0x400..+0x7e8 | latched copies `*_VL` (+0x400 of the live register), read-only, take effect at the frame boundary | names [code]; behaviour [code] (om-emu) |
| +0x800..+0x1fff | OSD palettes: plane q at +0x800 + 0x800×q, 128 words, second bank +0x200 (bit 4 of OSD14/16/18) | writer 0x600440d9 [code]; layout [code] (om-emu) |
| +0x2000..+0x2bff | **gamma tables**: 3 components × 2 banks × 128 words (section 4.2) | gamma_data_set 0x60193b75, dump `GMA_TBL.bin` [code] |
| +0x2c00.. | histogram bins (64/128/256) | hist_get_calc_result 0x6019450a [code] |
| +0x2e00.. | external-OSD copy data | extosd_cpdata_set 0x60044181 [code] |
| 0x9c003200..0x9c00323c | panel **serial engine** (start = +0x3214 bit 0, done = INTST1 bit 15), command words at 0x9c003800 | 0x60196d71..0x601971a9 [code]; role [code] (om-emu `vsc.mjs` SERIAL_START) |
| 0x9c100000 | OSD draw engine (separate block) | [graphics pipeline](graphics-pipeline.md) |

- The 0x3200 block is only reached at channel 0's base (absolute addresses), so it is one shared engine, not per
  channel. [code] 2026-11-22
- Most driver code addresses a register as `0x9c0000xx + ch × 0x4000` directly. Plane-indexed blocks (AREA, RSZ,
  DMA) are addressed as `0x9c000000 + index × 4` with the index from small tables. Only DMA7 (plane enables) has a
  helper, 0x60043208 (d0 = ch, d1 = value). [code] 2026-11-22
- Never written by any block0 code: COLMAT and COLMAT_K12..K9, REQ1-6, FIFOMIN1-5, MONI1-2, RAND1-2, OSR, FRM1-2,
  AREA19-21 apart from the histogram window, DENC apart from output init. [code] 2026-11-22 (no load of their
  addresses anywhere in block0; the only reference to COLMAT is the dump list 0x602545c0)

## 3. Register groups at a glance

Offsets are per channel. "W by" names the stock writer; section 4 has the bit fields we could read.

| group | registers | role | W by | tag |
|---|---|---|---|---|
| core | CTRL1-3 +0x0..+0x8, INTEN1 +0xc, INTST1 +0x14, INTEN2/INTST2 +0x3c0/+0x3c4 | control, interrupts (INTST1 bit 0 frame, bit 15 serial engine) | initialize 0x60042ec6, sync_init 0x60043bd2, finalize 0x6019385f | [code] |
| plane DMA | DMA1-3 +0x18..+0x20 (IMG1-3 DMA mode), DMA7 +0x30 (enables, bit 5-p), DMA9-11 +0x38..+0x40 (IMG1-3 address), DMA12-14 (OSD1-3 address), DMA15-17 (IMG strides), DMA18-20 (OSD strides, 64-byte units), DMA21-29 | which buffers are shown | update_set_through_addr 0x60194e50, set_imgformat 0x601948b0, image_init 0x60043748, osd_init 0x6004392e | [code] |
| areas | AREA1-9 (IMG1-3, three words each), AREA10-18 (OSD1-3), AREA19-21 (histogram window), AREA22-24 (video area), AREA25-27 (peaking window), AREA28-30 (hi/sh window) | where each plane and feature sits | image_init, osd_init, hist_prm_set, set_peak_area, set_hi_sh | [code] |
| resize | RSZ1-35 +0x104..+0x18c | scalers (IMG and OSD; EVF OSD 640→1024 via RSZ18/24/30) | image_init, h/v_rsz_*_custom 0x600430a7.. | [code] |
| planes | BG1 +0x190, IMGPLANE1-4 +0x194..+0x1a0, OSD1/2/4 +0x1a4..+0x1b0, OSD7-18 | background colour, plane format/level, OSD order/mix/level/palette bank | background_set 0x600441e9, set_imgformat, layeroff 0x60193788, osd_mixorder 0x6019458a | [code] |
| test | TEST1 +0x1bc | test pattern | test_pattern 0x60194241 | [code] |
| output | TVTFT1-17, DENC, TFTOUT1-4, HDMI1-2, DAC, SYNC1-12, SYNCV1-2, VSRST1-2, VMASK1, CLKPATHSEL, DATAPATHSEL1-3, CYCLE1 | panel/HDMI timing and routing | output_init 0x6004323d, sync_init 0x60043bd2 | [code] |
| filter | LPF1-6 +0x268..+0x27c | low-pass filters (output init only) | output_init | [code] writer, [inferred] role |
| **gamma** | GAM1 +0x204, GAM2 +0x208, tables +0x2000 | per-component LUTs, double-buffered | gamma_select 0x60193afe, gamma_read_switch 0x60193b3f, gamma_data_set 0x60193b75 | [code] |
| **histogram** | HIST1-3 +0x244..+0x24c, bins +0x2c00 | Y/R/G/B histogram of the shown image | hist_* 0x60193f6f..0x6019450a | [code] |
| **hi/sh, zebra** | HILIGHT1-4 +0x250..+0x25c, AREA28-30, BC3 +0x350 | highlight/shadow warning = zebra | set_hi_sh 0x60194665, exec_hi_sh 0x6019484b, set_hi_sh_blink 0x60194600 | [code] |
| **colour** | ROT1-4 +0x288..+0x294 | saturation gains (display colour mode) | set_rot 0x60194993 | [code] values, [inferred] meaning |
| **chroma** | CRM1-7 +0x298..+0x2b0 | chroma conversion, set once at init | set_chroma 0x60044e69 | [code] writer, [inferred] role |
| **colour matrix** | COLMAT +0x2ec, COLMAT_K12..K9 +0x2f0..+0x300 | 3 × 3 matrix (K1..K9, two per word) | **none** | [code] never written |
| **peaking** | PEAK1-14 +0x32c..+0x3e8 (PEAK6-14 at +0x3c8..) | focus-peaking edge detector, threshold, colour | set_peak_* 0x60195bf0..0x60196078, exe_peaking 0x60196869 | [code] |
| blink | BC1-2 +0x348/+0x34c (IMG), BC3 +0x350 (hi/sh) | blink cycles | set_img_blink 0x60044d23, set_hi_sh_blink | [code] |

## 4. The picture blocks in detail

### 4.1 Planes, format, order, background [code] 2026-11-22

- **IMGPLANEp** (+0x194 + 4p, p = 0..2 for IMG1..IMG3): bits 20-23 = format − 1, bit 12 = per-pixel alpha (formats with
  alpha), bits 0-8 = plane level (0x100 = full). `set_imgformat` 0x601948b0 takes format 1..10, and the `disp` console
  names them in order: **0 YC, 1 YC/YP, 2 OSD, 3 R8G8B8a8, 4 R8G8B8X8, 5 R5G5B5a1, 6 R5G5B5X1, 7 R4G4B4a4, 8 R4G4B4X4,
  9 R5G6B5** (strings 0x601f0070..). This confirms the c3d layer's IMGPLANE2 format 3 = R8G8B8a8 ([c3d GPU](c3d-gpu.md)).
  IMG1 takes only bits 12-13 and 20 (YC formats). The matching DMA1-3 byte gets bit 4 for some formats. [code]
- `display_vscdrv_layeroff` 0x60193788 writes 0x100 into bits 0-8 of IMGPLANE1-3 (so "layer off" is not level 0;
  meaning of 0x100 there is open). [code] / [inferred]
- **OSD1** (+0x1a4) bits 0-3 = OSD mix order code 0..5 (`osd_mixorder` 0x6019458a, RMW of the low nibble). Stock 3. [code]
- **BG1** (+0x190) = Cr<<16 | Cb<<8 | Y (`background_set` 0x600441e9, args a1 = Cr, a0 = Cb, d1 = Y); stock 0x80800b
  (black). Writers: boot 0x60042e39, `disp bg` 0x60186c60, test pattern 0x60194306. [code]
- **TEST1** (+0x1bc) = (width / n) << 4 | mode: `test_pattern` 0x60194241 first writes DMA7 = 0 (all planes off) then
  picks mode 6 (n 8), 2 (n 17) or 3 (n 7) from a 15-entry jump table; the console offers 0 off, 1 colour bar, 2 7 steps. [code]

### 4.2 Gamma [code] 2026-11-22

- **Tables**: component c (0..2) bank b (1 or 2) is 128 words at **+0x2000 + 0x400×c + 0x200×(b−1)**. Each word holds
  two entries, 10 bits each: word i = (t[2i+1] << 2) << 16 | (t[2i] << 2), from an 8-bit table t of 256 entries
  (`gamma_data_set` 0x60193b75, a0 = table, a1 = bank, d1 = component). [code]
- **GAM1** (+0x204) = comp2 bank << 8 | comp1 bank << 4 | comp0 bank (`gamma_select` 0x60193afe); 0 = gamma off
  (bypass), 0x111 = bank 1, 0x222 = bank 2. GAM1 has a latched copy GAM1_VL. **GAM2** (+0x208) bit 0 = CPU read access
  to the tables (`gamma_read_switch` 0x60193b3f; the `disp dump` reader sets it to read, then clears it). [code]
- **The writer** 0x60192a18 (called from 0x60191898, the DISP gamma request) takes a gamma id 0..19, picks the device's
  table set (0 = TFT, 1 = EVF), writes the three components into the bank that is **not** shown, clears GAM2 and flips
  GAM1 (0x111 ↔ 0x222). Id 16 = gamma off (GAM1 = 0). Table: 2 × 20 entries × 16 bytes at **0x601f7cf8**, entry
  {u8 id, ptr c0, ptr c1, ptr c2}, tables 0x601f22f8..0x601f7bf8. [code]
- **What the stock tables do**: all TFT tables are identity (the rear screen's colour adjust happens in the panel).
  The EVF set holds the **EVF colour temperature** steps: ids 4-6 cut c1 and most of all c2 (warm: c2 ends at 180, 210,
  235), id 7 is neutral, ids 8-10 cut c0 most (cool: c0 ends at 240, 225, 210). [code] tables; so **c0 = R, c1 = G,
  c2 = B** is the natural reading, which also makes the block an RGB gamma after the YCbCr→RGB step. [inferred]
- The firmware rewrites gamma only on a DISP gamma request (device change, EVF colour temperature), not per frame.
  [code] (single caller chain)
- The writer picks the hidden bank **from the GAM1 register itself** (`get_gamma_table` 0x60194889 reads GAM1: bank 1
  when it reads 0x222 or 0, else bank 2), not from a RAM copy. So a third party may flip GAM1 too: the next stock request
  writes the other bank and leaves GAM1 different from the third party's value (our display mods use that as their
  "driver changed it" signal). Device argument: 1 = rear TFT (table set 0), 2 = EVF (set 1, after a check 0x601918ee);
  `0x6004404f` maps device bits 1/2 to channel 0, 4 to channel 1. [code] 2026-11-22
- Active screens: **0xa2653720** holds the DISP code's active device bits (1 TFT, 2 EVF, 4 HDMI; OR'd at 0x6017fb51,
  read at 0x60181223 before `display_update_through_image`). [code] 2026-11-22

### 4.3 Histogram [code] 2026-11-20/22

- Element (Y/R/G/B) = HIST2 bits 24-25 (`hist_targetelement_set` 0x60194425); HIST1 = run/enable (`hist_calc_enable`
  0x6019445a); window = AREA19-21; bins at +0x2c00 (`hist_get_calc_result` 0x6019450a reads HIST3_VL first).
  `hist_prm_set` 0x60193f6f: HIST2 bit 20 always set, bit 12 when the device is not active, low bits from the bin
  count (64 → 0, 128 → 1 or 2: the compare chain is not fully decoded). More in [Display and OSD](display.md). [code]
- **How live view uses it, and where RGB lives** (2026-11-22, stock block0 disassembly):
  - Driver request = 6 words: +4 Y main, +8 Y sub-area, +0xc R, +0x10 G, +0x14 B buffer, +0x18 event. Driver mode
    byte 0x62105acc: **mode 1** = continuous Y on main + sub area (element 1, then "element 5" = sub buffer);
    **mode 3** = one-shot, first non-zero slot of +4/+0xc/+0x10/+0x14 → element 1/2/3/4 (= Y/R/G/B, confirmed by the
    slot order). (0x6018ebbe) [code]
  - App layer `CapHis_Histogram` calc 0x608b1570 (facade `CapHis_HistogramFacade` vtable 0x60b26274, slot 17 start →
    0x608b1570, slot 18 stop → 0x608b1f13, slot 14 0x608b27b6 = setParam(calcMode, Y, R, G, B enable flags, ...)).
    Calc mode global 0x621c7cec: **0x11 = live view "through"**: one continuous request with all five buffers
    (Y 0x621c7d00, Ysub 0x621c8100, R 0x621c8500, G 0x621c8900, B 0x621c8d00, 0x400 bytes each), which runs only Y
    main/sub; **0x20 = Rec View**: four one-shots Y → R → G → B, stopping (0x602e638e) between them (0x608b1b98..1eaa).
    Enable flags 0x621c7cf0/f4/f8/fc (Y/R/G/B). [code]
  - `CmpSqp_SequencePartsBase::startThroughHistogram` 0x6098d258 already passes per-channel R/G/B flags into setParam
    with calcMode 0x11; `getHistogramData` 0x608b25af returns all four channels (0x404 bytes each: valid flag, main
    bins, sub bins) when the flags are set. So RGB is plumbed end to end; only the through mode never measures it. [code]
  - Drawing: `guiDrawHistogram::draw_shooting` / `draw_play_detail` (strings 0x611007f1 / 0x611008fb) call
    `draw_Histogram_Parts` 0x60e1ae5b per channel with a colour index set through 0x60c92389. [code]
  - Consequence for an RGB live-view histogram [inferred]: the unit must be time-shared (stop through, three one-shots
    R/G/B, restart through), like Rec View does. All of this is app code inside the loader patch range, so it can be a
    card mod. Plan: private notes (2026-11-22).
  - **Driving it without CapHis** [code]+[emu] 2026-11-22: histogram API start `0x602e611a` (a0 = {Y, Ysub, R, G, B,
    device}), stop `0x602e638e` (d0 = device from `0x607c5ad9`(1, 1)) send DISP COM commands 14/15 (13 = set, 16 =
    calc end; dispatcher table 0x601e7fe0, index cmd - 2). Driver state: mode 0x62105acc, element 0x62105acd, buffer
    0x62105ad0 (cleared when a one-shot ends), sub buffer 0x62105ad4, event divider/counter 0x62105ad8/ad9. The stock
    Rec View pass instead waits for event 0x04020301 with no timeout (message 443 via 0x607c637b): calling it from a mod
    task hung the camera (RGBH1). Details: Live RGB histogram.

### 4.4 Highlight/shadow = zebra [code] 2026-11-22

`display_vscdrv_set_hi_sh` 0x60194665 (from the DISP request switch 0x6017f904, `SET_HISH`) takes a record
{+4 → {x, y}, +8 → {w, h}, +12 → attr_hilight {layer, hi_thresh}, +16 → attr_shadow {sh_thresh}, +20 blink cycle,
+24 byte} plus two colour pointers (a1 highlight, d1 shadow):

| register | content |
|---|---|
| AREA28 +0x320 | first get_size output word 0 << 16 \| second output word 0; om-emu full screen on the TFT: **0x1e02d0** (30, 720), so most likely x << 16 \| w (corrected 2026-11-22, was "w << 16 \| x") |
| AREA29 +0x324 | same, word 1: om-emu **0x801e0** (8, 480), likely y << 16 \| h |
| AREA30 +0x328 | second output word 1, halved for an interlaced device (0xa26564b0[ch] ≠ 1): om-emu 0x1e0 (480), likely the height |
| HILIGHT1 +0x250 | bit 0 = target layer (attr_hilight byte 0); bits 8-9 = highlight on, bits 4-5 = shadow on (`exec_hi_sh` 0x6019484b, mask 0x330, `EXE_HISH`) |
| HILIGHT2 +0x254 | byte at +24 << 16 \| hi_thresh << 8 \| sh_thresh |
| HILIGHT3 +0x258 | highlight colour, 3 bytes (c[2] << 16 \| c[1] << 8 \| c[0]) |
| HILIGHT4 +0x25c | shadow colour, same form |
| BC3 +0x350 bits 0-7 | blink field from the blink cycle in ms (default 1000; `set_hi_sh_blink` 0x60194600) |

- So the E-M5 III has **two-level zebras in hardware**: one threshold marks highlights, the other shadows, each with its
  own colour, in a window, optionally blinking. The OM-1's newer VSC uses the same HILIGHT1 bits 0x330 for its zebra
  and adds ZEBRA1_1..7 / ZEBRA2_1..7 pattern registers (om-emu `docs/om1-vsc-spec.md`, zebra record {onoff, 200, 100}).
  [code] + [code] (om-emu)
- **Colours are YCbCr** (Cr << 16 | Cb << 8 | Y): the DISP request 0x6019215a converts the GUI's RGB colours with BT.601
  (Y = 0.299R + 0.587G + 0.114B, Cb/Cr + 128; constants 19595/38470/7471, -11056/-21712, -27440/-5328) before calling
  set_hi_sh. The same formula gives the stock peaking words exactly (red 0xff544c, yellow 0x9400e1). [code] 2026-11-22
- Window (fields above): when the record's window is 0, set_hi_sh calls `get_size` 0x60043fee (d0 = device, a0 and a1 ->
  two {u16, u16} outputs, d1 -> 4 bytes) and takes AREA28/29 high halves from the a0 output, low halves from a1. In om-emu
  (TFT) that gives (30, 8) and (720, 480): offset and size. [code] + [emu] 2026-11-22
- **Mode 1 in the 2-bit on fields draws a flat colour, not stripes** (our zebra card mod, 2026-11-22: solid red highlights,
  solid blue shadows) [camera]. Value 2 looks about the same as 1, perhaps slower to respond; value 3 shows nothing visible (2026-11-22) [camera].
  This VSC has no zebra pattern registers (the OM-1's newer VSC adds ZEBRA1/2_1..7), so true stripes are likely not available in hardware [inferred].
- **Who writes hi/sh, and a hook for it** [code] 2026-11-22: set_hi_sh has one caller, 0x6019229f in the DISP hi/sh
  request 0x6019215a (SET_HISH case 0x601802ee of the DISP request switch, one call per active device); exec_hi_sh has one
  caller, 0x601922b0 in 0x601922a7 (EXE_HISH case 0x60180306). Both are 5-byte `call` instructions followed by the
  caller's own `ret`, in task context, so each can become `dc rel32` to a wrapper that makes the same call in the same
  frame and then writes its own values. Our zebra card mod does this. om-emu runs it: a stock SET_HISH or EXE_HISH is
  recorded and overwritten in the same request. [emu]
- The console reads all of this: `disp hish get` prints the fields ("hish exec hi/sh, layer, coord_x/y, size_w/h,
  blink_cycle"). [code]

### 4.5 Peaking [code] 2026-11-22

- **Window and enable**: `set_peak_area`/`set_peak_ctrl` 0x60195bf0 copies the chosen IMG plane's area into AREA25-27
  (+0x314..+0x31c) and writes PEAK1 (+0x32c) bit 0 = on. [code]
- **Colour**: `set_peak_color_palette` 0x60195e45 writes the same word to PEAK4 and PEAK5 (+0x340/+0x344), Cr<<16 | Cb<<8 | Y:
  1 white 0x8080ff, 2 black 0x808000, 3 red 0xff544c, 4 yellow 0x9400e1 (the camera's four peaking colours). PEAK9
  (+0x3d4) = 472 (white, yellow) or 40 (black, red) when the first argument is 1, else 0. [code]
- **Edge detector**: `set_peaking_edge_detect` 0x60195ecd writes 9 signed bytes into PEAK6-8 (+0x3c8..+0x3d0), from
  adjustment value 0xc21 when present, else defaults (mode 1: 0xf80c0c18, 0x00faf804, 0xfefa; else 0xfefafa24, 0xfeff,
  ...), then PEAK10 = 154, PEAK11 = 0x7ed1002c, PEAK12-14 = 0x86ff0086. A 3 × 3 kernel is the likely reading. [code] values, [inferred] meaning
- **Threshold**: `set_peaking_thresh` 0x60196078 writes PEAK2 = t & 0xfffff and PEAK3 = t ^ 0x1fffff, t from a table by
  peaking level (low/standard/high) and magnification. It runs from `display_update_through_image` 0x601907cb, so the
  firmware **re-writes the threshold every live-view update**. Our own value would be overwritten. [code]
- **Colour too**: `exe_peaking` 0x60196869 (which calls `set_peak_color_palette` and `set_peak_area`) is also called from
  `display_update_through_image` (0x601909f7, 0x60190a53), so PEAK4/5 are probably rewritten per update as well; a
  custom peaking colour needs a hook at 0x60195e45, not a polling task. [code] 2026-11-22
- Console: `disp pkg` (`tl <level>`, `on`, `off`) and `disp dl ep` (debug level). [code]

### 4.6 Colour (ROT), chroma (CRM), colour matrix (COLMAT)

- **ROT1-4** (+0x288..+0x294) are written as one 4-word record by `set_rot` 0x60194993. The only callers are the
  display colour-mode setter 0x6018f912 ("INVALID_COLOR MODE PRM") and 0x60193234. Mode 1: {0x100, 0x14000, 0x1300000,
  0x111}; mode 2: {0x100, 0x10000, 0x1000000, 0x111}. Mode 2 is plain 1.0 gains, mode 1 raises two of them to 1.25 and
  1.1875: these are **colour saturation gains** for the Vivid/Natural display colour setting, not rotation. [code]
  values (2026-11-22); field layout (1.0 = 0x100 at bit 0 of ROT1, bit 8 of ROT2, bit 16 of ROT3; ROT4 = enables)
  [inferred]. Probably what the firmware calls "color rotate" (`display_vscdrv_color_rotate_set`/`_exec` strings exist
  but nothing references them). On the OM-1 the EVF writes non-identity ROT1-4 too (om-emu A14). [code] (om-emu)
- **CRM1-7** (+0x298..+0x2b0): `set_chroma` 0x60044e69 writes a 7-word record once, from `display_vscdrv_initialize`
  0x60042a56; mode 2 fills {0, 0, 0xc03e0, 0xc0000, 0x3f4, 0xc0000, 0} (0x600420c8), other modes zeros. Role open;
  likely an output colour-space or chroma-limit stage. [code] writer / [inferred] role
- **COLMAT** (+0x2ec) and **COLMAT_K12, K34, K56, K78, K9** (+0x2f0..+0x300): nine coefficients, two per word, with
  latched copies. **No block0 code writes them** on the E-M5 III (and om-emu found the same on the OM-1: "COLMAT never
  written on these paths"). So the matrix sits at its reset value, which is unknown (bypass is the obvious guess). It is
  the most direct register for false colour, inverted or red views, if it works. First step: read it on the camera. [code] / [inferred]
- `display_vscdrv_set_knee` has a string but no code and no KNEE register in this family's name table (the OM-1's VSC
  has KNEE1-13): dead driver code shared with the newer body. [code]

## 5. Driver functions (E-M5 III 1.7)

Named from their own debug strings (`[DISP] <DRV> :name`). Full register list per function: the CSV. [code] 2026-11-22

| address | name | registers |
|---|---|---|
| 0x60042a56 / 0x60042ec6 | display_vscdrv_initialize | palettes, CRM1-7, DMA8, INTEN1/2, INTST1, DMA29 |
| 0x600430a7 / 0x60043147 | display_vscdrv_h/v_rsz_osd_custom | OSD RSZ (indexed) |
| 0x60043208 | (helper) | DMA7 |
| 0x6004323d | vscdrv_output_init | TVTFT, DENC, LPF1-6, AREA22-24, HDMI, TFTOUT, DAC, CLK/DATAPATHSEL, ROT1-4 |
| 0x60043748 / 0x601934ef | vscdrv_image_init (/ _without_img3) | IMGPLANE1-4, DMA15-27, AREA1-9, RSZ1/6/12, BC1-2 |
| 0x6004392e | vscdrv_osd_init | OSD1/2/4/7-18, AREA10-18, DMA18-26 |
| 0x60043bd2 | vscdrv_sync_init | SYNC1-12, DMA1-3, CTRL2/3, VMASK1, VSRST1/2, SYNCV1/2, INTST1 |
| 0x60043fee / 0x60044a6f | vscdrv_get_size / display_vscdrv_get_size | (RAM) |
| 0x60044181 | display_vscdrv_extosd_cpdata_set | +0x2e00 |
| 0x600441e9 | display_vscdrv_background_set | BG1 |
| 0x60044226 / 0x600445ba / 0x6004480e | display_vscdrv_fwd_imgaddr / imgsize / extosdaddr_custom | IMG addresses, sizes (indexed), DMA17/23 |
| 0x6004486d / 0x600449c2 | display_vscdrv_h_rsz_img_custom | IMG RSZ (indexed) |
| 0x60044a92 / 0x60044bcb / 0x60044bf9 / 0x60044c41 | sync_sig_mask / d_sig_mask / tftdata_mask / hdmi_data_mask | TFTOUT2/3, SYNC7 |
| 0x60044c8c / 0x601943ec | display_vscdrv_ext_osd_enable / disable | DMA3 |
| 0x60044cf2 | display_vscdrv_get_blink_field | (computes BC fields) |
| 0x60044d23 / 0x60044da6 | display_vscdrv_set_img_blink / set_osd_blink | BC1-2 / OSD10-12 |
| 0x60044e69 | display_vscdrv_set_chroma | CRM1-7 |
| 0x60193788 | display_vscdrv_layeroff | IMGPLANE1-3 |
| 0x6019385f | display_vscdrv_finalize | GAM1, ROT1-3, CTRL2 |
| 0x60193afe / 0x60193b3f / 0x60193b75 / 0x60194889 | gamma_select / gamma_read_switch / gamma_data_set / get_gamma_table | GAM1 / GAM2 / +0x2000 / GAM1 |
| 0x60193c0d / 0x60193d8a | display_vscdrv_fwd_osdaddr / osdsize_custom | OSD addresses, sizes (indexed) |
| 0x60193f6f, 0x60194425, 0x6019445a, 0x601944a1, 0x601944e0, 0x6019450a | hist_prm_set, hist_targetelement_set, hist_calc_enable/disable, hist_clear_intr_status, hist_get_calc_result | HIST1-3, AREA19-21, INTEN1, INTST1, +0x2c00 |
| 0x60194208 | display_vscdrv_dac_out_mask | DAC |
| 0x60194241 | display_vscdrv_test_pattern | DMA7, TEST1 |
| 0x6019458a | display_vscdrv_osd_mixorder | OSD1 |
| 0x60194600 / 0x60194665 / 0x6019484b | set_hi_sh_blink / set_hi_sh / exec_hi_sh | BC3 / AREA28-30, HILIGHT1-4 / HILIGHT1 |
| 0x601948b0 / 0x601949dd | display_vscdrv_set_imgformat / get_imgformat | IMGPLANE1-3, DMA1-3 |
| 0x60194993 | display_vscdrv_set_rot | ROT1-4 |
| 0x60194a64 / 0x60194be8 / 0x60194c1c | get_img1/2/3_dmatransfer_addr | DMA9-11 and _VL |
| 0x60194e50 / 0x60194f25 | update_set_through_addr / update_set_face_addr | DMA9/10 / DMA11 |
| 0x60194fa0, 0x601950c0, 0x6019511b, 0x6019519b | get_vdline, get_vdline_reg, get_hdline, set_hdline | MONI3, SYNC2/6/8/12 and _VL |
| 0x60195629 | display_vscdrv_ctrl_dma | DMA7 |
| 0x60195bf0, 0x60195e45, 0x60195ecd, 0x60196078, 0x60196869 | set_peak_area/ctrl, set_peak_color_palette, set_peaking_edge_detect, set_peaking_thresh, exe_peaking | PEAK1-14, AREA25-27 |

Strings with no code reference (dead in this body): color_rotate_set/exec, set_knee, get_dmatransfer_addr,
get_img3_addr, get_img/osd_active_area_offset, dmaerr_clear_intr_status. [code]

## 6. The `disp` console commands that touch the VSC

The user shell's `disp` command (table 0x60253784: {name, handler} pairs) has these VSC-related sub-commands. [code] 2026-11-22

| command | handler | what it does |
|---|---|---|
| `disp vsc r` | 0x60188867 | prints every named register (both channels when both are active) by walking the name table; `r 1`/`r 2` snapshot, `r 3` compares the snapshots; also `check`, `info` (plane enables, sync), `clk`, `set_th_time`, `get_th_line` |
| `disp dump` | 0x60189a66 | writes to the card: `OSD%d.RAW` (OSD planes), `VSC_REG.bin` (channel 0, +0x000..+0x3ff only: no _VL, no channel 1), `GMA_TBL.bin` (+0x2000..+0x2bff, with GAM2 = 1 during the read), `VSC_OSD.bin` (palettes) |
| `disp hish get` / `disp hish exe tft\|bievf ...` | 0x601870f4 | `get` prints the hi/sh fields (HILIGHT1, AREA28-30, BC3 and their _VL); `exe` posts hi/sh requests through the normal display request path (0x600548f7; arguments not decoded) |
| `disp pkg` | 0x6018989e | peaking test: writes PEAK1-14 and AREA25-27 (`tl <level>`, `on`, `off`) |
| `disp bg X Y Z` | 0x60186c60 | sets BG1 |
| `disp test N` | 0x6018847c | test pattern: 0 off, 1 colour bar, 2 7 steps |
| `disp histogram`, `disp hst` | 0x601870ee | **empty stub** (`retf`) in this build, although the help text offers `show` / `set PRM VAL` |
| `disp es` (`upds`, `updi`, `updo`, `setcp`, `setlc`) | 0x60189d2b | loads test pictures from the card (`C:\test.raw`, `C:\osd.raw`, ...) into planes |

- `disp vsc r` reads INTST1, INTST2 and SRAM1/2 too. Older notes say reading them has side effects; Olympus's own debug
  command does it anyway, but it is the one risk of a read-only dump. `disp dump` avoids INTST2/SRAM (it reads only up to
  +0x3ff, which still includes INTST1). [code] / [inferred] risk
- No `disp` sub-command writes an arbitrary VSC register (`wm`, `lut`, `histogram`/`hst` and `hd` are empty stubs: 0x60184327, 0x6018432a, 0x601870ee, 0x601870f1). A
  register poke needs a memory-write command (the system shell's `mem_put*`, untested, see
  [Wi-Fi debug shell](../features/wifi-debug-shell.md)) or a build. [code]

## 7. Other bodies and om-emu

- **Identical register table** (422 names, same offsets): OM-5 1.2, E-M1 III 1.6, OM-5 II 1.1. Their driver debug
  strings are not in the images we read (compressed or stripped), so function addresses must be found by pattern. The
  dump file names (`VSC_REG.bin`, `GMA_TBL.bin`) and the format names are present in all of them. [code] 2026-11-22
- **OM-1 1.9 / OM-1 II 1.3**: a different, larger VSC (503 names): per-plane DMASETn blocks, IMGnFMT, own HIST/PEAK/
  HILIGHT/COLMAT at new offsets, plus **ZEBRA1_1-7/ZEBRA2_1-7, KNEE1-13, YGAIN, RGBCNV, CMM (colour management, 64 knee
  points), NVEN and NV11..NV23 (night vision)** and YCEXT. So the OM-1's red night-vision view is a dedicated block; the
  E-M5 III family has to do it with gamma. [code] (name table) + [inferred] (NV = night vision)
- **PEN-F / E-M5 II**: no name table found; om-emu's "kind 3" (offsets as kind 2, two channels of 0x2000). [code] (om-emu)
- **om-emu** models kind 2 as register storage with latches, composes OSD planes (and IMG planes with our patch),
  BG1, plane levels and OSD order. It does not apply gamma, COLMAT, ROT, CRM, hi/sh, peaking or the histogram to the
  picture. So none of the view assists can be checked for looks in om-emu, but the register writes themselves can be
  logged there. [code] (om-emu)

## 8. What this means for view assists [inferred] 2026-11-22

| assist | registers | how | open |
|---|---|---|---|
| Red night view (EVF) | gamma c1, c2 (+0x2400/+0x2800 banks), GAM1 | write zeros to G and B tables in the hidden bank, identity to R, flip GAM1; stays until the next gamma request | **works on the camera** on both screens as a card mod: c0 = R, and gamma applies on the rear screen too (section 10); tints menus too |
| Red night view (any screen) | COLMAT | Y-only matrix into R | reset value, whether COLMAT is active at all |
| Two-level zebras | HILIGHT1-4, AREA28-30, BC3 | set_hi_sh with chosen thresholds and colours; exec_hi_sh | stripes or flat fill (colours are YCbCr, 4.4). the camera rewrites these all the time, so zebras need a hook at set_hi_sh/exec_hi_sh (section 10) |
| RGB clipping view | gamma (3 LUTs) | each channel dimmed to 50 %, values >= 250 at full | **works on the camera** as a card mod (section 10); tints menus too |
| Peaking colours | PEAK4/5 | any YCbCr word instead of the four stock ones | threshold and probably colour rewritten each update (4.5): needs a hook at 0x60195e45 |
| False colour | gamma (3 LUTs) or COLMAT | stepped LUTs per channel give a crude false colour on luminance only if the matrix can feed Y to all three | needs COLMAT |
| Mirror / desqueeze | RSZ, AREA, DMA stride | desqueeze = IMG1 horizontal scale (RSZ1-5); mirror has no known register (the swivel command talks to the panel) | RSZ field layout for IMG1 |
| Brightness boost | gamma, BG1 | curve | none |

## 9. Unknowns and proposed cheap camera tests

None of these has been run. Each is read-only or undoes itself at power-off.

1. **VSC read in live view** (read-only): Wi-Fi shell, `disp vsc r` on the TFT, then on the EVF, then with peaking on,
   hi/sh warning on, EVF colour temperature at −3 and +3. Answers: COLMAT reset value, live IMGPLANE1/DMA1 values, HIST2
   field use, PEAK and HILIGHT values per setting, GAM1 per device. Then `disp dump` for `GMA_TBL.bin` (EVF) to confirm
   c0/c1/c2 = R/G/B against the tables at 0x601f6df8... Risk: the read touches INTST1/INTST2/SRAM (section 6).
2. **Peaking colour/kernel check** (writes, undone by `disp pkg off` or power-off): `disp pkg on` / `tl N` and watch
   what changes.
3. **Hi/sh as zebra**: in the stock menu, set the highlight/shadow warning thresholds and look at the screen
   (stripes or flat colour), then `disp hish get` to read the fields. No writes.
4. **COLMAT and gamma pokes** need a memory write: only after test 1, and only through a reviewed build or the
   system shell's `mem_put4` once it is checked, never blind.

Still unknown from code: the field layout inside RSZ, CRM, ROT and COLMAT; what LPF1-6 filter; the meaning of DMA22,
DMA27-29; whether gamma acts on the TFT path.

## 10. What our display card mods showed on the camera (2026-11-22)

We built small card mods (loaded by our mod loader, nothing flashed) that write these registers, and ran them on one
E-M5 III. What they showed:

- **Red night view works.** Zeroing the G and B gamma tables turns the picture red, so gamma table c0 is red, and the
  gamma block acts on the rear screen as well as the EVF. [camera]
- **RGB clipping view works:** per-channel gamma curves show clipped channels in their own colour. [camera]
- **Gamma acts on everything shown**, menus and info included, so a curve-based view also tints the menus. A view
  that leaves the menus alone needs its own overlay made from the live frame. [camera]
- **The camera rewrites the highlight/shadow (zebra) registers constantly** (HILIGHT1-4, AREA28-30), even when its own
  Highlight & Shadow view is off. A mod that polls and rewrites them only fights the camera; zebras need a hook where
  the driver sets them (set_hi_sh / exec_hi_sh). [camera]
- **A register change needs an update request.** Every stock change ends with a call to 0x601939ec (d0 = device
  bits), which sets INTST1 = 1 and INTEN1 bit 0; the next frame interrupt (0x60193a4b) applies the change and sets the
  waiters' event flag. A write without the request appears only at the camera's next own update (for example when
  you move in a menu). [camera]+[code]
- **A request made during start-up can be lost** while live view comes up, so a mod that applies at power-on should
  repeat it for a while. [camera]+[inferred]
- **Two mods that both swap the gamma bank must coordinate**, or one saves the other's curves as the camera's and
  leaves the screen darker after Off. [inferred]
- om-emu stores and logs VSC register writes but does not draw gamma or zebras, so the look of a view assist can only
  be judged on the camera; om-emu also faults on reads of unnamed VSC offsets, so probes should read named registers
  only. [emu]
