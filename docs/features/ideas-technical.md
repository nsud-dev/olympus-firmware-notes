# Feature ideas: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Feature ideas](ideas.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

This page collects feature ideas that aren't projects yet. Some are things the camera's hardware could probably do.
Some are taken from other camera makers and from Magic Lantern, the Canon firmware add-on. Some are small shooting
tweaks. Each idea has a first verdict. The full ranked tables, with effort and blockers, are in our working notes.

Most of the cheap ideas reuse what Live ND already proved. The camera can hold several raw frames and average them on
the image engine with job 11.

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred.

## Image engine ideas

These came from a first brainstorm. Nothing was built.[^inf1] Cheapest first:

1. **Tripod multi-frame noise reduction.** The Live ND path with a full exposure per frame, averaged by job 11. Noise
   drops by √N for N frames. Cost S (small).[^inf1]
2. **Weighted averages** using duplicate inputs in job 11. `[acc, acc, acc, new]` gives a 3:1 mix. Repeated inputs
   are already proven on the camera with ND2 and ND4.[^cam1] So weighted averages and running accumulators look
   feasible.[^inf1]
3. **Band records**, merging only a sub-rectangle, for Live GND-style effects.[^inf1]
4. **The native jobs 0-10.** A min/max or subtract job would unlock Bright/Dark multiple exposure, dark-frame averaging
   and median stacks. These jobs are now mapped.[^fw2] Job 8 is a hardware memcpy, job 2 is the Live Composite raw
   combine and job 4 is a mesh warp. No average, min or subtract job was found.[^inf2]

See also: [The E-M5 III's own jobs 0 to 10](../hardware/image-engine-technical.md#the-e-m5-iiis-own-jobs-0-to-10).

Others on the list are average-mode multiple exposure, night live view via job 12, motion trails, Live Composite with
base noise reduction, a handheld night mode (after Handheld High Res, HHHR), 4-shot RGB pixel shift, sensor-shift star tracking, a raw
histogram with an exposure-to-the-right (ETTR) hint, sweep panorama and Dual ISO. Sweep panorama exists as names only,
with no code in any body. Dual ISO is the least feasible.[^inf1]

## Ideas from newer bodies

A wider brainstorm ranked 21 ideas, with donor, verdict, blocker, effort and first step.[^inf3] The shortlist:

1. Tripod multi-frame noise reduction on the Live ND path.
2. Focus stacking shot count 3-15. The OM-5 and E-M1 III have `MODE_FOCUS_STACKING_NUMBER`, and the E-M5 III only
   `_ONOFF`.[^fw1]
3. The OM-Log400 movie profile. The OM-5 has `EXPANDED_CONTRAST_MODE_LOG`, and the E-M5 III only OFF and
   SUPERFLAT.[^fw1]
4. A card-script runner for the MN103 debug console.
5. ARM Linux from the SD card (`arm load4`) as a NEON co-processor.[^inf3]
6. A Bluetooth remote, from the OM-5's Bluetooth Low Energy (BLE) accessory-remote keys plus its pairing-capable blebridge.[^fw1]

The OM-5 1.2 has 1,307 `MODE_*` keys absent from the E-M5 III. Most are renames. The real gaps are listed in the
write-up.[^fw1]

A rule we kept from this round is that a settings key or a GUI string is not a feature. Confirm there is reachable
code, or run the menu in om-emu, first.[^pol1]

## Shooting tweaks

### Focus-stack count

Setting 1448 exists and the menu item is missing. More than 8 shots needs wider arrays.[^fw1]

See also: [Focus stacking](focus-stacking.md).

### Auto exposure (AE) bracketing with more than 7 frames

- There is no fixed EV table. One function, called with (count, i, step, order), computes each frame, clamped to
  ±7 EV. The frame count is setting 5.[^fw1]
- Shooting computes each frame itself in the AE module, with the count in property `0x8281`. So the 7-frame cap is in
  the GUI only.[^fw1]
- A bracketing table writer writes count × 6-byte entries without checking. Its only caller is the GUI display, which
  has 7-entry (42 B) buffers. So 9 frames needs bigger buffers first.[^fw1]
- Setting 5's value is the frame count and `MODE_AUTOBKT_9` exists, but the menu lists only 2, 3, 5 and 7.[^fw1]
- A 9-frame build waits for the shared menu work. That means adding 9f, fixing the GUI buffers and checking 15
  readers.[^inf3]

### Interval shooting and holy-grail timelapse

- The controller is in the sequencer module, with `receiveIntervalTimerCallback`, a `Shoot` step and a sleep
  timer.[^fw1]
- Long intervals sleep and re-boot the camera (`CAM_INTERVAL_SHOOTING_BOOT`).[^fw1] So an exposure ramp must keep its
  state in a property or a card file.[^inf3]
- Each frame goes from the `Shoot` step through one more step to the OPE shoot request, an ordinary release.[^fw1]
- The ramp hook point is just before one instruction in the `Shoot` step.[^inf3]

### Auto ISO lowest shutter speed

Already on the E-M5 III 1.7, as the GUI item "Lowest S/S Setting" with `MODE_SHUTTER_ISO_LIMIT*`. Nothing to
port.[^fw1]

## Ideas from other makers

A third brainstorm listed 16 ideas from other makers and Magic Lantern. How each maps to the E-M5 III is
inferred.[^inf3] The shortlist:

- raw zebras, a raw histogram and an ETTR hint (Magic Lantern)
- a motion or lightning trigger and trap focus (Magic Lantern, Nikon Auto Capture)
- holy-grail timelapse or bulb ramping (Magic Lantern, Nikon and Sony smoothing)
- highlight-safe multi-frame noise reduction and tripod HDR merge (Google HDR+)
- a manual-focus guide from the on-sensor phase-detect pixels (PDAF) (Canon)
- automatic horizon correction by rolling the sensor (Pentax SR)

What they share:

- On-screen display (OSD) draw primitives and a CPU-readable live-view frame pointer, both found in the firmware.[^fw1] See
  [Display and live-view frames](../hardware/display.md).
- The in-body image stabilisation (IBIS) command interface, which hadn't been researched before.[^fw2] It is an IS sub-CPU with a 57-command set,
  including target-position, constant-speed and rotation drives. See [Image stabiliser](../hardware/stabiliser.md).

## Newer ideas

A ranked list of 26 ideas builds on what we learned since the third brainstorm. That covers the VSC display blocks, the
c3d GPU, the card loader, simulated key presses, Pro Capture and the MDET motion vectors.[^inf4] It is in the
project's private notes for now.

## Older bodies

Most ideas here reuse Live ND's raw-frame averaging on image-engine job 11.

- The E-M5 II's engine runs the same program format but has no job 11 or Live ND plumbing. So those ideas would need
  the same new port as Live ND there.[^fw3]
- The E-M5 Mark I has no programs of this format, so they don't apply.[^fw3]
- Shooting tweaks that are plain settings patches would need their own addresses on each body.[^inf5]

See also: [Older bodies](../bodies/comparison-technical.md#older-bodies-e-m5-ii-and-e-m5-mark-i).

## Address reference

E-M5 III 1.7 block0 addresses (base `0x60021020`).

| item | address |
|---|---|
| AE frame computation (count, i, step, order) | `0x6044260d` |
| AE module per-frame computation | `0x60448f9a`, `0x6044a127` |
| bracketing table writer (count × 6-byte entries) | `0x60308658` |
| its GUI caller, with 7-entry buffers | `0x607d289c` |

*AE bracketing.*

| item | address |
|---|---|
| interval `Shoot` step | `0x6099addf` |
| interval sleep timer | `0x6087502e` |
| next step of each frame | `0x6099abdf` |
| OPE shoot request | `0x60800901` |
| ramp hook point (just before) | `0x6099adf4` |

*Interval shooting.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware, 2026-11-05.
[^fw2]: Read in the firmware, 2026-11-06.
[^fw3]: Read in the firmware, 2026-11-21.
[^cam1]: Seen on our E-M5 III with Live ND's ND2 and ND4 settings. The weights themselves are inferred.
[^inf1]: Inferred, not traced or tested. First brainstorm, 2026-10-29.
[^inf2]: Inferred from the job mapping, 2026-11-06.
[^inf3]: Inferred, 2026-11-05.
[^inf4]: Inferred, round 4 brainstorm, 2026-11-22.
[^inf5]: Inferred, 2026-11-21.
[^pol1]: A project rule, 2026-11-05.

