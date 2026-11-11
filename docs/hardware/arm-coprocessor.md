# ARM co-processor and the ISC mailbox

## What it is
- One **Cortex-A9** (ARMv7-A, NEON, VFPv3) next to the MN103 cores. It does **wireless and compute**: Wi-Fi,
  Bluetooth LE, OI.Share HTTP API, Wi-Fi remote live view, and the **`hhhr`** NEON helper for Handheld High Res.
  It does **not** do AF. [code]
- Linux sees 36 MB at ARM-physical 0. GIC 0xa0001000, L2 at 0xa10c0000/0xa11c0000/0xa12c0000, SDIO for Wi-Fi
  `mmc@9a302000`, ttyS0 0x9a500400 (console, runs a **root shell**), ttyS1 0x98400000 (BT HCI). [code]

## Where the image is
| body | location | kernel | Wi-Fi |
|---|---|---|---|
| E-M5 III 1.7 | block 2 sub-block **0x45ef4000** (no nested checksum) | Linux 4.4.127 (2020-03-03) + uITRON image | CYW43455 |
| E-M1 III 1.6 | sub-block 0x46000000; `hhhr` identical apart from addresses | 4.4.127 same day | CYW43455 |
| OM-5 1.2 | sub-block 0x44ba0000; identical DTB; itron debug shell removed | 4.4.127 (2022-07-14) | CYW43455 |
| OM-5 II 1.1 | sub-block 0x44640000; single squashfs root | **5.10.197** | **CYW43439** (not drop-in) |
| OM-1 / OM-1 II | bank 9 | **AArch64 Cortex-A53**, ATF, 4.14.222 | CYW43455 |
[code] Extraction:; extracted files in.

E-M5 III segments: vector stub, uITRON (runs at 0x01000000), Linux stub, zImage, DTB `dc13.dtb`, gzip initramfs,
LZO squashfs mounted at `/usr`. [code]

## Daemons (E-M5 III)
`/etc/init.d/S99oly` starts `dc13_rtc`, `sccore start`, `hhhr`. [code]

| binary | job | ISC channels |
|---|---|---|
| sccore | supervisor, wifi start/stop, ARM debug shell | tx 27, rx 26 |
| **hhhr** | HHHR matrix maths (`MulMat`, ~1900 NEON/VFP ops) | rx **30** (48 B request), tx **31** → CPU0 (112 B result = three 3×3 matrices) |
| isc_olnet | Wi-Fi control | 17-21 |
| remocon | Wi-Fi remote live view over UDP | 1, 2 |
| isc_cgi, isc_file | OI.Share HTTP API / files | 11-13, 16 / 5, 6, 8 |
| blebridge + bsa_server | BLE | 28, 29 |
| (all) | log/ack | tx 14, rx 15 |
| sccore shell | `:cc`/`:ccr` root shell (2026-11-07) | rx 15 (32 B line), tx 14 (128 B output lines) |

`hhhr` request: +0 Y-image pointer, +4 pointer, +8 u16 frame index (0 = reference path maps only ptr+4); it adds
0x80000000 to addresses and maps them via `/dev/mem`; replies 112 B even if mmap fails; an ISC error makes it
exit. 100 ms timeout. [code]

## ISC (Inter System Communication)
- Panasonic mailbox: **48 channels**, control blocks at **0x8ff00c00**, **128 KB shared memory at 0x62fe0000
  (MN103 view) / 0x22fe0000 (ARM view)**. Kernel module `iscdrv.ko`, library `libisc.so`. [code]
- MN103 side: send 0x61205800, blocking receive 0x6120581c (service code 3), non-blocking receive = code 2
  (0x6120624f, −5 = empty) via dispatcher 0x61206cfe. [code] E-M5 III has no caller on channel 30. [code]
- CA9 power: `TSK_CA9PWR_MNGR`, `sys_util_ca9_start/stop`. Whether the ARM is powered with Wi-Fi/BT off is the
  HHHR H0 question. [open]

## MN103 debug console `arm` command (~0x60077d00-0x600783b8)
`arm load` (linux), `load2` (itron), **`load4` (Linux from SD: `C:\TARGET\bootlinux, zImage, dc13.dtb,
rootfscpio, rootfssq`)**, `arm start/1/2`, `arm shell sd0|sd3d|sd3c|siodbg` (route the ARM UART to SD-slot
pins), `arm pw on/off`. How to reach the debug console on a retail body is unknown. [code] 2026-11-07: the card console
(CON2, roadmap) is the route; it would need an executor line for `arm`/`:cc` commands (the maintainer's call). [inferred]

## Image loader and SD boot (2026-11-07)
- **0x60058c3c** loads the ARM image for every native ARM start (CA9 manager 0x6005978d and `arm load`): if
  **0xa2624f30 == 0x77777777** it calls 0x60058d0d and reads `C:\TARGET\bootlinux, zImage, dc13.dtb, rootfscpio, rootfssq`
  to 0xc0000000 / 0xc0008000 / 0xc0ff0000 / 0xc1000000 / 0xc2400000 (whole file, **no size check**, errors only printed);
  otherwise it reads segments 2-6 from flash (0x60167060). [code]
- **`arm load4` only writes 0x77777777 to 0xa2624f30**; the flag lasts until power-off, so SD boot = one RAM word + a normal
  ARM start (e.g. the Take lease). Oversized files overrun into the MN103 buffer map; missing files hang the ARM (WDT spins
  the MN103). [code]/[inferred]
- ARM-physical = MN address & 0x3fffffff (`am_to_arm_addr` 0x600590c9): the ARM can address all 1 GB
  (MN 0xc0000000 = ARM 0). [code]

## Stock ARM root shell from the MN103 console (2026-11-07)
- System-shell lines `:ccr <cmd>` / `:cc <cmd>` (input loop 0x600570bd) go as a raw 32-byte line on ISC **ch 15** to
  `sccore`, which runs **popen** (`:ccr`, output lines of 128 B back on **ch 14**) or **system** (`:cc`) as root. Commands
  are at most **27 characters**. MN103 task 0x60057065 prints the returned lines to the console (capturable with the stock
  tee). Needs the ARM running (flag 0xa2624f09). [code]
- `sccore ntest` = stock VFP timing loop (1M × 8 dependent multiply-adds, counter at ARM 0x98900000+0x14c). [code]
- `sccore` ch 26: 1 = `/etc/init.d/wifi start &`, 2 = `/etc/init.d/wifi stop` (reply on ch 27). [code]

## Compute (NEON) limits (2026-11-07)
- Linux has 36 MB; MN image buffers are reachable only through `/dev/mem`, which ARM Linux 4.4 maps non-cached for memory
  outside its own RAM, so full-resolution pixel passes on the A9 will be slow. `hhhr` maps only ~1.3 MB (reduced Y image,
  O_SYNC). CPU clock unknown (global timer pclk 144 MHz). Use the ARM for small/reduced data and networking; keep
  full-frame work on the DSP. [inferred]

## Bluetooth LE protocol (2026-11-07)
- Both E-M5 III and OM-5 `blebridge` are **GATT servers only** (camera advertises; remote/phone connects). MN103 ⇄ blebridge
  = 56-byte messages on ISC **ch 28**; E-M5 III blebridge accepts **8** command codes, OM-5 **19** (not compatible).
  `libbsa.so` and `bsa_server` differ too; the kernel and needed libraries are the same, so the OM-5 BLE userland is a
  candidate set to swap in. [code]/[inferred]
- MN103 BLE handler: E-M5 III ~0x612f98bc-0x612fa6d3 (~3.6 KB: INIT/ADVERTISE/CONNECT, transfer modes); OM-5
  ~0x61518fd3-0x6151c224 (~12.8 KB: ACC_PAIRING/ACC_REMOCON/ACC_RESTART/ACC_STANDBY, REMOCON/REMOCON_ONLY, button status
  0x6151ba0c/0x6151ba3c, button response 0x6151bb58). [code],


## Leads
- 2026-11-05: OM-5 1.2 vs E-M5 III userland: same kernel 4.4.127, identical `iscdrv.ko`; daemons moved from `/root`
  (initramfs) to `/usr/bin` (squashfs). OM-5 `blebridge` (47 KB vs 35 KB) adds BLE bonding/pairing (`BSA_SecAddDevice`,
  passkey request, `oly_ble_send_security_key`, advertise timer): the ARM half of OM-5's Bluetooth remote support. [code]

- Webcam over Wi-Fi: `remocon` already streams live view (no-patch fallback). [code]
- Custom ARM userland: initramfs ≤ 0x2b3800 gz or rootfs ≤ 0x336000 squashfs; only the block-2 checksum changes. [inferred]

,,.
