# Recovery from bootloops and bad flashes

Flashing your own firmware always carries the risk of a camera that won't start. This page sets out what the camera
checks at power-on, what a firmware update actually writes and in what order, which kinds of failure you can recover
from with just an SD card, and the step-by-step recovery procedure. It ends with the checks every one of our builds
passes before it goes near a camera.

The short version:

- The card updater checks the whole file before it writes anything, so a corrupt or wrong-model file is harmless.
- The updater lives inside the main program, so the camera has to boot most of the way to run it. A patch that crashes
  every normal boot early enough can leave you without a card-based rescue.
- So: keep everything we add switched off during boot, and keep a card with the stock firmware handy.

Two terms used below: the **watchdog** is a timer that resets the camera if the software stops "kicking" it, and a
**bootloop** is a camera that crashes, resets and crashes again on every start.

Tags: **[code]** read in the firmware, **[camera]** seen on a real E-M5 III, **[inferred]** not traced or tested.
Research 2026-11-07 (read-only; nothing flashed).
.
Related: [Boot and section loading](boot-and-sections.md), [Memory map](../hardware/memory-map.md).

## What checks what at power-on
- A loader we can't see (flash 0x40000000-0x40060000 or mask ROM) starts block0 at flash 0x40780020 = VMA 0x60021020.
  Whether it checks block0 is unknown. [inferred] 2026-11-07
- **Block0 never checks itself:** the boot stub and the section loader (0x60045e2e) copy without any checksum or
  signature; a read error is only logged. Section 7's constructors (table 0x611d4364) run right after it loads. [code] 2026-11-07
- Every boot also reads blocks 1, 2 and 4: sub_60166a64 (res.c, on the USRSTART_LOAD path) reads OSD 0x42160000,
  RESCOM 0x43f60000, PIC 0x47180000 and data 0x47a80000. [code] 2026-11-07
- **Watchdog is in the sub-CPU:** sub_600226e1(n) writes n to 0x98e0008c bits 0-5 + command 0x20041001. Boot sets 10
  at 0x60045200; task PER_WDT (id 25, 0x600741c0) kicks via 0x4700101b every 3 s. [code] 2026-11-07
- **Deliberate reboot = watchdog 1 + spin:** "COMMON Reboot" 0x6005849f, NMI handlers → 0x60069f5a (registers saved
  at 0x629be000, "NMI_INT Hassei!"), flash write guard 0x600c4680. So any fault resets in ~1 s, and a fault on every
  boot is a bootloop. A task-level hang does not reset (PER_WDT keeps kicking): one Live ND test build needed a battery pull. [code]+[camera]

## Flash map and what an update writes
- 128 MB flash at 0x40000000 (alias 0x80000000). Normal-operation writes are allowed only to the data windows
  0x40060000-0x40780000, 0x41f60000-0x42160000, 0x47a80000-0x48000000; anything else trips the guard
  (sub_600c463a: watchdog 0x81 + spin = reset). Block0 0x40780000-0x41f60000, OSD 0x42160000, RESCOM 0x43f60000,
  PIC 0x47180000-0x47a80000; boot area 0x40000000-0x40060000 is written only by update kind BOOT (0x10). [code] 2026-11-07
- Our .BIN files (USR, OSD, RESCOM, LUKE, PIC) never touch the boot area or the settings/adjustment data. [code]
- **Write order** (camera's own writer run in om-emu on the stock file): LUKE (to the IS sub-CPU) → PIC → RESCOM →
  OSD → **USR (block0) last**. Each flash component: erase the whole range, program, read back (0x60022353,
  0x600c4922). No rollback. [code] 2026-11-07

## The card updater (hold OK at power-on, `DCOLYMP/e1379999.bin`)
- Same design and task ids as the E-P7: FIRMUP_CLI id 88 entry 0x60c3a1b3, FIRMUP_SRV id 18 entry 0x60c3a638,
  FIRMUP_LED id 118. SRV is started only in USRSTART5 (0x6019de8a), after all 10 sections are ready; CLI has no
  static start, most likely the camera-app manager's MISC/FIRMUP sub-app. [code]/[inferred] 2026-11-07
- **Validator sub_60c3aa36(buf, size, mode, out) checks every component before writing anything:** model 0x1370,
  type 'E', header = trailer, word checksum over the descrambled payload; version not checked. Ran it natively in
  om-emu: stock and a Live ND test build pass; a flipped byte gives 0x3211, OM-5 model 0x3202, truncation 0x3202, all with
  **0 flash writes**. [code] 2026-11-07
- Lamp (FIRMUP_LED 0x601fca3a): solid while working (255), slow blink = success (250), **fast blink = failure** (100);
  then it waits for power off. [code]; solid/blink seen [camera]
- **The updater lives in block0 and needs almost the whole boot:** boot stub, loader, all sections, USRSTART2-5,
  file system task, resource reads. USB (OM Workspace) and Wi-Fi updates need even more (USB stack, GUI, ARM), so
  they are not independent rescue paths. [code]/[inferred] 2026-11-07

## Which failures are recoverable
| failure | recovery |
|---|---|
| Bad file (corrupt, wrong body, truncated) | rejected before writing, fast blink, camera unchanged [code] |
| Crash only when armed or on a feature path | power off (battery pull if hung), boot, reflash [camera] |
| Crash on every normal boot in a shooting/live-view/lens/USB hook | OK + power with the stock file; the update boot should not start the shooting app [inferred] |
| Intermittent boot failure (section-load race) | retry power-on with OK held; it gets through sometimes [camera]+[inferred] |
| Crash in the boot chain (USRSTART, loader, section 7 constructors, file system, resource reads) | card/USB unreachable; service or flash programmer only [inferred] |
| Power cut while the update writes USR (block0, last) | block0 half-erased: brick [code]+[inferred]; during the earlier blocks, block0 is intact but boot reads those blocks, so it may still fail [inferred] |
| Bad persistent state (settings value, trigger file on card) | survives a reflash; remove card files, reset settings from the menu [inferred] |

## Recovery procedure
1. Keep a spare card with only `DCOLYMP/e1379999.bin` = stock `OLY_E_137_1700_0000_0000.BIN` (no other E137 files).
2. Camera hung: battery out, wait 10 s, back in.
3. Remove anything that wakes a feature at boot: our request files (LND*.ARM etc.), USB/HDMI cables; lens off.
4. Normal power-on. If it boots: flash stock (or the last good build) the usual way.
5. If it loops or dies at power-on: spare card in, **hold OK while switching on**, keep holding until the lamp is solid.
   Several tries if the failure was intermittent. Solid → slow blink = done, switch off. Fast blink = file rejected,
   nothing written.
6. Never open the battery door while the lamp is solid; start every flash with a full battery.
7. If no lamp at all with OK held: the update boot can't run; stop and write down what happened (needs service or a
   flash programmer; open question).

## Pre-flash check suite (every build, 2026-11-07)
Every build we make goes through a pre-flash check script before it is handed over:
`preflash.py STOCK.BIN BUILD.BIN OUTDIR [--manifest M.json]`. It runs all the
checks below in ~90 s and writes REPORT.md; **a build is handed over for flashing only with a PASS (warnings listed) report in its
zip**. [code]

What it checks:

- **F1-F4:** the container and checksums, that the components match stock, and the camera's own validator run in
  om-emu.
- **B1-B3:** the boot stub, section table and section ends, and the functions on the recovery path and the idle boot.
- **S1-S2:** that new bytes sit inside loaded sections, and no early-section hook jumps into a later section without a
  ready-bit test.
- **R1:** that each feature stays in its own region.
- **A1-A2:** native evidence for every absolute address, and plain MN10300 instructions only.
- **E1-E2:** om-emu boot plus a 13-step script behaving as stock, and which changed bytes ran with nothing armed.

Calibration: stock PASS, a current HHHR test build PASS with warnings, **the build with the boot-race bug FAIL on its 0x601fce30 hook (the real dead-at-power-on bug)**,
and the corrupt/overlap/unloaded test files FAIL. Its limits: it can't see bugs that only happen when armed, the real
boot chain, indirect calls, or blocks 1-4 beyond a diff.

## Safety rules for our builds (proposed 2026-11-07)
1. **Pre-flight with the camera's own validator** (preflash F3): `fupcheck.mjs EMU FILE 2` in om-emu must return 0x0 with exactly
   USR, OSD, RESCOM, LUKE, PIC. Never ship a BOOT or extra component. [code]
2. **Recovery-path diff** (preflash B2/B3): `recovery_reach.py checkbin recovery-path-functions.csv,idle-executed-functions.csv STOCK BUILD`.
   Every hit must be camera-proven (today: section-end constants 0x60045dee/0x60045e16, focus-stack 0x6065e5ec) or
   explained in the PROCEDURE. The static list (2,579 functions) is a lower bound: it misses indirect calls (the boot-race build's
   0x601fce30 is not in it). [code]
3. Nothing of ours acts during boot: guard boot-reached hooks and keep them no-ops until the shooting app is up, so
   the update boot runs stock code. [inferred]
4. Arm state only in RAM (resets come up disarmed); read request files only on an armed user action, never at boot.
5. Safe-mode key (hold a key at power-on → all hooks stay off) and, later, a boot counter in sub-CPU backup words.
   Both need research (key reader address, free backup words). [inferred]
6. A hang→reboot watchdog only while armed, never at boot (it would turn a boot hang into a bootloop).

## Open
- Pre-block0 loader: does it check block0 or offer a rescue (USB/serial/test pads)? Service reflash method?
- What exactly starts FIRMUP_CLI, and does the OK-held boot skip the shooting app? A zero-write dry run on the camera
  (stock file with its last byte flipped, OK held → fast blink, nothing written) would confirm the trigger and the lamp.
