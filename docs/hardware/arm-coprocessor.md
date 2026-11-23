# ARM co-processor

<!-- human page -->
> The dense reference for this page is [ARM co-processor: technical notes](arm-coprocessor-technical.md).

Besides the MN103 processors that run the camera, the E-M5 III's chip has one ARM core running its own copy of Linux.
It looks after wireless, which covers Wi-Fi, Bluetooth and the OI.Share phone app. It also does one piece of maths for
Handheld High Res Shot. It does not take part in autofocus or normal shooting.

## Status

- **The software is mapped.** We know where the ARM's Linux lives in the firmware file and which programs it runs.
- **We know how to talk to it.** The two sides exchange messages through a hardware mailbox.
- **A root shell is built in.** The stock firmware can run commands on the ARM as root from the camera's debug console.

## What it is

The ARM is a single Cortex-A9 core with NEON, the ARM's vector maths unit. Linux on it sees only 36 MB of memory. It
reaches the rest of the camera's memory through a slow, uncached window.

The firmware file carries the whole ARM system. That means a small real-time OS image, a Linux 4.4 kernel, its hardware
description and two file systems.

## Programs on it

A start-up script launches a handful of programs.

| program | job |
|---|---|
| sccore | supervisor, starts and stops Wi-Fi, runs the debug shell |
| hhhr | the matrix maths for Handheld High Res Shot |
| isc_olnet | Wi-Fi control |
| remocon | Wi-Fi remote live view |
| isc_cgi, isc_file | the OI.Share phone app's web interface and file transfers |
| blebridge, bsa_server | Bluetooth Low Energy |

## The mailbox

The two sides talk through a hardware mailbox that Panasonic calls ISC, short for Inter System Communication. It has 48
channels and a 128 KB shared memory area. Each ARM program uses its own channels.

The `hhhr` helper is a good example. The main program sends it a 48-byte request naming two images. The helper maps
them, works out how the frames line up, and sends back 112 bytes holding three 3 by 3 matrices. It has to answer within
100 ms.

## Starting it

The main program powers the ARM up and down through a manager task. The ARM normally runs while Wi-Fi or Bluetooth is
in use. Whether it is powered when both are off is one of the open questions for High Res Shot.

The camera's debug console also has an `arm` command. One of its options boots the ARM from files on the SD card
instead of from flash. All it does is set one memory word, so the next ARM start reads the card. The card files are
read with no size check, so a file that is too large overwrites the main program's buffers.

## A root shell

Console lines starting with `:cc` or `:ccr` are passed to `sccore` on the ARM, which runs them as root. With `:ccr` the
output comes back to the console. Commands are limited to 27 characters, and the ARM must already be running.

## What it is fast enough for

Not much pixel work. Linux has little memory of its own, and it sees the camera's image buffers only through uncached
access, which is slow. Even `hhhr` works on a reduced brightness image of about 1.3 MB. The ARM suits small data and
networking. Full-size frames are a job for the image engine.

## Bluetooth

On both the E-M5 III and the OM-5, the camera is a Bluetooth server. The phone or remote connects to it. The OM-5's
Bluetooth program adds pairing and bonding, which its Bluetooth remote relies on. The E-M5 III's version understands 8
commands and the OM-5's 19, so they are not interchangeable. The Linux kernel and shared libraries are the same, so the
OM-5's Bluetooth programs are a candidate to swap in.

## Other cameras

| camera | ARM side |
|---|---|
| E-M1 III, OM-5 | the same Cortex-A9 and Linux 4.4. The `hhhr` helper is the same apart from addresses. |
| OM-5 II | the same core, Linux 5.10 and a different Wi-Fi chip |
| OM-1, OM-1 II | two 64-bit Cortex-A53 cores with ARM Trusted Firmware and Linux 4.14 |
| PEN-F, E-M5 II | no ARM. The main processor runs Wi-Fi itself. |
| E-M5 (Mark I) | no ARM and no Wi-Fi |

## Further reading

- [Handheld High Res Shot](../features/hhhr.md) explains where `hhhr` fits.
- [SoC overview](soc-overview.md) places the ARM among the chip's other processors.
- [Wi-Fi debug shell](../features/wifi-debug-shell.md) is one way into the debug console.
