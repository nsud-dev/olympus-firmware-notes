# Starry Sky AF

<!-- human page -->
> The dense reference for this page is [Starry Sky AF: technical notes](starry-sky-af-technical.md).

Normal autofocus cannot focus on stars. They are too small and too faint for it to find any contrast. Newer bodies have
a Starry Sky AF mode that can, which makes night-sky photography much easier. The E-M5 III does not have it.

Inside the firmware it is called Astro AF.

## Status

- **Research is done.** We know what the feature is made of and where it would hook into the E-M5 III.
- **A first test build was made but never run.** It sits on an old base and its memory has since gone to Live ND, so it
  has to be moved and rebuilt before it can be tried.

## On the newer bodies

The E-M1 III and the OM-5 have the same Starry Sky AF. The OM-5 II only adds a few choices for how it starts.

It is not one neat module. It is threaded through the whole autofocus system, from the settings and the shutter-button
check to the focus task, the exposure code, the lens drive and the menus. The new code itself is small, at about 5 to
6 KB. The work is in the 25 to 40 places where it joins the existing code.

When star mode is on and you half-press, the camera does three things differently.

1. It first moves the lens to its stored infinity position.
2. It switches off the phase-detect pixels on the sensor and relies on contrast alone.
3. It uses larger focus areas and puts the focus engine in a special mode.

The maths that measures contrast is the same library on all three bodies. So there is no new autofocus algorithm to
port, only the sequence around it.

The newer bodies also learn the infinity position for each lens and keep a table of them in flash memory. That table
is about 61 KB.

## The port

We use the E-M1 III to decide where hooks go, because its focus code is a close superset of the E-M5 III's. We use the
OM-5 for behaviour, settings and menus.

The test build makes star focus out of the E-M5 III's normal single AF with four changes.

1. Instead of its usual first lens move, it drives the lens to infinity using the lens's own information.
2. It switches off phase-detect focus.
3. It uses the newer bodies' larger focus areas.
4. It puts the focus engine into star mode.

The code is 321 bytes. It passed the simulator, but it has not been on a camera.

## The hard part

The per-lens infinity table is the risky piece. On the OM-5 it lives in a part of flash that holds lens data on the
E-M5 III. Writing there could damage that data. The plan is to keep the table in memory first and write flash only
once that is well understood.

## Next steps

1. Move the test code to the space set aside for it and rebuild it on the current base.
2. Try it on the camera with a fixed infinity position.
3. Add the settings and a menu choice.
4. Work out flash learning.

One question is still open. Nothing has yet been found in the E-M5 III that reads the Accuracy or Speed choice.

## Other cameras

| camera | Starry Sky AF |
|---|---|
| E-M1 III 1.6 | built in |
| OM-5 1.2 | built in, same as the E-M1 III |
| OM-5 II | built in, with extra start options |
| E-M5 III 1.7 | absent, test build made |
| E-M5 II, E-M5 (Mark I) | absent, would need new focus code |

## Further reading

- [Memory map](../hardware/memory-map.md) shows the space set aside for this feature.
- [Modifying the firmware](../firmware/patching-techniques.md) covers hooking and porting from a newer body.
