# Live ND (internal: DIGITAL_ND / DigitalNd / iseq_nd)

Live ND is a "digital ND filter": instead of one long exposure through a dark filter, the camera takes several shorter
exposures and averages them into one photo. Moving water or clouds blur as if you had used an ND filter, without the
filter. The OM-5 has it; the E-M5 III, which has the same chip and sensor, doesn't. Bringing it over is this project's
main goal.

**Where it stands (2026-11-13):**

- **Works on the camera:** a full Live ND shot from one press, run by our port of the OM-5's own Live ND shooting
  states: N frames at the set shutter speed, merged by the OM-5's image-engine job 11 into one photo, ND2, ND4, ND8 and
  ND16, at 1/8 s and at 1/125 s, several presses in a row with no restart in between (since 2026-11-12).
- **Live-view preview works too:** with LV Simulation on, the live view shows the Live ND blur as you'd get it in the
  photo, averaged over up to 240 frames by the OM-5's job 12, as on the OM-5 (since 2026-11-12). Handing the
  borrowed frame memory back before each photo works; a fix for one bug found there is waiting for a camera run.
- **Not built yet:** the dark-frame pass (keep Noise Reduction off with Live ND for now), and a menu: Live ND is still
  switched on by a request file on the card and the preview by a console setting.
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
| Hand-back | borrowed frames go back before a photo; menu and playback don't pass that point | [camera] photos fine; one bug, fix built, not run |

**Still to do:** checking the hand-back fix on the camera, the dark-frame pass, and switching the preview from the menu
setting instead of the console.

## How it compares with caduceus's Live ND (E-P7)

- External comparison 2026-11-11: caduceus-ep7 (E-P7, public) "early alpha Live ND" is stock Multiple Exposure with Auto
  Gain forced (1/N average), ND3/ND4 only, AP mode only, one frame per press; their one-press attempts (continuous drive,
  burst limit, custom self-timer) hung or crashed and are parked. Ours does ND2-ND16 in one press with job-11 merge, but
  isn't user-ready (card-file trigger, capture end then still open). Same blocker on both sides: ending a multi-frame capture
  cleanly. [code] (their repo, read-only)
- Since 2026-11-12 our side of that blocker is solved: the ported OM-5 states end the capture cleanly (see
  "How it was solved" above). [camera]

## Limits and open items

- Main pool = 20 slots: 16 held + 2 stream at ND16. **ND32 has no native code to port** on OM-5/OM-5 II; plan is a
  two-pass merge (or running accumulator), as OM-1 does natively. [code]+[inferred]
- Single-drive trigger cuts the stream after 1 frame (cause unfound); trigger stays silent H burst until the menu stage. [camera]
- OM-5 II 1.1 menu path (om-emu): Shooting Menu 2 > 1. Computational Modes > Live ND Shooting (greyed in P, enabled in S/M) > page with Live ND Shooting Off/On, ND Number, LV Simulation; ND Number lists ND2-ND16 and wraps (stand-in lens). 2026-11-05 [code]
- Card I/O rule: only a silent single shot (drive 30) may read the request or write logs. A burst writes nothing. 2026-11-05 [code]
- LV preview needs job 12 **and** its setter (0x9d window words). [code]

## Paths we tried and dropped (don't repeat)

- An earlier port based on the E-M1 III's Live ND was replaced by the OM-5 version, because the OM-5's buffer layout fits
  the E-M5 III's memory (about 1 GB; the E-M1 III's needs about 2 GB). [inferred]
- Capping the burst frame rate to get longer frames was the wrong model: the OM-5 never caps the frame rate, it asks
  the sensor for longer frames (kind 0x400, fps 0). [camera]