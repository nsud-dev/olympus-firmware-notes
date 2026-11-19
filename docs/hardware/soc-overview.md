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

**OM-1 / OM-1 II DRAM (2026-11-19).** What the firmware shows and what it doesn't:

- **Four DRAM channels.** The OM-1 block0 has a bus-measurement debug command (`busmes`, strings at 0x600925fc-0x60092900
  on OM-1 1.9) that reports `max_latency_ch0` to `ch3`, `sum_latency_ch0` to `ch3`, and per-channel refresh, ZQ
  calibration and other counters in two groups (`refl`/`refh`/`ddc`/`zqcal` and the same with `_ch23`). Average
  bandwidth prints as `<<average:%5.2f(GByte/sec)>>`. None of these strings is in the E-M5 III, OM-5, OM-5 II or
  E-M1 III block0. [code]
- **Type: LPDDR4 or LPDDR4X is the likely fit.** Per-channel ZQ calibration counts, separate low/high refresh counters,
  "lossmw" (masked-write loss) and channels in pairs match LPDDR4-family dies, which have two 16-bit channels each.
  Nothing names the type: no `lpddr`/`ddr4`/`ddr5` string in any block, the A53 kernel or rootfs. [inferred]
- **Bus width: probably 64 bits** (four 16-bit channels). If the channels were 32-bit it would be 128 bits, which is
  unusual for a camera SoC. [inferred]
- **Size: still "about 2 GB" class**, from the buffer map (~1.5 GB of image buffers, main pool 0xb8000000-0xff124000).
  The firmware never states the size. [inferred]
- **Why the firmware can't settle it:** the DRAM controller is set up (timings, training) by the boot code in the flash
  boot area before block0, and that code is not in the update file, the same as on the E-M5 III. A board photo or the
  chip marking would answer type, size and width outright. [inferred]

OM-3: its firmware is not in the shared folder. OM System ships updates through OM Workspace rather than a direct
download link, so the update file would have to be captured the same way as the others. Public spec sheets say it
uses the same TruePic X processor as the OM-1, so it very likely has the same memory controller design. [inferred]

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

The OM-5, OM-5 II and E-M1 III contain deep-learning (DL) subject-detection control code as CPU2 tasks
(`MDET_DL_*_CPU2`), but it is dead there (no network executor or weights, no shipped feature). The OM-1 runs the network
on CPU3 plus a hardware DML block (CLKDML) with ~5 × 9.3 MB weights; the E-M5 III has a CPU2 but no CPU3, no DML block and
none of the MDET_DL code. Corrected 2026-11-19 (earlier wording said these bodies "run" it on CPU2). [code]
See [AF detect](../features/af-detect.md).

### How the cores talk to each other (2026-11-19)

Read off the E-M5 III 1.7 disassembly (static only). [code] unless marked. Source: block0 disassembly.

- **Lock bits at 0x8fe00000.** 64 one-bit locks in 8 bytes spaced 8 apart: lock n is bit n&7 of byte
  0x8fe00000 + 8×((n>>3)&7). A core takes a lock with `bset` (sets the bit and reports whether it was already set) and
  drops it with `bclr`. Primitives: try 0x600587d6 / release 0x600587e0; manager 0x600587e6(d0 = id, d1 mode: 0 try once,
  255 spin, logging after 8 M tries) and release 0x6005892d; the id's low 16 bits are the lock number. The kernel spins on
  bits 1 and 2 of byte 0 (0x6003870f / 0x6003871c, via 0x600368fa, 0x60031ade, 0x60031b67); 0x600587b3 takes lock 37
  (bit 5 of 0x8fe00020) with interrupts masked; the ISC code has its own copy (0x61206b6d, interrupts masked). That
  `bset` is atomic across cores is [inferred] (the design depends on it).
- **Doorbell interrupts.** Each core has a register block at **0x99200400 (CPU0), 0x99300400 (CPU1), 0x99b00400
  (CPU2)**. Writing a bit to +0x08 raises that core's inter-core interrupt; its handler reads +0x08 and acknowledges each
  bit by writing it to +0x0c. CPU0's handler 0x60053f11: bit 0 sets event flag u16 (0x60040f00) with `iset_flg`, bit 1
  and bit 2 hand messages on (0x60053d23 / 0x60054218), **bits 3/4/5 = a cross-core call from CPU0/CPU1/CPU2** (drains
  0x600573ee / 0x60057442 / 0x60057496). Each kernel's config block (three, 0x18c apart; pointers at 0x60041528,
  0x600416b4, 0x60041840) names a routine that writes 1 to another core's +0x10 (0x600300a1 for CPU0, 0x600300c3 for CPU1,
  0x600300e5 for CPU2); that this is the kernel's "re-check your ready tasks" kick is [inferred]. +0x00 takes a fault
  request (0x60058333, see [HHHR](../features/hhhr.md)). Unexpected interrupts print `!!Dummy IRQ from CPUn` (0x60054fa8).
- **Cross-core calls (`sys_callrequest`).** 0x6005730b(d0 = target core, a0 = function, a1 = argument) runs a function on
  another core. A 3×3 descriptor table at 0x60077700 (48 bytes per target, 16 per sender: write-index byte, read-index
  byte, queue base, doorbell bit) gives one 32-entry ring of {function, argument} per sender→target pair, in uncached
  RAM 0xa2623fdc-0xa26249f4. The caller masks interrupts (0x60069e11), checks for a full ring (logs an error and returns
  −1), stores the entry, advances the write index, reads 0x8ff00000 (probably to make sure the writes have landed,
  [inferred]), and writes its bit (0x08/0x10/0x20) to the target's +0x08 (table 0x60077790: 0x99200408, 0x99300408,
  0x99b00408). The target's handler calls `function(argument)` for each entry, in interrupt context. The system shell
  command `syscall` prints the nine rings (0x60057a1d). Task names `CPUCALL_CPU1/2` and `CPUCONN_CPU1/2` exist; their
  role is open.
- **Shared kernel data.** All three kernels keep their objects in memory every core can reach: a kernel call on an
  object of another core (id = core<<12 | index) indexes that core's kernel pointer at 0x8ff00004 + 4 × core directly,
  under the kernel lock (e.g. `set_flg` 0x60035b26). [code]
- **What runs where (task-name strings).** CPU1: movie encode audio/video (`MOV_ENC_*_CPU1`), audio bridge, image
  processing module (`IMGPRO_MDL_CPU1`), its own shells; CPU2: recording (`REC_MAIN_CPU2`, `REC_VIEW_CPU2`,
  `REC_PRE_V1_CPU2`), `IMGPRO_MDL_CPU2`, `MDET_EVENT_SEND_CPU2`, its own shells. [code] (strings); which code runs in
  those tasks is open.
- **Other bodies** (byte search 2026-11-19): the doorbell table {0x99200408, 0x99300408, 0x99b00408} is in OM-5 1.2
  (0x6007a7b8), E-M1 III 1.6 (0x6007d3a4) and OM-5 II 1.1 (0x6007b0cc); OM-1 1.9 has neither these addresses nor the
  0x8fe00000 lock area (four cores, different map); PEN-F 3.1 has the lock-area loads but not the doorbell table. [code]

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
