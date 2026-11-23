# Shooting sequencer

> **Technical notes.** This page is the dense reference. For a readable introduction, start with [Taking a photo](../guides/taking-a-photo.md).

When you press the shutter, a "shooting sequencer" in the main program steps through a series of states: standby,
preparing, taking the exposure, developing, saving. This page describes that state machine, how it decides which path a
shot takes, how the high-speed burst path streams frames, where the exposure settings for a shot are kept, and how it
asks the sensor to change mode.

It is the part of the firmware Live ND hooks into, so most of what is known here came from that work.

Terms used here:

- **State table**: the list of sequencer states, each with a handler function and the events it reacts to.
- **Route**: a number (0-4) picked for each shot that decides which states it goes through.
- **StlUhs**: the firmware's name for the still "ultra-high-speed" burst state, which we use to capture Live ND frames.
- **Tv / Sv / Av**: shutter time, sensitivity and aperture in APEX units.

Tags: **[code]** read in the firmware, **[camera]** seen on a real E-M5 III, **[inferred]** not traced or tested.

## The state table

- The stock table is at **0x6044f9e4**: 34 entries of 20 bytes `{id, name, fn, evA, evB}`, states 0-33 (31-33 are
  PhotoInMovie). [code]
- The dispatcher loads it at 0x602a0f9f / 0x602a139c; the range check is at **0x602a1347** (`cmp N`); a state change is
  stored at 0x602a13b4 (d2 old, d0 new). [code]
- **Adding states works** (state test 1): copy the table to 0x600d0200 with extra entries, repoint the loads and raise
  the range check. [camera]
- Our Live ND builds have 38 entries at 0x600d0200: 34 = StlTakeCave (a copy of StlTake 0x602b34c6),
  35-37 = DigitalNd / DigitalNdDarkRdy / DigitalNdEnd; range check `cmp 37`; the chooser default is `mov 34` at
  0x602b3464, so **every single shot passes through state 34**. HHHR plans state 38. Ask before moving anything in
  0x600d0200-0x600d0800. [code]
- Native states that matter: 15 StlUhs, 25 HsContTake, 29 HsContEnd (0x602b5058), tripod High Res 25-30. On the OM-5,
  state 34 is PixShiftSrHandHeldEnd and the Live ND states 31-33 are DigitalNd (0x602b9265) / DarkRdy / End (table
  0x60468e74). [code]

## State names and the single-shot path (2026-11-19)

Names come from the state table's name strings (`st_<Name>_entry`). [code]

| id | state | id | state | id | state |
|---|---|---|---|---|---|
| 0 | Idle | 12 | StlRdy1 | 24 | ContEnd |
| 1 | RdyStart | 13 | StlRdy2 | 25 | HsContTake |
| 2 | RdyFcsRdy1 | 14 | StlTake | 26 | HsContWait |
| 3 | RdyFcsRdy2 | 15 | StlUhs | 27 | HsContRdy |
| 4 | RdyFcsRdy3 | 16 | StlLiveTake | 28 | HsContEndPre |
| 5 | RdyTrig2Wait | 17 | LvCompTake | 29 | HsContEnd |
| 6 | RdyFastTrig2Wait | 18 | LvCompEnd | 30 | PixShiftSrEnd |
| 7 | RdyFcsTake | 19 | StlEnd1 | 31 | PhotoInMovie |
| 8 | RdyFcsAbort | 20 | StlEnd2 | 32 | PhotoInMovieContWait |
| 9 | RdyAbort | 21 | ContAf | 33 | PhotoInMovieEnd |
| 10 | RdyEnd | 22 | ContAfStop | | |
| 11 | Standby | 23 | ContWait | | |

- Every state change goes through **`seq_set_next_state` 0x602a1341** (d0 = state, d1 = argument; out of range is
  logged), which stores 0x62107746 (next state) and 0x62107748 (argument); the current state is the u16 at 0x62107744.
  It has 53 call sites, all with a constant state number. [code] (static scan of block0, 2026-11-19)
- Read off those call sites, a single still shot runs: Idle → **1 RdyStart → 2/3/4 RdyFcsRdy1-3** (focus) →
  **5 RdyTrig2Wait** (waiting for the full press) → **7 RdyFcsTake** (RdyTrig2Wait's event 18) → **11 Standby** →
  **12 StlRdy1 → 13 StlRdy2** → chooser → **14 StlTake** → **19 StlEnd1 → 20 StlEnd2** → back to **5** if the byte
  0x62110be8 is 0, otherwise **9 RdyAbort → 10 RdyEnd**, which goes to 1 or 0. [code] Reading event 18 as the full press
  and 0x62110be8 as "half-press released" is [inferred].
- Other exits seen: RdyFcsRdy1 event 7 → 8 RdyFcsAbort; RdyFcsRdy2 → 4, or 6 RdyFastTrig2Wait (which goes to 7 on its
  event 18); RdyTrig2Wait event 2 → 9 RdyAbort; Standby events 7/9 → 9 / 5; StlUhs → 29 HsContEnd (0x602b5058);
  StlLiveTake → 19; PhotoInMovieEnd → 5 or 0. [code]
- **Sequential (non-high-speed) shooting loops through the Cont states:** StlTake (0x602b44ad) goes to **21 ContAf** when
  the byte 0x62110cec is non-zero, else to 19 StlEnd1; then ContAf → 22 ContAfStop → 23 ContWait → **13 StlRdy2** →
  chooser → StlTake again; ContAf/ContWait leave through 24 ContEnd → 19. [code] (2026-11-19) That 0x62110cec means
  "more frames to take" and ContAf is the focus step between frames are [inferred]. High-speed sequential (route 3)
  loops HsContTake 25 → 26 HsContWait → 27 HsContRdy → 25, ending 28 → 29 → 19 (or 30 PixShiftSrEnd). [code]
- **S-AF and C-AF are not separate states**: both half-press paths run RdyFcsRdy1-3 then wait in RdyTrig2Wait. Where
  the AF mode changes behaviour (presumably inside the focus task FCS) is not traced. [code] for the states, the rest
  [open]

## How a still shot picks its path

The **chooser 0x602b3441** sends route 4 to state 15 **StlUhs**, route 3 to 25 HsContTake, and everything else to 14 StlTake (34 StlTakeCave in
our Live ND builds, which patch the `mov 14` at 0x602b3464)
(only when 0x62110344 == 0). [code]
When 0x62110344 is non-zero the chooser ignores the route: it picks **17 LvCompTake** if 0x62110345 == 2, otherwise
**16 StlLiveTake**, so 0x62110344 marks the live-view long-exposure modes (Live Bulb/Time/Composite). [code] (meaning
[inferred]; 2026-11-19, disassembly of 0x602b3441-0x602b3483)

- The route byte is 0x6211020e, loaded on entering Standby (0x602b2263) from byte 10 of the shot message (on the OM-5,
  byte 11 = continue_mode). [code]
- Routes seen per drive mode: silent single 0, silent sequential L 1, silent/mechanical sequential H 3, Pro Capture L 1,
  Pro Capture H 3. No drive mode gives route 2 or 4 natively on the E-M5 III. Forcing 4 at Standby works. [camera]
- Route 4 (StlUhs) is a **burst path** at a fixed **60 fps** whatever the shutter speed, so frames are clamped to about
  1/60 s. The burst rate is the UHS rate picked from {60,30,20,15} (0x601dca90) by 0x602bb29a, only when the UHS type
  ctx+1990 (0x6211033a) == 2, and stored at 0x62110488. [camera]+[code]
- The OM-5 enters DigitalNd only with continue_mode 4 and the Live ND flag ctx+2196 (Standby byte 15). Its DigitalNd
  sends its own type-7 sensor request: kind 0x400, +20 = 1, fps 0. The E-M5 kind function 0x602ba4d5 lacks 0x400, but the
  E-M5 sensor side already handles kind 0x400 / fps 0 identically. [code]

## How the StlUhs burst streams frames

- Its template is at 0x602b4876: +0 supplier 0x602b4978, +4 completion 0x602b49cb, +8 per-component 0x602b4a54. [code]
- The completion runs in **interrupt context**. It posts ev63 (a0 = entry), then ev85 (the record) for frames 2 and
  later; frame 1 goes via message 0x62110588 (type 24). [camera]+[code]
- What the events do: ev63 0x602b4f16 re-queues an entry per frame (refill) and then prepares it (EXIF 0x602c0f6a);
  ev65 0x602b5062 releases a row (0x602b1348) and notifies 0x602b4e68; ev85 0x602b50e4 sends to the development queue
  (0x602c2295); ev80 frees development objects. The event table pairs start at 0x6044e8a4 (ev63 slot word 0x6044e8a8,
  ev85 0x6044e8e8). [code]

The row manager is the tricky part: [camera]

- The stream allocator keeps 1 row in reserve, and rows must come back **every frame** or the stream stalls at 4.
  `0x6210f448` is the allocated count; the refill request is 0x602ae9ce(0). [camera]
- Notifying "row done" for frames that haven't been developed reboots the camera.

Other details: the stop flag is f59a (request) / f59c (acknowledge); cleanup 0x602b4bc4 drains the queue; the limit per
burst is 600 frames (0x602b2807). [code] Single-drive streams end after 1 frame, and nothing in the Standby or shot
struct tells single from H burst; that is decided somewhere we haven't found. [camera]

## The exposure record

- Each shot has one exposure record, R = *(*(0x6210fb6c)+60), filled at StlRdy1 0x602b29b9 by 0x602c0cb0: +6 Tv
  (property 41002), +8 Sv (41034), +10 Av (41018). Tv = APEX × 256. [code]
- The E-M5 has the OM-5's Live ND plumbing **compiled in but switched off**: take-param +119/+120 = 0 at 0x604492ed;
  stubs 0x602292fd/0x60229301 return their input, 0x60229305 returns 0; AE ids 299-302 have records at 0x60547f54. [code]

## Source modules along the capture path (2026-11-19)

The firmware keeps many of its source-file names (see [OS and framework](os-and-framework.md#source-file-and-module-names)).
Along a still shot they line up in layers: [code] (module spans are inferred
from strings, so edges are approximate;)

- **Capture components (C++, Rhapsody):** `CapTak_Take.cpp` (~0x608c3914; `takePicture` 0x608c4e66 and its variants
  for continuous, auto, dark frame, Live Bulb, WB sample), `CapThr_ThroughImage.cpp` (live view), `CapBuf_TakeBuff.cpp`
  and `CapBuf_BufferManager.cpp` (shot buffers), `CapRec_Record.cpp`, `CapAef_AEAFLock.cpp`. [code]
- **Sequencer (C):** the state handlers above and `takepic.c` / `takepic_imgpro.c` (~0x602b7xxx-0x602bfxxx). [code]
- **Recording (C):** `rec_precon.c` (metadata step 0x6040c7f5, OB and WB filled), `rec_imgpro*.c`, `rec_mem.c`,
  `rec_media.c` (0x60403xxx-0x6040dxxx). [code]
- **Files and card:** `dcf*.c` (DCIM folder and file numbering, 0x6060e7f0-0x6061df9a), `sd_mount.c`, `sdmem.c`,
  `sdphy.c` (0x606481a4-0x6064f685). [code]
- How `CapTak_Take::takePicture` hands over to the sequencer, and how a developed image travels from `rec_imgpro` to the
  file writer, is not traced yet. [open]

## Sensor requests

The type-7 sender is 0x601fce30. It has 11 callers in section 1, so hooks there need a boot guard. Live view is mode 9
MSPD at 120 fps, half-press is mode 0 HSSC at 60, and the shutter is mode 14 STILL with fps 0 and the set Tv
(0x602b321b, 0x602b0adc burst; 0x602b9d20 single). [camera] See also [sensor](../hardware/sensor.md).
.

## Component-level sequence state (CmpSqp/CmpShc)
Separate from the state table above, the shooting-sequence components keep their own state id [code] (2026-11-18, from the decompile):
- `getSeqStateId` 0x607c4d23 reads g_61e99a1c; `setSeqStateId` 0x607c5934 writes it and logs `SEQ=%d`. [code]
- [code] Ids (from the `entry<STATE>` methods that set them): 1 STANDBY, 3 READY, 4 READY_FINISH, 5 READY_TRIG2,
  7 TAKE_PICTURE, 8 TAKE_PICTURE_CONT, 9 TAKE_PICTURE_AUTO, 10 TAKE_PICTURE_END_WAIT, 0xb SECOND_WAIT, 0xc END_WAIT,
  0xf MOV_READY, 0x10 MOV_READY_FINISH, 0x11 MOV_RECORDING, 0x12 MOV_SELFTIMER_WAIT, 0x13 MOV_END. Ids 6 and 0x14 are
  still unnamed (their entry methods sort between entrySECOND_WAIT and entrySTANDBY; one is probably SELFTIMER_WAIT).
- `execErrorHandlerByStateId` 0x609a2da5 maps each id to a per-state vtable slot (0x13a0..0x1438); the per-event error
  handlers in CmpSqp_SequencePartsBase (APPEVENT_* lens trouble, USB, Wi-Fi, power ...) are laid out one per state in
  the same slot order, which is how they get their `errorHandler<Event>In_<STATE>` names. [code]
