# om-emu additions: technical notes

> **Technical notes.** This page is the dense reference. For a readable introduction, start with [om-emu additions](om-emu-additions.md).

Base: [om-emu](https://github.com/flatpanda/om-emu) commit `ccfe2e0` (MIT since 18a8162, 2026-11-14), node 22 or
newer. Patches are `git diff` files in `tools/om-emu-c3d/patches/`. `sh apply.sh OM_EMU_CLONE` applies 0001-0010 in
order. The checks are off by default. With all ten applied, upstream `bin/test-pure.mjs` still passes [code]. Checks
are switched on with `node --import ./host/olyfwenv.mjs bin/session.mjs ...` plus the variables below. Each check
roughly doubles run time (every CPU load and store takes the slow path). Settings live in `src/core/olyfw.mjs`.
Page made 2026-11-23.

## Patches

| patch | switch | adds | found |
|---|---|---|---|
| 0001 kind2-img-planes | always | draws display-controller IMG planes (kind 2), format 3 (32-bit ARGB) at 1:1: the c3d GPU layer | GPU-drawn menus and overlays visible [emu] |
| 0002 vsc-write-log-hook | `--import vsclog.mjs` | logs each changed VSC register write, `VSC chN +0xOFF = 0xVAL` | display-controller register map |
| 0003 live-view-backdrop | `OM_BACKDROP=FILE.rgb` | 720x480 RGB picture under the layers (`c3d/backdrop.py`) | screenshots over a neutral picture |
| 0004 bitmap-no-table | always | OSD run-length bitmaps sent with no colour table draw their index (tone-curve grid, picture 0x1039) | colours inferred |
| 0005 checks-dcache-secmon | `OM_DCACHE=report[:KIB[:WAYS]] OM_DCACHE_OUT=FILE`, `OM_SECMON=FILE` | `src/core/dcache.mjs`: 8 KiB 2-way 16-byte write-back model; stale cached reads, lost write-backs, stale uncached reads. `src/core/secmon.mjs`: first fetch or read of each block0 section, to compare with stock | section monitor fails a build that hooked section 7 before it was ready (touched at clock 0.82 M, stock 36.08 M) [emu]; cache model 0 reports on stock |
| 0006 heap-fill | `OM_HEAP_FILL=deadbeef` | S-HEAP fills blocks it hands out and takes back, so unset fields fault instead of reading 0 | |
| 0007 kernel-checks | `OM_KCHECK=FILE` | `src/lab/kcheck.mjs`: a blocking service (twai_sem, wai_flg, twai_flg, loc_mtx, dly_tsk, trcv_dtq, tsnd_dtq) entered outside task context; the object lookup 0x60030eff on another CPU's object | stock: 0 of 17,456 blocking calls in an interrupt, 0 of 5 lookups cross-CPU [emu] |
| 0008 cpu2-e137 | `OM_CPU2=native OM_CPU2_OUT=FILE` | om-emu's native CPU 2 (OM-1 only) gets an E-M5 III profile: entry 0x50006771, shared SRAM 0x8ff00000, idle loop 0x50037052 | core 2 idles after 35,725 instructions; WB_MOV, MVR_MAIN and SDET start on it; stock reaches MENU [emu] |
| 0009 cpu1-e137 | `OM_CPU1=native OM_CPU2_OUT=FILE` | CPU 1 profile: entry 0x500062fc, idle loop 0x50036c9c, tasks CPUCONN1, CPUCALL1, CONTEST_CPU1; CPU 1's memory clear 0x50000466 skipped; per-core KCB (0x8ff00004 + 4 * cpu) for 0007 | core 1 idles after 56,929 instructions [emu]; neither second CPU's start-up reproduces the power-on restart |
| 0010 code-write-monitor | `OM_CODEWRITE=FILE` | `src/core/codewrite.mjs`: CPU stores into [image base, section 1 start), the range read from the section table after "BCS\0"; cached view = FAIL, uncached = WARN; section stores counted per 4 KB page | stock E-M5 III 1.7 and OM-5 II 1.1: 0 stores. A test build with driver data in a 0xFF gap at 0x6002ad80: 31 cached and 55 uncached stores during boot, black screen on the camera; its fix 0 stores and boots [camera] |

## Another body or a sleeping task

- [code] Another body's block0: build the Player with `rom: expandImage(block0)` and `OM_EMU_MODEL` set (E148 for the OM-5
  II). `session.mjs --main` refuses a block0 whose bytes under the lab's hooks changed.
- [code] A dormant task: read its id from the halfword the boot reads, add its entry to `lab.lt.allow` (the lab runs only
  allowed task entries), then `lab.nk.svc('act_tsk', {d0: tid})`. OM-5 II 1.1 port-expander task 133: id word
  0x6004144e. It starts and waits (state 4) [emu].

## Limits

- [code] CPUs 1 and 2 start after CPU 0 has booted, not beside its start-up. So the window where CPU 0 asks another
  CPU's kernel for an object before that kernel is up (camera fault at 0x60030f01) never opens. One second core at a
  time.
- om-emu skips the early start-up stages and the reset head's copies.
- No sensor, DSP, ARM, Wi-Fi or memory protection. Shooting-path hooks are mostly not reached.
- The lab writes memory directly, so the cache model counts only CPU uncached stores by default. `OM_DCACHE_ALL=1`
  also counts lab and device writes and gives about 42,000 false reports on stock.

