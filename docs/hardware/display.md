# Display, OSD overlays and live-view frames

How the E-M5 III draws its GUI over live view (overview and diagram: [Graphics pipeline](graphics-pipeline.md)), where the native histogram / highlight-shadow / peaking come from, and
where the CPU can read the current live-view frame. Started 2026-11-05.

## Display controller (VSC)
- The display driver is in section 1 (always loaded early): request switch 0x6017f904 (`DISP_*`), `display_update`
  0x6018fe32, `display_update_through_image` 0x601907cb. [code] (2026-11-05)
- VSC registers at **0x9c000000**, stride **0x4000 per channel**. ~~(TFT / EVF / HDMI)~~ Corrected 2026-11-05: two channels, **ch 0 = TFT or EVF, ch 1 = HDMI** (selector 0x6004404f). [code] (2026-11-05)
- **Live-view (through) image address:** `display_vscdrv_update_set_through_addr` **0x60194e50** writes the Y plane to
  **0x9c000038 + ch×0x4000** (C plane +0x3c for two-plane YC). The caller then stores the Y address in RAM at
  **0xa26538c4 + ch×0xe28** (C address in the next word). That word is the simplest "current LV frame" pointer. [code]
  (2026-11-05); not yet read on the camera.
- **Histogram is display hardware**, computed on the displayed image (post picture mode and gamma):
  `hist_prm_set` 0x60193f6f, `hist_get_calc_result` 0x6019450a, event `DISP_HISTOGRAM_CALC_END`. [code] (2026-11-05)
- **Highlight/shadow warning is display hardware:** `display_vscdrv_set_hi_sh` 0x60194665 sets it. Its threshold registers are
  **HILIGHT1-4 = VSC +0x250..+0x25c** by the firmware's own register-name table; the earlier note "+0x320/+0x324" was wrong
  (those are AREA28/29). Exactly which fields set_hi_sh fills isn't traced. Edge peaking ([EGPK]) is also a VSC function.
  [code] names / [inferred] writer (2026-11-05, corrected same day)
- **VSC register names:** 422-entry name table in the image at 0x60253888, copied to RAM 0x61e8edc8 at boot
  (`boot_copy_callback_tables`); the word index ×4 is the byte offset. Useful ones: DMA7 +0x30 (control), DMA9 +0x38 (Y
  address), DMA10 +0x3c (C address), HIST1-3 +0x244..+0x24c, HILIGHT1-4 +0x250..+0x25c, AREA28-30 +0x320..+0x328. Don't
  read INTST1 (index 5), INTST2 (0xf1) or SRAM1/2 (0xeb/0xec): side effects. [code] (2026-11-05)
- **Active display devices:** word 0xa2653720 (returned by 0x60041cab); the native register dump reads channel 0 when
  mask & 3 and channel 1 when mask & 0xff000004. [code] (2026-11-05)

## OSD (GUI layers)
- ~~The GUI app (section 6) rasterises in software into **OSD VRAM** in DRAM~~ Corrected 2026-11-05: `osddraw` drives a **hardware OSD draw engine at 0x9c100000** (command lists: FILL/COPY/BITMAP/LUT) that writes **OSD VRAM** in DRAM; then the GUI requests a display update. Overview: [Graphics pipeline](graphics-pipeline.md). [code] (2026-11-05)
- OSD planes come from frame pools **0x0b00 / 0x0c00 / 0x0d00** (layers 1-3), 4 × 0x83400 B each at 0xafdf3000 /
  0xafbe6000 / 0xaf9d9000; each buffer 896 × 600 at 8 bpp (stride 896; GUI screen 800 × 1200 spans two buffers, corrected 2026-11-05), 128-colour palette layers plus an RGB work layer (3). [code] (2026-11-05)
- Draw primitives (`osddraw`, one request-struct pointer in a0): init 0x60c1ede6, exec_start 0x60c20032, VRAM info
  0x60c1f01d(layer), **dot 0x60c1f04c, line 0x60c1f13e, rect 0x60c1f252, bitmap 0x60c1f466, font 0x60c1fb0a,
  copyFrame 0x60c1fd5a, copyAreaBlock 0x60c1feb5**. [code] (2026-11-05)
- Wrappers: `OSDControl::*` (SDK API) initOsdControl 0x607f4dfd, drawLine 0x607f5544, drawRect 0x607f5617,
  drawBitmap 0x607f544a, getVramInfo 0x607f5796; GUI `gpiDrawOsdLine` 0x60c951f0, `gpiDrawOsdRectangle` 0x60c952fb,
  `gpiUpdateDisplay` 0x60c9588b; `GPIInitPlatform` 0x60c93eee sets the GUI up. [code] (2026-11-05)
- Most GUI widgets use a graphics-context library at ~0x60c80000-0x60c93000; e.g. `guiDrawHistogram::draw_Histogram_Parts`
  0x60e1ae5b plots the hardware histogram as a polyline (0x60c8ebd9). [code] (2026-11-05)
- Level gauge data: `LevelCtrl::getSlope` → `OlyHfwOpeLevel::getSlope` 0x60860b34 (`Get_Slope_Roll_Pitch`). The GUI
  routine that draws the gauge isn't pinned yet. [code] / [inferred] (2026-11-05)
- The `disp` debug console can already dump OSD planes and VSC registers to the card (`OSD%d.RAW`, `VSC_REG.bin`) and
  load test images (`C:\test.raw`). [code] (2026-11-05)

## Other CPU-readable frames
- Face-detect input pool **0x2c00**: 11 × 640×480 4:2:0 (0x70800 B) at 0xddf7b000; `face_dbg_*` loads `C:\BD_VGA.RAW`
  into it as test input. [code]; that it carries live-view VGA frames in normal use is [inferred] (2026-11-05)
- Display-size pools 0x0a00 (5), 0x0e00 (2), 0x0f00 (3), each 1920×1080×2 B. Which one the normal LV display uses isn't
  traced; use the 0xa26538c4 pointer rather than a pool guess. [code] (2026-11-05)

## What it means for features
- Frame lines, trap-focus or motion markers: `osddraw` line/rect into a GUI layer from task context (never an ISR),
  after the GUI's own redraw so it isn't wiped. [inferred] (2026-11-05)
- Cheap "JPEG zebras": retune the hardware hi/sh thresholds (HILIGHT1-4). True raw zebras/histogram still need raw sampling
  (E3c decoder). [inferred] (2026-11-05)
- Motion / lightning trigger: diff a sparse Y grid of the current LV frame per frame. [inferred] (2026-11-05)

## LV1 / LV1b probes
- Build `OLY_E_137_1700_LV1_LIVEVIEW_PROBE.BIN` (`f93ff17e…`, stock base) logs every LV frame's Y/C address, device and a
  32×32 Y diff from the display update (hook 0x60190ab1), and at each armed silent single dumps the named VSC registers,
  8 pool objects and 2 MB of the current Y plane to `LVPnn*.BIN`. Native card API used from task context: fopen 0x60631f63,
  fwrite 0x60631fe8, fclose 0x60631f6c. Answers stride/format, CPU readability and per-frame cost.
  [code] (2026-11-05)
- **LV1 camera run 1:** reset about 1 s after the arming shot, in live view with no shutter press. Only hook R's armed path
  (32×32 uncached Y sampling + tick/context calls inside `display_update_through_image`) differs after arming, so
  reading frame pixels from the display-update path is the prime suspect. Rule until disproved: no frame reads or calls
  in that hook. LV1b (`b469a43b…`) keeps it a pure copy and does all frame reading at the silent single, log first.
  [camera] / [inferred] cause (2026-11-05)

