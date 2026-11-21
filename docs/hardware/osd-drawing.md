# Drawing on the GUI layers: calls, layers, colours and limits

How to draw your own shapes on the E-M5 III screen with the firmware's own 2D drawing calls, what each call does, how
the layers stack and blend, and the limits. Every recipe here was drawn and checked in om-emu on the E-M5 III 1.7 image
(tag **[emu]**: the firmware's own code ran natively, om-emu's display model composed the picture), unless tagged
otherwise. Nothing on this page has run on a camera yet. Overview of the display path: [Graphics pipeline](graphics-pipeline.md);
register detail: [Display and OSD](display.md); the c3d vector layer: [c3d GPU](c3d-gpu.md); what the profile editors
taught us about screens, pictures, timers and keys: UI drawing lessons (looks).

Started 2026-11-21. The emulator driver that ran every recipe here is in this repo's `tools/osdlab/` (README there).


## What you can draw (summary)

| want | how | status |
|---|---|---|
| filled box | `gpiDrawOsdRectangle` | [emu], E-M5 III, OM-5, OM-5 II, OM-1 |
| horizontal or vertical line | `gpiDrawOsdLine` (draws a filled bar) or a 1-px rectangle | [emu] |
| diagonal line, curve, circle | no primitive: plot with `gpiDrawOsdDot` or short bars | [emu] (sine curve of dots) |
| see-through fill | a palette entry with opacity below 31 | [emu] |
| own colours | `GPISetPalette` on free entries | [emu] |
| copy or move an area | `gpiDrawOsdBlockCopy` | [emu] |
| clear | fill with index 127 (transparent) | [emu] |
| change which layer is on top | `GPISetOsdOrder`, 6 orders | [emu] |
| animation | draw into the hidden buffer, flip with `gpiUpdateDisplay`, repeat from a timer | [emu] (12-frame moving box); timer from the looks editors [camera] |
| pictures (icons, own bitmaps) | `gpiDrawBitmap` with a picture's data (section 3b), or picture widgets and the lookup hook (looks editors) | [emu] direct; [camera] via widgets |
| text in the camera font | `DrawText` with the GUI's text context (section 3c), text widgets, or pre-rendered pictures (looks S2b) | [emu] direct; [camera] via pictures |
| full colour, anti-aliased, per-pixel alpha | the 32-bit IMG2 layer (c3d) under the GUI layers: [c3d GPU](c3d-gpu.md), om-emu patch in [graphics pipeline 6a](graphics-pipeline.md#6a-what-om-emu-would-need-to-show-the-c3d-layer-2026-11-21) | [camera] wheel, [emu] own pixels |

## 1. The three GUI layers

- The GUI draws into **three 8-bit layers**. Each has four 896 × 600 buffers (stride 896) and a table of 16-byte
  **VRAM info records** `{u32 address, u8 format (1 or 2), ..., u16 width 896 at +8, u16 height 600 at +10}` that every
  draw call takes in a0. The GUI keeps a pointer table per layer, filled by `GPIInitPlatform` 0x60c93eee:
  [code]+[emu] 2026-11-21

  | GUI layer | pointer table (4 entries) | records (shooting screen) | buffers (pool) | VSC plane | palette (VSC +0x800 + 0x800 q) |
  |---|---|---|---|---|---|
  | 0 | 0x6230de68 | 0x621d9674 + 16 b | 0xafbe6000 + 0x83400 b (0x0c00) | OSD2 (DMA13) | q = 1 |
  | 1 | 0x6230de78 | 0x621d96b4 + 16 b | 0xaf9d9000 + 0x83400 b (0x0d00) | OSD3 (DMA14) | q = 2 |
  | 2 | 0x6230de88 | 0x621d9634 + 16 b | 0xafdf3000 + 0x83400 b (0x0b00) | OSD1 (DMA12) | q = 0 |

- **Stacking:** the default order (VSC OSD1 +0x1a4 = 3) puts layer 2 on top, then layer 1, then layer 0. Three
  overlapping boxes, one per layer, confirm it [code]+[emu]. On the shooting screen the icons and the AF frame and grid lines are
  on layers 0 and 1 (the AF frame and the two grid lines use layer 1 colours 120-122); layer 2 is empty there, so it is
  the safe layer for our own overlays. [code]+[emu] 2026-11-21
- `GPISetOsdOrder` 0x60c95b1b (d0, d1) writes order codes 0..5; all six were drawn: (0,1)→0, (0,2)→1, (1,0)→2,
  (1,2)→3, (2,0)→4, (2,1)→5 (d0, d1 → OSD1 value). How om-emu maps a code to a stacking order is its own reading
  [code] (om-emu, "I"), so the picture of each order wants a camera check. [code]+[emu] 2026-11-21
- Stacking per code, top to bottom (our notes run with the IMG2 patch):
  0 (0,1): L1 > L0 > L2; 1 (0,2): L0 > L1 > L2; 2 (1,0): L1 > L2 > L0; **3 (1,2, stock): L2 > L1 > L0**; 4 (2,0):
  L0 > L2 > L1; 5 (2,1): L2 > L0 > L1. All three GUI layers draw over the 32-bit c3d layer (IMG2) under every code.
  Only code 3 and "GUI over the c3d layer" are camera-backed (profile editor labels over the wheel); the rest is
  om-emu's model. [emu] (2026-11-21) + [camera] for code 3
- OM-1 uses another VSC kind (kind 1) with its own compositor in om-emu, so its missing layer-1 box is more
  likely an emulator gap than the calls. [code] (om-emu) 2026-11-21
- **Drawing canvas:** the draw calls check x + w ≤ 800 and y + h ≤ 1200 (the GUI's 800 × 1200 canvas spans two
  buffers); on the rear screen buffer pixel (x, y) shows at screen (x, y) inside the 720 × 480 window (shots at
  x 40..680 land where drawn). `gpiSetDrawOffset` 0x60c963b1 / `gpiClearDrawOffset` 0x60c963d9 / `gpiGetDrawOffset`
  0x60c963f8 shift every call by an offset held at 0x61ea1ef8/0x61ea1efa. [code]+[emu] 2026-11-21

## 2. Colours and transparency

- A pixel is a palette index. The low 7 bits pick one of **128 entries**; the GUI fills empty space with 255, which
  reads as entry 127, transparent in all three palettes. [code] (om-emu) + [emu]
- A palette word is `tra << 24 | Cr << 16 | Cb << 8 | Y` (BT.601). **tra is opacity, 0..31**: 31 opaque, 0 fully
  transparent. Opacity mixes a layer only with what is under it: a see-through box drawn over another box on the same
  layer replaces those pixels (no blending inside a layer). [emu] 2026-11-21
- The stock palettes already hold see-through colours: on the shooting screen layer 1 has white, grey and blue-grey in
  three steps (opacity 31 / 16 / 7, entries 22-30) and see-through blacks (entries 17, 18 at opacity 17, 8); layer 0
  has see-through blacks (entries 1, 2, 4 at opacity 17, 25, 10: the dimming boxes). Layer 0's palette uses only about 40 entries; the rest are opacity 0 and draw nothing. [emu] 2026-11-21
- Palettes are per screen: the GUI reloads them for the shooting screen, SCP, menus, playback and others (strings
  "SetPalette Shooting / [SUBPANEL] SCP / Play-Menu / TOP_MENU / ..." at 0x61101748..). A screen change can therefore
  overwrite colours we set. [code] 2026-11-21
- **Own colours:** `GPISetPalette` 0x60c94f90 (movm prologue, reached through a vtable): d0 = first entry, d1 = count,
  a0 = an object whose word at +72 points to a halfword layer number, a1 = array of `0xAARRGGBB` words (alpha 0..255,
  stored as alpha >> 3). It calls OSDControl `setColorPalette` 0x607f58c9 (colour) and 0x607f5971 (opacity) per entry.
  The settable entries per layer come from the table 0x60ea5c78: **layer 0: 32, layer 1: 256 (all 128), layer 2: 64**;
  entries past the limit are skipped silently. A seven-step red ramp (alpha 255..64) into layer 1 entries 120-126
  showed as seven red boxes fading to black, and also turned the AF frame and grid lines red, because they use those
  entries. Pick entries the screen does not use. [code]+[emu] 2026-11-21
- Other screens use other entries. On the picture-mode editor screen (0x6110) layer 0 is empty (all index 31,
  opacity 0), layer 2 holds only the histogram (index 14), and every picture lands on layer 1 (descriptor planes 4 and
  5 both map there), using layer 1 entries 0, 4-6, 16-18, 22-24, 38, 59, 87, 100, 106, 114, 122 and, on the slider
  row, 41, 42, 46, 88, 98. [emu] 2026-11-21 (our notes)
- **Palette banks:** the display controller keeps two banks per OSD plane palette (words at 0x9c000800 + 0x800 q and
  the same + 0x200; q 0 = OSD1 = GUI layer 2); bit 4 of 0x9c000364 + 8 q picks the shown one. `GPISetPalette` only
  updates the GUI's own arrays: nothing reaches the controller until `gpiUpdateDisplay`, which uploads the palette into
  the hidden bank and flips the bit. Run: layer 2 entries 32-35 set, bank +0x200 shown (bit 4 = 1); after the next
  update the words were in bank 0 and bit 4 was 0. So call `gpiUpdateDisplay` after `GPISetPalette` and let a frame
  pass; writing the controller's words directly is not needed. [code] (om-emu model) + [emu] 2026-11-21

## 3. The draw calls

All draw calls queue requests for the 2D engine. They only work **between `drawOsdStart` and `drawOsdEnd`**: the queue
function 0x60c1db46 refuses a request unless the engine state 0x621d95b4 = 1 and 0x621d95b6 = 0 (error 303, nothing
drawn), and `drawOsdEnd` builds the command list and runs the engine. Calls in E-M5 III 1.7 addresses; "vinfo" = a VRAM
info record from section 1; colour = palette index; layer = 0..2. [code]+[emu] 2026-11-21

| call | address | arguments | result in om-emu |
|---|---|---|---|
| OSDControl `drawOsdStart` (cw_drawOsdStart) | 0x607f6de0 | none; logs "called twice" if nested | opens the batch |
| OSDControl `drawOsdEnd` | 0x607f6e55 | none | runs the engine on the batch |
| `gpiDrawOsdDot` | 0x60c95123 | d0 x, d1 y, a0 vinfo, a1 colour, stack: layer | 1 pixel |
| `gpiDrawOsdLine` | 0x60c951f0 | d0 x, d1 y, a1 w, a0 vinfo, stack: h, colour, layer | a filled w × h bar (a "line" with w and h both > 1 is a box; negative sizes draw nothing) |
| `gpiDrawOsdRectangle` | 0x60c952fb | as the line | filled box |
| `gpiDrawOsdBlockCopy` | 0x60c9540a | d0 src x, d1 src y, a0 src vinfo, a1 dst vinfo, stack: w, h, dst x, dst y, layer | copies the area |
| `gpiDrawBitmap` | 0x60c95576 | d0 x, d1 y, a0 vinfo, a1 picture stream, stack: w, h (0, 0), 16-bit remap table or 0, 8-bit remap table or 0, layer; frame 96 | draws a picture (section 3b) |
| `gpiDrawCharactor` | 0x60c95682 | d0 glyph width, d1 character code (log only), a0 vinfo, a1 glyph record; stack: x, y, 0x20, layer; frame 152 | one cached glyph (section 3c) |
| `gpiUpdateDisplay` | 0x60c9588b | d0 0 = show buffer (0x61ea1ecc), else that index xor 2 | commits all three layers |

- Behind them: osddraw `exec_rect` 0x60c1f252 (a 108-byte request on the heap, stride 896), queued by 0x60c1b887 →
  0x60c1db46; `exec_start` 0x60c20032 / `exec_end` 0x60c2004e are what drawOsdStart/End call. The GUI's own display
  list executor (rectangles, lines, characters, bitmaps from widget draw commands) is 0x60c94a86. [code] 2026-11-21
### 3a. The gc library (drawing contexts)
Widgets and owner-drawn children draw through a "gc" (graphics context, 688 bytes) instead of the gpi calls. First
pass, names from om-emu's OM-1 text notes mapped through its port table, the rest read from the code: [code] 2026-11-21
| call | address | what it does |
|---|---|---|
| GcCreate | 0x60c92194(d0 id) | new gc; device bounds at +4, clip at +24, pen size +40 = (1, 1) |
| gc for a GUI object | 0x60c88a97(a0 object) | the gc the histogram uses (our notes) |
| set device | 0x60c92747(a0 gc, d0 layer 0-2, a1 0) | which GUI layer it draws on (+68, +72) |
| set clip | 0x60c92295(a0 gc, a1 rect or 0) | +24 = rect ∩ device bounds; 0 = whole device |
| set foreground | 0x60c925b7(a0 gc, d0 colour) | +36 (and +640); the text colour too |
| set colours | 0x60c92389(a0 gc, d0, d1) | d0 → +644/+56 through 0x60c92459, d1 → background 0x60c9226c (+648/+60); -1 = none |
| set background | 0x60c9226c(a0 gc, d0 colour or -1) | +648/+60 |
| pen size | 0x60c92678(a0 gc, d0, d1) | +40, +42, each at least 1 |
| +54 mode | 0x60c9239a(a0 gc, d0) | +54 = d0 mod 38, negative → 38; meaning not known |
| set font | 0x60c92692(a0 gc, d0 font id) | +76 font handle |
| text | `DrawText` 0x60c89f5b, `DrawTextById` 0x60c89f43 | section 3c |
| polyline | 0x60c8ebd9 | the histogram's curve ([display](display.md)) |

The colour setters run the value through 0x60c923b2 when byte +660 is 1 (probably a colour-to-palette mapping; not
checked). Fill-rectangle and line calls on a gc are not mapped yet. [code] open

### 3b. Pictures (`gpiDrawBitmap`)
- A picture's 24-byte header {14, w, h, 8, 0, size, data, 7} is followed straight away by its stream; **a1 is the
  stream, header + 24** (not the header's data word). Headers come from the picture table: word at 0x61eb7628 (here
  0xa37c9b38) + 4 × id holds the header address (lookup 0x60c934bb returns that slot). The GUI calls it with w = h = 0
  (size taken from the stream). Drawn in om-emu: ids 0x100 (the "640" icon), 0x200 (self-timer) and 0x1084 (box) at
  our positions. w, h other than 0 drew nothing in om-emu (probably scaling; not checked). [code]+[emu] 2026-11-21
- The 8-bit table (4th stack word) remaps each source index to a layer palette entry: a table of 256 × 22 drew the
  icon as a white silhouette, with its transparent pixels left alone. The 16-bit table (3rd word) had no effect on
  this format-0x0b picture. The GUI's executor 0x60c94a86 builds both tables per picture (transparent colour → 0).
  [code]+[emu] 2026-11-21
- Our own pictures: same stream format (0x0a 4 bpp runs, 0x0b 12-bit tokens; see
  UI drawing lessons), any address. [inferred]

### 3c. Text (`DrawText`)
- **`DrawText` 0x60c89f5b** (om-emu's E143 name, its port table maps it to E137): d0 = style, d1 = UTF-16 string
  (NUL-terminated), a0 = text context ("gc"), a1 = box {x0, y0, x1, y1} as four halfwords; native call frame
  [d2,d3,a2,a3] 252. Style (24 bytes): colour u32, two words 0x10, 0x10, h-align byte, v-align byte, margins
  (4 halfwords at +14), edge colour byte at +22. The GUI's menu text context **0x621fd480** draws into layer 2
  buffer 0 (record 0x621d9634). Inside the start/end bracket, then update: four lines of our own text drew in the
  camera font on the shooting screen. [code]+[emu] 2026-11-21
- The font is antialiased and the colour picks a ramp in the layer's palette: colour 5 drew clean blue; 1, 10, 12
  drew with odd fringe colours on layer 2 (only 64 settable entries there). `ÄÖÜ äöü ß` and `→` did not draw in
  the English font (the line stopped or showed a substitute). Pick colours whose ramp is set, or set your own ramp
  with `GPISetPalette`. [emu] 2026-11-21
- Clean white text on the shooting screen: `GPISetPalette` on **layer 2** (halfword layer number 2 in the object, as
  for layer 1) entries 60-63 with white / black 78 % / amber / cyan, then `gpiUpdateDisplay`, then `DrawText` with
  colour 60 and edge 61: crisp white text with no fringes. Colour 2 without an own ramp drew white with
  rainbow fringes (its antialias steps use neighbouring entries). The two full-height lines at x = 40 and 680 that
  show on this screen in om-emu are the stock 4:3 frame edges (the default 4:3 aspect on the 3:2 panel), not a side
  effect of drawing. [emu]+[inferred] 2026-11-21
- Underneath, `DrawText` renders each glyph into a glyph cache (descriptor {w, h, data, 4, size}, 4 bpp) and calls
  `gpiDrawCharactor` once per character with a glyph record (colours at +2/+4/+6, glyph descriptor at +28): a captured
  record replayed at new positions redrew the same glyph. Use `DrawText`, not the per-glyph call. [code]+[emu] 2026-11-21

- **No diagonal or curve primitive.** The engine has fill, copy, bitmap and palette commands only (see
  [graphics pipeline](graphics-pipeline.md#1-gui-drawing-goes-through-a-hardware-osd-engine)), and `gpiDrawOsdLine` takes
  a box, not two end points. A sine curve of 150 dots drew cleanly; anything round or slanted is dots or short bars
  (one request each, so keep counts modest), or a pre-made picture, or the c3d layer. [code]+[emu] 2026-11-21
- A rectangle request returns non-zero in the gpi wrapper even when it drew (it then logs "gpiDrawOsdRectangle Error
  nWidth..."): treat that log as noise. [emu] 2026-11-21

## 4. Showing it, double buffering and animation

- Each layer has buffers 0-3; the GUI draws in one pair and shows the other. `gpiUpdateDisplay(0)` shows the buffer
  index held in 0x61ea1ecc (0 on the shooting screen), `gpiUpdateDisplay(1)` the other one (index xor 2), for all three
  layers at once, through OSDControl 0x607f5a01. With display sync on (the E-M5 III default) the switch waits for the
  next live-view frame. [code]+[emu] 2026-11-21
- **Animation recipe:** draw frame n into buffer 0 (n even) or 2 (n odd) of your layer, erase the old shape in that
  buffer with colour 127, then `gpiUpdateDisplay(0 or 1)` to show it. A 12-frame moving box on layer 2 ran this way with
  the stock GUI untouched. The other layers flip too, so this only suits screens whose
  layers 0 and 1 hold the same picture in both buffers (true on the shooting screen in om-emu). [emu] 2026-11-21
- **What drives the frames:** a one-shot GUI timer `0x60e1cc60(d0 event, d1 ms)`, re-armed on every tick (stock curve
  screen: event 532 every 100 ms; our S4f live histogram does the same), then a child redraw request
  `0x60c8799f(a0 child, d0 1, a1 0)`. [camera] (looks S4f), UI drawing lessons
- **Mixing with the c3d layer:** the OSD commit (display command 17) and the c3d layer flip (command 18) are handled
  one after another by the display task, and both write latched VSC registers that apply at the next frame boundary,
  so updates queued together should land on the same frame. Nothing locks them together, and the OSD side also waits
  for the live-view sync. [code] (our notes: 0x60190274, 0x601903d7, c3d sends 17 then 18 at 0x60c255c3) + [inferred] 2026-11-21
- How fast it can go on the camera (engine time per request, commit at the live-view rate) is not measured. [inferred]
- **One-off drawing does not last on a live GUI screen:** the screen's next own redraw and update replaces it. On the
  profile editor (status-118 histogram timer every 100 ms) a panel shown right after our update was gone 300 ms later.
  Draw from the screen's redraw path, or redraw after each GUI update. [emu] 2026-11-21 (our notes)
- Our drawing on layers 0 and 1 is overwritten whenever the GUI redraws that area; layer 2 is not touched by the
  shooting screen in om-emu. [emu]

## 5. Input

- **Keys and dials** reach a screen as control events (UP 0x9004, DOWN 0x9006, rear dial 0x9031, front dial 0x9032,
  OK-hold 0x903e; handler body 0x60d540de). [camera] (looks editors, lessons)
- **Touch** (from om-emu's reading of the E144 family, which includes the E-M5 III; om-emu facts, our addresses not
  yet mapped): the panel controller at I2C slave 0x48 reports up to two points; the driver passes one touch on, in rear
  panel pixels 720 × 480 (flipped to 719 - x, 479 - y only for the swivelled monitor). The camera layer turns them into
  touch kinds TOUCH, LONG TOUCH, RELEASE, TAP, DOUBLE TAP, SLIDE and FLICK (HFW statuses 225-230, 300), and the GUI gets
  message **0x9100**; a tap is shorter than 150 ms, a double tap a second tap within 800 ms. The SDK class
  `TouchPanel` has `startTouchPanel`, `endTouchPanel`, `ctrlTouchPanelEvent`, `getTouchPanelState`, `getTouchNumber`,
  `getTouchPanelHistory`, `isTouchDetection` and `ctrlTouchPanelArea` (names at 0x60ab378c..). [code] (om-emu, E144) +
  [code] (names) 2026-11-21
- **E-M5 III touch addresses** (om-emu's E143 facts through its port table, plus our reading): touch init 0x60197420,
  touch task 0x60197536, TP_OPEN 0x6019779c, gesture mask TP_MASK 0x60197925 (mask word 0x62105d3c), HFW touch callback
  0x608744a0 (gesture to status 225-230/300). [code] 2026-11-21
- **Into the GUI:** `sendEvent` **0x60d539e0**(a0 0, a1 message), message = 8 words {**107**, 0, kind, x, y, 0, 0, 0}.
  107 is the E-M5 III's index of 0x9100 (E143 uses 109). Kinds: 1 TOUCH, 2 LONG TOUCH, 3 RELEASE, 4 TAP, 5 DOUBLE TAP,
  6 SLIDE, 7 FLICK. Posted in om-emu on the shooting screen: TOUCH at (90, 30) lit the Wi-Fi/Bluetooth icon box light
  grey, the TAP that followed put it back, as on the OM-1. [code]+[emu] 2026-11-21
- **The GUI's touch filter** is 0x60e2dbed ("[GuiTouch] Area Not Found!" 0x6110e776 when nothing matches): it reads the
  screen's area lists through the table at **0x6110e548**; each area is 16 bytes {x, y, w, h halfwords, +8 hit-test
  function or 0, +12 action (255 = none)}. With no function it tests the point against the rectangle (0x60c937c9);
  a match sends the area's action on. [code] 2026-11-21
- So a touch button of our own is: a box (and text) on layer 2, plus either an area entry in our screen's list (the
  GUI then hit-tests it and sends its action), or a hook on 0x9100 for our screen that tests x, y itself. Not built
  on the camera. [inferred]

## 6. Other cameras

The same gpi calls exist with byte-identical code in every body checked (rectangle, line, dot, block copy, bitmap and
order; start/end and update differ only in addresses). Drawn in om-emu with the same three boxes: [code]+[emu] 2026-11-21

| body | rect | update | start / end | layer pointer table | drawn in om-emu |
|---|---|---|---|---|---|
| E-M5 III 1.7 | 0x60c952fb | 0x60c9588b | 0x607f6de0 / 0x607f6e55 | 0x6230de68 | yes, 3 layers |
| OM-5 1.2 | 0x60d52e49 | 0x60d534c7 | 0x6088a21a / 0x6088a28f | 0x62319a48 | yes, 3 layers (order code 2) |
| OM-5 II 1.1 | 0x60d54d22 | 0x60d55352 | 0x6088aa3b / 0x6088aab0 | 0x62353b4c | yes, 3 layers |
| E-M1 III 1.6 | 0x60cfb2a3 | 0x60cfb921 | 0x60844c49 / 0x60844cbe | 0x6233f0c8 | not run (no om-emu firmware set-up) |
| OM-1 1.9 | 0x610ddeda | 0x610de50e | 0x60b0a7a7 / 0x60b0a81c | 0x62b3dfdc | layer 0 yes; layer 1 box not seen |
| OM-1 II 1.3 | 0x610eaf3f | 0x610eb573 | 0x60b1559d / 0x60b15612 | 0x62b96214 | nothing seen yet |
| E-M5 II 4.1 | 0x60baf748 | none found | 0x606f0a01 / 0x606f0a57 | records 0x618c56a4 (see below) | yes, 3 layers |
| PEN-F 4.1 | 0x60bccf1b | none found | 0x606e25f4 / 0x606e264a | records 0x618eb390 (see below) | yes, 3 layers |
| E-M5 (Mark I) 2.3 | no `gpiDraw*` names | | | | can't run: not in om-emu |

- The OM-1 family keeps 4 buffers for layer 0, 2 for layer 1 and 1 for layer 2 (pointer table holes), so their buffer
  indices differ from the E-M5 III's. [emu] 2026-11-21
- **E-M5 II and PEN-F** (same chip): the rectangle call has the same arguments as on the E-M5 III, inside the same
  start/end bracket. They keep 3 layers × 2 buffers as 16-byte VRAM records {addr, plane, 896, 600}, plane order
  OSD1/OSD1/OSD2/OSD2/OSD3/OSD3; buffer 1 of each plane is the one on screen, so drawing into it shows with no update
  call (E-M5 II: OSD1 0x618c56b4, OSD2 0x618c56d4, OSD3 0x618c56f4; PEN-F: 0x618eb3a0 / 0x618eb3c0 / 0x618eb3e0).
  Pass the record address as vinfo. No `gpiUpdateDisplay` string in either. Run on the runtime image dumped from om-emu
  (their blocks are compressed). [code]+[emu] 2026-11-21
- **E-M5 (Mark I)** has `drawOsdStart/End` and `GPISetPalette` but no `gpiDraw*` names, and om-emu has no E-M5 I
  support, so nothing was drawn; string-level facts only (section below). [code] 2026-11-21
- OM-5 / OM-5 II / E-M1 III addresses are in the expanded images; the gpi strings are in their compressed parts. [code]

## Open questions
- Run a layer-2 overlay on the camera (boxes over live view, then the animation recipe from a timer). [inferred] open
- `gpiDrawBitmap` with w, h other than 0 (scaling?); `DrawText` on the camera (text context address, colours); which fonts hold accented letters. [code] open
- Frame rate: engine time per request and the real flip rate with live view. [inferred] open
- Touch: where an action number from an area goes, and a touch button of our own on the camera. [inferred] open
- OM-1 layer 1 (likely om-emu's kind-1 compositor) and OM-1 II: why the boxes don't show. [emu] open

## On the E-M5 II and E-M5 (Mark I) (2026-11-21)

- **E-M5 II 4.1:** the same `gpiDrawOsd*` calls and DMP OpenVG names are present, so this guide's method applies with new addresses. [code]
- **E-M5 (Mark I) 2.3:** `drawOsdStart/End` and `GPISetPalette` present, no `gpiDraw*` names and no OpenVG; a GPU exists (`play_gpu.c`). [code]

Full comparison: [older bodies](../bodies/comparison.md#older-bodies-e-m5-ii-and-e-m5-mark-i-2026-11-21).
