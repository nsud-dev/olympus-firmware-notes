# Gotchas: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Gotchas](gotchas.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

This page collects the mistakes that cost us a camera flash, a battery pull or a day of work, so nobody repeats them.
Read it before designing a build, and add to it whenever something goes wrong or a belief turns out to be false.

Each section covers one area. A bullet starts with the rule we follow now, then gives what the camera did and why. Near
the end are the beliefs we held and later corrected, and the dead ends not worth retrying. Addresses are in the
[Address reference](#address-reference).

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware or
our code, grey = inferred, amber = a correction.

## Addresses

- **Every address goes through `check_addrs.py`, and simulators never use values from notes.** A pool table address
  with a one-digit typo reset the camera on the shutter press across 4 flashes. The typo had been copied into the
  simulators too, so they agreed with it.[^cam4]
    - The same typo in `drive_stub` made Pro Capture H reset the camera. Pro Capture H works once it is
      fixed.[^cam4]
- **Check what a function is before calling it.** An early card logger called fread, thinking it was fwrite, so every
  log came out empty. See [Cache and card files](#cache-and-card-files).[^cam2]
- **Serial "channel" numbers are logical.** Callers of the serial driver pass logical channels 1 to 13. A map turns
  them into the 8 ports. The audio page took logical 3 as port 3, but it is port 1. Read the map before naming a
  port.[^fw10]

## Start-up and sections

The main program loads in ten sections. Later sections load in the background, so a hook can reach one before it is
ready.

- **Boot guards on every out-of-section hook.** Hooks that jumped into background-loaded sections before they were
  ready gave intermittent dead-at-power-on and live-view-then-reset loops.[^cam6]
- **Keep at least a cache line between any section end or our region and memory other CPUs use.** Better is 4 KB, and
  12 KB is camera-proven. Every Live ND test build raised the section 10 end to the first byte of the CPU 1/2 code
  buffer, and each gave one reset at every power-on. The reset went away once the section end went back to
  stock.[^cam10]
- **Section 7 is read second but ready late.** Never jump from a boot path in sections 1 to 6 into sections 7 to 10
  without a ready-bit guard. The boot loader's access monitor traps the early access, and one test build boot-looped
  this way. om-emu and our first static check both missed it.[^cam14]
- **Consume a request file before risky work.** A request file left on the card fired its trigger at start-up, then
  crashed, and the camera boot-looped.[^cam2]
- **Check settings before opening a file on the shutter path.** A hook did `fopen` on every shutter press before
  checking settings. Check settings first or use a once-per-boot latch, and watch for shutter delay.[^cam3]
- **Unloaded gaps between sections hold leftover RAM on the camera, not the file's `0xff`.** Emulators that map the
  whole file hide this.[^cam12]

> [!WARNING]
> A card update writes block0 last (LUKE, PIC, RESCOM, OSD, then USR), and erases each in full first. A power cut in
> the last phase leaves no updater to recover with. Use a full battery and never interrupt a solid lamp.[^fw6]

## Memory and buffers

- **Ask the pool for an address.** The main pool is two blocks, with ids 9 to 20 in the second block. We computed a
  linear stride and wrote 32 MB outside a frame slot. Use the vtable of the actual object.[^cam5]
- **CPU samples only below `0xc0000000`.** The second main-pool block isn't CPU-readable the way we read it, and
  reading it rebooted the camera.[^cam5]
- **Keep console peek ranges below `0xc0000000`.** One of our peek builds allowed addresses up to `0xdeffffff`. That
  range includes the ARM Linux RAM and the second main-pool block whose CPU reads rebooted the camera. Its scripts only
  read pool `0x0700`, so there was no harm so far. Don't type other addresses there.[^cam8]
- **The unused tail of a pool slot is not free RAM.** Buffer pools share memory by mode. Pool `0x0700` (live-view raw)
  overlaps pools `0x0800`, `0x1400`, `0x0900`, `0x4c00` and `0x4e00`. Write only into buffers taken from a
  pool.[^fw12]
- **Range-check program destinations.** A flash copy with its destination outside the program range reset the camera
  after allocation.[^cam2]
- **The physical-pool allocator is not a general malloc.** It has fixed classes of at most 128, 2,048 and 16,384 B.
  Larger requests print `scheap_phyalloc: Size Over` and return 0. Our first console build asked for 18,576 B and
  would have exited at once. The native tee-open takes 16,384 B from it and writes through the result without a null
  check.[^fw5]
- **The flash is not memory-mapped.** The flash ranges are names the NAND driver takes, not addresses the CPU can
  read. The access monitor guards that range after start-up, so a direct load resets the camera. Read flash only
  through the native copy helper.[^fw10]
    - The write guard's last window covers the bad-block spare pool and table copies. Never write at or above
      `0x47c00000`.[^fw10]
- **Check a checksum after any flash-to-RAM load.** The native copy helper always returns 0 (`clr d0`), so its return
  value says nothing.[^fw5]
- **Bank 6's last 32 bytes are a trailer, not free flash.**[^fw5]
- **The area after section 10 in the decoded block0 is `0xff` padding the loader never copies.** RAM after the
  section 10 end has no code references.[^fw5]
- **Don't raise AE bracketing above 7 frames without enlarging its buffers.** The bracket info back end writes count ×
  6-byte EV entries with no bound check. Its GUI caller has 7-entry (42 B) buffers, so more frames corrupt the stack.
  Focus stacking has the same pattern in its 9-slot combine and DevRec arrays.[^fw5]
- **Keep patch state out of the loaded program image.** On an E-P7, a build that stored a byte into section 3 code RAM
  through the cached alias restarted on first use. On an OM-5 II, a build with state in sections 2 and 6 froze, reset,
  then looped at every start. Both were fixed by moving state to the heap. Stock firmware makes no such stores. Prefer
  the heap or a fixed RAM block outside the sections, and never store before the section is ready.[^cam11]
- **Align data passed to stock code.** A u32 field needs 4 bytes and a string 2 bytes. The MN103 traps misaligned word
  and halfword access, but GNU/GDB-based simulators (including our eqsim) don't, so don't trust a simulator for
  alignment. The lesson comes from a camera restart on entering a patched screen, from a PEN-F HSL patch in
  fishcu/oly_fw_analysis, which had a u32 struct at a 2-byte boundary.[^inf1]

## Cache and card files

- **Write card logs with 8.3 names, from a heap buffer, with fwrite.** The early card logs were all 0 bytes, for three
  reasons in turn. The first log was written from an uncached buffer. Then the names were long, but firmware paths
  are 8.3 only. Then the logger called fread instead of fwrite.[^cam2]
- **Write code through the uncached view.** Writing firmware code in RAM through the cached address resets the camera,
  because of memory protection. OMKit installs its hooks through the uncached alias, byte by byte, first byte last,
  each inside one 16-byte line.[^cam13]
    - Two checks flag any store into the always-loaded code. om-emu patch 0010 `OM_CODEWRITE` does it at run time and
      preflash C1 does it statically. One of our test images hit exactly this and gave a black screen.[^emu1]

- **Make no card writes after a USB mass-storage session until power-off.** The camera still reports the card as
  mounted after the PC session. A camera write then puts back the old FAT, which corrupts the directory.[^inf3]
- **A firmware "w" open doesn't truncate.** Rewriting a file with shorter content left the tail of the old file
  behind on our E-M5 III. Remove the file first, or have readers stop at an end marker.[^cam15]

## Hook code

- **Every `nc`/`nj` must resolve, and only PCREL relocations are allowed.** An inline comment on an `nj` line left a
  jump unresolved, and `link` silently ignored a SYM_DIFF relocation. The result was a jump-to-self at a hook
  entry.[^fw2]
- **Resolve local branches before taking bytes from an object file.** The mn10300 assembler keeps same-section
  branches as PC-relative relocations, for linker relaxation. `objcopy -O binary` on the object then gives a zero
  displacement, which is a branch to itself. Link or resolve the object, and check that `objdump -r` lists
  nothing.[^fw13]
- **`call` and `calls` overwrite mdr.** Both write the return address to mdr. A stub that makes its own call and then
  jumps on to a native handler must save mdr before that call and restore it. The handler's `ret` and `retf` paths
  use mdr. Simulators must model it too.[^fw13]
- **Give non-leaf functions room in the `call` frame.** With `call f,[d2,d3,a2,a3],16`, an inner call's return
  address lands on a saved register, so the caller gets a3 back as its return address. Use 32 for functions that
  call others. 16 is fine for leaves.[^emu2]
- **Short "functions" just before a function are its prologue entry.** Two to six bytes of `movm` or `add -N,sp`
  before a body are a second entry for indirect callers. Direct callers use a frame-carrying `call` to the body. They
  are not thunks.[^fw8]
- **Don't take over the native console tee.** Its writer reads the ring pointer again for every byte and takes no
  lock. Clearing the pointer while a write is running can store through a null pointer, whatever order the clear
  uses. Format your own output instead.[^fw5]
- **Save locals from `(4,sp)`.** A call writes its return address at `(0,sp)`, which corrupted locals in one
  design.[^fw3]
- **The debug console isn't only reachable from the UART.** Its line executors can be called from our code.[^fw5]
- **Arm Live Time hooks only in S and M, not B.** Hooks active in B mode shut the camera off when armed.[^cam6]

## Image engine

> [!WARNING]
> The image-engine bridge can refuse a record, for example for its capacity. The worker then parks and the camera
> hangs until the battery is pulled. Read the bridge's checks for every record change.[^cam4]

- **Release and refill rows per frame without the "row done" notify.** A "row done" notify for frames we didn't
  develop rebooted the camera about 2 s after the press.[^cam5]
- **No anti-shock while a log is pending.** An anti-shock single shot while a log dump was pending froze the camera.
  The root cause is unknown.[^cam5]
- **The Live ND bridge admits only job 11 with an ND record.** Other jobs need their own controller, never a
  bypass.[^fw5]
- **OM-5 image-engine request packets are 8 bytes bigger than the E-M5 III's.** They are 84 B against 76 B, with the
  payload slot at +71 against +63. So donor setters can't go straight into the E-M5 III programming tables. Use an
  indirect shadow payload as Live ND job 11 does.[^fw5]
- **An early E-M1 III-based port blob was unusable.** A porter bug overlaid 42 trampolines (`0xd0` B) on the rodata
  base, so 181 rodata and RAM references were `0xd0` low. The E-M5 III iseq task never dispatches ND event bits `0x10`
  to `0x80`. A failed finish never called done, which hangs the sequencer. Those stages were flag-off regression
  builds only, and a reviewed engine fixed the shift.[^fw1]

## ARM co-processor

- **Check the CA9-started byte before any ISC call.** ISC calls take hardware locks that retry forever, and a
  "timeout" argument doesn't bound them. Start the CA9 only through its manager, because the worker is core-1
  only.[^fw5]
- **Power the ARM by posting to the CA9 manager queue with owner Take.** Request word 1 is on and 0 is off. Never post
  `0x00010000` (Wi-Fi off), because it stops the ARM even when other users need it. Don't call the start and stop
  workers directly, because the start blocks until Linux boots.[^fw5]
- **Convert addresses between the MN103 and ARM views with the native helpers.** The MN103-to-ARM helper masks with
  `0x3fffffff` and covers MN103 addresses `0xa0000000` to `0xdfffffff` only. The inverse maps ARM addresses below
  `0x20000000` to the `0xc...` view and the rest to the `0x8...` view. A helper that just adds `0x80000000` works
  only for `0xa...` and `0xb...` addresses, so never pass it pool bank 2 at `0xc4000000`.[^fw15]
- **Don't start the ARM mid-shot.** When a build posted Take on at state 34, the camera reset. The cause is open. Keep
  the ARM Linux RAM, which is reloaded from flash on every start, free of HHHR buffers.[^cam7]
- **Don't stop the ARM mid-shot either.** When a build posted Take off in the silent-single shot hook, the camera reset
  too. Post Take on and off only at an Idle (0) or Standby (11) state change. The ARM running during body-button shots
  is fine. A later build confirmed that start and stop at Idle are safe.[^cam7]

## Menus and screens

- **Don't extend fixed-size picture lists or counts the firmware sized itself.** In the first mod loader versions,
  MENU reset the camera anywhere, with or without a card, although the om-emu tests passed.[^cam10]
    - The build extended the Custom Menu letter-cell picture lists. It wrote entry 22 into the 16 zero bytes after
      each list and raised 32 widget template counts from 21 to 22.
    - The Wi-Fi shell captured an NMI on CPU0 in the list copy routine. The same build without those edits works.
    - A new menu letter now uses the stand-in glyph.
    - For a crash, capture the NMI dump over the Wi-Fi shell (`nc ... | tee`) before bisecting.
- **GUI picture widgets (class `0x8003`) take at most 8 picture states.** The widget caches one picture pointer per
  state at object +172 for 8 states, so state 8 and up reads a wild pointer and resets the camera. om-emu reads zero
  there and hides it. A side-bar editor test hit it with +2 on a 12-state digit widget.[^cam9]

> [!WARNING]
> Don't run the settings-store `size` shell sub-command (it prints "b/c/m %08d/%08d"). It measures each store by
> running the default rebuilder on the live image. The user settings become defaults, and the next power-off saves
> that.[^fw8]

## Webcam

- **Don't treat LST and IOC as errors in the DEPEVT status check.** The second webcam test broke on replug and gave errors,
  because its check treated LST/IOC as errors (`and 15` → `1`). Its reset and disconnect also skipped EndTransfer,
  unlike stock. Both were fixed in later tests.[^cam1]
- **Keep a pacing gate below the timer period.** A 34,000 µs gate equal to the 34 ms timer period skipped frames and
  gave jitter.[^fw4]

## Testing and tools

- **om-emu is not a boot test.** It never runs the boot stub, the section loader or USRSTART2-5, because its lab ends
  the init task. A build that breaks the start chain or the card updater's start can pass every om-emu script. Use
  `recovery_reach.py` for boot-path changes and `fupcheck.mjs` for the updater.[^fw6]
- **An om-emu pass covers only boot, UI, menus and settings.** om-emu stands in for the shooting state machine, burst,
  the image engine, block2, the ARM, CPU1-3 and boot from reset. Hooks there are never reached, such as the Live ND
  sites and the HHHR hook. Check coverage (`WATCH_PCS`) to see if a hook ran.[^fw5]
- **Delete the result JSON before each om-emu run.** An om-emu run that crashes during `open_session` writes no result
  file. A bisect that reads a fixed result path then sees the last pass, which is stale. Our `bisect3+.py` does
  this.[^fw5]
- **Run `preflash.py` on every build before it is zipped for flashing.** It caught a boot-race hook statically, and
  found Live ND guards overlapping an HHHR guard. om-emu alone passed a build with a hook into never-loaded code,
  because it doesn't run that path.[^fw6]
- **Disassemble the stabiliser program (LUKE) as plain `mn10300`, not `am33-2`.** Its maths extension ops (`udf`)
  share encodings with AM33 instructions, so `-m am33-2` shows `fadd`, `mcst48` and similar instructions it never
  uses. The same pass showed that LUKE has no handler for the target-position drive (`bc` id 11), which earlier notes
  listed as a route to star tracking.[^fw9]

## Donor bodies

- **The OM-5 does not switch to a "Live ND buffer layout" at run time.** Its preview ring pools are built at every
  boot like all pools, and are simply used only while the preview runs. The pool-map "flag `0x100`" is the lock-tag
  word at pool +16, not a layout flag. Adding pools the OM-5 way would put new code in boot-time static init, which we
  can't recover from the card if it goes wrong. Make pools lazily at preview start instead.[^fw7]
- **A menu string is not a feature.** OM-5 II GUI strings and MODE_* keys list features the body does not offer (Human,
  Birds and Dogs & Cats subjects, ND32/64/128, Live GND imaging). They are shared OM-series UI text. Likewise the
  MDET_DL subject-detect code in the E-M1 III, OM-5 and OM-5 II is dead code. Only the E-M1X and OM-1 family ship it.
  Confirm a feature with reachable code or an om-emu menu run before calling it a donor.[^fw5]

## Corrected beliefs

Things we thought were true, and what turned out to be the case.

<details><summary>All 25 corrected beliefs</summary>

| belief | truth |
|---|---|
| Hidden USB Mode value 1 = tether | HID PC-remote (PID `0x132`) |
| camecon re-enable gives a webcam | no handler, no live-view ops. The webcam must be ported |
| HHHR / Live ND / Star AF are menu-hidden like focus stacking | compiled out, ports needed (though the Live ND plumbing is present but off) |
| E-M5 III is TruePic IX | TruePic VIII (but not distinguishable as silicon from firmware) |
| E-M1 III → E-M5 III match ≈ 50% | 81-83% once LZ4 sections are expanded |
| E-M1 III is the donor | OM-5 1.2 (memory map fits 1 GB)[^pol2] |
| The OM-5 lengthens frames by capping fps | the OM-5 sends kind `0x400` + fps 0 from DigitalNd. A photo = ≤16 frames at the set Tv |
| `0x606320f2` is fwrite | it's fread. fwrite is `0x60631fe8` |
| iseq name table is {name,id} | {u32 id, char *name} |
| Prop 36537 is the hidden Live ND switch | a develop/gradation setting. Don't use it |
| Card update runs from an independent loader | the SD updater is in block0 (FIRMUP_CLI) |
| OM-5 II does ND64/128 | strings only. The engine does ND2-ND16. caduceus-om5 reports ND32/64 working after extending the step selector, with the merge count unverified[^inf2] |
| One test photo showed a merge | motion blur, retracted[^fix1] |
| Bundled binutils has `ld` | as/objdump/objcopy only |
| `0x6017f475` / `0x6019faf0` are our hooks | stock bytes decoded at the wrong offset |
| Selector 1 / Pop Art needed for allocation | only for the old typed-arena route |
| Allocation refusals were a code bug | selector 2 = HIGH_ISO from auto ISO in a dark room. Test at fixed ISO 200 |
| ND32 via longer burst frames[^pol1] | the OM-5 merges ≤16 frames at the set Tv. ND32 has no donor code and needs our own two-pass design |
| Route source = ctx byte 24949 (prop 38497) | doubtful. 24948/24949 look like bracketing info |
| `0x603fceb1`.. switch = readout setup per route | metadata tags (kinds 104/109) and the bracketing map |
| Main-pool address lookup is linear | two-block class, ids 9-20 in the second block |
| OB/WB are set at capture prep | filled later, at the metadata step |
| E-M5 III has no Live ND code at all | the OM-5 plumbing is compiled in, switched off |
| Webcam Photo Booth reopen bug is in the camera | the host never calls startStream on reopen. It is on the host side |
| The HHHR ARM reference frame maps request +4, and every pool keeps its bitmap at +64 | frame 0 maps +0 (the Y image), and 40 base-class pools keep it at +4. Caught by another tool's build[^fw5] |

*Beliefs we held and later corrected.*

</details>

## Dead ends

Approaches we tried and dropped, with the reason. Please don't redo them without a new idea.

- Forcing debug flags (`fcs seq set2 6`, `mode_digital_nd`) to switch features on. The engines are compiled out.
- Auto-closure porting of Live ND shooting helpers. It pulled in other subsystems, so we matched by hand instead.
- Webcam live frames while USB-connected. The camera leaves shooting mode.
- Flashing a whole OM-5 or OM-5 II image, and a full OM-5 II UI transplant.
- Porting deep-learning subject detection. It needs OM-1 hardware.
- Merging raw frames on the CPU. A byte-wise merge took 0.46 s per 128-row band (about 14 s per frame), so we chose
  image-engine job 11.[^cam4]
- Porting the OM-5 capture command struct. It is 19 words against the native 16 (an extra pointer at +28). Use the
  native StlUhs instead.[^fw11]
- Frame-rate caps on the AE selector or request. They are a wrong model of the OM-5, which asks the sensor for longer
  frames instead.[^fw11]

## Address reference

E-M5 III 1.7 block0 addresses (base `0x60021020`) unless noted.

| item | address |
|---|---|
| pool table, real address | `0x6053e158` |
| pool table, the typo | `0x60539158` |
| fread | `0x606320f2` |
| fwrite | `0x60631fe8` |
| stock bytes once taken for our hooks | `0x6017f475`, `0x6019faf0` |
| serial channel map | `0x600c2580` |
| serial port 3, port 1 | `0x98600000`, `0x98200000` |

*Addresses and names.*

| item | address |
|---|---|
| section 10 end as raised by the Live ND test builds | `0x61483000` |
| CPU 1/2 code buffer | `0xa1483000` |
| section 10 end in the decoded block0 | `0x61478000` |
| RAM with no code references | `0x61485000` to `0x61a00000` |
| main pool, second block (ids 9-20) | `0xc4000000` |
| upper limit for CPU reads | `0xc0000000` |
| ARM Linux RAM | `0xc0000000` to `0xc2aa0000` |
| peek build's upper limit | `0xdeffffff` |
| pool `0x0700` | `0xaa91d340` |
| program destination range | `0xa0000000` to `0xbfffffff` |
| physical-pool allocator | `0x600232c5` |
| native tee-open | `0x6010189a` |
| flash names (not CPU addresses) | `0x40000000` to `0x47ffffff`, and from `0x80000000` |
| native flash copy helper | `0x60022180` (`clr d0` at `0x6002234f`) |
| write guard's last window | `0x47b80000` to `0x48000000` |
| bank 6 trailer | `0x45d5ffe0` to `0x45d60000` |
| bracket info back end | `0x60308658` |
| its GUI caller | `0x607d289c` |

*Start-up, memory and flash.*

| item | address |
|---|---|
| Live ND image-engine bridge | `0x607ac076` |
| ISC dispatcher, send | `0x61206cfe`, `0x61205800` |
| ISC lock retries | `0x61206b95`, `0x6120597e` |
| CA9-started byte, its getter | `0xa2624f09`, `0x60059129` |
| CA9 start worker (core 1 only) | `0x60058e21` |
| CA9 manager queue u16 | `0x60041252` |
| letter-cell list copy routine | `0x60c944b6` (NMI at PC `0x60c94831`) |
| picture widget state cache | `0x60cc9888` |
| settings-store `size` handler (near) | `0x6005b81a` |
| default rebuilder call, into | `0x6005ca77` -> `0x6005c805`, into `0x623d1000` |
| webcam DEPEVT check byte (our build) | `0x613bb640` |
| stock EndTransfer path | `0x60c348fb` |
| shooting state machine | `0x602b...` |
| HHHR hook | `0x602a13b4` |
| HHHR guard | `0x600d079e` |
| readout switch once misread | `0x603fceb1` |
| metadata step (OB/WB) | `0x6040c7f5` |
| MN103 to ARM, ARM to MN103 helpers | `0x600590c9`, `0x600590f3` |
| console tee writer, ring pointer | `0x60022f61`, `0xa264dea8` |
| firmware file open used for writes | `0x60631f63` |

*Image engine, ARM, menus, webcam and tests.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^cam1]: Seen on our E-M5 III in the webcam tests, 2026-10-20.
[^cam2]: Seen on our E-M5 III using test firmware, 2026-10-24.
[^cam3]: Seen on our E-M5 III using test firmware, 2026-10-26.
[^cam4]: Seen on our E-M5 III using test firmware, 2026-10-29.
[^cam5]: Seen on our E-M5 III using test firmware, 2026-10-30.
[^cam6]: Seen on our E-M5 III using test firmware, 2026-11-04.
[^cam7]: Seen on our E-M5 III using test firmware and read in the firmware, 2026-11-06.
[^cam8]: Read in the firmware and seen on our E-M5 III, 2026-11-12.
[^cam9]: Read in the firmware and seen on our E-M5 III in a side-bar editor test, 2026-11-20.
[^cam10]: Seen on our E-M5 III using test firmware, until 2026-11-22.
[^cam11]: Seen on other bodies, 2026-11-18. caduceus-ep7 `docs/SD_V2_CRASH.md` (E-P7) and caduceus-om5 `research/OM5II-IMAGE-STORE-FAULT-2026-11-11.md` (OM-5 II).
[^cam12]: Seen on a camera in the camera-stuff project's GX1/GX2 probe (`research/NOTES.md`), 2026-11-07.
[^cam13]: Seen on the OM-5 II, from OMKit `docs/architecture.md` §6, read 2026-11-21.
[^cam14]: Seen on our E-M5 III using test firmware, 2026-11-19.
[^cam15]: Seen on our E-M5 III using test firmware, 2026-11-22.
[^emu1]: om-emu and preflash checks, 2026-11-23.
[^emu2]: Seen in om-emu, 2026-11-22.
[^fw1]: Read in our port code, 2026-10-21.
[^fw2]: Read in our build tools, 2026-10-29 and 2026-10-30.
[^fw3]: Read in the firmware, 2026-10-31.
[^fw4]: Read in our webcam code, 2026-10-20.
[^fw5]: Read in the firmware, 2026-11-05.
[^fw6]: Read in the firmware and our tools, 2026-11-07.
[^fw7]: Read in the firmware, 2026-11-15.
[^fw8]: Read in the firmware, 2026-11-18.
[^fw9]: Read in the firmware, 2026-11-23.
[^fw10]: Read in the firmware, 2026-11-25.
[^fw11]: Read in the firmware.
[^fw12]: Read in the firmware, 2026-11-12.
[^fw13]: Read in our build tools and the MN10300 toolchain, 2026-11-05.
[^fw15]: Read in the firmware, 2026-11-06.
[^inf1]: Inferred for the E-M5 III, 2026-11-11, from a camera restart in fishcu/oly_fw_analysis.
[^inf2]: Reported by caduceus-om5 (`firmware/om5ii/nd64.py`), 2026-11-18. Not checked by us.
[^inf3]: Seen by atx's fenykl project on an E-PL3, 2026-10-19. Inferred for the E-M5 III. See our fenykl notes.
[^pol1]: Decision 2026-10-31.
[^pol2]: The OM-5 1.2 has been the donor since 2026-10-22.
[^fix1]: A retracted reading. See [History](#history).

## History

- 2026-11-22: the MENU reset in the first mod loader versions was first put down to the cache. The picture-list edits
  caused it.
- 2026-11-05: an earlier note called the ~5 MB zero run `0x61483b31` to `0x61858fe0` likely zero-init data, not free,
  and listed using the zero runs in block0 as free space as a dead end. The area after section 10 is `0xff` padding
  the loader never copies.
- One test photo was read as a successful merge. It was motion blur, and the reading was retracted.

