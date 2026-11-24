# Failure patterns

<!-- human page -->

This page lists the ways a changed firmware has failed on an E-M5 III. Each entry gives the symptom, the cause and
a check that catches it before flashing.

Many of the checks run in the [om-emu](https://github.com/flatpanda/om-emu) emulator. Our additions to it are
described in [om-emu additions](../tools/om-emu-additions.md). Shorter one-line warnings are in
[Gotchas](gotchas.md).

## Start-up

| symptom | cause | check |
|---|---|---|
| Boot loop, or a dead camera at power-on | New code in an early part of the firmware jumped into a part that was not loaded yet. The firmware loads its sections one after another in the background. | A static check that no early hook reaches a later section. In the emulator, a monitor that fails a build which touches a section before the stock firmware does. |
| Fails on some start-ups only | The same cause, when the section load and the new code race each other. | The same checks, using the worst-case order. |
| Black screen from power-on | A driver kept its working data in an unused gap inside the code area. The processor's cache then held stale code. | A monitor that fails any store into the always-loaded code. |
| One reset at every power-on, then normal | Not fully explained. The crash sits in the task that creates tasks for the other processor cores. | None yet. The emulator starts the other cores too late to show it. |

## Menus and screens

| symptom | cause | check |
|---|---|---|
| Reset when a menu value is chosen | A screen widget keeps a fixed number of states. A new value one past the end read a wild pointer. | A rule on the widget's state number at the point of use. |
| Reset on opening the menu | A picture list was made one entry longer than the code that copies it expects. | A static rule on the list lengths. |
| A screen opens but draws nothing | The drawing layer and the draw call were of different kinds. | A screenshot comparison in the emulator. |

## Shooting

| symptom | cause | check |
|---|---|---|
| Reset on the shutter press | A one-digit typing error in an absolute address. | Require evidence from the stock firmware for every absolute address in a build. |
| Frozen live view | A lock was taken inside a completion callback. That callback runs in interrupt context, where blocking is not allowed. | A kernel check for blocking calls made from an interrupt. |
| Hang until the battery is pulled | The image engine refused a job and the task that sent it waited forever. | Check the engine's answer and give every wait a time limit. |
| Reboot when reading a buffer | Some memory blocks cannot be read by the main processor the usual way. | A memory-map rule for reads outside the known windows. |
| A feature stops working after a while | Two pieces of new code used overlapping scratch memory. | A write-ownership watch over the fields each piece owns. |
| Shutter delay | New code opened a file on every press before checking whether it was needed. | Count file operations per press. No file access on the shutter path. |
| Empty log files on the card | The buffer was written through the uncached address but read through the cached one. | Use one view of memory for a buffer, or flush between the two. |

## Emulator limits

An emulator catches a failure only on a path it runs. om-emu does not model the processor caches, real timing, the
sensor or the image engine. It runs the other processor cores only with our additions, and only after the main core
has started. So the shooting patterns above are mostly found by reading and by static checks, not by emulation.

Each emulator check here was added after a real failure. Each one had to fail the broken build, and pass both the
fixed build and the stock firmware.

Related: [Recovery](../firmware/recovery.md), [Gotchas](gotchas.md), [om-emu additions](../tools/om-emu-additions.md).
