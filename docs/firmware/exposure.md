# Exposure and white balance

<!-- human page -->
<!-- house style -->

## Key points

- Exposure has its own code module, with one task for live view and movies and another for still photos.
- Live view takes its shutter speed, ISO and frame rate from fixed tables called program lines.
- White balance for live view and movies runs on the third processor core (CPU2).
- The OM-5 II uses the same live-view tables and adds four more for dark scenes.

The camera measures how bright the scene is. It then picks a shutter speed, an ISO and an aperture. It also decides
how warm or cool the colours should be. This page explains where the E-M5 III does each of these steps.

Everything here comes from reading the firmware. Nothing was tested on the camera.

## Parts

- **Settings.** Metering mode, exposure compensation, Exposure Shift, the Auto ISO limits, anti-flicker and white
  balance are ordinary settings. One function copies them all into the exposure code's input.
- **Live-view exposure.** A task called EXP_MOVIE meters every live-view frame and picks the next exposure.
- **Still exposure.** A task called TAKE_EXPOSE meters at half-press and fixes the exposure for the photo.
- **White balance.** A task called WB_MOV handles live view and movies. Still photos get their white balance in the
  recording step after the shot.
- **Flash.** Flash metering has its own code. The task called STB_SEQ is the flash ("strobe") sequence. Older notes
  called it a standby sequencer. That was wrong.

## Metering

The image pipeline adds up brightness in 18 by 18 blocks for each frame. The exposure code reads that grid.

From the grid it works out one brightness value for each method. There is one for ESP (the evaluative mode), one
for the centre, one for the surround, a spot value, two averages and an ESP value that ignores faces. The camera
stores each of them as a setting-like value, so other parts of the firmware can read them.

The metering mode you pick decides which value is used. Exposure Shift in the custom menu adds a fixed offset per
metering mode.

The averaging uses fixed weight maps. Each map gives every block a class from the edge to the centre. Centre blocks
count about three times as much as blocks near the edge. The outer ring counts very little.

The weight also depends on brightness. A block that is much brighter than the rest gets extra weight. A block that
is much darker gets less weight. Blocks within two stops of the reference keep their normal weight.

The likely effect is that bright areas pull the exposure down, so highlights are less likely to clip. That effect is
our reading, not something traced.

The OM-5 II uses the same maps and weights.

## Live-view exposure

Live view uses fixed tables called program lines. Each table says which shutter speed and ISO to use at each
brightness level. The exposure code walks along a program line until it reaches the measured brightness. Then it reads
off the shutter speed and the ISO. The aperture stays open in live view.

The most common table works like this. The values come from the firmware, and what they are for is our reading.

1. In bright light the ISO stays at 200 and the shutter gets faster.
2. Around 1/250 s the ISO starts to rise instead.
3. In dim light the shutter drops to 1/100 s and then 1/50 s. Those speeds avoid flicker under 50 Hz lights.
4. At the dark end it reaches ISO 25600 at 1/30 s.

The tables also set the live-view frame rate. Live view runs at 240, 120 or 60 frames a second depending on light.

High ISO in live view is split into real sensor gain and extra digital gain. Each table caps the real sensor gain, for
example at ISO 3200. Anything above the cap is added digitally, up to three stops.

## Photo exposure

At half-press the still task meters again and computes shutter, ISO and aperture for the photo. The results go into
three stored values. The shooting sequence copies them when the photo starts. It then sends them to the sensor and
the lens.

Photos do not use a fixed curve. Each shooting mode has a template of limits. The limits cover the lowest and highest
ISO, the shutter range and the aperture range. Some limits are fixed numbers. Others are filled in at run time from
your Auto ISO range and the lens.

The firmware builds a program line from the template. It then finds where the measured brightness falls on that
line. On one part of the line it splits the change evenly between shutter and aperture. ISO is rounded to third
stops.

Program shift moves exposure from one value to the other by the same amount. Both values then stay inside the
template limits. Shift applies only in the modes that support it.

The OM-5 II has the same 65 templates. Its ISO and aperture limits are the same. Its shutter limits are filled in at
run time instead of being fixed numbers. The change is in the firmware. The reason for it is our guess.

## White balance

The pipeline has two statistics blocks for white balance. The firmware keeps a set of red, green and blue gains for
every frame. It also keeps two reference sets, for 5300 K daylight and 7500 K shade.

Live view and movie white balance run on CPU2, the third processor core. Keep warm colour is read there too. Still
photos get their final gains in the recording step. That this step also runs on CPU2 is our guess.

The white balance task collects the settings and the statistics. It then calls a separate white balance library.
That library has a part for auto white balance and a part for another mode. It returns the gains.

Auto white balance works in a colour plane turned to follow the line of natural light colours, from warm to cool.

1. It sorts the picture's blocks into a grid in that plane.
2. It finds where the colours bunch up along the line.
3. It works out how bright the scene is.
4. In a bright scene it trusts some light-source zones less. The rule is in the firmware, and its purpose is our
   reading.
5. It averages the trusted colours and keeps the result near the line.
6. It blends the new result with the last one, so the colour does not jump.

## Flicker

Live view has an anti-flicker setting. The exposure code detects 100 Hz and 120 Hz flicker.

The camera also has a setting for flicker-free still photos. The OM-5 shows it in a menu. On the E-M5 III the code
reads the setting, but no menu item for it was found yet.

## OM-5 II

The OM-5 II uses the same tasks. Its live-view tables match the E-M5 III byte for byte. It adds four tables for dark
scenes that let live view slow down to 1/8 s.

It also moves part of the metering work to CPU2 and adds more detailed flicker detection. About half of the exposure
code was changed. The strings and code shapes show this. What the new parts do is our reading of their names.

## Status

- The module, tasks, settings and live-view tables are mapped.
- The still program line, the metering weights and the white balance call chain are mapped.
- The auto white balance steps are mapped. Which light source each reference point stands for is open.
- A read-only check with the `exp` debug commands over the Wi-Fi shell is the next step.

## Further reading

- [Exposure and white balance: technical notes](exposure-technical.md) has the tables, the settings and every address.
- [Shooting sequencer](shooting-sequencer.md) shows how a photo picks up its exposure.
- [Flash and hot shoe](../hardware/flash-technical.md) covers the flash sequence.
