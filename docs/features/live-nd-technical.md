# Live ND: technical notes

> **Technical notes.** This page is the dense reference. For a readable introduction, start with [Live ND](live-nd.md).

Live ND is a "digital ND filter": instead of one long exposure through a dark filter, the camera takes several shorter
exposures and averages them into one photo. Moving water or clouds blur as if you had used an ND filter, without the
filter. The OM-5 has it; the E-M5 III, which has the same chip and sensor, doesn't. Bringing it over is this project's
main goal.

Internal names in the firmware: DIGITAL_ND, DigitalNd, iseq_nd.

**Where it stands (2026-11-20):**

- **Works on the camera:** a full Live ND shot from one press, run by our port of the OM-5's own Live ND shooting
  states: N frames at the set shutter speed, merged by the OM-5's image-engine job 11 into one photo, ND2, ND4, ND8 and
  ND16, at 1/8 s and at 1/125 s, several presses in a row with no restart in between (since 2026-11-12).
- **Live-view preview works too:** with LV Simulation on, the live view shows the Live ND blur as you'd get it in the
  photo, averaged over up to 240 frames by the OM-5's job 12, as on the OM-5 (since 2026-11-12). The borrowed frame
  memory goes back before each photo and the preview comes back after it (since 2026-11-15). Turning the shutter dial
  restarts the blur, and the light lines that showed for a moment after a photo are gone (2026-11-17).
- **Being tuned:** restarting the blur when the camera moves. It now uses the stabiliser's gyro readings, as the OM-5
  does, and felt right in a first hand-held test; the limits stay adjustable while we tune them (2026-11-17).
- **Preview and focusing (2026-11-18):** the preview now survives repeated autofocus, and the white lines that
  continuous AF (C-AF) drew over it are gone.
- **Noise Reduction (2026-11-19):** the first complete dark-frame pass worked: with Noise Reduction on, the camera
  merged the light frames, then the same number of dark frames, and saved a normal photo (ND4 and ND16, ISO 200). At
  ISO 3200, NR off works, but NR on reset the camera at the save: the preview still held frames the dark pass needed.
  A fix (hand the preview frames back earlier) is built and waiting for a test; until then use NR on only at low ISO.
- **Menu (2026-11-19):** Live ND now has rows in the camera's own shooting menu, and the values survive power-off.
  Letting those rows drive Live ND (instead of our hidden settings page) is built, not tested yet.
- **Next up:** Live ND in silent single drive, not only the drive we test with (built 2026-11-20, not tested).
- **Power-on restart solved (2026-11-22):** the test builds restarted the camera once at every power-on. The cause was
  one of our memory sections ending exactly where another processor core's start-up code is staged; with the section
  end back at its stock value the restart is gone [camera]. Lesson: leave a gap (at least a cache line, better 4 KB)
  between anything we add and memory another core uses. See [gotchas](../reference/gotchas.md) and
  [caches](../hardware/mn103-cpu.md#caches).
- **Not user-ready:** these are research builds tested on one camera; nothing is released to install.

How to read this page: the first sections explain how Olympus built Live ND, how our version works and what we
learned getting it to run on the E-M5 III.

Terms used here:

- **ND2, ND4 ... ND16**: the strength of the effect, 1 to 4 stops. ND8 means 8 frames merged.
- **Job 11 / job 12**: image-engine programs from the OM-5 that merge frames (photo) and accumulate the live-view
  preview. See [image engine](../hardware/image-engine.md).
- **Route 4 / StlUhs**: the burst capture path we use to get frames (see
  [shooting sequencer](../firmware/shooting-sequencer.md)).
- **Armed**: the user has asked for Live ND (a request file on the card plus S or M mode). Unarmed, every hook falls
  through to stock behaviour.
- **Tv**: shutter time. **N**: number of frames.

Tags: **[code]** read in the firmware, **[camera]** seen on a real E-M5 III, **[inferred]** not traced or tested.

## How Olympus does it (OM-5 1.2, our donor)

The OM-5 takes N frames at the shutter speed you set and averages them on the image engine. The "digital" shutter time
it shows is N × Tv. In detail:

- Live ND on = prop 7745, ND number = prop 7761 (1..5 = ND2..ND32 in the UI), LV simulation = 7777. [code]
- Photo path: **N ≤ 16 frames at the set Tv per frame**, merged by **DSP job 11** with a computed WBClip; ND code 1..4 =
  ND2..ND16; light table 0xa26f0644 caps at 16. The "digital" shutter time (N × Tv) is derived for display. [code]
- frame_max (30 × digital time) is only for the **live-view preview** (job 12, `iseq_ndlv`, start/add/roll). [code]
- Shooting states 31 DigitalNd / 32 DarkRdy / 33 End; entered when continue_mode = 4 and ctx+2196 (Live ND flag);
  DigitalNd sends its own type-7 sensor request: kind 0x400, flag 1, fps 0 (lets frames go slower than 1/15). [code]
- Tv limit N × Tv ≤ 64 s. OM-5 and OM-5 II engines stop at **ND16**; their ND32/64/128 strings are shared UI. [code]
- OM-1 / OM-1 II: native ND64 / ND128 with the same iseq_nd design (levels to 6/7, light table 64/128, six
  `9BIT_BAYER` accumulators: accumulate, not hold). DSP jobs aren't reusable, logic is. [code]
- E-M1 III: same engine, 32-frame table. [code]

## What the E-M5 III already has

- The OM-5 plumbing is **compiled in but switched off** (take-param +119/+120 zero, identity stubs, AE ids 299-302).
  The DSP jobs and the DigitalNd states are absent. [code]
- The E-M5 III image engine runs OM-5 job 11 correctly and job 12 to completion. [camera]

## How our version works

- **Trigger:** a request file on the card chooses the ND level; the shot is taken with a silent high-speed burst press
  in S or M mode. Without the request, every change falls through to stock behaviour. [camera]
- **Shooting states:** our port of the OM-5's three Live ND states (E-M5 III states 35-37) captures N frames and ends
  the shot, as on the OM-5. The sensor request asks for kind 0x400 with fps 0, so each frame is as long as the set
  shutter time; it goes out only from the Live ND shot's own request builders. [camera]
- **Merge:** the frames are kept as they arrive; at the end OM-5 job 11 averages them into a separate output frame,
  which the camera develops and saves as the photo. ND2, ND4, ND8 and ND16 use 2, 4, 8 and 16 frames. [camera]
- **Memory:** the main image pool has 20 slots in two blocks (ids up to 8 at 0xb0000000, ids 9-20 at 0xc4000000), so a
  slot address must come from the pool, never from a stride. 16 frames fit, with spare slots for the stream. [camera]
- **Live view:** the OM-5's job-12 preview, see "Live-view preview" below.

## What we measured on the camera

- A burst without the sensor request change runs at 60 fps (16.6-16.7 ms) at every shutter time, so frames clamp to
  about 1/60 s. With the request, frames follow the set time (125.0 ms apart at 1/8 s). [camera]
- A merged ND8 (8 × 1/8 s) on a tripod has the same brightness as a single 1/8 s shot, within 0.03 EV. [camera]
- Job 11 takes 32.5 ms for 2 frames, about 87 ms for 8 and 142.5 ms for 16. [camera]
- The merged JPEG gets smaller as N rises (3.96 / 3.23 / 2.64 MB for ND2 / ND4 / ND8): less noise. [camera]
- 16 frames at 1/125 s arrive without loss, and Live ND works on several presses in a row. [camera]
- Testing a T/N exposure needs no firmware: set Tv = T/N in M. The OM-5's shutter step tables are byte-identical in
  the E-M5 III (0x604d32ae/3328/337a). [code]

## Porting the OM-5's own Live ND states

**The idea.** Our first versions merged frames ourselves after a native burst. The OM-5 instead runs three dedicated
shooting states (DigitalNd, DarkRdy, End) that capture exactly N frames, hand each to its merge engine and finish the
shot. We ported those states (E-M5 III states 35-37) so one press behaves like the OM-5.


**How it was solved (2026-11-12).** At first the camera either never ended the capture or reset itself about a second
later, and no log in memory survived the reset. Tracing every run live over the camera's own Wi-Fi debug shell (see
[Wi-Fi debug shell](wifi-debug-shell.md)) replaced that guessing. Each traced run showed one place where an E-M5 III
function behaves differently from the OM-5 function it stands in for:

- **Capture start:** the E-M5 III's start function writes -1 through three request pointers, which turns the N-frame
  sequence into an endless burst, and a zero pointer there is a write to address 0 (the reset). The port uses its own
  copy of the start without those writes.
- **Run-dry frame:** near the end the OM-5 hands out a placeholder job with frame id 0 and skips the capture call for
  it; the port has to keep that check.
- **Display at the end:** the display task's "resume live view" handler waits, with no timeout, for a flag that only the
  sequencer's event 83 sets; the Live ND end state must handle events 81, 82 and 83.
- **Output frame:** the OM-5 merges all N frames into a separate output frame that the sensor never fills; without the
  merge the saved photo is an unwritten buffer.
- **Button release:** an event with no handler in the current state makes the dispatcher print a history dump, which at
  fast shutter speeds stalls the frame refill and loses frames; the release events need no-op handlers.

The general lesson: when ported code calls an E-M5 III function, compare it with the OM-5 function it replaces, not
just the arguments. Addresses and details are on [Live ND port layers](../firmware/live-nd-port-layers.md).
The seams between ported and native code are tracked on [Live ND port layers](../firmware/live-nd-port-layers.md).

## Live-view preview

**What the OM-5 does.** With LV Simulation on, the OM-5's live view shows what the Live ND photo will look like: it
keeps a ring of recent live-view frames and averages the last frame_max of them on every new frame with image-engine
job 12 (frame_max = 30 per second of the digital exposure time, up to 240). The switch is made per frame inside the
live-view module, not by the shooting states. [code]

**What we built.** The E-M5 III has none of that code, so we added it step by step:

| step | what it proved | result |
|---|---|---|
| Plumbing | frame_max and the digital time from the E-M5 III's own AE match the OM-5's rule | [camera] passed |
| Memory peeks | the live-view raw frame on the E-M5 III: 2912 × 544 pixels, rows of 3328 bytes | [camera] passed |
| Job 12 on stored frames | job 12 runs on E-M5 III frames; its reset, add, slide and average steps give correct results | [camera] passed |
| Job 12 on live view | the per-frame hook works; job records carry the CPU they run on, so jobs from the live-view task (CPU 1) must be counted separately | [camera] first live preview, 8 frames |
| Full window | the window follows the dial up to 240 frames, kept in up to 14 borrowed main frames; live view runs at 30 fps with LV Simulation on, as on the OM-5 | [camera] passed |
| Hand-back | borrowed frames go back before a photo; menu and playback don't pass that point | [camera] passed (fix confirmed 2026-11-15) |
| Restarts | the blur restarts when the shutter speed changes; the first frames after a photo are skipped | [camera] passed 2026-11-17 |
| Shake restart | the blur restarts when the camera moves, judged from the stabiliser's gyro readings as on the OM-5 | [camera] felt right in a first test 2026-11-17; being tuned |

**Restarting the blur when the camera moves.** If you move the camera, the averaged preview smears the old view into
the new one, so the OM-5 throws the average away and starts again. It decides from the stabiliser's gyro, not from the
picture: with each live-view frame the stabiliser reports how far the camera turned, converted into live-view pixels
(one number across, one up and down). The OM-5 compares each against a limit and restarts when either is over it. The
limit grows with the exposure time: normal up to 16 s, twice as large from 16 s, four times from 32 s (with a long
exposure a little movement is expected anyway). After a restart it keeps restarting for 500 ms, so the blur doesn't
build up again while the camera is still settling. [code] 2026-11-17

The E-M5 III's stabiliser sends the same report once per live-view frame, and its firmware has the same conversion
routines, but never applies them in live view. We call those native routines on each report and use the OM-5's rule.
Readings on the camera (larger of the two numbers per frame, rough): camera on a table 0, held still in the hand about
13, picked up about 250, panned about 360. With a limit of 40 the preview kept building up when held still and
restarted on a real move, which felt right in a first test. [camera] 2026-11-17

Why not compare the pictures? Our first try did that (a sample of pixels from frame to frame). It only reacted to a big,
sudden move, and a hand waved in front of the lens set it off while the gyro didn't change. A picture test can't tell a
moving subject from a moving camera, and a moving subject (water, clouds) is exactly what Live ND is for, so the
gyro is the right input. [camera] 2026-11-17

The limit, the exposure-time scaling and the hold time are copied or guessed values; they stay adjustable on the test
builds until they're tuned for other lenses, slow pans and long exposures. [inferred]

**Memory for the preview.** The OM-5 keeps a dedicated ring of frame buffers for the preview. Like all its buffer pools,
that ring is built at every power-on and simply sits unused when the preview is off; there is no switch to a different
memory layout. On the E-M5 III we don't copy that: adding pools at power-on would change the startup code, and a mistake
there can't be recovered from the card. So our preview borrows main frames while it runs, and a dedicated pool, if we
add one, will be made when the preview starts and removed when it ends. [code]+[inferred] 2026-11-15

**Still to do:** tuning the shake restart (other lenses and focal lengths, slow pans, long exposures; the gyro reports
are described on [stabiliser](../hardware/stabiliser.md)), the dark-frame pass, and switching the preview from the menu
setting.
Coexisting with a looks preview (2026-11-19): the planned looks live-view applier works in the colour/development stage

## Limits and open items

- Main pool = 20 slots: 16 held + 2 stream at ND16. **ND32 has no native code to port** on OM-5/OM-5 II; plan is a
  two-pass merge (or running accumulator), as OM-1 does natively. [code]+[inferred]
- 2026-11-18: caduceus-om5 reports ND32/ND64 working on an OM-5 II camera after two edits only (setting 1710 allowed
  list 1..6 and the ND step selector 0x6023c850 extended to steps 5-6; the same selector is at OM-5 1.2 0x60239afb,
  ~0x607a9d4f in the E-M5 III port). That questions the "engine stops at ND16" verdict below; whether their ND64 photo merges 64
  frames or 16 dark ones is not recorded. [camera] caduceus-om5, [code] this project. details
- Single-drive trigger cuts the stream after 1 frame (cause unfound); trigger stays silent H burst until the menu stage. [camera]
- OM-5 II 1.1 menu path (om-emu): Shooting Menu 2 > 1. Computational Modes > Live ND Shooting (greyed in P, enabled in S/M) > page with Live ND Shooting Off/On, ND Number, LV Simulation; ND Number lists ND2-ND16 and wraps (stand-in lens). 2026-11-05 [code]
- Card I/O rule: only a silent single shot (drive 30) may read the request or write logs. A burst writes nothing. 2026-11-05 [code]
- LV preview needs job 12 **and** its setter (0x9d window words). [code]

## Paths we tried and dropped (don't repeat)

- An earlier port based on the E-M1 III's Live ND was replaced by the OM-5 version, because the OM-5's buffer layout fits
  the E-M5 III's memory (about 1 GB; the E-M1 III's needs about 2 GB). [inferred]
- Capping the burst frame rate to get longer frames was the wrong model: the OM-5 never caps the frame rate, it asks
  the sensor for longer frames (kind 0x400, fps 0). [camera]
## On the E-M5 II and E-M5 (Mark I) (2026-11-21)

- **E-M5 II 4.1:** no Live ND code. Its image engine runs the same 320-bit program format (stub and memcpy job byte-identical to the E-M5 III's), so the OM-5 jobs 11/12 *might* load, but the job setters, frame pools, sensor modes and capture path are different code on a different chip (21% of register constants shared). A port would be a new project with the PEN-F as the code reference, starting with one OM-5 job run on an E-M5 II. [code] for the facts, [inferred] for the verdict.
- **E-M5 (Mark I) 2.3:** no programs of this format anywhere in the firmware, so there is no engine to run the merge; very likely impossible. [code]+[inferred]

Full comparison: [older bodies](../bodies/comparison-technical.md#older-bodies-e-m5-ii-and-e-m5-mark-i-2026-11-21).
