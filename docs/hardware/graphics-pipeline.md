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
  (2026-11-05); geometry/stride to be measured by the live-view probe.

## 5b. The second drawing engine: c3d and OpenVG (2026-11-20)

Besides the 2D OSD engine, the camera has a vector-graphics GPU used by the `c3d` task for the colour wheels (Color
Creator, and the Color/Mono Profile editors we added). How the GUI starts it and how its layer reaches the screen is on
[profile editor](../features/pen-f-profiles.md#on-camera-editor).

- Block0 carries an **OpenVG 1.x** library with **EGL**, from DMP: 95 `vg*` names (vgCreatePath, vgDrawPath, vgCreateImage,
  vgCreatePaint, vgClear, ...), EGL calls (eglCreateContext, eglCreateWindowSurface, ...) and DMP extensions
  (`vgCreateImageDataDMP`, `vgCreatePathDataDMP`, `VG_DMP_multi_draw_image`, `VG_DMP_image_native_format`,
  `EGL_DMP_commandbuffer_attributes`). No shader or OpenGL ES drawing names. [code] 2026-11-20 (string scan of the E-M5 III
  block0)
- So c3d draws with OpenVG paths, paints and images into an EGL surface (the 256 x 256 RGBA draw buffers), and the
  renderers we ported call this library. [code]+[inferred]
- **Update 2026-11-21:** registers (base 0x9c200000), command lists, the c3d tasks' commands, the 147-entry proc table and
  the display path (layer = VSC **IMG2**, set by DISP_SET_LAYER_CUSTOM) are on [c3d GPU](c3d-gpu.md). [code]
- Other bodies (string scan of block0, 2026-11-20): `osddraw`, `c3d` and EGL names are in all six. OpenVG names: E-M5 III 95,
  OM-1 95, OM-5 / E-M1 III / OM-5 II 94, PEN-F only 8 (older library; it still has `vgCreateImageDataDMP`). Names missing
  on the OM-5, E-M1 III and OM-5 II (`COLOR_CREATER`, `gpiUpdateDisplay`) may sit in their compressed parts. [code]

## 6. om-emu and the display
- om-emu models VSC kind 2 (registers, latches, OSD planes, palettes, scaling, stacking) and the OSD engine, and runs
  the GUI, osddraw and display task natively; its output is the composed frame (our `emurun.mjs` saves it).
  [code] (om-emu) (2026-11-05)
- It does **not** model IMG planes on E-M5 III (live view is skipped), the histogram, hi/sh or peaking. Live view
  is only driven on OM-1. [code] (om-emu) (2026-11-05) 2026-11-21: our om-emu patch draws the 32-bit IMG planes (the c3d
  layer), see 6a; live view (format 0) is still not drawn.
- Use: an `osddraw` overlay (frame lines, markers) can be smoke-tested in om-emu before a camera run; anything that
  reads LV pixels cannot. [inferred] (2026-11-05)

### 6a. What om-emu would need to show the c3d layer (2026-11-21)

Read of om-emu `ccfe2e0` (2026-11-19) for the E-M5 III. om-emu facts are [code] (om-emu).

- **Today nothing from c3d reaches om-emu's screen, for three separate reasons.** (1) The E-M5 III's VSC compositor
  (`emu/src/dev/vsccompose2.mjs`, kinds 2 and 3) skips every enabled IMG plane as "not modelled"; only the OSD planes are
  drawn. (2) The DMP OpenVG library and the c3d task never run there: om-emu has no model of the GPU (its OM-3 notes,
  `docs/hle-gaps.md` 4.12, say the same for that body: the stack is dormant and the wheel plane stays empty). (3) The
  GUI's background drawer is an om-emu stand-in, and the GUI busy word 0x61600ba0 is only cleared by the c3d engine's
  answer, so editor screens stall after the first key. [code] (om-emu) + [emu] (2026-11-19)
- **What the layer is on the E-M5 III:** two flipping 256 × 256 draw buffers, 4 bytes per pixel (byte 0 alpha, bytes 1-3
  colour, decoded as BGR), shown at (432, 112) on the rear screen. [camera] 2026-11-19.
  ~~Which VSC plane and format register carry it is not yet read~~ It is VSC plane **IMG2**, c3d layer format 4 (2026-11-21,
  [c3d GPU](c3d-gpu.md#5-how-the-layer-reaches-the-screen)); ~~the VSC format value is still open~~ the VSC sees it as IMGPLANE2 = 0x301100: **format 3** (bits 20..23),
  per-pixel alpha (bit 12), level 0x100 (step 1 result below). On the OM-3 the same kind of wheel uses IMG2 in format 3
  (`R8G8B8a8`, per-pixel alpha). [code] (om-emu, OM-3) + [inferred] for the E-M5 III
- **Plan in three steps, smallest first** [inferred]:
  1. **Done 2026-11-21.** *Compose IMG planes* (about 1 day): add the 32-bit per-pixel-alpha format (and the YC format for a still picture
     underneath) to the kind-2 compositor. Any buffer we fill ourselves then shows in om-emu, so this step alone lets the 2D
     UI work test full-colour, anti-aliased, transparent drawing done by the CPU, with no GPU involved.
  2. *Stand in for OpenVG at the API* (about 2-4 days, after the c3d entry points and handle layouts are mapped): hook
     the vg*/egl* calls c3d actually uses (clear, paths with fill/stroke, paints, image draws with a transform, surface
     swap), rasterise them in JavaScript into the draw buffer, and send c3d's completion so the GUI busy word clears.
     This shows our wheels and any OpenVG drawing we add, close to but not pixel-exact with the camera.
  3. *Model the GPU itself* (open-ended): registers and command buffers of the DMP core. Only worth it if step 2 is not
     faithful enough; not recommended now.
- **Step 1 result (2026-11-21):** VSC writes when stock Color Creator opens in om-emu give the kind-2 IMG plane
  registers, plane p = 0 IMG1 .. 2 IMG3: address DMA9 + 4p (IMG2 +0x3c = 0xa4423ec0, c3d draw buffer A), stride DMA15 + 4p
  in 64-byte units (IMG2 0x10 = 1024 B), area AREA1 + 12p in the OSD areas' three-word form (IMG2 0x1ce0100 / 0x780078 /
  0x100 = 256 × 256 at (432, 112) in the 720 × 480 window), control IMGPLANE1 + 4p (IMG2 0x301100), enable DMA7 bit 5 - p
  (0x7 -> 0x17). Also written then: DMA2 +0x1c 0x10 -> 0, DMA22 +0x6c 0x17 -> 0x10 (meaning open). Pixels are straight
  (not premultiplied) alpha: 5,788 pixels of the camera's dump have a colour byte above alpha. [emu]+[camera]
  This means DMA10 (+0x3c) is IMG2's address, which questions the older "DMA9 Y / DMA10 C of IMG1" reading
  ([Display and OSD](display.md)): IMG1's YC may use one address (om-emu's format 0 is interleaved). [open]
- [code] (om-emu run) With our patch om-emu draws format-3 IMG planes at 1:1; the camera's own
  profile-editor buffer dump poked into buffer A shows the wheel in the camera's place under the stock labels.
  om-emu redraws only when the GUI does, so poke before a key press.
  For drawing tests: open Color Creator (SCP > Picture Mode, INFO) and write any 256 × 256 picture to 0xa4423ec0
  (`img2poke.py`). [emu] 2026-11-21
- [code] (om-emu run) **Step 2 blocker (2026-11-21):** with Color Creator open and keys pressed, om-emu reaches the c3d bridge
  0x602fccc9 but nothing after it: no hit on c3d_exe_bridge_disp_init 0x60c255c3, the EGL set-up 0x60c26187, the swap
  0x60c2639f, eglSwapBuffers 0x6119e454, vgDrawPath 0x611bc4f8 or c3d_exe's reply 0x60c25f91. om-emu's module-ack stand-in
  (S-MODACK, `emu/src/lab/camapp.mjs`, queue C3D) answers the C3D queue, so the c3d tasks never run. Step 2 therefore also
  needs the c3d tasks started and fed (or their work done in JavaScript), plus an object model for paths, paints and
  images (layouts: [c3d GPU](c3d-gpu.md) 4b; VGImage not traced yet, and the wheels are mostly image sprites). Revised
  estimate for step 2: about a week. [inferred]
- [code] (om-emu run) **OSD over IMG2, and the order codes (2026-11-21):** with the c3d layer showing (patch above) and three
  overlapping gpi boxes on GUI layers 0/1/2, all OSD layers draw over IMG2 under every OSD1 order code; stacking top to
  bottom per code: 0 L1>L0>L2, 1 L0>L1>L2, 2 L1>L2>L0, 3 L2>L1>L0 (stock), 4 L0>L2>L1, 5 L2>L0>L1. These come from om-emu's
  own ORDER_CODES table and plane order (inferred there), so only code 3 and "OSD over the c3d layer" are camera-backed. [emu]
- [emu] **Step 2 done (2026-11-21): stock c3d runs in om-emu.** Opening Color Creator draws the stock wheel through our
  JS OpenVG stand-in and each key redraws it. What it took, each found on the way:
  - [code] (om-emu run) c3d_main (task 67, entry 0x60c279d5) and task 70 (0x60c26090) are dormant in om-emu: start them with act_tsk, take
    queue 158 out of S-MODACK and pass the GUI's synchronous sends to it to the native kernel.
  - [code] (om-emu run) c3d_exe (0x60c25bde, queue 0x100f) and c3d_sub (0x60c28732, queue 0x1002) are **CPU-1 tasks** (posts to them ring
    the CPU-1 doorbell). Run each post on CPU 0 as one pass of the task loop (`lab.task_message`). c3d_exe's init
    (0x60c25b35) runs once; skip the DMP driver task it creates (entry 0x611c6090, priority 55).
  - [code] (om-emu run) **Frame done:** c3d_main answers the GUI's command 46 late. It saves the request (0x621db678..) and replies on
    command 48. c3d_sub posts command 48 when it gets command 3 (the GPU's frame-done) while c3d_exe's draw flag
    0x6253c479 is set. Without a GPU, post command 3 to c3d_sub after each draw that swapped.
  - [code] (om-emu run) Sprite sheets come from the resource reader 0x60167060 (category 0x8006, see c3d-gpu.md 4); om-emu runs no
    resource loader on E137, so serve them from block2.
  - [code] (om-emu run) DMP GPU registers 0x9c200000 as plain stub memory. The DMP memory manager 0x611bea11 is given two pools
    (0xa46ce6c0 + 0x80000, 0xa474e6c0 + 0x680000), and allocations (0x611beb7b) come from the second.
  - Not modelled: gradient paints, dashes, blend modes other than source-over, masks. No stock-vs-camera pixel
    comparison yet: the camera dump in private notes is from the ported editor, not stock Color Creator.
- Other om-emu limits met while building the profile editors (no 4-bpp pictures, histogram drawn as a stand-in block,
  editor closes after ~6 s without keys) and the tools that worked: UI drawing lessons.
  First test for step 2: the traced CC2/MC/SC renderer draw streams, which stop at the final c3d submit. [emu] 2026-11-21
- **More screens and a stand-in live view** [emu] 2026-11-21:
  - The ART carousel matches the camera's artwork, and Part Color (SCP, ART14) draws.
  - Patch 0003 adds `OM_BACKDROP` (session.mjs) and `BACKDROP` (c3drun.mjs). These draw a 720 x 480 RGB picture
    (`c3d/backdrop.py`: a generated lake-at-dusk landscape by default, a hard-edged test scene with `--test`, or a photo) under every plane, so OSD and IMG2 transparency show.
  - `mode:N` turns the mode dial (2 ART, 3 SCN). SCN screens get START and END but no UPDATE: [open].

How to draw on the GUI layers ourselves (calls, arguments, palettes, layer order, animation, other bodies): [Drawing on the GUI layers](osd-drawing.md). [emu] 2026-11-21

## Open questions
- Engine register map beyond +0x04..+0x50 on E-M5 III, and how `osddraw` turns a diagonal line into commands. [inferred] open
- Answered 2026-11-06: the TFT panel area and OSD scaling on the rear screen (720×480, no scaling; table above). [code]
- Which pool holds the LV through-image in each mode, and its stride/format (the live-view probe answers this).
- Done 2026-11-06: a VSC/engine register dump in om-emu; IMG-plane (live view) registers stay
  unknown until the live-view probe runs, since om-emu has no live view on E-M5 III. [code]
