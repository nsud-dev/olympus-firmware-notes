# Docs map

These notes describe how the Olympus OM-D E-M5 Mark III's firmware and hardware work, and what we have found while
trying to bring features from newer bodies (mainly the OM-5) to it. Start with the [overview](overview.md) for a
plain tour; each page below opens with a short introduction and explains its terms.

Conventions used throughout:

- Addresses are E-M5 III firmware 1.7 block0 addresses (base `0x60021020`) unless another body is named.
- Tags say how a fact is known: **[camera]** seen on a real camera, **[code]** read in the firmware, **[inferred]**
  follows from the evidence but not traced or tested.
- Unfamiliar names (TruePic, iseq, StlUhs, DigitalNd, ...) are in the [glossary](reference/glossary.md).

## Start here
| page | what |
|---|---|
| [Overview](overview.md) | everything investigated so far, with the state of each feature |
| [Body comparison](bodies/comparison.md) | E-M5 III, OM-5, OM-5 II, E-M1 III, OM-1, OM-1 II, PEN-F side by side |
| [Glossary](reference/glossary.md) | Olympus naming and our shorthand |
| [Gotchas](reference/gotchas.md) | things that cost a flash or a day |

## Hardware
| page | what |
|---|---|
| [SoC overview](hardware/soc-overview.md) | "TruePic" is the whole chip: MN103 control cores, ARM, image engine |
| [MN103 CPU](hardware/mn103-cpu.md) | instruction set, calling convention, call frames, the vendor compiler, useful routines |
| [Image engine](hardware/image-engine.md) | job programs, which body has which jobs, the parameter window, submitting a job safely |
| [ARM co-processor](hardware/arm-coprocessor.md) | Cortex-A9 Linux, Wi-Fi/Bluetooth, the mailbox, booting it from SD, a root shell |
| [Memory map](hardware/memory-map.md) | memory per body, flash layout, frame pools, spare space for our code |
| [Graphics pipeline](hardware/graphics-pipeline.md) | how menus are drawn over live view and sent to the screens |
| [Display and OSD](hardware/display.md) | display controller registers, histogram and peaking, the live-view frame pointer |
| [USB](hardware/usb.md) | controller, USB modes and product ids |
| [Stabiliser (IBIS)](hardware/stabiliser.md) | the IS sub-CPU, its command set, IS Level |
| [Sensor](hardware/sensor.md) | size, raw format, calibration, sensor modes |

## Firmware
| page | what |
|---|---|
| [Container format](firmware/container-format.md) | the .BIN file: blocks, obfuscation, checksum, compressed sections |
| [Boot and section loading](firmware/boot-and-sections.md) | background-loaded sections and why hooks need boot guards |
| [Recovery](firmware/recovery.md) | bootloops, what the card updater checks and writes, recovery steps, pre-flash checks |
| [OS and framework](firmware/os-and-framework.md) | μITRON, the Rhapsody framework, tasks, events, debug shells |
| [Shooting sequencer](firmware/shooting-sequencer.md) | the shooting state machine, routes, burst frames, sensor requests |
| [Settings and menus](firmware/settings-and-menus.md) | settings and properties, the saved-settings store, menu tables, card-file settings |
| [Patching techniques](firmware/patching-techniques.md) | what has worked on the camera, and the rules we follow |
| [Live ND port layers](firmware/live-nd-port-layers.md) | where ported Live ND code meets the camera's own code |

## Features
| page | what |
|---|---|
| [Live ND](features/live-nd.md) | digital ND filter: merged ND2-ND16 photos work; clean capture end still open |
| [Handheld High Res (HHHR)](features/hhhr.md) | the OM-5's handheld 50 MP mode: programs load, ARM helper powered, compose unproven |
| [USB webcam](features/webcam.md) | enumerates and streams its own picture; live view parked |
| [Focus stacking with any lens](features/focus-stacking.md) | the lens-list patch ([bytes](patches/focus-stacking-any-lens.md)) and the shot-count study |
| [Stock Wi-Fi debug shell](features/wifi-debug-shell.md) | a card file that starts a debug network and shell |
| [Starry Sky AF](features/starry-sky-af.md) | what it is made of and a first test build |
| [Colour / mono profiles](features/pen-f-profiles.md) | the PEN-F-style back end is already on the E-M5 III; the UI is missing |
| [Movie: 29:59 limit, OM-Log400](features/movie.md) | the limit constant and the log-profile study |
| [AF subject / face / eye detect](features/af-detect.md) | what is portable and what needs newer hardware |
| [Live GND](features/live-gnd.md) | how the OM-1 II does it and a design for the E-M5 III |
| [Sync IS with Panasonic lenses](features/sync-is-panasonic.md) | why there is no flag-only patch |
| [Ideas](features/ideas.md) | other feature ideas, with first verdicts |
