# Focus stacking

<!-- human page -->
> The dense reference for this page is [Focus stacking: technical notes](focus-stacking-technical.md).

Focus stacking takes a series of shots at different focus distances and merges them in the camera into one picture that
is sharp from front to back. The E-M5 Mark III can do it, but only with a short list of Olympus lenses, and always with
eight shots.

Both of those limits are now lifted on our camera. This was the first thing the project changed, and it still works.


## Status

- **Any lens works.** The lens check is one branch in the firmware. Changing it makes the check always pass, so
  stacking works with lenses the camera otherwise refuses. Flashed and working since 19 October 2026.
- **The number of shots can be set, from 3 to 8.** The count is already a camera setting, with its own saved value.
  The E-M5 III simply has no menu row for it, and always uses eight.
- **Both work as card mods.** Since 22 November 2026 neither change needs a patched firmware. Our mod loader reads
  them from the SD card at start-up, and each has an Off and On row in the camera's menu.

To set the count today, switch stacking off, set the number, then switch stacking back on. The camera's own menu greys
the row out while stacking is on. A proper menu row, as the OM-5 has, is the next step.

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
| E-M5 III | yes | works, since October 2026 |
| E-M5 II | yes | the check is shaped differently, so it needs its own work |
| E-M5 (Mark I) | no | nothing to patch |
| PEN-F | no | no in-camera stacking |

## Further reading

- [Focus stacking: technical notes](focus-stacking-technical.md) has the addresses, the changed bytes and the shot-count study.
- The "Any-lens focus stacking patch" page, next to this one in the public notes, has the byte-level description.
- [Image engine](../hardware/image-engine.md) explains the programs that align and merge the frames.
