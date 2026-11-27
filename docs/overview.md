# Project overview

<!-- house style -->

## Key points

- This project studies how the Olympus OM-D E-M5 Mark III (E-M5 III) firmware works, for right to repair and to keep an older camera useful.
- The E-M5 III shares its chip and sensor with newer bodies such as the OM-5, so their features could, in principle, run on it too.
- Several changes already work on the camera, among them focus stacking with any lens, a card mod loader and colour and mono profiles.
- This page is a tour of every area we've looked at, with a one-line result and a link to the page with the detail.

This project started with one small patch and grew into a close study of how the E-M5 III's firmware works. The aim is
right to repair and keeping an older camera useful. The E-M5 III shares its chip and sensor with newer bodies such as
the OM-5, so features those bodies have could, in principle, run on it too.

This page is a tour of everything we've investigated, grouped by area, with a one-line result and a link to the page
with the detail. "On the camera" means tested on a real E-M5 III. "In the firmware" means read in the firmware's code.

## Pace

This is a spare-time project. Progress comes in bursts and can be slow, because of family commitments,
and every change has to be tested by flashing a real camera. Several test builds are ready and waiting in the flash
queue, so some "built, not yet run" items below will stay that way for a while.

## Background

This project grew out of an earlier patch to the focus-stacking lens check. It was made with an old IDA Pro, re-signed
and flashed, and it worked. That raised the question of what else could be enabled. Next we cracked the firmware
container, rebuilt it byte for byte, and began comparing the E-M5 III with newer bodies. See
[focus stacking](features/focus-stacking.md) and [container format](firmware/container-format.md).

## Firmware studied

We studied eight firmware files from seven bodies. They are E-M5 III 1.7 (the target), OM-5 1.2 (the main donor),
OM-5 II 1.1, E-M1 III 1.4 and 1.6, OM-1 1.9, OM-1 II 1.3 and PEN-F 3.1. They all share the same file format, control
CPU and load address. That is what makes moving code between them possible. See
[body comparison](bodies/comparison.md).

## Camera systems

For a start-to-finish read, the [guides](guides/README.md) follow one process at a time through the firmware. They
cover taking a photo, boot, a button press, live view, the operating system and how the cores talk. The table below is
the reference.

| area | what we found | page |
|---|---|---|
| The chip | TruePic is the whole SoC: MN103 control cores, an ARM core running Linux, and an image engine that runs small "job" programs. The E-M5 III and OM-5 look like the same silicon | [SoC overview](hardware/soc-overview.md) |
| Control CPU | Panasonic MN103/AM33-2. Its unusual call frames, the vendor compiler, instruction traps, a table of useful routines | [MN103 CPU](hardware/mn103-cpu.md) |
| Image engine | where the job programs live, which bodies have which jobs, what the E-M5 III's own jobs 0–10 do, how to submit a job without hanging the camera | [image engine](hardware/image-engine.md) |
| ARM co-processor | Linux 4.4 for Wi-Fi, Bluetooth and an HHHR maths helper. The mailbox between the two sides, booting it from the SD card, a root shell | [ARM co-processor](hardware/arm-coprocessor.md) |
| Memory | memory per body, flash layout, frame pools, and the spare regions our code lives in | [memory map](hardware/memory-map.md) |
| Display | how menus are drawn over live view by a hardware engine, the display controller, where the live frame is | [graphics pipeline](hardware/graphics-pipeline.md), [display](hardware/display.md) |
| Stabiliser | a separate IS processor with a 57-command set, and what the E-M5 III already has for the OM-5's "IS Level" | [stabiliser](hardware/stabiliser.md) |
| Sensor, USB | raw frame layout and calibration. USB modes and why there is no hidden tethering | [sensor](hardware/sensor.md), [USB](hardware/usb.md) |
| Boot | the main program loads in ten sections in the background, which caused our intermittent boot failures until we added guards | [boot and sections](firmware/boot-and-sections.md) |
| Recovery | what the card updater checks, what it writes, which failures you can recover from, and the checks every build passes | [recovery](firmware/recovery.md) |
| Second and third cores | what CPU1 and CPU2 run, their memory, and how they start and hand work to each other | [CPU1 and CPU2](hardware/cpu1-cpu2.md) |
| Lens and shutter | how the body talks to the lens. The mechanical shutter driver and the shutter count | [lens communication](hardware/lens-communication.md), [shutter](hardware/shutter.md) |
| Exposure and colour | metering, the choice of shutter speed, ISO and aperture, and white balance | [exposure](firmware/exposure.md) |
| After the shot | the C++ layer that turns button presses into shooting actions. Development, JPEG, raw and EXIF. The movie encoder | [C++ shooting layer](firmware/cpp-shooting-layer.md), [still image back end](firmware/still-backend.md), [movie encoder](firmware/movie-stack.md) |
| Audio, service, printing | sound for movies and memos. The service data and fault records. Direct printing and print orders | [audio](hardware/audio.md), [maintenance](firmware/maintenance.md), [printing](features/printing.md) |
| Interrupts, timers, DMA | how the chip reacts to hardware events, keeps time and moves data without the processor | [interrupts, timers and DMA](hardware/interrupts-timers-dma.md) |
| Memory and storage | the NAND flash and DRAM controllers, error correction and bad blocks | [memory and storage](hardware/memory-and-storage.md) |
| Sensor link | the serial link that sets the sensor's modes and the receiver for its picture data | [sensor link](hardware/sensor-link.md) |
| Flash and playback | flash metering and the hot shoe. Playback and in-camera editing | [flash](hardware/flash.md), [playback](firmware/playback.md) |
| Face detection | the hardware face detector and how autofocus uses faces and eyes | [face and eye detection](features/face-detect.md) |
| Software | μITRON, the Rhapsody state-machine framework, tasks, debug shells. The shooting state machine. Settings and menu tables | [OS and framework](firmware/os-and-framework.md), [shooting sequencer](firmware/shooting-sequencer.md), [settings and menus](firmware/settings-and-menus.md) |

*Camera systems we studied, what we found and the page for each.*

## Features

| feature | result so far | page |
|---|---|---|
| Saved mod settings and native menu rows | new rows and a page that behave like the camera's own (Live ND Shooting after High Res Shot), with values kept by the camera's own settings save across power-off. Works on the camera | [saved settings and menu rows](features/saved-settings-and-menu-rows.md) |
| Card mod loader | loads small mods from the SD card at start-up, with an Off/On row per mod in a new Custom Menu letter "K. Mods". Nothing else is flashed for each mod. Works on the camera | [patching techniques](firmware/patching-techniques.md), [menu rows](features/saved-settings-and-menu-rows.md) |
| Focus stacking with any lens | done, working on the camera. 3–8 shots and any lens also work as card mods loaded by our mod loader, on the camera | [focus stacking](features/focus-stacking.md) |
| Live ND | Research closed. A full one-press Live ND shot worked in testing on the camera (ND2-ND16, frames at the set shutter speed, merged by the OM-5's own image-engine program), and the live view previewed the blur. The noise-reduction dark-frame pass works at low ISO, Live ND has rows in the camera's own shooting menu, and the restart at every power-on is solved | [Live ND](features/live-nd.md), [port layers](firmware/live-nd-port-layers.md) |
| Handheld High Res (HHHR) | Research closed. The OM-5's four image-engine programs load, the memory is free, and we can power the ARM helper ourselves. Whether the programs compose a correct picture here is unproven | [HHHR](features/hhhr.md) |
| USB webcam | the camera shows up as a webcam and streams its own picture (tests 1 and 2c). Live view would need the camera to stay in shooting mode on USB, so it's parked | [webcam](features/webcam.md) |
| Stock Wi-Fi debug shell | a settings file on the card turns on a debug network and shell, with no flashing. It works on our camera and is how we watch test runs live from a laptop | [Wi-Fi debug shell](features/wifi-debug-shell.md) |
| Starry Sky AF | absent on the E-M5 III, present on the OM-5. A first armed test build exists | [Starry Sky AF](features/starry-sky-af.md) |
| Colour / mono profiles (PEN-F style) | working on the camera in our test builds. Color and Mono Profile are selectable, with an on-camera editor and a side bar (colour wheel, HSL row, sharpness, contrast, per-profile tone curve, live histogram) whose edits reach photos and live view. A Free tone curve is in progress. The processing and saved settings were already in the E-M5 III firmware | [colour profiles](features/pen-f-profiles.md) |
| Movie 29:59 limit, OM-Log400 | the 30-minute limit is one value set when recording starts, and the 640-wide sizes already get 2 hours. Much of the log profile's plumbing is present | [movie](features/movie.md) |
| Live GND | Research closed. The OM-1 II has a real one, and the OM-5 does not. There is an untested design for the E-M5 III on top of Live ND | [Live GND](features/live-gnd.md) |
| Subject / face / eye AF | face options are portable. Deep-learning subject detection needs OM-1 hardware | [AF detect](features/af-detect.md) |
| Sync IS with Panasonic lenses | no simple flag. A split body/lens mode is the best bet | [Sync IS](features/sync-is-panasonic.md) |
| Other ideas | multi-frame noise reduction, bracketing, timelapse ramping, ideas from other makers | [ideas](features/ideas.md) |

*Features we have worked on and where each one stands.*

## Method

- Every absolute address in a build must appear in Olympus's own code. A script checks it. Every hook stays switched off
  unless the user asks for the feature, so the camera behaves as stock otherwise. See
  [patching techniques](firmware/patching-techniques.md).
- Each build passes a pre-flash check (container, boot path, section loading, address evidence, an emulated boot) before
  it goes near the camera. See [recovery](firmware/recovery.md).
- After every camera run we write down what happened before designing the next build. The mistakes that cost a flash
  are collected in [gotchas](reference/gotchas.md).
- We wrote a Ghidra processor module for the MN103, with decompiler support, and an unpack tool for the firmware
  container.

## Further reading

- [Guides](guides/README.md) follow one process at a time through the firmware.
- [Body comparison](bodies/comparison.md) compares the firmware of the bodies we studied.
- [Gotchas](reference/gotchas.md) collects the mistakes that cost a flash.

