# Interrupts, timers and DMA

<!-- human page -->
<!-- house style -->

## Key points

- Each of the main chip's three cores has its own interrupt controller with 182 lines and seven priority levels.
- One timer block with 28 channels gives each core a 1 ms heartbeat and the firmware a microsecond clock.
- There is no shared DMA unit, because each block that moves a lot of data has its own copy engine.
- The OM-5 II program uses the same interrupt lines and priorities.

This page explains how the camera's main chip reacts to hardware events, how it keeps time, and how data moves without
the processor copying it. It covers the E-M5 III 1.7 program and the OM-5 II 1.1 program, read from its update file.
Both work the same way. Everything here comes from reading the firmware. Nothing here was run on the camera.

## Interrupts

An interrupt is a signal from a piece of hardware that says "I need attention now". The processor stops what it is
doing, runs a short handler, and then goes back.

The chip has three MN103 processor cores. Each core has its own interrupt controller with 182 numbered lines. A line
can be switched on for one core only. The firmware decides which core handles which line when a driver starts.

Each line also gets a priority from 0 to 6. Lower numbers are more urgent. A more urgent interrupt can break into a
less urgent handler. About 100 lines are in use. Most hardware sits at priority 2 to 5.

When an interrupt arrives, the operating system saves the running task, switches to a separate interrupt stack and
calls the handler. When the last handler finishes, it checks whether a task woke up and switches to it if needed.

## Interrupt sources

The table lists which hardware owns the lines in use.

<details><summary>Interrupt lines by hardware</summary>

| hardware | lines |
|---|---|
| shutter | 2 |
| sensor input | 4-6 |
| sensor serial commands | 7 |
| image pipeline blocks | 8-19, 21 |
| sensor frame timing | 22 |
| autofocus calculation unit | 20 |
| audio | 23, 24 |
| displays (rear screen, EVF and HDMI) | 25, 27 |
| external pins | 29-34 |
| timers | 88-99 |
| serial ports (8 channels) | 100-121 |
| USB | 124 |
| SD card | 125-129 |
| movie recording and video units | 133-152 |
| tracking units | 134, 135 |
| on-screen drawing | 158 |
| analogue inputs | 163 |
| buttons | 165 |
| power and wake block | 166, 167 |
| messages between cores | 168, 169, 170 |
| RAW decoder | 145 |
| the ARM helper's watchdog | 171 |

*Interrupt lines by hardware. Read in the firmware.*

</details>

Line 170 is a wake-up call from one core to another. The sender leaves a command in shared memory and rings the
line. The handler only switches the line off again.

Some owners are still guesses or unknown. The technical page marks each one.

## Timers

The chip has one timer block with 28 channels. Each channel counts down and can raise an interrupt when it reaches
zero.

- Channels 1, 2 and 3 are the heartbeat of the three cores. Each fires every millisecond and drives the operating
  system's clock.
- Channel 27 runs freely and never stops. The firmware reads it as a microsecond clock.
- Channels 10 to 25 are handed out to firmware code that asks for a timer.

Most firmware timers are not hardware channels. They share one software list that is checked every 2 milliseconds.
That check itself runs on one hardware channel. A card mod that uses this list is accurate to about 2 milliseconds.

The watchdog is not part of this block. It lives in the always-on [power block](power-block.md).

The 1 MHz count rate is inferred, not measured.

## DMA

DMA means a piece of hardware copies data to or from memory by itself, while the processor does other work.

The chip has no shared DMA unit that drivers borrow. Each block that moves a lot of data has its own copy engine. The
display reads its pictures from memory this way. The sensor input, USB, the SD card, the image pipeline and the drawing
engines do the same.

Each core also has a small built-in DMA unit. The firmware has a driver for it, but only a debug shell command uses
it.

Data that a copy engine reads must be written to memory first, not left in the processor's cache. See
[caches](caches.md).

## Notes for mods

- A mod's handler that runs in an interrupt must be short and must not wait for anything.
- A mod that polls on a timer is limited to about 2 millisecond steps.
- A buffer handed to any copy engine must use the uncached view of memory.
- The OM-5 II program uses the same lines and priorities as the E-M5 III program. A driver from either one finds its
  hardware in the same place.

## Further reading

- [Interrupts, timers and DMA: technical notes](interrupts-timers-dma-technical.md) has the line table, the timer
  registers, the DMA details and the address reference.
- [CPU1 and CPU2](cpu1-cpu2.md) covers the other two cores.
- [Power and watchdog block](power-block.md) covers the watchdog.
- [Caches](caches.md) explains the cache rule for copy engines.
