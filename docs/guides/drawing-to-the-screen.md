# Drawing to the screen

*Guide 18 · E-M5 III firmware 1.7 · accepted 2026-11-20. New to these guides? Read
[Before you start](before-you-start.md) and [Live view](live-view.md) first. Open questions:
research gaps.*

This guide explains how the camera puts menus, icons and the colour wheel on the rear screen and in the viewfinder.
There are two drawing systems. The **GUI layers** carry almost everything you see: a 2D engine draws them, and the display
controller lays them over the live picture. The **c3d layer** is used only by the colour-wheel editors and is drawn by a
small vector-graphics GPU. The second half follows the Color and Mono Profile editors we added, which use both.

We are on firm ground with the GUI layers: we have added screens, pictures and sliders, and they work on the camera.
For the c3d layer we know how to start it, feed it and get its picture on screen, but so far we have only run existing
renderers through it. **More on the GPU is coming soon:** separate research will map the GPU itself, and this
guide will grow when it reports.

## The shape of it

```
GUI screens and widgets ──► draw requests ──► 2D draw engine ──► three 8-bit GUI layers ─┐
                                                                                           │
c3d task ──► OpenVG library ──► vector GPU ──► 256 × 256 colour layer ─────────────────────┤
                                                                                           ▼
live-view frame (from the image engine) ──────────────────────────────────► display controller ──► screen / EVF / HDMI
```

## 1. The display controller

The display controller sits at the end of every path. Each output channel (one for the rear screen or viewfinder,
one for HDMI) has six planes: three picture planes (the first is live view) and three GUI planes on top. The controller
reads each plane from memory, scales it, stacks the GUI planes over the picture and sends the result to the panel. Its
built-in histogram, highlight warning and focus peaking also work here, on the displayed picture, not on raw data.

The CPU never copies a live-view frame. The image engine writes it to memory, and the driver points the first picture
plane at it, once per frame.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| display controller registers | 0x9c000000 + channel × 0x4000; channel 0 rear screen or EVF, 1 HDMI | [code] |
| six planes, latched at the frame boundary | IMG1-3, OSD1-3; enables at +0x30 | [code] |
| live-view plane address | set every frame by 0x60194e50; copy in RAM 0xa26538c4 + channel × 0xe28 | [code] |

Sources: [graphics pipeline](../hardware/graphics-pipeline.md), [display and OSD](../hardware/display.md).
</details>

## 2. The GUI layers

The menus, the shooting information, icons and text all live in three GUI layers. Each is a buffer of 896 × 600 pixels
at one byte per pixel. A pixel is a colour number, looked up in a 128-entry palette per layer, and one number means
"transparent", so the live picture shows through. Each layer has several buffers, so the GUI can draw into one while
another is on screen.

The viewfinder gets a 640 × 480 drawing that the controller scales up to the panel. The rear screen shows its part of
the buffer at 1:1.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| layers | pools 0x0b00 / 0x0c00 / 0x0d00, 4 × 896 × 600 bytes each | [code] |
| palette | 128 entries per layer, index 127 transparent, colours stored as YCbCr with alpha | [code] (om-emu) |
| EVF scaling | 640 → 1024 | [code] (om-emu) |

Sources: [graphics pipeline: OSD buffers and palettes](../hardware/graphics-pipeline.md#2-osd-buffers-and-palettes).
</details>

## 3. The 2D draw engine

The GUI doesn't set pixels itself. Its drawing library turns each request (fill a rectangle, copy a block, draw a
bitmap or a run of text) into a command for a hardware 2D engine, queues the commands in a list, and starts the engine
on the list. The engine has only a few commands: fill, copy, bitmap and palette lookup. There is no line command, so a
line is drawn as thin fills.

A typical menu page redraw is about 125 bitmaps (glyphs and icons), a dozen copies and one fill. When the GUI is done,
it asks the display task to show the new buffers. That happens at the next live-view frame, so the GUI and the picture
change together.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| 2D engine | registers 0x9c100000: list base +0x18, start +0x24, status +0x04 | [code] |
| commands | 0x10 fill, 0x20 copy, 0x30 bitmap, 0x40/0x41 palette, 0x60 bitmap 2, 0xff end | [code] (om-emu) |
| drawing library | `osddraw` 0x60c1xxxx; dot 0x60c1f04c, line 0x60c1f13e, rect 0x60c1f252, bitmap 0x60c1f466, font 0x60c1fb0a | [code] |
| show the new buffers | `gpiUpdateDisplay` 0x60c9588b, held to the next live-view frame | [code] (om-emu) |
| a menu redraw | ~125 bitmap + ~13 copy + 1 fill | [code] (om-emu run) |

Sources: [graphics pipeline: GUI drawing](../hardware/graphics-pipeline.md#1-gui-drawing-goes-through-a-hardware-osd-engine).
</details>

## 4. Screens, widgets and pictures

Above the drawing library sits the GUI framework. Every screen (a menu page, the shooting screen, an editor) is an
object made from a table: the screen has a list of **child widgets**, and each child is described by a fixed record
(its class, its rectangle for each screen layout, and what it shows). Two widget classes do most of the work:

- **Picture widgets** show one of a few stored pictures. They have **up to eight states**, one picture each, and the
  screen's redraw code picks the state and shows or hides the child.
- **Text widgets** show strings from the language table.

Many things that look like text are pictures: the digits and signs on sliders, and labels such as "Color" and "Vivid" in
the colour editor. Pictures are stored in the graphics block of the firmware, compressed as runs of palette colours,
and found by number through a table.

Screens are found by id through a hash table with free slots, so a new screen is a new row plus a small constructor.
Keys reach the screen as events, and the screen's controls decide what each key does.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| screen table | hash 0x60eb8690, 512 slots, 298 used; lookup 0x60cb467a | [code] |
| child records | 88 bytes: class, rectangles for the 640 and 720 layouts, picture list per state | [code] + [emu] |
| show/hide, pick state | 0x60dfcd4e(child, 0/1) / 0x60dfcd72(child, n) | [code] + [emu] |
| picture widget states | 8 at most (cached at object +172) | [camera] |
| picture lookup | 0x60c934bb; header {14, w, h, 8, 0, size, data, 7}; data = 12-bit colour/run tokens | [code] |

Sources: [profile editor](../features/pen-f-profiles-technical.md#on-camera-editor), [settings and menus](settings-and-menus.md).
</details>

## 5. The c3d layer

The colour wheels (Color Creator, and our Color and Mono Profile editors) are not drawn by the 2D engine. They come from
a separate task, **c3d**, which draws with a small vector-graphics GPU. The firmware carries a standard **OpenVG**
library for it (paths, paints and images, with no shaders), with **EGL** to set up the drawing surface and a set of
extensions from the GPU's maker, DMP.

The GUI talks to c3d through a mailbox:

1. A screen that wants a wheel asks the background controller to **start** a draw kind (Color Creator, Color Profile,
   Mono Profile, ...).
2. c3d takes a work buffer, loads that kind's **texture sheets** (the wheel's artwork) and sets up its drawing surface.
3. On every key, the GUI sends an **update** with the new values; c3d's renderer for that kind redraws the wheel into one
   of two 256 × 256 colour buffers (one byte of alpha, three of colour).
4. The display side shows that buffer as its own layer, positioned where the screen layout says.
5. Leaving the screen sends **end**.

The GUI is busy until c3d answers each request, so a key press waits for the wheel.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| OpenVG + EGL library | 95 `vg*` names, DMP extensions, no shader names | [code] |
| start / update / end | background controller API 0x10308 / 0x10301 / 0x10313 → c3d mailbox 0x60041054 | [code] |
| draw dispatcher | 0x60c25ed9, nine draw kinds | [code] |
| work buffer | by draw kind (table 0x60e55a94); wheels need 10-12 MB | [camera] |
| texture sheets | block 2 graphics groups, loaded at start (0x60c27449); pixel order is the GPU's own, copied as bytes | [code] |
| draw buffers | 256 × 256 × 4 bytes, alpha first | [camera] |
| debug | user shell `c3d dbginfo` / `c3d dbgall` | [camera] |
| the GPU's registers and command format | DMP SMAPH-F at 0x9c200000, command lists at +0x10d0; opcodes not decoded ([c3d GPU](../hardware/c3d-gpu.md)) | [code] |

Sources: [graphics pipeline: c3d and OpenVG](../hardware/graphics-pipeline.md#5b-the-second-drawing-engine-c3d-and-openvg-2026-11-20),
[profile editor](../features/pen-f-profiles-technical.md#on-camera-editor).
</details>

## 6. How the two meet on screen

For a screen that uses the wheel, the GUI and the display task agree on a **layout**: which GUI layers stay on, and
where the c3d layer goes. The display side sets it up through one of two calls, one for layouts with the GUI layers and
one without. If the wrong layout is chosen, the wheel can be drawn perfectly in memory and still never appear, or appear
with the GUI layers switched off.

This was the hardest part of our editors (section 8). A memory dump showed a correct wheel in the draw buffer, and the
screen was still empty.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| layout calls | display API 0x10035 (even layouts, with GUI buffers) / 0x10043 (odd layouts) | [code] |
| layout per draw kind and device | table 0x60e57198, 240 bytes per kind | [code] |
| Color Creator | layout 4, GUI layers on | [camera] |
| `disp get` shows which planes are on | user shell | [camera] |

Sources: [profile editor](../features/pen-f-profiles-technical.md#on-camera-editor).
</details>

## 7. Drawing your own: what is known to work

| goal | way | status |
|---|---|---|
| add a screen | new row in the screen table, a copied constructor and child list | camera |
| add an icon, a label or a digit | a picture widget child with up to eight states, using stock or own pictures | camera |
| new label text that is a picture | hook the picture lookup and serve your own picture | camera |
| a slider | the stock slider pictures as children, one marker per value | camera |
| lines and boxes over live view | the drawing library's line and rectangle, from a task, after the GUI's own redraw | emulator only (2026-11-21), not yet on the camera |
| run an existing wheel renderer | start the draw kind, size the work buffer, load its sheets, pick the layout | camera |
| draw your own vector graphics with OpenVG | own renderer in a stub draw kind (CC2, MC, SC or TG): the kind-by-kind table and 7-step how-to are in [c3d GPU section 9](../hardware/c3d-gpu.md#9-the-olympus-driver-kind-by-kind-2026-11-21) | **not tried** |

## 8. Following along: the profile editors

The Color Profile and Mono Profile editors were built in this order, and each step shows one part of the system:

1. **Clone the screen.** The stock Color Creator screen was copied under a new id, with its own kinds for the two
   editors.
2. **Port the renderers.** The E-M5 III has empty placeholders for the profile wheels. The E-M1 III's renderers were
   relocated (every helper they call already exists), and the wheel artwork came from the PEN-F, the only body that
   ships it.
3. **Give c3d enough memory.** The first run failed with "not enough free area": the profile wheels need 10-12 MB of
   work buffer, not the 6-7 MB the stock table gives them.
4. **Find the missing picture.** With memory fixed, a dump showed a perfect wheel in the draw buffer, but the screen
   stayed empty. The cause was one check in the GUI that sets up the display only for the draw kinds the stock E-M5 III
   uses. Adding the two new kinds fixed it.
5. **Labels and sliders.** "Color" and "Vivid" are pictures, so new labels meant new pictures served through the
   picture lookup. The side bar and its sliders are picture widgets built from stock pictures.
6. **The eight-state trap.** A digit widget with twelve states reset the camera at the ninth value: a picture widget
   keeps only eight. The emulator read zeros there and didn't crash.

The lesson for anyone drawing on this camera: the emulator runs the GUI and the 2D engine well, but it does not run
the c3d GPU or live view, and stock om-emu skips 4-bit pictures sent without a colour table (title bars, the AF grid,
value boxes), noting it only in its error output. Our patch 0004 draws them. Check the emulator's error output before
trusting a screenshot. Anything involving the wheel or live view has to be checked on the camera, with the `c3d` and `disp`
shell commands to see what happened.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| editor screen | 0x6110, cloned from Color Creator 0x6081 | [camera] |
| renderers | E-M1 III CC2 / MC relocated into the E-M5 III's placeholders | [camera] |
| draw-kind check that skipped the display setup | 0x607f3e38 | [camera] |
| eight-state limit | 0x60cc9888 reads +172 + 4 × state | [camera] |

Sources: [profile editor](../features/pen-f-profiles-technical.md#on-camera-editor).
</details>

## How our features use this

- **The Color and Mono Profile editors** use both systems: c3d for the wheel, picture widgets for the side bar, labels
  and sliders.
- **The dev settings page** is an ordinary GUI list page, drawn by the stock list view.
- **Live ND's preview** doesn't draw anything itself: it changes the live-view frame the picture plane shows.
- **Planned overlays** (frame lines, focus or motion markers) would use the drawing library on a GUI layer.

## Checked on other cameras

Each step checked against the firmware of other bodies. Nothing is assumed: "not checked" means we don't know.

| step | E-M5 III 1.7 | OM-5 1.2 | E-M1 III 1.6 | OM-5 II 1.1 | OM-1 1.9 | PEN-F 3.1 | other projects |
|---|---|---|---|---|---|---|---|
| `osddraw` drawing library | yes | **confirmed** | **confirmed** | **confirmed** | **confirmed** | **confirmed** | — |
| c3d task | yes | **confirmed** | **confirmed** | **confirmed** | **confirmed** | **confirmed** | — |
| OpenVG library | 95 names | **confirmed** (94) | **confirmed** (94) | **confirmed** (94) | **confirmed** (95) | **different**: 8 names, older | — |
| profile wheel renderers | placeholders (we ported them) | **different**: none | yes (unused) | **different**: none | close relatives | older version | — |
| profile editor screens | none (we added them) | none | none | not checked | not checked | **yes**, the only one | — |
| wheel artwork (texture sheets) | none (from the PEN-F) | not checked | placeholders | not checked | not checked | yes | — |

"Confirmed" in the first three rows means the names are in the firmware; the code wasn't compared.
Sources: [graphics pipeline](../hardware/graphics-pipeline.md), [profile editor](../features/pen-f-profiles-technical.md#on-camera-editor),
[body comparison](../bodies/comparison.md).
