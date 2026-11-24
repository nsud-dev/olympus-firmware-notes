# Body comparison: technical notes

> **Technical notes.** This page is the dense reference. For a readable introduction, start with [Body comparison](comparison.md).

This page puts the camera bodies we have looked at side by side: which chip generation each uses, how much memory, and
which features its firmware contains. It explains why the OM-5 is our main source ("donor") for features, and why you
can't simply flash an OM-5 firmware onto an E-M5 III.

All bodies here use the same firmware container (header, obfuscation and checksum) and an MN103-family control CPU that the
am33-2 tools decode. All but the E-M5 (Mark I) use block0 base 0x60021020; the Mark I uses 0x7e421020.
[code] TruePic is Olympus's name for the whole processor chip (see [SoC overview](../hardware/soc-overview.md)).

| | E-M5 III | OM-5 | OM-5 II | E-M1 III | OM-1 | OM-1 II | PEN-F | E-M5 II | E-M5 (I) |
|---|---|---|---|---|---|---|---| --- | --- |
| file / fw | E_137 1.7 | E_144 1.2 | E_148 1.1 | E_139 1.6 (1.4) | E_143 1.9 | E_146 1.3 | E_122 3.1 | E_118 4.1 | E_097 2.3 |
| magic | OE 13 70 | OE 14 40 | OE 14 80 | OE 13 90 | OE 14 30 | OE 14 60 | OE 12 20 | OE 11 80 | OE 09 70 |
| TruePic | VIII | IX | IX | IX | X | X | VII | VII | VI |
| blocks | 5 | 5 | 5 | 6 | 6 (+sub-CPU) | 6 | 4 | 4 | 5 |
| block0 LZ4 sections | none | 2 | 2 | 2 | none (32 MB) | none | none | none | none |
| buffer map / DRAM class | 1 GB | 1 GB | 1 GB | 2 GB | 2 GB | 2 GB | ? | ? | ? |
| MN103 cores seen | CPU0-2 | CPU0-2 | CPU0-2 | CPU0-2 | CPU0-3 | CPU0-3 | CPU0-2 | CPU0-2 | CPU0-1 (CPU2 rare) |
| ARM | A9, Linux 4.4 | A9, 4.4 | A9, 5.10 | A9, 4.4 | A53, 4.14 | A53, 4.14 | none (BCM43362 over SDIO) | none | none |
| Wi-Fi | CYW43455 | CYW43455 | CYW43439 | CYW43455 | CYW43455 | CYW43455 | BCM43362 | BCM43362 (SDIO, run by the MN103) | none |
| setting IDs | 0-1649 | 0-1892 | more | | | | |  |  |
| English GUI lang index | 8 | 5 | 5 | 8 | | | |  |  |
| DSP jobs 11/12 | absent | yes | yes | yes | new gen (no match) | new gen | own job set (same program format) | own job set (same program format) | no programs of this format |
| Live ND | plumbing off (ported by us) | ND2-16 | ND2-16 (ND64/128 strings only) | yes, 32-frame table | ND2-64 | ND2-128 | no | no | no |
| Live GND | no | no | UI only (stubs) | no | no | **yes** (`iseq_half_nd`) | no | no | no |
| HHHR | tripod HR only; ARM `hhhr` present | yes (50 MP) | yes (jobs 14/15 changed) | yes | yes | yes | tripod High Res only | tripod High Res only (40 MP) | no pixel shift |
| Starry Sky AF | no | yes | yes + start triggers | yes | yes | yes | no | no | no |
| DL subject detect | no | dead code | dead code + menu | dead code | **yes** (CPU3 + DML) | yes | no | no | no |
| USB webcam (UVC) | no (ported partly) | yes | yes | no | no | yes | no | no | no |
| USB-C / PD | no (micro-USB) | code only (micro-USB [camera] 2026-11-23) | yes | yes | yes | yes | no | no | no |
| function match → E-M5 III | — | 82% | 77% | 83% | not measured | | | not measured (code shape: see below) | not measured |

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
- **To the E-M5 II and E-M5 (Mark I):** see [Older bodies](#older-bodies-e-m5-ii-and-e-m5-mark-i-2026-11-21) below.


## Older bodies: E-M5 II and E-M5 (Mark I) (2026-11-21)

Compared here: E-M5 II 4.1 (`OLY_E_118_4100`, block0 names itself `E-M5MarkII`) and E-M5 (Mark I) 2.3 (`OLY_E_097_2300`,
`E-M5`). Static comparison only: no camera, no builds, no emulator. Numbers and scripts are in the decomp repo (link at the
end). In short: **the E-M5 II is a PEN-F in a different body, and both are a different chip from the E-M5 III. The
E-M5 Mark I is one more generation back and shares little beyond the container and the CPU family.** The E-M5 III to OM-5
step is small; the E-M5 III to E-M5 II step is large, roughly as far as the E-M5 III is from the OM-1.

### How different, layer by layer

| layer | E-M5 III 1.7 | E-M5 II 4.1 | E-M5 (I) 2.3 |
|---|---|---|---|
| container | 5 blocks, inverted + shuffled, sum-to-zero checksum | same format, 4 blocks, all checksums OK [code] | same format, 5 blocks, all checksums OK; different layout: main program at 0x902c0000, a 64 KB MN103 block of type 0x107 at 0x40060000 (looks like a loader) [code] |
| control CPU | MN103 / AM33-2, CPU0-2 | same, CPU0-2 named [code] | MN103 family (decodes cleanly with the am33-2 tools); CPU0 and CPU1 named, CPU2 only 3 times [code] |
| block0 base | 0x60021020 | 0x60021020 [code] | **0x7e421020**; working RAM constants at 0x6019xxxx-0x601fxxxx [code] |
| OS | μITRON + Rhapsody OXF | μITRON + Rhapsody OXF (`itronos`, `rhapsody/oxf`, `omreactive`) [code] | μITRON, **no Rhapsody OXF**: an older `ntos.cpp` layer, 76 C++ sources instead of ~740 [code] |
| application layer | `OlyApi*`, `SubApp*`, `Cmp*` components | the same layers [code] | the same naming already (`OlyApiShooting`, `SubAppState*`, `Cmp*`), fewer components [code] |
| SoC peripherals (register constants, Jaccard vs E-M5 III) | 1.00 (OM-5: 0.94) | **0.21**; vs PEN-F **0.98** [code] | **0.05**; vs E-M5 II 0.11 [code] |
| code shape (share of E-M5 III 8-instruction shapes also found) | (OM-5: 59.5%) | 27.3%; E-M5 II vs PEN-F 63.6% [code] | 11.5% [code] |
| source files named in block0 (shared with E-M5 III of 1076) | | 921 of 975; 971 shared with PEN-F [code] | 103 of 292 [code] |
| image engine | 320-bit microcode jobs 0-10 (bank 6); OM-5 jobs 11/12 run on it [camera] | **same program format**: the empty stub and the memcpy job are byte-identical to the E-M5 III's; its own jobs 7-13, 15-17 (the PEN-F's 7/13/15/16/17 byte-identical); E-M5 III-type job bank only 17% shared; same job-address register 0x9d200010 [code] | **no job programs of this format in any block**, no 0x9d200010 reference (the 0x9d000000 window is still referenced) [code]; a different or fixed-function engine [inferred] |
| image-engine resource banks | | banks 1-3 and the 0x14000 bank 93-98% identical to the E-M5 III's [code] | different layout, not compared [code] |
| GPU / drawing | DMP GPU, OpenVG (`vg*DMP`), `c3d`; OSD `gpiDraw*` | the same DMP OpenVG set and `gpiDrawOsd*` calls (fewer `vg*` names) [code] | a GPU (`play_gpu.c`, `c3d_dbg`, GL-style error strings) but **no OpenVG** names; `drawOsdStart/End` and `GPISetPalette` present, no `gpiDrawOsd*` [code] |
| ARM co-processor | Cortex-A9, Linux, Wi-Fi/BLE, `hhhr` helper | **none**: no ELF, kernel or device tree in any block [code] | none [code] |
| Wi-Fi / Bluetooth | CYW43455 on the ARM; BLE | **BCM43362 driven by the MN103 itself** over SDIO (`wlanapi_sdio_*`); Bluetooth strings are the old OBEX/accessory kind, no BLE [code] | **no Wi-Fi code** (no FlashAir/iSDIO either) [code] |
| settings | `MODE_*` key table (4853 names), saved by "acc flash write" | `MODE_*` key table (4192 names, block 2); no "acc flash write" [code] | no `MODE_*` key table in any block; settings stored differently [code] |
| card updater | `DCOLYMP`, `FIRMUP_CLI` in block0 | same [code] | same names [code]; recovery design very likely the same [inferred] |
| stabiliser sub-CPU | "LUKE" program in block 3 | no LUKE block; `SCPU_FIRMUP` strings [code] | `scpu_firmup.c`, `scpu_version` [code] |
| flash chip | | | NAND debug commands under `[TOSHIBA]` (`tnan`) [code] |

### What our work could do on these bodies [inferred unless marked]

**The rule of thumb:** on the E-M5 III we port from the OM-5 because 82% of its functions match. On the E-M5 II the
equivalent donor is the **PEN-F** (same chip, 98% of register constants, 971 shared source files), not the OM-5. Our
E-M5 III code and addresses don't carry over to the E-M5 II; the *methods* (where to look, how to hook, how to test) do.
On the E-M5 Mark I very little carries over beyond the container tools and the CPU tools.

| our work (E-M5 III) | E-M5 II 4.1 | E-M5 (I) 2.3 |
|---|---|---|
| firmware tools (unpack, checksum check) | **as-is**: unpacks, checksums verify [code] | **as-is**: unpacks, checksums verify [code]; the camera accepting a repack is untested |
| MN103 tools (objdump, Ghidra module, eqsim) | **as-is** for decoding [code]; symbols and decomp don't carry over | decoding works [code]; use base 0x7e421020; whether the CPU has AM33-2-only instructions not checked |
| focus stacking with any lens | **re-port**: in-camera stacking code is present (`MODE_FOCUS_STACKING_ONOFF`, `MODE_FOCUS_STACKING_ENABLED_LENS`, "Wait For Combining Finish") [code]; the E-M5 III-shaped lens check was not found (best shape match 13/25), so the gate needs its own trace; whether the menu offers stacking not checked | **impossible as a patch**: no stacking or focus-bracket strings [code] |
| Live ND | **re-port, large; feasibility open**: no ND code; the engine runs the same program format, so OM-5 jobs 11/12 *might* load, but the parameter setters, pools, sensor modes and capture path are all different code on a different chip. Native Live Time/Live Bulb exist [code]. First step would be running one OM-5 job on the E-M5 II (camera) | **very likely impossible**: no programmable-engine programs to run the merge; a CPU merge of full frames would be far too slow [inferred] |
| Live GND | as Live ND, plus a per-row gain path; not checked | as Live ND |
| HHHR (hand-held High Res) | **impossible as designed**: our port needs the ARM `hhhr` helper and jobs 14-17; the E-M5 II has no ARM. Tripod High Res is native (`pixshift_*`) [code] | impossible: no pixel shift [code] |
| Starry Sky AF | re-port; AF code differs; not checked | not checked; very unlikely to be worth it |
| colour / mono profile + editor (looks) | **re-port from the PEN-F, promising**: the E-M5 II lacks the `ColorCreator2`/`MonochromeCreator` back end that the E-M5 III kept [code], but the PEN-F, which has the whole feature, is the same chip and mostly the same code. A PEN-F → E-M5 II profile port is the E-M5 II's natural "OM-5 donor" project | impossible in practice: no back end, no near donor [code for absence] |
| native menu rows with saved values, dev menu | **re-port**: same `MODE_*` key-table and `SubApp`/`OlyApi` design [code]; the saved-values store differs (no "acc flash write") [code] | **re-port from scratch**: no `MODE_*` table; older framework [code] |
| card console, Wi-Fi debug shell | **re-port**: the debug shell (`skey`, `memdump`, `sdk api`) and card updater are present [code]; the entry route (property callback) and section hooks need finding | shell commands present (`skey`, `memdump`, `sdk api`) [code]; no Wi-Fi; re-port |
| drawing on screen (OSD `gpi` calls, c3d/OpenVG) | **method carries**: the same `gpiDrawOsd*` and DMP OpenVG calls [code]; addresses differ | partly: OSD start/end and palette calls present, the `gpiDraw*` names and OpenVG are not [code] |
| image-engine job submission (0x9d000000 window, 0x9d200010) | **method carries**: same window and program register referenced [code]; the job setter tables need finding | no programs of this format [code] |
| USB webcam (UVC) | no UVC descriptors (same as the PEN-F) [code]; the tether (`camecon`) path exists [code] | not checked |
| BLE geotagging | impossible: no BLE radio code [code] | impossible: no radio [code] |

How these were checked: string and constant scans of block0, operand-masked instruction-shape hashes, register-constant
sets, resource-bank chunk hashes and job-program hashes. "Present" means the code or data exists, not that it was tried.
Nothing here has been run on an E-M5 II or E-M5 Mark I.


## Why not just cross-flash the OM-5 image?

The OM-5 is close enough that people ask. The differences:

Different model id in every header: the E-M5 III card updater checks it and rejects an OM-5 file before writing
anything (result 0x3202, 0 flash writes, run natively in om-emu; see [Recovery](../firmware/recovery.md)) [code]. So a
cross-flash would first need the headers relabelled. Beyond that: a different block 3 (the IS sub-CPU program, whose
command ids are shifted against the E-M5 III's, see [stabiliser](../hardware/stabiliser.md)), USB-PD code for absent
hardware, different SD-pin GPIO setup, 5 factory calibration entries the E-M5 III never got (the other 172 of 173 are at the
same offsets and sizes), different settings store. Each is fixable piece by piece (which is what porting does), but a
whole-image flash risks a brick with no known recovery outside block0. [code] for the differences, [inferred] for the outcome.
One more reason [inferred] 2026-11-22: the card updater lives in block0, so a camera running OM-5 block0 would run the
OM-5's updater, which looks for `E144????BIN` and the OM-5 model; the stock E-M5 III file would most likely be refused,
leaving no card route back.
OM-5 = E-M5 III-class hardware ~~+ USB-C/PD~~ running the E-M1 III software branch (corrected 2026-11-23: the OM-5 port is micro-USB [camera]; the PD code is inherited from the E-M1 III, and the OM-5 II adds the USB-C hardware). The firmware shows no difference in the
display controller, sensor, Wi-Fi/BT module or ARM device tree; buttons, dials, panels and battery were not checked.

