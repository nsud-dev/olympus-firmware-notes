# Caches and the access monitor

<!-- human page -->
<!-- house style -->

## Key points

- Each of the three control processors has its own data cache, and nothing in the hardware keeps them in agreement.
- The stock firmware shares data between cores and with other parts of the chip through the uncached view of memory.
- The instruction cache is cleared only when a core starts, so code patched at run time must be written with care.
- While the camera starts, an access monitor guards the parts of the program that are still loading, including one
  byte past the end.

A cache is a small, fast copy of recently used memory, kept next to a processor so it does not have to wait for main
memory every time. Caches make the camera fast. They also cause some of the hardest bugs in firmware patching, because
what one part of the camera sees in memory is not always what another part sees.

This page explains how the E-M5 III's control processors cache memory, how the firmware keeps everything in step, and
the access monitor that guards memory while the camera starts. Everything here was read from the firmware's own code.

## Two views of memory

All the camera's memory can be reached at two addresses. One goes through the cache and the other bypasses it. The
bytes are the same, but a write through the cached view can sit in the cache for a while before it reaches memory.

## Data caches

Each of the three control processors has an 8 KB data cache. Nothing in the hardware keeps those caches in agreement.
If two cores share data through the cached view, each may see an old copy.

The stock firmware avoids that. Data shared between cores lives in the uncached view. Buffers for the image engine, the
display and the card are reached the same way. Messages to the ARM co-processor are the one place the firmware shares
through the cache, and there it writes each line back to memory by hand before the ARM reads it.

Between the cores and memory there are also small buffers that hold writes on their way out. Code that hands a buffer
to another part of the chip has to drain those too.

## Instruction cache

The firmware clears the instruction cache only when a core starts. No routine clears it later.

That matters for patching. If a patch changes code while the camera runs, a core can keep running the old instructions
from its cache. The safe way to write a hook follows from this.

1. Write it through the uncached view.
2. Keep it inside one 16-byte cache line.
3. Write the first byte last, so the jump only exists once it is complete.

Done that way, any mix of old and new cache contents still runs correctly.

## Access monitor

The access monitor is a piece of hardware that watches ranges of addresses and stops the camera if anything touches
one.

While the camera starts, the main program loads in ten sections, one after another. After each section the firmware
points the monitor at everything not yet loaded. So nothing can run or read code that is still on its way. After the
last section, the monitor switches to guarding the gaps in the address map for good.

The detail that matters is that the monitor's end address is inclusive. During start-up the firmware passes it the
first byte after the last section. So the monitor also covers that one extra byte.

## Rules for patches

- **Leave a gap after any section end.** Our rule is a gap of at least one cache line, and better a 4 KB page.
- **Share data through the uncached view,** or write it back and drain it by hand.
- **Write code the safe way** described above, and never rely on the firmware to clear the instruction cache.

> [!WARNING]
> We once raised a section end so that it sat right against memory another core uses while the camera starts. The
> camera reset at power-on. The inclusive end above is the likely reason.

## Status

The design is read from the code. Some details of what the hardware does are our interpretation. One camera result
backs it up. The likely cause of a power-on reset in our Live ND work is a detail on this page.

## Open questions

- How big the instruction cache is, and how it is laid out.
- Whether the monitor also watches cores 1 and 2 and the other bus masters.
- What exactly happens on a monitor hit.
- A camera test that touching the byte after a watched range trips it.

## Further reading

- [Caches and the access monitor: technical notes](caches-technical.md) has the cache registers, the routines and the
  monitor's channels.
- [Boot](../guides/boot.md) follows the ten sections as they load.
- [Core communication](../guides/cores.md) covers the uncached shared data between cores.
- [Memory map](memory-map.md) shows the two views of memory.
