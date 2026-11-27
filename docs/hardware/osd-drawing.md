# Drawing on the GUI layers: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Drawing your own graphics](../guides/drawing-your-own.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

This page shows how to draw your own shapes on the E-M5 III screen with the firmware's own 2D drawing calls. It covers
what each call does, how the layers stack and blend, and the limits. Every recipe here was drawn and checked in om-emu
on the E-M5 III 1.7 image, unless a note says otherwise. There the firmware's own code ran natively, and om-emu's
display model composed the picture.[^emu1] Nothing on this page has run on a camera yet. The emulator driver that ran
every recipe is in this repo's `tools/osdlab/`, with a README there.

Related pages:

- [Graphics pipeline](graphics-pipeline.md), the overview of the display path.
- [Display and OSD](display.md), the register detail.
- [c3d GPU](c3d-gpu.md), the vector layer.
- UI drawing lessons (looks), what the profile editors taught us about
  screens, pictures, timers and keys.

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred or seen in an emulator.

## What you can draw

| want | how | evidence |
|---|---|---|
| filled box | `gpiDrawOsdRectangle` | om-emu, on the E-M5 III, OM-5, OM-5 II and OM-1[^emu1] |
| horizontal or vertical line | `gpiDrawOsdLine` (draws a filled bar) or a 1-pixel rectangle | om-emu[^emu1] |
| diagonal line, curve, circle | no primitive. Plot with `gpiDrawOsdDot` or short bars | om-emu (a sine curve of dots)[^emu1] |
| see-through fill | a palette entry with opacity below 31 | om-emu[^emu1] |
| own colours | `GPISetPalette` on free entries | om-emu[^emu1] |
| copy or move an area | `gpiDrawOsdBlockCopy` | om-emu[^emu1] |
| clear | fill with index 127 (transparent) | om-emu[^emu1] |
| change which layer is on top | `GPISetOsdOrder`, 6 orders | om-emu[^emu1] |
| animation | draw into the hidden buffer, flip with `gpiUpdateDisplay`, repeat from a timer | om-emu (a 12-frame moving box)[^emu1]. The timer is from the profile editors, on the camera[^cam2] |
| pictures (icons, own bitmaps) | `gpiDrawBitmap` with a picture's data ([Pictures](#pictures)), or picture widgets and the lookup hook (profile editors) | om-emu for the direct call[^emu1]. On the camera through widgets[^cam2] |
| text in the camera font | `DrawText` with the GUI's text context ([Text](#text)), text widgets, or pre-rendered pictures (profile editors) | om-emu for the direct call[^emu1]. On the camera through pictures[^cam2] |
| full colour, anti-aliased, per-pixel alpha | the 32-bit IMG2 layer (c3d) under the GUI layers. See [c3d GPU](c3d-gpu.md) and the om-emu patch in [Graphics pipeline](graphics-pipeline.md#showing-the-c3d-layer-in-om-emu) | the wheel on the camera[^cam2]. Our own pixels in om-emu[^emu3] |

*What can be drawn on the GUI layers, and how each was checked.*

## The three GUI layers

The GUI draws into **three 8-bit layers**. Each has four 896 × 600 buffers, with a stride of 896.[^fw1][^emu1]

- Every draw call takes a **VRAM info record** in a0, called "vinfo" on this page. It is 16 bytes:
  `{u32 address, u8 format (1 or 2), ..., u16 width 896 at +8, u16 height 600 at +10}`.
- The GUI keeps a table of four record pointers per layer, filled by `GPIInitPlatform`.

| GUI layer | buffers (pool) | VSC plane | palette (q) |
|---:|---|---|---:|
| 0 | `0x0c00` | OSD2 (DMA13) | 1 |
| 1 | `0x0d00` | OSD3 (DMA14) | 2 |
| 2 | `0x0b00` | OSD1 (DMA12) | 0 |

*GUI layers with their buffer pools, VSC planes and palettes.[^fw1]*

The palette of plane q sits at VSC `+0x800` + `0x800` × q. Pointer tables, records and buffer addresses are in the
[address reference](#address-reference).

### Stacking

- The default order (VSC OSD1 = 3) puts layer 2 on top, then layer 1, then layer 0. Three overlapping boxes, one per
  layer, confirm it.[^fw1][^emu1]
- On the shooting screen the icons, the AF frame and the grid lines are on layers 0 and 1. The AF frame and the two grid
  lines use layer 1 colours 120-122. Layer 2 is empty there, so it is the safe layer for our own overlays.[^fw1][^emu1]
- `GPISetOsdOrder(d0, d1)` writes order codes 0 to 5 into OSD1. All six were drawn.[^fw1][^emu1]

| order code | (d0, d1) | stacking, top to bottom |
|---:|---|---|
| 0 | (0, 1) | L1 > L0 > L2 |
| 1 | (0, 2) | L0 > L1 > L2 |
| 2 | (1, 0) | L1 > L2 > L0 |
| 3 (stock) | (1, 2) | **L2 > L1 > L0** |
| 4 | (2, 0) | L0 > L2 > L1 |
| 5 | (2, 1) | L2 > L0 > L1 |

*Order codes and the stacking om-emu draws for each, with the IMG2 patch.[^emu3]*

- All three GUI layers draw over the 32-bit c3d layer (IMG2) under every code.[^emu3]
- How om-emu maps a code to a stacking order is its own reading, marked "I" there.[^emu2] So the picture of each order
  wants a camera check. Only code 3 and "GUI over the c3d layer" are camera-backed, by the profile editor labels over
  the wheel.[^cam1] The rest is om-emu's model.
- The OM-1 uses another VSC kind (kind 1) with its own compositor in om-emu. So its missing layer-1 box is more
  likely an emulator gap than the calls.[^emu2]

### Drawing canvas

- The draw calls check x + w ≤ 800 and y + h ≤ 1200. The GUI's 800 × 1200 canvas spans two buffers.[^fw1][^emu1]
- On the rear screen, buffer pixel (x, y) shows at screen (x, y) inside the 720 × 480 window. Shots at x 40 to 680
  land where drawn.[^emu1]
- `gpiSetDrawOffset`, `gpiClearDrawOffset` and `gpiGetDrawOffset` shift every call by an offset held in two RAM
  halfwords.[^fw1][^emu1]

## Colours and transparency

- A pixel is a palette index. The low 7 bits pick one of **128 entries**.[^emu2]
- The GUI fills empty space with 255, which reads as entry 127. That entry is transparent in all three
  palettes.[^emu2][^emu1]
- A palette word is `tra << 24 | Cr << 16 | Cb << 8 | Y` (BT.601). **tra is opacity, 0 to 31.** 31 is opaque and 0
  fully transparent.[^emu1]
- Opacity mixes a layer only with what is under it. A see-through box drawn over another box on the same layer
  replaces those pixels. There is no blending inside a layer.[^emu1]

**Stock see-through colours.** The stock palettes already hold see-through colours.[^emu1]

- On the shooting screen layer 1 has white, grey and blue-grey in three steps (opacity 31, 16 and 7, entries 22-30). It
  has see-through blacks too (entries 17 and 18, at opacity 17 and 8).
- Layer 0 has see-through blacks (entries 1, 2 and 4, at opacity 17, 25 and 10). These are the dimming boxes.
- Layer 0's palette uses only about 40 entries. The rest are opacity 0 and draw nothing.

**Palettes are per screen.** The GUI reloads them for the shooting screen, the Super Control Panel (SCP), menus,
playback and others (strings "SetPalette Shooting / [SUBPANEL] SCP / Play-Menu / TOP_MENU / ..."). So a screen change
can overwrite colours we set.[^fw1]

**Own colours.** `GPISetPalette` has a `movm` prologue and is reached through a vtable.[^fw1][^emu1]

- Arguments: d0 = first entry, d1 = count, a0 = an object whose word at +72 points to a halfword layer number, a1 = an
  array of `0xaarrggbb` words. Alpha is 0 to 255 and stored as alpha >> 3.
- It calls OSDControl `setColorPalette` for the colour and a second function for the opacity, per entry.
- The settable entries per layer come from a table: **layer 0: 32, layer 1: 256 (all 128), layer 2: 64.** Entries
  past the limit are skipped silently.
- A seven-step red ramp (alpha 255 to 64) into layer 1 entries 120-126 showed as seven red boxes fading to black. It
  also turned the AF frame and grid lines red, because they use those entries. Pick entries the screen does not use.

**Other screens use other entries.** On the picture-mode editor screen (`0x6110`) layer 0 is empty (all index 31,
opacity 0). Layer 2 holds only the histogram (index 14). Every picture lands on layer 1, because descriptor planes 4
and 5 both map there.[^emu7] They use layer 1 entries 0, 4-6, 16-18, 22-24, 38, 59, 87, 100, 106, 114 and 122, and on
the slider row 41, 42, 46, 88 and 98.

**Palette banks.** The display controller keeps two banks per OSD plane palette. A bit per plane picks the one
shown.[^emu2][^emu1] Plane q 0 is OSD1, which is GUI layer 2.

- `GPISetPalette` only updates the GUI's own arrays. Nothing reaches the controller until `gpiUpdateDisplay`, which
  uploads the palette into the hidden bank and flips the bit.
- In a run, layer 2 entries 32-35 were set while bank `+0x200` was shown (bit 4 = 1). After the next update the words
  were in bank 0 and bit 4 was 0.
- So call `gpiUpdateDisplay` after `GPISetPalette` and let a frame pass. Writing the controller's words directly is
  not needed.

## The draw calls

All draw calls queue requests for the 2D engine. They only work **between `drawOsdStart` and `drawOsdEnd`**. The queue
function refuses a request unless the engine state words read 1 and 0. It then returns error 303 and nothing is drawn.
`drawOsdEnd` builds the command list and runs the engine.[^fw1][^emu1]

In the table, vinfo is a VRAM info record from [The three GUI layers](#the-three-gui-layers), colour is a palette
index and layer is 0 to 2.

| call | arguments | result in om-emu |
|---|---|---|
| OSDControl `drawOsdStart` (`cw_drawOsdStart`) | none. Logs "called twice" if nested | opens the batch |
| OSDControl `drawOsdEnd` | none | runs the engine on the batch |
| `gpiDrawOsdDot` | d0 x, d1 y, a0 vinfo, a1 colour, stack: layer | 1 pixel |
| `gpiDrawOsdLine` | d0 x, d1 y, a1 w, a0 vinfo, stack: h, colour, layer | a filled w × h bar. A "line" with w and h both > 1 is a box. Negative sizes draw nothing |
| `gpiDrawOsdRectangle` | as the line | filled box |
| `gpiDrawOsdBlockCopy` | d0 src x, d1 src y, a0 src vinfo, a1 dst vinfo, stack: w, h, dst x, dst y, layer | copies the area |
| `gpiDrawBitmap` | d0 x, d1 y, a0 vinfo, a1 picture stream, stack: w, h (0, 0), 16-bit remap table or 0, 8-bit remap table or 0, layer. Frame 96 | draws a picture ([Pictures](#pictures)) |
| `gpiDrawCharactor` | d0 glyph width, d1 character code (log only), a0 vinfo, a1 glyph record, stack: x, y, `0x20`, layer. Frame 152 | one cached glyph ([Text](#text)) |
| `gpiUpdateDisplay` | d0 0 = show buffer, else that index xor 2 | commits all three layers |

*The gpi draw calls. Their E-M5 III 1.7 addresses are in the [address reference](#address-reference).*

Behind them sits `osddraw`.[^fw1]

- `exec_rect` puts a 108-byte request on the heap, with stride 896, and queues it.
- `exec_start` and `exec_end` are what `drawOsdStart` and `drawOsdEnd` call.
- The GUI's own display-list executor draws rectangles, lines, characters and bitmaps from widget draw commands.

### The gc library

Widgets and owner-drawn children draw through a "gc" (graphics context, 688 bytes) instead of the gpi calls. Names come
from om-emu's OM-1 text notes, mapped through its port table. The rest was read from the code.[^fw1]

| call | arguments | what it does |
|---|---|---|
| GcCreate | d0 id | new gc. Device bounds at +4, clip at +24, pen size +40 = (1, 1) |
| gc for a GUI object | a0 object | the gc the histogram uses (profile editors) |
| set device | a0 gc, d0 layer 0-2, a1 0 | which GUI layer it draws on (+68, +72) |
| set clip | a0 gc, a1 rect or 0 | +24 = rect ∩ device bounds. 0 = whole device |
| set foreground | a0 gc, d0 colour | +36 (and +640). The text colour too |
| set colours | a0 gc, d0, d1 | d0 to +644/+56 through a helper. d1 to the background setter (+648/+60). -1 = none |
| set background | a0 gc, d0 colour or -1 | +648/+60 |
| pen size | a0 gc, d0, d1 | +40, +42, each at least 1 |
| +54 mode | a0 gc, d0 | +54 = d0 mod 38, negative gives 38. Meaning not known |
| set font | a0 gc, d0 font id | +76 font handle |
| text | `DrawText`, `DrawTextById` | see [Text](#text) |
| polyline | | the histogram's curve ([Display and OSD](display.md)) |

*gc library calls. Addresses in the [address reference](#address-reference).*

The colour setters run the value through a helper when byte +660 is 1. That is probably a colour-to-palette mapping,
not checked. Fill-rectangle and line calls on a gc are not mapped yet.[^fw1]

### Pictures

`gpiDrawBitmap` draws a picture from its data.[^fw1][^emu1]

- A picture's 24-byte header `{14, w, h, 8, 0, size, data, 7}` is followed straight away by its stream. **a1 is the
  stream, header + 24**, not the header's data word.
- Headers come from the picture table. A RAM word (here `0xa37c9b38`) + 4 × id holds the header address, and the
  lookup function returns that slot.
- The GUI calls it with w = h = 0, so the size is taken from the stream.
- Drawn in om-emu: ids `0x100` (the "640" icon), `0x200` (self-timer) and `0x1084` (box) at our positions.
- w and h other than 0 drew nothing in om-emu. That is probably scaling, not checked.

**Remap tables.**[^fw1][^emu1]

- The 8-bit table (4th stack word) remaps each source index to a layer palette entry. A table of 256 × 22 drew the
  icon as a white silhouette, with its transparent pixels left alone.
- The 16-bit table (3rd word) had no effect on this format-`0x0b` picture.
- The GUI's executor builds both tables per picture, with the transparent colour mapped to 0.

**Picture formats.** The stream starts with a 4-byte header `{lines - 1: 12 bits, width - 1: 12 bits, format byte}`.
The size comes from it, which is why the GUI passes w = h = 0.[^fw2][^emu4]

- **`0x0a`, 4 bit.** One byte per run. The high nibble is the colour index 0 to 15, and the low nibble is the run
  length - 1 (1 to 16 pixels). Runs never cross a row end, so each row is encoded on its own. Example: the tone-curve
  grid `0x1039` (262 × 266).[^fw2][^cam3]
- **`0x0b`, 12 bit.** 12-bit tokens, five per 64-bit word. The icons above use it, and `0x100` was checked.[^fw2][^emu4]
- Other run-length formats the engine knows: `0x01`, `0x02` and `0x09`, not studied.[^emu2]

**How a 4-bit picture reaches the layer.**[^fw2][^emu4]

- The GUI sends an engine BITMAP command (opcode `0x30`). The grid's word is `0x20000330`, plane depth 3 = 8 bit.
- Bit 12 means a 16-entry colour table follows inline, and needs bit 11 too. Bit 11 alone means use the table loaded
  earlier. Both clear means no table.
- The grid is sent with no table and draws on the camera.[^cam3] So its index goes into the plane as it is. A 4-bit
  picture with no table uses the layer's palette entries 0 to 15.[^inf1] The exact colours were not measured.

**Making your own.**[^inf2]

1. Encode the rows as runs. Split a run at 16 pixels and at each row end.
2. Add the 4-byte stream header and the 24-byte picture header.
3. Put it anywhere in memory and pass header + 24 to `gpiDrawBitmap`.
4. Pick colours through the table, or choose indices that match the screen's palette entries 0 to 15.

The stream format is the same as the GUI's (`0x0a` 4-bit runs, `0x0b` 12-bit tokens, see
UI drawing lessons), at any address. Our own 4-bit pictures are not yet
drawn in om-emu or on the camera.[^inf2]

**om-emu.** Stock om-emu refuses a run-length bitmap sent without a table (error BMP_LUT in `emu/src/dev/engine.mjs`
cmdBitmap). So 4-bit pictures such as the grid were missing from its shots before our patch 0004. The patch draws them,
with the index straight into the plane when there is no table, and the loaded table with bit 11. With it, the grid
draws in om-emu.[^emu4]

### Text

**`DrawText`** draws a string in the camera font. The name is om-emu's E143 name, and its port table maps it to
E137.[^fw1][^emu1]

- Arguments: d0 = style, d1 = UTF-16 string (NUL-terminated), a0 = text context ("gc"), a1 = box `{x0, y0, x1, y1}` as
  four halfwords. Native call frame `[d2,d3,a2,a3] 252`.
- Style (24 bytes): colour u32, two words `0x10`, `0x10`, h-align byte, v-align byte, margins (4 halfwords at +14) and
  an edge colour byte at +22.
- The GUI's menu text context draws into layer 2 buffer 0.
- Inside the start and end bracket, then an update, four lines of our own text drew in the camera font on the shooting
  screen.

**Colours.** The font is antialiased, and the colour picks a ramp in the layer's palette.[^emu1]

- Colour 5 drew clean blue. Colours 1, 10 and 12 drew with odd fringe colours on layer 2, which has only 64 settable
  entries.
- `ÄÖÜ äöü ß` and `→` did not draw in the English font. The line stopped or showed a substitute.
- Pick colours whose ramp is set, or set your own ramp with `GPISetPalette`.

**Clean white text on the shooting screen.**[^emu1][^inf1]

1. Call `GPISetPalette` on **layer 2** (halfword layer number 2 in the object, as for layer 1), entries 60-63, with
   white, black at 78%, amber and cyan.
2. Call `gpiUpdateDisplay`.
3. Call `DrawText` with colour 60 and edge 61.

That gives crisp white text with no fringes. Colour 2 without its own ramp drew white with rainbow fringes, because its
antialias steps use neighbouring entries. The two full-height lines at x = 40 and 680 that show on this screen in
om-emu are the stock 4:3 frame edges (the default 4:3 aspect on the 3:2 panel), not a side effect of drawing.

**Underneath.** `DrawText` renders each glyph into a glyph cache (descriptor `{w, h, data, 4, size}`, 4 bits per
pixel). It then calls `gpiDrawCharactor` once per character with a glyph record (colours at +2/+4/+6, glyph descriptor
at +28). A captured record replayed at new positions redrew the same glyph. Use `DrawText`, not the per-glyph
call.[^fw1][^emu1]

### Limits

- **No diagonal or curve primitive.** The engine has fill, copy, bitmap and palette commands only (see
  [Graphics pipeline](graphics-pipeline.md#osd-drawing-engine)), and `gpiDrawOsdLine` takes a box, not two end
  points.[^fw1][^emu1]
- A sine curve of 150 dots drew cleanly. Anything round or slanted is dots or short bars, a pre-made picture, or the c3d
  layer. Each dot or bar is one request, so keep counts modest.[^emu1]
- A rectangle request returns non-zero in the gpi wrapper even when it drew. It then logs "gpiDrawOsdRectangle Error
  nWidth...". Treat that log as noise.[^emu1]

## Showing it, double buffering and animation

Each layer has buffers 0-3. The GUI draws in one pair and shows the other.[^fw1][^emu1]

- `gpiUpdateDisplay(0)` shows the buffer index held in a RAM word (0 on the shooting screen). `gpiUpdateDisplay(1)`
  shows the other one (index xor 2).
- It switches all three layers at once, through OSDControl.
- With display sync on (the E-M5 III default) the switch waits for the next live-view frame.

**Animation recipe.**[^emu1]

1. Draw frame n into buffer 0 (n even) or 2 (n odd) of your layer.
2. Erase the old shape in that buffer with colour 127.
3. Call `gpiUpdateDisplay(0 or 1)` to show it.

A 12-frame moving box on layer 2 ran this way with the stock GUI untouched. The other layers flip too. So this only
suits screens whose layers 0 and 1 hold the same picture in both buffers, which is true on the shooting screen in
om-emu.

**What drives the frames.** A one-shot GUI timer `(d0 event, d1 ms)` is re-armed on every tick. The stock curve screen
uses event 532 every 100 ms, and our live histogram does the same. Each tick then sends a child redraw request
`(a0 child, d0 1, a1 0)`.[^cam2] See also: UI drawing lessons.

**Mixing with the c3d layer.** The OSD commit (display command 17) and the c3d layer flip (command 18) are handled one
after another by the display task. c3d sends 17, then 18. Both write latched VSC registers that apply at the next frame
boundary, so updates queued together should land on the same frame.[^fw1][^inf1] Nothing locks them together, and the
OSD side also waits for the live-view sync.

**Limits on a live screen.**

- How fast it can go on the camera (engine time per request, commit at the live-view rate) is not measured.[^inf1]
- One-off drawing does not last on a live GUI screen. The screen's next own redraw and update replaces it. On the
  profile editor (status-118 histogram timer every 100 ms) a panel shown right after our update was gone 300 ms later.
  Draw from the screen's redraw path, or redraw after each GUI update.[^emu7]
- Our drawing on layers 0 and 1 is overwritten whenever the GUI redraws that area. Layer 2 is not touched by the
  shooting screen in om-emu.[^emu1]

## Input

**Keys and dials** reach a screen as control events: UP `0x9004`, DOWN `0x9006`, rear dial `0x9031`, front dial
`0x9032` and OK-hold `0x903e`.[^cam2] See also: UI drawing lessons, input.

### Touch

**The E-M5 III driver.** Gestures (tap, double tap, long press, slide, flick) are decided in the touch controller at
I2C `0x48`. The driver maps its codes to gesture bits and filters them. It has no tap timing, so the 150 ms and 800 ms
figures below are om-emu's model.[^fw3] See also: [Small devices, touch panel](small-devices-technical.md#touch-panel).

**om-emu's reading** of the E144 family, which includes the E-M5 III. Our addresses for these om-emu facts are not yet
mapped.[^emu5]

- The panel controller at I2C slave `0x48` reports up to two points. The driver passes one touch on, in rear panel
  pixels 720 × 480. They are flipped to 719 - x, 479 - y only for the swivelled monitor.
- The camera layer turns them into touch kinds TOUCH, LONG TOUCH, RELEASE, TAP, DOUBLE TAP, SLIDE and FLICK (HFW
  statuses 225-230, 300). The GUI gets message **`0x9100`**.
- A tap is shorter than 150 ms. A double tap is a second tap within 800 ms.
- The SDK class `TouchPanel` has `startTouchPanel`, `endTouchPanel`, `ctrlTouchPanelEvent`, `getTouchPanelState`,
  `getTouchNumber`, `getTouchPanelHistory`, `isTouchDetection` and `ctrlTouchPanelArea`.[^fw1]

**Into the GUI.** `sendEvent(a0 0, a1 message)` posts a touch. The message is 8 words
`{107, 0, kind, x, y, 0, 0, 0}`.[^fw1][^emu1]

- 107 is the E-M5 III's index of `0x9100`. E143 uses 109.
- Kinds: 1 TOUCH, 2 LONG TOUCH, 3 RELEASE, 4 TAP, 5 DOUBLE TAP, 6 SLIDE, 7 FLICK.
- Posted in om-emu on the shooting screen, TOUCH at (90, 30) lit the Wi-Fi and Bluetooth icon box light grey. The TAP
  that followed put it back, as on the OM-1.

**The GUI's touch filter.** It reads the screen's area lists through a table. It logs "[GuiTouch] Area Not Found!" when
nothing matches.[^fw1]

- Each area is 16 bytes: `{x, y, w, h}` halfwords, +8 a hit-test function or 0, +12 an action (255 = none).
- With no function it tests the point against the rectangle.
- A match sends the area's action on.

**Touch route into a screen.** These come from om-emu runs on a test image.[^emu6]

1. GUI message 107 reaches a handler that reads the touch handler object. A null object means the touch is dropped.
2. Otherwise, by kind, it calls the object's vtable: +4 TOUCH, +8 LONG, +12 RELEASE or FLICK, +16 TAP, +20 DOUBLE TAP,
   +24 SLIDE.
3. The shooting screen's object reads setting 1137, then runs the touch dispatcher, then the filter, then the screen's
   areas.

In the profile editor (gui `SS_REC`/`ID_ST_SETVAL`) the touch handler object is **0**. A posted touch reaches no screen
code at all. Our editor's control hook and the key handler see only their usual events.[^emu6]

- So stock menus get no touch. A touch feature on a menu page needs its own hook below the GUI, on the HFW touch
  callback or on the post of message 107, that passes x and y to our page while it is open.
- Whether the panel driver still reports while a menu is up (the gesture mask word) needs a camera probe.

**A touch button of our own** is a box (and text) on layer 2, plus one of two things. Either an area entry in our
screen's list, so the GUI hit-tests it and sends its action, or a hook on `0x9100` for our screen that tests x and y
itself. It has not been built on the camera.[^inf1]

## Other cameras

The same gpi calls exist with byte-identical code in every body checked: rectangle, line, dot, block copy, bitmap and
order. Start, end and update differ only in addresses. Each was drawn in om-emu with the same three boxes.[^fw1][^emu1]

| body | drawn in om-emu |
|---|---|
| E-M5 III 1.7 | yes, 3 layers |
| OM-5 1.2 | yes, 3 layers (order code 2) |
| OM-5 II 1.1 | yes, 3 layers |
| E-M1 III 1.6 | not run (no om-emu firmware set-up) |
| OM-1 1.9 | layer 0 yes. Layer 1 box not seen |
| OM-1 II 1.3 | nothing seen yet |
| E-M5 II 4.1 | yes, 3 layers. No update call found |
| PEN-F 4.1 | yes, 3 layers. No update call found |
| E-M5 (Mark I) 2.3 | can't run, not in om-emu. No `gpiDraw*` names |

*The gpi calls across bodies. Each body's addresses are in the [address reference](#other-bodies-addresses).*

- The OM-1 family keeps 4 buffers for layer 0, 2 for layer 1 and 1 for layer 2, seen as holes in the pointer table.
  So their buffer indices differ from the E-M5 III's.[^emu1]
- **E-M5 II and PEN-F** have the same chip. The rectangle call has the same arguments as on the E-M5 III, inside the
  same start and end bracket.[^fw1][^emu1]
    - They keep 3 layers × 2 buffers as 16-byte VRAM records `{addr, plane, 896, 600}`, in plane order
      OSD1/OSD1/OSD2/OSD2/OSD3/OSD3.
    - Buffer 1 of each plane is the one on screen, so drawing into it shows with no update call. Pass the record
      address as vinfo.
    - Neither has a `gpiUpdateDisplay` string.
    - They ran on the runtime image dumped from om-emu, because their blocks are compressed.
- **E-M5 II 4.1** has the same `gpiDrawOsd*` calls and the DMP OpenVG names, so this page's method applies with new
  addresses.[^fw1]
- **E-M5 (Mark I) 2.3** has `drawOsdStart`, `drawOsdEnd` and `GPISetPalette` but no `gpiDraw*` names and no OpenVG. A
  GPU exists (`play_gpu.c`). om-emu has no E-M5 I support, so nothing was drawn. These are string-level facts
  only.[^fw1]
- The OM-5, OM-5 II and E-M1 III addresses are in the expanded images. Their gpi strings are in their compressed
  parts.[^fw1]

See also: [Older bodies](../bodies/comparison-technical.md#older-bodies-e-m5-ii-and-e-m5-mark-i), the full
comparison.

## Open questions

- Run a layer-2 overlay on the camera: boxes over live view, then the animation recipe from a timer.
- `gpiDrawBitmap` with w and h other than 0 (scaling?). `DrawText` on the camera (text context address, colours).
  Which fonts hold accented letters.
- Frame rate: the engine time per request and the real flip rate with live view.
- Touch: where an action number from an area goes, and a touch button of our own on the camera.
- OM-1 layer 1 (likely om-emu's kind-1 compositor) and OM-1 II: why the boxes don't show.

## Address reference

E-M5 III 1.7 block0 addresses unless a body is named.

| GUI layer | pointer table (4 entries) | records, shooting screen (16 B each) | buffers (`0x83400` B each) |
|---:|---|---|---|
| 0 | `0x6230de68` | `0x621d9674` | `0xafbe6000` |
| 1 | `0x6230de78` | `0x621d96b4` | `0xaf9d9000` |
| 2 | `0x6230de88` | `0x621d9634` | `0xafdf3000` |

*GUI layer tables and buffers.*

| item | address |
|---|---|
| `GPIInitPlatform` (fills the pointer tables) | `0x60c93eee` |
| VSC OSD1 (stacking order) | `+0x1a4` |
| `GPISetOsdOrder` | `0x60c95b1b` |
| `gpiSetDrawOffset`, `gpiClearDrawOffset`, `gpiGetDrawOffset` | `0x60c963b1`, `0x60c963d9`, `0x60c963f8` |
| draw offset (x, y) | `0x61ea1ef8`, `0x61ea1efa` |
| palette strings | `0x61101748` and up |
| `GPISetPalette` | `0x60c94f90` |
| OSDControl `setColorPalette` (colour), opacity setter | `0x607f58c9`, `0x607f5971` |
| settable entries per layer table | `0x60ea5c78` |
| palette banks per OSD plane q | `0x9c000800` + `0x800` × q, and the same + `0x200` |
| bank select (bit 4) per plane q | `0x9c000364` + 8 × q |

*Layers and palettes.*

| item | address |
|---|---|
| OSDControl `drawOsdStart`, `drawOsdEnd` | `0x607f6de0`, `0x607f6e55` |
| `gpiDrawOsdDot`, `gpiDrawOsdLine` | `0x60c95123`, `0x60c951f0` |
| `gpiDrawOsdRectangle`, `gpiDrawOsdBlockCopy` | `0x60c952fb`, `0x60c9540a` |
| `gpiDrawBitmap`, `gpiDrawCharactor` | `0x60c95576`, `0x60c95682` |
| `gpiUpdateDisplay`, shown buffer index | `0x60c9588b`, `0x61ea1ecc` |
| OSDControl display switch | `0x607f5a01` |
| request queue function, engine state words | `0x60c1db46`, `0x621d95b4` (= 1), `0x621d95b6` (= 0) |
| `osddraw` `exec_rect`, queued by | `0x60c1f252`, `0x60c1b887` then `0x60c1db46` |
| `exec_start`, `exec_end` | `0x60c20032`, `0x60c2004e` |
| GUI display-list executor (builds remap tables) | `0x60c94a86` |

*Draw calls.*

| item | address |
|---|---|
| GcCreate | `0x60c92194` |
| gc for a GUI object | `0x60c88a97` |
| set device, set clip | `0x60c92747`, `0x60c92295` |
| set foreground, set colours | `0x60c925b7`, `0x60c92389` |
| colours helper (d0), background setter | `0x60c92459`, `0x60c9226c` |
| pen size, +54 mode, set font | `0x60c92678`, `0x60c9239a`, `0x60c92692` |
| colour mapping when +660 is 1 | `0x60c923b2` |
| `DrawText`, `DrawTextById` | `0x60c89f5b`, `0x60c89f43` |
| polyline | `0x60c8ebd9` |
| picture table word (value `0xa37c9b38`), lookup | `0x61eb7628`, `0x60c934bb` |
| menu text context (draws into record `0x621d9634`) | `0x621fd480` |

*gc library, pictures and text.*

| item | address |
|---|---|
| one-shot GUI timer | `0x60e1cc60` |
| child redraw request | `0x60c8799f` |
| display task OSD commit, c3d flip handling | `0x60190274`, `0x601903d7` |
| c3d sends 17 then 18 | `0x60c255c3` |
| key handler body | `0x60d540de` |
| `TouchPanel` names | `0x60ab378c` and up |
| touch init, touch task, TP_OPEN | `0x60197420`, `0x60197536`, `0x6019779c` |
| gesture mask TP_MASK, mask word | `0x60197925`, `0x62105d3c` |
| HFW touch callback (gesture to status 225-230/300) | `0x608744a0` |
| `sendEvent` | `0x60d539e0` |
| GUI touch filter, "Area Not Found" string | `0x60e2dbed`, `0x6110e776` |
| area list table | `0x6110e548` |
| rectangle hit test | `0x60c937c9` |
| message 107 handler, vtable calls | `0x60e1b4a9` and up, `0x60e1b4c0` to `0x60e1b52a` |
| touch handler object pointer | `0x61ebae9c` |
| shooting screen's object, its handler | `0x61aeb8a0`, `0x60e39345` |
| touch dispatcher | `0x60e39c08` |
| our profile editor's control hook | `0x60bf156a` |

*Timing and input.*

### Other bodies addresses

| body | rect | update | start / end | layer pointer table |
|---|---|---|---|---|
| E-M5 III 1.7 | `0x60c952fb` | `0x60c9588b` | `0x607f6de0` / `0x607f6e55` | `0x6230de68` |
| OM-5 1.2 | `0x60d52e49` | `0x60d534c7` | `0x6088a21a` / `0x6088a28f` | `0x62319a48` |
| OM-5 II 1.1 | `0x60d54d22` | `0x60d55352` | `0x6088aa3b` / `0x6088aab0` | `0x62353b4c` |
| E-M1 III 1.6 | `0x60cfb2a3` | `0x60cfb921` | `0x60844c49` / `0x60844cbe` | `0x6233f0c8` |
| OM-1 1.9 | `0x610ddeda` | `0x610de50e` | `0x60b0a7a7` / `0x60b0a81c` | `0x62b3dfdc` |
| OM-1 II 1.3 | `0x610eaf3f` | `0x610eb573` | `0x60b1559d` / `0x60b15612` | `0x62b96214` |
| E-M5 II 4.1 | `0x60baf748` | none found | `0x606f0a01` / `0x606f0a57` | records `0x618c56a4` |
| PEN-F 4.1 | `0x60bccf1b` | none found | `0x606e25f4` / `0x606e264a` | records `0x618eb390` |

*gpi addresses by body.*

| body | OSD1 record | OSD2 record | OSD3 record |
|---|---|---|---|
| E-M5 II 4.1 | `0x618c56b4` | `0x618c56d4` | `0x618c56f4` |
| PEN-F 4.1 | `0x618eb3a0` | `0x618eb3c0` | `0x618eb3e0` |

*On-screen VRAM records (buffer 1 of each plane) on the E-M5 II and PEN-F.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware, 2026-11-21.
[^fw2]: Read in the firmware, 2026-11-22.
[^fw3]: Read in the firmware, 2026-11-25.
[^emu1]: Drawn in om-emu on the E-M5 III 1.7 image (or the named body), with the firmware's own code running natively and om-emu's display model composing the picture, 2026-11-21.
[^emu2]: om-emu's reading of the firmware, facts only, 2026-11-21.
[^emu3]: Seen in om-emu with our IMG2 patch, 2026-11-21.
[^emu4]: Seen in om-emu, 2026-11-22.
[^emu5]: om-emu's reading of the E144 family, which includes the E-M5 III, facts only, 2026-11-21. Touch names read in the firmware the same day.
[^emu6]: Seen in om-emu on a test image, 2026-11-23.
[^emu7]: Seen in om-emu with the profile editors, 2026-11-21.
[^cam1]: Seen on our E-M5 III: the profile editor labels draw over the colour wheel.
[^cam2]: Seen on our E-M5 III in the profile editors.
[^cam3]: Seen on our E-M5 III: the tone-curve grid draws, 2026-11-22.
[^inf1]: Inferred, 2026-11-21.
[^inf2]: Inferred, not yet drawn in om-emu or on the camera.

