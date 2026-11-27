# Focus stacking

<!-- human page -->
<!-- house style -->

## Key points

- The E-M5 III can stack focus in the camera, but only with a short list of Olympus lenses and always with eight shots.
- On our camera both limits are lifted, so stacking works with any lens and with 3 to 8 shots.
- Both changes now load from the SD card at start-up, without a patched firmware.
- The same one-byte lens change should work on the OM-5, OM-5 II, E-M1 III, OM-1 and OM-1 II, but we have not tried it.

Focus stacking takes a series of shots at different focus distances and merges them in the camera into one picture that
is sharp from front to back. The E-M5 III can do it, but only with a short list of Olympus lenses, and always with
eight shots.

Both of those limits are now lifted on our camera. This was the first thing the project changed, and it still works.

## Lens check

The lens check is one branch in the firmware. Changing it makes the check always pass, so stacking works with lenses
the camera otherwise refuses. It is flashed and working on our E-M5 III.

## Number of shots

The number of shots can be set, from 3 to 8. The count is already a camera setting, with its own saved value. The
E-M5 III has no menu row for it, and always uses eight.

## Card mods

Neither change needs a patched firmware any more. Both work as card mods. Our mod loader reads them from the SD card at
start-up, and each has an Off and On row in the camera's menu.

## Why eight is the limit

The shot count is a normal setting, and the OM-5's menu offers 3 to 8 for it. Going beyond 8 is a bigger job than it
looks. The part of the firmware that combines the frames keeps room for nine images, which is eight frames plus the
finished picture. The part that saves the result stops at nine too. The merge itself would allow up to 15 frames, so
the limit is in the bookkeeping around it, not the merging.

On the OM-5 those arrays hold 16. Raising the E-M5 III's would mean checking the compositor and the memory as well, so
3 to 8 is what is offered for now.

## Other cameras

The lens check is the same function with the same branch on the OM-5, OM-5 II, E-M1 III, OM-1 and OM-1 II, so the same
one-byte change should work on all of them. We have not tried it on any of those.

| camera | in-camera stacking | the lens-check patch |
|---|---|---|
| OM-5, OM-5 II | yes | same branch, not tried |
| E-M1 III | yes | same branch, not tried |
| OM-1, OM-1 II | yes | same branch, not tried |
| E-M5 III | yes | works |
| E-M5 II | yes | the check is shaped differently, so it needs its own work |
| E-M5 (Mark I) | no | nothing to patch |
| PEN-F | no | no in-camera stacking |

*In-camera stacking and the lens-check change on each body. Read in each body's firmware.*

## In use

To set the count today, switch stacking off, set the number, then switch stacking back on. The camera's own menu greys
the row out while stacking is on.

## Status

Both changes work on our E-M5 III. A proper menu row for the shot count, as the OM-5 has, is the next step.

## Further reading

- [Focus stacking: technical notes](focus-stacking-technical.md) has how to find the lens check, the change, and the shot-count study.
- The "Any-lens focus stacking patch" page, next to this one in the public notes, walks through the change step by step.
- [Image engine](../hardware/image-engine.md) explains the programs that align and merge the frames.
