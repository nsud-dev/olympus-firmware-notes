# What this project has looked into

This project started with one small patch and grew into a close study of how the Olympus OM-D E-M5 Mark III's firmware
works. The aim is right to repair and keeping an older camera useful: the E-M5 III shares its chip and sensor with
newer bodies such as the OM-5, so features those bodies have could, in principle, run on it too.

This page is a tour of everything we've investigated, grouped by area, with a one-line result and a link to the page
with the detail. Dates are 2026 unless stated. Tags: **[camera]** tested on a real E-M5 III, **[code]** read in the
firmware, **[inferred]** follows from the evidence but not tested.

## A note on pace

This is a spare-time project. Progress comes in bursts and can be slow, because of family commitments,
and every change has to be tested by flashing a real camera. Several test builds are ready and waiting in the flash
queue, so some "built, not yet run" items below will stay that way for a while.

## How it started

This project grew out of an earlier patch to the focus-stacking lens check, made with an old IDA Pro, re-signed and
flashed; it worked. That raised the question of what else could be enabled. From 19 October we cracked the
firmware container, rebuilt it byte for byte, and began comparing the E-M5 III with newer bodies. See
[focus stacking](features/focus-stacking.md) and [container format](firmware/container-format.md).

## Firmware we've taken apart

Eight firmware files from seven bodies: E-M5 III 1.7 (the target), OM-5 1.2 (the main donor), OM-5 II 1.1, E-M1 III 1.4
and 1.6, OM-1 1.9, OM-1 II 1.3 and PEN-F 3.1. They all share the same file format, control CPU and load address, which
is what makes moving code between them possible. [code] See [body comparison](bodies/comparison.md).

## How the camera works

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
| Focus stacking with any lens | done, working on the camera; a shot-count setting (3-8) is built and waiting for a test [camera] | [focus stacking](features/focus-stacking.md) |
| Live ND | merged ND2-ND16 photos work on the camera with frames at the set shutter speed; ending the capture cleanly (the one-press OM-5 behaviour) still hangs or resets [camera] | [Live ND](features/live-nd.md), [port layers](firmware/live-nd-port-layers.md) |
| Handheld High Res (HHHR) | the OM-5's four image-engine programs load, the memory is free, and we can power the ARM helper ourselves; whether the programs compose a correct picture here is unproven [camera] | [HHHR](features/hhhr.md) |
| USB webcam | the camera shows up as a webcam and streams its own picture (tests 1 and 2c); live view would need the camera to stay in shooting mode on USB, so it's parked [camera] | [webcam](features/webcam.md) |
| Stock Wi-Fi debug shell | a settings file on the card turns on a debug network and shell, no flashing; traced, not yet tried [code] | [Wi-Fi debug shell](features/wifi-debug-shell.md) |
| Starry Sky AF | absent on the E-M5 III, present on the OM-5; a first armed test build exists [code] | [Starry Sky AF](features/starry-sky-af.md) |
| Colour / mono profiles (PEN-F style) | the processing and saved settings are already in the E-M5 III; only the way to pick and edit them is missing [code] | [colour profiles](features/pen-f-profiles.md) |
| Movie 29:59 limit, OM-Log400 | the time limit is one constant; much of the log profile's plumbing is present [code] | [movie](features/movie.md) |
| Live GND | only the OM-1 II has a real one; a design for the E-M5 III on top of Live ND [inferred] | [Live GND](features/live-gnd.md) |
| Subject / face / eye AF | face options are portable; deep-learning subject detection needs OM-1 hardware [code] | [AF detect](features/af-detect.md) |
| Sync IS with Panasonic lenses | no simple flag; a split body/lens mode is the best bet [code] | [Sync IS](features/sync-is-panasonic.md) |
| Other ideas | multi-frame noise reduction, bracketing, timelapse ramping, ideas from other makers | [ideas](features/ideas.md) |

## How we work

- Every absolute address in a build must appear in Olympus's own code; a script checks it. Every hook stays switched off
  unless the user asks for the feature, so the camera behaves as stock otherwise. See
  [patching techniques](firmware/patching-techniques.md).
- Each build passes a pre-flash check (container, boot path, section loading, address evidence, an emulated boot) before
  it goes near the camera. See [recovery](firmware/recovery.md).
- After every camera run we write down what happened before designing the next build. The mistakes that cost a flash
  are collected in [gotchas](reference/gotchas.md).
- We wrote a Ghidra processor module for the MN103, with decompiler support, and an unpack/repack tool for the firmware
  container.

