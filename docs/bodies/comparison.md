# Body comparison

This page puts the camera bodies we have looked at side by side: which chip generation each uses, how much memory, and
which features its firmware contains. It explains why the OM-5 is our main source ("donor") for features, and why you
can't simply flash an OM-5 firmware onto an E-M5 III.

All bodies here use the same firmware container, the same MN103/AM33-2 control CPU and the same block0 base 0x60021020.
[code] TruePic is Olympus's name for the whole processor chip (see [SoC overview](../hardware/soc-overview.md)).

| | E-M5 III | OM-5 | OM-5 II | E-M1 III | OM-1 | OM-1 II | PEN-F |
|---|---|---|---|---|---|---|---|
| file / fw | E_137 1.7 | E_144 1.2 | E_148 1.1 | E_139 1.6 (1.4) | E_143 1.9 | E_146 1.3 | E_122 3.1 |
| magic | OE 13 70 | OE 14 40 | OE 14 80 | OE 13 90 | OE 14 30 | OE 14 60 | OE 12 20 |
| TruePic | VIII | IX | IX | IX | X | X | VII |
| blocks | 5 | 5 | 5 | 6 | 6 (+sub-CPU) | 6 | 4 |
| block0 LZ4 sections | none | 2 | 2 | 2 | none (32 MB) | none | none |
| buffer map / DRAM class | 1 GB | 1 GB | 1 GB | 2 GB | 2 GB | 2 GB | ? |
| MN103 cores seen | CPU0-2 | CPU0-2 | CPU0-2 | CPU0-2 | CPU0-3 | CPU0-3 | ? |
| ARM | A9, Linux 4.4 | A9, 4.4 | A9, 5.10 | A9, 4.4 | A53, 4.14 | A53, 4.14 | ? |
| Wi-Fi | CYW43455 | CYW43455 | CYW43439 | CYW43455 | CYW43455 | CYW43455 | ? |
| setting IDs | 0-1649 | 0-1892 | more | | | | |
| English GUI lang index | 8 | 5 | 5 | 8 | | | |
| DSP jobs 11/12 | absent | yes | yes | yes | new gen (no match) | new gen | ? |
| Live ND | plumbing off (ported by us) | ND2-16 | ND2-16 (ND64/128 strings only) | yes, 32-frame table | ND2-64 | ND2-128 | no |
| Live GND | no | no | UI only (stubs) | no | no | **yes** (`iseq_half_nd`) | no |
| HHHR | tripod HR only; ARM `hhhr` present | yes (50 MP) | yes (jobs 14/15 changed) | yes | yes | yes | no |
| Starry Sky AF | no | yes | yes + start triggers | yes | yes | yes | no |
| DL subject detect | no | dead code | dead code + menu | dead code | **yes** (CPU3 + DML) | yes | no |
| USB webcam (UVC) | no (ported partly) | yes | yes | no | no | yes | no |
| USB-C / PD | no (micro-USB) | yes | yes | yes | yes | yes | no |
| function match → E-M5 III | — | 82% | 77% | 83% | not measured | | |

? = not checked; an empty cell means not looked at.

**Which body we take what from.** Donor rules: **OM-5 1.2** for code, memory model and DSP jobs (Live ND, HHHR, Star AF, AF features);
OM-5 II only for what it adds; E-M1 III for hook placement (its fcs is a superset of E-M5's); OM-1/OM-1 II for logic/maths
references only (ND32+, Live GND) since their DSP jobs and memory don't fit.

## What the bodies share (scan, 2026-11-20)

Much of what we found on the E-M5 III is shared code, so it is a lead on the other bodies too. This table is from a
plain scan of each body's main program (block0; OM-5, OM-5 II and E-M1 III on their expanded images) for strings and
constants that belong to each item. **Present means the item's strings or constants are in the firmware, not that it
was tried or behaves the same.** [code] 2026-11-20

| item | E-M5 III 1.7 | OM-5 1.2 | OM-5 II 1.1 | E-M1 III 1.6 | OM-1 1.9 | PEN-F 3.1 | why it matters |
|---|---|---|---|---|---|---|---|
| debug shell commands `ui key skey`, `file memdump`, `take dbgmode` | yes | yes | yes | yes | yes | yes | remote key presses, RAM dumps to the card, event trace ([Wi-Fi debug shell](../features/wifi-debug-shell.md)) |
| `sdk api` command set | yes | yes | yes | yes | yes | yes | on the E-P7 its handlers were found to be a large block of code reachable only from the shell, a free-space candidate (Caduceus E-P7) |
| card updater folder `DCOLYMP` | yes | yes | yes | yes | yes | yes | the same recovery route ([recovery](../firmware/recovery.md)) |
| settings image saved by "acc flash write" | yes | yes | yes | yes | yes | not found | where saved mod settings can live ([saved settings](../features/saved-settings-and-menu-rows.md)) |
| setting → property table, same first entries | yes | yes | yes | yes | yes | yes | the same menu and settings design ([Settings and menus](../guides/settings-and-menus.md)) |
| RGB histogram path (`YRGB`, `getHistogram`) | yes | yes | yes | yes | yes | yes | per-channel histograms are native code ([display](../hardware/display.md)) |
| loader access-monitor register (0x99700040) | yes | yes | yes | yes | yes | yes | sections must be ready before a hook touches them ([boot and sections](../firmware/boot-and-sections.md)); on the OM-5 II the same monitor was traced by the Caduceus OM-5 project |
| ARM loader from the card (`C:\TARGET`) | yes | yes | yes | yes | no | no | loading ARM code from the card ([ARM co-processor](../hardware/arm-coprocessor.md)); the OM-1's ARM is a different (64-bit) design |
| `DigitalNd` (Live ND engine) | no | yes | yes | yes | yes | no | where native Live ND lives ([Live ND](../features/live-nd.md)) |

How to use it: a "yes" tells you where to start looking on your body; the addresses differ on every build, and each
body needs its own check. The per-technique tables on [Modifying the firmware](../firmware/patching-techniques.md)
record which bodies a technique has actually been shown on.


## Our features on the other bodies (2026-11-20)

For each feature we have built or are building on the E-M5 III: does another body already have it natively, and if not,
does it have the parts our port uses? Static check only (no camera, no builds, no emulator runs). **"Present" means the
code or data exists in the firmware, not that it works or was tried.** Each cell says how it was checked:
**S** = strings or constants in block0, **C** = code read or matched (relocation-masked function match or disassembly of
the counterpart), **K** = from an earlier KB finding (linked). All [code] unless marked [inferred]. 2026-11-20

| feature (E-M5 III state) | OM-5 1.2 | OM-5 II 1.1 | E-M1 III 1.6 | OM-1 1.9 | OM-1 II 1.3 | PEN-F 3.1 |
|---|---|---|---|---|---|---|
| Live ND (our port, menu rows working) | native ND2-16 (S, K) | native ND2-16 (S, K) | native (S, K) | native ND2-64 (S, K) | native ND2-128 (S, K) | absent: no `iseq_nd`, no `DigitalNd` (S); DSP jobs 11/12 not checked |
| Live GND (not ported) | absent (S) | UI strings only (K) | absent (S) | absent (S) | native `iseq_half_nd` (S, K) | absent (S) |
| HHHR, hand-held High Res (our port in progress) | native (S, K) | native (S, K) | native (S, K) | native (S, K) | native (S, K) | absent; tripod High Res only (`pixshift_sr` strings, no hand-held) (S) |
| Starry Sky AF (test build made, not run) | native (S, K) | native + start options (S, K) | native (S, K) | native (S) | native (S) | absent: no astro strings (S) |
| Focus stacking with any lens (done on camera) | same lens check, branch at 0x606d63fb (C) | 0x606d5524 (C) | 0x606983f9 (C) | 0x608e3899 (C) | 0x608fd3f2 (C) | no in-camera stacking: check name string present but never referenced, no stacking strings (S, C) |
| Native menu rows with saved values (our method, works on camera) | settings design shared, getter counterpart found (S, C, K); free gap not checked | same | same; setter matches in shape (C) | same | same | different: no "acc flash write" settings image (S); getter shape found (C) |
| Color / Mono Profile back end (E-M5 III: present, no stock UI; ours added in test builds) | present (S, K) | present (S, K) | present (S, K) | present (S) | present (S) | present, native feature (K) |
| Profile editor wheel renderers (CC2 / Mono / Shading; E-M5 III: stubs, E-M1 III ones relocated in our test builds) | none, cases removed (K) | none (C: 0 of 46/26/14 chunks) | full (K) | close relative: 31/46, 18/26, 10/14 chunks (C) | 28/46, 16/26, 7/14 (C) | older version: 19/46, 8/26, 4/14 (C) |
| Profile editor screens (kinds -20/-23) | no (K) | no profile picture modes (K, om-emu) | no (K) | not checked | not checked | yes, the only shipped editor (K) |
| USB webcam (UVC; ours parked) | native (S, C: UVC descriptors) | native (S, C) | no UVC descriptors (C) | no UVC descriptors (C) | native (S, C) | no UVC descriptors (C) |
| Sync IS for Panasonic lenses (no flag-only patch on E-M5 III) | same copt + `L_STAT_PANA` design (S); verdict likely the same [inferred] | same | same | same | same | no copt strings (S) |
| Wi-Fi debug shell via card file (works on E-M5 III) | F971 callback matches in shape (C), shell commands (S) | same | same | same | same | shell commands present, callback differs (4/5 chunks) (S, C) |
| Card console after section 10 (works on camera) | shell present (S); section-end site not located | same | same | same | same | same |

How the code checks were done: `fmatch.py` disassembles the E-M5 III (or E-M1 III) function, masks call/jump operands
and address-like constants, and looks for it in each body; "n/m chunks" is how many 8-instruction pieces were found near
one place. A low count is not proof of absence, because struct offsets and setting ids shift between bodies.
The focus-stack branch was confirmed by disassembly: every body from the OM-5 on has the same function shape, with the
`bne` (`c9 04`) that our patch replaces at the same offset (+0x16).

What this means for porting [inferred]:

- **To the OM-5 / OM-5 II / E-M1 III / OM-1 family:** Live ND, HHHR and Starry Sky AF are already native. What carries
  over is the any-lens focus stack patch (same one branch, address per body), menu rows with saved values (same settings
  design, new addresses), the card console and the Wi-Fi shell, and the profile editor (back end everywhere; the
  E-M1 III and OM-1 family still have the wheel renderers, the OM-5 / OM-5 II don't).
- **To the PEN-F:** Live ND, HHHR and Starry Sky AF are absent and would be full ports onto an older chip (TruePic VII);
  not checked whether its image engine has the jobs they need. The profile editor is native there.
- **E-M5 II and E-M5 (Mark I): needs firmware.** We hold no images for either. The E-M5 II is the same generation as the
  PEN-F (TruePic VII), so the PEN-F column is the closest guide until we have them; the E-M5 Mark I is older still
  (TruePic VI) and may not share the container or CPU layout. Nothing is checked.


## Why not just cross-flash the OM-5 image?

The OM-5 is close enough that people ask. The differences:

Different model id in every header (updater very likely rejects it), different block 3 loader, USB-PD code for absent
hardware, different SD-pin GPIO setup, 5 factory calibration entries the E-M5 III never got, different settings store.
Each is fixable piece by piece (which is what porting does), but a whole-image flash risks a brick with no known recovery
outside block0. [code] for the differences, [inferred] for the outcome.
OM-5 = E-M5 III-class hardware + USB-C/PD running the E-M1 III software branch.

