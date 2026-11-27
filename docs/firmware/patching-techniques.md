# Modifying the firmware: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Feature ports](../guides/port-anatomy.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

This page collects the ways we have changed the E-M5 III's firmware and seen them work, one technique per section.
Each section gives the method in general terms, the pitfalls we hit, how to take it further, and a link to a worked
example. It ends with a **checked on** table. The table says which camera and firmware the technique has been shown
on, by whom, and how sure it is.

A method that works on one body is a lead on another, not a result. The addresses, tables and load order differ, so
each body needs its own row. If you get a technique working on another camera, a new row is welcome.

For how the camera works underneath, read the [guides](../guides/README.md) first. Exact addresses live on the
reference pages each section links to.

Terms used here:

- A **byte patch** changes a few bytes in place, for example to turn a branch into a no-op.
- A **section** is one of the ten parts of the main program that load in the background after power-on
  ([boot and sections](boot-and-sections.md)).
- **Slack** is the unused `0xff` bytes after the end of a section in the firmware file. Our code goes there.[^fw1]
- A **hook** redirects a native jump or call into our code, which then returns to the original path. A
  **trampoline** is the small piece of code that saves registers, calls our code and restores them.
- A **boot guard** is a check that the section a hook jumps into is ready.
- **Armed** means the user has asked for a feature. Our features act only when armed. Otherwise every hook falls
  straight through to stock behaviour.
- The **donor** is the newer body we port code from (the OM-5).

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on a camera, blue = read in the firmware,
grey = inferred or seen in an emulator.

In the checked-on tables, the status column says how far a technique has been shown. "Camera" means seen on a real
camera, "firmware" means read in the firmware, and "emulator" means seen in an emulator. Rows from other projects are
their reports, credited and linked. We have not repeated them.

## Techniques

1. [Byte patch, repack and flash](#1-byte-patch-repack-and-flash)
2. [Make room for code](#2-make-room-for-code)
3. [Hook native code](#3-hook-native-code)
4. [Guard hooks during boot](#4-guard-hooks-during-boot)
5. [Act only when armed](#5-act-only-when-armed)
6. [Keep settings across power-off](#6-keep-settings-across-power-off)
7. [Add native menu rows](#7-add-native-menu-rows)
8. [Run the image engine on your own frames](#8-run-the-image-engine-on-your-own-frames)
9. [Add shooting states](#9-add-shooting-states)
10. [Port code from a newer body](#10-port-code-from-a-newer-body)
11. [Watch a test run live](#11-watch-a-test-run-live)
12. [Change the USB personality](#12-change-the-usb-personality)
13. [Recover from a bad flash](#13-recover-from-a-bad-flash)
14. [Prototype in an emulator first](#14-prototype-in-an-emulator-first)
15. [Borrow a stock menu row for a settings page](#15-borrow-a-stock-menu-row-for-a-settings-page)
16. [Run commands from a card file](#16-run-commands-from-a-card-file)
17. [Press buttons remotely](#17-press-buttons-remotely)
18. [Change an image-engine program](#18-change-an-image-engine-program)
19. [Ask the sensor for a different mode](#19-ask-the-sensor-for-a-different-mode)
20. [Power up the ARM helper yourself](#20-power-up-the-arm-helper-yourself)
21. [Load feature code from the card](#21-load-feature-code-from-the-card)

## 1. Byte patch, repack and flash

**What it gets you.** The smallest possible change. Remove a check, change a constant, flip a branch.

**Method.**

1. Unpack the update file. Our public `olyfw.py` does the unpacking.
2. Change the bytes in the decoded block.
3. Repack, and fix the block and file checksums. [Container format](container-format.md) describes the wrapper and
   checksum.
4. Flash it from the card like an official update.

**Pitfalls.** The camera checks the checksums, not whether the code makes sense. A correct checksum says nothing about
whether the camera will start. Keep a known-good file on hand to flash back ([recovery](recovery.md)).

**Extend it.** Most constants worth changing (time limits, allowed lens lists, setting ranges) sit next to a compare
or a table. Look for the compare in the code that uses the value.

**Worked example.** [Focus stacking with any lens](../features/focus-stacking.md), which changes one branch.

| camera · firmware | status | by | notes |
|---|---|---|---|
| E-M5 III · 1.7 | camera | this project | focus stacking with any lens[^cam2] |

*Where the byte patch has been shown.*

**Other bodies.** Every MN103 body we have opened uses the same container and checksum scheme
([container format](container-format.md#which-camera-a-file-is-for)).[^fw1] Flashing a modified file on them is not
checked here.

## 2. Make room for code

**What it gets you.** Space for your own code and tables, loaded by the camera's own loader.

**Method.**

- Each section is copied up to an end address written as a constant in the loader. Raising that constant makes the
  slack after the section load with it ([boot and sections](boot-and-sections.md)).
- Prove a new region before you rely on it. Put a small routine there and check it runs.
- Give each feature its own region and record it in the [memory map](../hardware/memory-map.md#spare-space-for-our-code),
  so builds can be stacked without overwriting each other.

**Pitfalls.**

- Slack in a later section only exists once that section is ready (technique 4).
- Don't assume an unloaded region is clean. On the OM-3, unloaded gaps held leftover data, not the file's `0xff`
  (camera-stuff).[^cam8]
- Never store patch state into the loaded program image through the cached address range. On other bodies this
  restarted the camera ([gotchas](../reference/gotchas.md)).

**Extend it.** The always-ready part at the start of the program has a small tail for guards and stubs that must run
at any time. Everything larger goes after a section.

**Worked example.** The regions table in the [memory map](../hardware/memory-map.md#spare-space-for-our-code).

| camera · firmware | status | by | notes |
|---|---|---|---|
| E-M5 III · 1.7 | camera | this project | sections 3, 4 and 10 raised and used. Section-0 tail used for guards. |
| OM-3 · 1.1 | camera | camera-stuff (fernandezk26) | section 6 end raised by 4 KB and 64 KB, a probe checked the region on every pass |
| E-P7 · 1.1 | firmware | Caduceus E-P7 | code-space survey, including handlers reachable only from a debug command |

*Where making room for code has been shown.*

**Other bodies.** Look for the loader's section table and the switch of end constants it uses.

## 3. Hook native code

**What it gets you.** Your code runs at a chosen point in the camera's own flow, then the camera carries on.

**Method.**

- Replace a native `jmp` or `call` with one into a trampoline. The trampoline saves every register it touches,
  including MDR, and runs your code. Then it performs the displaced instructions and returns to the original path.
- Copy native call frames exactly. The MN103 `call` builds the callee's frame, so a wrong frame size corrupts the stack
  ([MN103 primer](../guides/mn103-primer.md)).
- Before touching native objects, check the context. The code must be running in a task (not an interrupt) and on the
  expected core, and it takes locks with a time-out. On failure, fall through with registers and stack unchanged.

**Pitfalls.**

- No file I/O, locks or waits in interrupt context. Some completion callbacks run in an interrupt.
- Every absolute address needs native evidence (an operand in the stock code), not a value from notes. A single typo
  in a table address cost several flashes.
- Compile C as plain MN10300. The camera's own code never uses AM33-only encodings, so ours doesn't either.

**Extend it.** Before hooking a function, read two of its native callers to learn what each register means at the
hook point.

**Worked example.** The Live ND hooks ([Live ND](../features/live-nd.md)).

| camera · firmware | status | by | notes |
|---|---|---|---|
| E-M5 III · 1.7 | camera | this project | many hooks in the capture, menu and live-view paths |

*Where hooking native code has been shown.*

**Other bodies.** The call and frame rules are the CPU's, so they hold on every MN103 body. The hook points differ.

## 4. Guard hooks during boot

**What it gets you.** Hooks that can't stop the camera from starting.

**Method.**

- Sections are read in one order but become **ready** in index order, 1 to 10. Until a section is ready, the loader
  watches its range with a hardware access monitor, and touching it stops the boot ([boot](../guides/boot.md)).
- A hook may jump only into a section that is ready before the hook can run, or through a guard. A guard is a few
  instructions in always-ready code that test the section's ready bit. If the bit isn't set, the guard runs the stock
  instructions and returns.

**Pitfalls.** Code that runs at boot can surprise you. The menu's setting getter and setter run before any menu is
opened. Emulators that don't model the access monitor will run a build that boot-loops on the camera.

**Extend it.** One guard can serve several hooks into the same section. Keep guards in the always-ready tail.

**Worked example.** The boot lesson on the
[saved settings](../features/saved-settings-and-menu-rows.md#where-the-code-goes-the-boot-lesson) page. The ready bits
are in [boot and sections](boot-and-sections.md).

| camera · firmware | status | by | notes |
|---|---|---|---|
| E-M5 III · 1.7 | camera | this project | guards on every out-of-section hook. A build without one boot-looped. |
| OM-5 II · 1.1 | firmware | Caduceus OM-5 research | same access monitor in the loader |

*Where boot guards have been shown.*

**Other bodies.** Find the ready-bit word and the function that waits for a section.

## 5. Act only when armed

**What it gets you.** A modified camera that behaves exactly like stock until you ask for the feature.

**Method.** Every hook starts by checking one condition, such as a setting, a menu row or a mode. If it isn't met, the
hook falls straight through to the stock path with nothing changed.

**Pitfalls.** "Nothing changed" includes registers, the stack and timing-sensitive paths. A hook that does work before
the check can still break stock behaviour.

**Extend it.** Once a feature has a menu row (technique 7), the row becomes the arming condition.

**Worked example.** Every [Live ND](../features/live-nd.md) hook checks its armed flag first.

| camera · firmware | status | by | notes |
|---|---|---|---|
| E-M5 III · 1.7 | camera | this project | all our builds keep stock behaviour when not armed |

*Where arming has been shown.*

## 6. Keep settings across power-off

**What it gets you.** Your feature's settings survive power-off, saved by the camera itself, with no card file.

**Method.**

- The user settings live in one RAM image that the camera saves to flash as a whole at power-off. Stock records end
  well before the end of the image, and stock code never reads the rest.
- Keep your values in that unused tail behind a marker. On first use, if the marker is missing, write defaults.
  Range-check every value when reading.

**Pitfalls.** A settings reset or the stock restore file doesn't clear the tail, so provide your own reset. A battery
pull loses changes since the last save.

**Extend it.** The same block can hold tuning values for development.

**Worked example.** [Saved settings and menu rows](../features/saved-settings-and-menu-rows.md#where-the-values-live).

| camera · firmware | status | by | notes |
|---|---|---|---|
| E-M5 III · 1.7 | camera | this project | values survive power-off[^cam3] |
| E-P7 · 1.1 | firmware | Caduceus E-P7 (internal storage notes) | the idea's source. Built and emulator-checked, not run on a camera. |

*Where saved settings have been shown.*

**Other bodies.** Find the settings image, the end of its records and the save routine.

## 7. Add native menu rows

**What it gets you.** Your feature appears in the camera's own menus, looking and behaving like a stock row.

**Method.**

- The menu is built from data tables (tabs, pages, controllers, value lists, strings). Copy the tables you need into
  free space and point the stock code's counts and bases at the copies.
- Give new rows new setting ids. Hook the menu's getter and setter so the new ids read and write your saved block
  (technique 6) and every other id runs stock code.
- Answer new text through a hook on the string lookup.

**Pitfalls.** A tab page holds a fixed number of rows. The getter and setter run at boot (technique 4).

**Extend it.** A row can sit wherever the newer body has it, because a row reaches its value through its setting id.

**Worked example.** [Saved settings and menu rows](../features/saved-settings-and-menu-rows.md#how-the-menu-rows-are-added).
The menu tables are on [settings and menus](settings-and-menus.md), and the
[Settings and menus guide](../guides/settings-and-menus.md) walks through it.

| camera · firmware | status | by | notes |
|---|---|---|---|
| E-M5 III · 1.7 | camera | this project | Live ND row and page in Shooting Menu 2[^cam3] |

*Where native menu rows have been shown.*

**Other bodies.** Not checked. Bodies with the newer OM-1-style menus may be built differently. Look for the tab lists
and the getter and setter that take a setting id.

## 8. Run the image engine on your own frames

**What it gets you.** The image engine's own programs (merging, averaging) applied to frames you chose.

**Method.**

1. Hold the frames you want instead of letting the camera release them.
2. Fill the job's record (inputs, output, black level, clip).
3. Submit the job through the camera's own worker.

**Pitfalls.** The bridge checks the record before the engine runs. Ask the frame pools for addresses rather than
computing them.

> [!WARNING]
> A record the bridge refuses hangs the camera.

**Extend it.** A second donor program (job 12) runs on live-view frames the same way, for the Live ND preview.

**Worked example.** [Live ND](../features/live-nd.md). The jobs and records are on the
[image engine](../hardware/image-engine-technical.md#safe-submission) page.

| camera · firmware | status | by | notes |
|---|---|---|---|
| E-M5 III · 1.7 | camera | this project | donor merge job on held photo frames, job 12 on live-view frames |

*Where running the image engine on chosen frames has been shown.*

**Other bodies.** The job programs differ per body
([which jobs each camera has](../hardware/image-engine-technical.md#jobs-by-camera)).

## 9. Add shooting states

**What it gets you.** New steps in the capture sequence, the way a newer body adds a feature's own states.

**Method.** Copy the shooting state table to free space, add states, and point the table base at the copy
([shooting sequencer](shooting-sequencer.md#the-state-table)).

**Pitfalls.** Event numbers change when the table is renumbered. Check every event a ported state posts.

| camera · firmware | status | by | notes |
|---|---|---|---|
| E-M5 III · 1.7 | camera | this project | relocated table with added states |

*Where added shooting states have been shown.*

## 10. Port code from a newer body

**What it gets you.** A newer body's feature logic, without rewriting it.

**Method.**

- Relocate the donor's functions into free space and resolve their calls to the matching native functions.
- Where a call joins the native code, read the native callers to learn the arguments, and write an adapter. Never
  assume the donor's arguments.

**Pitfalls.** The same helper can take different arguments on the two bodies even when it builds the same thing.

**Worked example.** [Live ND](../features/live-nd.md), ported from the OM-5.

| camera · firmware | status | by | notes |
|---|---|---|---|
| E-M5 III · 1.7 (OM-5 · 1.2 donor) | camera | this project | Live ND functions relocated and running |

*Where ported donor code has been shown.*

## 11. Watch a test run live

**What it gets you.** Feedback from a test run without guessing from the photo.

**Method.** The stock firmware has a debug Wi-Fi shell turned on by a settings file on the card. Its trace shows the
camera's own events as you press buttons ([Wi-Fi debug shell](../features/wifi-debug-shell.md)). Our builds also write
a small log to the card.

**Pitfalls.** Card writes only from a safe point, not from an interrupt and not mid-burst.

| camera · firmware | status | by | notes |
|---|---|---|---|
| E-M5 III · 1.7 | camera | this project, using the shell found by oly_fw_analysis | |

*Where live tracing has been shown.*

## 12. Change the USB personality

**What it gets you.** The camera presents itself as a different USB device.

**Method.** Change the product id, class and descriptors the USB stack hands out ([USB](../hardware/usb.md)).

| camera · firmware | status | by | notes |
|---|---|---|---|
| E-M5 III · 1.7 | camera | this project | webcam class enumerated and streamed ([webcam](../features/webcam.md)) |

*Where a changed USB personality has been shown.*

## 13. Recover from a bad flash

**What it gets you.** A way back when a build stops the camera from starting.

**Method.**

- The card updater (hold OK at power-on with the update file on the card) runs before the main program's sections. So
  it still works when a build boot-loops. Flash the last good file
  ([recovery](recovery-technical.md#the-card-updater-hold-ok-at-power-on-dcolympe1379999bin)).
- Check every build before it goes near the camera
  ([pre-flash checks](recovery-technical.md#pre-flash-check-suite)). The checks cover these.
    - container and checksums
    - the camera's own update validator
    - boot-critical bytes left alone
    - section load order and guards
    - address evidence

**Pitfalls.** The checks only catch what they model. One build passed a load-order check that used the read order, not
the ready order, and boot-looped.

> [!WARNING]
> Never cut power while the camera writes the main block.

**Extend it.** Each failure becomes a new check.

| camera · firmware | status | by | notes |
|---|---|---|---|
| E-M5 III · 1.7 | camera | this project | a boot-looping build was recovered with the card updater[^cam3] |

*Where recovery with the card updater has been shown.*

**Other bodies.** The updater's checks and write order differ. Find what it validates before it writes.

## 14. Prototype in an emulator first

**What it gets you.** Menu and screen changes tried in minutes, without flashing.

**Method.** [om-emu](https://github.com/flatpanda/om-emu) (by flatpanda) boots the E-M5 III 1.7 firmware to its menus
and shooting screen and takes byte patches. Apply the build, script key presses, and compare screens and states with
stock.

**Pitfalls.** It does not model the sensor, the image engine, the other cores or the boot access monitor. So a build
that runs there can still boot-loop on the camera (technique 4). Shooting-path hooks are never reached.

**Extend it.** Running the camera's own update validator inside the emulator checks a file before flashing.

| camera · firmware | status | by | notes |
|---|---|---|---|
| E-M5 III · 1.7 | emulator | this project, with om-emu | native menu rows and the settings page were prototyped there first |

*Where emulator prototyping has been shown.*

**Other bodies.** om-emu also boots the OM-5 1.2 and OM-5 II.[^fw1] See its own documentation.

## 15. Borrow a stock menu row for a settings page

**What it gets you.** A page of your own settings quickly, before doing native rows (technique 7).

**Method.** Take a stock row that opens a display-only screen and point its handler at your own screen, drawn by the
stock list view. On the E-M5 III the host is the Custom Menu J2 "Certification" row.

**Pitfalls.** Find a row nobody needs. Values reset at power-off unless you add technique 6.

| camera · firmware | status | by | notes |
|---|---|---|---|
| E-M5 III · 1.7 | camera | this project | development settings page[^cam4] ([memory map](../hardware/memory-map.md#spare-space-for-our-code)) |
| E-M10 II · 1.4 | reported by its project | [fenykl](https://github.com/atx/fenykl) | the idea's source, a settings page on the Eye-Fi row |

*Where a borrowed settings row has been shown.*

## 16. Run commands from a card file

**What it gets you.** Read and write memory and call functions on a running camera, without a debugger.

**Method.** A small console in free space reads a command file from the card when asked. It runs the reads, writes and
calls in it, and writes the output to the card.

**Pitfalls.** File I/O only from a safe point (technique 3). Keep the command set to reads unless you know what a write
does.

| camera · firmware | status | by | notes |
|---|---|---|---|
| E-M5 III · 1.7 | camera | this project | card console after section 10[^cam5] ([memory map](../hardware/memory-map.md#spare-space-for-our-code)) |

*Where the card console has been shown.*

## 17. Press buttons remotely

**What it gets you.** Repeatable tests, with the same key sequence every run, from a laptop.

**Method.** The stock Wi-Fi debug shell (technique 11) has a `ui key` command. `ui key skey <code> 1|0` sets or clears
a key's bit in the button task's key image, so the camera handles it like a real press
([Wi-Fi debug shell](../features/wifi-debug-shell.md)).

**Pitfalls.** The dials, touch screen and power lever are not covered. It can't hold OK at power-on, because the shell
starts after boot.

| camera · firmware | status | by | notes |
|---|---|---|---|
| E-M5 III · 1.7 | firmware | this project | traced. The key-event trace (`ui key debug 1`) is seen on the camera. Scripted presses are not yet tested. |

*Where remote key presses have been shown.*

## 18. Change an image-engine program

**What it gets you.** The image engine doing something its stock program doesn't.

**Method.** Load a modified copy of a program instead of the stock one, changing chosen fields of its microcode words.
Run it on test data through the normal job path (technique 8). Compare the output with stock
([image engine](../hardware/image-engine-technical.md#job-11-on-the-camera)).

**Pitfalls.** The format is only partly mapped. Change one field per test and keep the stock program as the control.

| camera · firmware | status | by | notes |
|---|---|---|---|
| E-M5 III · 1.7 | camera | this project | modified merge program run on the camera[^cam3] |

*Where a changed image-engine program has been shown.*

**Other bodies.** The same engine generation runs from the PEN-F to the OM-5 II. The OM-1 differs.[^fw1]

## 19. Ask the sensor for a different mode

**What it gets you.** Frames of a different length or rate than the camera would choose, such as one frame per set
shutter time for Live ND.

**Method.** Send your own sensor request of the kind the newer body uses, only from the capture you are changing
([Live ND](../features/live-nd.md), [shooting sequencer](shooting-sequencer.md#sensor-requests)).

**Pitfalls.** Change only the requests of your own capture. Giving every caller the new kind hung the camera.

| camera · firmware | status | by | notes |
|---|---|---|---|
| E-M5 III · 1.7 | camera | this project | frames at the set shutter speed for Live ND[^cam6] |

*Where a changed sensor mode has been shown.*

## 20. Power up the ARM helper yourself

**What it gets you.** The ARM co-processor running when you need it, for example as a maths helper, without Wi-Fi.

**Method.** Ask the camera's own power manager for the ARM the way the wireless features do, and hand it back
afterwards ([ARM co-processor](../hardware/arm-coprocessor.md), [Handheld High Res (HHHR)](../features/hhhr.md)).

**Pitfalls.** Sending to the ARM while it is off resets the camera. Change its power only outside a capture.

| camera · firmware | status | by | notes |
|---|---|---|---|
| E-M5 III · 1.7 | camera | this project | powered up and down cleanly around shots[^cam5] |

*Where powering the ARM has been shown.*

## 21. Load feature code from the card

**What it gets you.** Flash the camera once with a small loader. After that, feature code and its updates are files
on the card. A bad module costs a card edit, not a reflash. No card, or OK held at power-on, gives a stock camera.

**Method.** This is how OMKit does it on the OM-5 II.

1. One 5-byte hook in a late start-up callback (live view already up) only creates a low-priority task.
2. The task waits for every section's ready bit.
3. It keeps a once-per-power-on flag in a section reloaded at each boot.
4. It skips everything when OK is held.
5. It retries the card open for a late mount.
6. It checks magic, length, sum and version.
7. It reads the file into free RAM and jumps into it.
8. The loaded core installs its hooks into the code **in RAM**. It writes through the uncached alias, byte by byte,
   first byte last. Each hook is a 5-byte jump inside one 16-byte line and displaces only position-independent
   instructions.

**Pitfalls.**

- Nothing loaded this way runs before the loader. Boot-time guards, section-loading fixes, fault handlers and changes
  to what the boot copies must stay in the flashed image.
- Writing firmware code through the cached address resets the camera (memory protection, per OMKit). Use the uncached
  alias. Data tables the firmware reads through the cache need the same care.
- Quick power off-on and light sleep keep the loaded code running. Auto power-off is a new boot.

**Extend it.** A module interface (one function table that only grows) lets features ship separately.

**On the E-M5 III.** Our loader has the focus-stacking and display mods loaded from the card.[^cam7] It adds a native
Custom Menu letter K, "K. Mods", with an Off/On row per mod and a Wi-Fi Shell row
([saved settings and menu rows](../features/saved-settings-and-menu-rows.md)). Its hook is on the `FastEndCb`
callback. Its base sits in section-1 slack, with the section-1 end raised. The mods live in RAM, and the on/off table
is in the tail of store 50. Holding OK skips loading. It also runs in om-emu. The addresses are in the
[address reference](#address-reference).

| camera · firmware | status | by | notes |
|---|---|---|---|
| OM-5 II · 1.1 | camera | OMKit (necrostaz) | loader on the owner's camera[^cam9]. Wi-Fi and USB start paths not checked. |
| E-M5 III · 1.7 | camera | this project | loader running on the camera, with a "K. Mods" menu[^cam7] |

*Where loading feature code from the card has been shown.*

## Rules for every build

The pre-flash checks in [recovery](recovery-technical.md#pre-flash-check-suite) test most of these
automatically.

1. Every absolute address has native evidence.
2. Every hook outside its target's section is guarded (technique 4).
3. Nothing changes unless armed (technique 5).
4. Context checks come before touching native objects. Locks are taken with a time-out.
5. No file I/O, locks or waits in interrupt context.
6. Native call frames are copied exactly. MDR is saved in trampolines.
7. Frame addresses come from the pools, not from arithmetic.
8. The image engine's record checks are read before any record change.
9. C is compiled as plain MN10300.
10. Each build has a name, a SHA-256, and a procedure with its base, the bytes changed, the test and the recovery. A
    readout of each camera run is written before the next build.
11. The donor's behaviour is researched before a test is designed. Camera runs confirm designs.

## Build infrastructure

- Assembler. Binutils `as`, `objdump` and `objcopy` only, with no `ld`. Our own link step applies relocations and
  checks that every one resolved.[^fw1]
- Simulator. The GDB MN10300 simulator, for gate and diff tests on real images.[^fw1]
- Builds are stored as deltas against the stock file.[^fw1]

## Address reference

E-M5 III 1.7 block0 addresses (base `0x60021020`).

| item | address |
|---|---|
| focus stacking branch (technique 1) | `0x6065e5ec` |
| card loader hook, `FastEndCb` (technique 21) | `0x6019c68c` |
| card loader base, in section-1 slack | `0x6022d800` |
| section-1 end, raised to | `0x6022e800` |
| loaded mods in RAM | `0x61500000`-`0x61a00000` |
| mod on/off table, in the store 50 tail | +`0x39e00` |

*Addresses used by the worked examples on this page.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware or in our tools.
[^cam2]: Seen on our E-M5 III, 2026-10-19.
[^cam3]: Seen on our E-M5 III, 2026-11-19.
[^cam4]: Seen on our E-M5 III, 2026-11-17.
[^cam5]: Seen on our E-M5 III, 2026-11-06.
[^cam6]: Seen on our E-M5 III, 2026-11-05.
[^cam7]: Seen on our E-M5 III, running since 2026-11-22.
[^cam8]: Seen on an OM-3 by the camera-stuff project.
[^cam9]: Reported by OMKit, running on the owner's OM-5 II since 2026-10-30.

