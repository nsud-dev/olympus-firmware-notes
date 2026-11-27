# Docs map

These notes describe how the Olympus OM-D E-M5 Mark III's firmware and hardware work. They come from a love of these
cameras. The more I learn about them, the more the engineering behind them surprises and impresses me. The hardware and
software are both remarkable pieces of engineering, and the people behind them deserve more praise than I can give.
Thank you for what must have been decades of careful, hard work. Exploring it has given me a real sense of wonder and
discovery.

**This is a research wiki.** It explains how the camera works and gives advice on making mods. It doesn't ship mods,
builds or decompiled code.

The notes also cover how far the camera's design is shared with newer bodies (mainly the OM-5). Start with the
[overview](overview.md) for a plain tour. Each page below opens with a short introduction and explains its terms.

Conventions used throughout:

- Addresses are E-M5 III firmware 1.7 block0 addresses (base `0x60021020`) unless another body is named.
- Tags say how a fact is known: **[camera]** seen on a real camera, **[code]** read in the firmware, **[inferred]**
  follows from the evidence but not traced or tested.
- Unfamiliar names (TruePic, iseq, StlUhs, DigitalNd, ...) are in the [glossary](reference/glossary.md).

## Start here
| page | what |
|---|---|
| [Guides](guides/README.md) | how processes on the camera work, explained without the reference detail; the place to learn |
| [Overview](overview.md) | everything investigated so far, with the state of each feature |
| [Body comparison](bodies/comparison.md) | E-M5 III, OM-5, OM-5 II, E-M1 III, OM-1, OM-1 II, PEN-F, E-M5 II, E-M5 Mark I side by side ([technical notes](bodies/comparison-technical.md)) |
| [E-M5 III family hardware](bodies/om5-family-hardware.md) | what the three bodies share, where they differ, and which parts of a program are model-specific |
| [I/O expander driver swap](bodies/expander-driver-swap.md) | report on one bug of our own from moving a driver between firmware versions, and the checks that catch it |
| [Settings map E-M5 III ↔ OM-5](bodies/settings-map-om5.md) | which settings the two cameras share, which differ, and how a saved settings image converts ([technical notes](bodies/settings-map-om5-technical.md)) |
| [Glossary](reference/glossary.md) | Olympus naming and our shorthand |
| [Gotchas](reference/gotchas.md) | things that cost a flash or a day ([technical notes](reference/gotchas-technical.md)) |
| [Failure patterns](reference/failure-patterns.md) | ways a changed firmware failed on the camera: symptom, cause and the check that catches it |

## Hardware
| page | what |
|---|---|
| [SoC overview](hardware/soc-overview.md) | "TruePic" is the whole chip: MN103 control cores, ARM, image engine ([technical notes](hardware/soc-overview-technical.md)) |
| [MN103 CPU](hardware/mn103-cpu.md) | instruction set, calling convention, call frames, the vendor compiler, useful routines |
| [Image engine](hardware/image-engine.md) | job programs, which body has which jobs, the parameter window, submitting a job safely ([technical notes](hardware/image-engine-technical.md)) |
| [ARM co-processor](hardware/arm-coprocessor.md) | Cortex-A9 Linux, Wi-Fi/Bluetooth, the mailbox, booting it from SD, a root shell ([technical notes](hardware/arm-coprocessor-technical.md)) |
| [Memory map](hardware/memory-map.md) | memory per body, flash layout, frame pools, spare space for our code |
| [Graphics pipeline](hardware/graphics-pipeline.md) | how menus are drawn over live view and sent to the screens |
| [Display and OSD](hardware/display.md) | display controller registers, histogram and peaking, the live-view frame pointer |
| [USB](hardware/usb.md) | controller, USB modes and product ids ([technical notes](hardware/usb-technical.md)) |
| [Stabiliser (IBIS)](hardware/stabiliser.md) | the IS sub-CPU, its command set, IS Level ([technical notes](hardware/stabiliser-technical.md)) |
| [Image-stabiliser controller](hardware/is-controller.md) | the stabiliser's own two-core chip: its program, the commands it handles, the OM-5 version ([technical notes](hardware/is-controller-technical.md)) |
| [Power and watchdog block](hardware/power-block.md) | the always-on part of the main chip: power-on causes, clock, alarm, watchdog ([technical notes](hardware/power-block-technical.md)) |
| [Sensor](hardware/sensor.md) | size, raw format, calibration, sensor modes ([technical notes](hardware/sensor-technical.md)) |

## Firmware
| page | what |
|---|---|
| [Container format](firmware/container-format.md) | the .BIN file: blocks, obfuscation, checksum, compressed sections |
| [Boot and section loading](firmware/boot-and-sections.md) | background-loaded sections and why hooks need boot guards |
| [Recovery](firmware/recovery.md) | bootloops, what the card updater checks and writes, recovery steps, pre-flash checks ([technical notes](firmware/recovery-technical.md)) |
| [OS and framework](firmware/os-and-framework.md) | μITRON, the Rhapsody framework, tasks, events, debug shells |
| [Shooting sequencer](firmware/shooting-sequencer.md) | the shooting state machine, routes, burst frames, sensor requests |
| [Settings and menus](firmware/settings-and-menus.md) | settings and properties, the saved-settings store, menu tables, card-file settings |
| [Patching techniques](firmware/patching-techniques.md) | what has worked on the camera, and the rules we follow |
| [Live ND port layers](firmware/live-nd-port-layers.md) | where ported Live ND code meets the camera's own code |

## Tools
| page | what |
|---|---|
| [om-emu additions](tools/om-emu-additions.md) | our ten patches to the om-emu emulator: GPU layer, crash checks, second and third CPUs ([technical notes](tools/om-emu-additions-technical.md)) |

## Features
| page | what |
|---|---|
| [Live ND](features/live-nd.md) | the digital ND filter from the OM-5, working on the camera ([technical notes](features/live-nd-technical.md)) |
| [Handheld High Res Shot](features/hhhr.md) | the OM-5's hand-held 50 MP mode, part-way ported ([technical notes](features/hhhr-technical.md)) |
| [USB webcam](features/webcam.md) | enumerates and streams its own picture; live view parked ([technical notes](features/webcam-technical.md)) |
| [Focus stacking](features/focus-stacking.md) | any lens, and 3 to 8 shots ([technical notes](features/focus-stacking-technical.md), [how the patch works](patches/focus-stacking-any-lens.md)) |
| [Card mods](features/card-mods.md) | load features from the SD card instead of flashing, with a menu row each |
| [Wi-Fi debug shell](features/wifi-debug-shell.md) | a card file that starts a debug network and shell ([technical notes](features/wifi-debug-shell-technical.md)) |
| [Starry Sky AF](features/starry-sky-af.md) | what it is made of and a first test build ([technical notes](features/starry-sky-af-technical.md)) |
| [Color and Monochrome Profiles](features/pen-f-profiles.md) | the PEN-F profiles with an on-camera editor ([technical notes](features/pen-f-profiles-technical.md)) |
| [Movie recording](features/movie.md) | the limit constant and the log-profile study ([technical notes](features/movie-technical.md)) |
| [Subject detection](features/af-detect.md) | what is portable and what needs newer hardware ([technical notes](features/af-detect-technical.md)) |
| [Live GND](features/live-gnd.md) | how the OM-1 II does it and a design for the E-M5 III ([technical notes](features/live-gnd-technical.md)) |
| [Sync IS with Panasonic lenses](features/sync-is-panasonic.md) | why there is no flag-only patch ([technical notes](features/sync-is-panasonic-technical.md)) |
| [Open gate video](features/open-gate.md) | could the camera record the whole 4:3 sensor area as video: sensor, pipeline and encoder limits ([technical notes](features/open-gate-technical.md)) |
| [Histogram](features/histogram.md) | where the histogram comes from, why it measures one channel at a time, live RGB and raw histograms |
| [Ideas](features/ideas.md) | other feature ideas, with first verdicts ([technical notes](features/ideas-technical.md)) |
