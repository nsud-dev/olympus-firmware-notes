# Other image-processor feature ideas

Brainstorm from 2026-10-29, nothing built. Full ranked table:.

Cheapest first:
1. **Tripod multi-frame NR**: Live ND path with full exposure per frame, job 11 average (√N less noise). Cost S.
2. **Duplicate-input weighting** in job 11 (`[acc, acc, acc, new]` = 3:1). Repeated inputs are already proven by E8a, so
   weighted averages / running accumulators look feasible. [camera] for repeats, weights [inferred]
3. **Band records** (sub-rectangle merges) for Live GND-style effects.
4. **Identify native jobs 0-10** (a min/max or subtract job would unlock Bright/Dark multi-exposure, dark-frame averaging, median stacks).
   2026-11-06: **mapped** ([image engine](../hardware/image-engine.md#native-jobs-0-10-mapped-2026-11-06)): job 8 = hardware memcpy, job 2 = Live Composite raw combine, job 4 = mesh warp; no average/min/subtract job found. [code]/[inferred]

Others: average-mode multiple exposure, night LV via job 12, motion trails, Live Composite with base NR, handheld night mode
(after HHHR), 4-shot RGB pixel shift, sensor-shift star tracking, raw histogram/ETTR, sweep panorama (names only, no code in any body),
Dual ISO (lowest feasibility).

## Round 2 (2026-11-05): wider brainstorm
Shortlist: (1) tripod multi-frame NR on the Live ND path; (2) focus stacking shot count 3-15 (OM-5/E-M1 III have
`MODE_FOCUS_STACKING_NUMBER`, E-M5 III only `_ONOFF`) [code]; (3) OM-Log400 movie profile (OM-5 `EXPANDED_CONTRAST_MODE_LOG`,
E-M5 III only OFF/SUPERFLAT) [code]; (4) card-script runner for the MN103 debug console; (5) ARM Linux from SD (`arm load4`)
as a NEON co-processor [inferred]; (6) Bluetooth remote (OM-5 BLE accessory-remote keys + pairing-capable blebridge) [code].
- Evidence (2026-11-05): OM-5 1.2 has 1,307 `MODE_*` keys absent in E-M5 III, mostly renames; real gaps listed in the
  write-up. Lists:. [code]
- Rule kept: a key or GUI string is not a feature; confirm reachable code or an om-emu menu run first. [process]

## Shooting-mode tweaks research (2026-11-05)
- Focus-stack count: setting 1448 exists, menu missing, >8 needs wider arrays; see [focus stacking](focus-stacking.md). [code]
- AE bracketing: no fixed EV table; 0x6044260d(count, i, step, order) computes each frame, clamp ±7 EV; frame count = setting 5.
  0x60308658 writes count × 6-byte entries unchecked and the GUI caller 0x607d289c has 7-entry (42 B) buffers, so 9 frames
  needs bigger buffers first. [code] 0x60308658's only caller is that GUI display; shooting computes each frame itself in the
  AE module (0x60448f9a, 0x6044a127; count = prop 0x8281), so the 7 cap is GUI-only (2026-11-05). [code] Setting 5's value is
  the frame count and `MODE_AUTOBKT_9` exists, but the menu lists only 2/3/5/7, so a 9-frame build waits for the shared menu
  thread (add 9f, fix GUI buffers, check 15 readers). [code]+[inferred]
- Interval shooting: controller in the sequencer module (`receiveIntervalTimerCallback`, `Shoot` step 0x6099addf, sleep timer
  0x6087502e); long intervals sleep and re-boot the camera (`CAM_INTERVAL_SHOOTING_BOOT`), so a holy-grail ramp must keep its
  state in a property or card file. [code]+[inferred] Each frame: `Shoot` → 0x6099abdf → OPE shoot request 0x60800901
  (ordinary release); ramp hook point just before 0x6099adf4 (2026-11-05). [code]+[inferred]
- Auto-ISO lowest shutter: already on E-M5 III 1.7 (GUI "Lowest S/S Setting", `MODE_SHUTTER_ISO_LIMIT*`). Nothing to port. [code]

## Round 3 (2026-11-05): ideas from other makers and Magic Lantern
Shortlist: raw zebras/histogram/ETTR hint (Magic Lantern); motion/lightning trigger + trap focus (ML, Nikon Auto Capture);
holy-grail timelapse / bulb ramping (ML, Nikon/Sony smoothing); highlight-safe multi-frame NR / tripod HDR merge (Google HDR+);
MF focus guide from on-sensor PDAF (Canon); auto horizon correction by sensor roll (Pentax SR). [inferred]
- Shared enablers: OSD draw primitives and a CPU-readable LV frame pointer **found 2026-11-05** ([hardware/display.md](../hardware/display.md)) [code];
  IBIS command interface ~~not yet researched~~ found 2026-11-06: IS sub-CPU with a 57-command set incl. target-position, constant-speed
  and rotation drives ([hardware/stabiliser.md](../hardware/stabiliser.md), verdicts in). [code]
