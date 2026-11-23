# Memory map

> **Technical notes.** This page is the dense reference. For a readable introduction, start with [Frame pools and memory](../guides/frame-pools-and-memory.md).

This page is a guide to where things are in the E-M5 III's flash and RAM: how much memory each camera has, how the
128 MB flash chip is divided, the RAM regions that matter when patching, how the camera hands out frame buffers
("frame pools"), and which spare regions we use for our own code.

A few terms used below:

- **Flash** holds the firmware permanently; **RAM** (DRAM) is the working memory, about 1 GB on this camera.
- **Cached / uncached**: the same RAM is visible at two addresses. 0x6xxxxxxx is the cached view and 0xaxxxxxxx the
  uncached view (see [MN103 CPU](mn103-cpu.md#address-aliases-cached-and-uncached)). [camera]
- **Block0** is the main program in the firmware file; at boot it is copied into RAM in "sections" (see
  [boot](../firmware/boot-and-sections.md)).
- **Slack** is unused space (0xFF bytes) after the end of a section, which we use for our own code. [code]

Tags: **[code]** read in the firmware, **[camera]** seen on a real E-M5 III, **[inferred]** not traced or tested.

## How much memory each camera has

The firmware sets out its image buffers in a fixed map, which tells us roughly how big the RAM is:

| body | buffer map | class |
|---|---|---|
| E-M5 III 1.7 | 0xa3f25540-0xdf02e000 (924 MB), inside the uncached window 0xa0000000-0xdfffffff | **1 GB** |
| OM-5 1.2 | same start and end, laid out differently (frees 0xc0000000-0xc4000000; adds 21 MB at 0x9ca3b000) | 1 GB |
| OM-5 II 1.1 | same as OM-5 | 1 GB |
| E-M1 III 1.6 | 0x84000000-0xfbbf9000 (~1.8 GB) | 2 GB |
| OM-1 / OM-1 II | ~1.5 GB of buffers, main pool 0xb8000000-0xff124000 | 2 GB |

[code] for the maps (`decomp/hhhr/generator/ramscan.py`), [inferred] for the physical DRAM size (no teardown).

This is why we port from the OM-5: it has the same 1 GB layout, so **OM-5 1.2 is the memory model for ports**. The E-M1 III and OM-1 buffer designs need twice the memory and don't fit.

## Flash layout (E-M5 III)

The flash is 128 MB at 0x40000000 (also visible at 0x80000000):

| range | what |
|---|---|
| 0x40000000-0x40060000 | boot area before block0 (written only by an update of kind BOOT; not in our .BIN files) |
| 0x40060000-0x40780000 | data window (settings bulk 0x406a0000, 0x40700000, 0x40740000) |
| 0x40780000-0x41f60000 | block0 (USR), the main program |
| 0x41f60000-0x42160000 | data window |
| 0x42160000-0x43f60000 / 0x43f60000-0x47160000 | block1 OSD (GUI resources) / block2 RESCOM (resources) |
| 0x47180000-0x47a80000 | block4 PIC |
| 0x47a80000-0x48000000 | data windows (0x47a80000, 0x47b80000) |


Outside a firmware update, any write outside the three data windows trips a guard, sub_600c463a, which starts the
watchdog and spins until the camera resets. [code] 2026-11-07

## RAM regions worth knowing (E-M5 III)

| region | what |
|---|---|
| 0x60030000-0x600d0800 | copied by the boot stub, so always ready (holds our state table and boot guards) |
| 0x600de000-0x613fe800 | block0 sections 1-10, loaded in the background ([boot](../firmware/boot-and-sections.md)) |
| 0x62000000+ | RAM globals (the Ghidra RAM block; size assumed) |
| 0x62fe0000 (+128 KB) | memory shared with the ARM (ISC) |
| 0x8ff00c00 | ISC control blocks |
| 0x8fe00000-0x8fe0003f | 64 cross-core lock bits (`bset`/`bclr`) ([SoC overview](soc-overview-technical.md#how-the-cores-talk-to-each-other-2026-11-19)) |
| 0x99200400 / 0x99300400 / 0x99b00400 | inter-core interrupt (doorbell) registers of CPU0 / CPU1 / CPU2 |
| 0xa2623fdc-0xa26249f4 | cross-core call rings (9 × 32 entries) |
| 0xa0000000-0xdfffffff | uncached image window (cached alias 0x6xxxxxxx for the low parts) |
| 0xa411f540-0xa4277140 | the camera's own image-engine job programs 0-10 |
| 0xa4277140-0xa42bf540 | 296 KB with no code references (a candidate home for donor job programs) |
| 0xa07b4800-0xa07b6000 | Live ND's "M" block (uncached view of section-4 slack) |

## Frame pools

The camera doesn't hand out image memory freely. It keeps "pools" of fixed-size buffers, one pool per kind ("class")
of buffer, and code asks a pool for a buffer by key and gets back an id. Live ND and HHHR both need to borrow frames
this way.

How to use a pool: [camera]

- The pool table is at **0x6053e158** + 8×class. [camera]
- Acquire with **0x603f70f5**(d0 = key, a0 = &u16 id) (inner function 0x603f7140); look up the address with
  0x603f73e2(d0=id); release with **0x603f71fe**(d0=id); add a reference with 0x603f7350; query the geometry with
  0x603f77c4, which goes to vtable+32 0x603f8ea5. [camera]
- **The key is class << 8**, and ids are `class<<8 | index`. Passing a bare class number gives class 0.
- A pool object holds: +8 base, +12 slot size, +20 free count (u16), +24 count (u16), +64 bitmap. For the base class,
  addr = base + (idx−1)×size.

The main pool is a trap: [camera]

- **The main pool (class 0) is a derived two-block class** (vtable 0x6053e778, init 0x603f65a9): 20 slots of
  0x1f47600 bytes (32.8 MB each). Ids up to 8 are at **0xb0000000**, ids 9-20 at **0xc4000000** (address method
  0x603f9cb7). Always ask the pool for an address; never compute it from a stride. (One of our builds had exactly this bug.) [camera]

Other pools: [camera]

- meta 0xae95d740, 0xd200 × 20; descriptor (class 0x15) 0xaeb333c0, 0xa400 × 64; aux 0xa9d55b40, 0x2f1e00 × 4;
  record pool 0x621107c4, 64 × 12 bytes. [camera]
- The **static pool init 0x603f65a9** (one shooting mode's set) gives base, size, count and geometry for every key.
  For example the OSD layers 0x0b00/0x0c00/0x0d00 (4 × 0x83400 at 0xafdf3000/0xafbe6000/0xaf9d9000), the display
  0x0a00/0x0e00/0x0f00 (1920×1080×2), face-detect VGA 0x2c00 (11 × 640×480 4:2:0 at 0xddf7b000). Full table
; see [display](display.md). [code] (2026-11-05)
- Tripod High Res uses pool 0x4f00 (8 frames). The OM-5's handheld HHHR pool is 0x6100 (12 frames). [code]

Porting rules: [code]

- The dispatch table has 87 entries; donor buffer ids (0x5f00-0x6500, 0x6700-0x6900) aren't in it. Don't add ids or
  lock tags; write adapters over the native pools. [code]
- The OM-5's Live ND swaps the main pool 0x0000 (18 slots) for 0x6b00 (19 slots, same memory, lock tag 0x102). The
  E-M5's main pool already has 20 slots, so that layout doesn't need porting. [code]

## Spare space for our code

Each feature gets its own region so builds can be stacked. Most regions are slack after a block0 section. To use slack,
raise that section's end constant in the loader switch (section 4 at 0x60045deb, section 9 at 0x60045e13). [camera]

| region | size | owner | status |
|---|---|---|---|
| 0x600d009a-0x600d0800 (section 0 tail) | 1.9 KB | shared, see below | always ready |
| section 4 slack 0x6079d800-0x607b6800 | ~100 KB | **Live ND** (code 0x607a0000+, M data) | proven in cave test 2 [camera] |
| section 2 slack 0x6056c000-0x6057e000 | 72 KB | Starry Sky AF | not loaded yet |
| section 2 slack 0x6057e000-0x60582000 | 16 KB | **looks** picture-mode tables (~11 KB; shared with Starry Sky AF, decided 2026-11-19); section-2 end raised to 0x60582000 by a looks test build, **camera-proven 2026-11-19** [camera]; looks section-2 code 0x60581860-0x605819b8 (profile apply, settings redirect, tone curve, live-view tone + table) [code] 2026-11-20 private notes | loaded |
| section 2 tail 0x6056bcd8-0x6056c000 (0xFF in stock) | 808 B | Live ND live-view guards (0x6056bcd8-0x6056bd00, 0x6056bfe0-0x6056c000); console memory peek (0x6056bd00-0x6056bd98); **geotag G1** 0x6056be00-0x6056bf00 (g1.s 0x6056be00-0x6056bef9, hook 0x602bd46c) [code] 2026-11-17 | loaded with section 2 |
| section-5 gap 0x60bef800-0x60bf7800 | 32 KB | **looks** GUI picture-mode tables (~14 KB; section-5 end 0x60045df3 raised 0x60bef800 -> 0x60bf7800; rest of the gap to 0x60c17000 unowned) [code] 2026-11-19 | not loaded yet; om-emu only |
| section-5 gap 0x60bf7800-0x60bfb000 | 14 KB | **looks** colour-profile editor code + tables + editor state (0x60bf8820, 8 B) + E-M1 III wheel renderers + 16-slot image-handle table (0x60bf9f00) + sprite tables, 0x60bf8000-0x60bfa4c8; section-5 end raised to 0x60bfb000 (editor test build; not camera-proven) [code] 2026-11-19 private notes | ready, not run |
| section-5 gap 0x60bfb000-0x60c03000 | 32 KB | **looks** side-bar editor pictures (row names, tone icons, strip piece, curve pictures) and data from 0x60bfb000 (to about 0x60c01b40); section-5 end raised 0x60bfb000 -> 0x60bff000 (camera-run OK 2026-11-20) -> 0x60c03000 [code] 2026-11-20 | camera-run 2026-11-20 (side-bar editor boots and works) |
| section 9 lower 0x613bb000-0x613d4000 | 100 KB | webcam (parked, still reserved) | used by the webcam tests [camera] |
| section 9 upper 0x613d4000-0x613fe800 | 170 KB | **HHHR** | all 0xFF; the section 9 end must move to 0x613fe800 |
| 0x600d0800-0x600de000 (gap before section 1) | 54 KB | none | see below |
| 0x6022d7d4-0x6022d800 (section-1 tail, after the hash table ending 0x6022d7d4) | 44 B | **Live ND** stabiliser-reply gate (gyro conversion) 0x6022d7d4-0x6022d7f5 [code] 2026-11-17 | same section as its hook 0x60114b7e |
| 0x61477cf0-0x61478000 (section-10 tail, loaded) | 784 B | **card console, first version** | runner 0x61477cf0-0x61477ff4 (never flashed; replaced by the second version 2026-11-06) [code] 2026-11-05 |
| 0x61478000-0x61480000 (after section 10) | 32 KB | **card console** | works, see below [camera] 2026-11-06 |
| 0x61480000-0x61483000 (after the card console) | 12 KB | **dev settings page DM1** (0x61480000-0x61481550; section-10 end raised to 0x61483000; boots and works) [camera] 2026-11-17 | see below |
| 0x61123c5c-0x61124000 (section-6 tail) | 932 B | **DM1 stubs + J2 table copies** 0x61123c60-0x61123d70 (0xFF and unreferenced in stock) [code] 2026-11-17 | same section as the menu hooks |
| 0x61500000-0x61a00000 | ~5 MB RAM | **mod RAM window**: card mods loaded by the mod loader, 256 KB or 64 KB per mod; checked free on the camera (sampled every 4 KB, all 0xFF and unchanged after 5 minutes) [camera] 2026-11-22; 0x61600000-0x6163ffff left unused (GUI busy word 0x61600ba0 inside it) | see below |
| flash gap block0→block1 (≤ 2 MB) | | none | unverified |
| 0x6022d800-0x6022e800 (after the stock section-1 end) | 4 KB | **mod loader base** (hook stub, MODLOAD task, loader, API table 0x6022d800-0x6022dfd8; runtime words 0x6022e7f0-0x6022e800 written through 0xa022e7f0); section-1 end 0x60045ddd raised 0x6022d800 -> 0x6022e800 [code] 2026-11-21, runs on the camera [camera] 2026-11-22 private notes | loaded with section 1 once raised; no stock references into it (listing search) |
| 0x6022e800-0x60250000 (after section-1 end, before the data at 0x60250000) | 134 KB | none | 0xFF, not loaded; one `fc` immediate 0x60d42cd5 → 0x60243980 to rule out first [code] 2026-11-18 |
| 0x605d4000-0x605da800 (after section-3 end, end immediate at 0x60045e1d) | 26 KB | **native menu rows** 0x605d4000-0x605da000 Live ND menu code + tables (section-3 end raised to 0x605da000; camera-proven 2026-11-19); 0x605da000-0x605da800 free [code] 2026-11-19 private notes | 0xFF, only reference is the end constant [code] 2026-11-18 |
| 0x60bef800-0x60c17000 (after section-5 end, 0x60045df5) | 158 KB | none | 0xFF; one `fc` hit 0x6136f60b → 0xa0bf8c9d, probably chance [code] 2026-11-18 |
| 0x61124000-0x61125000 (after section-6 end, 0x60045dfd) | 4 KB | none | 0xFF, only the end constant refers to it [code] 2026-11-18 |
| 0x611d4800-0x611dc800 (section-7 gap) | 32 KB | none (a menu test build used it and boot-looped 2026-11-19: section 7 is ready last, behind the access monitor; don't place boot-reached code here) [camera] 2026-11-19 | `fc` hits 0x605b5e5e (movbu disp) and 0x6139551d checked: chance |
| 0x611dc800-0x61205800 (rest of the section-7 gap) | 164 KB | none | 0xFF [code] 2026-11-18 |
| store-50 image tail +0x39E00-0x39E87 (RAM 0x6240ae00) | 136 B | **mod loader state table** (marker `MDS\x01`, 16 entries {tag, on, flags, version}) [emu] 2026-11-21 private notes | saved whole with the settings at power-off (as +0x39F00) |
| store-50 image tail +0x39F00-0x39F7F (RAM 0x6240af00) | 128 B | **saved mod settings** block (marker `MOD\x01`, Live ND bytes, 16 dev words); adjacent to the looks LOOKS block at +0x3A000 (agreed 2026-11-19) [emu] | saved whole with the settings at power-off |
| store-50 image tail +0x3A3C0-0x3A3FF (RAM 0x6240b3c0) | 64 B | **looks CRV block** (Free tone curve points: `CRV\x01`, Color Profile {x, y} x 5 at +4, Mono at +14; read checked: marker and x rising by 8 or more, else a straight line) [emu] 2026-11-22 private notes | saved with the tail at power-off (by compare) |
| 0x61208800-0x61209800 (after section-8 end, 0x60045e0d) | 4 KB | none | 0xFF, only the end constant [code] 2026-11-18 |
| `sdk api` handlers (section 5, near 0x60810d6b) | ~200 KB (E-P7 figure) | none | stock code, freed only by cutting the `sdk`/`api` table words (loses those shell commands); see linked projects [inferred] 2026-11-18 |

Section gaps (2026-11-18): every block0 section is followed in the image by 0xFF up to the next section's start (table
0x600272a4, flash and VMA move together), and the loader copies only up to each end constant in the switch at
0x60045dc5. So each gap becomes loadable by raising one constant, as was done for sections 4, 9 and 10. The six new rows
above were checked for `fc` immediates (cached and uncached alias) in stock block0; none is camera-tested, so prove each
with a section-end probe (pattern + card readback) before putting code there. [code] 2026-11-18 (scan: 4-byte words after
an `fc` prefix and aligned words; aligned-word hits are at the same noise level as in the proven section-2/9 slack)


Notes on the rows above:

- **Section 0 tail, 0x600d009a-0x600d0800.** Always ready, so boot guards and small hook stubs live here: the
  state table at 0x600d0200, boot guards 0x600d06a4-0x600d079e, and small stubs for our test builds (focus-stack count,
  IS Level, Live ND guards). It is nearly full: about 98 B at 0x600d079e are kept for HHHR. [code]
- **Gap before section 1, 0x600d0800-0x600de000.** 0xFF in the image, never copied, no code references. It becomes
  **always ready** if the boot-copy end immediate at 0x600211af (0x600d0800) is raised to 0x600de000. [code] 2026-11-05
- **Card console, 0x61478000-0x61480000.** Code at 0x61478000, state at 0x61479800, buffers up to 0x61480000. The section-10
  end at 0x60045e24 was raised to 0x61480000 and that worked. [camera] 2026-11-06

- **After the card console, 0x61480000-0x61483000.** 0xFF padding, not loaded, no code references; loadable by raising the
  section 10 end constant at 0x60045e24 (0x61478000). [code] 2026-11-05
- **0x61485000-0x61a00000.** Not in any loaded section, no code references (0xa1483000-0xa1484800 staging and 0x61484e00
  32 B stay reserved). Free unless a RAM check on the camera shows writes. [code]/[inferred] 2026-11-05
- A correction: we first listed ~5 MB zero runs (e.g. 0x61483b31-0x61858fe0) as "not free (likely zero-init data)".
  Corrected 2026-11-05: see the rows above. [code]/[inferred]


## The small-object heap (`scheap`, 2026-11-19)

Read off the disassembly. [code] Source: block0 disassembly.

- The general allocator **0x600232c5(d0 = size)** returns a block in a0 [code] (742 call sites; free **0x600232f7(a0)**, 759
  sites). It is not a free-list heap: it picks one of three fixed-block classes by size (0x600235a4, under cross-core
  lock 10 and with interrupts masked), and a request over 16 KB fails with "scheap_phyalloc: Size Over" and returns 0.
- Classes (tables 0x60027044 base, 0x60027054 count, 0x60027084 block size including header), all in uncached RAM [code]:

| class | for sizes | block | count | area |
|---|---|---|---|---|
| small | ≤ 128 B | 0xc0 | 178 | 0xa1ab0fc0-0xa1ab9540 |
| middle | ≤ 2 KB | 0x840 | 21 | 0xa1e80800-0xa1e8b540 |
| large | ≤ 16 KB | 0x4040 | 43 | 0xa1cbb540-0xa1d68000 |
| 4th (custom/apim?) | not reached by 0x600232c5 | 0xc0 | 100 | from 0xa26c9500 |

- Free finds the class from the address range and logs "scheap_phyfree: not allocated" otherwise. The user shell's `sc
  heaplist small|middle|large|custom|apim|count` and `sc heapshow` list them. About 786 KB in all, so anything big
  (image data) must come from the frame pools. [code]

- Other bodies: the `scheap_phyalloc` and `sc heaplist` strings are in all six block0s (OM-5, E-M1 III, OM-5 II,
  OM-1, PEN-F). The same block-size table {0xc0, 0x840, 0x4040, 0xc0} is at OM-5 0x60027dc8, E-M1 III 0x60027fb0,
  OM-5 II 0x600282c8; not found on the OM-1 or PEN-F (different sizes or layout, not traced). [code] 2026-11-19

## Image buffer pool map, E-M5 III vs OM-5 (2026-11-12)
- Pool object: +8 base, +12 slot size (per slot: pool 0x0700 at 0xaa91d340 + 4 x 0xfe4c00 ends at the base of pool 0x2d00), +20/+24 count, +22 id. Pool table E-M5 III 0x6053e158 (87 entries), OM-5 0x60575c70 (113). [code] 2026-11-12
- OM-5 Live ND layout = pools with flag bit 0x100: 0x6700/0x6800 (ring, 248 x 0x1ba000), 0x6b00 (19 still frames), 0x6c00, 0x6d00, 0x6e00, 0x6f00, 0x7000. [inferred] 2026-11-12
- Live-view raw pools: OM-5 0x0700 = 4 x 0x4e6400 and 0x5c00 = 4 x 0xfe4c00; E-M5 III 0x0700 = 4 x 0xfe4c00 only, second pool 0x3900 at 0xc4000000. [code] 2026-11-12
- Pools are built at every boot by section static constructors: E-M5 III init array 0x6056bca8 (12 entries, the first, 0x603f657f, is the pool list; runner 0x60199d84 bounded by a byte count of 48, so the 0xff words after the array are not a terminator), OM-5 0x605a7694 (13 entries, count 52). Pool objects are static RAM objects (E-M5 still pool 0xa25bb974, OM-5 ring 0x6700 at 0xa25f11a8). The OM-5 ring is constructed at every boot and only used while the preview runs; there is no runtime layout switch for it. [code] 2026-11-15
- Correction: the "flags" column of the pool map is the ctor's last argument, stored as the word at pool +16 (the lock tag, e.g. 0x102 for the OM-5's 0x6b00, 0x101 for the ring); the byte at +30 comes from the second argument and is 0 for the ring. So "Live ND layout = flag bit 0x100" means "lock-tag group 0x1xx". [code] 2026-11-15
- Counted from the same table (2026-11-19): the E-M5 III's constructors build 64 pools, the OM-5's 87. The E-M5 III pools add up to about 4.4 GB of slots in a 924 MB buffer area, so most memory belongs to several pools at once (alternative layouts for different modes). [code] 2026-11-19
- Free (null) entries in the E-M5 III pool table: 0x10-0x13, 0x1a-0x21, 0x44-0x47, 0x4a; the limit 87 is an immediate in at least 10 places of the buffer module (0x603f7135..0x603f7a45), so new ids must reuse null entries. A pool could be made lazily (native multi ctor 0x603f92dc on our RAM + table entry at preview start, cleared at the end) without touching boot; table writability at run time is untested. [code]+[inferred] 2026-11-15
