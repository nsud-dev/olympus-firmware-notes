# Handheld High Res Shot (HHHR; internal: pixshift SR handheld, `iseq_pixshift_sr`)

High Res Shot combines several frames, taken with the sensor shifted by tiny amounts, into one 50 MP picture. The
E-M5 III can do this on a tripod. The OM-5 can also do it handheld: it measures how the camera moved between frames and
aligns them before combining. That handheld version (HHHR) is the second big feature this project is bringing over.

**Where it stands (2026-11-13):** the port is being built and tested in small steps, each proving one piece on the
camera. Nothing user-visible yet.

- **Proven on the camera:** the OM-5's four image-engine programs for HHHR (jobs 14-17) load onto the E-M5 III through
  its own flash path; the memory HHHR needs is free during a High Res shot; and our code can power the ARM co-processor
  (which does part of the maths) without Wi-Fi and switch it off again cleanly (the "ARM lease" is solved).
- **Unproven:** whether jobs 14-17 actually compose a correct picture on the E-M5 III's chip. They have been loaded,
  not yet run on real frames.
- **Next:** a build that sends one request to the ARM's `hhhr` helper is ready but not yet run. It also carries a
  small read-only memory peek on the stock Wi-Fi debug shell, so HHHR runs can be watched from a laptop the way the
  Live ND runs were. After that, job 16 runs on a test pattern without the ARM.

Terms used here:

- **Tripod vs handheld High Res**: the same feature, picked by a "Shooting Method" setting on the OM-5.
- **Jobs 14-17**: the OM-5's image-engine programs that compose, fill, convert and resize the HHHR result (see
  [image engine](../hardware/image-engine.md)).
- **ARM / CA9 / `hhhr`**: the Cortex-A9 co-processor and the small Linux program on it that computes alignment matrices
  (see [ARM co-processor](../hardware/arm-coprocessor.md)). **ISC** is the mailbox between the two sides.
- **Take lease**: our name for asking the camera's own CA9 power manager to keep the ARM running for a shot.

Tags: **[code]** read in the firmware, **[camera]** seen on a real E-M5 III, **[inferred]** not traced or tested.

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
- ARM `hhhr` daemon request (from its binary): frame index +8 == 0 is the reference path and maps the **+0 Y pointer** (~0x13f000 B); nonzero maps +4 (+0x40, ~0x5800 B). Both mmaps are PROT_READ/MAP_SHARED (r2=1, r3=1 at 0x947c/0x9638), so the ARM only reads that memory. An ISC error on the ARM side makes the daemon exit. (An earlier handoff note said frame 0 maps only +4; that was our error, corrected by another tool's build and checked 2026-11-05.) [code]
- Pool objects come in three classes: base (ctor 0x603f8aa6, vtable 0x6053e698, 40 pools) has its in-use word at **+4**; bitmap class (0x603f92dc, vtable 0x6053e740) and two-block class (0x603f96c6, vtable 0x6053e778) have it at +64 (up to 6 words). Proof: vtable +44 usage methods 0x603f8fee / 0x603f934f / 0x603f9732. (An earlier handoff note said all pools use +64; corrected 2026-11-05.) [code]
- OM-5 II changed jobs 14/15; stay on OM-5 1.2. OM-1 jobs unusable. [code]

## Test ladder

The planned stages, each a separate camera test:

ARM ping (Wi-Fi on and off) · memory census in a tripod High Res shot · dry runs of jobs 14-17 · motion detection
(mdet type 17) · handheld burst capture · compose to a file · record · menu.

## What we've learned so far, in short

- **The image-engine programs load.** All four OM-5 programs (jobs 14-17) load through the camera's own flash path and
  check out (2026-11-05). Running them on real frames is still to come. [camera]
- **The memory is there.** A census during a tripod High Res shot showed the planned HHHR layout is otherwise unused;
  HHHR reuses the tripod mode's memory. [camera]
- **The ARM is off unless something starts it.** A first ping with Wi-Fi off powered the camera off. The ARM isn't
  running with wireless off, or even with wireless on until a phone connects. [camera]
- **We can start it ourselves.** The camera's CA9 power manager takes requests from two owners, "Take" and "Wi-Fi".
  Posting a Take request mid-shot reset the camera; doing it between shots works, and turns the ARM on and off cleanly
  without Wi-Fi (2026-11-06). [camera]
- **Next:** one request to `hhhr` on mailbox channel 30, then job 16 on a test pattern.

## Open questions

TruePic VIII running jobs 14-17; ARM power with wireless off; live buffers during High Res; IS control for handheld
(possible separate MCU: check prop 7729 readers 0x6058e07e/0x60592ca2). Since 2026-11-06 the IS controller is known to
be a separate sub-CPU, see [stabiliser](../hardware/stabiliser.md).

