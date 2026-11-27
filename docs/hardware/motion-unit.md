# Motion search unit

<!-- human page -->
<!-- house style -->

## Key points

- The motion search unit compares small blocks of the live-view picture between two frames and reports how far each
  block moved.
- Many parts of the camera share it, and their jobs wait in one queue and run one at a time.
- Tracking autofocus follows each subject area with at most nine blocks, a limit set by the tracker's software, not by
  the hardware.
- The unit is separate from the image engine that runs the subject-detection network.

This page explains a small piece of hardware in the camera's processor that measures movement between live-view frames.
The firmware calls it EMS1. Tracking autofocus depends on it, and so do several other features. Most of this page comes
from reading the OM-5 II firmware. A first log on our E-M5 III using test firmware checked part of it.

It is a fixed-function unit. It does one job very fast and cannot run a program. The stock E-M5 III, the E-M1X and the
OM-5 II all have it at the same place in the processor.

## Function

The unit takes a small copy of the live-view picture. It cuts an area into blocks. Each block is a multiple of 8
pixels wide. For every block it tries positions in the next frame, up to about 64 pixels in each direction, and keeps
the best one.

For each block it returns three things. The first is the movement left or right. The second is the movement up or
down. The third is a score for how good the best match was. It also returns some flags the software uses to decide
whether to trust the block.

## Users

| user | what for |
|---|---|
| flicker detection | finds the stripes that flickering lights cause |
| scene detection | helps the automatic scene modes |
| tracking autofocus | follows the subject's blocks from frame to frame |
| camera-motion estimate | separates the subject's movement from the camera's |
| motion autofocus helper | gives C-AF a sense of how the subject moves |
| subject detection | a search step next to the network |
| two image-pipeline and AF jobs | not identified yet |

*Parts of the camera that use the motion search unit, read in the firmware.*

All these jobs go into one queue. When the unit is free, it takes the next job, loads its settings and runs it. Each
job brings a full set of settings, so the unit does not have to remember anything between jobs.

## Tracking

For tracking, the firmware asks for three areas around the subject. Each area has at most three by three blocks. That
is a small sample. A small or distant subject, or one that changes shape, gives only a few blocks that the tracker can
trust.

The tracker combines the block movements into one movement for the subject. It then checks the colour and size match
from the second unit and decides where the subject is now.

## Limits

The nine-block limit comes from how the tracker stores its data, not from the hardware. The unit handles bigger grids
for other jobs. The unit also has nothing to do with the subject-detection network, which runs on the image engine.

So a better tracker could ask the unit for more blocks, or add a network on the image engine. A second network would
share the image engine with subject detection. Today one pass of the subject-detection network takes about 60
milliseconds on the camera.

## Results between network passes

The unit's results can help follow a subject between two passes of the subject-detection network.

- The unit's raw results go to buffers that the camera hands out fresh for every frame and frees again. Added code
  should not read those.
- Two parts of the camera keep their own copies at fixed places, and added code can read those safely.
- Tracking autofocus keeps how far each tracked area moved in the last frame, and where the subject is now.
- The motion helper for C-AF keeps a four by four grid of movements around the AF point.
- Both are updated once per live-view frame while they run.
- Our subject boxes can use these movements to follow the subject between network passes. They also make up for the
  delay between the frame the network saw and the frame on screen.

## First camera log

A first log on our E-M5 III using test firmware showed which of these run, and how often.

- Nothing runs in plain live view or S-AF.
- C-AF and tracking autofocus both start the tracker. In C-AF this may be only because our subject-detection test code
  was running.
- The C-AF motion helper did not start in any mode tried.
- While tracking runs, its window and position update at least ten times a second.
- Its per-area movements are valid in only about a third of frames. The subject position itself is the steadier signal.

## Status

Which shooting modes turn on the two fixed copies was first checked by the camera log above. A second log with a better
trigger is to measure the exact update rate.

## Further reading

- [Motion search unit (EMS1): technical notes](motion-unit-technical.md) has the driver, the registers, the result
  format and the addresses.
- [Autofocus and tracking AF](../features/autofocus.md) covers the tracker that uses the unit.
- [Image engine](image-engine.md) covers the hardware that runs the subject-detection network.
