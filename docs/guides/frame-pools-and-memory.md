# Frame pools and memory

*Guide 14 · E-M5 III firmware 1.7 · accepted 2026-11-19. New to these guides? Read
[Before you start](before-you-start.md) and [An MN103 primer](mn103-primer.md) first. Open questions:
research gaps.*

This guide covers how the camera's memory is laid out and handed out: the address space, the small heap for ordinary
objects, the frame pools that hold every image buffer, and the spare space we use for our own code. Anyone porting a
feature that needs image memory (Live ND, handheld high res) works with pools from day one.

How sure we are varies by part, so each section says it. How a pool works and how to borrow from one is proven on the
camera: our Live ND builds do it on every shot. The full list of pools is read from the code, not measured. The size of
the RAM is inferred from the pool layout, since nobody has opened the camera to read the chip.

## 1. The address space

The MN103 cores see one 32-bit address space. The parts that matter:

| range | what |
|---|---|
| 0x40000000, 128 MB | the flash chip (firmware and settings) |
| 0x60000000 upwards | RAM, **cached** view: the program, its data, the cores' globals |
| 0xa0000000-0xdfffffff | RAM, **uncached** view: image buffers, shared tables |
| 0x8xxxxxxx / 0x9xxxxxxx | hardware registers and small shared areas (locks, doorbells) |

The same RAM appears twice. 0x6xxxxxxx goes through the CPU's cache and 0xaxxxxxxx doesn't, so an address and the same
address with 0x6 changed to 0xa are the same bytes. The rule is simple: data only the CPU touches is read through the cached view; anything a
hardware block (the image engine, the display, the card controller) also reads or writes is used through the uncached
view, so the CPU never works from a stale cached copy.

How much RAM is there? The firmware's image buffers span about 924 MB, so the camera almost
certainly has **1 GB**. The OM-5 and OM-5 II use the same span; the E-M1 III and OM-1 lay out about twice as much,
which is why the OM-5 is our donor (its buffer design fits).

One trap, found the hard way: plain CPU reads from the main pool's second block (section 6) **rebooted the camera**, even
though the image engine uses that memory without trouble. We treat that block as image-engine only.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| cached / uncached views of the same RAM | 0x6xxxxxxx / 0xaxxxxxxx | [camera] |
| image buffer span | 0xa3f25540-0xdf02e000 (924 MB) | [code] |
| 1 GB of RAM | from the span; no teardown | [inferred] |
| CPU read at 0xc4000000 resets the camera | a Live ND test build | [camera] |
| RAM regions in detail | [memory map](../hardware/memory-map.md#ram-regions-worth-knowing-e-m5-iii) | [code] |

Sources: [memory map](../hardware/memory-map.md), [MN103 CPU: address aliases](../hardware/mn103-cpu.md#address-aliases-cached-and-uncached).
</details>

## 2. Three kinds of memory

The firmware gets memory three ways, and each is for a different size of thing:

| kind | for | how big |
|---|---|---|
| static | the program's own variables, objects created at start-up | fixed when the firmware was built |
| the heap | small objects made while running: messages, records, file buffers | up to 16 KB each, about 786 KB in all |
| frame pools | image data: raw frames, developed images, display layers | up to 33 MB each, most of the RAM |

There is no general allocator for big blocks. Anything bigger than 16 KB comes from a pool, or is a static area.

## 3. The heap

The heap is not the free-list heap you might know from a desktop C library. It is three stocks of fixed-size blocks,
picked by the size you ask for:

| class | for requests up to | blocks |
|---|---|---|
| small | 128 bytes | 178 |
| middle | 2 KB | 21 |
| large | 16 KB | 43 |

Asking for 200 bytes takes a whole 2 KB block. A request over 16 KB fails and returns nothing, with a "Size Over"
message in the log. A free works out the class from the address, so freeing a pointer that didn't come from the heap is
caught and logged.

The heap is shared by all three cores, so every allocation takes one of the
[cross-core lock bits](cores.md#3-lock-bits) and masks interrupts for the moment it takes. That makes it cheap and
safe to call from any task.

```
pseudocode, written from the disassembly (0x600232c5, 0x600235a4)

malloc(size):
    if size <= 128:      class = small
    elif size <= 2048:   class = middle
    elif size <= 16384:  class = large
    else:                log "scheap_phyalloc: Size Over"; return 0
    mask interrupts; take cross-core lock 10
    block = first free block of the class      (0 if the class is empty)
    release lock; restore interrupts
    return block
```

The user shell lists the heap with `sc heaplist` and `sc heapshow`, which is the quickest way to check for a leak.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| malloc / free | 0x600232c5 (742 callers) / 0x600232f7 (759 callers) | [code] |
| class choice, lock, interrupts | 0x600235a4, lock 10 | [code] |
| class tables | bases 0x60027044, counts 0x60027054, block sizes 0x60027084 | [code] |
| areas | small 0xa1ab0fc0, middle 0xa1e80800, large 0xa1cbb540 (all uncached) | [code] |
| a fourth class of 100 small blocks at 0xa26c9500 | not reached by malloc; "custom" or "apim" in the shell | [code]; use open |
| how full it gets in use | not measured | open |

Sources: [memory map: the small-object heap](../hardware/memory-map.md#the-small-object-heap-scheap-2026-11-19).
</details>

## 4. Frame pools

Image memory is handed out by **pools**. A pool is a run of equal-sized buffers ("slots") for one kind of image: the
live-view raw frames, the full-size still frames, the display layers, the face-detection images, and so on. Each kind
has a class number, and the pool for class *c* is entry *c* of a table.

Code borrows a slot by asking the pool, and gets back an **id**: the class in the high byte and the slot number in the
low byte (0x0701 is slot 1 of class 0x07). The id is the handle for everything else: ask the pool for the slot's address,
add a reference if a second user needs it, release it when done. A slot goes back to the pool when its last reference
is released.

```
pseudocode, written from the disassembly (0x603f70f5, 0x603f73e2, 0x603f71fe)

take(key = class << 8, out id):     find a free slot in the class's bitmap, mark it, id = class<<8 | slot
address(id):                         ask the pool object (each class can compute it its own way)
add_reference(id) / release(id):     count users; the slot is free again at zero
```

Two details caught us early on, both now proven on the camera:

- **The key is the class shifted left by 8.** Passing a bare class number asks for class 0, the main still pool, and
  quietly succeeds.
- **Always ask the pool for an address.** Some pools don't place their slots at base + n × size (see section 6).

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| pool table | 0x6053e158, 87 entries (8 bytes per class) | [camera] |
| take / release / add a reference | 0x603f70f5 / 0x603f71fe / 0x603f7350 | [camera] |
| address of an id | 0x603f73e2 | [camera] |
| geometry query | 0x603f77c4 (pool method at vtable +32) | [camera] |
| pool object | +8 base, +12 slot size, +20 free count, +24 count, +64 bitmap | [camera] |

Sources: [memory map: frame pools](../hardware/memory-map.md#frame-pools).
</details>

## 5. Pools share memory

The pools are not carved out of RAM once and for all. The constructors that run at every start build **64 pools**,
and their slots add up to about **4.4 GB**, nearly five times the memory they live in. Most of the buffer area belongs
to several pools at once.

That works because the pools are alternative layouts of the same memory: the slots a still capture uses, the slots
movie recording uses, and the slots a special mode uses overlap, and the camera only ever runs one of those at a time.
A pool's memory is safe to use only while the camera is in a mode that uses that pool and not its neighbours.

This is the part we know least well. We have the full list of pools with their base, slot size and count, read from
the constructor calls. What we don't have is which pools are live in which mode; that has to be worked out pool by pool,
or measured.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| pool constructors | run at every boot from the init array 0x6056bca8 (first entry 0x603f657f) | [code] |
| full pool list, E-M5 III and OM-5 | read from the constructor calls; summary on the [memory map](../hardware/memory-map.md#image-buffer-pool-map-e-m5-iii-vs-om-5-2026-11-12) | [code] |
| 64 pools, ~4.4 GB of slots in 924 MB | same list | [code] |
| which pools are live in which mode | not traced | open |

Sources: [memory map: pool map](../hardware/memory-map.md#image-buffer-pool-map-e-m5-iii-vs-om-5-2026-11-12).
</details>

## 6. The main still pool

Full-size photos are held in the **main pool** (class 0): 20 slots of about 33 MB, each big enough for one raw still.
A burst, a multi-shot mode or a long-exposure noise pass takes several of them.

The main pool is in two blocks, slots 1-8 in one and slots 9-20 in the other, with a gap between them that
belongs to other pools. So "base + n × size" is wrong for slots 9-20. One of our early Live ND builds made exactly this
mistake and wrote 32 MB over memory that wasn't image memory. The pool's own address function knows about the two blocks,
which is why the rule is to always ask it.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| main pool | class 0, 20 × 0x1f47600 bytes; own address method 0x603f9cb7 | [camera] |
| two blocks | slots 1-8 from 0xb0000000, 9-20 from 0xc4000000 (last ends 0xdb758800) | [camera] |
| the two-block bug | Live ND builds E6-E6c; fixed in E6d | [camera] |

Sources: [Live ND](../features/live-nd.md), [memory map: frame pools](../hardware/memory-map.md#frame-pools).
</details>

## 7. Some other pools

A few pools that come up often:

| pool | what | known from |
|---|---|---|
| live-view raw | 4 slots of 16 MB; normal live view alternates the first two ([Live view](live-view.md)) | camera |
| second live-view-sized pool | 4 slots at 0xc4000000, over the main pool's second block; user unknown | code |
| display and on-screen layers | full-HD display buffers, four OSD layers | code |
| face detection | 11 VGA images | code |
| Tripod High Res | 8 frames | code |
| descriptors, metadata | small per-shot records | camera |

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| live-view raw | 0x0700: 4 × 0xfe4c00 at 0xaa91d340 | [camera] |
| second pool | 0x3900: 4 × 0xfe4c00 at 0xc4000000 | [code] |
| display / OSD | 0x0a00, 0x0e00, 0x0f00 / 0x0b00, 0x0c00, 0x0d00 | [code] |
| face detection | 0x2c00, 11 × 640×480 at 0xddf7b000 | [code] |
| Tripod High Res | 0x4f00 | [code] |
| descriptors / metadata | class 0x15 at 0xaeb333c0 (64) / 0xae95d740 (20) | [camera] |

Sources: [memory map: frame pools](../hardware/memory-map.md#frame-pools), [display](../hardware/display.md).
</details>

## 8. Room for our own code

The program is loaded into RAM in sections (see [Boot](boot.md)), and each section is followed by unused space, filled
with 0xFF in the firmware file. That space is where our code goes. The loader copies each section up to an end address
written into its code, so raising that one number makes the space after a section load with it.

Two kinds of space matter:

- **Always ready.** The first part of the program is copied before anything runs. Boot guards and tiny stubs that may
  run at any time live in its tail, which is nearly full.
- **Loaded in the background.** The other sections arrive while the camera starts. Code there may only run once its
  section is in, so every hook into it is guarded by a "section ready" check.

Each feature gets its own region so builds can be stacked: Live ND in the slack after section 4, handheld high res at
the top of section 9, the dev settings page after section 10. Several more gaps are mapped in the code but not yet
tried on the camera.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| always-ready tail | 0x600d009a-0x600d0800 | [code]; in use [camera] |
| section end constants | loader switch 0x60045dc5 (section 4 at 0x60045deb, section 9 at 0x60045e13, section 10 at 0x60045e24) | [camera] |
| regions per feature, measured use | [memory map: spare space](../hardware/memory-map.md#spare-space-for-our-code) | [camera] / [code] |
| untried gaps after sections 1, 3, 5, 6, 7, 8 | same table | [code] |

Sources: [memory map](../hardware/memory-map.md#spare-space-for-our-code), [boot and sections](../firmware/boot-and-sections.md).
</details>

## How our features use this

- **Live ND borrows main frames.** The capture takes its frames from the main pool and gives them back at the end; the
  live preview keeps a window of recent frames in main-pool slots too. The OM-5 has dedicated pools for this; on the
  E-M5 III we use the native main pool through its own functions rather than adding pools.
- **No new pool ids.** The table size (87) is written into at least ten places in the code, and the donor's ids don't
  fit it, so a donor's extra pools can't simply be added. A port writes small adapters over the existing pools instead.
- **Handheld high res** on the OM-5 uses its own buffers (a 12-frame pool and three more, about 640 MB). The port plan
  lays out its own buffers in the main-pool memory through the same kind of adapter; which pools are free while it
  runs still needs a camera census.
- **The second-block rule.** Our code never reads the main pool's second block with the CPU; only the image engine touches it.
- **Each feature its own region** of spare space, recorded in the memory map, so two features never overwrite each
  other's code.

## Checked on other cameras

Each step checked against the firmware of other bodies. Nothing is assumed: "not checked" means we don't know.

| step | E-M5 III 1.7 | OM-5 1.2 | E-M1 III 1.6 | OM-5 II 1.1 | OM-1 1.9 | PEN-F 3.1 | other projects |
|---|---|---|---|---|---|---|---|
| RAM class (from the buffer span) | 1 GB | **confirmed** 1 GB, laid out differently | **different**: 2 GB | **confirmed** 1 GB | **different**: 2 GB | not checked | — |
| heap (`scheap`, three classes) | yes | **confirmed** (same block sizes) | **confirmed** | **confirmed** | **different**: same name, block-size table not found | **different**: same name, block-size table not found | — |
| pool table and pool API | yes, 87 entries | **confirmed**, 113 entries | not checked | not checked | not checked | not checked | — |
| pools built by constructors at boot | 64 pools | **confirmed**, 87 pools | not checked | not checked | not checked | not checked | — |
| main still pool | 20 slots, two blocks | **different**: 18 slots, plus a 19-slot Live ND layout | not checked | not checked | **different**: larger, 0xb8000000-0xff124000 | not checked | — |
| dedicated Live ND preview pools | none | **different**: 248-slot ring | not checked | not checked | not checked | not checked | — |

Sources: [memory map](../hardware/memory-map.md).
