# Movie recording

<!-- human page -->
> The dense reference for this page is [Movie recording: technical notes](movie-technical.md).

This page covers two movie questions. The E-M5 III stops recording after 29 minutes 59 seconds, while the OM-5 records
for longer. The OM-5 also has a flat "OM-Log400" picture profile for colour grading, which the E-M5 III lacks.

The recording limit turns out to be one number in the firmware. The log profile is harder. Much of what it needs is
already in the E-M5 III, but the piece that picks the log curve is missing.

## Status

- **Recording limit.** Found and understood. A card mod that lifts it works in the emulator but has not been tried on
  the camera.
- **OM-Log400.** Researched. Nothing has been built yet.

## 29:59 limit
When a recording starts, the camera hands the movie encoder a maximum recording time in milliseconds. On the E-M5 III
that time is 30 minutes, unless the recording type is one that already gets two hours. The encoder stops when the time
runs out.

The OM-5 and OM-5 II have no 30-minute case at all. They always pass two hours. The E-M1 III and PEN-F carry the same
30-minute number as the E-M5 III.

Lifting the limit means changing that single number to the OM-5's two hours. No other limit was found in the movie
code. Three things are still unknown. The remaining-time display on screen may have its own cap. It is not known how
the camera handles the 4 GB file split on a longer recording. Heat over a long recording has not been tested either.

As a card mod, the change is made while the camera runs and undone when the menu row is switched off.

## How a movie is recorded

The sensor runs in a different mode for each movie size. 4K is a crop from the middle of the sensor. Cinema 4K uses the
full width, and Full HD reads a band of the sensor at half resolution. A fixed scaler brings each mode to the
recording size.

The encoder handles H.264 only, up to level 5.1. That level caps how many pixels per second it can take. 4K at 30
frames needs about 288 million pixels a second, and Cinema 4K at 24 needs about 350 million. There is no Cinema 4K at
30, and the same tables appear in the E-M1 III. So this looks like a limit of the processor rather than a product
decision. HEVC arrived later, on the OM-1.

## OM-Log400

A log profile records a flat tone curve. The picture looks washed out straight from the camera, but it keeps more
detail in the highlights and shadows for grading later.

On the OM-5, OM-Log400 is a picture mode. It sits next to a "super flat" mode and comes with a View Assist setting
that shows a normal-looking picture on screen while recording the flat one.

What the E-M5 III already has:

- the same picture-mode numbering as the OM-5 up to the point where the log mode was added
- the exposure code that records which contrast mode is active, filled in exactly as on the OM-5
- the image-engine data that the OM-5 most likely draws its curves from, which is byte for byte the same

What it lacks:

- the code that chooses the log curve when a movie's picture settings are built
- View Assist
- a setting and menu value to switch it on

The OM-5 slotted its log mode into the middle of the picture-mode list. A port should give it a new E-M5 III number
instead of renumbering the existing modes.

The next step is to follow the OM-5's log mode into the code that builds the picture settings. A cheap test would be to
force the existing super flat mode in a movie on the E-M5 III and see what comes out.

## Other cameras

| camera | 30-minute limit | log profile |
|---|---|---|
| E-M5 III 1.7 | yes | no, but most of the groundwork is there |
| E-M1 III 1.6 | yes | no |
| PEN-F 3.1 | yes | no |
| OM-5 1.2, OM-5 II 1.1 | no, two hours | OM-Log400 |
| OM-1, OM-1 II | no 30-minute number found | not checked here |
| E-M5 II, E-M5 (Mark I) | yes | no, and an older movie system without the groundwork |

## Further reading

- [Sensor and calibration](../hardware/sensor.md#sensor-modes) lists the sensor modes per movie
  size.
- [Color and Monochrome Profiles](pen-f-profiles.md) covers the other picture modes we added.
