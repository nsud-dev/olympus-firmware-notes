# Body comparison: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Body comparison](comparison.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

This page puts the camera bodies we have looked at side by side. It covers which chip generation each uses, how much
memory it has and which features its firmware contains. It explains why the OM-5 is our main source ("donor") of
features, and why an OM-5 firmware image can't simply replace the E-M5 III's.

All bodies here use the same firmware container, meaning the same header, obfuscation and checksum. Their control CPU is
from the MN103 family, which the am33-2 tools decode.[^fw1] All but the E-M5 (Mark I) share one block0 base address. The
Mark I has its own (see [Address reference](#address-reference)).[^fw1] TruePic is Olympus's name for the whole
processor chip (see [SoC overview](../hardware/soc-overview.md)).

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred.

## Bodies at a glance

| | E-M5 III | OM-5 | OM-5 II | E-M1 III | OM-1 | OM-1 II | PEN-F | E-M5 II | E-M5 (I) |
|---|---|---|---|---|---|---|---|---|---|
| file / fw | E_137 1.7 | E_144 1.2 | E_148 1.1 | E_139 1.6 (1.4) | E_143 1.9 | E_146 1.3 | E_122 3.1 | E_118 4.1 | E_097 2.3 |
| magic | OE 13 70 | OE 14 40 | OE 14 80 | OE 13 90 | OE 14 30 | OE 14 60 | OE 12 20 | OE 11 80 | OE 09 70 |
| TruePic | VIII | IX | IX | IX | X | X | VII | VII | VI |
| blocks | 5 | 5 | 5 | 6 | 6 (+sub-CPU) | 6 | 4 | 4 | 5 |
| block0 LZ4 sections | none | 2 | 2 | 2 | none (32 MB) | none | none | none | none |
| buffer map / DRAM class | 1 GB | 1 GB | 1 GB | 2 GB | 2 GB | 2 GB | ? | ? | ? |
| MN103 cores seen | CPU0-2 | CPU0-2 | CPU0-2 | CPU0-2 | CPU0-3 | CPU0-3 | CPU0-2 | CPU0-2 | CPU0-1 (CPU2 rare) |
| ARM | A9, Linux 4.4 | A9, 4.4 | A9, 5.10 | A9, 4.4 | A53, 4.14 | A53, 4.14 | none (BCM43362 over SDIO) | none | none |
| Wi-Fi | CYW43455 | CYW43455 | CYW43439 | CYW43455 | CYW43455 | CYW43455 | BCM43362 | BCM43362 (SDIO, run by the MN103) | none |
| setting IDs | 0-1649 | 0-1892 | more | | | | | | |
| English GUI lang index | 8 | 5 | 5 | 8 | | | | | |

*Firmware file, chip and platform by body. ? = not checked. An empty cell means not looked at.*

| | E-M5 III | OM-5 | OM-5 II | E-M1 III | OM-1 | OM-1 II | PEN-F | E-M5 II | E-M5 (I) |
|---|---|---|---|---|---|---|---|---|---|
| image-engine jobs 11/12 | absent | yes | yes | yes | new gen (no match) | new gen | own job set (same program format) | own job set (same program format) | no programs of this format |
| Live ND | plumbing off (ported by us) | ND2-16 | ND2-16 (ND64/128 strings only) | yes, 32-frame table | ND2-64 | ND2-128 | no | no | no |
| Live GND | no | no | UI only (stubs) | no | no | **yes** (`iseq_half_nd`) | no | no | no |
| HHHR | tripod HR only. ARM `hhhr` present | yes (50 MP) | yes (jobs 14/15 changed) | yes | yes | yes | tripod High Res only | tripod High Res only (40 MP) | no pixel shift |
| Starry Sky AF | no | yes | yes + start triggers | yes | yes | yes | no | no | no |
| DL subject detect | no | dead code | dead code + menu | dead code | **yes** (CPU3 + DML) | yes | no | no | no |
| USB webcam (UVC) | no (ported partly) | yes | yes | no | no | yes | no | no | no |
| USB-C / PD | no (micro-USB) | code only (micro-USB[^cam1]) | yes | yes | yes | yes | no | no | no |
| function match → E-M5 III | — | 82% | 77% | 83% | not measured | | | not measured (code shape: see below) | not measured |

*Features by body. HHHR is hand-held High Res, DL deep learning, PD USB power delivery. Empty = not looked at.*

## Donor rules

Each body serves a different purpose as a donor.[^pol1]

- **OM-5 1.2** for code, the memory model and the image-engine jobs (Live ND, HHHR, Star AF, AF features).
- **OM-5 II** only for what it adds.
- **E-M1 III** for hook placement, because its fcs is a superset of the E-M5 III's.
- **OM-1, OM-1 II and OM-3** for logic and maths references only (ND32 and up, Live GND), because their image-engine
  jobs and memory don't fit.

## Shared code

Much of what we found on the E-M5 III is shared code, so it is a lead on the other bodies too. This table comes from a
plain scan of each body's main program (block0) for strings and constants that belong to each item. The OM-5, OM-5 II
and E-M1 III were scanned on their expanded images.[^fw2] **Present means the item's strings or constants are in the
firmware, not that it was tried or behaves the same.**

| item | E-M5 III 1.7 | OM-5 1.2 | OM-5 II 1.1 | E-M1 III 1.6 | OM-1 1.9 | PEN-F 3.1 | why it matters |
|---|---|---|---|---|---|---|---|
| debug shell commands `ui key skey`, `file memdump`, `take dbgmode` | yes | yes | yes | yes | yes | yes | remote key presses, RAM dumps to the card, event trace ([Wi-Fi debug shell](../features/wifi-debug-shell.md)) |
| `sdk api` command set | yes | yes | yes | yes | yes | yes | on the E-P7 its handlers were found to be a large block of code reachable only from the shell, a free-space candidate (Caduceus E-P7) |
| card updater folder `DCOLYMP` | yes | yes | yes | yes | yes | yes | the same recovery route ([recovery](../firmware/recovery.md)) |
| settings image saved by "acc flash write" | yes | yes | yes | yes | yes | not found | where saved mod settings can live ([saved settings](../features/saved-settings-and-menu-rows.md)) |
| setting → property table, same first entries | yes | yes | yes | yes | yes | yes | the same menu and settings design ([Settings and menus](../guides/settings-and-menus.md)) |
| RGB histogram path (`YRGB`, `getHistogram`) | yes | yes | yes | yes | yes | yes | per-channel histograms are native code ([display](../hardware/display.md)) |
| loader access-monitor register (`0x99700040`) | yes | yes | yes | yes | yes | yes | sections must be ready before a hook touches them ([boot and sections](../firmware/boot-and-sections.md)). On the OM-5 II the same monitor was traced by the Caduceus OM-5 project |
| ARM loader from the card (`C:\TARGET`) | yes | yes | yes | yes | no | no | loading ARM code from the card ([ARM co-processor](../hardware/arm-coprocessor.md)). The OM-1's ARM is a different (64-bit) design |
| `DigitalNd` (Live ND engine) | no | yes | yes | yes | yes | no | where native Live ND lives ([Live ND](../features/live-nd.md)) |

*Shared items by body, from a string and constant scan of each main program.[^fw2]*

A "yes" tells you where to start looking on your body. The addresses differ on every build, and each body needs its own
check. The per-technique tables on [Modifying the firmware](../firmware/patching-techniques.md) record which bodies a
technique has actually been shown on.

## Our features on the other bodies

For each feature we have built or are building on the E-M5 III, the table answers two questions. Does another body
already have it natively? If not, does it have the parts our port uses? It is a static check only, with no camera, no
builds and no emulator runs.[^fw3] **"Present" means the code or data exists in the firmware, not that it works or was
tried.**

Each cell says how it was checked.

- **S** means strings or constants in block0.
- **C** means code read or matched, by a relocation-masked function match or by disassembly of the counterpart.
- **K** means an earlier finding in these notes, linked from the feature's page.

| feature (E-M5 III state) | OM-5 1.2 | OM-5 II 1.1 | E-M1 III 1.6 | OM-1 1.9 | OM-1 II 1.3 | PEN-F 3.1 |
|---|---|---|---|---|---|---|
| Live ND (our port, menu rows working) | native ND2-16 (S, K) | native ND2-16 (S, K) | native (S, K) | native ND2-64 (S, K) | native ND2-128 (S, K) | absent: no `iseq_nd`, no `DigitalNd` (S). Image-engine jobs 11/12 not checked |
| Live GND (not ported) | absent (S) | UI strings only (K) | absent (S) | absent (S) | native `iseq_half_nd` (S, K) | absent (S) |
| HHHR, hand-held High Res (our port in progress) | native (S, K) | native (S, K) | native (S, K) | native (S, K) | native (S, K) | absent. Tripod High Res only (`pixshift_sr` strings, no hand-held) (S) |
| Starry Sky AF (test build made, not run) | native (S, K) | native + start options (S, K) | native (S, K) | native (S) | native (S) | absent: no astro strings (S) |
| Focus stacking with any lens (done on camera) | same lens check, branch at `0x606d63fb` (C) | `0x606d5524` (C) | `0x606983f9` (C) | `0x608e3899` (C) | `0x608fd3f2` (C) | no in-camera stacking: check name string present but never referenced, no stacking strings (S, C) |
| Native menu rows with saved values (our method, works on camera) | settings design shared, getter counterpart found (S, C, K). Free gap not checked | same | same. Setter matches in shape (C) | same | same | different: no "acc flash write" settings image (S). Getter shape found (C) |
| Color / Mono Profile back end (E-M5 III: present, no stock UI. Ours added in test builds) | present (S, K) | present (S, K) | present (S, K) | present (S) | present (S) | present, native feature (K) |
| Profile editor wheel renderers (CC2 / Mono / Shading. E-M5 III: stubs, E-M1 III ones relocated in our test builds) | none, cases removed (K) | none (C: 0 of 46/26/14 chunks) | full (K) | close relative: 31/46, 18/26, 10/14 chunks (C) | 28/46, 16/26, 7/14 (C) | older version: 19/46, 8/26, 4/14 (C) |
| Profile editor screens (kinds -20/-23) | no (K) | no profile picture modes (K, om-emu) | no (K) | not checked | not checked | yes, the only shipped editor (K) |
| USB webcam (UVC. Ours parked) | native (S, C: UVC descriptors) | native (S, C) | no UVC descriptors (C) | no UVC descriptors (C) | native (S, C) | no UVC descriptors (C) |
| Sync IS for Panasonic lenses (no flag-only patch on E-M5 III) | same copt + `L_STAT_PANA` design (S). Verdict likely the same[^inf1] | same | same | same | same | no copt strings (S) |
| Wi-Fi debug shell via card file (works on E-M5 III) | F971 callback matches in shape (C), shell commands (S) | same | same | same | same | shell commands present, callback differs (4/5 chunks) (S, C) |
| Card console after section 10 (works on camera) | shell present (S). Section-end site not located | same | same | same | same | same |

*Our E-M5 III features on the other bodies. S, C and K say how each cell was checked.[^fw3]*

`fmatch.py` disassembles the E-M5 III (or E-M1 III) function, masks call and jump operands and address-like constants,
and looks for it in each body. "n/m chunks" is how many 8-instruction pieces were found near one place. A low count is
not proof of absence, because struct offsets and setting ids shift between bodies.

The focus-stack branch was confirmed by disassembly. Every body from the OM-5 on has the same function shape, with the
`bne` (`c9 04`) that our patch replaces at the same offset (`+0x16`).[^fw3]

The porting outlook follows from the table.[^inf2]

- **To the OM-5, OM-5 II, E-M1 III and OM-1 family.** Live ND, HHHR and Starry Sky AF are already native. These carry
  over:
    - the any-lens focus stack patch (the same one branch, with an address per body)
    - menu rows with saved values (the same settings design, new addresses)
    - the card console and the Wi-Fi shell
    - the profile editor. Its back end is everywhere. The E-M1 III and OM-1 family still have the wheel renderers, and
      the OM-5 and OM-5 II don't.
- **To the PEN-F.** Live ND, HHHR and Starry Sky AF are absent there and would be full ports onto an older chip
  (TruePic VII). Whether its image engine has the jobs they need is not checked. The profile editor is native there.
- **To the E-M5 II and E-M5 (Mark I).** See [Older bodies](#older-bodies-e-m5-ii-and-e-m5-mark-i) below.

## Older bodies: E-M5 II and E-M5 (Mark I)

This section compares the E-M5 II 4.1 (`OLY_E_118_4100`, block0 names itself `E-M5MarkII`) and the E-M5 (Mark I) 2.3
(`OLY_E_097_2300`, `E-M5`). It is a static comparison only, with no camera, no builds and no emulator.[^fw4]

**The E-M5 II is a PEN-F in a different body, and both are a different chip from the E-M5 III.** The E-M5 Mark I is one
more generation back and shares little beyond the container and the CPU family. The step from the E-M5 III to the OM-5
is small. The step from the E-M5 III to the E-M5 II is large, roughly as far as the E-M5 III is from the OM-1.[^fw4]

### Layer by layer

The table compares the three bodies one layer at a time, from the file container up to the stabiliser sub-CPU.

<details><summary>All layers compared</summary>

| layer | E-M5 III 1.7 | E-M5 II 4.1 | E-M5 (I) 2.3 |
|---|---|---|---|
| container | 5 blocks, inverted + shuffled, sum-to-zero checksum | same format, 4 blocks, all checksums OK | same format, 5 blocks, all checksums OK. Different layout: main program at `0x902c0000`, a 64 KB MN103 block of type `0x107` at `0x40060000` (looks like a loader) |
| control CPU | MN103 / AM33-2, CPU0-2 | same, CPU0-2 named | MN103 family (decodes cleanly with the am33-2 tools). CPU0 and CPU1 named, CPU2 only 3 times |
| block0 base | `0x60021020` | `0x60021020` | **`0x7e421020`**. Working RAM constants at `0x6019xxxx`-`0x601fxxxx` |
| OS | μITRON + Rhapsody OXF | μITRON + Rhapsody OXF (`itronos`, `rhapsody/oxf`, `omreactive`) | μITRON, **no Rhapsody OXF**: an older `ntos.cpp` layer, 76 C++ sources instead of ~740 |
| application layer | `OlyApi*`, `SubApp*`, `Cmp*` components | the same layers | the same naming already (`OlyApiShooting`, `SubAppState*`, `Cmp*`), fewer components |
| SoC peripherals (register constants, Jaccard vs E-M5 III) | 1.00 (OM-5: 0.94) | **0.21**. vs PEN-F **0.98** | **0.05**. vs E-M5 II 0.11 |
| code shape (share of E-M5 III 8-instruction shapes also found) | (OM-5: 59.5%) | 27.3%. E-M5 II vs PEN-F 63.6% | 11.5% |
| source files named in block0 (shared with E-M5 III of 1,076) | | 921 of 975. 971 shared with PEN-F | 103 of 292 |
| image engine | 320-bit microcode jobs 0-10 (bank 6). OM-5 jobs 11/12 run on it[^cam2] | **same program format**: the empty stub and the memcpy job are byte-identical to the E-M5 III's. Its own jobs 7-13, 15-17 (the PEN-F's 7/13/15/16/17 byte-identical). E-M5 III-type job bank only 17% shared. Same job-address register `0x9d200010` | **no job programs of this format in any block**, no `0x9d200010` reference (the `0x9d000000` window is still referenced). A different or fixed-function engine[^inf3] |
| image-engine resource banks | | banks 1-3 and the `0x14000` bank 93-98% identical to the E-M5 III's | different layout, not compared |
| GPU / drawing | DMP GPU, OpenVG (`vg*DMP`), `c3d`. OSD `gpiDraw*` | the same DMP OpenVG set and `gpiDrawOsd*` calls (fewer `vg*` names) | a GPU (`play_gpu.c`, `c3d_dbg`, GL-style error strings) but **no OpenVG** names. `drawOsdStart/End` and `GPISetPalette` present, no `gpiDrawOsd*` |
| ARM co-processor | Cortex-A9, Linux, Wi-Fi/BLE, `hhhr` helper | **none**: no ELF, kernel or device tree in any block | none |
| Wi-Fi / Bluetooth | CYW43455 on the ARM. BLE | **BCM43362 driven by the MN103 itself** over SDIO (`wlanapi_sdio_*`). Bluetooth strings are the old OBEX/accessory kind, no BLE | **no Wi-Fi code** (no FlashAir/iSDIO either) |
| settings | `MODE_*` key table (4,853 names), saved by "acc flash write" | `MODE_*` key table (4,192 names, block 2). No "acc flash write" | no `MODE_*` key table in any block. Settings stored differently |
| card updater | `DCOLYMP`, `FIRMUP_CLI` in block0 | same | same names. Recovery design very likely the same[^inf3] |
| stabiliser sub-CPU | "LUKE" program in block 3 | no LUKE block. `SCPU_FIRMUP` strings | `scpu_firmup.c`, `scpu_version` |
| flash chip | | | NAND debug commands under `[TOSHIBA]` (`tnan`) |

*The E-M5 III, E-M5 II and E-M5 (Mark I) layer by layer. Read in the firmware unless a cell has its own note.[^fw4]*

</details>

### Our work on these bodies

On the E-M5 III we port from the OM-5 because 82% of its functions match. On the E-M5 II the equivalent donor is the
**PEN-F**, not the OM-5. It is the same chip, shares 98% of register constants and 971 source files.[^fw4] Our E-M5 III
code and addresses don't carry over to the E-M5 II. The *methods* do, meaning where to look, how to hook and how to
test.[^inf3] On the E-M5 Mark I very little carries over beyond the container tools and the CPU tools.[^inf3]

<details><summary>Our E-M5 III work, item by item</summary>

| our work (E-M5 III) | E-M5 II 4.1 | E-M5 (I) 2.3 |
|---|---|---|
| firmware tools (unpack, checksum check) | **as-is**: unpacks, checksums verify[^fw4] | **as-is**: unpacks, checksums verify[^fw4]. The camera accepting a repack is untested |
| MN103 tools (objdump, Ghidra module, eqsim) | **as-is** for decoding[^fw4]. Symbols and decomp don't carry over | decoding works[^fw4]. Use the Mark I base address. Whether the CPU has AM33-2-only instructions not checked |
| focus stacking with any lens | **re-port**: in-camera stacking code is present (`MODE_FOCUS_STACKING_ONOFF`, `MODE_FOCUS_STACKING_ENABLED_LENS`, "Wait For Combining Finish")[^fw4]. The E-M5 III-shaped lens check was not found (best shape match 13/25), so the gate needs its own trace. Whether the menu offers stacking not checked | **impossible as a patch**: no stacking or focus-bracket strings[^fw4] |
| Live ND | **re-port, large. Feasibility open**: no ND code. The engine runs the same program format, so OM-5 jobs 11/12 *might* load, but the parameter setters, pools, sensor modes and capture path are all different code on a different chip. Native Live Time/Live Bulb exist[^fw4]. First step would be running one OM-5 job on the E-M5 II (camera) | **very likely impossible**: no programmable-engine programs to run the merge. A CPU merge of full frames would be far too slow[^inf3] |
| Live GND | as Live ND, plus a per-row gain path. Not checked | as Live ND |
| HHHR (hand-held High Res) | **impossible as designed**: our port needs the ARM `hhhr` helper and jobs 14-17. The E-M5 II has no ARM. Tripod High Res is native (`pixshift_*`)[^fw4] | impossible: no pixel shift[^fw4] |
| Starry Sky AF | re-port. AF code differs. Not checked | not checked. Very unlikely to be worth it |
| colour / mono profile + editor (looks) | **re-port from the PEN-F, promising**: the E-M5 II lacks the `ColorCreator2`/`MonochromeCreator` back end that the E-M5 III kept[^fw4], but the PEN-F, which has the whole feature, is the same chip and mostly the same code. A PEN-F → E-M5 II profile port is the E-M5 II's natural "OM-5 donor" project | impossible in practice: no back end, no near donor[^fw5] |
| native menu rows with saved values, dev menu | **re-port**: same `MODE_*` key-table and `SubApp`/`OlyApi` design[^fw4]. The saved-values store differs (no "acc flash write")[^fw4] | **re-port from scratch**: no `MODE_*` table. Older framework[^fw4] |
| card console, Wi-Fi debug shell | **re-port**: the debug shell (`skey`, `memdump`, `sdk api`) and card updater are present[^fw4]. The entry route (property callback) and section hooks need finding | shell commands present (`skey`, `memdump`, `sdk api`)[^fw4]. No Wi-Fi. Re-port |
| drawing on screen (OSD `gpi` calls, c3d/OpenVG) | **method carries**: the same `gpiDrawOsd*` and DMP OpenVG calls[^fw4]. Addresses differ | partly: OSD start/end and palette calls present, the `gpiDraw*` names and OpenVG are not[^fw4] |
| image-engine job submission (`0x9d000000` window, `0x9d200010`) | **method carries**: same window and program register referenced[^fw4]. The job setter tables need finding | no programs of this format[^fw4] |
| USB webcam (UVC) | no UVC descriptors (same as the PEN-F)[^fw4]. The tether (`camecon`) path exists[^fw4] | not checked |
| BLE geotagging | impossible: no BLE radio code[^fw4] | impossible: no radio[^fw4] |

*Our E-M5 III work on the older bodies. Verdicts are inferred unless a cell has a firmware note.[^inf3]*

</details>

These were checked with string and constant scans of block0, operand-masked instruction-shape hashes, register-constant
sets, resource-bank chunk hashes and job-program hashes. "Present" means the code or data exists, not that it was
tried. Nothing here has been run on an E-M5 II or E-M5 Mark I.

## OM-3 1.1

The OM-3 is an OM-1 II with different controls, not an OM-5 relative. This is a static comparison only, with no camera,
no builds and no emulator runs. The file is `OLY_E_147_1100` (body code E147).[^fw6]

| item | OM-3 1.1 | compared with |
|---|---|---|
| line | TruePic X, OM-1 family: same six-block map as the OM-1 II, same block0 boot stub (first 42 bytes) | OM-1 II 1.3 |
| block0 base | **`0x60021020`**: 31,286 pointers land on string starts at this base, under 2,300 at any nearby offset | same as every body since the E-M5 III |
| MN103 control cores | **four** (CPU0-CPU3): the `sys_callrequest_info[CPUx]<-[CPUy]` table is 4 x 4, no CPU4+ strings | OM-1, OM-1 II: four. OM-5 family: three |
| clock list | identical to the OM-1 II, including `CLKDML`, `CLKDETA/B`, `CLKGPU`, `CLKIMGA-G` and PCIe | |
| deep-learning block | **yes**: `CLKDML`, `MDET_DL_CPU3_*`, `DL_CPU3_DML_COMPLETE`. Six 9.3 MB weight blobs, byte-identical to the OM-1 II's six (the OM-1 has the first five) | OM-1 II |
| ARM co-processor | **two Cortex-A53 cores**: device tree (`ntcj,nep1`, `cpu@0`, `cpu@1`) byte-identical to the OM-1 and OM-1 II, kernel config `CONFIG_NR_CPUS=2`, Linux 4.14.222 (kernel build date 26 February 2025) | OM-1 II |
| ARM userland | same 2,205-file root fs as the OM-1 II apart from the Wi-Fi/Bluetooth firmware | OM-1 II |
| Wi-Fi | **CYW43439** (`cyfmac43439-sdio`, `CYW4343A2` Bluetooth patch), the OM-5 II's chip, not the OM-1 family's CYW43455 | OM-5 II |
| image-engine jobs | 21 jobs, byte-identical to the OM-1 II ([image engine](../hardware/image-engine-technical.md)). None shared with the OM-5 II | OM-1 II |
| memory map | 2 GB class: same buffer-pool end constant `0xff124000` as the OM-1 II (51 uses each), so the same ~2 GB layout[^inf6] | OM-1 II |
| stabiliser and sub-CPU blocks | own builds (about 50% and 40% of bytes equal to the OM-1 II's) | |
| main program | 82% of operand-masked 8-instruction sequences also occur in the OM-1 II, 68% in the OM-5 II (whole block0, data included) | |

*The OM-3 against its closest relatives. Read in the firmware unless a cell has its own note.[^fw6]*

The OM-3's feature code in block0 matches the OM-1 II's.

| feature | OM-3 1.1 | how checked |
|---|---|---|
| Live ND | native **ND2-ND128**: the level builder has the OM-1 II's `cmp 128` / `cmp 256` steps (`0x6031a800`), light-table frame cap 128 (`0x608a8a4a`..) | byte patterns from the OM-1 II sites |
| Live GND | native, the OM-1 II's `iseq_half_nd` engine. The engine area matches the OM-1 II at 99.4% of instructions (operand-masked diff of 21,440 instructions, OM-1 II `0x60890000`-`0x608a0000` against OM-3 `+0x6d8f`), and the parameter maths (`func_calc_comp_prm` and the two functions after it, OM-3 `0x608a03f1`-`0x608a0979`) is identical apart from addresses | instruction diff |
| hand-held High Res, Starry Sky AF | native (`pixshift_sr`, `star_af` strings as on the OM-1 II) | strings |
| subject detection | native (above) | strings, weight hashes |
| USB webcam (UVC) | native: UVC VideoControl header descriptor present, as on the OM-1 II and OM-5 II (absent on the OM-1) | descriptor bytes |
| focus stacking with any lens | same lens check as the OM-1 II | byte pattern + disassembly |
| new against the OM-1 II | strings for a picture-mode dial (`PIC_MODE_DIAL`, Color / Monochrome Creator 2 sets), a CP (computational photography) control with Live ND, Live GND, focus stacking, HDR, multiple exposure and High Res states (`STS_CHG_INFO_CP_*`), movie "My Sets" 1-5, an action dial, BLE accessory pairing (also on the OM-5 II), a frame-rate boost (also on the OM-5 II) | strings only |

*OM-3 feature code and how each was checked.[^fw6]*

The porting outlook follows from these tables.[^inf2]

- **OM-3 to the OM-1 and OM-1 II.** This is the closest of any pair. The chip, engine jobs, cores, ARM and weights are the
  same. What is new is mostly tied to the OM-3's own dials and buttons.
- **OM-3 to the OM-5 family or the E-M5 III.** This is like the OM-1 II.
    - Its image-engine jobs use the TruePic X format and can't run on TruePic IX.
    - Subject detection needs CPU3 and the DML block.
    - The memory map is 2 GB class.
    - Only MN103 control logic is a donor. The OM-3 and OM-1 II are equal donors for Live GND logic, since the code is
      the same.
- **E-M5 III work to the OM-3.** The any-lens focus stack finding applies the same way (desk check, not tried).
  Live ND, Live GND, HHHR, Starry Sky AF and the webcam are already native.

## Whole-image swaps

The OM-5 is close enough that people ask whether its whole firmware image would do on an E-M5 III. The differences are
these.[^fw7]

- Every header carries a different model id. The E-M5 III card updater checks it and rejects an OM-5 file before
  writing anything. Run natively in om-emu, it returned result `0x3202` with 0 flash writes.[^emu1] See
  [Recovery](../firmware/recovery.md).
- Block 3, the IS sub-CPU program, is different. Its command ids are shifted against the E-M5 III's (see
  [stabiliser](../hardware/stabiliser.md)).
- The OM-5 carries USB-PD code for hardware the E-M5 III lacks.
- The SD-pin GPIO setup is different.
- There are 5 factory calibration entries the E-M5 III never got. The other 172 of 173 are at the same offsets and
  sizes.
- The settings store is different.

Each difference can be handled piece by piece, which is what porting does.[^inf4] A whole-image flash risks a brick with
no known recovery outside block0.[^inf4]

There is one more reason.[^inf5] The card updater lives in block0. So a camera running the OM-5 block0 would run the
OM-5's updater, which looks for `E144????BIN` and the OM-5 model. The stock E-M5 III file would most likely be refused,
leaving no card route back.

The OM-5 is E-M5 III-class hardware running the E-M1 III software branch.[^fw7] Its port is micro-USB.[^cam1] Its
power-delivery code is inherited from the E-M1 III, and the OM-5 II adds the USB-C hardware.[^fix1] The firmware shows no
difference in the display controller, sensor, Wi-Fi/BT module or ARM device tree. Buttons, dials, panels and battery
were not checked.[^fw7]

## Address reference

Block0 bases, by body.

| body | address |
|---|---|
| E-M5 III, OM-5, OM-5 II, E-M1 III, OM-1, OM-1 II, OM-3, PEN-F, E-M5 II | block0 base `0x60021020` |
| E-M5 (Mark I) | block0 base `0x7e421020` |
| E-M5 (Mark I) | main program `0x902c0000`, a 64 KB MN103 block of type `0x107` at `0x40060000` |

*Block0 base addresses by body.[^fw1]*

| item | body | address |
|---|---|---|
| loader access-monitor register | all scanned bodies | `0x99700040` |
| image-engine window | E-M5 III, E-M5 II, E-M5 (Mark I) | `0x9d000000` |
| image-engine job-address register | E-M5 III, E-M5 II | `0x9d200010` |
| any-lens focus stack branch | OM-5 1.2 | `0x606d63fb` |
| | OM-5 II 1.1 | `0x606d5524` |
| | E-M1 III 1.6 | `0x606983f9` |
| | OM-1 1.9 | `0x608e3899` |
| | OM-1 II 1.3 | `0x608fd3f2` |
| Live ND level builder | OM-3 1.1 | `0x6031a800` |
| Live ND light-table frame cap | OM-3 1.1 | `0x608a8a4a` |
| Live GND engine area | OM-1 II 1.3 | `0x60890000`-`0x608a0000` (OM-3 at `+0x6d8f`) |
| Live GND parameter maths | OM-3 1.1 | `0x608a03f1`-`0x608a0979` |
| buffer-pool end constant | OM-1 II, OM-3 | `0xff124000` |

*Registers, branches and constants named on this page.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware.
[^fw2]: Read in the firmware, 2026-11-20. A string and constant scan of each body's block0.
[^fw3]: Read in the firmware, 2026-11-20. A static check only: no camera, no builds, no emulator runs.
[^fw4]: Read in the firmware, 2026-11-21. A static reading only: no camera, no builds, no emulator.
[^fw5]: The absence is read in the firmware. The verdict is inferred, 2026-11-21.
[^fw6]: Read in the firmware, 2026-11-24. A static reading only: no camera, no builds, no emulator runs.
[^fw7]: Read in the firmware. The outcome of a whole-image flash is inferred.
[^cam1]: Checked on the camera, 2026-11-23.
[^cam2]: Seen on our E-M5 III.
[^emu1]: Run natively in om-emu.
[^inf1]: Inferred, 2026-11-20.
[^inf2]: Inferred from the tables above.
[^inf3]: Inferred, 2026-11-21.
[^inf4]: Inferred.
[^inf5]: Inferred, 2026-11-22.
[^inf6]: Inferred from the shared constant, 2026-11-24.
[^pol1]: Project policy.
[^fix1]: Corrected on 2026-11-23. The older reading is in [History](#history).

## History

- 2026-11-23: the OM-5 was first described as E-M5 III-class hardware plus USB-C and power delivery. Its port is
  micro-USB. The power-delivery code is inherited from the E-M1 III, and the OM-5 II adds the USB-C hardware.

