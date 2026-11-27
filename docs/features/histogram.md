# Histogram

<!-- human page -->
<!-- house style -->
> The dense reference for this page is the histogram part of [Display and OSD](../hardware/display.md#histogram) and the histogram section of the [display controller register notes](../hardware/vsc-display-controller-technical.md#histogram).

## Key points

- The histogram is measured by a small unit in the display controller, not by software.
- That unit sees the finished picture, so it can't show true sensor clipping.
- Live view measures brightness only, and picture review measures red, green and blue one after another.
- The firmware already supports a live red, green and blue histogram, and our experiment showed the three curves on the camera.

The E-M5 III shows a brightness histogram in live view. In playback it can also show red, green and blue. This
page explains how the curves are measured, and what a live red, green and blue histogram would need.

## Display hardware

The histogram is not computed by software. A small unit inside the display controller counts the pixels of the
picture on its way to the screen. The firmware only sets it up and collects the result.

The unit sees the finished picture, after white balance, picture mode and the
tone curve. It never sees raw sensor data. The highlight and shadow warning and focus peaking come from the same
place and have the same limit.

## Channels

The unit measures one thing per run. It has a two-bit setting that selects brightness, red, green or blue. Each run
returns one set of bins.

Live view keeps the unit on brightness all the time. It also measures the small zoom-frame area when one is shown.
That is the pair of curves you see on the INFO screen.

Picture review after a shot works differently. The firmware runs the unit four times in a row, once per channel.
That is how playback gets its red, green and blue curves.

## Live RGB histogram

The firmware already supports a live red, green and blue (RGB) histogram. The request the application hands to the driver has four result
slots, one per channel. The driver runs whichever slot is filled. A debug command even has a "brightness and RGB"
option beside "brightness only".

A live RGB histogram needs three extra measurements per refresh. The brightness measurement must be restored
afterwards. There are two difficulties.

- The stock review pass waits for its result with no time limit. Borrowing that pass from another task can leave
  both waiting forever, which freezes the controls.
- The live-view screen redraws its own curve on its own schedule. Extra curves drawn in the same box are painted
  over unless the stock drawing is taken into account.

## Colours

Each screen layer has its own palette. The colours playback uses for its red, green and blue curves are fully
transparent on the live-view layer. Curves drawn with them appear see-through. The live-view layer has its own
opaque red, green and blue.

## Raw histogram

A histogram of raw data would show true sensor clipping, which the stock histogram cannot. No stock unit can
provide it, because all of them sit after the picture has been developed.

The raw live-view frame sits in memory in a known place before any processing. Software
could sample it, split it by colour site and count the clipped pixels. The result would describe the live-view
exposure. It predicts the photo only while live view simulates the shot's exposure.

## Other cameras

The same per-channel histogram code and names are in the OM-5 and OM-1 firmware. It is shared code and not a feature
of newer bodies.

## Status

The stock behaviour is read from the firmware and seen on the camera. A live RGB histogram has been tried as an
experiment. It showed the three curves on the camera, but it does not yet run cleanly beside the stock drawing.

<details><summary>Where in the firmware</summary>

| what | where (E-M5 III 1.7) | known from |
|---|---|---|
| histogram set-up and result | `hist_prm_set` 0x60193f6f, `hist_get_calc_result` 0x6019450a | [code] |
| channel select | display controller +0x248 bits 24-25, setter 0x60194425 | [code] |
| result bins | display controller +0x2c00 | [code] |
| driver start, stop, result | 0x6018ebbe, 0x6018ec6f, 0x6018ec9a | [code] |
| application start and stop | 0x602e611a, 0x602e638e | [code] |
| live-view INFO drawing | `draw_shooting` 0x60e1a3dd | [code] |
| curve drawing | `draw_Histogram_Parts` 0x60e1ae5b | [code] |

*Histogram functions and registers in the E-M5 III 1.7 firmware.*

</details>

## Further reading

- [Display and OSD](../hardware/display.md#histogram) has the histogram internals.
- [Display controller registers](../hardware/vsc-display-controller-technical.md#histogram) has the histogram registers.
- [Live view](../guides/live-view.md) explains how the live-view picture is made.
