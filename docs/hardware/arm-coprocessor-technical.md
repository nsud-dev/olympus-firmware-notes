# ARM co-processor: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [ARM co-processor](arm-coprocessor.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

Besides the MN103 cores that run the camera, the system-on-chip (SoC) has one ARM core running its own copy of Linux.
It looks after wireless (Wi-Fi, Bluetooth, the OI.Share phone app) and one piece of computation for Handheld High Res
(HHHR). The two sides talk through a hardware mailbox that Panasonic calls ISC ("Inter System Communication").

This page covers where the ARM's software lives in the firmware file, which programs run on it and which mailbox
channels they use. It also covers how the MN103 can start the ARM, including from files on the SD card, how to reach a
root shell on it, and what it is and isn't fast enough for.

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: blue = read in the firmware, grey = inferred.

## Core

The ARM is one **Cortex-A9** (ARMv7-A, with NEON and VFPv3 maths units) next to the MN103 cores. It does **wireless and
compute**. That means Wi-Fi, Bluetooth LE, the OI.Share HTTP API, Wi-Fi remote live view, and the **`hhhr`** NEON helper
for HHHR. It does **not** do autofocus.[^fw1]

Its device tree gives some hardware details.[^fw1]

- Linux sees 36 MB of RAM at ARM-physical address 0.
- The interrupt controller (GIC) and three L2 cache controllers are listed. Their addresses are in the
  [address reference](#address-reference).
- Wi-Fi is on SDIO, `mmc@9a302000`.
- ttyS0 is the console and runs a **root shell**.
- ttyS1 talks to the Bluetooth chip (HCI).

## Software in each firmware

| body | kernel | Wi-Fi chip | notes |
|---|---|---|---|
| E-M5 III 1.7 | Linux 4.4.127[^fw9] + a uITRON image | CYW43455 | block 2 sub-block, no checksum of its own |
| E-M1 III 1.6 | 4.4.127, built the same day[^fw9] | CYW43455 | `hhhr` identical apart from addresses |
| OM-5 1.2 | 4.4.127[^fw9] | CYW43455 | identical DTB, the itron debug shell removed |
| OM-5 II 1.1 | **5.10.197** | **CYW43439** (not drop-in) | a single squashfs root |
| OM-1 / OM-1 II | **AArch64 Cortex-A53**, ATF, 4.14.222 | CYW43455 | bank 9 (OM-1), bank 8 (OM-1 II) |
| PEN-F 3.1, E-M5 II 4.1 | **none**. No ELF, kernel or device tree in any block. | BCM43362 | the MN103 drives Wi-Fi itself over SDIO (`wlanapi_sdio_*`)[^fw3] |
| E-M5 (Mark I) 2.3 | none | none | no Wi-Fi code[^fw3] |

*The ARM software by body. Sub-block and bank addresses are in the [address reference](#address-reference).[^fw1]*

### E-M5 III image

On the E-M5 III the ARM image is a chain of segments.[^fw1]

1. A vector stub.
2. A uITRON image.
3. A Linux stub.
4. The zImage kernel.
5. The device tree `dc13.dtb`.
6. A gzip initramfs.
7. An LZO squashfs mounted at `/usr`.

### OM-1 and OM-1 II: two Cortex-A53 cores

The OM-1's ARM side is a **two-core Cortex-A53** cluster as far as any software can use it. Four independent places in
both OM-1 1.9 and OM-1 II 1.3 agree.[^fw4]

- **Device tree** (`seg1`, compatible `ntcj,nep1`). It has exactly two `cpu` nodes, `cpu@0` and `cpu@1`,
  `arm,cortex-a53`, `enable-method = "psci"` (PSCI 1.0 over SMC). The OM-1 and OM-1 II trees are byte-for-byte the same
  after decoding.
- **Kernel config** (embedded `IKCFG`). `CONFIG_NR_CPUS=2`, `CONFIG_SMP=y`. Linux
  4.14.222.[^fw9]
- **ATF BL31 v2.2** (`seg0`). `plat_core_pos_by_mpidr` rejects any Aff1 or Aff2 and any Aff0 above 1. The PSCI
  power-domain tree is `{1, 2}`, one cluster of two cores.
- **GICv3 redistributor region.** It is `0x40000` bytes, which is two 128 KB redistributor frames, one per
  core.[^fw4][^inf2]

The firmware can't say whether the die has more A53 cores that are fused off or held in reset. Nothing in the firmware
addresses a third core.[^inf2] The camera's other processors are separate from this cluster. Those are four MN103 cores
CPU0-3, the DSP and the DL block.[^fw4]

Linux on the A53 only gets 96 MB of RAM. That is `memory@0x40000` with size `0x5100000` (81 MB), plus a 14.75 MB
RAM-disk root (`slram=mtd0,0x05140000,+0x000ec0000`).[^fw4]

## Programs on the E-M5 III

At boot `/etc/init.d/S99oly` starts `dc13_rtc`, `sccore start` and `hhhr`.[^fw1] Each program uses its own mailbox
channels.

| binary | job | ISC channels |
|---|---|---|
| sccore | supervisor, Wi-Fi start/stop, ARM debug shell | tx 27, rx 26 |
| **hhhr** | HHHR matrix maths (`MulMat`, ~1900 NEON/VFP operations) | rx **30** (48-byte request), tx **31** to CPU0 (112-byte result = three 3×3 matrices) |
| isc_olnet | Wi-Fi control | 17-21 |
| remocon | Wi-Fi remote live view over UDP | 1, 2 |
| isc_cgi, isc_file | OI.Share HTTP API / files | 11-13, 16 / 5, 6, 8 |
| blebridge + bsa_server | Bluetooth LE | 28, 29 |
| (all) | log / acknowledge | tx 14, rx 15 |
| sccore shell | `:cc`/`:ccr` root shell | rx 15 (32-byte line), tx 14 (128-byte output lines)[^fw5] |

*Programs on the ARM and the mailbox channels each uses.[^fw1]*

### The `hhhr` request

The request holds three fields.[^fw1]

- +0 is a pointer to the Y (brightness) image.
- +4 is another pointer.
- +8 is a u16 frame index. 0 is the reference path, which only maps ptr+4.

The helper adds `0x80000000` to the addresses and maps them through `/dev/mem`. It replies with 112 bytes even if the
mapping fails. A mailbox error makes it exit. The time-out is 100 ms.[^fw1]

## ISC mailbox

The mailbox has **48 channels** and **128 KB of shared memory**. The shared memory has one address in the MN103 view
and another in the ARM view. On the ARM side the mailbox is the kernel module `iscdrv.ko` and the library
`libisc.so`.[^fw1]

On the MN103 side there are three calls, all through one dispatcher.[^fw1]

- Send.
- Blocking receive, service code 3.
- Non-blocking receive, code 2. It returns −5 when the channel is empty.

Nothing on the E-M5 III uses channel 30.[^fw1]

### Power

The task `TSK_CA9PWR_MNGR` powers the ARM up and down with `sys_util_ca9_start` and `sys_util_ca9_stop`. It is a CPU1
task (`SYS_CA9_PWR_MNG`, id `0x101c`).[^fw6] Whether the ARM is powered while Wi-Fi and Bluetooth are off is the first
HHHR test's question.

## Debug command `arm`

The MN103's debug console has an `arm` command.[^fw1]

- `arm load` loads Linux, and `load2` loads itron.
- **`load4` loads Linux from the SD card**: `C:\TARGET\bootlinux, zImage, dc13.dtb, rootfscpio, rootfssq`.
- `arm start/1/2` starts the ARM.
- `arm shell sd0|sd3d|sd3c|siodbg` routes an ARM serial port to the card-slot pins (sd0), SD channel 3 or the siodbg
  pins.
- `arm jtag` puts the ARM JTAG on five card-slot pins.[^fw7]
- `arm pw on` and `arm pw off` switch its power.

See also: [OS and framework](../firmware/os-and-framework.md), section "Debug serial port".

The card console is the route to the debug console on a retail body. It would need an executor line for the `arm` and
`:cc` commands. Adding one is a project decision.[^inf3]

## Image loader and SD boot

Every native ARM start goes through one image loader. The CA9 power manager and `arm load` both call it.[^fw5]

- If a flag word holds `0x77777777`, the loader reads `C:\TARGET\bootlinux, zImage, dc13.dtb, rootfscpio, rootfssq`
  from the card to five fixed addresses. It reads each whole file with **no size check**, and only prints
  errors.[^fw5]
- Otherwise it reads segments 2 to 6 from flash.[^fw5]
- **`arm load4` does nothing but write `0x77777777` to the flag word.** The flag lasts until power-off. So booting the
  ARM from SD is one RAM word plus a normal ARM start, for example the Take lease.[^fw5][^inf3]

> [!WARNING]
> The SD boot path has no size check. Files that are too big overrun into the MN103's buffers. Missing files hang the
> ARM, and the watchdog then spins the MN103.

An ARM-physical address is the MN103 address & `0x3fffffff`. So the ARM can address all 1 GB, and MN103 `0xc0000000`
is ARM 0.[^fw5]

## Root shell

The stock firmware already has a root shell on the ARM, reachable from the MN103 console.[^fw5]

- Console lines starting `:ccr <cmd>` or `:cc <cmd>` are sent as a raw 32-byte line on ISC **channel 15** to `sccore`.
  It runs the command as root.
    - `:ccr` uses **popen**. The output comes back as 128-byte lines on **channel 14**.
    - `:cc` uses **system**.
- Commands can be at most **27 characters**.
- An MN103 task prints the returned lines to the console, where the stock log tee can capture them.
- The ARM must be running, which a flag shows.

`sccore` has other features.[^fw1]

- `sccore ntest` is a stock VFP timing loop, 1M × 8 dependent multiply-adds, with a counter at ARM
  `0x98900000`+`0x14c`.
- On channel 26, 1 = `/etc/init.d/wifi start &` and 2 = `/etc/init.d/wifi stop`. The reply comes on channel 27.

## Speed

Linux has only 36 MB. The MN103's image buffers are reachable only through `/dev/mem`. ARM Linux 4.4 maps memory
outside its own RAM as non-cached, so full-resolution pixel passes on the A9 will be slow. `hhhr` itself maps only about
1.3 MB, a reduced Y image opened O_SYNC. The CPU clock is unknown. The global timer runs from a 144 MHz pclk.[^inf3]

So the ARM suits small or reduced data and networking. Full-frame work stays on the image engine.[^inf3]

## Bluetooth LE

Both the E-M5 III's and the OM-5's `blebridge` are **GATT servers only**. The camera advertises and the phone or
remote connects. The MN103 and blebridge exchange 56-byte messages on ISC **channel 28**.[^fw5]

The E-M5 III blebridge accepts **8** command codes and the OM-5's **19**, so they aren't compatible. `libbsa.so` and
`bsa_server` differ too. The kernel and the libraries they need are the same, so the OM-5's Bluetooth programs are a
candidate set to swap in.[^fw5][^inf3]

The MN103 side has a Bluetooth handler in both bodies.[^fw5]

- E-M5 III, about 3.6 KB. It covers INIT, ADVERTISE, CONNECT and the transfer modes.
- OM-5, about 12.8 KB. It covers ACC_PAIRING, ACC_REMOCON, ACC_RESTART, ACC_STANDBY, REMOCON and REMOCON_ONLY, a
  button status and a button response.

## Leads

- The OM-5 1.2 and E-M5 III ARM programs share the kernel 4.4.127 and an identical `iscdrv.ko`. The programs moved
  from `/root` (initramfs) to `/usr/bin` (squashfs).[^fw8]
- The OM-5 `blebridge` (47 KB against 35 KB) adds Bluetooth bonding and pairing (`BSA_SecAddDevice`, passkey request,
  `oly_ble_send_security_key`, an advertise timer). That is the ARM half of the OM-5's Bluetooth remote
  support.[^fw8]
- For a webcam over Wi-Fi, `remocon` already streams live view. It is a fallback that needs no patch.[^fw1]
- A custom ARM userland would have to fit an initramfs of at most `0x2b3800` bytes gzipped, or a rootfs of at most
  `0x336000` bytes squashfs. Only the block-2 checksum changes.[^inf1]

## Open questions

- Whether the ARM is powered while Wi-Fi and Bluetooth are off. The first HHHR test answers it.
- Whether the OM-1's die has more A53 cores that are fused off or held in reset.
- The ARM's CPU clock.

## Address reference

E-M5 III 1.7 block0 addresses (MN103 view) unless a body or the ARM view is named.

| body | location of the ARM software |
|---|---|
| E-M5 III 1.7 | block 2 sub-block `0x45ef4000` |
| E-M1 III 1.6 | sub-block `0x46000000` |
| OM-5 1.2 | sub-block `0x44ba0000` |
| OM-5 II 1.1 | sub-block `0x44640000` |

*Where each body's firmware file holds the ARM software.*

| item | address |
|---|---|
| GIC | `0xa0001000` |
| L2 cache | `0xa10c0000`, `0xa11c0000`, `0xa12c0000` |
| Wi-Fi SDIO | `0x9a302000` |
| ttyS0 (console) | `0x9a500400` |
| ttyS1 (Bluetooth HCI) | `0x98400000` |
| uITRON image run address | `0x01000000` |
| OM-1 `plat_core_pos_by_mpidr`, PSCI tree (file offsets in `seg0`) | `0x36c`, `0x5148` |
| OM-1 GICv3 redistributor region | `0xa00c0000` |

*ARM-side hardware, in the ARM view.*

| item | address |
|---|---|
| ISC control blocks | `0x8ff00c00` |
| ISC shared memory | `0x62fe0000` (MN103 view), `0x22fe0000` (ARM view) |
| send, blocking receive | `0x61205800`, `0x6120581c` |
| non-blocking receive, dispatcher | `0x6120624f`, `0x61206cfe` |
| `arm` command | about `0x60077d00`–`0x600783b8` |
| image loader | `0x60058c3c` |
| CA9 power manager call | `0x6005978d` |
| SD boot flag word | `0xa2624f30` |
| SD file reader | `0x60058d0d` |
| SD load addresses | `0xc0000000`, `0xc0008000`, `0xc0ff0000`, `0xc1000000`, `0xc2400000` |
| flash segment reader | `0x60167060` |
| `am_to_arm_addr` | `0x600590c9` |
| console input loop (`:cc`, `:ccr`) | `0x600570bd` |
| reply print task | `0x60057065` |
| ARM running flag | `0xa2624f09` |

*Mailbox, start-up and shell on the MN103 side.*

| item | address |
|---|---|
| E-M5 III Bluetooth handler | about `0x612f98bc`–`0x612fa6d3` |
| OM-5 Bluetooth handler | about `0x61518fd3`–`0x6151c224` (OM-5) |
| OM-5 button status, button response | `0x6151ba0c`, `0x6151ba3c`, `0x6151bb58` (OM-5) |

*Bluetooth handlers.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware.
[^fw2]: Read in the firmware, 2026-11-24.
[^fw3]: Read in the firmware, 2026-11-21.
[^fw4]: Read in the firmware, 2026-11-19, in OM-1 1.9 and OM-1 II 1.3.
[^fw5]: Read in the firmware, 2026-11-07.
[^fw6]: Read in the firmware, 2026-11-25.
[^fw7]: Read in the firmware, 2026-11-23.
[^fw8]: Read in the firmware, 2026-11-05, comparing the OM-5 1.2 and E-M5 III ARM programs.
[^fw9]: Kernel build dates read in the firmware. E-M5 III and E-M1 III 2020-03-03, OM-5 2022-07-14, OM-1 II
    2025-02-21, OM-3 2025-02-26.
[^inf1]: Inferred, not traced or tested.
[^inf2]: Inferred, 2026-11-19.
[^inf3]: Inferred, 2026-11-07.

## History

- Before 2026-11-07: how to reach the debug console on a retail body was unknown. Since 2026-11-07 the card console is
  the route.

