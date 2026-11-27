# Caches and the access monitor: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Caches and the access monitor](caches.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

This page covers how the E-M5 Mark III's MN103 control cores cache memory, and how the firmware writes caches back and
invalidates them. It also covers how the firmware keeps the three cores and the ARM helper in step, and the hardware
access monitor the boot uses to guard memory.

Everything here was read from the firmware's own code, in E-M5 III firmware 1.7, block 0. Addresses are where the code
runs. Function addresses are in the [address reference](#address-reference).

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred, our reading of what the hardware does.

## Summary

- Each MN103 core has its own **8 KB data cache: 2 ways, 256 sets, 16-byte lines**, write-back.[^fw1][^inf1]
- RAM is visible twice, **`0x6xxxxxxx` through the cache and `0xaxxxxxxx` uncached**, with the same bytes.[^cam1]
- The hardware does **not** keep the cores' caches coherent. The firmware puts shared data in the uncached view. Where
  it does share through the cache, in messages to the ARM helper, it writes lines back by hand.[^fw1][^inf1]
- The **instruction cache is invalidated only when a core starts**. No routine in block 0 invalidates it later.[^fw1]
- During start-up a hardware **access monitor** watches the parts of the program that have not finished loading. Its
  end address is **inclusive**.[^fw1]

## Cache control register (CHCTR)

CHCTR is a 16-bit register at absolute address `0x8070`. Each core sees its own copy. The core's number (0, 1 or 2)
is at `0x8050`.[^fw1]

| bit | mask | what the code does with it | meaning |
|---:|---|---|---|
| 0 | `0x01` | set at core start | instruction cache on[^inf1] |
| 1 | `0x02` | set at core start. Cleared while the code edits data-cache tags, set again after. | data cache on[^fw1] |
| 3 | `0x08` | polled until 0 after bit 1 is cleared | data cache busy[^fw1] |
| 4 | `0x10` | written once, at core start (CHCTR = `0x30`, then 3) | invalidate instruction cache[^inf1] |
| 5 | `0x20` | at core start, and at the end of the whole-cache routine | invalidate data cache[^inf1] |

*CHCTR bits and how the firmware uses them.*

The bit layout matches the AM33 family's published CHCTR layout, which is where the names come from. Nothing in block 0
ever sets the upper bits, which are the write-mode bits on AM33. So the caches run in their reset mode, write-back by
our reading.[^inf1]

Each core starts the same way.[^fw1]

1. Interrupts off.
2. `CHCTR = 0x30`.
3. `CHCTR = 3`.
4. Bit 4 set in its own bus register, `0x98100408` for core 1 or `0x98100808` for core 2.

## Data cache

**Geometry.** 2 ways × 256 sets × 16 bytes = 8 KB.[^fw1]

- Each way has a tag array of one word per line. Way 0 is at `0x28900000` and way 1 at `0x28980000`, `0x1000` bytes
  each.
- A line's set is `address & 0xff0` and its tag is `address & 0xfffff000`. Tag bit 0 means valid.
- Writing `0x20000000` (or 0) to a tag throws the line away.

The discard routine shows this. It compares `(tag ^ address) & 0xfffff000` and tests bit 0.[^fw1]

**Write-back regions.** The code writes dirty lines back by **reading** special regions. The reads are discarded, and
their only use is a side effect.[^inf1]

- `0x28a00000` and `0x28a80000`, one region per way. The whole-cache routine reads every word of 4 KB from each.[^fw1]
- `0x28b00000` + set and `0x28b80000` + set, one per way. The second whole-cache routine reads one word per line. The
  by-address routine **writes** `address | mode` there for each line, with mode 0 or 1.[^fw1] Which mode also drops
  the line is inferred.[^inf1]

The cache arrays end at `0x28b80fff`. The monitor's guard window starts at `0x28b81000`, as described under
[The access monitor](#the-access-monitor-0x99700000).[^fw1]

## Cache routines

| routine | what it does | callers |
|---|---|---|
| **whole data cache, current core** | critical section. Data cache off, wait busy, read `0x28a00000`/`0x28a80000` (write back). Set bit 4 of this core's bus register (`0x98100000` + `0x400` × core) and wait for it to clear. Mark every tag invalid. CHCTR \|= `0x20`, then \|= 2. | 21, among them the settings save and the section-9 ready hook |
| second whole-cache routine, current core | data cache off, wait busy, read `0x28b00000`/`0x28b80000` per line, invalidate all tags, back on | range routines when the range is over 8 KB |
| write back a range, mode 0 / 1 | 16 bytes at a time | ISC message layer |
| discard a range | drop each valid line whose tag matches, no write-back | ISC message layer |
| drain | bit 4 in this core's bus register, then in the four bus buffers `0x98100c00`–`0x98100c0c`, waiting for each to clear | the full routine |
| drain or invalidate one address range | see [Bus buffers](#bus-buffers) | three wrappers, two with bit 4 and one with bit 0 |

*Cache routines.[^fw1] Their addresses are in the [address reference](#address-reference).*

The range routines act only on the cached view (`0x60000000` to `0x7fffffff`). For any other address they return at
once.[^fw1]

They live in the ISC library, the MN103 to ARM mailbox. The library wraps them with interrupts masked.[^fw1]

- Clean = write back + drain.
- Invalidate = discard + bus bit 0.
- Full = write back + drain + invalidate.

## Bus buffers

Between the cores and memory there are buffers the code has to drain as well.[^inf1] They sit in the `0x98100000`
block.

- **One register per core** at `0x98100000` + `0x400` × core. Setting bit 4 starts a drain, and the bit clears when it
  is done. Bit 0 is used the same way by the invalidate path. Offset +8 gets `0x10` when a core starts.[^fw1] What the
  buffers are, write buffers or read prefetch, is inferred.[^inf1]
- **Four address-window buffers** at `0x98100c00`–`0x98100c0c`. Their window starts are at `0x98100c10` on and their
  ends at `0x98100c20` on. For an uncached range (`0xa0000000` to `0xbfffffff`), the range routine drains only the
  windows that overlap the range, in **64-byte units** (`& 0x1fffffc0`).[^fw1]

So uncached writes are not always on their way to memory straight away. Code that hands a buffer to another bus master
has to drain it.[^inf1]

## Sharing between cores, the ARM helper and DMA

- **Cores 0, 1 and 2.** Each cache routine works on the calling core only, by core number. Nothing found snoops or
  flushes another core's cache. Stock code keeps shared data (kernel objects, call rings, lock bits) in the uncached
  view.[^fw1] So there is no hardware coherence.[^inf1]
- **ARM helper (ISC mailbox).** The ISC library writes back and drains message buffers before the ARM reads them. It
  discards lines before the MN103 reads the ARM's reply.[^fw1]
- **Image engine, display, card.** The buffers they use are reached through the uncached view, so they need no cache
  maintenance.[^fw1][^cam3]
- **Code written at run time.** The main whole-cache routine writes back and invalidates the **data** cache only. The
  instruction cache is invalidated only at core start. So code changed while running can still execute from old
  cached lines on that core until they are evicted.[^fw1] Writing a hook through the uncached view, first byte last,
  inside one 16-byte line, keeps every possible mix of old and new lines safe.[^inf1]

## The access monitor (0x99700000)

The access monitor is a hardware block that watches address ranges and stops the camera on an access inside
one.[^fw1]

**Registers.**[^fw1]

| register | use |
|---|---|
| `0x99700000` | control. Bits 0-1 are cleared before changes. |
| `0x99700004` | one enable bit per channel |
| `0x99700010`–`0x9970001c` | per-group settings. Bits 16 and 17 watch reads and writes.[^inf1] The boot clears the low 5 bits. |
| `0x99700040` + 8n / `0x99700044` + 8n | **start / end** of channel n, first set of four channels |
| `0x99700060` + 8n | second set of four channels |

*Access monitor registers.*

**The end address is inclusive.** The firmware's own permanent table is programmed once start-up is done.[^fw1] It
gives ranges like these, and every end is the last byte.

- `0x00000000`–`0x00007fff`
- `0x0000a000`–`0x1fffffff`
- `0x38000000`–`0x3fffffff`
- `0x47002000`–`0x5fffffff`
- `0x28b81000`–`0x46ffffff`

**Addresses are folded before programming.** The loader passes each bound through a fold routine. It turns an uncached
`0xa…` address into its `0x6…` twin, and `0x80xxxxxx` into `0x40xxxxxx`.[^fw1] So the monitor compares one address per
byte of RAM, and an access through either view should match.[^inf1]

**After start-up** the monitor permanently guards the unmapped gaps of the address map, as in the table above. The gaps
show three things.[^fw1]

- The small fast memory at `0x47000000` is 8 KB (`0x47000000`–`0x47001fff`), because the guard starts at
  `0x47002000`.
- `0x8000`–`0x9fff` (system registers) is real.
- Where the cache arrays end.

The fourth entry of the second set (`0x60000200`, `0x0037c1ff`) does not read as an address range yet.

**During start-up** the loader programs channel 3 after each block-0 section n < 10 is finished. The channel then
covers **the start of section n+1 to the end of section 10**, for reads and writes, so nothing touches code that is
still loading. After section 10 the loader switches to the permanent table.[^fw1]

The end the loader passes is the section's end address as the loader uses it, the first byte after the
section.[^fw1] With the inclusive compare, **the monitor also covers the first byte after section 10**.[^inf1]

What a hit does is not traced yet. The driver has a status printer, with the strings "read" and "write".[^fw1] Camera
builds that touched a still-loading section boot-looped.[^cam2]

## Rules for patches

- **Leave a gap after any section end.** The start-up monitor covers the byte after section 10 too. So a raised
  section end must not land on memory that anything reads while the camera starts. Keep at least 16 bytes free, and
  better a 4 KB page, the project's margin rule.[^inf1]
- **Share data with care.** Put data shared with another core or a DMA block in the uncached view, or write it back
  and drain it by hand with the ISC-style sequence.[^fw1]
- **Write code safely.** Write code through the uncached view, first byte last, inside one 16-byte line. Don't count on
  the whole-cache routine to clear the instruction cache.[^fw1][^inf1]

## Open questions

- The instruction cache size and layout. No code touches its tags, so it is not visible from block 0.
- What the bus registers' bits 0 and 4 do exactly, and what the four address-window buffers belong to.
- Whether the access monitor sees cores 1 and 2 and the DMA masters, and what it does on a hit (NMI, reset).
- The second monitor channel set (`0x99700060`) and its odd fourth entry.[^inf1]
- A camera check that an access to the byte after a monitored range trips the monitor.

## Address reference

E-M5 III 1.7 block 0 addresses.

| item | address |
|---|---|
| CHCTR | `0x8070` |
| core number | `0x8050` |
| core 1 / core 2 start | `0x6002731c` / `0x60027791` |
| core 1 / core 2 bus register (+8) | `0x98100408` / `0x98100808` |
| data-cache tags, way 0 / way 1 | `0x28900000` / `0x28980000` |
| whole-cache write-back regions | `0x28a00000`, `0x28a80000` |
| per-line write-back regions | `0x28b00000`, `0x28b80000` |
| whole data cache, current core | **`0x600644ae`** |
| section-9 ready hook (a caller) | `0x60199e23` |
| second whole-cache routine | `0x61206703` |
| write back a range, mode 0 / 1, line step | `0x612067ef` / `0x612067f9`, `0x6120675a` |
| discard a range | `0x61206803` |
| drain, called from | `0x61206899`, from `0x6120698c` |
| drain or invalidate one range, wrappers | `0x612068d5`, from `0x6120696e` (bit 4), `0x61206978` (bit 4), `0x61206982` (bit 0) |
| ISC dispatcher | `0x61206cfe` |
| ISC clean / invalidate / full | `0x612069ac`, `0x61206a0b` / `0x61206a60` / `0x6120698c` |
| bus registers, one per core | `0x98100000` + `0x400` × core |
| address-window buffers, starts, ends | `0x98100c00`–`0x98100c0c`, `0x98100c10`…, `0x98100c20`… |

*Cache registers and routines.*

| item | address |
|---|---|
| access monitor block | `0x99700000` |
| monitor driver, channel writer | `0x60065a6a`, `0x60066195` |
| permanent table, programmed by | `0x600c07f0`, `0x600659d0` |
| bound fold routine | `0x600645aa` |
| start-up loader (channel 3) | `0x60045eb3`, `0x60045fb0` |
| switch to the permanent table | `0x60045eed` → `0x60065f63` → `0x60065991` |
| status printer | `0x600661be` |

*Access monitor.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware, survey of 2026-11-22. The instructions show it directly.
[^inf1]: Inferred, 2026-11-22. Our reading of what the hardware does.
[^cam1]: Seen on our E-M5 III.
[^cam2]: Seen on our E-M5 III with test builds.
[^cam3]: Seen on our E-M5 III. A card log written from an uncached buffer came out empty for another reason, see [gotchas](../reference/gotchas.md).

