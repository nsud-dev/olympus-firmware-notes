# Display and live-view frames

<!-- house style -->
> **Technical reading.** The detailed version of [Live view](../guides/live-view.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

This page is about the screen side of the camera. It covers how the E-M5 III draws its menus and icons over the live
picture, where the built-in histogram, highlight and shadow warning and focus peaking come from, and where our own code
can find the current live-view frame. For the big picture, with a diagram, start with
[Graphics pipeline](graphics-pipeline.md). This page has the register-level detail.

Terms used here:

- **VSC** is the display controller, the hardware that combines picture and menus and sends them to the screens.
- **OSD** ("on-screen display") means the menu and icon layers drawn on top of the picture.
- **Live view (LV)** is the moving picture from the sensor that you see before taking a shot. The firmware calls it the
  "through image".
- **Y and C planes.** The live-view frame is stored as brightness (Y) and colour (C) in two separate planes.

Addresses are E-M5 III 1.7 block0 addresses (base `0x60021020`). VSC register offsets (`+0x...`) are per channel.
Functions, buffers and pools are in the [Address reference](#address-reference).

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred or seen in an emulator.

## Display controller (VSC)

The full register-level map, with every register, its writer, gamma, zebra, peaking, the colour blocks and other
bodies, is the [VSC register map](vsc-display-controller-technical.md).[^fw3]

The display driver is in section 1, which is always loaded early. It has a request switch for the `DISP_*` requests,
`display_update` and `display_update_through_image`.[^fw1]

The VSC registers start at the VSC base, with `0x4000` bytes per channel. There are two channels. Channel 0 is the rear
screen (TFT) or the electronic viewfinder (EVF), and channel 1 is HDMI. A selector function picks the channel.[^fw1][^fix1]

### Live-view image

`display_vscdrv_update_set_through_addr` writes the Y plane's address to DMA9 (`+0x38`) of the channel, and the C plane
to `+0x3c` for two-plane YC. Its caller then stores the Y address in a RAM word per channel, with the C address in the
next word. That RAM word is the simplest "current LV frame" pointer.[^fw1] It has not been read on the camera yet.

### Histogram

**The histogram is display hardware.** It is computed on the displayed image, after picture mode and gamma. The
functions are `hist_prm_set` and `hist_get_calc_result`, with the event `DISP_HISTOGRAM_CALC_END`.[^fw1]

- **Per channel.** The block has a 2-bit **target element** (`+0x248` bits 24-25,
  `display_vscdrv_hist_targetelement_set`). The display-layer routine takes element 1-4 (after a check) and writes
  element − 1. Each calculation returns one bin set (64, 128 or 256 bins at `+0x2c00`).[^fw2]
- The 4 elements are probably Y + R/G/B (or Y + colour difference). So an RGB histogram = 3 calculations, one per
  element. Which element live view uses, and whether the OM-5 and OM-1 do RGB, is not checked.[^inf2]
- `disp dl hst` only sets the histogram debug level. `disp histogram` and `disp hst` are empty stubs in this build (see
  the [VSC register map](vsc-display-controller-technical.md#console-commands)).[^fix3]

**RGB histograms already exist natively.** A read-only pass found these paths.[^fw2]

- The request handed to the driver carries 4 result slots, and the driver runs one element per slot. It picks element
  1-4 = the first filled slot, with a state byte.
- The app layer starts per-channel calculations (`Disp_Start_Histogram_Calculation Y/R/G/B`).
- A `GET_HISTOGRAM` command takes colour 0 = `YRGB` or 1 = `ONLY Y`, and a resolution (32 or 128).
- Playback over the communication API has `OlyHfwOpePlyCom::getHistogram` with r/g/b channel states.

The element order is most likely 1 = Y, 2 = R, 3 = G, 4 = B.[^fw2][^inf2] The same strings and paths are in the
**OM-5 1.2 and OM-1 1.9**, so this is shared Olympus and OM code, not a newer-body feature.[^fw2] Which element the
on-screen live-view histogram uses is still unconfirmed, likely Y only. An RGB live-view histogram would reuse this
path, with three extra calculations per refresh, one per element.[^inf2]

### Highlight and shadow, and peaking

**The highlight and shadow warning is display hardware too.** `display_vscdrv_set_hi_sh` sets it. By the firmware's own
register-name table, its threshold registers are **HILIGHT1-4 = `+0x250` to `+0x25c`**.[^fw1][^fix2] The thresholds are in
HILIGHT2, the colours in HILIGHT3/4, the window in AREA28-30 and the on bits in HILIGHT1. It is a two-level zebra unit
(see the [VSC register map](vsc-display-controller-technical.md#highlight-and-shadow-zebra)).[^fw3]

Edge peaking (`[EGPK]`) is also a VSC function. The names are read in the firmware. The writer is inferred.[^fw1][^inf1]

### Register names

The firmware carries a 422-entry table of VSC register names, copied to RAM at boot (`boot_copy_callback_tables`). The
word index × 4 is the byte offset.[^fw1] Some useful ones follow.

- DMA7 `+0x30` (control), DMA9 `+0x38` (Y address), DMA10 `+0x3c` (C address).[^fw1] c3d's IMG2 buffer goes to DMA10,
  so DMA9 to DMA11 may be the IMG1 to IMG3 addresses instead ([graphics pipeline](graphics-pipeline.md) 6a).[^emu1]
  This is still open.
- HIST1-3 `+0x244` to `+0x24c`, HILIGHT1-4 `+0x250` to `+0x25c`, AREA28-30 `+0x320` to `+0x328`.[^fw1]
- Don't read INTST1 (index 5), INTST2 (`0xf1`) or SRAM1/2 (`0xeb`/`0xec`). Reading them has side effects.[^fw1]

**Which displays are active.** One RAM word holds the active displays, returned by a getter. The native register dump
reads channel 0 when mask & 3 and channel 1 when mask & `0xff000004`.[^fw1]

## OSD (the GUI layers)

The GUI doesn't draw pixels itself. `osddraw` drives a **hardware OSD draw engine** with command lists of FILL, COPY,
BITMAP and LUT. The engine writes into **OSD VRAM** in DRAM, and the GUI then asks for a display update.[^fw1][^fix1]
Overview: [Graphics pipeline](graphics-pipeline.md).

**The layers.** The OSD planes come from frame pools `0x0b00`, `0x0c00` and `0x0d00` (layers 1-3), each 4 × `0x83400`
bytes. Each buffer is 896 × 600 at 8 bits per pixel (stride 896). The GUI screen of 800 × 1200 spans two
buffers.[^fw1][^fix1] Layers 1-2 use a 128-colour palette, and there is an RGB work layer (3).[^fw1]

**Drawing functions.** `osddraw` functions take one request-struct pointer in a0. They are init, exec_start, VRAM info
(by layer), **dot, line, rect, bitmap, font, copyFrame and copyAreaBlock**.[^fw1]

**Wrappers around them.**[^fw1]

- `OSDControl::*` (SDK API): initOsdControl, drawLine, drawRect, drawBitmap, getVramInfo.
- GUI: `gpiDrawOsdLine`, `gpiDrawOsdRectangle`, `gpiUpdateDisplay`. `GPIInitPlatform` sets the GUI up.

Most GUI widgets use a graphics-context library. For example `guiDrawHistogram::draw_Histogram_Parts` plots the
hardware histogram as a polyline.[^fw1]

The level gauge gets its data from `LevelCtrl::getSlope` → `OlyHfwOpeLevel::getSlope` (`Get_Slope_Roll_Pitch`).[^fw1]
The routine that draws the gauge isn't pinned yet.[^inf1]

The `disp` debug console command can already dump the OSD planes and VSC registers to the card (`OSD%d.RAW`,
`VSC_REG.bin`) and load test images (`C:\test.raw`).[^fw1]

## Other frames the CPU can read

- The face-detect input pool `0x2c00` holds 11 frames of 640 × 480 at 4:2:0 (`0x70800` bytes each). `face_dbg_*` loads
  `C:\BD_VGA.RAW` into it as a test input.[^fw1] That it carries live-view VGA frames in normal use is inferred.[^inf1]
- The display-size pools `0x0a00` (5), `0x0e00` (2) and `0x0f00` (3) each hold frames of 1920 × 1080 × 2 bytes. Which
  one normal live view uses isn't traced. So use the live-view frame pointer rather than guessing a pool.[^fw1]

## Feature uses

- **Frame lines, trap-focus or motion markers.** Draw with `osddraw` line or rect into a GUI layer, from task context
  (never from an interrupt), after the GUI's own redraw so it doesn't wipe them.[^inf1]
- **Cheap "JPEG zebras".** Retune the hardware highlight and shadow thresholds (HILIGHT2) and colours (HILIGHT3/4). The
  fields are in the [VSC register map](vsc-display-controller-technical.md#highlight-and-shadow-zebra). True raw zebras
  or a raw histogram still need raw sampling (our raw decoder).[^inf1]
- **Motion or lightning trigger.** Compare a sparse grid of Y values in the current LV frame, frame by frame.[^inf1]

## The live-view probe builds

We built a probe to answer stride, format, whether the CPU can read the frame, and how much each frame costs.

- **The probe.** A live-view probe build (on stock) hooks the display update. It logs every LV frame's Y and C address,
  the active device and a 32 × 32 Y diff. At each armed silent single shot it dumps the named VSC registers, 8 pool
  objects and 2 MB of the current Y plane to `LVPnn*.BIN`. It uses the native card API (fopen, fwrite, fclose) from
  task context.[^fw1]
- **First probe, camera run 1.** The camera reset about 1 s after the arming shot, in live view, without pressing the
  shutter.[^cam1] The only thing that changes after arming is the hook's armed path. That path does 32 × 32 uncached Y
  sampling plus tick and context calls inside `display_update_through_image`. So reading frame pixels from the
  display-update path is the prime suspect.[^inf1]
- **The second probe** keeps the hook a pure copy and does all frame reading at the silent single, writing the log
  first.[^inf1]

> [!WARNING]
> Reading frame pixels or making calls inside the display-update hook is the prime suspect for a camera reset. Until
> this is disproved, the rule is no frame reads or calls in that hook.

## Address reference

E-M5 III 1.7 block0 addresses.

| item | address |
|---|---|
| VSC registers, channel 0 and channel 1 | `0x9c000000`, `+0x4000` per channel |
| channel selector | `0x6004404f` |
| DISP request switch | `0x6017f904` |
| `display_update`, `display_update_through_image` | `0x6018fe32`, `0x601907cb` |
| `display_vscdrv_update_set_through_addr` | `0x60194e50` |
| Y plane address register (DMA9), C plane (DMA10) | `0x9c000038 + ch × 0x4000`, `+0x3c` |
| current LV frame pointer in RAM (Y, then C in the next word) | `0xa26538c4 + ch × 0xe28` |
| `hist_prm_set`, `hist_get_calc_result` | `0x60193f6f`, `0x6019450a` |
| `display_vscdrv_hist_targetelement_set` | `0x60194425` |
| element check in the display layer | `0x6018e880` |
| driver element pick, state byte | `0x6018ebdb` to `0x6018ec42`, `0x62105acd` |
| `Disp_Start_Histogram_Calculation` | `0x608dc23b` on |
| `GET_HISTOGRAM` colour argument | `0x608244cc` |
| `display_vscdrv_set_hi_sh` | `0x60194665` |
| register name table, RAM copy | `0x60253888`, `0x61e8edc8` |
| active display word, getter | `0xa2653720`, `0x60041cab` |

*Display controller.*

| item | address |
|---|---|
| OSD draw engine | `0x9c100000` |
| OSD layer pools `0x0b00`, `0x0c00`, `0x0d00` | `0xafdf3000`, `0xafbe6000`, `0xaf9d9000` |
| `osddraw` init, exec_start, VRAM info | `0x60c1ede6`, `0x60c20032`, `0x60c1f01d` |
| `osddraw` dot, line, rect, bitmap | `0x60c1f04c`, `0x60c1f13e`, `0x60c1f252`, `0x60c1f466` |
| `osddraw` font, copyFrame, copyAreaBlock | `0x60c1fb0a`, `0x60c1fd5a`, `0x60c1feb5` |
| `OSDControl` initOsdControl, drawLine, drawRect, drawBitmap, getVramInfo | `0x607f4dfd`, `0x607f5544`, `0x607f5617`, `0x607f544a`, `0x607f5796` |
| `gpiDrawOsdLine`, `gpiDrawOsdRectangle`, `gpiUpdateDisplay`, `GPIInitPlatform` | `0x60c951f0`, `0x60c952fb`, `0x60c9588b`, `0x60c93eee` |
| graphics-context library | `0x60c80000` to `0x60c93000` (approximate) |
| `draw_Histogram_Parts`, its polyline call | `0x60e1ae5b`, `0x60c8ebd9` |
| `OlyHfwOpeLevel::getSlope` | `0x60860b34` |
| face-detect input pool `0x2c00` | `0xddf7b000` |

*OSD, GUI and frame pools.*

| item | address |
|---|---|
| probe hook in the display update | `0x60190ab1` |
| card API fopen, fwrite, fclose | `0x60631f63`, `0x60631fe8`, `0x60631f6c` |

*Live-view probe.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware, 2026-11-05.
[^fw2]: Read in the firmware, 2026-11-20. Stock block0 disassembly, with the OM-5 1.2 and OM-1 1.9 images for the shared code.
[^fw3]: Read in the firmware, 2026-11-22.
[^emu1]: Seen in om-emu, 2026-11-21.
[^inf1]: Inferred, 2026-11-05.
[^inf2]: Inferred, 2026-11-20.
[^cam1]: Seen on our E-M5 III, 2026-11-05.
[^fix1]: Corrected 2026-11-05, see [History](#history).
[^fix2]: Corrected 2026-11-05. An earlier note gave other offsets, see [History](#history).
[^fix3]: Corrected 2026-11-22, see [History](#history).

## History

- 2026-11-05: we first thought there was one VSC channel each for TFT, EVF and HDMI. There are two channels.
- 2026-11-05: we first thought the GUI app in section 6 drew in software. It drives the hardware OSD draw engine.
- 2026-11-05: the GUI screen layout over the OSD buffers was corrected. The 800 × 1200 screen spans two buffers.
- 2026-11-05: an earlier note put the highlight and shadow thresholds at `+0x320`/`+0x324`. Those are AREA28/29.
- 2026-11-22: the stock shell's `disp dl hst` was thought to set the histogram parameters for a camera check. It only
  sets the debug level.
- 2026-11-22: which fields `set_hi_sh` fills was open until traced.

