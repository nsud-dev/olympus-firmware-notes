# om-emu additions: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [om-emu additions](om-emu-additions.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

[om-emu](https://github.com/flatpanda/om-emu) is an emulator for Olympus and OM System cameras, written by the om-emu
contributors. It is MIT-licensed. We added eleven small patches to it. They draw more of the E-M5 III's screens and
add checks that fail a test build the real camera would crash on. This page lists each patch with its switch, what it
adds and what it found, then how to run another body or a sleeping task, and the limits.

The patches are our own changes to om-emu. They ship as plain `git diff` files with om-emu's MIT notice and credit, not
as a fork.

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the code,
grey = seen in the emulator or inferred.

## Setup

- **Base.** om-emu commit `ccfe2e0`, with node 22 or newer. om-emu has been MIT-licensed since its commit
  `18a8162`.[^pol1]
- **Patches.** `git diff` files in `tools/om-emu-c3d/patches/`. `sh apply.sh OM_EMU_CLONE` applies 0001 to 0011 in
  order.
- **Upstream tests.** With all eleven applied, upstream `bin/test-pure.mjs` still passes.[^fw1]
- **Switching checks on.** The checks are off by default. Run
  `node --import ./host/olyfwenv.mjs bin/session.mjs ...` with the variables in the tables below. Settings live in
  `src/core/olyfw.mjs`.
- **Cost.** Each check roughly doubles run time, because every CPU load and store takes the slow path.

## Screen drawing

| patch | switch | adds | found |
|---|---|---|---|
| 0001 kind2-img-planes | always | draws display-controller IMG planes (kind 2), format 3 (32-bit ARGB) at 1:1, which is the c3d GPU layer | GPU-drawn menus and overlays visible[^emu1] |
| 0002 vsc-write-log-hook | `--import vsclog.mjs` | logs each changed VSC register write, `VSC chN +0xOFF = 0xVAL` | display-controller register map |
| 0003 live-view-backdrop | `OM_BACKDROP=FILE.rgb` | 720 × 480 RGB picture under the layers (`c3d/backdrop.py`) | screenshots over a neutral picture |
| 0004 bitmap-no-table | always | OSD run-length bitmaps sent with no colour table draw their index, such as the tone-curve grid, picture `0x1039` | colours inferred[^inf1] |

*Patches that draw more of the screen.*

## Crash checks

| patch | switch | adds | found |
|---|---|---|---|
| 0005 checks-dcache-secmon | `OM_DCACHE=report[:KIB[:WAYS]] OM_DCACHE_OUT=FILE`, `OM_SECMON=FILE` | `src/core/dcache.mjs`, an 8 KiB 2-way 16-byte write-back cache model that reports stale cached reads, lost write-backs and stale uncached reads. `src/core/secmon.mjs`, the first fetch or read of each block0 section, to compare with stock | the section monitor fails a build that hooked section 7 before it was ready (touched at clock 0.82 M, stock 36.08 M)[^emu1]. The cache model gives 0 reports on stock |
| 0006 heap-fill | `OM_HEAP_FILL=deadbeef` | S-HEAP fills blocks it hands out and takes back, so unset fields fault instead of reading 0 | |
| 0007 kernel-checks | `OM_KCHECK=FILE` | `src/lab/kcheck.mjs`. Flags a blocking service (twai_sem, wai_flg, twai_flg, loc_mtx, dly_tsk, trcv_dtq, tsnd_dtq) entered outside task context, and the kernel object lookup on another CPU's object | stock gives 0 of 17,456 blocking calls in an interrupt and 0 of 5 lookups cross-CPU[^emu1] |
| 0010 code-write-monitor | `OM_CODEWRITE=FILE` | `src/core/codewrite.mjs`. Flags CPU stores into the always-loaded code, from the image base to section 1's start, read from the section table after "BCS\0". Cached view = FAIL, uncached = WARN. Section stores are counted per 4 KB page | stock E-M5 III 1.7 and OM-5 II 1.1 make 0 stores. A test build with driver data in a `0xff` gap made 31 cached and 55 uncached stores during boot and gave a black screen on the camera. Its fix makes 0 stores and boots[^cam1] |
| 0011 serial-bus-tap | `OM_SERTAP=FILE` | `src/core/sertap.mjs`. Logs every transfer and receive started through the serial controller driver (fact `sio` tx_start / rx_start) on any channel, with index, bytes, count and caller. FAIL on an IIC address byte `0x00`. 0007's standing probes become named groups | a test build whose grafted expander driver sent its unfilled buffer, `00 00 01` where the OM-5's own driver sends `1c 08 1d`. USB was dead and a Wi-Fi start reset the camera. Its fix sends `1c 08 1d` and works[^cam1] |

*Patches that fail a build the camera would crash on. Each was checked against a failing build, its fix and stock.*

## Second and third CPUs

om-emu's native CPU 2 was for the OM-1 only. Two patches give it E-M5 III profiles, so CPU 1 or CPU 2 can run its own
firmware beside CPU 0.

| patch | switch | adds | found |
|---|---|---|---|
| 0008 cpu2-e137 | `OM_CPU2=native OM_CPU2_OUT=FILE` | an E-M5 III profile for CPU 2, with its entry, shared SRAM and idle loop | core 2 idles after 35,725 instructions. WB_MOV, MVR_MAIN and SDET start on it, and stock reaches MENU[^emu1] |
| 0009 cpu1-e137 | `OM_CPU1=native OM_CPU2_OUT=FILE` | a CPU 1 profile, with its entry, idle loop and tasks CPUCONN1, CPUCALL1 and CONTEST_CPU1. CPU 1's memory clear is skipped. A per-core kernel control block (KCB) for 0007 | core 1 idles after 56,929 instructions[^emu1]. Neither second CPU's start-up reproduces the power-on restart |

*Patches that run the second and third CPUs. The [address reference](#address-reference) has the entries and loops.*

## Another body or a sleeping task

- **Another body's block0.** Build the Player with `rom: expandImage(block0)` and `OM_EMU_MODEL` set, for example E148
  for the OM-5 II. `session.mjs --main` refuses a block0 whose bytes under the lab's hooks changed.[^fw2]
- **A dormant task.** Read its id from the halfword the boot reads. Add its entry to `lab.lt.allow`, because the lab
  runs only allowed task entries. Then call `lab.nk.svc('act_tsk', {d0: tid})`.[^fw2]
    - The OM-5 II 1.1 port-expander task is 133. It starts and waits (state 4).[^emu1]
    - On the OM-5 1.2 the same driver is task 133 too (`--start-tid 133`).[^fw2]
- **Comparing transfers.** `sertap_run.mjs --ref STOCK.json` lines up the started task's first transfers with a stock
  run's by position, and compares the address byte and length.[^fw2]

## Limits

- **Late second CPUs.** CPUs 1 and 2 start after CPU 0 has booted, not beside its start-up. So the window where CPU 0
  asks another CPU's kernel for an object before that kernel is up never opens. On the camera that is a
  fault.[^fw2]
- **One second core at a time.** Only one of CPU 1 and CPU 2 runs at a time.
- **Early start-up.** om-emu skips the early start-up stages and the reset head's copies.
- **Missing hardware.** There is no sensor, image engine, ARM, Wi-Fi or memory protection. Shooting-path hooks are
  mostly not reached.
- **Lab writes.** The lab writes memory directly, so the cache model counts only CPU uncached stores by default.
  `OM_DCACHE_ALL=1` also counts lab and device writes, and gives about 42,000 false reports on stock.

## Address reference

E-M5 III 1.7 addresses unless a body is named. Block0 functions are at base `0x60021020`. CPU 1 and CPU 2 addresses
are in their own code space.

| item | address |
|---|---|
| kernel object lookup (0007) | `0x60030eff` |
| camera fault in that lookup, cross-CPU | `0x60030f01` |
| test build's driver data in a `0xff` gap (0010) | `0x6002ad80` |
| OM-5 II 1.1 port-expander task id word | `0x6004144e` |

*CPU 0 addresses the patches use or found.*

| item | address |
|---|---|
| CPU 2 entry | `0x50006771` |
| CPU 2 idle loop | `0x50037052` |
| CPU 1 entry | `0x500062fc` |
| CPU 1 idle loop | `0x50036c9c` |
| CPU 1 memory clear (skipped) | `0x50000466` |
| shared SRAM | `0x8ff00000` |
| per-core KCB | `0x8ff00004` + 4 × cpu |

*Second and third CPU profiles in patches 0008 and 0009.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when. This page was first written on
2026-11-23.

[^fw1]: Checked by running upstream's `bin/test-pure.mjs` with all eleven patches applied.
[^fw2]: Read in the om-emu code and our driver scripts.
[^emu1]: Seen in om-emu with our patches applied.
[^cam1]: Seen on our E-M5 III using test firmware. The emulator check fails the broken build and passes its fix.
[^inf1]: Inferred.
[^pol1]: om-emu's licence, MIT since its commit `18a8162` on 2026-11-14.

