# Gotchas and dead ends: technical notes

> **Technical notes.** This page is the dense reference. For a readable introduction, start with [Gotchas and dead ends](gotchas.md).

This page collects the mistakes that cost us a camera flash, a battery pull or a day of work, so nobody repeats them.
Read it before designing a build, and add to it whenever something goes wrong or a belief turns out to be false.

It has three parts: things that hung or reset the camera (with the cause and the rule we follow now), beliefs we held
and later corrected, and dead ends not worth retrying.

## Things that hung, reset or bricked-for-a-while the camera

Each row: what the camera did, why, and the rule we follow since.

| what happened | cause | rule now | when |
|---|---|---|---|
| MENU reset the camera anywhere, with or without a card (first mod loader versions; om-emu tests passed) | [camera] 2026-11-22: extending the Custom Menu letter-cell picture lists (entry 22 written into the 16 zero bytes after each list, 32 widget template counts 21 -> 22). NMI on CPU0 in the list copy routine 0x60c944b6 (PC 0x60c94831, Wi-Fi shell capture); The same build without those edits works; an earlier cache theory was wrong | don't extend fixed-size picture lists or counts the firmware sized itself; a new menu letter uses the stand-in glyph; for a crash, capture the NMI dump over the Wi-Fi shell (`nc ... \| tee`) before bisecting. Source repo:private notes | 2026-11-22 |
| Reset on press across 4 flashes | pool table typo 0x60539158 vs real 0x6053e158, copied into sims too | every address through `check_addrs.py`; sims don't use note values | 2026-10-29 |
| 32 MB written outside a frame slot | main pool is two blocks (ids 9-20 at 0xc4000000); we computed a linear stride | ask the pool (vtable of the actual object) | 2026-10-30 |
| Reboot when CPU read the 0xc4000000 block | that block isn't CPU-readable the way we read it | CPU samples only below 0xc0000000 | 2026-10-30 |
| Camera hung until battery pull | DSP bridge refused a record (capacity) and the worker parked | read bridge checks for every record change | 2026-10-29 |
| Reboot ~2 s after press | "row done" notify for frames we didn't develop | release + refill rows per frame without notify | 2026-10-30 |
| Freeze on antishock single | antishock while a log dump pending; root cause unknown | no antishock while a log is pending | 2026-10-30 |
| Boot loop while LNDM1.ARM on card | trigger fired at startup, then crashed | consume the request file before risky work | 2026-10-24 |
| Reset after allocation | flash-copy dest outside 0xa0000000-0xbfffffff | range-check program destinations | 2026-10-24 |
| Intermittent dead-at-power-on / LV-then-reset loops | hooks jumping into background-loaded sections before they were ready | boot guards on every out-of-section hook | found 2026-11-04 |
| Live Time shut camera off when armed | hooks active in B mode | arm only in S/M, exclude B | 2026-11-04 |
| Camera restart entering a patched screen (lesson learned from a PEN-F HSL patch in fishcu/oly_fw_analysis) | u32 struct at a 2-byte boundary; MN103 traps misaligned word/halfword access, GNU/GDB-based simulators (including our eqsim) don't [inferred] | align data passed to stock code (u32 fields 4 B, strings 2 B); don't trust the sim for alignment | 2026-11-11 |
| Early card logs all 0 bytes | first log written from an uncached buffer, then long filenames (fw paths are 8.3 only), then the logger called 0x606320f2 (fread) instead of fwrite 0x60631fe8 | 8.3 names, heap buffer, fwrite 0x60631fe8 [camera] | 2026-10-24 |
| Pro Capture H reset the camera | the same pool-table typo in drive_stub (Pro Cap H works once fixed) | as above [camera] | 2026-10-29 |
| Jump-to-self at a hook entry | an inline comment on an `nj` line left a jump unresolved; `link` silently ignored a SYM_DIFF reloc | builds assert every nc/nj resolved and only PCREL relocs [code] | 2026-10-29/30 |
| Corrupted locals after a call | a call writes its return address at (0,sp) | save locals from (4,sp) [code] | 2026-10-31 |
| Request file opened on every shutter press | hook did fopen before checking settings | check settings first / once-per-boot latch; watch shutter delay [camera] | 2026-10-26 |
| E-M1 III-based stage 3D blob unusable | porter bug: 42 trampolines (0xd0 B) overlaid the rodata base, so 181 rodata/RAM refs were 0xd0 low; E-M5 iseq task never dispatches ND event bits 0x10-0x80; a failed finish never called done (sequencer hang) | 3D/3U were flag-off regression builds only; reviewed engine8 fixed the shift [code] | 2026-10-21 |
| Webcam test 2 broke on replug / errors | DEPEVT status check treated LST/IOC as errors (byte 0x613bb640 `and 15`→`1`); reset/disconnect skipped EndTransfer unlike stock 0x60c348fb | fixed in 2b/2c [camera] | 2026-10-20 |
| Webcam 2d pacing jitter | 34000 µs gate equal to the 34 ms timer period, so frames get skipped | gate below the period [code] | 2026-10-20 |
| An om-emu pass looked like a shooting-path test | om-emu stands in for the shooting state machine (0x602b...), burst, DSP, block2, ARM, CPU1-3, boot from reset: hooks there are never reached (Live ND sites, HHHR 0x602a13b4) | an om-emu pass covers only boot/UI/menus/settings; check coverage (WATCH_PCS) to see if a hook ran [code] private notes | 2026-11-05 |
| om-emu run crashes during open_session write no result file | a bisect reading a fixed result path then sees the last pass (stale) | delete the result JSON before each run (fixed in our bisect3+.py) [code] private notes | 2026-11-05 |
- 2026-11-12: console peeks: keep CPU peek ranges below 0xc0000000. One of our peek builds allowed up to 0xdeffffff, which includes ARM Linux RAM 0xc0000000-0xc2aa0000 and the 0xc4000000 block whose CPU reads rebooted the camera. Its scripts only read pool 0x0700 at 0xaa91d340, so no harm so far; don't type other addresses there. [code]+[camera]
- Buffer pools share memory by mode: the unused tail of a pool slot is not free RAM. Pool 0x0700 (live-view raw) overlaps pools 0x0800, 0x1400, 0x0900, 0x4c00, 0x4e00; write only into buffers taken from a pool. [code] 2026-11-12

- Keep patch state out of the loaded program image (other bodies, 2026-11-18): an E-P7 build that stored a byte into section-3 code RAM through the cached alias restarted on first use; an OM-5 II build with state in sections 2 and 6 froze, reset, then looped at every start. Both fixed by moving state to heap. Stock firmware makes no such stores. Prefer heap or a fixed RAM block outside the sections; at least never store before the section is ready. [camera] (caduceus-ep7 `docs/SD_V2_CRASH.md`, caduceus-om5 `research/OM5II-IMAGE-STORE-FAULT-2026-11-11.md`)
- Don't run the settings-store `size` shell sub-command (handler near 0x6005b81a, prints "b/c/m %08d/%08d"): it measures each store by running the default rebuilder on the live image (0x6005ca77 -> 0x6005c805 into 0x623d1000), so the user settings become defaults and the next power-off saves that. [code] 2026-11-18
- GUI picture widgets (class 0x8003) take at most 8 picture states: the widget caches one picture pointer per state at object +172 for 8 states (0x60cc9888), so state 8+ reads a wild pointer and resets the camera. om-emu reads zero there and hides it. 2026-11-20 side-bar editor test (+2 on a 12-state digit widget) [code]+[camera]
- Unloaded gaps between sections hold leftover RAM on the camera, not the file's 0xFF; emulators that map the whole file hide this (camera-stuff `research/NOTES.md` GX1/GX2 probe, 2026-11-07). [camera]

- Writing firmware code in RAM through the cached address resets the camera (memory protection); OMKit installs its hooks through the uncached alias, byte by byte, first byte last, each inside one 16-byte line (OM-5 II, 2026-11-21 read). [camera] (OMKit `docs/architecture.md` §6)
- **Section end flush against another CPU's buffer = one reset at every power-on** (every Live ND test build until 2026-11-22; gone once the section end went back to stock): section-10 end raised to 0x61483000 = first byte of the CPU 1/2 code buffer 0xa1483000. Rule: keep at least a cache line (better 4 KB; 12 KB is camera-proven) between any section end or our region and memory other CPUs use. [camera] (features/live-nd.md)

## Wrong beliefs we corrected

Things we thought were true, and what turned out to be the case.

- 2026-11-23: **The stabiliser program (LUKE) must be disassembled as plain `mn10300`, not `am33-2`.** Its maths
  extension ops (`udf`) share encodings with AM33 instructions, so `-m am33-2` shows `fadd`, `mcst48` and similar
  instructions it never uses. The same pass showed that LUKE has no handler for the target-position drive (`bc` id 11),
  which earlier notes listed as a route to star tracking. [code]

- 2026-11-15: **The OM-5 does not switch to a "Live ND buffer layout" at run time.** Its preview ring pools are built
  at every boot like all pools and are simply used only while the preview runs. The pool-map "flag 0x100" is the lock-tag
  word at pool +16, not a layout flag. Adding pools the OM-5 way would put new code in boot-time static init, which we
  can't recover from the card if it goes wrong; make pools lazily at preview start instead. [code]
- 2026-11-05: **0x600232c5 is not a general malloc**: it is a fixed-class physical-pool allocator (classes ≤128, ≤2,048, ≤16,384 B). Larger requests print `scheap_phyalloc: Size Over` and return 0. Our first console build asked for 18,576 B and would have exited at once. Native tee-open 0x6010189a takes 16,384 B from it and writes through the result without a null check. [code]
- 2026-11-05: the "~5 MB zero run 0x61483b31-0x61858fe0, likely zero-init data, not free" note was wrong: in the decoded block0 the area after section 10 (0x61478000) is 0xFF padding the loader never copies, and RAM 0x61485000-0x61a00000 has no code refs. Also, the debug console isn't only reachable from the UART: its line executors can be called from our code. [code]
- 2026-11-05: OM-5 II GUI strings and MODE_* keys list features the body does not offer (Human/Birds/Dogs & Cats subjects, ND32/64/128, Live GND imaging); they are shared OM-series UI text. Likewise the MDET_DL subject-detect code in E-M1 III/OM-5/OM-5 II is dead code: only E-M1X and OM-1 family ship it. Confirm a feature with reachable code or an om-emu menu run before calling it a donor. [code]
- 2026-11-05: HHHR handoff said the ARM reference frame maps request +4 and that every pool keeps its bitmap at +64; really frame 0 maps +0 (the Y image) and 40 base-class pools keep it at +4. Caught by another tool's build. [code]
| belief | truth |
|---|---|
| Hidden USB Mode value 1 = tether | HID PC-remote (PID 0x132) |
| camecon re-enable gives a webcam | no handler, no live-view ops; webcam must be ported |
| HHHR / Live ND / Star AF are menu-hidden like focus stacking | compiled out; ports needed (though Live ND plumbing is present but off) |
| E-M5 III is TruePic IX | TruePic VIII (but not distinguishable as silicon from firmware) |
| E-M1 III → E-M5 III match ≈ 50% | 81-83% once LZ4 sections are expanded |
| E-M1 III is the donor | OM-5 1.2 (memory map fits 1 GB) since 2026-10-22 |
| The OM-5 lengthens frames by capping fps (E10c-e) | OM-5 sends kind 0x400 + fps 0 from DigitalNd; photo = ≤16 frames at set Tv |
| 0x606320f2 is fwrite | it's fread; fwrite is 0x60631fe8 |
| iseq name table is {name,id} | {u32 id, char *name} |
| Prop 36537 is the hidden Live ND switch | develop/gradation setting; don't use |
| Card update runs from an independent loader | the SD updater is in block0 (FIRMUP_CLI) |
| OM-5 II does ND64/128 | strings only; engine ND2-ND16 (2026-11-18: caduceus-om5 reports ND32/64 working after extending the step selector; merge count unverified; caduceus-om5 `firmware/om5ii/nd64.py`) |
| One test photo showed a merge | motion blur; retracted |
| Bundled binutils has `ld` | as/objdump/objcopy only |
| 0x6017f475 / 0x6019faf0 are our hooks | stock bytes decoded at the wrong offset |
| Selector 1 / Pop Art needed for allocation | only for the old typed-arena route |
| Allocation refusals were a code bug | selector 2 = HIGH_ISO from auto ISO in a dark room; test at fixed ISO 200 |
| ND32 via longer burst frames (decision 2026-10-31) | OM-5 merges ≤16 frames at the set Tv; ND32 has no donor code and needs our own two-pass design |
| Route source = ctx byte 24949 (prop 38497) | doubtful: 24948/24949 look like bracketing info |
| 0x603fceb1.. switch = readout setup per route | metadata tags (kinds 104/109) and the bracketing map |
| Main-pool address lookup is linear | two-block class: ids 9-20 at 0xc4000000 |
| OB/WB are set at capture prep | filled later, at the metadata step 0x6040c7f5 |
| E-M5 III has no Live ND code at all | the OM-5 plumbing is compiled in, switched off |
| Webcam Photo Booth reopen bug is in the camera | the host never calls startStream on reopen; host side |

## Dead ends (don't redo)

Approaches we tried and dropped, with the reason.

- Forcing debug flags (`fcs seq set2 6`, `mode_digital_nd`) to switch features on: the engines are compiled out.
- Using the ~5 MB zero runs in block0 as free space: likely zero-init data.
- Auto-closure porting of Live ND shooting helpers: pulled in other subsystems; matched by hand instead.
- Webcam live frames while USB-connected: camera leaves shooting mode.
- Full OM-5 / OM-5 II image cross-flash; full OM-5 II UI transplant.
- DL subject detect port (needs OM-1 hardware).
- CPU merge of raw frames: a byte-wise merge took 0.46 s per 128-row band (~14 s per frame); we chose DSP job 11 (2026-10-29). [camera]
- Porting the OM-5 capture command struct: it is 19 words vs native 16 (extra pointer at +28); use native StlUhs instead. [code]
- Frame-rate caps on the AE selector/request: wrong model of the OM-5 (it asks the sensor for longer frames instead). [code]

- 2026-11-05: OM-5 DSP request packets are 8 bytes bigger than E-M5 III's (84 vs 76 B; payload slot +71 vs +63), so donor setters can't go straight into the E-M5 programming tables; use an indirect shadow payload as Live ND job 11 does. [code]
- 2026-11-05: bank 6's last 32 bytes (0x45d5ffe0-0x45d60000) are a trailer, not free flash. [code]
- 2026-11-05: bracket info back end 0x60308658 writes count × 6-byte EV entries with no bound check, and the GUI caller 0x607d289c has 7-entry (42 B) buffers: raising AE BKT above 7 frames without enlarging them corrupts the stack. Same pattern for focus stacking: 9-slot combine/DevRec arrays. [code]
- 2026-11-05: the Live ND DSP bridge (0x607ac076) only admits job 11 with an ND record; other jobs need their own controller, never a bypass. [code]

- 2026-11-05: the native copy helper 0x60022180 always returns 0 (clr d0 at 0x6002234f); check a checksum after any flash->RAM load instead of trusting the return. [code]

- 2026-11-05: ISC calls (dispatcher 0x61206cfe, send 0x61205800) take hardware locks that retry forever (0x61206b95, 0x6120597e); a "timeout" argument doesn't bound them. Check the CA9-started byte 0xa2624f09 (getter 0x60059129) before any ISC call; start the CA9 only via its manager (worker 0x60058e21 is core-1 only). [code]
- 2026-11-05: To power the ARM, post to the CA9 manager queue u16 (0x60041252) with owner Take (request word 1 = on, 0 = off). Never post 0x00010000 (Wi-Fi off): it stops the ARM even when other users need it. Don't call the start/stop workers directly; the start blocks until Linux boots. [code]
- 2026-11-06: Don't start the ARM mid-shot: when a build posted Take on at state 34, the camera reset (cause open). Keep MN 0xc0000000..0xc2aa0000 (ARM Linux RAM, reloaded from flash on every start) free of HHHR buffers. [camera]+[code]
- 2026-11-06: Don't stop the ARM mid-shot either: when a build posted Take off in the silent-single shot hook, the camera reset too. Post Take on/off only at an Idle (0)/Standby (11) state change; the ARM running during body-button shots is fine; a later build confirmed start and stop at Idle are safe. [camera]
- 2026-11-07: **om-emu is not a boot test.** It never runs the boot stub, the section loader or USRSTART2-5 (its lab ends the init task), so a
  build that breaks the start chain or the card updater's start can pass every om-emu script. Use `recovery_reach.py` for boot-path
  changes and `fupcheck.mjs` for the updater. [code]
- 2026-11-07: **a card update writes block0 last** (LUKE, PIC, RESCOM, OSD, then USR), each erased in full first: a power cut in the
  last phase leaves no updater to recover with. Full battery, never interrupt a solid lamp. [code]
- 2026-11-07: run `preflash.py` on every build before it is zipped for flashing; it caught a boot-race hook statically and
  found Live ND guards overlapping HHHR's 0x600d079e. om-emu alone passed a build with a hook into never-loaded
  code (it doesn't run that path). [code]
