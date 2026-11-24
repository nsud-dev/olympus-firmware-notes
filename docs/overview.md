# Project overview

This project started with one small patch and grew into a close study of how the Olympus OM-D E-M5 Mark III's firmware
works. The aim is right to repair and keeping an older camera useful. The E-M5 III shares its chip and sensor with
newer bodies such as the OM-5, so features those bodies have could, in principle, run on it too.

This page is a tour of everything we've investigated, grouped by area, with a one-line result and a link to the page
with the detail. Dates are 2026 unless stated. Tags: **[camera]** tested on a real E-M5 III, **[code]** read in the
firmware, **[inferred]** follows from the evidence but not tested.

## Pace

This is a spare-time project. Progress comes in bursts and can be slow, because of family commitments,
and every change has to be tested by flashing a real camera. Several test builds are ready and waiting in the flash
queue, so some "built, not yet run" items below will stay that way for a while.

## Background

This project grew out of an earlier patch to the focus-stacking lens check, made with an old IDA Pro, re-signed and
flashed; it worked. That raised the question of what else could be enabled. From 19 October we cracked the
firmware container, rebuilt it byte for byte, and began comparing the E-M5 III with newer bodies. See
[focus stacking](features/focus-stacking.md) and [container format](firmware/container-format.md).

## Firmware studied

Eight firmware files from seven bodies: E-M5 III 1.7 (the target), OM-5 1.2 (the main donor), OM-5 II 1.1, E-M1 III 1.4
and 1.6, OM-1 1.9, OM-1 II 1.3 and PEN-F 3.1. They all share the same file format, control CPU and load address, which
is what makes moving code between them possible. [code] See [body comparison](bodies/comparison.md).

## Camera systems

For a start-to-finish read, the [guides](guides/README.md) follow one process at a time (taking a photo, boot, a
button press, live view, the operating system, how the cores talk) through the firmware. The table below is the
reference.

| area | what we found | page |
|---|---|---|
| The chip | TruePic is the whole SoC: MN103 control cores, an ARM core running Linux, and an image engine that runs small "job" programs. The E-M5 III and OM-5 look like the same silicon | [SoC overview](hardware/soc-overview.md) |
| Control CPU | Panasonic MN103/AM33-2; its unusual call frames, the vendor compiler, instruction traps, a table of useful routines | [MN103 CPU](hardware/mn103-cpu.md) |
| Image engine | where the job programs live, which bodies have which jobs, what the E-M5 III's own jobs 0-10 do, how to submit a job without hanging the camera | [image engine](hardware/image-engine.md) |
| ARM co-processor | Linux 4.4 for Wi-Fi, Bluetooth and an HHHR maths helper; the mailbox between the two sides; booting it from the SD card; a root shell | [ARM co-processor](hardware/arm-coprocessor.md) |
| Memory | memory per body, flash layout, frame pools, and the spare regions our code lives in | [memory map](hardware/memory-map.md) |
| Display | how menus are drawn over live view by a hardware engine, the display controller, where the live frame is | [graphics pipeline](hardware/graphics-pipeline.md), [display](hardware/display.md) |
| Stabiliser | a separate IS processor with a 57-command set, and what the E-M5 III already has for the OM-5's "IS Level" | [stabiliser](hardware/stabiliser.md) |
| Sensor, USB | raw frame layout and calibration; USB modes and why there is no hidden tethering | [sensor](hardware/sensor.md), [USB](hardware/usb.md) |
| Boot | the main program loads in ten sections in the background, which caused our intermittent boot failures until we added guards | [boot and sections](firmware/boot-and-sections.md) |
| Recovery | what the card updater checks, what it writes, which failures you can recover from, and the checks every build passes | [recovery](firmware/recovery.md) |
| Software | μITRON, the Rhapsody state-machine framework, tasks, debug shells; the shooting state machine; settings and menu tables | [OS and framework](firmware/os-and-framework.md), [shooting sequencer](firmware/shooting-sequencer.md), [settings and menus](firmware/settings-and-menus.md) |

## Features

| feature | result so far | page |
|---|---|---|
| Saved mod settings and native menu rows | new rows and a page that behave like the camera's own (Live ND Shooting after High Res Shot), with values kept by the camera's own settings save across power-off; works on the camera (2026-11-19) [camera] | [saved settings and menu rows](features/saved-settings-and-menu-rows.md) |
| Card mod loader | loads small mods from the SD card at start-up, with an Off/On row per mod in a new Custom Menu letter "K. Mods"; nothing else flashed for each mod; works on the camera [camera] (2026-11-22) | [patching techniques](firmware/patching-techniques.md), [menu rows](features/saved-settings-and-menu-rows.md) |
| Focus stacking with any lens | done, working on the camera; 3-8 shots and any lens also work as card mods loaded by our mod loader [camera] (2026-11-22) | [focus stacking](features/focus-stacking.md) |
| Live ND | a full one-press Live ND shot works on the camera (ND2-ND16, frames at the set shutter speed, merged by the OM-5's own image-engine program), and the live view previews the blur; the noise-reduction dark-frame pass works at low ISO, Live ND has rows in the camera's own shooting menu, and the restart at every power-on is solved [camera] (updated 2026-11-22) | [Live ND](features/live-nd.md), [port layers](firmware/live-nd-port-layers.md) |
| Handheld High Res (HHHR) | the OM-5's four image-engine programs load, the memory is free, and we can power the ARM helper ourselves; whether the programs compose a correct picture here is unproven [camera] | [HHHR](features/hhhr.md) |
| USB webcam | the camera shows up as a webcam and streams its own picture (tests 1 and 2c); live view would need the camera to stay in shooting mode on USB, so it's parked [camera] | [webcam](features/webcam.md) |
| Stock Wi-Fi debug shell | a settings file on the card turns on a debug network and shell, no flashing; works on our camera (2026-11-12) and is how we watch test runs live from a laptop [camera] | [Wi-Fi debug shell](features/wifi-debug-shell.md) |
| Starry Sky AF | absent on the E-M5 III, present on the OM-5; a first armed test build exists [code] | [Starry Sky AF](features/starry-sky-af.md) |
| Colour / mono profiles (PEN-F style) | working on the camera in our test builds: Color and Mono Profile selectable, an on-camera editor with a side bar (colour wheel, HSL row, sharpness, contrast, per-profile tone curve, live histogram) whose edits reach photos and live view [camera] 2026-11-20/22; a Free tone curve is in progress. The processing and saved settings were already in the E-M5 III [code] | [colour profiles](features/pen-f-profiles.md) |
| Movie 29:59 limit, OM-Log400 | the time limit is one constant; much of the log profile's plumbing is present [code] | [movie](features/movie.md) |
| Live GND | only the OM-1 II has a real one; a design for the E-M5 III on top of Live ND [inferred] | [Live GND](features/live-gnd.md) |
| Subject / face / eye AF | face options are portable; deep-learning subject detection needs OM-1 hardware [code] | [AF detect](features/af-detect.md) |
| Sync IS with Panasonic lenses | no simple flag; a split body/lens mode is the best bet [code] | [Sync IS](features/sync-is-panasonic.md) |
| Other ideas | multi-frame noise reduction, bracketing, timelapse ramping, ideas from other makers | [ideas](features/ideas.md) |

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

