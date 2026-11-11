# ARM co-processor and the ISC mailbox

Besides the MN103 cores that run the camera, the SoC has one ARM core running its own copy of Linux. It looks after
wireless (Wi-Fi, Bluetooth, the OI.Share phone app) and one piece of computation for Handheld High Res. The two sides
talk through a hardware mailbox that Panasonic calls ISC ("Inter System Communication").

This page covers where the ARM's software lives in the firmware file, which programs run on it and which mailbox
channels they use, how the MN103 can start the ARM (including from files on the SD card), how to reach a root shell on
it, and what it is and isn't fast enough for.

Tags: **[code]** read in the firmware, **[camera]** seen on a real E-M5 III, **[inferred]** not traced or tested.

## What it is

The ARM is one **Cortex-A9** (ARMv7-A, with NEON and VFPv3 maths units) next to the MN103 cores. It does **wireless and
compute**: Wi-Fi, Bluetooth LE, the OI.Share HTTP API, Wi-Fi remote live view, and the **`hhhr`** NEON helper for
Handheld High Res. It does **not** do autofocus. [code]

Some hardware details from its device tree: Linux sees 36 MB of RAM at ARM-physical address 0; the interrupt controller
(GIC) is at 0xa0001000; L2 cache at 0xa10c0000/0xa11c0000/0xa12c0000; Wi-Fi is on SDIO `mmc@9a302000`; ttyS0 at
0x9a500400 is the console and runs a **root shell**; ttyS1 at 0x98400000 talks to the Bluetooth chip (HCI). [code]

## Where the ARM software is in each firmware

| body | location | kernel | Wi-Fi chip |
|---|---|---|---|
| E-M5 III 1.7 | block 2 sub-block **0x45ef4000** (no checksum of its own) | Linux 4.4.127 (2020-03-03) + a uITRON image | CYW43455 |
| E-M1 III 1.6 | sub-block 0x46000000; `hhhr` identical apart from addresses | 4.4.127, same day | CYW43455 |
| OM-5 1.2 | sub-block 0x44ba0000; identical DTB; the itron debug shell removed | 4.4.127 (2022-07-14) | CYW43455 |
| OM-5 II 1.1 | sub-block 0x44640000; a single squashfs root | **5.10.197** | **CYW43439** (not drop-in) |
| OM-1 / OM-1 II | bank 9 | **AArch64 Cortex-A53**, ATF, 4.14.222 | CYW43455 |

[code] Extraction script:; extracted files in
.

On the E-M5 III the image is a chain of segments: a vector stub, a uITRON image (runs at 0x01000000), a Linux stub, the
zImage kernel, the device tree `dc13.dtb`, a gzip initramfs, and an LZO squashfs mounted at `/usr`. [code]

## Programs running on the ARM (E-M5 III)

At boot `/etc/init.d/S99oly` starts `dc13_rtc`, `sccore start` and `hhhr`. [code] Each program uses its own mailbox
channels:

| binary | job | ISC channels |
|---|---|---|
| sccore | supervisor, Wi-Fi start/stop, ARM debug shell | tx 27, rx 26 |
| **hhhr** | HHHR matrix maths (`MulMat`, ~1900 NEON/VFP operations) | rx **30** (48-byte request), tx **31** to CPU0 (112-byte result = three 3×3 matrices) |
| isc_olnet | Wi-Fi control | 17-21 |
| remocon | Wi-Fi remote live view over UDP | 1, 2 |
| isc_cgi, isc_file | OI.Share HTTP API / files | 11-13, 16 / 5, 6, 8 |
| blebridge + bsa_server | Bluetooth LE | 28, 29 |
| (all) | log / acknowledge | tx 14, rx 15 |
| sccore shell | `:cc`/`:ccr` root shell (2026-11-07) | rx 15 (32-byte line), tx 14 (128-byte output lines) |

The `hhhr` request is: +0 pointer to the Y (brightness) image, +4 another pointer, +8 a u16 frame index (0 = the
reference path, which only maps ptr+4). It adds 0x80000000 to the addresses and maps them through `/dev/mem`. It replies
with 112 bytes even if the mapping fails; a mailbox error makes it exit. The timeout is 100 ms. [code]

## The ISC mailbox

- It has **48 channels**, control blocks at **0x8ff00c00**, and **128 KB of shared memory at 0x62fe0000 (MN103 view) /
  0x22fe0000 (ARM view)**. On the ARM side it is the kernel module `iscdrv.ko` and the library `libisc.so`. [code]
- On the MN103 side: send is 0x61205800; blocking receive is 0x6120581c (service code 3); non-blocking receive is
  code 2 (0x6120624f, returns −5 when empty), through the dispatcher 0x61206cfe. [code] Nothing on the E-M5 III uses
  channel 30. [code]
- Powering the ARM: task `TSK_CA9PWR_MNGR` with `sys_util_ca9_start/stop`. Whether the ARM is powered while Wi-Fi and
  Bluetooth are off is the HHHR test H0 question. [open]

## Starting the ARM: the `arm` debug command (~0x60077d00-0x600783b8)

The MN103's debug console has an `arm` command: `arm load` (Linux), `load2` (itron), **`load4` (Linux from the SD card:
`C:\TARGET\bootlinux, zImage, dc13.dtb, rootfscpio, rootfssq`)**, `arm start/1/2`, `arm shell sd0|sd3d|sd3c|siodbg`
(routes the ARM serial port to the SD-slot pins), and `arm pw on/off`. [code] How to reach the debug console on a retail
body was unknown; since 2026-11-07 the card console (CON2, roadmap) is the route, but it would need an
executor line for `arm`/`:cc` commands (the maintainer's call). [inferred]

## The image loader and booting the ARM from SD (2026-11-07)

Every native ARM start goes through **0x60058c3c**, which loads the ARM image (it is called by the CA9 power manager
0x6005978d and by `arm load`). [code]

- If **0xa2624f30 == 0x77777777**, it calls 0x60058d0d and reads `C:\TARGET\bootlinux, zImage, dc13.dtb, rootfscpio,
  rootfssq` from the card to 0xc0000000 / 0xc0008000 / 0xc0ff0000 / 0xc1000000 / 0xc2400000. It reads each whole file
  with **no size check**, and only prints errors. Otherwise it reads segments 2-6 from flash (0x60167060). [code]
- **`arm load4` does nothing but write 0x77777777 to 0xa2624f30.** The flag lasts until power-off, so booting the ARM
  from SD is one RAM word plus a normal ARM start (for example the Take lease). Files that are too big overrun into the
  MN103's buffers; missing files hang the ARM (the watchdog then spins the MN103). [code]/[inferred]
- ARM-physical address = MN103 address & 0x3fffffff (`am_to_arm_addr` 0x600590c9), so the ARM can address all 1 GB
  (MN 0xc0000000 = ARM 0). [code]

## A root shell on the ARM from the MN103 console (2026-11-07)

The stock firmware already has this. [code]

- Console lines starting `:ccr <cmd>` or `:cc <cmd>` (input loop 0x600570bd) are sent as a raw 32-byte line on ISC
  **channel 15** to `sccore`. It runs the command as root, with **popen** for `:ccr` (output comes back as 128-byte lines
  on **channel 14**) or **system** for `:cc`. [code]
- Commands can be at most **27 characters**.
- MN103 task 0x60057065 prints the returned lines to the console, where the stock log tee can capture them. [code]
- The ARM must be running (flag 0xa2624f09). [code]

Other `sccore` features: `sccore ntest` is a stock VFP timing loop (1M × 8 dependent multiply-adds, counter at ARM
0x98900000+0x14c), and on channel 26, 1 = `/etc/init.d/wifi start &`, 2 = `/etc/init.d/wifi stop` (reply on channel
27). [code]

## What the ARM is fast enough for (2026-11-07)

Linux has only 36 MB. The MN103's image buffers are reachable only through `/dev/mem`, and ARM Linux 4.4 maps memory
outside its own RAM as non-cached, so full-resolution pixel passes on the A9 will be slow. `hhhr` itself maps only
~1.3 MB (a reduced Y image, O_SYNC). The CPU clock is unknown (the global timer runs from a 144 MHz pclk). So: use the
ARM for small or reduced data and networking, and keep full-frame work on the image engine. [inferred]

## Bluetooth LE (2026-11-07)

Both the E-M5 III's and the OM-5's `blebridge` are **GATT servers only**: the camera advertises and the phone or remote
connects. The MN103 and blebridge exchange 56-byte messages on ISC **channel 28**. The E-M5 III blebridge accepts **8**
command codes, the OM-5's **19**, so they aren't compatible. `libbsa.so` and `bsa_server` differ too, but the kernel and
the libraries they need are the same, so the OM-5's Bluetooth programs are a candidate set to swap in.
[code]/[inferred]

On the MN103 side the Bluetooth handler is: [code],


- E-M5 III ~0x612f98bc-0x612fa6d3 (~3.6 KB: INIT/ADVERTISE/CONNECT, transfer modes). [code]
- OM-5 ~0x61518fd3-0x6151c224 (~12.8 KB: ACC_PAIRING/ACC_REMOCON/ACC_RESTART/ACC_STANDBY, REMOCON/REMOCON_ONLY,
  button status 0x6151ba0c/0x6151ba3c, button response 0x6151bb58). [code]

## Leads

- 2026-11-05: OM-5 1.2 vs E-M5 III programs: the same kernel 4.4.127 and an identical `iscdrv.ko`; the programs moved
  from `/root` (initramfs) to `/usr/bin` (squashfs). The OM-5 `blebridge` (47 KB vs 35 KB) adds Bluetooth bonding and
  pairing (`BSA_SecAddDevice`, passkey request, `oly_ble_send_security_key`, an advertise timer): the ARM half of the
  OM-5's Bluetooth remote support. [code]
- Webcam over Wi-Fi: `remocon` already streams live view, a fallback that needs no patch. [code]
- A custom ARM userland would have to fit: initramfs ≤ 0x2b3800 bytes gzipped or rootfs ≤ 0x336000 bytes squashfs;
  only the block-2 checksum changes. [inferred]

,,.
