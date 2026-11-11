# Docs map

Addresses are E-M5 III firmware 1.7 block0 VMAs (base `0x60021020`) unless a body is named.
Tags: **[camera]** seen on a camera, **[code]** read in firmware, **[inferred]** not traced or tested.

## Hardware
| page | what |
|---|---|
| [SoC overview](hardware/soc-overview.md) | "TruePic" = whole chip; MN103 control cores, ARM, image engine |
| [MN103 CPU](hardware/mn103-cpu.md) | ISA, calling convention, call frames, AM33-only traps, UDF ops, timers |
| [Image engine](hardware/image-engine.md) | job programs, parameter window, job records |
| [ARM co-processor](hardware/arm-coprocessor.md) | Cortex-A9 Linux, Wi-Fi/BT, mailbox |
| [Memory map](hardware/memory-map.md) | DRAM per body, buffer windows, frame pools, free code regions |
| [Display and OSD](hardware/display.md) | display controller, OSD draw primitives, histogram/peaking, LV frame pointer |
| [Graphics pipeline](hardware/graphics-pipeline.md) | GUI → OSD engine → planes/mix → panels |
| [USB](hardware/usb.md) | controller, PIDs, USB modes |
| [Stabiliser (IBIS)](hardware/stabiliser.md) | IS sub-CPU, host module, command set |
| [Sensor](hardware/sensor.md) | geometry, raw format, calibration table |

## Firmware
| page | what |
|---|---|
| [Container format](firmware/container-format.md) | .BIN blocks, obfuscation, checksum, LZ4 sections |
| [Boot and section loading](firmware/boot-and-sections.md) | boot stub, background-loaded sections, ready bits |
| [Recovery](firmware/recovery.md) | bootloops, flash map, card updater rules, safety rules for builds |
| [OS and framework](firmware/os-and-framework.md) | μITRON, Rhapsody OXF, tasks, events, debug console |
| [Shooting sequencer](firmware/shooting-sequencer.md) | state table, routes, event handlers, sensor requests |
| [Settings and menus](firmware/settings-and-menus.md) | setting→property tables, menu tables, card file API |
| [Patching techniques](firmware/patching-techniques.md) | byte patches, code caves, hooks, boot guards |

## Feature studies
| page | what |
|---|---|
| [Focus stacking with any lens](features/focus-stacking.md) | lens-list gate, 2-byte patch ([bytes](patches/focus-stacking-any-lens.md)), shot-count study |
| [Stock Wi-Fi debug shell](features/wifi-debug-shell.md) | card-file switch that starts a debug network + shell |
| [Sync IS with Panasonic lenses](features/sync-is-panasonic.md) | why there is no flag-only patch |
| [Movie: 29:59 limit, OM-Log400](features/movie.md) | limit site, log profile study |
| [AF subject / face / eye detect](features/af-detect.md) | what is portable, what needs newer hardware |
| [Starry Sky AF](features/starry-sky-af.md) | feasibility and plan |
| [Live GND](features/live-gnd.md) | how the OM-1 II does it |
| [Colour / mono profiles](features/pen-f-profiles.md) | back end present on E-M5 III, UI missing |
| [Ideas](features/ideas.md) | other image-processor ideas |

## Reference
| page | what |
|---|---|
| [Body comparison](bodies/comparison.md) | E-M5 III, OM-5, OM-5 II, E-M1 III, OM-1, OM-1 II, PEN-F |
| [Gotchas](reference/gotchas.md) | things that cost a flash or a day |
| [Glossary](reference/glossary.md) | Olympus naming (TruePic, iseq, StlUhs, DigitalNd, ...) |
