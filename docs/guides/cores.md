# How the cores talk to each other

*Guide 5 · E-M5 III firmware 1.7 · draft 1, 2026-11-19. New to these guides? Read
[Before you start](before-you-start.md) and [The MN103 operating system](operating-system.md) first. Open questions:
research gaps.*

The system-on-chip has three MN103 cores (CPU0, CPU1 and CPU2) and an ARM Cortex-A9. Each MN103 core runs its own
copy of the μITRON kernel with its own tasks. This guide explains how they cooperate: the memory they share, the lock
bits that keep them from treading on each other, the "doorbell" interrupts one core rings on another, the queue that
lets one core run a function on another, and the mailbox (ISC) that links the MN103 side to the ARM.

All of this was read from the code; none of it has been watched on a running camera yet.

## 1. Who runs what

CPU0 runs almost everything we work with: the user interface, the shooting sequencer, autofocus control, the lens and
the stabiliser link. The other two cores take specific heavy or time-critical jobs. Their task names, which carry a
`_CPU1` or `_CPU2` suffix, give a rough picture:

- **CPU1**: movie encoding (audio and video), an audio bridge, an image-processing module.
- **CPU2**: recording (tasks named for the main recording path, the review view and a pre-view), a second
  image-processing module, and a task that sends subject-detection events.

Each core also has its own system and user shells.

Deep-learning subject detection is a useful example of how work is split. The OM-5, OM-5 II and E-M1 III contain its
control code as tasks on CPU2 (`MDET_DL_*_CPU2`), but in those bodies it is dead code: there is no network executor and
no network weights, and the feature isn't offered. The body that does ship it, the OM-1, runs the network on a fourth
core (CPU3) and a dedicated deep-learning hardware block, with about 47 MB of weights. The E-M5 III has neither, so the
part that does the heavy work can't be ported; only the control code on CPU2 could be.

The ARM runs Linux, for Wi-Fi, Bluetooth and the helper that does the maths for handheld high-res shots.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| core number of the running core | (0x8050) | [code] |
| task names per core (`MOV_ENC_VIDEO_CPU1`, `REC_MAIN_CPU2`, `IMGPRO_MDL_CPU2`, `S_SHELL_CPU1`, ...) | strings | [code] |
| which code runs in those tasks | not traced | open |
| ARM programs and their channels | [ARM co-processor](../hardware/arm-coprocessor.md) | [code] |

Sources: [SoC overview](../hardware/soc-overview-technical.md#how-the-cores-talk-to-each-other-2026-11-19).
</details>

## 2. Shared memory

All three MN103 cores see the same RAM, so the simplest way to share is to put data somewhere both can reach. The
catch is the cache: each core has its own, so a value one core has written may still be sitting in its cache when
another core reads it. The firmware avoids this by reaching shared data through the **uncached** view of RAM (the
0xa... addresses, see the [MN103 primer](mn103-primer.md#7-the-address-space)) or through a separate shared block.

That shared block, at 0x8ff00000, holds the things every core needs: a pointer to each core's kernel data, the serial
port state that all the consoles print through, and records of a few shared objects such as frame pools. The kernels
themselves keep their objects where any core can reach them, which matters in section 5.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| shared block | 0x8ff00000-0x8ff000bc; per-core kernel pointer at 0x8ff00004 + 4 × core; UART state 0x8ff0005c | [code] |
| live-view pool object in the shared area | 0x8ff001d4 | [camera] |
| cached / uncached views | 0x6xxxxxxx / 0xaxxxxxxx | [camera] |

Sources: [OS and framework](../firmware/os-and-framework.md#debug-consoles) (task table route), [memory map](../hardware/memory-map.md).
</details>

## 3. Lock bits

When two cores might change the same data at the same time, they need a lock that works across cores. Interrupt
masking, the usual tool on one core, does nothing to stop another core.

The firmware keeps 64 one-bit locks in a small area of memory. A core takes a lock with the MN103's `bset`
instruction, which sets a bit in memory and reports whether it was already set, in one step. If the bit was clear, the
core now holds the lock; if it was set, someone else does, and the core tries again. `bclr` clears the bit to let go.
Because the test and the set happen together, two cores can't both see the bit clear.

```
pseudocode, written from the disassembly (0x6003870f, 0x600587e6; byte-matching C waits for the decompile)

take_lock(n):
    mask interrupts on this core          ; the kernel's and the ISC code's versions do
    loop:
        if bset(bit n) found it clear: return       ; we hold it
        (after 8 million tries, log a warning and keep trying)

drop_lock(n):
    bclr(bit n)
    restore interrupts
```

The kernels use two of these bits to protect their shared data. The mailbox to the ARM (section 7) uses others. Most of
these loops have no timeout: if the holder never lets go, the waiting core spins forever.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| lock area | 0x8fe00000-0x8fe0003f: lock n = bit n&7 of byte 0x8fe00000 + 8 × (n>>3) | [code] |
| try / release primitives | 0x600587d6 / 0x600587e0 | [code] |
| lock manager (mode 0 try once, 255 spin) / release | 0x600587e6 / 0x6005892d | [code] |
| kernel lock (bits 1 and 2) | 0x6003870f / 0x6003871c, used by 0x600368fa, 0x60031ade, 0x60031b67 | [code] |
| ISC's own copy | 0x61206b6d | [code] |
| `bset` atomic across cores | the design depends on it | [inferred] |

Sources: [SoC overview](../hardware/soc-overview-technical.md#how-the-cores-talk-to-each-other-2026-11-19).
</details>

## 4. Doorbells: one core interrupting another

Shared memory and locks let cores share data, but a core still needs a way to tell another "look now" without making
it check memory over and over. For that, each MN103 core has a small register block. Writing a bit to it raises an
interrupt on that core: a **doorbell**.

The receiving core's handler reads which bits are set, clears each one by writing it to an acknowledge register, and
acts on it. On CPU0, the bits mean:

| bit | meaning |
|---|---|
| 0 | set an event flag, waking a task on this core |
| 1, 2 | pass on a message |
| 3, 4, 5 | a cross-core call is waiting from CPU0, CPU1 or CPU2 (section 6) |

There is a second doorbell register that the kernel itself uses: each core's kernel configuration names a small
routine that writes to another core's block. It is probably how one kernel tells another to look at its ready tasks
again after a change (section 5), but that isn't proven.

An interrupt arriving from another core that nobody expected prints `!!Dummy IRQ from CPU1` (or CPU0, CPU2).

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| doorbell blocks | CPU0 0x99200400, CPU1 0x99300400, CPU2 0x99b00400 | [code] |
| raise / acknowledge | write the bit to +0x08 / +0x0c | [code] |
| CPU0's doorbell handler | 0x60053f11 (event flag u16 at 0x60040f00) | [code] |
| kernel kick to another core | write 1 to +0x10; routines 0x600300a1, 0x600300c3, 0x600300e5, named in the three kernel configs (0x60041528, 0x600416b4, 0x60041840) | [code]; purpose [inferred] |
| fault request | +0x00 (0x60058333) | [code] |
| unexpected inter-core interrupt message | 0x60054fa8 | [code] |

Sources: [SoC overview](../hardware/soc-overview-technical.md#how-the-cores-talk-to-each-other-2026-11-19), [memory map](../hardware/memory-map.md).
</details>

## 5. Kernel calls across cores

The [OS guide](operating-system.md#7-one-kernel-per-core) explained that every kernel object id carries its core number.
So a task on CPU0 can set an event flag that belongs to CPU1, using the same call it would use for its own flag.

What happens underneath is direct: CPU0's kernel takes the kernel lock bit, finds CPU1's kernel data through the
shared block, and changes the flag there itself. It doesn't send CPU1 a message asking it to do so. CPU1's own
scheduler then has to notice that a task may now be ready, which is presumably what the kernel's doorbell in section 4
is for.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| example: set event flag, any core | `set_flg` 0x60035b26: id → core (id >> 12), core's kernel data via 0x8ff00004 + 4 × core | [code] |
| kernel lock taken around it | 0x60038721 (mask interrupts, then lock bits) | [code] |

Sources: [OS and framework](../firmware/os-and-framework.md#kernel-objects-the-static-task-table-and-the-oly-layer-2026-11-19).
</details>

## 6. Running a function on another core

For anything more than waking a task, the firmware has a small remote-call service. A core asks another core to run a
function with one argument:

```
pseudocode, written from the disassembly (0x6005730b; byte-matching C waits for the decompile)

call_on_core(target, function, argument):
    mask interrupts
    ring = the ring for (this core → target)
    if ring is full:
        log an error, return -1
    put {function, argument} in the next slot
    advance the ring's write index
    read the shared block once            ; probably to make sure the writes have landed
    ring the target's doorbell with this core's bit
    restore interrupts
```

There is one ring of 32 slots for every pair of cores (nine in all, including a core calling itself), kept in uncached
memory. On the other side, the doorbell handler empties the ring for the core that rang, calling each function with
its argument. That happens inside the interrupt, so these functions follow the interrupt rules: no waiting.

The system shell's `syscall` command prints the nine rings and their recent entries, which makes this one of the easier
mechanisms to watch on a live camera.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| post a call | 0x6005730b(d0 target, a0 function, a1 argument) | [code] |
| descriptor table | 0x60077700 (3 × 3 × 16 bytes: write index, read index, ring base, doorbell bit) | [code] |
| rings | 0xa2623fdc-0xa26249f4, 32 × 8 bytes each | [code] |
| doorbell address table | 0x60077790: 0x99200408, 0x99300408, 0x99b00408 | [code] |
| drain the ring from CPU0 / CPU1 / CPU2 | 0x600573ee / 0x60057442 / 0x60057496 (from the doorbell handler) | [code] |
| `syscall` shell command | 0x60057a1d | [code] |

Sources: [SoC overview](../hardware/soc-overview-technical.md#how-the-cores-talk-to-each-other-2026-11-19).
</details>

## 7. The ARM: the ISC mailbox

The ARM is a different CPU running Linux, so it doesn't share the kernels' data. It talks to the MN103 cores through a
hardware mailbox that Panasonic calls **ISC** (Inter System Communication). ISC has 48 numbered channels. Each ARM
program uses its own channels: the Wi-Fi and app manager, the Bluetooth bridge, the handheld high-res helper.

Messages are short (32 to 112 bytes depending on the channel). Anything bigger, such as image data for the high-res
helper, goes through 128 KB of memory both sides map, or through image buffers the ARM maps directly.

The ARM is only powered when something needs it. A power-manager task on CPU0 starts it on request (for Wi-Fi, or for
a shot that needs it) and waits for a boot message from the ARM before marking it ready. Sending on ISC while the ARM is
off doesn't fail cleanly: the ISC code spins on its lock bits, and a send to a stopped ARM is the likely cause of a
crash in one of our tests.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| ISC channels, control blocks | 48 channels, 0x8ff00c00 | [code] |
| shared memory | 0x62fe0000 (MN103) = 0x22fe0000 (ARM), 128 KB | [code] |
| ISC send / receive (blocking) | 0x61205800 / 0x6120581c | [code] |
| ARM started flag | byte 0xa2624f09 (getter 0x60059129) | [code] |
| ARM power manager | task TSK_CA9PWR_MNGR, loop 0x6005978d | [code] |
| crash after a send with the ARM stopped | HHHR test P, 2026-11-05 | [camera]; cause [inferred] |

Sources: [ARM co-processor](../hardware/arm-coprocessor.md), [HHHR](../features/hhhr.md), [gotchas](../reference/gotchas.md).
</details>

## What this means for our patches

- **Know which core you are on.** Our hooks check the core number and act only on CPU0, because the native objects
  they touch belong to CPU0's kernel.
- **Don't call ISC without checking the ARM.** Check the ARM-started flag first; the ISC locks never time out.
- **Change ARM power only outside a capture.** Starting or stopping the ARM in the middle of a shot reset the camera
  in the HHHR tests; at idle it was fine.
- **Remote calls run in an interrupt.** A function handed to another core through the call rings must not wait or take
  locks.
- **A watchable mechanism.** If we ever need to see cross-core traffic, the `syscall` shell command already prints it.

## Checked on other cameras

Each step checked against the firmware of other bodies. Nothing is assumed: "not checked" means we don't know.

| step | E-M5 III 1.7 | OM-5 1.2 | E-M1 III 1.6 | OM-5 II 1.1 | OM-1 1.9 | PEN-F 3.1 | other projects |
|---|---|---|---|---|---|---|---|
| three MN103 cores | yes | **confirmed** (CPU2 strings) | **confirmed** | **confirmed** | **different**: four cores (CPU3) | **confirmed** (CPU2 strings) | — |
| lock bits at 0x8fe00000 | yes | **confirmed** | **confirmed** | **confirmed** | **different**: not at this address | **confirmed** | — |
| doorbell table 0x99200408 / 0x99300408 / 0x99b00408 | 0x60077790 | **confirmed** 0x6007a7b8 | **confirmed** 0x6007d3a4 | **confirmed** 0x6007b0cc | **different**: not found | **different**: not found | — |
| cross-core call service (`sys_callrequest`) | yes | **confirmed** (strings) | **confirmed** (strings) | **confirmed** (strings) | **confirmed** (strings) | not found in strings | — |
| ISC mailbox to the ARM | yes | **confirmed** | **confirmed** | not checked | not checked | not checked | — |

"Confirmed (strings)" means the names are there; the code behind them wasn't compared.
[SoC overview](../hardware/soc-overview-technical.md#how-the-cores-talk-to-each-other-2026-11-19),
[ARM co-processor](../hardware/arm-coprocessor.md).
