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

Most pages come as a pair. The light reading page explains how something works in plain words. Its technical reading
page, linked at the top, adds tables, addresses and footnoted sources.

Conventions used throughout:

- Addresses are E-M5 III firmware 1.7 block0 addresses (base `0x60021020`) unless another body is named.
- On technical pages, how a fact is known and when sits in a footnote. The footnote colour shows whether it was seen on
  a camera, read in the firmware or inferred.
- Unfamiliar names (TruePic, iseq, StlUhs, DigitalNd, ...) are in the [glossary](reference/glossary.md).

## Start here

- **Learn.** [Guides](guides/README.md) · [Overview](overview.md) · [Glossary](reference/glossary.md)
- **Lessons.** [Gotchas](reference/gotchas.md) · [Failure patterns](reference/failure-patterns.md)

## Bodies

- **Across the range.** [Body comparison](bodies/comparison.md) · [Firmware source lineage](bodies/lineage.md)
- **E-M5 III and OM-5.** [E-M5 III family hardware](bodies/om5-family-hardware.md) ·
  [Settings map E-M5 III ↔ OM-5](bodies/settings-map-om5.md) · [I/O expander driver swap](bodies/expander-driver-swap.md)

## Hardware

- **The main chip.** [SoC overview](hardware/soc-overview.md) · [MN103 control CPU](hardware/mn103-cpu.md) ·
  [CPU1 and CPU2](hardware/cpu1-cpu2.md) · [ARM co-processor](hardware/arm-coprocessor.md) ·
  [Caches and the access monitor](hardware/caches.md) · [Interrupts, timers and DMA](hardware/interrupts-timers-dma.md) ·
  [Power and watchdog block](hardware/power-block.md)
- **Memory.** [Memory map](hardware/memory-map.md) · [Memory and storage controllers](hardware/memory-and-storage.md)
- **From sensor to picture.** [Sensor and calibration](hardware/sensor.md) · [Sensor control link](hardware/sensor-link.md) ·
  [Image engine](hardware/image-engine.md) · [Motion search unit](hardware/motion-unit.md)
- **Screens and graphics.** [Display and live-view frames](hardware/display.md) ·
  [Display controller](hardware/vsc-display-controller.md) · [Graphics pipeline](hardware/graphics-pipeline.md) ·
  [Drawing on the GUI layers](hardware/osd-drawing.md) · [Vector GPU](hardware/c3d-gpu.md)
- **Around the body.** [Lens communication](hardware/lens-communication.md) · [Shutter](hardware/shutter.md) ·
  [Image stabiliser](hardware/stabiliser.md) · [Stabiliser controller](hardware/is-controller.md) ·
  [Flash and hot shoe](hardware/flash.md) · [Audio](hardware/audio.md) · [USB](hardware/usb.md) ·
  [Small body devices](hardware/small-devices.md)

## Firmware

- **Files and start-up.** [Firmware file format](firmware/container-format.md) ·
  [Boot and section loading](firmware/boot-and-sections.md) · [Recovery](firmware/recovery.md)
- **How the software is built.** [Operating system and framework](firmware/os-and-framework.md) ·
  [C++ shooting layer](firmware/cpp-shooting-layer.md) · [Shooting sequencer](firmware/shooting-sequencer.md) ·
  [Settings and menus](firmware/settings-and-menus.md) · [Maintenance layer](firmware/maintenance.md)
- **Pictures and movies.** [Exposure and white balance](firmware/exposure.md) ·
  [Still image back end](firmware/still-backend.md) · [Movie encoder stack](firmware/movie-stack.md) ·
  [Playback and in-camera editing](firmware/playback.md)
- **Changing it.** [Modifying the firmware](firmware/patching-techniques.md) ·
  [Live ND port layers](firmware/live-nd-port-layers.md)

## Features

- **Focus and detection.** [Autofocus and tracking AF](features/autofocus.md) ·
  [Subject tracking](features/subject-tracking.md) · [Face and eye detection](features/face-detect.md) ·
  [Face and subject AF options](features/af-detect.md) · [Subject detection research](features/subject-detection.md) ·
  [Network engine program](features/nn-engine-program.md) · [Model training](features/model-training.md) ·
  [Starry Sky AF](features/starry-sky-af.md)
- **From newer bodies.** [Live ND](features/live-nd.md) · [Live GND](features/live-gnd.md) ·
  [Handheld High Res Shot](features/hhhr.md) · [Color and Monochrome Profiles](features/pen-f-profiles.md)
- **Shooting and video.** [Focus stacking](features/focus-stacking.md) · [Movie recording](features/movie.md) ·
  [Open gate video](features/open-gate.md) · [Histogram](features/histogram.md) ·
  [Sync IS with Panasonic lenses](features/sync-is-panasonic.md)
- **Connections.** [Geotagging and the hot shoe](features/geotagging-and-hotshoe.md) · [Printing](features/printing.md) ·
  [USB webcam](features/webcam.md) · [Wi-Fi debug shell](features/wifi-debug-shell.md) ·
  [User shell commands](features/shell-commands.md)
- **Mods and ideas.** [Card mods](features/card-mods.md) ·
  [Saved settings and menu rows](features/saved-settings-and-menu-rows.md) · [Feature ideas](features/ideas.md) ·
  [Focus stacking with any lens](patches/focus-stacking-any-lens.md)

## Tools

- [om-emu additions](tools/om-emu-additions.md)
