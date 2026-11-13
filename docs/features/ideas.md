# Other image-processor feature ideas

This page collects feature ideas that aren't projects yet: things the camera's hardware could probably do, ideas taken
from other camera makers and from Magic Lantern (the Canon firmware add-on), and small shooting tweaks. Each idea has a
first verdict; the full ranked tables with effort and blockers are in the working notes linked from each section.

Most of the cheap ideas reuse what Live ND already proved: the camera can hold several raw frames and average them on
the image engine (job 11).

Tags: **[code]** read in the firmware, **[camera]** seen on a real E-M5 III, **[inferred]** not traced or tested.

## Round 1 (2026-10-29): image-processor ideas

Brainstorm from 2026-10-29, nothing built.

Cheapest first:

1. **Tripod multi-frame noise reduction:** the Live ND path with a full exposure per frame, averaged by job 11 (√N less
   noise). Cost S (small).
2. **Weighted averages** using duplicate inputs in job 11 (`[acc, acc, acc, new]` = 3:1). Repeated inputs are already
   proven on the camera with ND2/ND4, so weighted averages and running accumulators look feasible. [camera] for repeats, weights [inferred]
3. **Band records** (merging only a sub-rectangle) for Live GND-style effects.
4. **Identify the native jobs 0-10.** A min/max or subtract job would unlock Bright/Dark multiple exposure, dark-frame
   averaging and median stacks. 2026-11-06: **mapped**
   ([image engine](../hardware/image-engine.md#the-e-m5-iiis-own-jobs-0-to-10-mapped-2026-11-06)): job 8 = hardware
   memcpy, job 2 = Live Composite raw combine, job 4 = mesh warp; no average/min/subtract job found. [code]/[inferred]


Others on the list: average-mode multiple exposure, night live view via job 12, motion trails, Live Composite with base
noise reduction, a handheld night mode (after HHHR), 4-shot RGB pixel shift, sensor-shift star tracking, raw
histogram/ETTR, sweep panorama (names only, no code in any body), and Dual ISO (least feasible).

## Round 2 (2026-11-05): a wider brainstorm


The shortlist:

1. Tripod multi-frame noise reduction on the Live ND path.
2. Focus stacking shot count 3-15 (the OM-5 and E-M1 III have `MODE_FOCUS_STACKING_NUMBER`, the E-M5 III only `_ONOFF`).
   [code]
3. The OM-Log400 movie profile (OM-5 `EXPANDED_CONTRAST_MODE_LOG`; E-M5 III only OFF/SUPERFLAT). [code]
4. A card-script runner for the MN103 debug console.
5. ARM Linux from the SD card (`arm load4`) as a NEON co-processor. [inferred]
6. A Bluetooth remote (the OM-5's BLE accessory-remote keys plus its pairing-capable blebridge). [code]

- Evidence (2026-11-05): the OM-5 1.2 has 1,307 `MODE_*` keys absent from the E-M5 III, mostly renames; the real gaps
  are listed in the write-up. [code]
- A rule we kept: a settings key or a GUI string is not a feature. Confirm there is reachable code, or run the menu in
  om-emu, first. [process]

## Shooting-mode tweaks (2026-11-05)


**Focus-stack count:** setting 1448 exists, the menu item is missing, and more than 8 needs wider arrays; see
[focus stacking](focus-stacking.md). [code]

**AE bracketing (more than 7 frames):**

- There's no fixed EV table: 0x6044260d(count, i, step, order) computes each frame, clamped to ±7 EV; the frame count is
  setting 5. [code]
- 0x60308658 writes count × 6-byte entries without checking, and its GUI caller 0x607d289c has 7-entry (42 B) buffers,
  so 9 frames needs bigger buffers first. [code] But 0x60308658's only caller is that GUI display; shooting computes
  each frame itself in the AE module (0x60448f9a, 0x6044a127; count = property 0x8281), so the 7 cap is GUI-only
  (2026-11-05). [code]
- Setting 5's value is the frame count and `MODE_AUTOBKT_9` exists, but the menu lists only 2/3/5/7. A 9-frame build
  waits for the shared menu work (add 9f, fix the GUI buffers, check 15 readers). [code]+[inferred]


**Interval shooting (holy-grail timelapse):**

- The controller is in the sequencer module (`receiveIntervalTimerCallback`, `Shoot` step 0x6099addf, sleep timer
  0x6087502e). Long intervals sleep and re-boot the camera (`CAM_INTERVAL_SHOOTING_BOOT`), so an exposure ramp must keep
  its state in a property or a card file. [code]+[inferred]
- Each frame goes `Shoot` → 0x6099abdf → OPE shoot request 0x60800901 (an ordinary release); the ramp hook point is just
  before 0x6099adf4 (2026-11-05). [code]+[inferred]

**Auto-ISO lowest shutter speed:** already on the E-M5 III 1.7 (GUI "Lowest S/S Setting", `MODE_SHUTTER_ISO_LIMIT*`).
Nothing to port. [code]

## Round 3 (2026-11-05): ideas from other makers and Magic Lantern

E-M5 III is [inferred].

The shortlist: raw zebras, raw histogram and an ETTR hint (Magic Lantern); a motion/lightning trigger and trap focus
(Magic Lantern, Nikon Auto Capture); holy-grail timelapse / bulb ramping (Magic Lantern, Nikon/Sony smoothing);
highlight-safe multi-frame noise reduction and tripod HDR merge (Google HDR+); a manual-focus guide from the on-sensor
PDAF (Canon); automatic horizon correction by rolling the sensor (Pentax SR). [inferred]

What they share:

- OSD draw primitives and a CPU-readable live-view frame pointer, both **found 2026-11-05**
  ([hardware/display.md](../hardware/display.md)). [code]
- The IBIS command interface, found 2026-11-06 (it hadn't been researched before): an IS sub-CPU with a 57-command set
  including target-position, constant-speed and rotation drives ([hardware/stabiliser.md](../hardware/stabiliser.md),
  verdicts in). [code]
