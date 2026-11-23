# om-emu patches: the E-M5 III's 32-bit image layer

Four small changes to the om-emu emulator so it shows the picture layer the camera's vector GPU (c3d) draws into, and
a stand-in for live view under it. Used by the scripts in `../c3d/` and for the notes pages `docs/hardware/c3d-gpu.md`
and `docs/hardware/graphics-pipeline.md`. They contain no firmware bytes: you need your own firmware file.

## Licence and credit
om-emu is by the om-emu contributors, MIT licence. These patches modify MIT-licensed code and carry om-emu's licence:
Copyright (c) 2026 om-emu contributors, MIT (see om-emu's `LICENSE`). Our own scripts here (`apply.sh`,
`img2poke.py`, `vsclog.mjs`): MIT.

## Set-up
- An om-emu clone at commit `ccfe2e0`, node 22 or newer, and the E-M5 III firmware unpacked with
  `node emu/bin/fetch-fw.mjs --model E137`.
- `sh apply.sh OM_EMU_CLONE` applies the nine patches in order (0003 builds on 0001; 0005-0009 on 0001-0004, 0009 on 0008).

## The patches
- `0001-kind2-img-planes.patch`: om-emu skipped every IMG plane on the E-M5 III's display controller (kind 2), so the
  layer the c3d GPU draws was never shown. It now draws IMG planes in format 3 (32-bit, per-pixel alpha) at 1:1.
  Format 0 (YC, live view) and scaled planes are still refused.
- `0002-vsc-write-log-hook.patch` + `vsclog.mjs`: logs every changed display-controller register write
  (`node --import vsclog.mjs emu/bin/session.mjs ...`, lines `VSC chN +0xOFF = 0xVAL` on stdout).
- `0003-live-view-backdrop.patch`: om-emu has no live view, so transparent layers showed over plain black. With
  `OM_BACKDROP=FILE.rgb` (720 x 480 raw RGB) the screen compositor starts from that picture. Make one with
  `python3 ../c3d/backdrop.py OUT.rgb [PHOTO | --test]` (default: a generated lake-at-dusk landscape).
- `0004-bitmap-no-table.patch`: om-emu's OSD draw engine refused a run-length bitmap sent with no colour table
  (error BMP_LUT), so those pictures were never drawn. The E-M5 III's tone-curve grid (picture 0x1039, format 0x0A,
  a 4-bit index over a 4-bit run) is one; it draws on the camera. Such a bitmap now writes its index straight into
  the plane, and one sent with the loaded table (bit 11 only) goes through that table. Colours are inferred.
- `0005-olyfw-checks-dcache-secmon.patch` (2026-11-22, our notes): two optional checks for the
  regression cases in `../regress/`. A data-cache coherence model (`src/core/dcache.mjs`: stale cached reads, lost
  write-backs and stale uncached reads where code mixes the cached 0x6… and uncached 0xA… views) and a section
  first-touch monitor (`src/core/secmon.mjs`: when each block0 section is first fetched or read, to compare a build's
  boot order with stock's). Settings in `src/core/olyfw.mjs`, set from the environment by `host/olyfwenv.mjs`
  (`node --import ./host/olyfwenv.mjs bin/session.mjs ...` with `OM_DCACHE=report OM_DCACHE_OUT=FILE`,
  `OM_SECMON=FILE`). Off by default: nothing changes, and upstream `bin/test-pure.mjs` passes.
- `0006-heap-fill.patch`: `OM_HEAP_FILL=deadbeef` makes S-HEAP fill each block it hands out or takes back, so reads
  of fields nobody set fault instead of reading 0.
- `0007-olyfw-kernel-checks.patch` (2026-11-22): `OM_KCHECK=FILE` installs two checks when the native kernel boots
  (`src/lab/kcheck.mjs`, run through a standing probe set in `src/core/interp.mjs` that the debugger's probes leave
  alone): a blocking service (twai_sem, wai_flg, twai_flg, loc_mtx, dly_tsk, trcv_dtq, tsnd_dtq) entered outside a
  task's context, and the kernel's object lookup (E137 0x60030eff) on another CPU's object. The lab writes every CPU's
  table pointer at boot, so the second can't fault here as it does on the camera; it lists the sites.
- `0008-olyfw-cpu2-e137.patch` (2026-11-22): om-emu's native CPU 2 (`--cpu2 native`, `src/lab/cpu2.mjs`) was OM-1
  only; it now runs on the E-M5 III too (`OM_CPU2=native` for `bin/session.mjs`, `OM_CPU2_OUT=FILE` writes core 2's
  status and log). The E-M5 III's CPU 2 boots differently, so `cpu2.mjs` gets an E137 profile: entry 0x50006771, the
  shared SRAM at 0x8ff00000, three CPUs, its own idle command loop (0x50037052, block 0x8ff0008c), BOOT_CPU2's two
  release words, the link and task ids the port misplaced, and four stand-ins: the UART character output, the
  data-cache purge, the cross-CPU callback tables (CPU 0's bring-up sets them, the lab doesn't) and the registry
  bootstrap (BOOT_CPU2's on the E-M5 III, which the lab already runs on CPU 0). `src/core/cores.mjs` takes the local
  page as an option (E137: 0x4700). Core 2 then boots to its idle loop (35,725 instructions), WB_MOV, MVR_MAIN and
  SDET start on it from CPU 0's boot stages, and stock reaches the shooting screen and MENU. The OM-1 test
  (`test/test_cpu2.mjs`, 30/30) and `bin/test-pure.mjs` (264/264) still pass.
- `0009-olyfw-cpu1-e137.patch` (2026-11-22): the lab's second core can run CPU 1 instead of CPU 2 on the E-M5 III
  (`OM_CPU1=native`; CPU 2 then stays stood in, `OM_CPU2_OUT=FILE` writes core 1's status and log). `cpu2.mjs` gets a
  CPU 1 profile: entry 0x500062fc, BOOT_CPU1's three release words (0x8ff00044, 0x8ff006fc, 0x8ff0004c), its idle
  command loop (0x50036c9c, block 0x8ff00064), its tasks CPUCONN1, CPUCALL1 0x500368f7 and CONTEST_CPU1 0x500337aa,
  and one more stand-in: CPU 1's memory clear (0x50000466 over 0x620a2000..0x62527100) is skipped, because in the lab
  CPU 1 starts after CPU 0 has booted and already uses that range (zeroing it faults CPU 0). The second core's KCB is
  read from the shared table (0x8ff00004 + 4 * cpu). Core 1 then boots, starts its four tasks, enters its idle loop
  (56,929 instructions) and keeps passing it (its halt word stays 0, so it sleeps in its waits between passes), and
  stock reaches the shooting screen and MENU. The kernel checks (0007) now read the running core's KCB for the
  nesting byte (without that, core 1's dly_tsk in its idle loop showed as blocking in an interrupt). `test/test_cpu2.mjs`
  (30/30), `bin/test-pure.mjs`, `kcheck_selftest.mjs` and the E137 CPU 2 run (`OM_CPU2=native`) are unchanged.
- `img2poke.py`: writes a session script that pokes a 256 x 256 picture into the layer and takes a shot.

The patches are ordinary `git diff` output, written so they could be offered to om-emu as they are.
