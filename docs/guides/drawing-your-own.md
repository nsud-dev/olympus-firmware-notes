# Drawing your own graphics

This guide shows how to put your own boxes, lines, curves, pictures, text and moving things on the E-M5 III's rear
screen with the firmware's own drawing calls, and how to react to a touch. It follows on from
[Drawing to the screen](drawing-to-the-screen.md), which explains the hardware: read that first if "layer", "palette"
or "2D draw engine" are new to you.

Every recipe here was run in the om-emu emulator (by the om-emu contributors, MIT licence) on the stock 1.7 firmware: the emulator
runs the camera's own code, so the firmware draws, not a copy of it. None of it has been run on the camera yet; that
is the next step. The facts and addresses for each section are on the reference page
[Drawing on the GUI layers](../hardware/osd-drawing.md).

## The shape of it

```
your code
   │  drawOsdStart
   ├─► gpiDrawOsdRectangle / Line / Dot / BlockCopy / Bitmap, DrawText   (queued, not drawn yet)
   │  drawOsdEnd        ──► the 2D draw engine runs the queue into a layer buffer in memory
   │  gpiUpdateDisplay  ──► the display controller shows that buffer from the next frame
   ▼
rear screen: live view, the c3d layer, then three GUI layers on top
```

Four rules cover most of it:

1. Every draw call goes between **start** and **end**. Outside that bracket the calls are refused.
2. You draw into a **buffer of a layer**. Nothing changes on screen until you **update**.
3. A pixel is a **palette index**, not a colour. The layer's palette turns it into a colour and an opacity.
4. The engine fills, copies and draws pictures. It has **no diagonal line, curve or circle**: those are built from
   dots or short bars.

## 1. Opening a batch and showing it

A batch starts with `drawOsdStart` and ends with `drawOsdEnd`. In between, each draw call becomes a request in a
list. `drawOsdEnd` turns the list into engine commands and starts the engine. Then `gpiUpdateDisplay` tells the display
controller which buffers to show; the switch happens at the next frame, so there is no tearing.

Starting a second batch before the first has ended is refused with a log line ("called twice"). The GUI uses the same
bracket for its own drawing, so your code should draw from the GUI's own task (for example from a screen's draw
handler or a GUI timer), not from an interrupt.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| start / end | `drawOsdStart` 0x607f6de0 / `drawOsdEnd` 0x607f6e55 | [code] + [emu] |
| show | `gpiUpdateDisplay` 0x60c9588b; d0 0 shows the current buffer, otherwise it flips | [code] + [emu] |
| refused outside the bracket | queue 0x60c1db46, error 303 | [code] + [emu] |

</details>

## 2. Where to draw: layers and buffers

The GUI has three 8-bit layers, each 896 × 600 pixels with four buffers. The rear screen shows 720 × 480 of that area.
The default order puts **layer 2 on top**, then layer 1, then layer 0, and all three above the c3d layer and live view.

- **Layer 1** holds most of the GUI: icons, menus, the shooting info.
- **Layer 0** holds dimming boxes and is empty on many screens.
- **Layer 2** is empty on the shooting screen. It is the natural place for your own overlay: you can clear it freely
  without touching the GUI's drawing.

Each call takes a "vinfo", the address of a small record describing one buffer of one layer. Pass the record for the
buffer you want to draw in. Six order codes swap the layers around if you need one in front of another.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| buffer records, 16 bytes {address, plane, 896, 600} | layer 0: 0x621d9674 + 16 × buffer; layer 1: 0x621d96b4 + 16 × buffer; layer 2: 0x621d9634 + 16 × buffer | [code] + [emu] |
| layer order | `GPISetOsdOrder` 0x60c95b1b, codes 0-5; default 3 (2 over 1 over 0) | [code] + [emu], code 3 [camera] |

</details>

## 3. Colours and see-through

Each layer has a palette of 128 entries. An entry holds a colour (as YCbCr) and an opacity from 0 (invisible) to 31
(solid). Entry 127 is transparent in every layer, so drawing with 127 erases.

Opacity blends a layer with the layers under it, not with what you drew earlier on the same layer: a half see-through
box drawn over another box on the same layer simply replaces those pixels.

The GUI loads a fresh palette for each kind of screen (shooting, menus, playback, Super Control Panel), so a colour
that is white on one screen can be something else on another. You can set your own entries with `GPISetPalette`. Pick
entries the current screen does not use: on the shooting screen, setting layer 1's entries 120-126 also recoloured the
AF frame and the grid lines, because they use those entries. Layer 0 accepts only its first 32 entries, layer 2 its
first 64, and layer 1 all of them.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| set entries | `GPISetPalette` 0x60c94f90: d0 first, d1 count, a1 array of 0xAARRGGBB (alpha stored as alpha >> 3) | [code] + [emu] |
| settable entries per layer | table 0x60ea5c78: 32 / 256 / 64 | [code] + [emu] |

</details>

## 4. Shapes

- **Box:** `gpiDrawOsdRectangle` fills a box with one palette index.
- **Line:** `gpiDrawOsdLine` takes the same arguments and also fills a box. A horizontal line is a box one pixel high.
- **Dot:** `gpiDrawOsdDot` sets one pixel.
- **Curves and circles:** compute the points yourself and draw dots, or short bars for thick lines. A sine curve of
  150 dots drew cleanly. For smooth, antialiased round shapes the c3d GPU is the better tool (see
  [Drawing to the screen](drawing-to-the-screen.md) section 5). The GPU reference has a how-to for your own drawing
  in a free draw kind: TG gives a 480 × 480 surface shown at 638 × 480 from x = 160 under the GUI layers
  ([c3d GPU](../hardware/c3d-gpu.md) section 9).
- **Copy:** `gpiDrawOsdBlockCopy` copies an area from one buffer to another, which is how you save and restore what was
  under something you draw.

Coordinates are in the 896 × 600 layer. A shape must fit inside 800 × 1200 after the GUI's draw offset is added, or
the call does nothing.

<details><summary>Where in the firmware</summary>

| call | address | arguments |
|---|---|---|
| `gpiDrawOsdRectangle` | 0x60c952fb | d0 x, d1 y, a1 width, a0 vinfo; stack: height, colour, layer |
| `gpiDrawOsdLine` | 0x60c951f0 | as the rectangle |
| `gpiDrawOsdDot` | 0x60c95123 | d0 x, d1 y, a0 vinfo, a1 colour; stack: layer |
| `gpiDrawOsdBlockCopy` | 0x60c9540a | d0 source x, d1 source y, a0 source vinfo, a1 target vinfo; stack: width, height, target x, target y, layer |

All [code] + [emu] 2026-11-21.

</details>

## 5. Pictures

The camera holds about 8,000 pictures: every icon on its screens. `gpiDrawBitmap` draws one at any position. You look
the picture up by its number in the picture table, which gives a 24-byte header; the call wants the address just after
the header, where the compressed pixel data starts. The size comes from the data.

An optional colour table maps each of the picture's colours to a palette entry of your choice. Mapping every colour to
white turned the "640" icon into a white silhouette. That is how one icon can serve as normal, highlighted and greyed
out.

Your own pictures use the same compressed format and can live at any address (see
section 3b of [Drawing on the GUI layers](../hardware/osd-drawing.md) for the format).

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| `gpiDrawBitmap` | 0x60c95576: d0 x, d1 y, a0 vinfo, a1 header + 24; stack: 0, 0, 0, colour table or 0, layer | [code] + [emu] |
| picture table | word at 0x61eb7628, + 4 × number = the header's address (lookup 0x60c934bb) | [code] + [emu] |

</details>

## 6. Text

`DrawText` is the function the menus use. It takes a style (colour, edge colour, alignment), a string in UTF-16 and a
box, and draws the string in the camera's own antialiased font. Given the GUI's menu text context, it draws on
layer 2. Four lines of our own text drew on the shooting screen this way.

Two things to know. The font's edges use a run of palette entries next to the colour you choose, so on layer 2 some
colours come out with odd fringes; colour 5 drew clean. And the English font has no accented letters or arrows (Ä, ß
and → did not draw). Text in other scripts needs the matching language font loaded.

Under `DrawText`, each character is rendered into a glyph cache and drawn with `gpiDrawCharactor`, one call per
character. Use `DrawText`; the per-character call needs a cached glyph.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| `DrawText` | 0x60c89f5b: d0 style, d1 string, a0 text context, a1 box {x0, y0, x1, y1}; native frame [d2,d3,a2,a3] 252 | [code] (om-emu's E143 map) + [emu] |
| style, 24 bytes | colour, 0x10, 0x10, horizontal and vertical alignment bytes, margins at +14, edge colour at +22 | [code] (om-emu) + [emu] |
| menu text context | 0x621fd480 (draws on layer 2) | [emu] |
| one character | `gpiDrawCharactor` 0x60c95682 | [code] + [emu] |

</details>

## 7. Animation

Animation is double buffering. Draw the next frame into a buffer that is not on screen, update to show it, and use the
other buffer for the frame after. To move something, erase it in its old place (draw colour 127 there, or copy back
what was under it) and draw it in the new place. A box moving along a sine path in twelve steps ran smoothly this way.

The flip happens at the next display frame, so you cannot go faster than the screen (60 frames a second on the rear
screen). A GUI timer is the right clock for it; the looks editors used one for a live histogram.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| double buffering on layer 2 | buffers 0 and 2, `gpiUpdateDisplay` 0 / 1 | [emu] |
| GUI timers and redraw requests | timers 0x60e1cc60, redraw 0x60c8799f | [camera] (looks) |
| flip latches at the next frame | display commit command 17 | [code] + [inferred] |

</details>

## 8. Touch and buttons

The touch panel reports up to two points to a touch task. The task turns them into gestures (touch, long touch,
release, tap, double tap, slide, flick) and the GUI receives them as a touch message with the kind and the point in
screen pixels (720 × 480).

The GUI then looks the point up in the current screen's list of touch areas. An area is a rectangle with an action
number; when the point is inside it, the GUI sends that action on. Posting a touch at the Wi-Fi icon in the emulator
lit the icon's box, exactly as a finger does.

A button of your own is therefore: a box and a label on layer 2, and either an area in your screen's list (the GUI
does the hit test) or your own handler for the touch message that checks the point against the box. Keys and dials
arrive as control events in the same way (UP, DOWN, the two dials, OK).

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| post a touch | `sendEvent` 0x60d539e0(a0 0, a1 {107, 0, kind, x, y, 0, 0, 0}); kinds 1-7 | [code] + [emu] |
| touch filter | 0x60e2dbed; area lists through 0x6110e548; area = {x, y, w, h, hit test or 0, action} | [code] |
| touch driver | init 0x60197420, task 0x60197536, open 0x6019779c, gesture mask 0x60197925 | [code] (om-emu facts) |
| key and dial events | UP 0x9004, DOWN 0x9006, rear dial 0x9031, front dial 0x9032 | [camera] (looks) |

</details>

## 9. Trying it in the emulator

om-emu can call any firmware function on a running emulated camera and take a screenshot afterwards. Our small Python
driver wraps the calls above (`start`, `rect`, `dot`, `bitmap`, `text`, `touch`, `update`), so a test is a few lines:
open a batch, draw, end, update, screenshot. The driver is in these notes' `tools/osdlab/` folder.


The emulator also runs the stock c3d vector layer under the GUI layers: the Color Creator wheel draws and redraws
on each key, so a c3d drawing can be checked the same way (see
[graphics pipeline](../hardware/graphics-pipeline.md) section 6a).

Two things the emulator does not tell you: how long the engine takes on the real chip, and whether a hook that draws
from your own code is safe on the camera. Both need a camera run.

## 10. Limits

- Three GUI layers, four buffers each, 8 bits per pixel, 128 palette entries per layer (fewer settable on layers 0
  and 2).
- No diagonal, curve or circle primitive; no blending inside a layer.
- Palettes change with the screen, so your colours can change under you.
- Text only in the loaded language font.
- Updates at most once per display frame.
- Drawing done once is not kept. When the screen redraws itself (on a timer, a key or a status change), its next
  update replaces your drawing, sometimes within 100 ms. Draw from the screen's own redraw path, or draw again after
  each GUI update.

## Checked on other cameras

| step | E-M5 III 1.7 | OM-5 1.2 | OM-5 II 1.1 | OM-1 1.9 | E-M5 II 4.1 | PEN-F 4.1 | E-M5 (Mark I) 2.3 |
|---|---|---|---|---|---|---|---|
| boxes on all three layers | confirmed | confirmed (rect 0x60d52e49) | confirmed (rect 0x60d54d22) | layer 0 only seen | confirmed (rect 0x60baf748) | confirmed (rect 0x60bccf1b) | not in the emulator |
| start / end bracket | confirmed | confirmed | confirmed | confirmed | confirmed | confirmed | names present |
| update call | confirmed | confirmed | confirmed | confirmed | different: draws straight into the shown buffer | different, as the E-M5 II | not checked |
| pictures, text, touch | confirmed | not checked | not checked | not checked | not checked | not checked | not checked |

## Credit

The emulator is om-emu, by the om-emu contributors (MIT licence). Its notes on the OM-1's text, touch and display paths gave us the names and
the shape of the text and touch calls, which we then found on the E-M5 III. The picture format and the palette
lessons come from our looks editor work.
