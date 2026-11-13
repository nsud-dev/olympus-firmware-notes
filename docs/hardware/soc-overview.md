# SoC overview

Every camera in this family is built around one main chip, a system on a chip (SoC) that holds several different
processors. This page explains what those processors are, which ones changed between camera models, and what that
means for moving features from a newer body to the E-M5 Mark III.

The short version: the E-M5 III, OM-5, OM-5 II and E-M1 III look like the same chip as far as the firmware can tell.
The OM-1 generation is genuinely new hardware.

Tags in square brackets say how we know something: **[code]** we read it in the firmware, **[camera]** we saw it on a
real E-M5 III, **[inferred]** it follows from the evidence but hasn't been traced or tested.

## "TruePic" is the whole chip

Olympus advertises each camera as having a "TruePic VIII", "TruePic IX" or "TruePic X" processor. That name covers the
whole SoC, not one core. Inside it there are several kinds of processor, and they were updated at different times.
[inferred, from firmware]

The main parts are:

- **Control CPUs.** They run the camera's main program: menus, buttons, the shooting sequence, settings. They are
  Panasonic MN103 cores, more precisely the AM33-2 variant. See [MN103 CPU](mn103-cpu.md).
- **ARM co-processor.** A separate ARM core running Linux, mainly for Wi-Fi and Bluetooth. See
  [ARM co-processor](arm-coprocessor.md).
- **Image engine.** Dedicated hardware that does the heavy pixel work by running small "job" programs. We often call it
  the DSP. See [Image engine](image-engine.md).
- **Newer blocks** that only the OM-1 generation has, such as a deep-learning accelerator.

How they compare across bodies:

| part | E-M5 III, OM-5, OM-5 II, E-M1 III | OM-1, OM-1 II (TruePic X) |
|---|---|---|
| Control CPUs | MN103 / AM33-2, three cores (CPU0 to CPU2) [code] | still MN103 with the same instruction set and tools, but four cores (CPU0 to CPU3) [code] |
| ARM co-processor | 32-bit Cortex-A9 running Linux 4.4 (5.10 on the OM-5 II) [code] | 64-bit Cortex-A53 with ARM Trusted Firmware (ATF), Linux 4.14 [code] |
| Image engine | the same generation on all four bodies; OM-5 jobs ran unchanged on an E-M5 III [camera] | new: none of its job programs match an older body [code] |
| Deep-learning block | none | a "DML" block (clock `CLKDML`), driven from CPU3 [code] |
| Other new blocks | none | detection blocks (`CLKDETA/B`), a GPU, PCIe, seven image pipelines (`CLKIMGA-G`) [code] |
| Clocks in the clock list | 38 (E-M5 III) | 94 [code] |

"Analyse OM-1 and OM-1 II firmware" (2026-11-05).

## The dc13 chip

Linux on the ARM side describes the hardware in a "device tree" (DTB), and that tree names the chip. On the E-M5 III,
E-M1 III and OM-5 it says `panasonic,dc13`; the E-M5 III and OM-5 even ship an identical device tree. The OM-5 II and
OM-1 say `ntcj,dc13` or just `ntcj`. That is probably Nuvoton Technology Japan, which took over Panasonic's chip
business, so it looks like a rename rather than new silicon. [code] for the strings, [inferred] for the company.

Olympus sells the E-M5 III as TruePic VIII and the OM-5 and E-M1 III as TruePic IX. From the firmware we can't tell them
apart as different silicon: [code]+[camera]

- the peripheral registers match (99.8% of register addresses in matched functions are identical),
- the image-engine resources match (all but 26 of about 27,000 chunks are identical),
- and the E-M5 III ran the OM-5's image jobs 11 and 12 on the camera.

Whether it is the same die renamed or a minor revision can't be settled from firmware. [inferred]

Addresses that come up on other pages: [code]

- Peripheral registers live at 0x98xxxxxx, 0x9Axxxxxx, 0x9Cxxxxxx and 0x8ff0xxxx. [code]
- The image engine's parameter window starts at 0x9d000000. [code]
- The USB controller is a Synopsys DWC3 at 0x98f0c000. [code]

## Memory

The main memory (DRAM) sits outside the SoC: the clock list includes a memory controller and a DDR PHY interface
(`CLKEMC`, `CLKDFI`). Whether it is a separate package or stacked on the SoC (package-on-package) would need a teardown.
[inferred]

The E-M5 III, OM-5 and OM-5 II have about 1 GB; the E-M1 III and OM-1 have about 2 GB. Details are on the
[memory map](memory-map.md) page.

Bigger memory chips would not be a simple swap. The firmware sets up the memory controller and lays out every buffer
for one size, so both would have to change. [inferred] The E-M1 III uses the same TruePic IX family with a ~2 GB layout,
so the controller very likely supports 2 GB, and its firmware would be the reference for such an upgrade (see
roadmap). [inferred]

## Why Olympus keeps the MN103

This is a guess, not evidence. The main program is more than 100,000 functions, built on the same operating system and
compiler for over a decade. Rewriting it for ARM would cost far more than adding hardware blocks around the old control
CPU, and the heavy work (image engine, JPEG, deep learning) already runs on dedicated blocks. [inferred]

For us this is good news: control logic taken from a newer body runs unchanged on the E-M5 III, because it is the same
CPU.

## Several MN103 cores

The control program refers to CPU0, CPU1 and CPU2 (for example `sys_callrequest_info[CPUx]`). The ARM is one more node
on the same internal messaging system, which Panasonic calls ISC ("Inter System Communication"). Most ARM programs
send their messages to `cpu=1`; the handheld high-res helper `hhhr` returns its results to `cpu=0`. [code]

Our hook code checks that the value at 0x8050 is 0 (`(0x8050) == 0`) to be sure it is running on core 0. [code]
(Live ND nd2.s)

The OM-5 and E-M1 III run their deep-learning (DL) subject detection "on CPU2" (tasks `MDET_DL_*_CPU2`). The E-M5 III
has a CPU2 but not that code. [code]

## Other processors on the board

- **Power sub-CPU** (battery, charger, power). The OM-1 and OM-1 II ship its firmware as block 5 of the update file
  (header address 0x08000000, type 0x107, strings `Scpu` and PBH). The E-M1 III also has a block 5 at 0x08000000. The
  E-M5 III has no block 5. [code]
- **Wi-Fi and Bluetooth module.** Cypress CYW43455 on the E-M5 III, OM-5, E-M1 III and OM-1; CYW43439 on the OM-5 II.
  [code]
- **Image stabiliser (IS) controller.** The sensor-shift stabiliser has its own IS sub-CPU on a serial link, driven by a
  part of the main program called the "bc" module (found 2026-11-06; before that it was unknown whether there was a
  separate MCU). See [stabiliser](stabiliser.md). [code]

See also: [MN103 CPU](mn103-cpu.md), [Image engine](image-engine.md), [ARM co-processor](arm-coprocessor.md).
