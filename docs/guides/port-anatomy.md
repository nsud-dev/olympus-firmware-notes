# Anatomy of a feature port

*Guide 9 · E-M5 III firmware 1.7 · accepted 2026-11-20. New to these guides? Read
[Before you start](before-you-start.md) first; this guide leans on most of the others. Open questions:
research gaps.*

This guide follows one feature port from start to finish: Live ND, taken from the OM-5 and running on the E-M5 III.
It is about the order of the work and the decisions at each step: which body to take the feature from, what to read
before building anything, how to get a first result, how ported code meets native code, and how to see what went
wrong when a test build fails on the camera.

It is not a list of techniques. Each technique it uses (hooks, boot guards, arming, extra shooting states, menu rows)
has its own section on [modifying the firmware](../firmware/patching-techniques.md), with its method and pitfalls; this
guide links to them by number.

Live ND took about a month on and off, from mid-October to mid-November 2026, and dozens of test builds. Most of what went
wrong falls into a few patterns, and those are what this guide is for.

## The shape of it

```
choose the donor ──► read the donor ──► list what the target already has
                                                  │
                         first result with the target's own code (frames + merge)
                                                  │
                           port the donor's own logic (states, requests)
                                                  │
                    find and fix the join points, one camera run at a time
                                                  │
                         finish: preview, menus, settings, tuning
```

## 1. Choose the donor

Several newer bodies have Live ND: the OM-5, the OM-5 II, the E-M1 III and the OM-1. They share the processor and most
of the software design, so any of them could in principle be the donor. What decides it is whether the donor's
design **fits the target's hardware**.

The first attempt took the E-M1 III's version. It was replaced, because the E-M1 III lays out its image buffers for
about 2 GB of memory and the E-M5 III has about 1 GB. The OM-5 has the same 1 GB layout as the E-M5 III, so its
version of the feature can borrow memory the way it does at home. The OM-1 is newer still, but its design also assumes
2 GB, and its image-engine programs are of a different generation.

The rule: before porting code, compare the two bodies' memory maps, image-engine generation and sensor requests. A
donor whose feature fits in its own memory map will fit in yours only if the maps agree.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| memory class per body | [memory map: how much memory each camera has](../hardware/memory-map.md#how-much-memory-each-camera-has) | [code]; RAM size [inferred] |
| donor choice | OM-5 1.2 for Live ND and handheld high res (2026-10-22) | decision |
| image-engine generation | same from PEN-F to OM-5 II; OM-1 differs ([image engine](../hardware/image-engine.md)) | [code] |

Sources: [Frame pools and memory](frame-pools-and-memory.md), [Live ND: paths we tried and dropped](../features/live-nd-technical.md#paths-we-tried-and-dropped-dont-repeat).
</details>

## 2. Read the donor first

Before building anything, find out how the donor really does it. For Live ND on the OM-5 that meant:

- **The settings:** three properties (on/off, ND number, live-view simulation) and their menu rows.
- **The shooting states:** three states of their own (capture, dark frame, end), entered when a flag is set.
- **The sensor request:** the capture asks the sensor for frames as long as the set shutter time, with no frame-rate
  limit.
- **The merge:** an image-engine program (job 11) averages N frames into one output frame; another (job 12) keeps a
  running average for the live-view preview.
- **The memory:** which pools hold the frames, and how many.

Every time we skipped this step it cost us. One example: getting frames longer than 1/60 s. We first tried capping the
burst frame rate, which made the camera slow and frames still clamped at about 1/60 s. Reading the OM-5 showed it
never caps the frame rate at all: it sends a different sensor request. With that request the frames came out at the
set time on the first try.

The rule we work by now: research the donor until a test can only confirm a design, not find one.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| OM-5 Live ND properties | 7745 on, 7761 ND number, 7777 LV simulation | [code] |
| OM-5 states | 31 DigitalNd, 32 DarkRdy, 33 End | [code] |
| sensor request | kind 0x400, fps 0 | [code]; on the E-M5 III [camera] |
| frame-rate cap attempts | dropped | [camera] |

Sources: [Live ND: how Olympus does it](../features/live-nd-technical.md#how-olympus-does-it-om-5-12-our-donor).
</details>

## 3. List what the target already has

The E-M5 III turned out to contain more of Live ND than expected. Much of the OM-5's plumbing is **compiled in and
switched off**: the flags exist, some helper functions are present as stubs, and the exposure code has the Live ND
cases. What is missing is the three shooting states and the two image-engine programs.

That changes the job. Instead of porting everything, you port the missing pieces and switch on what is there. It also
tells you where the risk is: a native function that exists on both bodies may still behave differently (section 6).

The other half of the inventory is resources: free space for code (section-end slack), free memory for frames, free
ids in the state table and the menus. Each of those had a limit we hit later.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| plumbing present but off | take-param +119/+120 zero, identity stubs, exposure ids 299-302 | [code] |
| OM-5 job 11 runs on the E-M5 III image engine | first merged photo | [camera] |
| free space per feature | [memory map: spare space](../hardware/memory-map.md#spare-space-for-our-code) | [camera] / [code] |

Sources: [Live ND: what the E-M5 III already has](../features/live-nd-technical.md#what-the-e-m5-iii-already-has).
</details>

## 4. Get a first result with the target's own code

The first goal is not the feature. It is the smallest thing that proves the hard part works. For Live ND the hard part
is the merge, so the first builds used the E-M5 III's own burst mode to get frames, kept the frames instead of saving
them, and ran the OM-5's merge program on them from our own code.

| step | what it proved |
|---|---|
| frames from the native burst, held in memory | we can keep frames past their normal life |
| OM-5 job 11 run on two held frames | the E-M5 III's image engine runs the donor's program |
| merged frame saved as the photo | first Live ND-style photo (two frames) |
| eight and then sixteen frames | ND2 to ND16 |
| the OM-5's sensor request | frames at the set shutter time, not 1/60 s |

Each line was one or two camera runs. By the end of this stage the feature worked in a crude form, triggered by a
request file on the card, before any of the donor's own logic had been ported.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| first merged photo | 2026-10-29 | [camera] |
| ND8, ND2-ND16 | 2026-10-30 | [camera] |
| frames at the set time, same brightness as a single shot within 0.03 EV | 2026-11-05 | [camera] |
| how job 11 is driven | [Live ND](../features/live-nd-technical.md#how-our-version-works) | [camera] |

Sources: [Live ND: what we measured on the camera](../features/live-nd-technical.md#what-we-measured-on-the-camera).
</details>

## 5. Arm, don't replace

From the first build, every change does nothing unless the user has asked for the feature. A hook checks "armed?" and
falls straight through to the stock code if not. During development "armed" was a request file on the card plus the
right drive mode and exposure mode; later it became a native menu row.

This is what makes testing safe: a test build behaves as stock firmware for everything else, so a mistake shows up
only when you use the feature, and the card update still works to undo it. It is also how the port avoids breaking
other features, which was a requirement from the start.

The trap is arming too widely. One build gave the new sensor request to every caller while armed, not only the Live ND
burst, and the camera hung on an ordinary shot. The fix was to arm per call site, for the burst's own request builders
only.

Techniques: [3 hook native code](../firmware/patching-techniques.md#3-hook-native-code),
[4 guard hooks during boot](../firmware/patching-techniques.md#4-guard-hooks-during-boot),
[5 act only when armed](../firmware/patching-techniques.md#5-act-only-when-armed).

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| request too wide: hang on a single shot | 2026-11-05 | [camera] |
| armed only for the burst's request builders | three call sites | [camera] |

Sources: [Live ND: how our version works](../features/live-nd-technical.md#how-our-version-works).
</details>

## 6. Port the donor's logic, then find the join points

The crude version merged frames after a native burst. The OM-5 instead runs its own three states that capture exactly
N frames, feed the merge and finish the shot. To behave like the OM-5 on one press, we ported those states: relocated
the OM-5's functions into free space, added them to a copy of the state table, and pointed each call they make at the
matching E-M5 III function.

That is where most of the time went. Ported code calls native code at dozens of places (**join points**), and the two
sides come from different software branches. At five of them the E-M5 III function did something the OM-5 function
does not:

| join point | what went wrong | fix |
|---|---|---|
| capture start | the E-M5 III's start function marks the sequence endless and writes through a pointer the OM-5 leaves at 0, so capture never ended, or the camera reset | our own copy of the start without those writes |
| last frames | the OM-5 hands out a placeholder job near the end and skips it; the port passed it on and the sensor got a null address | keep the donor's check |
| display at the end | the display waits, with no timeout, for an event the Live ND end state didn't handle | handle the three events |
| output frame | the OM-5 merges into a separate frame the sensor never fills; without the merge the photo is an unwritten buffer | merge into it at the end |
| button release | an event with no handler makes the dispatcher print a long dump, which stalls frames at fast shutter speeds | do-nothing handlers for those events |

The lesson: **when ported code calls a target function, compare that function with the donor function it replaces,
not just the arguments.** Matching arguments into a function that behaves differently still breaks.

Techniques: [9 add shooting states](../firmware/patching-techniques.md#9-add-shooting-states),
[10 port code from a newer body](../firmware/patching-techniques.md#10-port-code-from-a-newer-body).

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| ported states | E-M5 III states 35-37 = OM-5 31-33 | [camera] |
| every join point, with addresses | [Live ND port layers](../firmware/live-nd-port-layers.md) | [code] / [camera] |
| first complete run (capture, end, back to live view) | 2026-11-12 | [camera] |
| merged ND2-ND16 through the ported states | 2026-11-12 | [camera] |

Sources: [Live ND: porting the OM-5's own states](../features/live-nd-technical.md#porting-the-om-5s-own-live-nd-states).
</details>

## 7. See what happened

A failed test build gives you almost nothing to go on. The camera hangs (and stays hung until the battery comes out),
or it resets about a second later and memory is lost. Guessing from that took a week of builds. Three things replaced
the guessing:

- **A log on the card.** Our builds keep a small log in memory and write it to the card at a safe moment (never from an
  interrupt or mid-burst). That gives the state of the last run, but not of a run that reset.
- **The stock Wi-Fi debug shell.** It traces the camera's own events live as you press the shutter. With it, each
  failed run pointed at one join point, and the five in section 6 were found in one day.
- **An emulator.** Menus, boot and settings can be tried in om-emu before the camera. It doesn't model everything
  (it ran a build that boot-looped the camera), so it narrows the search but doesn't replace the camera.

Two working rules came out of this. A hang and a reset are different problems: a hang is a wait that never ends, a
reset is a fault. And after every camera run, write down what worked, what failed and the likely cause before
designing the next build.

Techniques: [11 watch a test run live](../firmware/patching-techniques.md#11-watch-a-test-run-live),
[14 prototype in an emulator first](../firmware/patching-techniques.md#14-prototype-in-an-emulator-first).

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| no RAM log survives the self-reset | yes | [camera] |
| Wi-Fi shell trace | `take dbgmode 1`; [Wi-Fi debug shell](../features/wifi-debug-shell.md) | [camera] |
| known hang and reset causes | [gotchas](../reference/gotchas.md) | [camera] |

Sources: [Live ND port layers: join points found on the camera](../firmware/live-nd-port-layers.md#join-points-found-on-the-camera-2026-11-12).
</details>

## 8. Memory: borrow, don't add

The OM-5 has extra frame pools for Live ND that the E-M5 III lacks, and the pool table can't simply grow. So the port
borrows frames from the main still pool through the pool's own functions, and gives them back before the photo is
saved. The live-view preview does the same with a window of up to 240 frames.

The main still pool is in two blocks, and one early build computed slot addresses from a stride: frame eight landed in
memory that wasn't image memory. Since then, every address comes from the pool.

See [Frame pools and memory](frame-pools-and-memory.md) for how pools work.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| two-block address bug, fixed | 2026-10-30 | [camera] |
| preview window, 240 frames in borrowed main frames | 2026-11-12 | [camera] |

Sources: [Frame pools and memory](frame-pools-and-memory.md#6-the-main-still-pool).
</details>

## 9. Finish it

With the shot working, the rest is making it a feature:

- **The preview.** The OM-5's job 12 keeps a running average of live-view frames so you see the blur before you shoot
  ([Live view](live-view.md)). It needed the job, its setter, a frame window and restarts when the scene changes
  (shutter dial, camera movement).
- **Menus and settings.** Native rows where the OM-5 has them, values kept across power-off
  ([Settings and menus](settings-and-menus.md)).
- **Tuning.** Values such as the movement thresholds stay adjustable on a hidden settings page while they are tuned.
- **What's still open.** The dark-frame pass for noise reduction, and a restart at power-on in the test builds.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| live preview | 2026-11-12; restart on dial 2026-11-17 | [camera] |
| menu rows and saved values | 2026-11-19 | [camera] |
| dark-frame pass | built, not proven | open |

Sources: [Live ND](../features/live-nd.md).
</details>

## How every build is made

These rules came from the camera, each one after a failure:

- Every address our code uses is checked against the stock code before a build is handed over.
- Every hook into another section is guarded until that section is ready.
- Nothing changes unless armed.
- No card writes, locks or waits in an interrupt.
- Each build has a name, a checksum and a procedure with the base, the bytes changed, the test and how to recover. It
  passes the pre-flash checks before it reaches the camera.

The full list is on [modifying the firmware: rules for every build](../firmware/patching-techniques.md#rules-for-every-build).

## Checked on other cameras

Where the Live ND pieces exist in each body. Nothing is assumed: "not checked" means we don't know.

| piece | E-M5 III 1.7 | OM-5 1.2 | E-M1 III 1.6 | OM-5 II 1.1 | OM-1 1.9 | PEN-F 3.1 | other projects |
|---|---|---|---|---|---|---|---|
| Live ND shooting states | **ported** (ours) | yes (donor) | **confirmed** (our first port came from them) | not checked | not checked | not checked | — |
| merge engine and levels | ported, ND2-ND16 | ND2-ND16 | **different**: 32-frame table | **confirmed** ND2-ND16 | **different**: native ND64/ND128 | not checked | OM-5 II (Caduceus OM-5 port): ND32/ND64 reported after two edits |
| image buffer layout for ~1 GB | yes | **confirmed** | **different**: ~2 GB | **confirmed** | **different**: ~2 GB | not checked | — |
| image-engine jobs reusable as-is | job 11 and 12 run (ours) | yes | **confirmed** (same generation) | **confirmed** | **different**: other generation | **confirmed** (same generation) | — |
| plumbing compiled in, switched off | yes | has Live ND | has Live ND | has Live ND | has Live ND | not checked | — |

Sources: [Live ND](../features/live-nd.md), [image engine](../hardware/image-engine.md),
[memory map](../hardware/memory-map.md), Atlas-linked projects.
