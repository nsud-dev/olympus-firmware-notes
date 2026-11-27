# Feature ideas

<!-- human page -->
<!-- house style -->
> The dense reference for this page is [Feature ideas: technical notes](ideas-technical.md).

## Key points

- These ideas are not projects yet, and they come from the camera's hardware, other camera makers and small shooting tweaks.
- Most of the cheap ideas reuse Live ND's averaging of several raw frames on the image engine.
- Tripod noise reduction, which averages several full exposures, is the cheapest idea on the list.
- The camera's own image-engine jobs can't average, subtract or take the minimum of frames, so several ideas need a new job.

These are ideas that are not projects yet. Some are things the camera's hardware could probably do. Some come from
other camera makers or from Magic Lantern, the firmware add-on for Canon cameras. Some are small shooting tweaks.

Most of the cheap ideas reuse something Live ND already proved. The E-M5 III can hold several raw frames in memory and
average them on the image engine.

## From the image engine

- **Tripod noise reduction.** Take several full exposures and average them. Noise drops with the square root of the
  number of frames. This is the cheapest idea on the list.
- **Weighted averages.** Live ND already feeds the same frame in more than once, so mixing frames 3 to 1 or keeping a
  running average looks feasible.
- **Merging part of a frame.** This could give Live GND-style effects.

The E-M5 III's own image-engine jobs are now mapped. None of them averages, subtracts or takes the minimum of frames.
So multiple exposures in Bright or Dark mode, dark-frame averaging and median stacks would all need a new job.

Other ideas in this group include motion trails, night live view, Live Composite with noise reduction, a hand-held
night mode, 4-shot pixel shift in colour, star tracking by moving the sensor, a raw histogram, sweep panorama and
dual ISO. Dual ISO is the least feasible.

## From newer bodies

1. Tripod noise reduction, as above.
2. More focus-stacking shots. This is now done as a card mod.
3. The OM-Log400 movie profile, covered on the [movie page](movie.md).
4. Running scripts from the card through the debug shell.
5. Running Linux on the ARM co-processor from the card, to use it for heavy maths.
6. A Bluetooth remote, using the OM-5's remote code.

The OM-5 has about 1,300 setting names that the E-M5 III lacks. Most of them are renames rather than new features.

## Shooting tweaks

- **Focus-stacking shot count.** The setting exists but the menu does not offer it. See [focus stacking](focus-stacking.md).
- **AE bracketing with 9 frames.** The camera works out each frame itself. The limit of 7 frames is only in the menu
  and the on-screen display. A 9-frame option needs the menu work done first.
- **Holy-grail timelapse.** Interval shooting sleeps and restarts the camera between long intervals. So an exposure ramp
  would have to keep its state in a setting or a card file.
- **Auto ISO lowest shutter speed.** Already on the E-M5 III. Nothing to do.

## From other makers

The shortlist is raw zebras, a raw histogram with an exposure-to-the-right hint, a motion or lightning trigger, trap
focus, bulb ramping for timelapse, highlight-safe multi-frame noise reduction, tripod HDR, a manual-focus guide from the
phase-detect pixels, and automatic horizon correction by rolling the sensor.

Two things make most of these possible. We found how to draw on the screen and how to read a live-view frame. We also
found the stabiliser's command set, which includes moving the sensor to a set position and rotating it.

## Newer ideas

A ranked list of 26 newer ideas builds on what we learned later. That covers the display controller, the vector GPU,
the card loader, remote button presses and the motion vectors. It lives in the project's private notes for now.

## Other cameras

Most ideas here rely on Live ND's frame averaging. The E-M5 II would need the same new port as Live ND, and the
original E-M5 has no engine of this kind at all.

## Further reading

- [Feature ideas: technical notes](ideas-technical.md) has the shortlists, the evidence and the addresses.
- [Focus stacking](focus-stacking.md) covers the focus-stacking shot count.
- [Movie recording](movie.md) covers the OM-Log400 profile.
- [Live ND](live-nd.md) describes the frame averaging most of these ideas reuse.
