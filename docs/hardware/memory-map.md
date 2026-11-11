# Memory map

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

This is why we port from the OM-5: it has the same 1 GB layout, so **OM-5 1.2 is the memory model for ports** (the maintainer's
donor decision 2026-10-22). The E-M1 III and OM-1 buffer designs need twice the memory and don't fit.

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
- **The key is class << 8**, and ids are `class<<8 | index`. Passing a bare class number gives class 0. (Build E8b)
- A pool object holds: +8 base, +12 slot size, +20 free count (u16), +24 count (u16), +64 bitmap. For the base class,
  addr = base + (idx−1)×size.

The main pool is a trap: [camera]

- **The main pool (class 0) is a derived two-block class** (vtable 0x6053e778, init 0x603f65a9): 20 slots of
  0x1f47600 bytes (32.8 MB each). Ids up to 8 are at **0xb0000000**, ids 9-20 at **0xc4000000** (address method
  0x603f9cb7). Always ask the pool for an address; never compute it from a stride. (Build E6 had exactly this bug.) [camera]

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
| section 4 slack 0x6079d800-0x607b6800 | ~100 KB | **Live ND** (code 0x607a0000+, M data) | proven in cave test 2 [camera]; **0x6079f000-0x6079f080 CP0 body (planned 2026-11-08)** private notes |
| section 2 slack 0x6056c000-0x60582000 | 88 KB | Starry Sky AF | not loaded yet |
| section 9 lower 0x613bb000-0x613d4000 | 100 KB | webcam (parked, still reserved) | used by the webcam tests [camera] |
| section 9 upper 0x613d4000-0x613fe800 | 170 KB | **HHHR** | all 0xFF in E10f; the section 9 end must move to 0x613fe800 |
| 0x600d0800-0x600de000 (gap before section 1) | 54 KB | none | see below |
| 0x61477cf0-0x61478000 (section-10 tail, loaded) | 784 B | **CON1 console** | runner 0x61477cf0-0x61477ff4 (built, not run) [code] 2026-11-05 |
| 0x61478000-0x61480000 (after section 10) | 32 KB | **CON2 console** | works, see below [camera] 2026-11-06 |
| 0x61480000-0x61483000 (after CON2) | 12 KB | none | see below |
| 0x61485000-0x61a00000 | ~5.5 MB RAM | none | see below |
| flash gap block0→block1 (≤ 2 MB) | | none | unverified |

Notes on the rows above:

- **Section 0 tail, 0x600d009a-0x600d0800.** It holds the state table at 0x600d0200 and the boot guards
  0x600d06a4-0x600d079e; **FS1 focus-stack count 0x600d0140-0x600d01e4** (2026-11-05); **0x600d00a0-0x600d00ce ISL1
  gate** (built 2026-11-07 on P2b3; 0x600d00ce-0x600d00e0 kept for ISL2);
  **0x600d00e0-0x600d0100 CP0 stub (planned 2026-11-08)**. Left free: ~98 B at 0x600d079e
  (HHHR), 0x600d01e4-0x600d0200 and 0x600d009a-0x600d0100. [code] **Conflict (2026-11-07):** the Live ND E11a* guards
  run to 0x600d07b9, 27 bytes into the HHHR area at 0x600d079e (P2c has HHHR code there), so those builds clash when
  stacked. [code]
- **Gap before section 1, 0x600d0800-0x600de000.** 0xFF in the image, never copied, no code references. It becomes
  **always ready** if the boot-copy end immediate at 0x600211af (0x600d0800) is raised to 0x600de000. [code] 2026-11-05
- **CON2, 0x61478000-0x61480000.** Code at 0x61478000, state at 0x61479800, buffers up to 0x61480000. The section-10
  end at 0x60045e24 was raised to 0x61480000 and that worked. [camera] 2026-11-06

- **After CON2, 0x61480000-0x61483000.** 0xFF padding, not loaded, no code references; loadable by raising the
  section 10 end constant at 0x60045e24 (0x61478000). [code] 2026-11-05
- **0x61485000-0x61a00000.** Not in any loaded section, no code references (0xa1483000-0xa1484800 staging and 0x61484e00
  32 B stay reserved). Free unless a RAM check on the camera shows writes. [code]/[inferred] 2026-11-05
- A correction: we first listed ~5 MB zero runs (e.g. 0x61483b31-0x61858fe0) as "not free (likely zero-init data)".
  Corrected 2026-11-05: see the rows above. [code]/[inferred]

