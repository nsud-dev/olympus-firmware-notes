# Recovery: technical notes

> **Technical notes.** This page is the dense reference. For a readable introduction, start with [Recovery](recovery.md).

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
- **Watchdog is in the ~~sub-CPU~~ always-on power block** (2026-11-23: no separate processor, see [power block](../hardware/power-block-technical.md); kick = key 0x19191012 to 0x98e00090): sub_600226e1(n) writes n to 0x98e0008c bits 0-5 + command 0x20041001. Boot sets 10
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
- **It does not check nested sub-block checksums** [emu] 2026-11-21: a block 2 sub-block with a wrong checksum and the
  outer block's checksum fixed passes with 0x0 in modes 2, 1 and 0 (only "... Gets" per component). So nothing before
  flashing catches that; preflash's `subblock-sum` self-test case can't show F3 failing. A flipped byte (outer checksum
  wrong) still gives 0x3211.
- Lamp (FIRMUP_LED 0x601fca3a): solid while working (255), slow blink = success (250), **fast blink = failure** (100);
  then it waits for power off. [code]; solid/blink seen [camera]
- **The updater lives in block0 and needs almost the whole boot:** boot stub, loader, all sections, USRSTART2-5,
  file system task, resource reads. USB (OM Workspace) and Wi-Fi updates need even more (USB stack, GUI, ARM), so
  they are not independent rescue paths. [code]/[inferred] 2026-11-07

- **Other bodies** (string search 2026-11-19, OM-5 and E-M1 III on the expanded images): every body we hold has
  FIRMUP_CLI, FIRMUP_SRV and `DCOLYMP`, and a card file pattern with its own model number: E-M5 III `E137????BIN`,
  E-M1 III `E139????BIN`, OM-5 `E144????BIN`, OM-1 `E143????BIN`, PEN-F `E122????BIN` (OM-5 II: not found in the
  unexpanded image). The NMI message "NMI_INT Hassei" is in all six; "COMMON Reboot" in all but the PEN-F. [code]

## The boot-area loader (read from a flash backup, 2026-11-23)

Read from an FDMP backup of one E-M5 III (all 16 files matched their logged sums). The area 0x40000000-0x40060000 holds
two programs, both linked at VMA 0x60020000 (flash offset + 0x20000000). [code]

- **Stage 1** (flash 0x40000000-0x4000ffff) runs at power-on. At 0x60022378 it sets up clocks and then decides
  [code]:
  1. It writes 0x100 to pad register 0x9b8001f0 and reads 0x9b8001ec bit 4 (0x60022468). If the bit is 1, it boots
     normally.
  2. Else it reads and clears bit 9 of the always-on word 0x98e00000 (0x60021f6f). If that bit was 1, it boots normally.
     ~~The main program sets that bit at start-up~~ Corrected 2026-11-23: the main program sets that bit in its power-off path sub_6005f203 when property 0xA011 equals 9 (0x6005f2f5 -> 0x6006423a, plain store, same code in OM-5 and OM-5 II 1.1). 0xA011 is the u8 at +6 of the "small" store (layout 10, same packing in all three bodies; E-M5 III setting id 3016). Writers in E-M5 III: 0x612a822b, 0x603ee8f3, 0x60442c8d. Stage 1 clears the bit only on an OK-held start, so a program that keeps 0xA011 = 9 makes every hold-OK start skip the updater (suspected for one of our test images, 2026-11-23). Way out to test: OK-held start, battery pull while running, then OK-held start with the card. [code]+[inferred]
  3. Otherwise it copies flash 0x40010000-0x4005ffff to RAM 0x60030000 and runs stage 2.
  - Normal boot copies the first 60 KB of block0 (flash 0x40780000) to 0x60021000 and enters it (0x60022730). Stage 1
    does no checksum of block0. [code]
- **Stage 2** (flash 0x40010000-0x4005ffff, 320 KB) is a small OS of its own (task table 0x6006b234) with an NAND
  driver, an SD card stack and **its own card updater**: `DCOLYMP`, `E137????BIN` and `G137????BIN`, every component type
  (USR, OSD, PIC, RESCOM, LUKE, BOOT and more), descramble, checksum, write, compare, then "UPDATE SUCCESS" or "UPDATE
  FAIL" on the debug serial port and a lamp mode. Updater task 0x6004d1ce (task 5). It does not need block0. [code]
- So the camera has a card rescue below the main program. It runs when pad 0x9b8001ec (pin entry 2 of the block0 pin
  table 0x60026280, interrupt 0x32, gio id 194) reads low at power-on. **Which control or test point drives that pad is
  not known yet.** It could be the OK key (the "hold OK" update) or a factory pad. [inferred]
  **Answered 2026-11-23: pad 2 is the OK key** [camera]. A read-only pin watch on
  an E-M5 III logged pad 2 low exactly twice, during the two 3-second OK holds of an OK-only run, and at no other
  time. So "hold OK at power-on" runs the boot-area stage 2 updater, not block0's FIRMUP. A card update therefore works
  even if block0 can't start, as long as the boot area is intact and bit 9 of 0x98e00000 is clear.
- **Stage-2 exits (2026-11-23) [code].** The firmup task 0x6004d1ce boots block0 without writing through 0x60065614. That routine prints "UPDATE OPERATION WAS NOT PERFORMED" to the UART, then copies 0x40780000+0xf000 to 0xa0021000. Callers: unmount error 0x6004d20e, mount error 0x6004d234, a file-search error other than not-found 0x6004d2d0, a load error 0x6004d323, and no file found for any of the 11 types 0x6004d392. The "File Init" check 0x6004d3fe and the "SCPU Init" check 0x6004e73d always pass. The always-on cause decode at 0x6004f6fe reads +0x48 and +0x00 bit 1 and stores the code at 0xa25d3d8e. No reader of that code was found, and the backup words +0x08..+0x3c only have a setter (0x6004faea). So a silent skip after stage 2 starts means a card or file problem, not a cause check.
- Stage 1 touches only byte 0x8ff00160 of the core-shared block. Neither the E-M5 III nor the OM-5 main program
  addresses that byte directly. [code]

## Which failures are recoverable
| failure | recovery |
|---|---|
| Bad file (corrupt, wrong body, truncated) | rejected before writing, fast blink, camera unchanged [code] |
| Crash only when armed or on a feature path | power off (battery pull if hung), boot, reflash [camera] |
| Crash on every normal boot in a shooting/live-view/lens/USB hook | OK + power with the stock file. ~~the update boot should not start the shooting app [inferred]~~ Corrected 2026-11-23: the OK-held update is run by the camera app's MISC/FIRMUP sub-state and FIRMUP_SRV starts in the last user-start stage, so it needs nearly the whole boot, including the stage 2-4 tasks. It helps only for faults that happen after start-up (e.g. in a hook armed later) [code]+[inferred] (OM-5 `startFirmupSubAppStateMisc` 0x60fa1b90 used at 0x60d31e38). Superseded later on 2026-11-23 for the OK-held start: that one is run by the boot-area loader's own updater, which needs no block0 (see the boot-area loader section) [code]+[camera] |
| Intermittent boot failure (section-load race) | retry power-on with OK held; it gets through sometimes [camera]+[inferred] |
| Crash in the boot chain (USRSTART, loader, section 7 constructors, file system, resource reads) | ~~card/USB unreachable; service or flash programmer only [inferred]~~ 2026-11-23: hold OK at power-on with the stock file on the card. OK is read by the boot-area loader, whose own updater needs no block0 [code]+[camera] |
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
- **R1:** that each feature stays in its own region.
- **A1-A2:** native evidence for every absolute address, and plain MN10300 instructions only.
- **E1-E2:** om-emu boot plus a 13-step script behaving as stock, and which changed bytes ran with nothing armed.

- **N1 (2026-11-21):** negative control: the manifest's feature probes must match the build and not the previous
  build (`--prev`).
- **W1 (2026-11-21, on with `--emu`):** om-emu write watch over free space (regions.csv, census.csv) and the
  build's new bytes; canary stores in idle-boot code are its positive control (280 canary writes seen in the self-test) [emu].
- **F5 (2026-11-21):** nested sub-block checksums. The camera's own validator (F3) only checks the outer
  USR/OSD/RESCOM/LUKE/PIC blocks: it returns 0x0 on a file whose nested sub-block checksum is wrong [emu]
  (the validator in om-emu, modes 2/1/0), so F5 checks them statically.

**Self-test (2026-11-21, om10mi-mods method):** `selftest.py` builds deliberately broken images (bad checksum, section
overlap, boot-stub byte, unloaded hook, section-1→4 and section-2→7 boot races, dangling address, AM33 instruction,
misaligned store, foreign region, text past a section end, recovery-path byte, replaced body, probe that matches the
previous build, nested sub-block checksum) and runs a real build that boot-looped on the camera: each must FAIL its named check, stock
must not. All static cases as required [code]; om-emu cases (E1 hang, E2 unarmed stub, W1 writes to free RAM, F3
flipped byte = 0x3211 checksum_error) as required [emu] (2026-11-21); every check except the WARN-only F4/B3 has now been shown failing, and stock passes with W1 on
.

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
5. Safe-mode key (hold a key at power-on → all hooks stay off) and, later, a boot counter in sub-CPU backup words. Camera-proven pattern on the OM-5 II (OMKit, 2026-11-21 read): the loader asks the key-state routine whether OK is held and skips all added code [camera] theirs; E-M5 III key-state routine not looked up. details
   Both need research (key reader address, free backup words). [inferred]
6. A hang→reboot watchdog only while armed, never at boot (it would turn a boot hang into a bootloop).

## Open
- Crash record (idea from caduceus-ep7, 2026-11-18): hook the NMI path right after its 1 s watchdog set, copy fault
  frames, task id, sections loaded and the capture ring into RAM that boot does not clear, write it to the card on the
  next half-press. Would show the PC of resets that happen before the Wi-Fi shell is up (Live ND power-on reset).
  Unproven anywhere: does DRAM survive the watchdog reset? [inferred] 2026-11-18 snapshots in two Live ND test runs of the exception save area 0x629be000 were inconclusive (area all FF after power-off + boot; the reset itself not captured) [camera]. details
- ~~Pre-block0 loader: does it check block0 or offer a rescue (USB/serial/test pads)?~~ Answered 2026-11-23 (section
  "The boot-area loader"): it has its own card updater, gated by pad 0x9b8001ec. Open: what drives that pad.
  2026-11-23: block0 sets up the debug UART 0x98700000 first and never polls it at boot, so any serial rescue would have
  to be in the loader or the SoC boot ROM. Board pads unknown. [code]+[inferred] (os-and-framework "Debug serial port")
- What exactly starts FIRMUP_CLI, and does the OK-held boot skip the shooting app? A zero-write dry run on the camera
  (stock file with its last byte flipped, OK held → fast blink, nothing written) would confirm the trigger and the lamp.
