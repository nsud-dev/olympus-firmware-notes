# SoC overview: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [SoC overview](soc-overview.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

Every camera in this family is built around one main chip, a system on a chip (SoC) that holds several different
processors. This page explains what those processors are, which ones changed between camera models, and what that
means for moving features from a newer body to the E-M5 Mark III.

The E-M5 III, OM-5, OM-5 II and E-M1 III look like the same chip as far as the firmware can tell. The OM-1 generation
is genuinely new hardware. The page also covers the older chips, the two-chip E-M1X, the main memory, how the control
cores talk to each other and the other processors on the board.

Addresses are E-M5 III 1.7 block0 addresses (base `0x60021020`) unless a body is named. They are collected in the
[Address reference](#address-reference).

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred.

## TruePic and the chip's parts

Olympus advertises each camera as having a "TruePic VIII", "TruePic IX" or "TruePic X" processor. That name covers the
whole SoC, not one core. Inside it there are several kinds of processor, and they were updated at different
times.[^inf1]

The main parts are:

- **Control CPUs.** They run the camera's main program, which covers menus, buttons, the shooting sequence and
  settings. They are Panasonic MN103 cores, more precisely the AM33-2 variant. See [MN103 CPU](mn103-cpu.md).
- **ARM co-processor.** A separate ARM core running Linux, mainly for Wi-Fi and Bluetooth. See
  [ARM co-processor](arm-coprocessor.md).
- **Image engine.** Dedicated hardware that does the heavy pixel work by running small "job" programs. Our older notes
  call it the DSP. See [Image engine](image-engine.md).
- **Newer blocks** that only the OM-1 generation has, such as a deep-learning accelerator.

The parts compare across bodies as follows.

| part | E-M5 III, OM-5, OM-5 II, E-M1 III | OM-1, OM-1 II, OM-3 (TruePic X) |
|---|---|---|
| control CPUs | MN103 / AM33-2, three cores (CPU0 to CPU2)[^fw1] | still MN103 with the same instruction set and tools, but four cores (CPU0 to CPU3)[^fw1] |
| ARM co-processor | 32-bit Cortex-A9 running Linux 4.4 (5.10 on the OM-5 II)[^fw1] | 64-bit Cortex-A53 with ARM Trusted Firmware (ATF), Linux 4.14[^fw1] |
| image engine | the same generation on all four bodies. OM-5 jobs ran unchanged on an E-M5 III.[^cam1] | new. None of its job programs match an older body.[^fw1] |
| deep-learning block | none | a "DML" block (clock `CLKDML`), driven from CPU3[^fw1] |
| other new blocks | none | detection blocks (`CLKDETA/B`), a GPU, PCIe, seven image pipelines (`CLKIMGA-G`)[^fw1] |
| clocks in the clock list | 38 (E-M5 III) | 94[^fw1] |

*The chip's parts in the two current generations. Read in each body's firmware.*

## The dc13 chip

Linux on the ARM side describes the hardware in a "device tree" (DTB), and that tree names the chip. On the E-M5 III,
E-M1 III and OM-5 it says `panasonic,dc13`. The E-M5 III and OM-5 even ship an identical device tree. The OM-5 II and
OM-1 say `ntcj,dc13` or just `ntcj`.[^fw2] That is probably Nuvoton Technology Japan, which took over Panasonic's chip
business, so it looks like a rename rather than new silicon.[^inf2]

Olympus sells the E-M5 III as TruePic VIII and the OM-5 and E-M1 III as TruePic IX. From the firmware we can't tell
them apart as different silicon.[^fw2][^cam1]

- The peripheral registers match. 99.8% of register addresses in matched functions are identical.
- The image-engine resources match. All but 26 of about 27,000 chunks are identical.
- The E-M5 III ran the OM-5's image jobs 11 and 12 on the camera.

Whether it is the same die renamed or a minor revision can't be settled from firmware.[^inf2]

Some chip addresses come up on many other pages. They are the four peripheral register regions, the start of the image
engine's parameter window and the USB controller, a Synopsys DWC3.[^fw2] All are in the
[Address reference](#address-reference).

## Older generations: TruePic VII and VI

The E-M5 II 4.1, PEN-F 3.1 and E-M5 (Mark I) 2.3 firmware give the comparison below.[^fw3][^inf3]

| | E-M5 III (VIII) | E-M5 II, PEN-F (VII) | E-M5 Mark I (VI) |
|---|---|---|---|
| control CPU | MN103 / AM33-2, CPU0-2 | same family, CPU0-2 | MN103 family, CPU0-1 named |
| peripheral register constants shared with the E-M5 III | (OM-5: 94%) | 21-22% (E-M5 II vs PEN-F: 98%) | 5% |
| image engine | 320-bit microcode jobs | same program format, older job set | no programs of that format |
| ARM co-processor | Cortex-A9, Linux | none | none |
| Wi-Fi | CYW43455 via the ARM | BCM43362 driven by the MN103 over SDIO | none |
| GPU | DMP, OpenVG | DMP, OpenVG | a GPU, no OpenVG |

*Three chip generations. Measured in each body's firmware. The chip reading is inferred.*

So the E-M5 II and PEN-F are one chip, a different one from the E-M5 III's, and the E-M5 Mark I is a third.[^inf3] The
same address regions hold peripherals on all of them, but which registers sit where mostly changed.[^fw3] The regions
are in the [Address reference](#address-reference).

See also: [older bodies](../bodies/comparison-technical.md#older-bodies-e-m5-ii-and-e-m5-mark-i).

## E-M1 II and E-M1X: the same chip, one or two of them

Both files came from OM's update server.

- **Same chip as the E-M5 III.** The block0 clock-name list of the E-M1 II and the E-M1X is the E-M5 III's exactly,
  78 of 78 names, including the Cortex-A9 clocks. The OM-5 has 77 of them and the PEN-F has 4.[^fw4] So the 2016
  "TruePic VIII" of the E-M1 II is the same chip family (dc13) as the E-M5 III's.[^inf4]
- **E-M1 II leaves the ARM unused.** It has the A9 clocks but no ARM Linux, no device tree and no Cortex-A9 image. Its
  Wi-Fi is a BCM43362 driven by the MN103, as on the PEN-F.[^fw4]
- **E-M1X has two chips.** Block7 (type `0x111`, 4 MB) is a full MN103 program for the second chip. It greets with
  "Hello DC13's Slave System" and has CPU0-CPU2 and its own `iseq` and image-processing code. Block0 powers it on and
  loads it (`sys_sasic_slave_on_*`, `load arm itron slave`). So the E-M1X has six MN103 cores, two image engines and
  two A9s. Its device tree is `panasonic,dc13`, a different build from the E-M5 III's.[^fw4]
- **Where E-M1X subject detection runs.** Block0 sends images to the second chip (`MDET_DL_SND_IMG`,
  `MDET_DL_RCV_SBJCT`, `deep_learning_sasic`, `RS_USE_SLAVE_SUBJECT`). The second chip's program has `DL_START`,
  `DL_END`, `DSP:%d_DL_CB` and `GET_DL_DTCT_RES`.[^fw4] So the network appears to run as image-engine work on the
  second chip, with its CPUs only driving it.[^inf4] Block0 has a debug command "load learning data". Block5 (type
  `0x10f`, about 6.6 MB of data, entropy about 5.2) is the likely learning data.[^fw4][^inf4] The subjects are motor
  sports, airplane, train and bird. The second chip also runs handheld high res (`imgpro_mdl_handheld_hr_*`).[^fw4]
- **What this means.** One dc13 image engine can run a subject-detection network, but the E-M1X gave it a whole second
  chip. On the E-M5 III that engine is shared with live view and capture, so whether a network fits alongside them is
  open. The next section answers the format and block5 questions.[^inf4]

### E-M1X subject detection: the second chip's job bank and network

The second chip's program (block7) runs at its own load address, given in the
[Address reference](#address-reference).

- **Block5 is the second chip's job bank.** It starts with the same 16-byte table rows as a block2 bank and holds 10
  entries. Entry 3 is the memcpy job, byte-identical to job 8 of every TruePic IX body. Entries 5 and 6 are the E-M1X's
  own handheld high res jobs 14 and 15. Entries 7 and 8 are its own versions of jobs 16 and 17. Entry 4 (432 KB) is a
  new job program, the network job. Entries 0, 1, 2 and 9 are four data blocks of 1,397,760 bytes each.[^fw4]
- **The four data blocks are the network weights.** They are not job code. They read as little-endian 16-bit values,
  about 0.7 million per block, and no two blocks share a line. The firmware loads all four back to back into the second
  chip's memory at start-up (trace name "load learning data").[^fw4] One block per subject type is the likely reading,
  since the E-M1X detects four kinds of subject.[^inf4]
- **The network job uses the TruePic IX program format.** It has 6,759 instructions in the 320-bit format, with the
  same start sequence as every TruePic IX job. 98% of its instructions use only field values that the 93 known
  E-M5 III, OM-5, OM-5 II, E-M1 III and E-M1X jobs also use. The rest use a few values seen nowhere else, among them
  one control operation (69) found only in this job.[^fw4] Whether the E-M5 III's engine runs those few is untested.
  Both chips are dc13 and the E-M1X main chip has the E-M5 III's jobs 0-10 byte for byte, so the same engine revision
  is likely.[^inf4]
- **The second chip drives the engine the same way.** Its engine driver uses the E-M5 III's engine registers, the
  parameter window plus slot and the program register. The network job's setter copies defaults from the end of the
  job program, writes 12 parameter words and starts the program, like the E-M5 III setters.[^fw4]
- **How the two chips work together.** The main chip sends each image over the chip-to-chip link (trace names
  `CCI:%d_WRITE`, `SEND_IMG`). The second chip queues it in one of two image queues, runs the network job, and decodes
  the result into boxes with a position, size and trust score (`us_isp_sort_x/y/size_w/size_h/trust`). Commands and
  results go back over a serial (UART) line (`UART_SEND_SBJ_COMP`).[^fw4]

## Memory

The main memory (DRAM) sits outside the SoC. The clock list includes a memory controller and a DDR PHY interface
(`CLKEMC`, `CLKDFI`). Whether it is a separate package or stacked on the SoC (package-on-package) would need a
teardown.[^inf5]

The E-M5 III, OM-5 and OM-5 II have about 1 GB. The E-M1 III and OM-1 have about 2 GB. Details are on the
[memory map](memory-map.md) page.

Bigger memory chips would not be a simple swap. The firmware sets up the memory controller and lays out every buffer
for one size, so both would have to change.[^inf5] The E-M1 III uses the same TruePic IX family with a ~2 GB layout. So
the controller very likely supports 2 GB, and its firmware would be the reference for such an upgrade.[^inf5] See also:
roadmap.

### OM-1 and OM-1 II memory

The firmware shows some things about the OM-1 memory and leaves others open.

- **Four DRAM channels.** The OM-1 block0 has a bus-measurement debug command (`busmes`). It reports
  `max_latency_ch0` to `ch3`, `sum_latency_ch0` to `ch3`, and per-channel refresh, ZQ calibration and other counters in
  two groups (`refl`/`refh`/`ddc`/`zqcal` and the same with `_ch23`). Average bandwidth prints as
  `<<average:%5.2f(GByte/sec)>>`. None of these strings is in the E-M5 III, OM-5, OM-5 II or E-M1 III block0.[^fw5]
  The OM-1 II block0 has the same set.
- **Type: LPDDR4 or LPDDR4X is the likely fit.** Per-channel ZQ calibration counts, separate low and high refresh
  counters, "lossmw" (masked-write loss) and channels in pairs match LPDDR4-family dies, which have two 16-bit channels
  each. Nothing names the type. No `lpddr`, `ddr4` or `ddr5` string is in any block, the A53 kernel or the root file
  system.[^inf6]
- **Bus width: probably 64 bits** (four 16-bit channels). If the channels were 32-bit it would be 128 bits, which is
  unusual for a camera SoC.[^inf6]
- **Size: still "about 2 GB" class**, from the buffer map (~1.5 GB of image buffers in the main pool). The firmware
  never states the size.[^inf6]
- **Why the firmware can't settle it.** The DRAM controller is set up (timings, training) by the boot code in the flash
  boot area before block0. That code is not in the update file, the same as on the E-M5 III. A board photo or the chip
  marking would answer type, size and width outright.[^inf6]

The OM-3 1.1 firmware has the same `busmes` four-channel counters and the same buffer-pool end constant as the
OM-1 II.[^fw6] So it has the same memory controller design and the same ~2 GB class.[^inf4] It also has four MN103
cores, the DML block and two Cortex-A53 cores. See also: [body comparison](../bodies/comparison-technical.md#om-3-11).

## Staying with the MN103

This is a guess, not evidence. The main program is more than 100,000 functions, built on the same operating system and
compiler for over a decade. Rewriting it for ARM would cost far more than adding hardware blocks around the old control
CPU. The heavy work (image engine, JPEG, deep learning) already runs on dedicated blocks.[^inf7]

For us this is good news. Control logic taken from a newer body runs unchanged on the E-M5 III, because it is the same
CPU.

## Several MN103 cores

The control program refers to CPU0, CPU1 and CPU2, for example in `sys_callrequest_info[CPUx]`. The ARM is one more
node on the same internal messaging system, which Panasonic calls ISC ("Inter System Communication"). Most ARM programs
send their messages to `cpu=1`. The handheld high-res helper `hhhr` returns its results to `cpu=0`.[^fw7]

Our hook code checks that the core number register reads 0, to be sure it is running on core 0.[^fw7]

The OM-5, OM-5 II and E-M1 III contain deep-learning (DL) subject-detection control code as CPU2 tasks
(`MDET_DL_*_CPU2`). It is dead there. They have no network executor or weights, and no shipped feature uses it. The
OM-1 runs the network on CPU3 plus a hardware DML block (`CLKDML`) with ~5 × 9.3 MB weights. The E-M5 III has a CPU2
but no CPU3, no DML block and none of the `MDET_DL` code.[^fix1] See also: [Face and subject AF options](../features/af-detect.md).

### Communication between cores

This section was read off the E-M5 III 1.7 disassembly, statically.[^fw8] The functions, tables and registers it names
are in the [Address reference](#cores).

**Lock bits.** There are 64 one-bit locks in 8 bytes spaced 8 apart in the lock area. Lock n is bit `n & 7` of byte
`8 × ((n >> 3) & 7)` from the start of the area.[^fw8]

- A core takes a lock with `bset`, which sets the bit and reports whether it was already set. It drops the lock with
  `bclr`.[^fw8]
- There are try and release primitives. A lock manager takes d0 = id and d1 = mode (0 try once, 255 spin, logging
  after 8 M tries), with its own release. The id's low 16 bits are the lock number.[^fw8]
- The kernel spins on bits 1 and 2 of byte 0. One routine takes lock 37 (bit 5 of the fifth byte) with interrupts
  masked. The ISC code has its own copy of the lock code, also with interrupts masked.[^fw8]
- That `bset` is atomic across cores is inferred, because the design depends on it.[^inf8]

**Doorbell interrupts.** Each core has a register block. Writing a bit to `+0x08` raises that core's inter-core
interrupt. Its handler reads `+0x08` and acknowledges each bit by writing it to `+0x0c`.[^fw8]

- In CPU0's handler, bit 0 sets event flag u16 with `iset_flg`, and bits 1 and 2 hand messages on.[^fw8] Bit 0 wakes
  the remote-kernel-call server CPUCONN, bit 1 is the reply and bit 2 serves the inter-core message slots.[^fw9] See
  also: [CPU1 and CPU2](cpu1-cpu2-technical.md#how-they-talk-to-cpu0).
- Bits 3, 4 and 5 are a cross-core call from CPU0, CPU1 and CPU2. Each has its own drain routine.[^fw8]
- Each kernel has a config block. There are three, `0x18c` apart, and a field at `+0x13c` of each points to a routine
  that writes 1 to another core's `+0x10`.[^fw8] That this is the kernel's "re-check your ready tasks" kick is
  inferred.[^inf8]
- `+0x00` takes a fault request, see [HHHR](../features/hhhr.md).[^fw8]
- Unexpected interrupts print `!!Dummy IRQ from CPUn`.[^fw8]

**Cross-core calls (`sys_callrequest`).** One function runs a function on another core. It takes d0 = target core,
a0 = function and a1 = argument.[^fw8]

- A 3 × 3 descriptor table has 48 bytes per target and 16 per sender. Each entry holds a write-index byte, a read-index
  byte, a queue base and a doorbell bit. It gives one 32-entry ring of {function, argument} per sender → target pair,
  in uncached RAM.[^fw8][^fix2]
- The caller masks interrupts and checks for a full ring. A full ring logs an error and returns −1. Otherwise the
  caller stores the entry and advances the write index.[^fw8]
- It then reads the shared block, probably to make sure the writes have landed.[^inf8] Finally it writes its bit
  (`0x08`, `0x10` or `0x20`) to the target's `+0x08`, through a table of the three doorbell addresses.[^fw8]
- The target's handler calls `function(argument)` for each entry, in interrupt context.[^fw8]
- The system shell command `syscall` prints the nine rings.[^fw8]
- Tasks `CPUCALL_CPU1/2` and `CPUCONN_CPU1/2` exist. CPUCONN serves remote kernel calls, and CPUCALL runs task-level
  cross-core calls.[^fw9] See also: [CPU1 and CPU2](cpu1-cpu2-technical.md#how-they-talk-to-cpu0).

**Shared kernel data.** All three kernels keep their objects in memory every core can reach. A kernel call on an object
of another core (id = `core << 12 | index`) indexes that core's kernel pointer in the shared block directly, under the
kernel lock. `set_flg` is an example.[^fw8]

**What runs where.** The CPU1 and CPU2 static task tables hold 73 and 29 tasks.[^fw9]

- CPU1 runs the image-engine job workers DSP0 and DSP1, Wi-Fi, BLE, PTP-IP, ARM power, c3d and EGL, the movie file
  writer and Avfw encoder threads, and second-CPU AF.[^fw9]
- CPU2 runs the movie recorder, still record helpers (the record pipeline is CPU0), motion and scene detection, and
  audio.[^fw9]
- Both load the block0 sections.[^fw9]
- Several names read as task names before (`MOV_ENC_*_CPU1`, `IMGPRO_MDL_CPUn`) are other kernel objects.[^fw9]

The full tables are on [CPU1 and CPU2](cpu1-cpu2-technical.md).

**Other bodies.** The doorbell table is in the OM-5 1.2, E-M1 III 1.6 and OM-5 II 1.1. OM-1 1.9 has neither these
addresses nor the lock area, with four cores and a different map. PEN-F 3.1 has the lock-area loads but not the
doorbell table.[^fw8]

## Other processors on the board

- **Power sub-CPU** (battery, charger, power). The OM-1 and OM-1 II ship its firmware as block 5 of the update file
  (type `0x107`, strings `Scpu` and PBH). The E-M1 III also has a block 5 at the same address. The E-M5 III has no
  block 5.[^fw2] The E-M5 III and OM-5 have no power microcontroller at all. Clock, wake, power-off and watchdog live in
  an always-on block of the main chip, which all four bodies share.[^fw10][^inf9] See also:
  [power block](power-block-technical.md).
- **Wi-Fi and Bluetooth module.** Cypress CYW43455 on the E-M5 III, OM-5, E-M1 III and OM-1. CYW43439 on the
  OM-5 II.[^fw2]
- **Image stabiliser (IS) controller.** The sensor-shift stabiliser has its own IS sub-CPU on a serial link, driven by a
  part of the main program called the "bc" module.[^fw11] See also: [stabiliser](stabiliser.md).

See also: [MN103 CPU](mn103-cpu.md), [Image engine](image-engine.md), [ARM co-processor](arm-coprocessor.md).

## Open questions

- E-M1X detection network: its input size, how often it runs, and how long one pass takes.
- Whether the E-M5 III's engine runs the network job's few unique operations.
- The OM-1 memory's type, size and bus width, which a board photo or chip marking would settle.
- Whether the E-M5 III's main memory is a separate package or stacked on the SoC.

## Address reference

E-M5 III 1.7 block0 addresses unless a body is named.

### Chip

| item | address |
|---|---|
| peripheral register regions | `0x98xxxxxx`, `0x9axxxxxx`, `0x9cxxxxxx`, `0x8ff0xxxx` |
| peripheral regions shared with the TruePic VII and VI chips | `0x98` to `0x9f` and `0x8ff0` (top address bits) |
| image engine parameter window | `0x9d000000` |
| image engine program register | `0x9d200010` |
| USB controller (Synopsys DWC3) | `0x98f0c000` |
| always-on power block | `0x98e00000` |
| power microcontroller firmware, block 5 header address (OM-1, OM-1 II, E-M1 III) | `0x08000000` |

*Chip-wide addresses.*

### Other bodies

| item | address |
|---|---|
| E-M1X block7 load address (header) | `0x90000000` |
| E-M1X second chip's program base | `0x60000000` |
| OM-1 1.9 `busmes` strings | `0x600925fc` to `0x60092900` |
| OM-1 main buffer pool | `0xb8000000` to `0xff124000` |
| OM-3 1.1 and OM-1 II buffer-pool end constant | `0xff124000` |

*Addresses in other bodies.*

### Cores

| item | address |
|---|---|
| core number register | `0x8050` |
| lock area | `0x8fe00000` (lock n: bit `n & 7` of byte `0x8fe00000 + 8 × ((n >> 3) & 7)`) |
| lock try, release | `0x600587d6`, `0x600587e0` |
| lock manager, release | `0x600587e6`, `0x6005892d` |
| kernel spin on byte 0 bits 1 and 2 | `0x6003870f`, `0x6003871c`, via `0x600368fa`, `0x60031ade`, `0x60031b67` |
| lock 37 (bit 5 of `0x8fe00020`), interrupts masked | `0x600587b3` |
| ISC copy of the lock code | `0x61206b6d` |
| doorbell register blocks CPU0, CPU1, CPU2 | `0x99200400`, `0x99300400`, `0x99b00400` |
| CPU0 inter-core handler | `0x60053f11` |
| event flag u16 (bit 0) | `0x60040f00` |
| message hand-on, bits 1 and 2 | `0x60053d23`, `0x60054218` |
| cross-core call drains, from CPU0, CPU1, CPU2 | `0x600573ee`, `0x60057442`, `0x60057496` |
| kernel config blocks | `0x600413ec`, `0x60041578`, `0x60041704` |
| their `+0x13c` pointer fields | `0x60041528`, `0x600416b4`, `0x60041840` |
| "re-check" kick routines for CPU0, CPU1, CPU2 | `0x600300a1`, `0x600300c3`, `0x600300e5` |
| fault request writer (`+0x00`) | `0x60058333` |
| dummy IRQ message | `0x60054fa8` |
| `sys_callrequest` | `0x6005730b` |
| 3 × 3 descriptor table | `0x60077700` |
| call rings (uncached RAM) | `0xa2623fdc` to `0xa26248f2` |
| interrupt mask | `0x60069e11` |
| shared block read before the doorbell | `0x8ff00000` |
| doorbell address table | `0x60077790`: `0x99200408`, `0x99300408`, `0x99b00408` |
| `syscall` shell command | `0x60057a1d` |
| kernel pointers per core | `0x8ff00004 + 4 × core` |
| `set_flg` | `0x60035b26` |
| CPU1 task table (73 tasks) | `0x6003c460` |
| CPU2 task table (29 tasks) | `0x6003d544` |
| doorbell table in OM-5 1.2, E-M1 III 1.6, OM-5 II 1.1 | `0x6007a7b8`, `0x6007d3a4`, `0x6007b0cc` |

*Core communication: locks, doorbells, cross-core calls and kernel data.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware of each body, 2026-11-05.
[^cam1]: Seen on our E-M5 III, which ran the OM-5's image jobs 11 and 12.
[^inf1]: Inferred from the firmware, 2026-11-05.
[^fw2]: Read in the firmware.
[^inf2]: Inferred.
[^fw3]: Measured in the E-M5 II 4.1, PEN-F 3.1 and E-M5 (Mark I) 2.3 firmware, 2026-11-21.
[^inf3]: Inferred from those measurements, 2026-11-21.
[^fw4]: Read in the E-M1 II and E-M1X firmware from OM's update server, 2026-11-24.
[^inf4]: Inferred, 2026-11-24.
[^inf5]: Inferred, 2026-11-05.
[^fw5]: Read in the OM-1 1.9 and OM-1 II firmware strings, 2026-11-19.
[^inf6]: Inferred, 2026-11-19.
[^fw6]: Read in the OM-3 1.1 firmware, 2026-11-24.
[^inf7]: Inferred. A guess, not evidence.
[^fw7]: Read in the firmware and in our hook code.
[^fw8]: Read in the E-M5 III 1.7 disassembly, static only, 2026-11-19. Other bodies by byte search the same day.
[^inf8]: Inferred, 2026-11-19.
[^fw9]: Read in the firmware, 2026-11-25.
[^fix1]: Corrected 2026-11-19. Earlier wording said these bodies "run" the network on CPU2.
[^fix2]: The end of the ring area was corrected on 2026-11-25.
[^fw10]: Read in the firmware, 2026-11-23.
[^inf9]: Inferred, 2026-11-23.
[^fw11]: Read in the firmware. Found 2026-11-06.

## History

- 2026-11-06: before the "bc" module was found, it was unknown whether the stabiliser had a separate MCU.
- 2026-11-19: earlier wording said the OM-5, OM-5 II and E-M1 III "run" deep-learning detection on CPU2. The code is
  dead there.
- 2026-11-19: the roles of `CPUCALL_CPU1/2` and `CPUCONN_CPU1/2` were open, and only task-name strings told what runs
  where. Both settled 2026-11-25 by the CPU1 and CPU2 task tables.
- 2026-11-23: the E-M5 III was thought to have a power sub-CPU. It has an always-on block of the main chip instead.
- 2026-11-25: the end of the cross-core ring area was corrected.

