# Graphics pipeline (GUI, OSD engine, VSC, live view)

This page follows a pixel from the camera's software to the rear screen or EVF. In short: the GUI (menus, icons,
shooting info) is drawn into OSD buffers by a small hardware 2D engine, and the display controller (VSC) lays those
buffers over the live-view picture and sends the result to the panel. Register-level detail, the display's built-in
features (histogram, highlight warning, peaking) and the live-view frame pointer are on [Display and OSD](display.md);
this page is the overview.

Terms used here:

- **GUI**: the part of the main program that draws menus and the shooting screen.
- **OSD** ("on-screen display"): the layers the GUI draws into, shown on top of the picture.
- **VSC**: the display controller that mixes layers and drives the TFT (rear screen), EVF and HDMI.
- **Live view (LV)**: the moving picture from the sensor before a shot.
- **om-emu**: a third-party emulator that runs the E-M5 III GUI. We use facts from it only, never its code. "E144"
  marks OM-5 facts that om-emu applies to the E-M5 III through its port; "E137" is the E-M5 III.

Tags: **[code]** read in the firmware, **[camera]** seen on a real E-M5 III, **[inferred]** not traced or tested.
om-emu facts are tagged [code] (om-emu). Started 2026-11-05. Evidence:, VSC register names.

## The whole path

The diagram reads top to bottom: the live picture on the left branch, the GUI on the right, both meeting in the VSC.

```
 sensor ──> image engine (ISP: demosaic, picture mode, gamma, resize)           [inferred]
              │  YC 4:2:x frame, display-size pools 0x0a00/0x0e00/0x0f00 (1920x1080 slots)
              v
 display_update_through_image 0x601907cb
   └─ set_through_addr 0x60194e50 ──> VSC DMA9 (Y, +0x38) / DMA10 (C, +0x3c) = plane IMG1
        └─ copy of Y addr kept in RAM 0xa26538c4 + ch*0xe28   <── "current LV frame" pointer

 GUI app (section 6)                 osddraw 0x60c1xxxx
   widgets / gpiDraw* ──> request ──> command list ──> OSD DRAW ENGINE 0x9c100000 (FILL/COPY/BITMAP/LUT)
                                                          │ writes 8-bit palette pixels
                                                          v
                         OSD buffers, pools 0x0b00/0x0c00/0x0d00 (4 x 896x600 each)
                                                          │ gpiUpdateDisplay -> display task commit
                                                          v
 VSC channel 0 (TFT or EVF) / channel 1 (HDMI), regs 0x9c000000 + ch*0x4000
   IMG1 (live view) ─┐
   IMG2, IMG3       ─┼─ scale (RSZ) ─ mix over BG1 ─ hist / hi-sh / peaking ─ panel timing ─> TFT / EVF / HDMI
   OSD1..3 + palette┘   (OSD on top of IMG; OSD1 bottom, OSD3 top)
```

## 1. GUI drawing goes through a hardware OSD engine

The GUI never sets pixels one by one. It builds a list of drawing commands and hands it to a 2D engine.

- **Correction (2026-11-05):** the GUI does not rasterise in software. `osddraw` builds command lists and kicks a 2D
  draw engine at **0x9c100000**: command-list base +0x18 (E137 emulator run: list at 0xaf8c2840), status W1C +0x04,
  start +0x24 (1 = run list), sync trigger mask +0x30, enable +0x08 (kick 0x60c1dc85..0x60c1dcfd; 39 register stores in 0x60c1daed..0x60c1e6da). [code] (2026-11-05)
- Engine commands (E144 family): 0x10 FILL, 0x20 COPY, 0x30 BITMAP (packed glyphs/icons, optional LUT, scaling),
  0x40/0x41 LUT, 0x60 BITMAP2, 0xFF END; 8-bit pixels; FIFO mode via +0x28; raises an IRQ when done.
  [code] (om-emu, E144) (2026-11-05)
- No line opcode exists in that set, so `osddraw_exec_line` lines are drawn as 1-pixel FILLs or runs; diagonal lines
  are likely costly. [inferred] (2026-11-05)
- **om-emu run on E-M5 III (2026-11-06):** the engine executed ~2,600 commands from start-up to the menu, zero errors.
  A menu page redraw is ~125 BITMAP (glyphs/icons) + ~13 COPY (buffer sync) + 1 FILL. The INFO histogram is a 266×50 box
  drawn as 266×1 / 1×50 FILLs plus one 3- or 4-px-wide FILL per bin (128 columns), so lines really are thin FILLs.
  Every command used stride 896. [code] (om-emu run)
- `osddraw_exec_line` 0x60c1f13e queues a 108-byte request with **stride 896** (0x60c1f1e0). Primitives dot/line/rect/
  bitmap/font/copy and the `OSDControl::*` and `gpiDrawOsd*` wrappers are listed on [Display and OSD](display.md). [code]
  (2026-11-05)

## 2. OSD buffers and palettes

The engine draws into three layers of 8-bit pixels. Each pixel is a colour number looked up in a palette, and one
number means "transparent" so the live picture shows through.

- Three GUI layers = pools **0x0b00/0x0c00/0x0d00**, four 0x83400-byte buffers each. 0x83400 = **896 × 600 bytes at
  8 bpp**; om-emu reads the same layout for E137 and a GUI screen of 800 × 1200 that spans two buffers (front/back
  pairs synced by COPY). [code] + [code] (om-emu) (2026-11-05)
- Pixels are 7-bit palette indices; **index 127 is transparent** (live view shows through). Each OSD plane has a
  128-entry palette in VSC space (+0x800 + 0x800×plane, double-buffered, bank flipped at commit); entries are
  `alpha(0..31)<<24 | Cr<<16 | Cb<<8 | Y`, converted from the GUI's RGB by BT.601. [code] (om-emu, E144 family)
  (2026-11-05)
- Stacking: VSC OSD1 (+0x1a4) = 3 on the E-M5 III family, so GUI layer 0 is the bottom plane and layer 2 the top.
  [code] (om-emu) (2026-11-05)
- EVF: the GUI draws a 640 × 480 canvas that the VSC scales to the 1024 × 768 panel area (RSZ18/24/30 0x11, step
  0x9fc). [code] (om-emu run on E137) (2026-11-05)
- **Register dump at the shooting screen (om-emu, E-M5 III, 2026-11-06):** [code] (om-emu run)

  | register | TFT | EVF | meaning |
  |---|---|---|---|
  | AREA22/23/24 (+0xf8/+0xfc/+0x100) | 0x1e02d0 / 0x80008 / 0x1e0 | 0x300400 / 0x260026 / 0x300 | video area: TFT 720×480 at (30, 8); EVF 1024×768 at (48, 38) |
  | DMA12/13/14 (+0x44/+0x48/+0x4c) | 0xafef9800 / 0xafcec800 / 0xafadf800 | same | OSD1/2/3 buffer = pools 0x0b00/0x0c00/0x0d00; flips by 0x106800 (two records) to 0xafdf3000/0xafbe6000/0xaf9d9000 |
  | DMA18/19/20 (+0x5c..+0x64) | 0xe | 0xe | OSD stride 14×64 = 896 B |
  | DMA7 (+0x30) | 0x7 | 0x7 | only OSD1-3 enabled (no live view in the emulator) |
  | RSZ18/24/30 | 0 (1:1) | 0x11, step 0x9fc | OSD scaling: none on the TFT, 640→1024 on the EVF |
  | OSD7-9 (+0x2e0..) | 0x100 (100 %) | 0xcc (80 %) | OSD plane level |
  | SYNC2 / SYNC8 | 0x1ef (495 lines) | SYNC8 0x339 (825 lines) | vertical totals |
  | OSD1 / OSD4 / BG1 | 3 / 0x111111 / 0x80800b | same | stacking / mix / black background |
  | 0xa2653720 (RAM) | 1 | 2 | active display mask: bit 0 TFT, bit 1 EVF |

- So on the TFT the OSD is shown 1:1: the GUI's 896-wide buffer is cropped to a 720×480 window. [code] (om-emu run)
  (2026-11-06)

## 3. Display controller (VSC)
- **Channel 0 serves the TFT and the EVF** (one at a time), channel 1 serves HDMI: selector 0x6004404f maps device
  mask bit 0/1 → ch 0 and bits 0xff000004 → ch 1. Corrects "one channel each for TFT/EVF/HDMI". [code] (2026-11-05)
- Six planes per channel: IMG1..IMG3 (YC images; IMG1 = live view) and OSD1..OSD3; enable bits in DMA7 (+0x30).
  Registers have latched copies at +0x400 (`*_VL`) that take effect at the frame boundary; INTST1 bit 0 = frame IRQ.
- Histogram (HIST1-3), highlight/shadow (HILIGHT1-4), peaking (PEAK1-14), colour matrix (COLMAT), gamma (GAM), rotation
  (ROT) and resize (RSZ) are VSC blocks, so they act on the displayed YC image, not on raw. [code] (2026-11-05)
- Background BG1 = 0x80800b (black in YCbCr); plane level OSD7-9 = 2×floor(p×128/100). [code] (om-emu) (2026-11-05)

## 4. When the screen updates
- `gpiUpdateDisplay` 0x60c9588b asks the display task to commit the dirty OSD buffers (new plane addresses, palette
  bank). The E-M5 III GUI turns display sync on at start (`guiUtility::setDispSync`), so OSD commits are held until
  the next image (live-view) sync for that device. [code] (om-emu, E137) (2026-11-05)
- So overlays drawn by us appear with the next LV frame, and a GUI redraw can overwrite them; draw after the GUI's
  update, from task context. [inferred] (2026-11-05)

## 5. Live-view frames
- The LV picture is never copied by the CPU: the ISP writes a YC frame and the driver points VSC IMG1 at it each
  frame (0x60194e50). The CPU-readable pointer is RAM **0xa26538c4 + ch×0xe28** (C plane next word). [code]
  (2026-11-05); geometry/stride to be measured by the LV1 probe (test queue).

## 6. om-emu and the display
- om-emu models VSC kind 2 (registers, latches, OSD planes, palettes, scaling, stacking) and the OSD engine, and runs
  the GUI, osddraw and display task natively; its output is the composed frame (our `emurun.mjs` saves it).
  [code] (om-emu) (2026-11-05)
- It does **not** model IMG planes on E-M5 III (live view is skipped), the histogram, hi/sh or peaking. Live view
  is only driven on OM-1. [code] (om-emu) (2026-11-05)
- Use: an `osddraw` overlay (frame lines, markers) can be smoke-tested in om-emu before a camera run; anything that
  reads LV pixels cannot. [inferred] (2026-11-05)

## Open questions
- Engine register map beyond +0x04..+0x50 on E-M5 III, and how `osddraw` turns a diagonal line into commands. [inferred] open
- Answered 2026-11-06: the TFT panel area and OSD scaling on the rear screen (720×480, no scaling; table above). [code]
- Which pool holds the LV through-image in each mode, and its stride/format (LV1 probe answers this).
- Done 2026-11-06: a VSC/engine register dump in om-emu (the maintainer OK'd running it); IMG-plane (live view) registers stay
  unknown until the LV1 camera run, since om-emu has no live view on E-M5 III. [code]
