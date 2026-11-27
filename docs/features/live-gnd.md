# Live GND


<!-- human page -->
<!-- house style -->

## Key points

- Live GND does the job of a graduated ND filter inside the camera, darkening the sky while leaving the foreground alone.
- The OM-1 II has a working version, and the OM-5 and E-M5 III do not.
- The OM-1 II's gain curve lives in its image-engine program, which can't run on the E-M5 III.
- A design for the E-M5 III reuses the Live ND capture and merge and adds its own gain pass. Nothing has been built.

A graduated ND filter darkens the sky while leaving the foreground alone. Live GND does the same job inside the camera.
It shoots several frames and blends them with a strength that changes across the picture.

The OM-1 II has a working version, and the OM-5 and E-M5 III do not. This page explains how it works there, and how it could be built on the
E-M5 III from our Live ND work.

## On the OM-1 II

For a GND filter of k stops, the camera takes 2 to the power k frames, each k stops shorter than a normal exposure. For
a 3-stop filter that means 8 frames, each 3 stops shorter.

1. It adds the frames together. Because each frame is short, the bright sky does not clip.
2. It then brings the foreground back up with a gain that fades in along the filter line.

The result is a sky k stops darker than the foreground, with nothing clipped. You set the line's position, angle and
how soft its edge is, much like a real filter.

The firmware works out the line from those settings with some simple trigonometry. The gain curve itself is inside the
OM-1 II's image-engine program. That engine is a newer design and its programs cannot run on the E-M5 III.

## Other cameras

| camera | Live GND |
|---|---|
| OM-1 II | working |
| OM-5 II | menu settings only, with nothing behind them |
| OM-1 | no |
| OM-5, E-M1 III, E-M5 III | no |
| E-M5 II | no, would be a new port |
| E-M5 (Mark I) | no, very likely impossible |

*Live GND across bodies. Read in each body's firmware.*

## A design for the E-M5 III

The E-M5 III can already capture and average several frames for Live ND. Live GND would reuse that.

1. Capture the frames with the shutter speed shortened by k stops.
2. Merge them with the same image-engine job Live ND uses.
3. Apply our own gain pass to the merged raw picture, using a small lookup table for the soft edge.

The gain pass would run on the main processor, or on the ARM co-processor if that is too slow. The plan goes in steps.
A single frame with gain comes first, then 2-, 4- and 8-frame filters, then tuning and position and angle controls,
and finally the menu and live view. A 32-frame filter will not fit in memory.

Three questions are open:

- which filter width is the soft one
- where the E-M5 III's raw picture starts and how wide its margins are
- whether the main processor is fast enough for the gain pass

## Status

A design has been written from the OM-1 II's firmware. Nothing has been built.

## Further reading

- [Live GND: technical notes](live-gnd-technical.md) has the OM-1 II parameters, the gain stages already in the
  E-M5 III and the design details.
- [Live ND](live-nd.md) covers the capture and merge that Live GND builds on.
- [Image engine](../hardware/image-engine.md) explains why the OM-1 II's own programs cannot be reused.
