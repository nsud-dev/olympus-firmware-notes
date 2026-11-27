# Shooting sequencer: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Taking a photo](../guides/taking-a-photo.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

When you press the shutter, a "shooting sequencer" in the main program steps through a series of states. They are
standby, preparing, taking the exposure, developing and saving. This page describes that state machine and how it
decides which path a shot takes. It also covers how the high-speed burst path streams frames, where the exposure
settings for a shot are kept, and how the sequencer asks the sensor to change mode.

It is the part of the firmware Live ND hooks into, so most of what is known here came from that work.

Terms used here:

- **State table**: the list of sequencer states, each with a handler function and the events it reacts to.
- **Route**: a number (0 to 4) picked for each shot that decides which states it goes through.
- **StlUhs**: the firmware's name for the still "ultra-high-speed" burst state, which we use to capture Live ND frames.
- **Tv / Sv / Av**: shutter time, sensitivity and aperture in APEX units.

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred.

## The state table

The stock table has 34 entries of 20 bytes, `{id, name, fn, evA, evB}`, for states 0 to 33. States 31 to 33 are
PhotoInMovie.[^fw1]

- The dispatcher loads the table at two sites. The range check is a `cmp N`. A state change is stored with d2 = old and
    d0 = new.[^fw1]
- **Adding states works.** Copy the table to a free area with extra entries, repoint the loads and raise the range
    check. This worked on our E-M5 III in a state test.[^cam1]
- Our Live ND builds have 38 entries in that copy.[^fw1]
    - 34 = StlTakeCave, a copy of StlTake.
    - 35 to 37 = DigitalNd, DigitalNdDarkRdy and DigitalNdEnd.
    - The range check is `cmp 37`.
    - The chooser default is `mov 34`, so **every single shot passes through state 34**.
- HHHR plans state 38.
- Native states that matter are 15 StlUhs, 25 HsContTake, 29 HsContEnd and the tripod High Res states 25 to 30.[^fw1]
- On the OM-5, state 34 is PixShiftSrHandHeldEnd. Its Live ND states 31 to 33 are DigitalNd, DarkRdy and End, in its own
    table.[^fw1]

## State names and the single-shot path

Names come from the state table's name strings (`st_<Name>_entry` in our symbol table).[^fw2]

| id | state | id | state | id | state |
|---:|---|---:|---|---:|---|
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

*The 34 stock states of the E-M5 III, from the state table's name strings.*

Every state change goes through **`seq_set_next_state`**, with d0 = state and d1 = argument. An out-of-range state is
logged. The function stores the next state and the argument, beside the u16 that holds the current state. It has 53
call sites, all with a constant state number.[^fw2]

### The single shot

Read off those call sites, a single still shot runs these states.[^fw2]

1. Idle, then **1 RdyStart**.
2. **2, 3 and 4 RdyFcsRdy1 to 3** (focus).
3. **5 RdyTrig2Wait**, waiting for the full press.
4. **7 RdyFcsTake**, on RdyTrig2Wait's queue event 11 (the take request) or event 18.
5. **11 Standby**.
6. **12 StlRdy1**, then **13 StlRdy2**.
7. The chooser, then **14 StlTake**.
8. **19 StlEnd1**, then **20 StlEnd2**.
9. Back to **5** if a status byte is 0. Otherwise **9 RdyAbort**, then **10 RdyEnd**, which goes to 1 or 0.

Who sends event 18 is open. Reading the status byte in step 9 as "half-press released" is inferred.[^inf1]

Other exits are seen too.[^fw2]

- RdyFcsRdy1 event 7 goes to 8 RdyFcsAbort.
- RdyFcsRdy2 goes to 4, or to 6 RdyFastTrig2Wait, which goes to 7 on its event 18.
- RdyTrig2Wait event 2 goes to 9 RdyAbort.
- Standby events 7 and 9 go to 9 and 5.
- StlUhs goes to 29 HsContEnd.
- StlLiveTake goes to 19.
- PhotoInMovieEnd goes to 5 or 0.

### Where the take request enters

Event numbers in these tables are word +8 of the 16-byte message on queue `0x60`. They are matched against the state's
queue-event list (state record +12).[^fw3]

- The C++ take request (`api_rec`, message type 11) is **queue event 11**.[^fw3]
- RdyTrig2Wait and RdyFastTrig2Wait send it to 7 RdyFcsTake. Their handler keeps the request in RAM.[^fw3]
- Standby sends it to 12 StlRdy1 and stores the **request pointer**.[^fw3]
- Event 18 also leads to 7 but comes from another sender. So event 11 is the take-picture path, and event 18 is not
    the plain full press.[^fw3]

See also: [C++ shooting layer](cpp-shooting-layer-technical.md#the-request-inside-the-sequencer).

### Sequential shooting

**Sequential (non-high-speed) shooting loops through the Cont states.**[^fw2]

1. StlTake goes to **21 ContAf** when a "more frames" byte is non-zero, else to 19 StlEnd1.
2. ContAf goes to 22 ContAfStop, then 23 ContWait, then **13 StlRdy2**.
3. The chooser, then StlTake again.

ContAf and ContWait leave through 24 ContEnd to 19.[^fw2] That the byte means "more frames to take" and that ContAf is
the focus step between frames are inferred.[^inf1]

High-speed sequential (route 3) loops HsContTake 25, 26 HsContWait, 27 HsContRdy and back to 25. It ends 28, 29, 19
(or 30 PixShiftSrEnd).[^fw2]

**S-AF and C-AF are not separate states.** Both half-press paths run RdyFcsRdy1 to 3, then wait in RdyTrig2Wait.[^fw2]
Where the AF mode changes behaviour, presumably inside the focus task FCS, is not traced.

## How a still shot picks its path

The **chooser** picks the take state from the route and from a live-view long-exposure flag.[^fw2]

| condition | next state |
|---|---|
| flag is 0, route 4 | 15 **StlUhs** |
| flag is 0, route 3 | 25 HsContTake |
| flag is 0, any other route | 14 StlTake (34 StlTakeCave in our Live ND builds, which patch the `mov 14`) |
| flag non-zero, second byte = 2 | 17 **LvCompTake** |
| flag non-zero, otherwise | 16 **StlLiveTake** |

*What the chooser does, from the disassembly of the chooser.*

When the flag is non-zero the chooser ignores the route. So the flag marks the live-view long-exposure modes (Live Bulb,
Time and Composite).[^inf1]

- The route byte is loaded on entering Standby, from byte 10 of the shot message. On the OM-5, byte 11 is
    continue_mode.[^fw1]
- Routes seen per drive mode on our E-M5 III: silent single 0, silent sequential L 1, silent or mechanical sequential
    H 3, Pro Capture L 1 and Pro Capture H 3. No drive mode gives route 2 or 4 natively on the E-M5 III. Forcing 4 at
    Standby works.[^cam2]
- Route 4 (StlUhs) is a **burst path** at a fixed **60 fps** whatever the shutter speed, so frames are clamped to
    about 1/60 s.[^cam2]
- The burst rate is the UHS rate, picked from {60, 30, 20, 15}. It is picked only when the UHS type (ctx+1990) is 2,
    and it is stored in RAM.[^cam2][^fw1]
- The OM-5 enters DigitalNd only with continue_mode 4 and the Live ND flag ctx+2196 (Standby byte 15).[^fw1]
- The OM-5's DigitalNd sends its own type-7 sensor request, kind `0x400`, +20 = 1, fps 0. The E-M5 kind function lacks
    `0x400`. But the E-M5 sensor side already handles kind `0x400` and fps 0 identically.[^fw1]

## How the StlUhs burst streams frames

Its template has a supplier at +0, a completion at +4 and a per-component function at +8.[^fw1]

The completion runs in **interrupt context**. It posts ev63 (a0 = entry), then ev85 (the record) for frames 2 and
later. Frame 1 goes via a message of type 24.[^cam2][^fw1]

| event | what it does |
|---|---|
| ev63 | re-queues an entry per frame (refill), then prepares it (EXIF) |
| ev65 | releases a row and notifies |
| ev85 | sends to the development queue |
| ev80 | frees development objects |

*Burst events. Handler and table addresses are in the [address reference](#address-reference).[^fw1]*

The row manager is the tricky part.[^cam2]

- The stream allocator keeps 1 row in reserve. Rows must come back **every frame**, or the stream stalls at 4.
- One RAM word holds the allocated count. The refill request is a call with argument 0.

> [!WARNING]
> Notifying "row done" for frames that haven't been developed reboots the camera.

Other details follow.

- The stop flag is f59a (request) and f59c (acknowledge). A cleanup function drains the queue.[^fw1]
- The limit per burst is 600 frames.[^fw1]
- Single-drive streams end after 1 frame. Nothing in the Standby or shot struct tells single from H burst. That is
    decided somewhere we haven't found.[^cam2]

## The exposure record

Each shot has one exposure record, R = `*(*(request pointer)+60)`. The request pointer holds the `api_rec` take
request.[^fw3] R is filled at StlRdy1.[^fw1]

| offset | value | property |
|---|---|---:|
| +6 | Tv | 41002 |
| +8 | Sv | 41034 |
| +10 | Av | 41018 |

*The exposure record. Tv = APEX × 256.[^fw1]*

The E-M5 has the OM-5's Live ND plumbing **compiled in but switched off**.[^fw1]

- Take-param +119 and +120 are set to 0.
- Two stubs return their input, and a third returns 0.
- AE ids 299 to 302 have records.

## Source modules along the capture path

The firmware keeps many of its source-file names (see
[OS and framework](os-and-framework.md#source-file-and-module-names)). Along a still shot they line up in layers.[^fw2]
Module spans are inferred from strings, so edges are approximate.[^inf1]

- **Capture components (C++, Rhapsody):** `CapTak_Take.cpp`, with `takePicture` and its variants for continuous, auto,
    dark frame, Live Bulb and WB sample. Also `CapThr_ThroughImage.cpp` (live view), `CapBuf_TakeBuff.cpp` and
    `CapBuf_BufferManager.cpp` (shot buffers), `CapRec_Record.cpp` and `CapAef_AEAFLock.cpp`.[^fw2]
- **Sequencer (C):** the state handlers above, and `takepic.c` and `takepic_imgpro.c`.[^fw2]
- **Recording (C):** `rec_precon.c` (a metadata step that fills OB and WB), `rec_imgpro*.c`, `rec_mem.c` and
    `rec_media.c`.[^fw2]
- **Files and card:** `dcf*.c` (DCIM folder and file numbering), `sd_mount.c`, `sdmem.c` and `sdphy.c`.[^fw2]

`CapTak_Take::takePicture` hands over to the sequencer through `api_rec.c` (API `0x20013`). It writes message type 11
to queue `0x60`, which the sequencer task drains on event-flag bit 1.[^fw3] See also:
[C++ shooting layer](cpp-shooting-layer-technical.md#how-a-take-picture-reaches-the-c-sequencer).

How a developed image travels from `rec_imgpro` to the file writer is on [still image back end](still-backend-technical.md).

## Sensor requests

The type-7 sender has 11 callers in section 1, so hooks there need a boot guard.[^cam2]

| use | sensor mode | fps |
|---|---|---:|
| live view | 9 MSPD | 120 |
| half-press | 0 HSSC | 60 |
| shutter | 14 STILL, with the set Tv | 0 |

*Sensor modes the sequencer asks for. Call sites for burst and single are in the [address reference](#address-reference).[^cam2]*

See also: [Sensor](../hardware/sensor.md).

## Component-level sequence state (CmpSqp/CmpShc)

Separate from the state table above, the shooting-sequence components keep their own state id.[^fw4]
`getSeqStateId` reads it. `setSeqStateId` writes it and logs `SEQ=%d`.[^fw4]

| id | state | id | state |
|---:|---|---:|---|
| 1 | STANDBY | `0xb` | SECOND_WAIT |
| 3 | READY | `0xc` | END_WAIT |
| 4 | READY_FINISH | `0xf` | MOV_READY |
| 5 | READY_TRIG2 | `0x10` | MOV_READY_FINISH |
| 7 | TAKE_PICTURE | `0x11` | MOV_RECORDING |
| 8 | TAKE_PICTURE_CONT | `0x12` | MOV_SELFTIMER_WAIT |
| 9 | TAKE_PICTURE_AUTO | `0x13` | MOV_END |
| 10 | TAKE_PICTURE_END_WAIT | | |

*Component-level state ids, from the `entry<STATE>` methods that set them.[^fw4]*

Ids 6 and `0x14` are still unnamed. Their entry methods sort between entrySECOND_WAIT and entrySTANDBY. One is probably
SELFTIMER_WAIT.[^inf3]

`execErrorHandlerByStateId` maps each id to a per-state vtable slot (`0x13a0` to `0x1438`). The per-event error handlers
in CmpSqp_SequencePartsBase (APPEVENT_* lens trouble, USB, Wi-Fi, power and so on) are laid out one per state in the
same slot order. That is how they get their `errorHandler<Event>In_<STATE>` names.[^fw4]

## Open questions

- Who sends queue event 18.
- What decides that a single-drive stream ends after 1 frame.
- Where the AF mode changes behaviour, presumably inside the focus task FCS.
- The names of component-level state ids 6 and `0x14`.

## Address reference

E-M5 III 1.7 block0 addresses unless a body is named.

| item | address |
|---|---|
| stock state table | `0x6044f9e4` |
| table loads, range check, state store | `0x602a0f9f` / `0x602a139c`, `0x602a1347`, `0x602a13b4` |
| our table copy (38 entries) | `0x600d0200` |
| StlTake, copied as StlTakeCave | `0x602b34c6` |
| chooser, its default `mov` | `0x602b3441` (code `0x602b3441` to `0x602b3483`), `0x602b3464` |
| HsContEnd | `0x602b5058` |
| OM-5 DigitalNd, OM-5 state table | `0x602b9265`, `0x60468e74` (OM-5) |
| `seq_set_next_state` | `0x602a1341` |
| current state (u16), next state, argument | `0x62107744`, `0x62107746`, `0x62107748` |
| "back to 5" status byte | `0x62110be8` |
| "more frames" byte | `0x62110cec` |
| StlTake exit to ContAf | `0x602b44ad` |
| live-view long-exposure flag, second byte | `0x62110344`, `0x62110345` |
| RdyTrig2Wait take handler, request kept at | `0x602c49ec`, `0x62111bac` |
| Standby take handler | `0x602b255f` |
| request pointer | `0x6210fb6c` |

*States, the chooser and the take request.*

| item | address |
|---|---|
| route byte, loaded at | `0x6211020e`, `0x602b2263` |
| UHS rates {60, 30, 20, 15}, picker | `0x601dca90`, `0x602bb29a` |
| UHS type (ctx+1990), burst rate store | `0x6211033a`, `0x62110488` |
| E-M5 kind function | `0x602ba4d5` |
| StlUhs template | `0x602b4876` |
| supplier, completion, per-component | `0x602b4978`, `0x602b49cb`, `0x602b4a54` |
| frame 1 message (type 24) | `0x62110588` |
| ev63 handler, EXIF prepare | `0x602b4f16`, `0x602c0f6a` |
| ev65 handler, row release, notify | `0x602b5062`, `0x602b1348`, `0x602b4e68` |
| ev85 handler, development queue send | `0x602b50e4`, `0x602c2295` |
| event table pairs, ev63 slot, ev85 slot | from `0x6044e8a4`, `0x6044e8a8`, `0x6044e8e8` |
| allocated row count, refill request | `0x6210f448`, `0x602ae9ce` |
| cleanup, per-burst limit | `0x602b4bc4`, `0x602b2807` |

*Routes and the burst path.*

| item | address |
|---|---|
| exposure record fill at StlRdy1 | `0x602b29b9`, by `0x602c0cb0` |
| take-param +119/+120 cleared | `0x604492ed` |
| Live ND stubs (input, input, 0) | `0x602292fd`, `0x60229301`, `0x60229305` |
| AE ids 299–302 records | `0x60547f54` |
| `CapTak_Take.cpp`, `takePicture` | about `0x608c3914`, `0x608c4e66` |
| `takepic.c`, `takepic_imgpro.c` | about `0x602b7xxx` to `0x602bfxxx` |
| `rec_precon.c` metadata step | `0x6040c7f5` |
| recording modules | `0x60403xxx` to `0x6040dxxx` |
| `dcf*.c` | `0x6060e7f0` to `0x6061df9a` |
| `sd_mount.c`, `sdmem.c`, `sdphy.c` | `0x606481a4` to `0x6064f685` |
| `api_rec.c` take picture | `0x60302f93` |
| queue `0x60` id (u16) | `0x60040fd8` |
| sequencer task | `0x602a0f90` |
| type-7 sensor request sender | `0x601fce30` |
| sensor request sites | `0x602b321b`, `0x602b0adc` (burst), `0x602b9d20` (single) |
| `getSeqStateId`, state id variable | `0x607c4d23`, `0x61e99a1c` |
| `setSeqStateId` | `0x607c5934` |
| `execErrorHandlerByStateId` | `0x609a2da5` |

*Exposure record, modules, sensor requests and the component-level state.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware.
[^fw2]: Read in the firmware, 2026-11-19, from a static scan of block0.
[^fw3]: Read in the firmware, 2026-11-25.
[^fw4]: Read in the firmware, 2026-11-18, from our decompile's naming notes.
[^cam1]: Seen on our E-M5 III, in a test build that added sequencer states.
[^cam2]: Seen on our E-M5 III during the Live ND work.
[^inf1]: Inferred, 2026-11-19.
[^inf3]: Inferred, 2026-11-18.

## History

- 2026-11-25: how `CapTak_Take::takePicture` hands over to the sequencer was an open question. It is answered above
  (`api_rec.c`, message type 11, queue `0x60`).

