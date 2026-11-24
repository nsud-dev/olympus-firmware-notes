# Handheld High Res Shot


<!-- human page -->
> The dense reference for this page is [Handheld High Res Shot: technical notes](hhhr-technical.md).

High Res Shot takes several frames with the sensor shifted by tiny amounts and combines them into one 50 megapixel
picture. The E-M5 Mark III can do this on a tripod. The OM-5 can also do it hand-held, because it measures how the
camera moved between frames and lines them up before combining. That hand-held version is the second big feature this
project is bringing over.

Nothing works end to end yet. This page says which pieces are proven and which are not.


## Status

Where it stood when the research closed on 24 November 2026, on the E-M5 III:

- **The image-engine programs load.** Hand-held High Res needs four programs for the camera's image engine, which
  compose, fill, convert and resize the picture. All four come from the OM-5, and all four load onto the E-M5 III
  through the camera's own path.
- **The memory is free.** A census taken during a tripod High Res shot showed that the memory hand-held High Res needs
  is not in use. The hand-held version can reuse the tripod mode's memory.
- **The helper processor can be started.** Part of the alignment maths runs on a small ARM processor inside the camera,
  which is normally asleep unless Wi-Fi is on. Our code can now switch it on for a shot and off again cleanly.
- **Not proven:** whether those four programs compose a correct picture on this camera. They have been loaded,
  never run on real frames.

The next two steps were built or planned. One test build sends a single request to the ARM helper. After that the
compose program would run on a test pattern.

## Where we stopped

We closed the hand-held High Res research on 24 November 2026. Most of the hard unknowns were behind us. The
image-engine programs load, the memory they need is free, and the ARM helper can be switched on and off safely. Any
of those could have ended the port. None of them did.

One open question remained. Do the four programs compose a correct picture on this camera? After that came wiring.
One request to the ARM helper, then the compose program on real frames, then the hand-held flow in the shooting
sequence. The same methods had already worked for Live ND.


We stopped here to put the time into documenting the camera's systems and studying how far this hardware shares its
design with newer bodies. The pages here stay as a record of how the feature works and how far the port got.

## On the OM-5

Hand-held High Res is not a separate mode on the OM-5. It is a "Shooting Method" setting inside High Res Shot, so the
camera decides at the shutter press which kind of shot to take.

The shot itself runs like this:

1. The camera takes a burst of frames, up to 12, with the sensor shifted between them.
2. For each frame it estimates how the picture moved against the first one, using the motion-detection hardware.
3. The ARM helper turns those estimates into alignment matrices, one per frame.
4. The image engine composes the aligned frames into four large colour planes.
5. Three more engine programs fill gaps, convert to RGB and resize the result to 50 megapixels.

On a tripod, step 2 and step 3 are unnecessary, which is why the E-M5 III can already do the tripod version.

## The port

The E-M5 III already has the tripod version, the ARM helper program and the hardware the hand-held version needs. What
it lacks is the code that runs the hand-held flow and the four engine programs. The port has to supply both, and work
within four constraints:

- **Memory.** The OM-5's hand-held buffers come to about 640 MB. Most of the buffer identifiers differ between the two
  cameras, so the layout has to be designed for the E-M5 III rather than copied.
- **Space for the engine programs.** The four programs are large. There is room for them in the firmware's flash, and a
  gap in the engine's own memory that fits one large program or the three smaller ones.
- **Space for the code.** The hand-held module needs about 45 KB, which fits in a free region of the firmware. Code
  there only runs once that part of the firmware has loaded, so every hook needs a guard.
- **Talking to the ARM.** The camera's mailbox to the ARM blocks if nothing has arrived, which is not safe to call from
  the shooting path, so the port uses the non-blocking form.

## Lessons

**The ARM is asleep, and waking it is a shot-timing problem.** A first attempt to ping the helper with Wi-Fi off turned
the camera off. The ARM is not running unless something starts it. The camera's own power manager takes requests from
two owners, Wi-Fi and the shooting path, so our code asks as the shooting path. Asking in the middle of a shot reset the
camera. Asking between shots works, and the ARM then starts and stops cleanly with no Wi-Fi involved.

**Use the camera's own loading path for engine programs.** Writing new engine programs into memory by hand would mean
guessing at the engine's state. Loading them the way the camera loads its own programs gets that right for free.

## Other cameras

| camera | hand-held High Res | notes |
|---|---|---|
| OM-5 | built in | the source of this port |
| OM-5 II | built in | two of the four engine programs changed, so the port stays with the OM-5 |
| E-M1 III | built in | up to 16 frames; the same design |
| OM-1, OM-1 II | built in | newer engine programs that can't be reused |
| E-M5 III | tripod only | this port adds the hand-held version |
| E-M5 II | tripod only (40 MP) | no ARM processor at all, so this design can't work there |
| E-M5 (Mark I) | none | no pixel-shift code |

## Further reading

- [HHHR: technical notes](hhhr-technical.md) has the addresses, the memory plan, the test ladder and the open questions.
- [Image engine](../hardware/image-engine.md) explains the engine programs.
- [ARM co-processor](../hardware/arm-coprocessor.md) covers the helper processor and the mailbox.
