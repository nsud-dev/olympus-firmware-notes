# Memory map

## DRAM size per body (from static image-buffer maps)
| body | buffer map | class |
|---|---|---|
| E-M5 III 1.7 | 0xa3f25540-0xdf02e000 (924 MB), inside the uncached window 0xa0000000-0xdfffffff | **1 GB** |
| OM-5 1.2 | same start/end, laid out differently (frees 0xc0000000-0xc4000000; adds 21 MB at 0x9ca3b000) | 1 GB |
| OM-5 II 1.1 | same as OM-5 | 1 GB |
| E-M1 III 1.6 | 0x84000000-0xfbbf9000 (~1.8 GB) | 2 GB |
| OM-1 / OM-1 II | ~1.5 GB of buffers, main pool 0xb8000000-0xff124000 | 2 GB |
[code] for the maps (`decomp/hhhr/generator/ramscan.py`), [inferred] for physical DRAM size (no teardown).
**OM-5 1.2 is the memory model for ports** (the maintainer's donor decision 2026-10-22). E-M1 III/OM-1 buffer designs don't fit.

## Flash map (E-M5 III, 128 MB at 0x40000000, alias 0x80000000)
| range | what |
|---|---|
| 0x40000000-0x40060000 | boot area before block0 (written only by update kind BOOT; not in our .BIN files) |
| 0x40060000-0x40780000 | data window (settings bulk 0x406a0000, 0x40700000, 0x40740000) |
| 0x40780000-0x41f60000 | block0 (USR) |
| 0x41f60000-0x42160000 | data window |
| 0x42160000-0x43f60000 / 0x43f60000-0x47160000 | block1 OSD / block2 RESCOM |
| 0x47180000-0x47a80000 | block4 PIC |
| 0x47a80000-0x48000000 | data windows (0x47a80000, 0x47b80000) |
- Outside an update, writes outside the three data windows trip the guard sub_600c463a (watchdog + spin = reset).
  [code] 2026-11-07

## RAM regions worth knowing (E-M5 III)
| region | what |
|---|---|
| 0x60030000-0x600d0800 | copied by the boot stub, always ready (holds our state table and boot guards) |
| 0x600de000-0x613fe800 | block0 sections 1-10, loaded in the background ([boot](../firmware/boot-and-sections.md)) |
| 0x62000000+ | RAM globals (Ghidra RAM block; size assumed) |
| 0x62fe0000 (+128 KB) | ISC shared memory with the ARM |
| 0x8ff00c00 | ISC control blocks |
| 0xa0000000-0xdfffffff | uncached image window (cached alias 0x6xxxxxxx for low parts) |
| 0xa411f540-0xa4277140 | native DSP job programs 0-10 |
| 0xa4277140-0xa42bf540 | 296 KB with no code refs (candidate for donor job programs) |
| 0xa07b4800-0xa07b6000 | Live ND's "M" block (uncached view of section-4 slack) |

## Frame pools
- Pool table **0x6053e158** + 8×class; acquire **0x603f70f5**(d0 = key, a0 = &u16 id) (inner 0x603f7140),
  lookup 0x603f73e2(d0=id) → address, release **0x603f71fe**(d0=id), addref 0x603f7350, geometry query
  0x603f77c4 → vtable+32 0x603f8ea5. [camera]
- **Pool key = class << 8**; ids are `class<<8 | index`. Passing a bare class gives class 0. (E8b) [camera]
- Pool object: +8 base, +12 slot size, +20 free count (u16), +24 count (u16), +64 bitmap; addr = base +
  (idx−1)×size for the base class. [camera]
- **Main pool (class 0) is a derived two-block class** (vtable 0x6053e778, init 0x603f65a9): 20 slots of
  0x1f47600 (32.8 MB); ids ≤ 8 at **0xb0000000**, ids 9-20 at **0xc4000000** (address method 0x603f9cb7).
  Always ask the pool for addresses, never compute from a stride. (E6 bug) [camera]
- Other pools seen: meta 0xae95d740 0xd200×20, descriptor (class 0x15) 0xaeb333c0 0xa400×64, aux 0xa9d55b40
  0x2f1e00×4, record pool 0x621107c4 64×12 B. [camera]
- **Static pool init 0x603f65a9** (one mode's set) gives base/size/count/geometry for every key: e.g. OSD layers 0x0b00/0x0c00/0x0d00
  (4 × 0x83400 at 0xafdf3000/0xafbe6000/0xaf9d9000), display 0x0a00/0x0e00/0x0f00 (1920×1080×2), face-detect VGA 0x2c00 (11 × 640×480 4:2:0
  at 0xddf7b000). Full table; see [display](display.md). [code] (2026-11-05)
- Tripod High Res pool 0x4f00 (8 frames). HHHR handheld pool on OM-5 0x6100 (12 frames). [code]
- Dispatch table has 87 entries; donor buffer ids (0x5f00-0x6500, 0x6700-0x6900) aren't in it. Don't add ids or
  lock tags: use adapters over native pools. [code]
- OM-5 Live ND swaps main pool 0x0000 (18 slots) for 0x6b00 (19 slots, same memory, lock tag 0x102). E-M5's main
  pool is already 20 slots, so no layout port is needed. [code]

## Free code regions (block0 slack)
| region | size | owner | status |
|---|---|---|---|
| 0x600d009a-0x600d0800 (section 0 tail) — **2026-11-07: Live ND E11a* guards run to 0x600d07b9, 27 B into the HHHR area at 0x600d079e (P2c has HHHR code there): conflict when stacking** [code] private notes | 1.9 KB | state table 0x600d0200 + boot guards 0x600d06a4-0x600d079e; **FS1 focus-stack count 0x600d0140-0x600d01e4** (2026-11-05) | ~98 B at 0x600d079e (HHHR) + 0x600d01e4-0x600d0200 + 0x600d009a-0x600d0100 left [code]; **0x600d00a0-0x600d00ce ISL1 gate** (built 2026-11-07 on P2b3; 0x600d00ce-0x600d00e0 kept for ISL2); **0x600d00e0-0x600d0100 CP0 stub (planned 2026-11-08)** private notes |
| section 4 slack 0x6079d800-0x607b6800 | ~100 KB | **Live ND** (code 0x607a0000+, M data) | proven, cave test 2 [camera]; **0x6079f000-0x6079f080 CP0 body (planned 2026-11-08)** private notes |
| section 2 slack 0x6056c000-0x60582000 | 88 KB | Starry Sky AF | never loaded yet |
| section 9 lower 0x613bb000-0x613d4000 | 100 KB | webcam (parked, still reserved) | used by webcam tests [camera] |
| section 9 upper 0x613d4000-0x613fe800 | 170 KB | **HHHR** | all 0xFF in E10f; section 9 end must move to 0x613fe800 |
| ~~~5 MB zero runs (e.g. 0x61483b31-0x61858fe0)~~ | | none | ~~not free (likely zero-init data)~~ corrected 2026-11-05: see the next three rows |
| 0x600d0800-0x600de000 (gap before section 1) | 54 KB | none | 0xFF in the image, never copied, no code refs; becomes **always ready** if the boot-copy end immediate at 0x600211af (0x600d0800) is raised to 0x600de000 [code] 2026-11-05 |
| 0x61477cf0-0x61478000 (section-10 tail, loaded) | 784 B | **CON1 console** | runner 0x61477cf0-0x61477ff4 (built, not run) [code] 2026-11-05 |
| 0x61478000-0x61480000 (after section 10) | 32 KB | **CON2 console** (code 0x61478000, state 0x61479800, buffers to 0x61480000); section-10 end 0x60045e24 raised to 0x61480000, works [camera] 2026-11-06 private notes |
| 0x61480000-0x61483000 (after CON2) | 12 KB | none | 0xFF padding, not loaded, no code refs; loadable by raising the section 10 end constant at 0x60045e24 (0x61478000) [code] 2026-11-05 |
| 0x61485000-0x61a00000 | ~5.5 MB RAM | none | not in any loaded section, no code refs (0xa1483000-0xa1484800 staging and 0x61484e00 32 B stay reserved); free unless a camera RAM check shows writes [code]/[inferred] 2026-11-05 |
| flash gap block0→block1 (≤ 2 MB) | | none | unverified |
To use slack, raise the section end constant in the loader switch (section 4 at 0x60045deb, section 9 at 0x60045e13). [camera]

