# Caches and the access monitor: technical notes

> **Technical notes.** This page is the dense reference. For a readable introduction, start with [Caches and the access monitor](caches.md).

How the E-M5 Mark III's MN103 control cores cache memory, how the firmware writes caches back and invalidates them, how
it keeps the three cores and the ARM helper in step, and the hardware access monitor the boot uses to guard memory.
Everything here was read from the firmware's own code (E-M5 III firmware 1.7, block 0, addresses are where the code
runs). Each fact is tagged: **[code]** means the instructions show it directly, **[inferred]** means it is our reading
of what the hardware does, **[camera]** means a test on the camera showed it. Survey of 2026-11-22.

## In short

- Each MN103 core has its own **8 KB data cache: 2 ways, 256 sets, 16-byte lines**, write-back. [code]+[inferred]
- RAM is visible twice: **0x6xxxxxxx through the cache, 0xaxxxxxxx uncached**, same bytes. [camera]
- The hardware does **not** keep the cores' caches coherent. The firmware puts shared data in the uncached view, and
  where it does share through the cache (messages to the ARM helper) it writes lines back by hand. [code]+[inferred]
- The **instruction cache is invalidated only when a core starts**. No routine in block 0 invalidates it later. [code]
- During start-up a hardware **access monitor** watches the parts of the program that have not finished loading. Its end
  address is **inclusive**. [code]

## The cache control register (CHCTR, 0x8070)

A 16-bit register at absolute address 0x8070. Each core sees its own copy. The core's number (0, 1 or 2) is at 0x8050.
[code]

| bit | mask | what the code does with it | meaning |
|---|---|---|---|
| 0 | 0x01 | set at core start | instruction cache on [inferred] |
| 1 | 0x02 | set at core start; cleared while the code edits data-cache tags, set again after | data cache on [code] |
| 3 | 0x08 | polled until 0 after bit 1 is cleared | data cache busy [code] |
| 4 | 0x10 | written once, at core start (CHCTR = 0x30, then 3) | invalidate instruction cache [inferred] |
| 5 | 0x20 | at core start, and at the end of the whole-cache routine | invalidate data cache [inferred] |

The bit layout matches the AM33 family's published CHCTR layout, which is where the names come from. Nothing in block 0
ever sets the upper bits (the write-mode bits on AM33), so the caches run in their reset mode, write-back by our
reading. [inferred]

Each core starts the same way: interrupts off, `CHCTR = 0x30`, `CHCTR = 3`, then bit 4 set in its own bus register
0x98100408 (core 1, 0x6002731c) or 0x98100808 (core 2, 0x60027791). [code]

## The data cache

**Geometry.** 2 ways x 256 sets x 16 bytes = 8 KB. Each way has a tag array of one word per line: way 0 at 0x28900000,
way 1 at 0x28980000, 0x1000 bytes each. A line's set is `address & 0xff0` and its tag is `address & 0xfffff000`, and
tag bit 0 means valid. Writing 0x20000000 (or 0) to a tag throws the line away. [code] (0x61206803 compares
`(tag ^ address) & 0xfffff000` and tests bit 0.)

**Write-back regions.** The code writes dirty lines back by **reading** special regions [inferred: read and discarded,
the only use is a side effect]:
- 0x28a00000 and 0x28a80000: the whole-cache routine reads every word of 4 KB from each (one region per way). [code]
- 0x28b00000 + set and 0x28b80000 + set (one per way): the second whole-cache routine reads one word per line; the
  by-address routine **writes** `address | mode` there for each line, mode 0 or 1. [code] Which mode also drops the
  line is [inferred].

The cache arrays end at 0x28b80fff: the monitor's guard window starts at 0x28b81000 (see below). [code]

## Cache routines

| address | what it does | callers |
|---|---|---|
| **0x600644ae** | whole data cache, current core: critical section; data cache off; wait busy; read 0x28a00000/0x28a80000 (write back); set bit 4 of this core's bus register (0x98100000 + 0x400 x core) and wait for it to clear; mark every tag invalid; CHCTR \|= 0x20, then \|= 2 | 21 (settings save, section-9 ready hook 0x60199e23, others) [code] |
| 0x61206703 | whole data cache, current core: data cache off, wait busy, read 0x28b00000/0x28b80000 per line, invalidate all tags, back on | range routines when the range is over 8 KB [code] |
| 0x612067ef / 0x612067f9 | write back a range, mode 0 / 1, 16 bytes at a time (0x6120675a) | ISC message layer [code] |
| 0x61206803 | discard a range: drop each valid line whose tag matches, no write-back | ISC message layer [code] |
| 0x61206899 | drain: bit 4 in this core's bus register, then in the four bus buffers 0x98100c00-0x98100c0c, waiting for each to clear | 0x6120698c [code] |
| 0x612068d5 | drain or invalidate for one address range (see bus buffers) | 0x6120696e (bit 4), 0x61206978 (bit 4), 0x61206982 (bit 0) [code] |

The range routines act only on the cached view (0x60000000-0x7fffffff); for any other address they return at once.
[code] They live in the ISC library (the MN103 to ARM mailbox, dispatcher 0x61206cfe), which wraps them with interrupts
masked: clean = write back + drain (0x612069ac, 0x61206a0b), invalidate = discard + bus bit 0 (0x61206a60), full =
write back + drain + invalidate (0x6120698c). [code]

## Bus buffers (0x98100000 block)

Between the cores and memory there are buffers the code has to drain as well. [inferred]
- **One register per core** at 0x98100000 + 0x400 x core. Setting bit 4 starts a drain and the bit clears when it is
  done. Bit 0 is used the same way by the invalidate path. Offset +8 gets 0x10 when a core starts. [code] What the
  buffers are (write buffers, read prefetch) is [inferred].
- **Four address-window buffers** at 0x98100c00-0x98100c0c, with window starts at 0x98100c10.. and ends at
  0x98100c20.. . For an uncached range (0xa0000000-0xbfffffff), 0x612068d5 drains only the windows that overlap the
  range, in **64-byte units** (`& 0x1fffffc0`). [code] So uncached writes are not always on their way to memory
  straight away, and code that hands a buffer to another bus master has to drain it. [inferred]

## Sharing between cores, the ARM helper and DMA

- **Cores 0, 1 and 2:** each cache routine works on the calling core only, by core number. Nothing found snoops or
  flushes another core's cache. Stock code keeps shared data (kernel objects, call rings, lock bits) in the uncached
  view. [code] for the routines, [inferred] for "no hardware coherence".
- **ARM helper (ISC mailbox):** the ISC library writes back and drains message buffers before the ARM reads them, and
  discards lines before the MN103 reads the ARM's reply. [code]
- **Image engine, display, card:** buffers they use are reached through the uncached view, so no cache maintenance is
  needed for them. [code]+[camera] (a card log written from an uncached buffer came out empty for another reason, see
  gotchas)
- **Code written at run time:** 0x600644ae writes back and invalidates the **data** cache only. The instruction cache
  is invalidated only at core start, so code changed while running can still execute from old cached lines on that
  core until they are evicted. Writing a hook through the uncached view, first byte last, inside one 16-byte line, keeps
  every possible mix of old and new lines safe. [code]+[inferred]

## The access monitor (0x99700000)

A hardware block that watches address ranges and stops the camera on an access inside one. [code] Reading it:
- **Registers.** 0x99700000 control (bits 0-1 cleared before changes), 0x99700004 one enable bit per channel,
  0x99700010-0x9970001c per-group settings (bits 16 and 17 = watch reads, watch writes [inferred]; low 5 bits
  cleared by the boot), and two sets of four channels: **start at 0x99700040 + 8n, end at 0x99700044 + 8n**, and a
  second set at 0x99700060 + 8n. Driver 0x60065a6a, channel writer 0x60066195. [code]
- **The end address is inclusive.** The firmware's own permanent table (0x600c07f0, programmed by 0x600659d0 once
  start-up is done) gives ranges like 0x00000000-0x00007fff, 0x0000a000-0x1fffffff, 0x38000000-0x3fffffff,
  0x47002000-0x5fffffff and 0x28b81000-0x46ffffff: every end is the last byte. [code]
- **Addresses are folded before programming.** The loader passes each bound through 0x600645aa, which turns an
  uncached 0xa... address into its 0x6... twin (and 0x80xxxxxx into 0x40xxxxxx). So the monitor compares one address
  per byte of RAM, and an access through either view should match. [code] for the folding, [inferred] for the match.
- **After start-up** it permanently guards the unmapped gaps of the address map (the table above). The gaps show that
  the small fast memory at 0x47000000 is 8 KB (0x47000000-0x47001fff: the guard starts at 0x47002000), that
  0x8000-0x9fff (system registers) is real, and where the cache arrays end. [code] The fourth entry of the second set
  (0x60000200, 0x0037c1ff) does not read as an address range yet. [open]
- **During start-up**, after each block-0 section n < 10 is finished, the loader (0x60045eb3, 0x60045fb0) programs
  channel 3 to cover **start of section n+1 .. end of section 10**, reads and writes, so nothing touches code that is
  still loading; after section 10 it switches to the permanent table (0x60045eed -> 0x60065f63 -> 0x60065991).
  [code] The end it passes is the section's end address as the loader uses it (the first byte after the section), so
  with the inclusive compare **the monitor also covers the first byte after section 10**. [code]+[inferred]
- What a hit does is not traced yet. The driver has a status printer (0x600661be, strings "read"/"write"). Camera
  builds that touched a still-loading section boot-looped. [camera]

## What this means for patches

- Leave a gap after any section end. The start-up monitor covers the byte after section 10 too, so a raised section
  end must not land on memory that anything reads while the camera starts. Keep at least 16 bytes free, and better a
  4 KB page (the project's margin rule). [inferred]
- Put data shared with another core or a DMA block in the uncached view, or write back and drain it by hand with the
  ISC-style sequence. [code]
- Write code through the uncached view, first byte last, inside one 16-byte line, and don't count on 0x600644ae to
  clear the instruction cache. [code]+[inferred]

## Still open

- Instruction cache size and layout: no code touches its tags, so it is not visible from block 0.
- What the bus registers' bits 0 and 4 do exactly, and what the four address-window buffers belong to.
- Whether the access monitor sees cores 1 and 2 and the DMA masters, and what it does on a hit (NMI, reset).
- The second monitor channel set (0x99700060) and its odd fourth entry. [inferred]
- A camera check that an access to the byte after a monitored range trips the monitor.

