# Display, OSD overlays and live-view frames

This page is about the screen side of the camera: how the E-M5 III draws its menus and icons over the live picture,
where the built-in histogram, highlight/shadow warning and focus peaking come from, and where our own code can find the
current live-view frame. For the big picture, with a diagram, start with [Graphics pipeline](graphics-pipeline.md);
this page has the register-level detail.

Terms used here:

- **VSC** is the display controller, the hardware that combines picture and menus and sends them to the screens.
- **OSD** ("on-screen display") means the menu and icon layers drawn on top of the picture.
- **Live view (LV)** is the moving picture from the sensor that you see before taking a shot. The firmware calls it the
  "through image".
- **Y and C planes**: the live-view frame is stored as brightness (Y) and colour (C) in two separate planes.

Tags: **[code]** read in the firmware, **[camera]** seen on a real E-M5 III, **[inferred]** not traced or tested.
Started 2026-11-05.

## Display controller (VSC)

The display driver is in section 1 (always loaded early). Its request switch is 0x6017f904 (`DISP_*` requests), with
`display_update` 0x6018fe32 and `display_update_through_image` 0x601907cb. [code] (2026-11-05)

The VSC registers are at **0x9c000000**, with **0x4000 bytes per channel**. There are two channels: **ch 0 = the rear
screen (TFT) or the EVF**, **ch 1 = HDMI** (selector 0x6004404f). We first thought there was one channel each for TFT,
EVF and HDMI; corrected 2026-11-05. [code] (2026-11-05)

**Where the live-view image is.** `display_vscdrv_update_set_through_addr` **0x60194e50** writes the Y plane's address
to **0x9c000038 + ch×0x4000** (and the C plane to +0x3c for two-plane YC). Its caller then stores the Y address in RAM at
**0xa26538c4 + ch×0xe28**, with the C address in the next word. That RAM word is the simplest "current LV frame"
pointer. [code] (2026-11-05); not yet read on the camera.

**The histogram is display hardware.** It is computed on the displayed image, after picture mode and gamma: functions
`hist_prm_set` 0x60193f6f and `hist_get_calc_result` 0x6019450a, event `DISP_HISTOGRAM_CALC_END`. [code] (2026-11-05)

**The highlight/shadow warning is display hardware too.** `display_vscdrv_set_hi_sh` 0x60194665 sets it. By the
firmware's own register-name table its threshold registers are **HILIGHT1-4 = VSC +0x250..+0x25c**. (An earlier note said
"+0x320/+0x324"; that was wrong, those are AREA28/29.) Exactly which fields set_hi_sh fills isn't traced. Edge peaking
([EGPK]) is also a VSC function. [code] names / [inferred] writer (2026-11-05, corrected same day)

**Register names.** The firmware carries a 422-entry table of VSC register names at 0x60253888, copied to RAM
0x61e8edc8 at boot (`boot_copy_callback_tables`); the word index ×4 is the byte offset. [code] (2026-11-05) Useful
ones:

- DMA7 +0x30 (control), DMA9 +0x38 (Y address), DMA10 +0x3c (C address) [code]
- HIST1-3 +0x244..+0x24c, HILIGHT1-4 +0x250..+0x25c, AREA28-30 +0x320..+0x328 [code]
- Don't read INTST1 (index 5), INTST2 (0xf1) or SRAM1/2 (0xeb/0xec): reading them has side effects. [code]

**Which displays are active:** word 0xa2653720 (returned by 0x60041cab). The native register dump reads channel 0 when
mask & 3 and channel 1 when mask & 0xff000004. [code] (2026-11-05)

## OSD (the GUI layers)

The GUI doesn't draw pixels itself. `osddraw` drives a **hardware OSD draw engine at 0x9c100000** (command lists of
FILL, COPY, BITMAP and LUT) that writes into **OSD VRAM** in DRAM; the GUI then asks for a display update. (We first
thought the GUI app in section 6 drew in software; corrected 2026-11-05.) Overview: [Graphics pipeline](graphics-pipeline.md).
[code] (2026-11-05)

**The layers.** The OSD planes come from frame pools **0x0b00 / 0x0c00 / 0x0d00** (layers 1-3), each 4 × 0x83400 bytes
at 0xafdf3000 / 0xafbe6000 / 0xaf9d9000. Each buffer is 896 × 600 at 8 bits per pixel (stride 896); the GUI screen of
800 × 1200 spans two buffers (corrected 2026-11-05). Layers 1-2 use a 128-colour palette, and there is an RGB work layer
(3). [code] (2026-11-05)

**Drawing functions** (`osddraw`, one request-struct pointer in a0): init 0x60c1ede6, exec_start 0x60c20032, VRAM info
0x60c1f01d(layer), **dot 0x60c1f04c, line 0x60c1f13e, rect 0x60c1f252, bitmap 0x60c1f466, font 0x60c1fb0a, copyFrame
0x60c1fd5a, copyAreaBlock 0x60c1feb5**. [code] (2026-11-05)

**Wrappers around them:** [code] (2026-11-05)

- `OSDControl::*` (SDK API): initOsdControl 0x607f4dfd, drawLine 0x607f5544, drawRect 0x607f5617, drawBitmap
  0x607f544a, getVramInfo 0x607f5796. [code]
- GUI: `gpiDrawOsdLine` 0x60c951f0, `gpiDrawOsdRectangle` 0x60c952fb, `gpiUpdateDisplay` 0x60c9588b; `GPIInitPlatform`
  0x60c93eee sets the GUI up. [code]

Most GUI widgets use a graphics-context library at ~0x60c80000-0x60c93000. For example
`guiDrawHistogram::draw_Histogram_Parts` 0x60e1ae5b plots the hardware histogram as a polyline (0x60c8ebd9). [code]
(2026-11-05)

The level gauge gets its data from `LevelCtrl::getSlope` → `OlyHfwOpeLevel::getSlope` 0x60860b34
(`Get_Slope_Roll_Pitch`). The routine that draws the gauge isn't pinned yet. [code] / [inferred] (2026-11-05)

The `disp` debug console command can already dump the OSD planes and VSC registers to the card (`OSD%d.RAW`,
`VSC_REG.bin`) and load test images (`C:\test.raw`). [code] (2026-11-05)

## Other frames the CPU can read

- The face-detect input pool **0x2c00**: 11 × 640×480 4:2:0 frames (0x70800 bytes) at 0xddf7b000; `face_dbg_*` loads
  `C:\BD_VGA.RAW` into it as a test input. [code]; that it carries live-view VGA frames in normal use is [inferred]
  (2026-11-05)
- Display-size pools 0x0a00 (5), 0x0e00 (2) and 0x0f00 (3), each 1920×1080×2 bytes. Which one normal live view uses
  isn't traced, so use the 0xa26538c4 pointer rather than guessing a pool. [code] (2026-11-05)

## What this means for features

- **Frame lines, trap-focus or motion markers:** draw with `osddraw` line/rect into a GUI layer, from task context
  (never from an interrupt), after the GUI's own redraw so it doesn't wipe them. [inferred] (2026-11-05)
- **Cheap "JPEG zebras":** retune the hardware highlight/shadow thresholds (HILIGHT1-4). True raw zebras or a raw
  histogram still need raw sampling (the E3c decoder). [inferred] (2026-11-05)
- **Motion or lightning trigger:** compare a sparse grid of Y values in the current LV frame, frame by frame.
  [inferred] (2026-11-05)

## The LV1 and LV1b probe builds

To answer stride, format, whether the CPU can read the frame, and how much each frame costs, we built a probe:

- Build `OLY_E_137_1700_LV1_LIVEVIEW_PROBE.BIN` (`f93ff17e…`, stock base) logs every LV frame's Y/C address, the active
  device and a 32×32 Y diff from the display update (hook 0x60190ab1). At each armed silent single shot it dumps the
  named VSC registers, 8 pool objects and 2 MB of the current Y plane to `LVPnn*.BIN`. It uses the native card API from
  task context: fopen 0x60631f63, fwrite 0x60631fe8, fclose 0x60631f6c.
  [code] (2026-11-05)
- **LV1 camera run 1:** the camera reset about 1 s after the arming shot, in live view, without pressing the shutter.
  The only thing that changes after arming is hook R's armed path (32×32 uncached Y sampling plus tick and context calls
  inside `display_update_through_image`), so reading frame pixels from the display-update path is the prime suspect.
  Rule until disproved: no frame reads or calls in that hook. LV1b (`b469a43b…`) keeps the hook a pure copy and does all
  frame reading at the silent single, writing the log first. [camera] / [inferred] cause (2026-11-05)
