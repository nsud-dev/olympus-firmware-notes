# Handheld High Res Shot (HHHR; internal: pixshift SR handheld, `iseq_pixshift_sr`)

High Res Shot combines several frames, taken with the sensor shifted by tiny amounts, into one 50 MP picture. The
E-M5 III can do this on a tripod. The OM-5 can also do it handheld: it measures how the camera moved between frames and
aligns them before combining. That handheld version (HHHR) is the second big feature this project is bringing over.

**Where it stands (2026-11-07):** the port is being built and tested in small steps, each proving one piece on the
camera. Nothing user-visible yet.

- **Proven on the camera:** the OM-5's four image-engine programs for HHHR (jobs 14-17) load onto the E-M5 III through
  its own flash path; the memory HHHR needs is free during a High Res shot; and our code can power the ARM co-processor
  (which does part of the maths) without Wi-Fi and switch it off again cleanly (the "ARM lease" is solved).
- **Unproven:** whether jobs 14-17 actually compose a correct picture on the E-M5 III's chip. They have been loaded,
  not yet run on real frames.
- **Next:** P2c sends one request to the ARM's `hhhr` helper; it is built and reviewed but not yet run.

Terms used here:

- **Tripod vs handheld High Res**: the same feature, picked by a "Shooting Method" setting on the OM-5.
- **Jobs 14-17**: the OM-5's image-engine programs that compose, fill, convert and resize the HHHR result (see
  [image engine](../hardware/image-engine.md)).
- **ARM / CA9 / `hhhr`**: the Cortex-A9 co-processor and the small Linux program on it that computes alignment matrices
  (see [ARM co-processor](../hardware/arm-coprocessor.md)). **ISC** is the mailbox between the two sides.
- **Take lease**: our name for asking the camera's own CA9 power manager to keep the ARM running for a shot.
- **H0-H6, L, C, P, P2a-P2c**: our test stages and builds, in order.

Tags: **[code]** read in the firmware, **[camera]** seen on a real E-M5 III, **[inferred]** not traced or tested.
Earlier status line (2026-11-05): OM-5-based port plan done; H0/H1 handoff for the maintainer's tool;
the HHHR work now builds stacked on the Live ND head (E10f). H0/H1 candidate from the maintainer's tool (SHA b069b0aa…) rebuilt
byte-identical and reviewed 2026-11-05.

## How the OM-5 does it (OM-5 1.2, our donor)

- A **method of High Res Shot**, not a separate mode: prop 7729 "Shooting Method" (setting 1680) picks tripod/handheld;
  9 code readers branch on it (pool select 0x602bcb39: 0x6100 handheld vs 0x4f00 tripod). [code]
- Flow: prep → api_start (if S+flags) → HsContTake per-frame callback → api_comp (up to 16 frames on E-M1 III; OM-5 keeps 12):
  per-frame Y image, mdet motion estimation vs frame 1 (`mdet_hhhr_request`, type 17), **ARM `hhhr`** 3×3 matrices
  (ISC ch30/31), **DSP job 14** compose into 4 planes 10416×7824 → state 34 PixShiftSrHandHeldEnd → job 15 fill, 16 RGB,
  17 resize → 50 MP output (`term_post_50m`). Done callback always called (also on abort). [code]
- OM-5 module 0x6067f9xx-0x606871xx (~30 KB, 232 named fns, slave-ASIC paths dropped vs E-M1 III). API: init 0x6067d37a,
  start 0x6067d39d, comp 0x6067d3f0, term 0x6067d45b, query 0x6067d4c8, end 0x6067d527. [code]

## What the E-M5 III already has

- Tripod High Res (states 25-30, pool 0x4f00, 50 MP record path) and the ARM `hhhr` daemon (started at boot, identical to
  E-M1 III's apart from addresses). [code]
- The MN103 HHHR module, prop 7729, pool 0x6100, state 34, jobs 14-17 are **compiled out**. Forcing the debug flag
  `fcs seq set2 6` won't work. [code]

## Facts for the port

These are the constraints the port has to respect: memory, image-engine programs, code space and the ARM link.

- Memory: OM-5 HHHR buffers ~640 MB (planes 0x5f00/0x6200 4×28 MB each, 0x6000 4×14 MB, 0x6100 12×31 MB). E-M5 layout must be
  designed (55 of 68 buffer ids differ); proposed in 0xb0000000-0xdec39800; no new ids/lock tags, use an adapter. [code]+[inferred]
- DSP: OM-5 jobs 14 (0x41800), 15 (0xd600), 16 (0x29c00), 17 (0x7600); flash room bank 6 0x45c86e00-0x45d60000; RAM gap
  0xa4277140-0xa42bf540 (296 KB) fits job 14 or 15+16+17. [code]
- Code space: ~45 KB into section 9 upper 0x613d4000-0x613fe800 (section 9 end immediate 0x60045e13 must go to 0x613fe800);
  hooks need section-9 ready guards; guard area nearly full (98 B) → shared guard trampoline. End state 38. [code]
- ISC send 0x61205800, recv 0x6120581c; E-M5 has no ch30 caller. [code]
- ISC receive 0x6120581c **blocks** (service code 3); non-blocking receive = dispatcher 0x61206cfe with d0 0x15C00002, returns -5 when empty. [code] 2026-11-05
- ARM `hhhr` daemon request (from its binary): frame index +8 == 0 is the reference path and maps the **+0 Y pointer** (~0x13f000 B); nonzero maps +4 (+0x40, ~0x5800 B). Both mmaps are PROT_READ/MAP_SHARED (r2=1, r3=1 at 0x947c/0x9638), so the ARM only reads that memory. An ISC error on the ARM side makes the daemon exit. (An earlier handoff note said frame 0 maps only +4; that was our error, corrected by the maintainer's tool's build and checked 2026-11-05.) [code]
- Pool objects come in three classes: base (ctor 0x603f8aa6, vtable 0x6053e698, 40 pools) has its in-use word at **+4**; bitmap class (0x603f92dc, vtable 0x6053e740) and two-block class (0x603f96c6, vtable 0x6053e778) have it at +64 (up to 6 words). Proof: vtable +44 usage methods 0x603f8fee / 0x603f934f / 0x603f9732. (An earlier handoff note said all pools use +64; corrected 2026-11-05.) [code]
- OM-5 II changed jobs 14/15; stay on OM-5 1.2. OM-1 jobs unusable. [code]

## Test ladder

The planned stages, each a separate camera test:

H0 ARM ping (Wi-Fi on/off) · H1 memory census in a tripod High Res shot · H2 DSP dry runs jobs 14-17 · H3 mdet type 17 ·
H4 handheld burst capture · H5 compose to file · H6 record · U1/U2 menu.

## What we've learned so far, in short

- **The image-engine programs load.** Build L loaded all four OM-5 programs (jobs 14-17) through the camera's own flash
  path and checked them (run 1 passed, 2026-11-05). Running them on real frames is still to come.
- **The memory is there.** A census during a tripod High Res shot (C run 1) showed the planned HHHR layout is otherwise
  unused; HHHR reuses the tripod mode's memory.
- **The ARM is off unless something starts it.** A first ping with Wi-Fi off (P) powered the camera off. P2a showed the
  ARM isn't running with wireless off, or even with wireless on until a phone connects.
- **We can start it ourselves.** The camera's CA9 power manager takes requests from two owners, "Take" and "Wi-Fi".
  Posting a Take request mid-shot reset the camera (P2b); doing it between shots works, and P2b3 turned the ARM on and
  off cleanly without Wi-Fi (2026-11-06).
- **Next:** P2c, one request to `hhhr` on mailbox channel 30.

## Build and research log

The full record, oldest first.

- [code] 2026-11-05: E-M5 III DSP programming tables have 18 slots (0-17); slots 14-17 are return stubs 0x60319bce/bd1/bd4/bd7 in both primary 0x60257ab0 and alternate 0x60257b88 (as 11/12 were before Live ND); job 18 has no slot. OM-5 setters 14-17 = 0x6032a094/a26f/a2d6/a419 (table 0x6025f8e8).
- [code] 2026-11-05: Stage A+B candidate af102801 reviewed (rebuilt identical): P uses fixed 0xb0000000 (no CPU access), jobs 14-17 staged inert at bank6 0x45c86e00-0x45d06e00. Packet ABI: E-M5 submit 0x603185eb allocates 76 B (payload job +60, slot +63); OM-5 0x60328a27 allocates 84 B (+68/+71); donor setters need an indirect shadow payload. Live ND bridge 0x607ac076 only admits job 11. Bank 6 last 32 B (0x45d5ffe0) are a trailer, not free.
- [code] 2026-11-05: L candidate f8af6d03 reviewed (rebuilt identical): one main frame (key 1-8, addr < 0xbe0b8a00), four programs loaded via native mode-258 flash path (0x600c4922: a0 source, a1 dest; flash mutex (0x60040d24) with timeout 20), sum32 check, release; quarantine on mismatch. Native copy helper 0x60022180 clears d0 at 0x6002234f, so its return proves nothing. OK for one L camera run.
- [camera] 2026-11-05: L run 1 PASSED on f8af6d03: status 0, frame key 2 at 0xb1f47600, all four OM-5 programs (jobs 14-17) loaded via native flash path with matching sum32, frame released, free count 19->18->19, 51 ms total (job 14 11.8 ms). First 32 bytes match the program files (all four share the same header).
- [camera] 2026-11-05: C census run 1 (f8af6d03): tripod High Res uses pool 0x4f00 = 8 frames at 0xb0000000-0xbfa3b000 (all 8 in use, main pool idle); no other used pool lies in the planned HHHR layout (0xb0000000-0xc0bc0000, 0xc4000000-0xd9811200); 0xc4 block unused. HHHR selects pool 0x6100 instead of 0x4f00, so it reuses that memory. Snapshots only.
- [camera] 2026-11-05: P ping run 1 with Wi-Fi/BT off (f8af6d03): request consumed, screen black then camera powered off; no log; camera fine afterwards. [inferred] the CA9 (ARM) is stopped with wireless off and an ISC 30 send to it is fatal, not a timeout; HHHR must check/request CA9 power (TSK_CA9PWR_MNGR) before ISC. Don't rerun P until it checks the CA9 state.
- [code] 2026-11-05: CA9 started flag = byte 0xa2624f09 (getter 0x60059129, set 0x60058f6f, cleared 0x6005909f; native console send gated on it at 0x60057220). ISC dispatcher/send locks spin forever, so the P failure was not bounded by P's timeouts. HHHR must hold a CA9 start (via the power manager) for the whole shot.
- [code] 2026-11-05: P2a candidate 9c3389a6 (on L-on-E10g) reviewed, rebuilt identical: P only reads CA9 flags 0xa2624f09/0xa2624f08 and core id; no ISC call left anywhere in HHHR code. Main-pool key 2 = pool 0x4f00 slot 1 (overlapping allocator views), so the controller needs non-overlapping memory.
- [camera] 2026-11-05: P2a wireless off (9c3389a6): CA9-started byte 0xa2624f09 = 0, handshake 0xa2624f08 = 0, core 0, no ISC; camera fine. Confirms the ARM is stopped with wireless off, consistent with the P crash.
- [camera] 2026-11-05: P2a wireless on (Availability On, no phone connected): CA9-started byte still 0, handshake 0. [inferred] the ARM isn't started just by enabling wireless; it is probably started on demand (e.g. a phone connection). HHHR must start the CA9 itself in every case.
- [code] 2026-11-05: CA9 power is a native two-owner lease. Task TSK_CA9PWR_MNGR (loop 0x6005978d) takes 16-byte requests on message buffer u16 (0x60041252); request word +8 = low half on(1)/off(0), high half owner Take(0)/Wi-Fi(1); flags Take 0xa2624f0c, Wi-Fi 0xa2624f10. Take off stops only if Wi-Fi isn't held; Wi-Fi off (0x00010000) always stops, then restarts if Take is held. E-M5 III never uses Take (shell only); OM-5 HHHR does (take task 0x602b7b51, posts Take on when props 61633+7729 are 1). Start worker waits for sccore's ISC ch 27 boot message, then sets 0xa2624f09. HHHR plan: post Take on/off async (0x600514a2, +0 = 0), never 0x00010000; P2b lease test with no ISC.
- [inferred] 2026-11-05: P2b terminal policy (after the tool's spec stop): limits 20 shots/60 s checked only in the shot hook; on the limit shot one logged Take-off if on was enqueued and off not; only rc 0 = enqueued, no retries; refuse to arm if Take is pre-held; no unlogged native action (intent record before each post). Source: private notes design/P2B-DECISIONS.md
- [code] 2026-11-05: no per-channel readiness on the MN103 side; native senders (console, BLE 0x612f9b4b) only check 0xa2624f09. ARM S99oly starts sccore and hhhr in the background together, so wait a settle time after 0xa2624f09 = 1 before ch 30. ARM Linux uses MN 0xc0000000..0xc2aa0000 while running.
- [camera] 2026-11-06: P2b run 1 (d994e390, wireless off): Take on posted and enqueued (return 0), then the camera reset; no record after shot 1. [inferred] cause open: the manager copies the ARM image from flash (0x60058c3c) and powers the CA9 mid-capture; an ARM watchdog IRQ 171 (0x600584ba) spins the MN103. Pool overlap is weak (only pools 800/832 overlap ARM RAM 0xc0000000..0xc2aa0000; census saw nothing there). Next: P2a + phone connected + silent single. HHHR planes must end at 0xc0000000 (PLAN s3 overlaps ARM RAM). Don't rerun P2b.
- [camera] 2026-11-06: P2a with phone connected in OI.Share: 0xa2624f09 = 1, 0xa2624f08 = 1, silent singles normal, no reset, but shot with the OI.Share remote (body controls locked while connected). So the ARM can run during native remote shooting; with body controls it's untested, and the native camera may switch mode before starting it. HHHR must start the ARM outside a shot (OM-5: mode transition 0x60237696).
- [code] 2026-11-06 (build tool second opinion, checked here): the 10 s ARM-start alarm 0x60058e07 calls 0x6005832b(1) (reason 1 at 0x8ff000b4, fault request 0x99200400) -> spin 0x600584a8, so a missed ch 27 boot message faults the camera after ~10 s. Native Wi-Fi start first powers the Wi-Fi device: 0x6121f1ac(1) -> 0x6121f1f7 -> 0x6121f115 (core 0, else cross-core) -> 0x6121f09c events 0x01000003/4/2 and 117 via 0x6121f022, then the CA9 owner request. The bare Take on skips that. Lead: the ARM may not finish booting with the Wi-Fi device unpowered.
- [camera] 2026-11-06: The maintainer: the P2b reset was immediate after the shot (not ~10 s), so mid-capture start interference leads over the boot timeout. Next: P2b2 posts Take on at Idle/Standby after the shot, with reset timing noted (design/P2B2-DECISIONS.md E6/E7 on handoff/hhhr-p2b).
- [camera] 2026-11-06: P2b2 run 1: Take on posted at the first Idle/Standby change after the shot (return 0) booted the ARM with a Take-only lease (started 0xa2624f09=1, handshake 0xa2624f08=1; no 10 s boot fault, so no Wi-Fi device prep needed). Body-button silent singles with the ARM running were fine. Reset on the shot that posted Take off inside the shot hook. [inferred] Change ARM power only outside a capture; P2b3 defers Take off too (design/P2B3-DECISIONS.md on handoff/hhhr-p2b).
- [camera] 2026-11-06: P2b3 run 1 PASSED: Take on and Take off both posted at the first Idle/Standby change after a shot (return 0 each). ARM booted (started=1, handshake=1), two body-button shots normal, then clean shutdown (started, handshake, Take 0xa2624f0c all 0), no reset. HHHR can lease the ARM itself without Wi-Fi. Next: P2c ch 30 ping.
- [code] 2026-11-06: ARM /root/hhhr request (48 B on ch 30): +0 Y image ptr, +4 statistic buffer ptr, +8 u16 frame index-1, +14/+16 = 0x510/0x3cc, +18/+20 = 4, +0x2c MN result ptr (MN only). Index 0 maps (+0)+0x80000000 (~1.3 MB); index != 0 maps (+4)+0x80000000+0x40 (~22 KB). mmap result not checked (bad pointer can crash the daemon); reply 112 B on ch 31 to cpu 0. OM-5 sends from compose 0x603911c4 via hhhr_arm_calc 0x60376613 (send 100 ms, then blocking receive). P2c plan: one index-1 ping at a zeroed pool frame, non-blocking receive only. private notes design/P2C-DECISIONS.md
- [code] 2026-11-06: P2c G1 audit (build tool, checked here): the native ARM statistic buffer is pool memory at 0xab6f44c0, while our P2c ping points at 0xb… pool frames; native am2arm 0x600590c9 is MN & 0x3fffffff and the hhhr +0x80000000 mapping only holds for MN 0xa…/0xb… addresses, so 0xb frames are fine. Answered on private notes #1 (commit 710e82b).
- [code] 2026-11-06/07: P2c `8a74ddf4…` (one ch30 ping when armed, log HHR6P) reviewed OK, preflash PASS with warnings (REPORT.md in the zip); not yet run on the camera.

## Open questions

TruePic VIII running jobs 14-17; ARM power with wireless off; live buffers during High Res; IS control for handheld
(possible separate MCU: check prop 7729 readers 0x6058e07e/0x60592ca2). Since 2026-11-06 the IS controller is known to
be a separate sub-CPU, see [stabiliser](../hardware/stabiliser.md).

