# SoC overview

## "TruePic" is the whole chip
"TruePic VIII / IX / X" is Olympus's marketing name for the whole image-processor SoC, not one core.
The chip has several kinds of processor, and they changed at different rates. [inferred, from firmware]

| part | E-M5 III / OM-5 / OM-5 II / E-M1 III | OM-1 / OM-1 II (TruePic X) |
|---|---|---|
| Control CPUs | Panasonic **MN103 / AM33-2**, CPU0-CPU2 [code] | still MN103, same ISA and tools, CPU0-**CPU3** [code] |
| ARM co-processor | 32-bit **Cortex-A9**, Linux 4.4 (5.10 on OM-5 II) [code] | 64-bit **Cortex-A53** + ATF, Linux 4.14 [code] |
| Image engine ("DSP", runs job programs) | same generation on all four bodies; OM-5 jobs ran on E-M5 III [camera] | **new**: no job program matches any older body [code] |
| Deep-learning block | none | **DML** block (clock `CLKDML`) driven from CPU3 [code] |
| Other new blocks | none | detection blocks (`CLKDETA/B`), GPU, PCIe, 7 image pipelines (`CLKIMGA-G`) [code] |
| Clock list size | 38 clocks (E-M5 III) | 94 clocks [code] |

"Analyse OM-1 and OM-1 II firmware" (2026-11-05).

## The dc13 SoC
- Device tree compatible string `panasonic,dc13` on E-M5 III, E-M1 III, OM-5 (identical DTB in E-M5 III and
  OM-5). The OM-5 II and OM-1 trees say `ntcj,dc13` / `ntcj`: probably Nuvoton Technology Japan, Panasonic's
  former chip business, so a rename, not new silicon. [code] for the strings, [inferred] for the company.
- E-M5 III (TruePic VIII) vs OM-5 / E-M1 III (TruePic IX): **not distinguishable as different silicon** from
  firmware. Same peripheral map (99.8% of register addresses in matched functions identical), same image-engine
  resources (all but 26 of ~27,000 chunks identical), and the E-M5 III ran OM-5 image jobs 11 and 12. [code]+[camera]
  Same die renamed vs minor revision can't be settled from firmware. [inferred]
- Peripheral I/O at 0x98xxxxxx, 0x9Axxxxxx, 0x9Cxxxxxx, 0x8ff0xxxx; image-engine parameter window 0x9d000000+.
  USB = Synopsys DWC3 at 0x98f0c000. [code]

## Memory
- DRAM is external to the SoC: the clock list has a memory controller and DDR PHY interface (`CLKEMC`, `CLKDFI`).
  Separate package vs package-on-package needs a teardown. [inferred] (the maintainer asked, 2026-11-05)
- 1 GB class on E-M5 III / OM-5 / OM-5 II, 2 GB class on E-M1 III / OM-1. Details: [memory map](memory-map.md).
  Fitting bigger chips would need a new memory controller setup and buffer map, not a swap. [inferred]
- The E-M1 III uses the same TruePic IX family with a ~2 GB map, so the controller very likely supports 2 GB; its firmware is
  the reference for a RAM upgrade (see roadmap). [inferred] (the maintainer asked, 2026-11-05)

## Why Olympus keeps the MN103
Guess, not evidence: the main program is >100,000 functions on the same OS and compiler for over a decade, so
porting it to ARM costs more than adding hardware blocks around the control CPU. Heavy work runs on dedicated
blocks (image engine, JPEG, DML). Good for us: ported control logic runs unchanged across bodies. [inferred]

## Multiple MN103 cores
- MN103 code refers to CPU0/CPU1/CPU2 (`sys_callrequest_info[CPUx]`); the ARM is a further ISC node.
  Most ARM daemons address `cpu=1`; `hhhr` returns results to `cpu=0`. [code]
- Our hook code checks `(0x8050) == 0` to be sure it's on core 0. [code] (Live ND nd2.s)
- OM-5 / E-M1 III run DL subject-detect tasks "on CPU2" (`MDET_DL_*_CPU2`); E-M5 III has a CPU2 but not that code. [code]

## Other on-board processors
- **Sub-CPU** (battery/charger/power): OM-1 / OM-1 II ship its firmware as block 5 (header addr 0x08000000, type
  0x107, strings `Scpu`, PBH). E-M1 III also has a block 5 at 0x08000000. E-M5 III has no block 5. [code]
- **Wi-Fi/BT module**: Cypress CYW43455 on E-M5 III, OM-5, E-M1 III, OM-1; CYW43439 on OM-5 II. [code]
- **IS (sensor shift)** control: ~~whether it is a separate MCU is unknown~~ 2026-11-06: a **separate IS sub-CPU** on a serial link, driven by the MN103 "bc" module; see [stabiliser](stabiliser.md). [code]

See also: [MN103 CPU](mn103-cpu.md), [Image engine](image-engine.md), [ARM co-processor](arm-coprocessor.md).
