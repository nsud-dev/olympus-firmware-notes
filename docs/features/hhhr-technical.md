# Handheld High Res Shot: technical notes


<!-- house style -->
> **Technical reading.** The detailed version of [Handheld High Res Shot](hhhr.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

High Res Shot combines several frames, taken with the sensor shifted by tiny amounts, into one 50 MP picture. The
E-M5 III can do this on a tripod. The OM-5 can also do it handheld. It measures how the camera moved between frames and
aligns them before combining. That handheld version, Handheld High Res (HHHR), is the second big feature this project is
bringing over.

The firmware's internal names are pixshift SR handheld and `iseq_pixshift_sr`. These notes use the short form HHHR.

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred, amber = a correction.

## Terms

- **Tripod and handheld High Res** are the same feature, picked by a "Shooting Method" setting on the OM-5.
- **Jobs 14 to 17** are the OM-5's image-engine programs that compose, fill, convert and resize the HHHR result. See
  [Image engine](../hardware/image-engine.md).
- **ARM, CA9 and `hhhr`.** The ARM is the Cortex-A9 (CA9) co-processor. `hhhr` is the small Linux program on it that
  computes alignment matrices. See [ARM co-processor](../hardware/arm-coprocessor.md).
- **ISC** is the mailbox between the two sides.
- **Take lease** is our name for asking the camera's own CA9 power manager to keep the ARM running for a shot.

## Status

The port was built and tested in small steps, each proving one piece on the camera. Nothing is user-visible.[^pol1]
The research closed before the next build ran. See [Status](hhhr.md#status) on the light page.

- **Proven on the camera.** The OM-5's four image-engine programs for HHHR (jobs 14 to 17) load onto the E-M5 III
  through its own flash path.[^cam1] The memory HHHR needs is free during a High Res shot.[^cam2] Our code can power
  the ARM co-processor, which does part of the maths, without Wi-Fi and switch it off again cleanly. The "ARM lease" is
  solved.[^cam3]
- **Unproven.** Whether jobs 14 to 17 actually compose a correct picture on the E-M5 III's chip. They have been loaded,
  not yet run on real frames.
- **Next.** A build that sends one request to the ARM's `hhhr` helper is ready but not yet run. It also carries a
  small read-only memory peek on the stock Wi-Fi debug shell, so HHHR runs can be watched from a laptop the way the
  Live ND runs were. After that, job 16 runs on a test pattern without the ARM.

## On the OM-5

The OM-5 1.2 is our donor. HHHR there is a method of High Res Shot, not a separate mode. Prop 7729 "Shooting Method"
(setting 1680) picks tripod or handheld. Nine code readers branch on it. The pool select function picks pool `0x6100`
for handheld and `0x4f00` for tripod.[^fw1]

A handheld shot runs in this order.[^fw1]

1. Prep, then `api_start` (if S plus flags).
2. `HsContTake` runs a per-frame callback.
3. `api_comp` takes up to 16 frames on the E-M1 III. The OM-5 keeps 12. For each frame:
    1. a Y image is made
    2. motion detection (mdet) estimates the motion against frame 1 (`mdet_hhhr_request`, type 17)
    3. the ARM `hhhr` program computes a 3 × 3 matrix, over ISC channels 30 and 31
4. Image-engine job 14 composes the frames into 4 planes of 10416 × 7824.
5. The sequence reaches state 34, `PixShiftSrHandHeldEnd`.
6. Job 15 fills, job 16 converts to RGB and job 17 resizes, giving the 50 MP output (`term_post_50m`).

The done callback is always called, also on abort.[^fw1]

The OM-5 module is about 30 KB with 232 named functions. The slave-ASIC paths of the E-M1 III version are dropped. Its
API has init, start, comp, term, query and end entry points.[^fw1] The addresses are in the
[address reference](#address-reference).

## On the E-M5 III

The E-M5 III has tripod High Res, with states 25 to 30, pool `0x4f00` and the 50 MP record path. It also has the ARM
`hhhr` daemon, started at boot and identical to the E-M1 III's apart from addresses.[^fw1]

The MN103 HHHR module, prop 7729, pool `0x6100`, state 34 and jobs 14 to 17 are compiled out. Forcing the debug flag
`fcs seq set2 6` won't work.[^fw1]

## Constraints for the port

These are the constraints the port has to respect: memory, image-engine programs, code space and the ARM link.

### Memory

The OM-5's HHHR buffers come to about 640 MB.[^fw1]

| pool | frames |
|---|---|
| `0x5f00` | 4 × 28 MB |
| `0x6200` | 4 × 28 MB |
| `0x6000` | 4 × 14 MB |
| `0x6100` | 12 × 31 MB |

*OM-5 HHHR buffer pools. Read in the OM-5 firmware.*

The E-M5 layout must be designed, because 55 of 68 buffer ids differ.[^fw1] The proposed layout sits in one range of
pool memory (see the [address reference](#address-reference)). It adds no new ids or lock tags and uses an adapter
instead.[^inf1]

### Image-engine programs

| job | size |
|---:|---:|
| 14 | `0x41800` |
| 15 | `0xd600` |
| 16 | `0x29c00` |
| 17 | `0x7600` |

*OM-5 jobs 14 to 17 and their sizes in bytes.[^fw1]*

There is flash room for them in bank 6. A 296 KB gap in engine RAM fits job 14, or jobs 15, 16 and 17 together.[^fw1]

The OM-5 II changed jobs 14 and 15, so the port stays on the OM-5 1.2. The OM-1 jobs are unusable.[^fw1]

### Code space

The module needs about 45 KB in the upper part of section 9. The immediate that holds the end of section 9 must be moved
to the end of that range.[^fw1] Hooks need section-9 ready guards. The guard area is nearly full, with 98 B left, so the
hooks share one guard trampoline. The end state is 38.[^fw1]

### ARM link

The E-M5 III has no caller of ISC channel 30.[^fw1]

The ISC receive call blocks (service code 3). The non-blocking receive is the dispatcher called with `d0` =
`0x15c00002`. It returns -5 when the mailbox is empty.[^fw2]

The ARM `hhhr` daemon's request is read from its binary.[^fw2]

- Frame index (+8) equal to 0 is the reference path. It maps the Y pointer at +0, about `0x13f000` bytes.
- A nonzero index maps +4 (+`0x40`), about `0x5800` bytes.[^fix1]
- Both mmaps are `PROT_READ`/`MAP_SHARED` (r2=1, r3=1 in the binary), so the ARM only reads that memory.
- An ISC error on the ARM side makes the daemon exit.

### Pool objects

Pool objects come in three classes.[^fw2]

- The base class, used by 40 pools, has its in-use word at +4.
- The bitmap class and the two-block class have it at +64, up to 6 words.[^fix2]

The proof is each class's usage method at vtable +44.[^fw2] Constructors, vtables and methods are in the
[address reference](#address-reference).

## Test ladder

The planned stages, each a separate camera test:

1. ARM ping, with Wi-Fi on and off
2. memory census in a tripod High Res shot
3. dry runs of jobs 14 to 17
4. motion detection (mdet type 17)
5. handheld burst capture
6. compose to a file
7. record
8. menu

## Camera results

- **The image-engine programs load.** All four OM-5 programs (jobs 14 to 17) load through the camera's own flash path
  and check out. Running them on real frames is still to come.[^cam1]
- **The memory is there.** A census during a tripod High Res shot showed the planned HHHR layout is otherwise unused.
  HHHR reuses the tripod mode's memory.[^cam2]
- **The ARM is off unless something starts it.** A first ping with Wi-Fi off powered the camera off. The ARM isn't
  running with wireless off, or even with wireless on until a phone connects.[^cam2]
- **We can start it ourselves.** The camera's CA9 power manager takes requests from two owners, "Take" and "Wi-Fi".
  Posting a Take request mid-shot reset the camera. Doing it between shots works, and turns the ARM on and off cleanly
  without Wi-Fi.[^cam3]
- **Next.** One request to `hhhr` on mailbox channel 30, then job 16 on a test pattern.

> [!WARNING]
> A ping to the ARM with Wi-Fi off powered the camera off. A Take request posted in the middle of a shot reset the
> camera. Posting Take requests between shots works.

## Older bodies

- **E-M5 II 4.1.** Tripod High Res (40 MP, `pixshift_*`) is native. HHHR as we port it needs the ARM `hhhr` helper and
  jobs 14 to 17, and the E-M5 II has no ARM co-processor at all. Impossible as designed.[^fw3][^inf2]
- **E-M5 (Mark I) 2.3.** It has no pixel-shift code. Impossible.[^fw3]

See also: [older bodies](../bodies/comparison-technical.md#older-bodies-e-m5-ii-and-e-m5-mark-i).

## Open questions

- TruePic VIII running jobs 14 to 17.
- ARM power with wireless off.
- Live buffers during High Res.
- IS control for handheld. A separate MCU was possible. The check is the two other readers of prop 7729. The IS
  controller is now known to be a separate sub-CPU.[^fw4] See [Stabiliser](../hardware/stabiliser.md).

## Address reference

E-M5 III 1.7 addresses unless the OM-5 is named. Functions are block0 addresses (base `0x60021020`).

| item | address |
|---|---|
| pool select | `0x602bcb39` |
| HHHR module | `0x6067f9xx` to `0x606871xx` |
| API init | `0x6067d37a` |
| API start | `0x6067d39d` |
| API comp | `0x6067d3f0` |
| API term | `0x6067d45b` |
| API query | `0x6067d4c8` |
| API end | `0x6067d527` |

*OM-5 1.2 addresses.*

| item | address |
|---|---|
| proposed HHHR buffer layout | `0xb0000000` to `0xdec39800` |
| flash room in bank 6 | `0x45c86e00` to `0x45d60000` |
| engine RAM gap (296 KB) | `0xa4277140` to `0xa42bf540` |
| section 9 upper (code space) | `0x613d4000` to `0x613fe800` |
| immediate holding the end of section 9 | `0x60045e13`, must become `0x613fe800` |

*Memory and code space on the E-M5 III.*

| item | address |
|---|---|
| ISC send | `0x61205800` |
| ISC receive (blocking) | `0x6120581c` |
| ISC dispatcher (non-blocking receive with `d0` = `0x15c00002`) | `0x61206cfe` |
| `hhhr` daemon mmap arguments (ARM binary) | `0x947c`, `0x9638` |
| prop 7729 readers to check for IS control | `0x6058e07e`, `0x60592ca2` |

*ARM link and open checks.*

| class | constructor | vtable | usage method (vtable +44) | in-use word |
|---|---|---|---|---|
| base (40 pools) | `0x603f8aa6` | `0x6053e698` | `0x603f8fee` | +4 |
| bitmap | `0x603f92dc` | `0x6053e740` | `0x603f934f` | +64 |
| two-block | `0x603f96c6` | `0x6053e778` | `0x603f9732` | +64 |

*Pool object classes.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware.
[^fw2]: Read in the firmware, 2026-11-05.
[^fw3]: Read in the firmware, 2026-11-21.
[^fw4]: Known since 2026-11-06. See [Stabiliser](../hardware/stabiliser.md).
[^cam1]: Seen on our E-M5 III, 2026-11-05.
[^cam2]: Seen on our E-M5 III.
[^cam3]: Seen on our E-M5 III, 2026-11-06.
[^inf1]: Read in the firmware for the ids, inferred for the layout.
[^inf2]: Inferred from the firmware, 2026-11-21.
[^pol1]: Project status as recorded on 2026-11-13.
[^fix1]: Corrected 2026-11-05. See [History](#history).
[^fix2]: Corrected 2026-11-05. See [History](#history).

## History

- 2026-11-05: an earlier handoff note said frame 0 maps only +4. That was our error, corrected by the build tool's
  build and checked the same day.
- 2026-11-05: an earlier handoff note said all pools use +64. Corrected the same day.

