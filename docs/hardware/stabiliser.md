# Image stabiliser

<!-- human page -->
> The dense reference for this page is [Image stabiliser: technical notes](stabiliser-technical.md).

The E-M5 III's in-body stabiliser moves the sensor to cancel camera shake. Small motors called voice coils move it,
and sensors measure where it is. Gyros and an accelerometer measure how the camera moves.

The main program does not run the stabiliser itself. A separate small processor does that work, and the main program
sends it commands.

## Status

- **How the main program drives the stabiliser is mapped,** including the full command set.
- **Its movement reports work as a motion sensor.** We use them to restart the Live ND preview when the camera moves.
- **The OM-5's movie "IS Level" setting is half there.** A test build for one of its levels is made but has not been
  run.

## The stabiliser processor

The stabiliser has its own processor, separate from the main chip. It runs the fast control loop that reads the gyros
and drives the sensor. The main program talks to it over a serial link.

That processor has firmware of its own, in the "LUKE" part of the update file. It uses the same family of instruction
set as the main processor (MN10300), so our usual tools can read it. It has two cores. One talks to the main processor
and reads the motion sensors. The other runs the control loop.

[The image-stabiliser controller](is-controller.md) describes it in detail.

## Commands

The main program sends numbered commands. There are 57 of them, with names in the firmware's own Japanese. The
interesting ones are:

- set the mode, centre the sensor, stop
- start stabilising, including how the work is split between body and lens
- the two High Res Shot drives, one for a tripod and one for hand-held use
- drive the sensor to a set position, at a constant speed, or rotate it

The last three are never sent by the stock firmware. Only a debug command in the camera's shell can send them. The
stabiliser's own program ignores the first of them, the drive to a set position. The constant-speed and rotation drives
are present. They are what features such as star tracking or automatic horizon correction would need.

When a cooperating lens is fitted, the "start stabilising" command tells the stabiliser what share of the correction the
lens will do. With any other lens, the body does all of it.

The command numbers shift between cameras. The OM-5 lacks one command, so its numbers from 23 up are one lower than
the E-M5 III's.

## Movement reports

During live view the main program asks the stabiliser for a report once per frame. Each report carries two movement
values.

The OM-5 converts them into live-view pixels and uses them to restart its Live ND preview when the camera moves. The
E-M5 III has the same conversion code but never calls it in live view. We call it from a small hook. The readings are
clear.

| situation | movement per frame |
|---|---|
| camera on a table | 0 |
| held still in the hand | about 13 |
| picked up | about 250 |
| panning | about 360 |

Waving a hand in front of the lens does not change the values, so they measure the camera and not the picture. It is
still open whether they are the raw shake or what is left after the sensor has corrected it.

## IS Level

The OM-5, E-M1 III and OM-5 II have a movie setting called IS Level, with three positions. The E-M5 III does not.

Each position picks a set of stabiliser parameters. The E-M5 III already has two of the three sets, and it has the
code for the +1 level, but nothing ever asks for it. Only the −1 level is truly missing. A test build that switches on
the +1 level is made and waiting for a camera run.

## Other cameras

The OM-5's host side is almost the same as the E-M5 III's. It drops one command and adds a few parameters, such as
per-axis limits and a body/lens ratio. The two stabiliser firmwares differ in 42% of their bytes. Most of that is
code that moved. The OM-5's program handles the same commands with the same code, minus support for early prototype
boards.

## Further reading

- [Sync IS with Panasonic lenses](../features/sync-is-panasonic.md) explains why body and lens cooperation is decided by
  the lens.
- [Live ND](../features/live-nd.md) uses the movement reports.
- [Wi-Fi debug shell](../features/wifi-debug-shell.md) is where the stabiliser's debug command lives.
