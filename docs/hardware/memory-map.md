# Memory map: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Frame pools and memory](../guides/frame-pools-and-memory.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

This page is a guide to where things are in the E-M5 III's flash and RAM. It covers how much memory each camera has,
how the 128 MB flash chip is divided and the RAM regions that matter when patching. It also covers how the camera hands
out frame buffers ("frame pools") and which spare regions we use for our own code.

A few terms used below:

- **Flash** holds the firmware permanently. **RAM** (DRAM) is the working memory, about 1 GB on this camera.
- **Cached and uncached.** The same RAM is visible at two addresses. `0x6xxxxxxx` is the cached view and `0xaxxxxxxx`
  the uncached view.[^cam1] See also: [MN103 CPU](mn103-cpu.md#address-aliases-cached-and-uncached).
- **Block0** is the main program in the firmware file. At boot it is copied into RAM in "sections" (see
  [boot](../firmware/boot-and-sections.md)).
- **Slack** is unused space (`0xff` bytes) after the end of a section. We use it for our own code.[^fw1]

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred or seen in an emulator.

## How much memory each camera has

The firmware sets out its image buffers in a fixed map, which tells us roughly how big the RAM is.

| body | buffer map | class |
|---|---|---|
| E-M5 III 1.7 | `0xa3f25540`-`0xdf02e000` (924 MB), inside the uncached window `0xa0000000`-`0xdfffffff` | **1 GB** |
| OM-5 1.2 | same start and end, laid out differently (frees `0xc0000000`-`0xc4000000`, adds 21 MB at `0x9ca3b000`) | 1 GB |
| OM-5 II 1.1 | same as OM-5 | 1 GB |
| E-M1 III 1.6 | `0x84000000`-`0xfbbf9000` (about 1.8 GB) | 2 GB |
| OM-1 / OM-1 II | about 1.5 GB of buffers, main pool `0xb8000000`-`0xff124000` | 2 GB |

*Buffer maps by body. The maps are read in the firmware.[^fw1] The class (physical DRAM size) is inferred.[^inf1]*

This is why we port from the OM-5. It has the same 1 GB layout, so **the OM-5 1.2 is the memory model for
ports**.[^pol1] The E-M1 III and OM-1 buffer designs need twice the memory and don't fit.

## Flash layout (E-M5 III)

The flash is 128 MB. The driver names it `0x40000000`-`0x47ffffff`, with an alias at `0x80000000`. These names are not
CPU-readable memory.[^fix1]

| range | what |
|---|---|
| `0x40000000`-`0x40060000` | boot area before block0. Written only by an update of kind BOOT, and not in our .BIN files |
| `0x40060000`-`0x40780000` | data window (settings bulk at `0x406a0000`, `0x40700000`, `0x40740000`) |
| `0x40780000`-`0x41f60000` | block0 (USR), the main program |
| `0x41f60000`-`0x42160000` | data window |
| `0x42160000`-`0x43f60000` / `0x43f60000`-`0x47160000` | block1 OSD (GUI resources) / block2 RESCOM (resources) |
| `0x47180000`-`0x47a80000` | block4 PIC |
| `0x47a80000`-`0x48000000` | data windows (`0x47a80000`, `0x47b80000`) |

*Flash layout of the E-M5 III, by driver address.[^fw2]*

### Write guard

Outside a firmware update, any write outside the three data windows trips a guard. The guard starts the watchdog and
spins until the camera resets.[^fw3]

| window | notes |
|---|---|
| `0x40060000`-`0x40780000` | |
| `0x41f60000`-`0x42160000` | |
| `0x47a80000`-`0x47b80000` | |
| `0x47b80000`-`0x48000000` | also covers the bad-block spare pool (`0x47c00000`-`0x47ebffff`) and the three bad-block table copies (`0x47ec0000`-`0x47f1ffff`), which the guard does not protect |

*Flash data windows that the write guard allows.[^fw3][^fw2]*

> [!WARNING]
> Never write at or above `0x47c00000`. The bad-block spare pool and the bad-block tables live there, and the write
> guard does not protect them.

The flash addresses are names for the driver only. The CPU never reads them as memory, and the access monitor guards
the range.[^fw2] See also: [Memory and storage controllers](memory-and-storage-technical.md).

### Flash wear

- The chip is raw NAND behind a controller. It is read in 2 KB pages and erased in 128 KB blocks.[^fw4]
- The firmware keeps a bad-block table ("BadBlockManagementTable", "Bad Block Hassei ERASE/WRITE").[^fw4]
- The part number is not known. No datasheet name or ID table was found in block0.[^fw4]
- Each page has 128 spare bytes. Error correction (ECC) works in 1 KB sectors, at least 14 bits each.[^fw2][^inf3] There are 22 spare
  blocks. A block moves to a spare after a read with more than 13 corrected bits.[^fw2] See also:
  [Memory and storage controllers](memory-and-storage-technical.md), for the driver and the table.
- 128 MB with 2 KB pages and 128 KB blocks is the usual 1 Gbit single-level cell (SLC) geometry. Such parts are rated about 60,000 to
  100,000 erase cycles per block (with ECC).[^inf2]
- A card update erases each written component range once, then programs and reads it back. Only the BOOT kind compares
  and skips equal data, and our files have no BOOT part. So one full flash costs one erase cycle on each block of USR,
  OSD, RESCOM and PIC.[^fw5] The boot-area stage-2 updater used by hold-OK is assumed to do the same.[^inf3]
- So the chip should take tens of thousands of full flashes. Wear is not a practical limit. A power cut while block0 is
  written is the real risk.[^inf3]
- The OM-5 rotates its settings banks after 40,000 writes. That hints that Olympus budgets at least that many cycles per
  block.[^inf3]

## RAM regions worth knowing (E-M5 III)

<details><summary>RAM regions and hardware blocks, 25 rows</summary>

| region | what |
|---|---|
| `0x60030000`-`0x600d0800` | copied by the boot stub, so always ready. Holds our state table and boot guards |
| `0x600de000`-`0x613fe800` | block0 sections 1-10, loaded in the background ([boot](../firmware/boot-and-sections.md)) |
| `0x62000000` and up | RAM globals (the Ghidra RAM block, size assumed) |
| `0x62fe0000` (+128 KB) | memory shared with the ARM (ISC) |
| `0x8ff00c00` | ISC control blocks |
| `0x8fe00000`-`0x8fe0003f` | 64 cross-core lock bits (`bset`/`bclr`) ([SoC overview](soc-overview-technical.md#communication-between-cores)) |
| `0x99200400` / `0x99300400` / `0x99b00400` | inter-core interrupt (doorbell) registers of CPU0 / CPU1 / CPU2 |
| `0x9ba00000`-`0x9ba004c0` | shutter (MECHA) block, used only by the mec driver `0x600e0000`-`0x600ef000`[^fw2] ([shutter](shutter-technical.md#the-hardware-block)) |
| `0x99000000` / `0x9a300000` | SD host port 0 (card slot, UHS-II link `+0x2200`, PHY `+0x6000`) / port 1 (Wi-Fi SDIO). DMA `+0x0`, SD core `+0x2000`[^fw2] ([still image back end](../firmware/still-backend-technical.md#sd-host)) |
| `0x9b900000`-`0x9b90009c` | flash timing block (strobe), driver `0x60170e30`-`0x60172573`, IRQ line 1[^fw2] ([flash](flash-technical.md#the-flash-timing-block-0x9b900000)) |
| `0x9b700000` | CIC raw (ORF) compression block, driver `0x60c22aed`[^fw2] |
| `0x99900000` / `0x99901000` | JPEG codec. Common `+0x00` interrupt ack, `+0x08` enable. Codec registers at `0x99901000` (Huffman `+0x200`-`+0x800`, quantisation `+0xc00`/`+0xc80`), interrupt line 146[^fw2] ([still image back end](../firmware/still-backend-technical.md#jpeg)) |
| `0xa2623fdc`-`0xa26248f2` | cross-core call rings (9 × 32 entries) and their indexes[^fix2] |
| `0xa26248f4`-`0xa2624f00` | task-level cross-core call slots and the CPUCALL queue ids ([CPU1 and CPU2](cpu1-cpu2-technical.md#memory-each-core-uses)) |
| `0xa25ea2c8`-`0xa25ebf6c` | remote kernel-call and message slots, 52 bytes each, per core |
| `0x61f27680`-`0x62078680` | task stack pools: CPU0 `+0xb1000`, CPU1 `0x61fd8680` `+0x70000`, CPU2 `0x62048680` `+0x30000`[^fw2] |
| `0x62078f40`-`0x6207cf40` | debug-task stacks (CPU0, CPU1), then system stacks CPU0 8 KB, CPU1 2 KB, CPU2 2 KB |
| `0x6207cf40` / `0x6253c580` / `0x62559480` | kernel data of CPU0 / CPU1 / CPU2 (about 81 / 52 / 29 KB) |
| `0x620a2000`-`0x62527100` | BSS cleared by CPU1 at its reset. CPU0 clears `0x61f22900`-`0x61f27670` and `0x62527100`-`0x626b0888` |
| `0xa1483000`-`0xa1484800` | 6 KB core library staged by CPU0, copied by every core into its local page `0x47000800` at start. Keep a margin from it |
| `0x47000000`-`0x47001800` | each core's local page: early stack below `0x47000800`, library above |
| `0x99200000` / `0x99300000` / `0x99b00000` | per-core SoC interrupt controller. One word per line (182 lines, bit = level), pending line per level at `+0x300` + 4L[^fw2] ([interrupts](interrupts-timers-dma-technical.md)) |
| `0x98900000` | timer block, 28 channels. `+0x14c` free-running counter[^fw2] ([interrupts, timers](interrupts-timers-dma-technical.md#timers)) |
| `0xa0000000`-`0xdfffffff` | uncached image window (cached alias `0x6xxxxxxx` for the low parts) |
| `0xa411f540`-`0xa4277140` | the camera's own image-engine job programs 0-10 |
| `0xa4277140`-`0xa42bf540` | 296 KB with no code references (a candidate home for donor job programs) |
| `0xa07b4800`-`0xa07b6000` | Live ND's "M" block (uncached view of section-4 slack) |

*RAM regions and hardware blocks of the E-M5 III.*

</details>

## Frame pools

The camera doesn't hand out image memory freely. It keeps "pools" of fixed-size buffers, one pool per kind ("class")
of buffer. Code asks a pool for a buffer by key and gets back an id. Live ND and Handheld High Res (HHHR) both need to borrow
frames this way.

**How to use a pool.**[^cam1]

- The pool table has one 8-byte entry per class.
- Acquire with the acquire function (d0 = key, a0 = pointer to a u16 id). Look up the address with the lookup function
  (d0 = id). Release with the release function (d0 = id).
- There are also functions to add a reference and to query the geometry. The geometry query goes to vtable +32.
- **The key is class << 8**, and ids are `class << 8 | index`. Passing a bare class number gives class 0.
- A pool object holds +8 base, +12 slot size, +20 free count (u16), +24 count (u16) and +64 bitmap. For the base
  class, the address is base + (index - 1) × size.

The addresses of these functions are in the [address reference](#address-reference).

**The main pool is a trap.**[^cam1] The main pool (class 0) is a derived two-block class: 20 slots of `0x1f47600`
bytes (32.8 MB each). Ids up to 8 are at `0xb0000000`, and ids 9-20 at `0xc4000000`. Always ask the pool for an
address. Never compute it from a stride. One of our builds had exactly this bug.

**Other pools.**[^cam1]

| pool | base | slots |
|---|---|---|
| meta | `0xae95d740` | `0xd200` × 20 |
| descriptor (class `0x15`) | `0xaeb333c0` | `0xa400` × 64 |
| aux | `0xa9d55b40` | `0x2f1e00` × 4 |
| record pool | `0x621107c4` | 64 × 12 bytes |

*Smaller pools seen on our camera.*

The **static pool init** (one shooting mode's set) gives the base, size, count and geometry for every key.[^fw5] For
example:

| key | use | slots |
|---|---|---|
| `0x0b00`, `0x0c00`, `0x0d00` | OSD layers | 4 × `0x83400` at `0xafdf3000`, `0xafbe6000`, `0xaf9d9000` |
| `0x0a00`, `0x0e00`, `0x0f00` | display | 1920 × 1080 × 2 |
| `0x2c00` | face-detect VGA | 11 × 640 × 480 4:2:0 at `0xddf7b000` |

*Examples from the static pool init. See also [Display and OSD](display.md).[^fw5]*

Tripod High Res uses pool `0x4f00` (8 frames). The OM-5's handheld HHHR pool is `0x6100` (12 frames).[^fw1]

**Porting rules.**[^fw1]

- The dispatch table has 87 entries. Donor buffer ids (`0x5f00`-`0x6500`, `0x6700`-`0x6900`) aren't in it.
- Don't add ids or lock tags. Write adapters over the native pools.
- The OM-5's Live ND swaps the main pool `0x0000` (18 slots) for `0x6b00` (19 slots, same memory, lock tag `0x102`).
  The E-M5's main pool already has 20 slots, so that layout doesn't need porting.

## Image buffer pool map

We made full tables of every pool for both the E-M5 III and the OM-5, from the constructor calls. They list the id,
class, base, slot size, count, flags and constructor site.[^fw6]

- **Pool object.** +8 base, +12 slot size, +20/+24 count, +22 id.[^fw6] Slots are consecutive: pool `0x0700` at
  `0xaa91d340` + 4 × `0xfe4c00` ends at the base of pool `0x2d00`.
- **Pool table.** The E-M5 III's has 87 entries, the OM-5's 113.[^fw6]
- **Lock tags.** The "flags" column of the pool map is the constructor's last argument. It is stored as the word at
  pool +16, the lock tag, for example `0x102` for the OM-5's `0x6b00` and `0x101` for the ring. The byte at +30 comes
  from the second argument and is 0 for the ring.[^fw7]
- **OM-5 Live ND layout.** It is the pools in lock-tag group `0x1xx`: `0x6700`/`0x6800` (ring, 248 × `0x1ba000`),
  `0x6b00` (19 still frames), `0x6c00`, `0x6d00`, `0x6e00`, `0x6f00` and `0x7000`.[^inf4][^fw7]
- **Live-view raw pools.** The OM-5 has `0x0700` = 4 × `0x4e6400` and `0x5c00` = 4 × `0xfe4c00`. The E-M5 III has only
  `0x0700` = 4 × `0xfe4c00`, with a second pool `0x3900` at `0xc4000000`.[^fw6]
- **Built at every boot.** Section static constructors build the pools at every boot.[^fw7]
    - The E-M5 III's init array has 12 entries. The first is the pool list. Its runner is bounded by a byte count of
      48, so the `0xff` words after the array are not a terminator.
    - The OM-5's has 13 entries, count 52.
    - Pool objects are static RAM objects (E-M5 still pool `0xa25bb974`, OM-5 ring `0x6700` at `0xa25f11a8`).
    - The OM-5 ring is constructed at every boot and only used while the preview runs. There is no runtime layout
      switch for it.
- **Counts.** The E-M5 III's constructors build 64 pools, the OM-5's 87. The E-M5 III pools add up to about 4.4 GB of
  slots in a 924 MB buffer area. So most memory belongs to several pools at once, as alternative layouts for different
  modes.[^fw8]
- **Free entries.** The free (null) entries in the E-M5 III pool table are `0x10`-`0x13`, `0x1a`-`0x21`, `0x44`-`0x47`
  and `0x4a`. The limit 87 is an immediate in at least 10 places of the buffer module, so new ids must reuse null
  entries.[^fw7]
- **Lazy pools.** A pool could be made lazily, without touching boot. The native multi constructor would run on our RAM
  and fill a table entry at preview start, cleared at the end. Whether the table is writable at run time is
  untested.[^inf5]

## Spare space for our code

Each feature gets its own region, so builds can be stacked. Most regions are slack after a block0 section. To use
slack, raise that section's end constant in the loader switch.[^cam1] The constants are in the
[address reference](#address-reference).

<details><summary>Spare regions and their owners, 28 rows</summary>

| region | size | owner | status |
|---|---|---|---|
| `0x600d009a`-`0x600d0800` (section 0 tail) | 1.9 KB | shared, see below | always ready |
| section 4 slack `0x6079d800`-`0x607b6800` | about 100 KB | **Live ND** (code `0x607a0000` and up, M data) | proven in cave test 2[^cam1] |
| section 2 slack `0x6056c000`-`0x6057e000` | 72 KB | Starry Sky AF | not loaded yet |
| section 2 slack `0x6057e000`-`0x60582000` | 16 KB | **looks** picture-mode tables (about 11 KB, shared with Starry Sky AF[^pol2]). Section-2 end raised to `0x60582000` by a looks test build, camera-proven[^cam2]. Looks section-2 code `0x60581860`-`0x605819b8` (profile apply, settings redirect, tone curve, live-view tone and table)[^fw11] | loaded |
| section 2 tail `0x6056bcd8`-`0x6056c000` (`0xff` in stock) | 808 B | Live ND live-view guards (`0x6056bcd8`-`0x6056bd00`, `0x6056bfe0`-`0x6056c000`). Console memory peek (`0x6056bd00`-`0x6056bd98`). **Geotag line** `0x6056be00`-`0x6056bf00` (code `0x6056be00`-`0x6056bef9`, hook `0x602bd46c`)[^fw9] | loaded with section 2 |
| section-5 gap `0x60bef800`-`0x60bf7800` | 32 KB | **looks** GUI picture-mode tables (about 14 KB). Section-5 end `0x60045df3` raised `0x60bef800` to `0x60bf7800`. The rest of the gap to `0x60c17000` is unowned[^fw8][^pol2] | not loaded yet. om-emu only |
| section-5 gap `0x60bf7800`-`0x60bfb000` | 14 KB | **looks** colour-profile editor code, tables, editor state (`0x60bf8820`, 8 B), E-M1 III wheel renderers, 16-slot image-handle table (`0x60bf9f00`) and sprite tables, `0x60bf8000`-`0x60bfa4c8`. Section-5 end raised to `0x60bfb000` (editor test build, not camera-proven)[^fw8] | ready, not run |
| section-5 gap `0x60bfb000`-`0x60c03000` | 32 KB | **looks** side-bar editor pictures (row names, tone icons, strip piece, curve pictures) and data from `0x60bfb000` (to about `0x60c01b40`). Section-5 end raised `0x60bfb000` to `0x60bff000` (camera run OK), then to `0x60c03000`[^fw11][^cam3] | camera run: the side-bar editor boots and works[^cam3] |
| section 9 lower `0x613bb000`-`0x613d4000` | 100 KB | webcam (parked, still reserved) | used by the webcam tests[^cam1] |
| section 9 upper `0x613d4000`-`0x613fe800` | 170 KB | **HHHR** | all `0xff`. The section 9 end must move to `0x613fe800` |
| `0x600d0800`-`0x600de000` (gap before section 1) | 54 KB | none | see below |
| `0x6022d7d4`-`0x6022d800` (section-1 tail, after the hash table ending `0x6022d7d4`) | 44 B | **Live ND** stabiliser-reply gate (gyro conversion) `0x6022d7d4`-`0x6022d7f5`[^fw9] | same section as its hook `0x60114b7e` |
| `0x61477cf0`-`0x61478000` (section-10 tail, loaded) | 784 B | **card console, first version** | runner `0x61477cf0`-`0x61477ff4`, never flashed, replaced by the second version[^fw5][^cam4] |
| `0x61478000`-`0x61480000` (after section 10) | 32 KB | **card console** | works, see below[^cam4] |
| `0x61480000`-`0x61483000` (after the card console) | 12 KB | **dev settings page** (`0x61480000`-`0x61481550`, section-10 end raised to `0x61483000`, boots and works)[^cam5] | see below |
| `0x61123c5c`-`0x61124000` (section-6 tail) | 932 B | **dev page stubs and menu table copies** `0x61123c60`-`0x61123d70` (`0xff` and unreferenced in stock)[^fw9] | same section as the menu hooks |
| `0x61500000`-`0x61a00000` | about 5 MB RAM | **mod RAM window**: card mods loaded by the mod loader, 256 KB or 64 KB per mod. Checked free on the camera (sampled every 4 KB, all `0xff` and unchanged after 5 minutes)[^cam6]. `0x61600000`-`0x6163ffff` left unused (GUI busy word `0x61600ba0` inside it) | see below |
| flash gap block0 to block1 (≤ 2 MB) | | none | unverified |
| `0x6022d800`-`0x6022e800` (after the stock section-1 end) | 4 KB | **mod loader base** (hook stub, MODLOAD task, loader, API table `0x6022d800`-`0x6022dfd8`, runtime words `0x6022e7f0`-`0x6022e800` written through `0xa022e7f0`). Section-1 end `0x60045ddd` raised `0x6022d800` to `0x6022e800`[^fw12]. Runs on the camera[^cam6] | loaded with section 1 once raised. No stock references into it (listing search) |
| `0x6022e800`-`0x60250000` (after the section-1 end, before the data at `0x60250000`) | 134 KB | none | `0xff`, not loaded. One `fc` immediate `0x60d42cd5` to `0x60243980` to rule out first[^fw10] |
| `0x605d4000`-`0x605da800` (after the section-3 end, end immediate at `0x60045e1d`) | 26 KB | **native menu rows** `0x605d4000`-`0x605da000`: Live ND menu code and tables (section-3 end raised to `0x605da000`, camera-proven[^cam2]). `0x605da000`-`0x605da800` free[^fw8] | `0xff`, only reference is the end constant[^fw10] |
| `0x60bef800`-`0x60c17000` (after the section-5 end, `0x60045df5`) | 158 KB | none | `0xff`. One `fc` hit `0x6136f60b` to `0xa0bf8c9d`, probably chance[^fw10] |
| `0x61124000`-`0x61125000` (after the section-6 end, `0x60045dfd`) | 4 KB | none | `0xff`, only the end constant refers to it[^fw10] |
| `0x611d4800`-`0x611dc800` (section-7 gap) | 32 KB | none. A menu test build used it and boot-looped. See the warning below[^cam2] | `fc` hits `0x605b5e5e` (movbu disp) and `0x6139551d` checked: chance |
| `0x611dc800`-`0x61205800` (rest of the section-7 gap) | 164 KB | none | `0xff`[^fw10] |
| store-50 image tail `+0x39e00`-`+0x39e87` (RAM `0x6240ae00`) | 136 B | **mod loader state table** (marker `MDS\x01`, 16 entries `{tag, on, flags, version}`)[^emu1] | saved whole with the settings at power-off (as `+0x39f00`) |
| store-50 image tail `+0x39f00`-`+0x39f7f` (RAM `0x6240af00`) | 128 B | **saved mod settings** block (marker `MOD\x01`, Live ND bytes, 16 dev words). Adjacent to the looks LOOKS block at `+0x3a000`[^pol2][^emu3] | saved whole with the settings at power-off |
| store-50 image tail `+0x3a3c0`-`+0x3a3ff` (RAM `0x6240b3c0`) | 64 B | **looks CRV block** (Free tone curve points: `CRV\x01`, Color Profile `{x, y}` × 5 at +4, Mono at +14. The read is checked: marker and x rising by 8 or more, else a straight line)[^emu2] | saved with the tail at power-off (by compare) |
| `0x61208800`-`0x61209800` (after the section-8 end, `0x60045e0d`) | 4 KB | none | `0xff`, only the end constant[^fw10] |
| `sdk api` handlers (section 5, near `0x60810d6b`) | about 200 KB (E-P7 figure) | none | stock code. Freed only by cutting the `sdk`/`api` table words, which loses those shell commands. See linked projects[^inf6] |

*Spare regions for our code, with owner and load status.*

</details>

> [!WARNING]
> Don't place code that boot reaches in the section-7 gap. Section 7 is ready last, behind the access monitor. A menu
> test build placed there boot-looped the camera.

**Section gaps.** Every block0 section is followed in the image by `0xff` up to the next section's start. Flash and
VMA move together in the section table. The loader copies only up to each end constant in its switch. So each gap
becomes loadable by raising one constant, as was done for sections 4, 9 and 10.[^fw10]

The six section-gap rows from that scan were checked for `fc` immediates (cached and uncached alias) in stock block0.
None is camera-tested, so prove each with a section-end probe (pattern and card readback) before putting code there.
The scan looked at 4-byte words after an `fc` prefix and at aligned words. Aligned-word hits are at the same noise
level as in the proven section-2 and section-9 slack.[^fw10]

Notes on the rows above:

- **Section 0 tail, `0x600d009a`-`0x600d0800`.** It is always ready, so boot guards and small hook stubs live here. It
  holds the state table, the boot guards and small stubs for our test builds (focus-stack count, IS Level, Live ND
  guards). It is nearly full. About 98 B at its end are kept for HHHR.[^fw1]
- **Gap before section 1, `0x600d0800`-`0x600de000`.** It is `0xff` in the image, never copied and has no code
  references. It becomes **always ready** if the boot-copy end immediate (`0x600d0800`) is raised to
  `0x600de000`.[^fw5]
- **Card console, `0x61478000`-`0x61480000`.** Code at `0x61478000`, state at `0x61479800` and buffers up to
  `0x61480000`. The section-10 end was raised to `0x61480000`, and that worked.[^cam4]
- **After the card console, `0x61480000`-`0x61483000`.** In stock it is `0xff` padding, not loaded, with no code
  references. It is loadable by raising the section-10 end constant (`0x61478000` in stock).[^fw5]
- **`0x61485000`-`0x61a00000`.** Not in any loaded section, and no code references. The staging area
  `0xa1483000`-`0xa1484800` and 32 B at `0x61484e00` stay reserved. It is free unless a RAM check on the camera shows
  writes.[^fw5][^inf7]

## The small-object heap (scheap)

The general allocator returns a block in a0 for a size in d0. It has 742 call sites, and the free function 759.[^fw8]

- It is not a free-list heap. It picks one of three fixed-block classes by size, under cross-core lock 10 and with
  interrupts masked.[^fw8]
- A request over 16 KB fails with "scheap_phyalloc: Size Over" and returns 0.[^fw8]

| class | for sizes | block | count | area |
|---|---|---|---:|---|
| small | ≤ 128 B | `0xc0` | 178 | `0xa1ab0fc0`-`0xa1ab9540` |
| middle | ≤ 2 KB | `0x840` | 21 | `0xa1e80800`-`0xa1e8b540` |
| large | ≤ 16 KB | `0x4040` | 43 | `0xa1cbb540`-`0xa1d68000` |
| 4th (custom/apim?) | not reached by the allocator | `0xc0` | 100 | from `0xa26c9500` |

*Heap classes. The block size includes the header. All are in uncached RAM.[^fw8]*

- Free finds the class from the address range, and logs "scheap_phyfree: not allocated" otherwise.[^fw8]
- The user shell's `sc heaplist small|middle|large|custom|apim|count` and `sc heapshow` list them.[^fw8]
- It is about 786 KB in all, so anything big (image data) must come from the frame pools.[^fw8]
- Other bodies: the `scheap_phyalloc` and `sc heaplist` strings are in all six block0s (OM-5, E-M1 III, OM-5 II, OM-1,
  PEN-F). The same block-size table `{0xc0, 0x840, 0x4040, 0xc0}` is in the OM-5, E-M1 III and OM-5 II. It was not
  found on the OM-1 or PEN-F (different sizes or layout, not traced).[^fw8]

## Address reference

E-M5 III 1.7 block0 addresses unless a body is named.

| item | address |
|---|---|
| flash write guard (`sub_600c463a`) | `0x600c463a` |
| OM-5 settings bank rotation (after 40,000 writes) | `0x6002272c` (OM-5) |
| loader switch | `0x60045dc5` |
| section table | `0x600272a4` |
| boot-copy end immediate (`0x600d0800`) | `0x600211af` |
| section 1, 3, 4, 5, 6, 8, 9, 10 end constants | `0x60045ddd`, `0x60045e1d`, `0x60045deb`, `0x60045df3`/`0x60045df5`, `0x60045dfd`, `0x60045e0d`, `0x60045e13`, `0x60045e24` |
| state table, boot guards | `0x600d0200`, `0x600d06a4`-`0x600d079e` |
| HHHR reserve in section 0 | about 98 B at `0x600d079e` |

*Flash guard, loader and section constants.*

| item | address |
|---|---|
| pool table (8 B per class) | `0x6053e158` + 8 × class |
| acquire (inner function) | `0x603f70f5` (`0x603f7140`) |
| look up address | `0x603f73e2` |
| release | `0x603f71fe` |
| add a reference | `0x603f7350` |
| query geometry, vtable +32 | `0x603f77c4`, `0x603f8ea5` |
| main pool vtable, address method | `0x6053e778`, `0x603f9cb7` |
| static pool init (also the main pool init) | `0x603f65a9` |
| pool constructor calls | E-M5 III `0x603f6291` and up, OM-5 `0x6040c400` and up |
| pool table | E-M5 III `0x6053e158` (87 entries), OM-5 `0x60575c70` (113) |
| static constructor init array, first entry (pool list) | E-M5 III `0x6056bca8`, `0x603f657f`. OM-5 `0x605a7694` |
| init array runner | `0x60199d84` |
| buffer module immediates for the limit 87 | `0x603f7135` to `0x603f7a45` |
| native multi constructor | `0x603f92dc` |

*Frame pools.*

| item | address |
|---|---|
| allocator (d0 = size, block in a0) | `0x600232c5` |
| free (a0) | `0x600232f7` |
| class pick | `0x600235a4` |
| class tables: base, count, block size | `0x60027044`, `0x60027054`, `0x60027084` |
| block-size table in other bodies | OM-5 `0x60027dc8`, E-M1 III `0x60027fb0`, OM-5 II `0x600282c8` |

*Small-object heap.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware.
[^fw2]: Read in the firmware, 2026-11-25.
[^fw3]: Read in the firmware, 2026-11-07.
[^fw4]: Read in the firmware, 2026-11-24, from block0 strings.
[^fw5]: Read in the firmware, 2026-11-05.
[^fw6]: Read in the firmware, 2026-11-12.
[^fw7]: Read in the firmware, 2026-11-15.
[^fw8]: Read in the firmware, 2026-11-19.
[^fw9]: Read in the firmware, 2026-11-17.
[^fw10]: Read in the firmware, 2026-11-18.
[^fw11]: Read in the firmware, 2026-11-20.
[^fw12]: Read in the firmware, 2026-11-21.
[^cam1]: Seen on our E-M5 III.
[^cam2]: Seen on our E-M5 III using test firmware, 2026-11-19.
[^cam3]: Seen on our E-M5 III using test firmware, 2026-11-20.
[^cam4]: Seen on our E-M5 III using test firmware, 2026-11-06.
[^cam5]: Seen on our E-M5 III using test firmware, 2026-11-17.
[^cam6]: Seen on our E-M5 III using test firmware, 2026-11-22.
[^emu1]: Seen in om-emu, 2026-11-21.
[^emu2]: Seen in om-emu, 2026-11-22.
[^emu3]: Seen in om-emu.
[^inf1]: Inferred. We have no teardown.
[^inf2]: Inferred from typical SLC datasheets, not from this chip.
[^inf3]: Inferred, 2026-11-24.
[^inf4]: Inferred, 2026-11-12.
[^inf5]: Inferred, 2026-11-15.
[^inf6]: Inferred, 2026-11-18.
[^inf7]: Inferred, 2026-11-05.
[^pol1]: Project decision on the donor body, 2026-10-22.
[^pol2]: Project decision, 2026-11-19.
[^fix1]: Corrected 2026-11-25. See [History](#history).
[^fix2]: End of the range corrected 2026-11-25.

## History

- 2026-11-05: we first listed about 5 MB of zero runs (for example `0x61483b31`-`0x61858fe0`) as "not free (likely
  zero-init data)". Corrected the same day: see the spare-space rows.
- 2026-11-15: the "flags" column of the pool map was read as flag bits, so the OM-5 Live ND layout was "flag bit
  `0x100`". It is the lock tag, so the layout is lock-tag group `0x1xx`.
- 2026-11-25: the flash range was first treated as CPU-readable memory. The addresses are names for the driver only.
- 2026-11-25: the end of the cross-core call rings was corrected.

