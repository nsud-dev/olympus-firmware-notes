# Motion search unit (EMS1): technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Motion search unit](motion-unit.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

EMS1 is a small fixed-function unit in the camera's system-on-chip that matches blocks of a picture between two
live-view frames. Tracking autofocus depends on it, and so do several other clients. This page covers its driver and
job queue, its registers and presets, its clients, its result format, how the tracker reads the results frame by frame,
and what that means for tracking.

Addresses are from the OM-5 II 1.1 firmware unless a body is named. Names come from the tracker's profiling table (see
[autofocus technical notes](../features/autofocus-technical.md#names)).

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred or seen in an emulator.

## Summary

- **Block matching.** EMS1 is a fixed-function block-matching unit at `0x9b500000`. It compares blocks of a small
  picture between two frames. For each block it returns a motion vector, a match cost and flags.[^fw1] "Match cost" is
  our reading of the field.[^inf1]
- **Shared.** One driver queue serves several clients. They are the live-view evaluation task (flicker, scene
  detection, tracking and its sub job), the tracker core, subject detection, the motion-AF helper and two more clients
  in the image pipeline and AF code.[^fw1]
- **One job at a time.** Jobs run one at a time from a FIFO. Each job carries a complete register image.[^fw1]
- **Channels.** The unit has five channels and two block-compare passes (interrupts `BC1`, `BC11`–`BC14`, `BC2`,
  `BC21`–`BC24`), plus three `TR` interrupts.[^fw1]
- **Small grid for tracking.** Tracking reads at most a 3 × 3 block grid in each of three areas per frame.[^fw1]
- **Separate from the image engine.** The image engine (`0x9d000000`) runs the subject-detection network. The two do not
  compete for the same hardware.[^fw1]
- **Same address in other bodies.** The same base address is in the stock E-M5 III 1.7, E-M1X 2.4 and OM-5 II block0.
  The literal `0x9b500000` appears 4, 6 and 4 times.[^fw4]

## Driver

The driver has the usual open, close, control and start calls. Open and close write registers `0x880` to `0x8ac`. The
control call writes the job's register image through per-channel setters and area setters. Start writes register
`0x14`.[^fw1]

Clients use a public interface on top.[^fw1]

- `ems1_drv_if_init` clears the queue state.
- `ems1_drv_if_iocontrol` is the public entry for clients.
- `ems1_drv_if_iocontrol_sub` enqueues the job and starts the unit if it is idle.
- `ems1_drv_if_call_back` and `ems1_drv_if_call_back_cpun` handle completion and start the next job.
- `ems1_drv_if_enq` and `ems1_drv_if_deq` run the FIFO.
- Six result readers, with small wrappers, decode the result memory.

See also: the [address reference](#address-reference) for each function.

### Job request

- **Request.** A client passes one request struct of at least 1148 bytes. `ems1_drv_if_iocontrol_sub` copies 287 words
  of it to the stack and starts the unit.[^fw1]
- **Control word.** At +1096. Bits 0 to 4 are kept as the interrupt set. Bit 1 and bit 16 add enables built from
  registers `0x44` and `0x50`. Bits 1 to 3 select a mode.[^fw1][^inf1]
- **Other fields.** +1112 and +1116 are a callback pair. +1128 is the queue link. +1140 is the start flag.[^fw1][^inf1]
- **Other cores.** The request stores the caller's CPU number (the byte at `0x8050`). A job from another core is passed
  over with the cross-core call and finished there by `_call_back_cpun`.[^fw1]
- **Scheduling.** There is a single FIFO and no priority. When the unit is idle, the job is dequeued and `open`,
  `iocontrol` and `start` run at once. Otherwise it waits.[^fw1]

The offsets are read in the code. The meanings of the fields are inferred.

### Registers

Offsets from `0x9b500000`.[^fw1]

| range | use |
|---|---|
| `0x00` | control (bits 0 and 1 cleared before each job) |
| `0x04` | interrupt enable, built per job |
| `0x10`, `0x18`, `0x1c`, `0x20`–`0x30`, `0x40`–`0x4c` | common setup. `0x18` is bit-packed from preset bytes |
| `0x14` | start |
| `0x5c`–`0x6c`, `0x80`–`0x11c`, `0x800`–`0x84c`, `0x120`–`0x174`, `0x340`–`0x3c8`, `0x400`–`0x5c4` | five channels. Each setter writes one column, step 4 or `0x10` |
| `0x160`–`0x334`, `0x3cc`, `0x3d0`, `0x4ac` | area and window registers |
| `0x880`–`0x8ac` | open and close, likely a clock or bus enable[^inf1] |

*EMS1 register map, from the driver's setters.*

The interrupt names are `EMS1_DRV_INT_BC1`, `BC11` to `BC14`, `BC2`, `BC21` to `BC24` and `TR1` to `TR3`.[^fw1] They
read as two block-compare passes with four sub-channels each, and three transfer or tracking ends.[^inf1]

### Presets

Each client's register image starts from a preset.[^fw1]

- Parameter id `0x1994` (u32) holds 7 records of 26 words.
- The keys are 0, 2, `0x4002`, `0xa`, `0x400a`, `0xb` and `0x400b`, looked up by `get_ems_param_ems1top_address`.
- `get_ems_param_proems1_address` serves the `proems1` set.
- `set_param_ems1_drv_reg` and `set_param_ems1_drv_area_reg` copy them into the request.

## Clients

| client | job |
|---|---|
| live-view evaluation task `take_mov` | jobs `flc` (flicker), `iauto` (scene), `laf` and `laf_sub` (tracking), `param`. Strings also list `fnr` and `dl` presets |
| tracker core (`mdet_calc_flame_vector.c`) | frame vector, likely camera motion[^inf1] |
| subject detection (MDET DL) | DL-side search, see `laf_dl_calc_ems1_register_value` |
| tracker helper under image processing | unnamed |
| motion AF (`mdet_mvaf`) | vectors for C-AF, callback `mdet_mvaf_ems1_callback` |
| image pipeline, under the live-view job builder | unnamed, possibly electronic stabilisation[^inf1] |
| AF-side state machine | three jobs, unnamed |

*EMS1 clients. Where each submits its job is in the [address reference](#address-reference).[^fw1]*

The tracking jobs are queued from the live-view frame queue (`frame_packets`, `frame_queue`).[^fw1] So tracking gets at
most one EMS1 job per live-view frame.[^inf1]

## Results

The result readers decode the result memory. Per block the stride is 64 bytes.[^fw1]

| field | bits | meaning |
|---|---|---|
| word 0, bits 0–6 | 7-bit signed | horizontal motion (-64..63), likely in pixels of the search picture[^inf1] |
| word 0, bits 7–13 | 7-bit signed | vertical motion |
| word 0, bits 14–31 | 18 bits | match cost, likely a sum of differences[^inf1] |
| word +64 | bits 0, 3–11 flags, bits 20–23 a 4-bit value | per-block status. The 4-bit value is used as trust |
| words +68, +72 | 17-bit signed each | per-area x and y, likely a summed or sub-pixel vector[^inf1] |
| word +76 | bits 0, 8, 16, 24 | four flags |

*EMS1 result fields per block.[^fw1]*

The block index is row × ceil(width / 16) + column for modes 0 to 4. So whole-frame clients see a grid of 16-pixel
columns. A 24-byte summary record holds two halves of {9-bit value, flag, two bytes, 9-bit value, 4-bit value, two
16-bit values}.[^fw1]

### Tracker use of the results

- **Reading.** `read_data` reads three result sets per frame. Each is a grid of up to 3 × 3 blocks. It stores 8-byte
  vector records (72 bytes per set), 11-byte flag records (99 per set) and 24-byte summaries.[^fw1]
- **Trust.** `judge_mdet_block_trust` stores per frame whether the summary's 4-bit value (byte +8) is non-zero. The
  sets are chosen by two bytes, 0 and 1. Non-zero means *not usable*.[^fix1] `calc_trvec_a` zeroes the set's vector
  when that value is non-zero, unless a flag byte is 1.[^fw1]
- **Vectors.** `calc_quantity_movement` then calls `calc_trvec_a` and `calc_trvec_b` to turn the blocks into tracking
  vectors.[^fw1]
- **Set-up.** `mdet_laf_ems1_start` sets the block width to (n+1) × 8 and the search ranges to 4n + 8 from the job
  configuration. It keeps area positions in 21.11 fixed point. `set_track_area_a` steps the search window from two
  tables.[^fw1]
- **Search picture.** The search picture is a resized copy of the live-view Bayer data (`get_bayer_resize_datasize`,
  `get_rsz`).[^fw1]

## Result path, frame by frame

This section follows one tracking job from start to the tracker's own memory.[^fw2]

One tracking job moves through six places in order.

1. The AF frame handler.
2. The EMS1 driver queue.
3. The EMS1 unit.
4. The per-frame image-pool buffers.
5. The tracker on CPU 2.
6. The tracker's fixed arrays.

The table below says who starts each step.

| from | to | what moves | path | started by | how often |
|---|---|---|---|---|---|
| AF frame handler | EMS1 driver queue | tracking job (1148-byte request block) | `ems1_drv_if_iocontrol` | the frame handler | once per live-view frame[^inf1] |
| EMS1 driver queue | EMS1 unit | the job's register image | driver `open`, `iocontrol`, `start` | the queue, when the unit is idle | per job |
| EMS1 unit | image-pool buffers | block results and summaries | two buffers per area | the unit | per job |
| image-pool buffers | tracker on CPU 2 | {summary, block} buffer addresses per area | completion message, `mdet_callrequest_cpun` | the completion callback | per job |
| tracker on CPU 2 | tracker fixed arrays | copied results | `read_data` | the tracker task | per job |

*Steps of a tracking job.[^fw2]*

### Who starts the tracking job

The live-view evaluation task keeps a client mask. Its start handler maps the bits.[^fw2]

- `0x01` scene detection (`iauto`).
- `0x02`, `0x04` and `0x08` tracking (`mdet_laf_start`).
- `0x10` motion AF (`mdet_mvaf_start`).
- `0x40` a client that sets a flag, read by the tracking frame handler as a DL flag.

The stop handler and the mask update use the same bits. Bit `0x20` has no case there.[^fw2]

### Per frame

The AF-side frame handler runs once per live-view frame packet. When the tracking record (+`0x2f4` of its context)
exists, it chains three calls that submit the tracking EMS1 job. The request block is 1148 bytes. Its control word is
(area mask & 7) × 2.[^fw2] "Once per frame" is inferred from the frame-packet path.[^inf1]

### Where the results land

The results go to two kinds of memory.[^fw2]

- **Per-frame buffers.** Per-block and per-area results go to image-pool buffers allocated per frame, two buffers per
  area. Their ids sit in the tracking record at +`0x30` (block results) and +`0x36` (summaries), one u16 per area. The
  buffer manager turns an id into an address. The buffers are released after the tracker has read them, by reference
  count. So they are not at a fixed address.
- **Fixed result slots.** Small fixed result slots sit at a pointer + `0x40` × n. The AF-side jobs use +`0x40` and
  +`0x80`, +`0x240` and +`0x280`, and +`0x2c0` and +`0x300`. The tracking job uses +`0xc0` to +`0x1c0` (request
  +`0x2e0` and +`0x2e4` per area, area stride `0x8c`).

### Hand-off to the tracker

On completion, the driver callback builds a message.[^fw2]

- Byte 0 is 1 (EMS1 only) or 3 (EMS1 and EMS2).
- Three pairs {summary address, block address} follow, one per area. A pair is zero when its area is off.
- Frame information comes last.

`mdet_laf_chase_object` passes the message to CPU 2 (`mdet_callrequest_cpun`). There `mdet_laf_chase_object_task` →
`mdet_laf_exec_ems1` → `mdet_laf_ems1_chase_object` → `read_data` copy the results into the tracker's fixed arrays
(see [Tracker use of the results](#tracker-use-of-the-results)).[^fw2]

### What the tracker keeps each frame

These are at fixed addresses, so they are safe to read from added code.[^fw2]

| address | type | meaning |
|---|---|---|
| `0xa27366ee` + 24 × area | 24-byte summary | per area. Bytes +3 and +4 = signed area motion x and y in search-window steps. Byte +8 = 4-bit error (0 = usable) |
| `0xa2736738` + 72 × area | 8-byte block records × 9 | s8 dx, s8 dy, pad, u32 match cost (18 bits) |
| `0xa2736998`, `0xa273699c` | s16 | area A motion this frame (x, y) = summary byte × step (`0xa2736aac`, `0xa2736ab0`) − `0xa2736a20` or `0xa2736a24`. 0 when unusable |
| `0xa273699a`, `0xa273699e` | s16 | the same for area B |
| `0xa27369ae`, `0xa27369d6` | s16 × 10 rings | per-frame x and y of area A. Index `0xa27369a4`, length from tuning (`0xa2736ab7`) |
| `0xa27366e6`, `0xa27366ea` | s16 | area A window position for the next frame (search-picture pixels) = old + motion |
| `0xa2736997` | u8 | ring index, advances once per tracking frame |
| `0xa273429a`, `0xa273429c` | u16 | tracker position in the 640 × 480 frame, after fusion with colour, depth, faces and DL |

*Tracker variables updated each frame.[^fw2]*

The values subtracted in the area motion (`0xa2736a20`, `0xa2736a24`) are set by `set_track_area_a`. They are likely
the window's own shift.[^inf1] The unit of the search window is the resized Bayer picture. `mdet_laf_ems1_start` sets
the tracker frame to 640 wide and 340, 360 or 480 high by live-view mode (`0xa2736ab5`).[^fw2]

### Motion AF field

Motion AF (mvaf) gives a 4 × 4 motion field.[^fw2]

- When mask bit `0x10` is on, `mdet_mvaf_notice_frame_data` runs per frame. It keeps a ring of three frames and submits
  a job from its own request block.
- A reader decodes up to 4 × 4 areas (rows `0x621476a0`, columns `0x621476a1`) using the per-area words +68 and +72.
- `mdet_mvaf_get_vector_value` converts them to the 640 × 480 frame. x = ((v >> 8) × step − offset) × 640 / picture
  width, and y the same with the frame height (480, 360 or 339).

So the area words are fixed point with 8 fraction bits.[^inf1]

| address | type | meaning |
|---|---|---|
| `0x621478ac`, `0x621478cc` | s16 [4][4] | x and y motion per area, 640 × 480 units |
| `0x621478ec` | u8 [16] | flags = bit 0 of the area status \| bit 3 × 2 |
| `0x62146cb8` or `0x62146d0a` | `0x51`-byte block | published copy: x [16] at +0, y [16] at +`0x20`, flags [16] at +`0x40`. `0x62146d5c` selects the buffer (0 → `0x62146cb8`) |
| `0x6214769c` | u8 | 1 after a result was published |
| `0x62146d60` | u32 | mvaf state (low nibble 1 idle, 2 or 3 job pending, 4 stop) |
| `0x62146d9d` | s8 | frame ring index 0–2, advances once per finished job |

*Motion AF output.[^fw2]*

The grid is placed around the focus side's AF point. A focus-side call stores the AF point through
`mdet_mvaf_fcs_coordinates_change`, and `mdet_calc_coordinates` turns it into the area rectangle. The focus side reads
the field through `mdet_mvaf_get_ems_info` when a flag byte is 1.[^fw2] "Around the AF point" is inferred from the
geometry.[^inf1]

### Camera log

A first card log on our E-M5 III using test firmware read the client mask and the tracker variables.[^cam1]

- **Idle live view and S-AF.** The `take_mov` mask is 0, so neither the tracker nor motion AF runs.[^cam1]
- **C-AF.** Mask `0x0004`, tracker state 2, AF point kinds 11 and 12.[^cam1] Our subject-detection test code was
  running. The tracker's DL mode went to 1 at the same moment, so that code's hook may start it.[^inf2]
- **C-AF+TR.** Mask `0x0002`, tracker state 1, kind 4.[^cam1]
- **Motion AF.** Mask bit `0x10` never appeared, and the mvaf state stayed 0.[^cam1]
- **Ring index.** The ring index stayed 0. The code wraps it at `0xa2736810`, so the ring length is most likely 1.[^inf2]
  It is not a frame counter.
- **Summary bias.** Summary bytes +3 and +4 carry a -32 bias. A still scene reads (-32, -32), so motion = value + 32,
  in window units.[^cam1]
- **Area vectors.** Area vector A equals the summary bytes when byte +8 = 0, and is 0 when byte +8 = `0xf`. Area 0 was
  valid in 30 to 38% of samples, area 1 almost never and area 2 about 20%. The window moved by the vector when one was
  valid.[^cam1]
- **Update rate.** The tracker updates its window and position at 10 per second or more. The 100 ms samples changed in
  55 to 64% of intervals.[^cam1]
- **AF point.** The AF point block +16 and +20 equals the tracker position in many samples, so they use the same
  coordinates.[^cam1]

Which modes run which client is not readable from the code. The mask comes from the AF side. A card log is needed, and the first one is summarised above (design in subject tracking plan "Motion between
network passes").

### Moving object detection

The OM-1 has an "EMS1 reliability pause".[^fw3]

- It consumes a moving-object list of 8 objects (`0x110` bytes), made from a separate whole-frame EMS1 job with shake
  removed (message id607).
- It pauses when AF asks for tracking but the tracker engine is stopped.
- It restarts at the saved start point when the AF mode turns on.
- It can move the tracking area onto a moving object.
- It stops no EMS1 job.

The OM-5 II has moving object detection (MOD) too.[^fix2]

- The AF frame handler submits the whole-frame job whenever `take_mov` bits `0x02` to `0x08` are set.[^fw3] So it runs
  in C-AF and C-AF+TR, going by the camera log's masks.[^inf2]
- A CPU 2 message (`0x30020004`) leads to code that removes shake, labels moving blocks and writes up to 10 boxes into
  tracker RAM.[^fw3]
- The moving-shield and moving-correction functions read the boxes.[^fw3]
- Only the OM-1's pause consumer is missing.[^fw3] The OM-5 II's moving object detection has not been seen on the
  camera yet.

| field | address | type |
|---|---|---|
| left | `0xa2735d70` | s16 [10] |
| top | `0xa2735d84` | s16 [10] |
| width | `0xa2735d98` | s16 [10] |
| height | `0xa2735dac` | s16 [10] |
| mean motion x, y | `0xa2735dc0`, `0xa2735dd4` | s16 [10], 640 × 480 units |
| blocks | `0xa2735de8` | |
| label | `0xa2735df2` | u8 [10] |
| count | `0xa2735dfc` | |

*OM-5 II moving-object boxes in tracker RAM.[^fw3]*

## Rate and headroom

- Tracking gets at most one job per live-view frame, shared in a FIFO with the other clients. The real rate depends on
  the live-view mode and is not readable from the code. An on-camera log is needed.[^inf1]
- The subject-detection network runs on the image engine, not on EMS1. Camera runs measured 57 to 65 ms per pass. Live
  view stayed at about 47 or 55 fps, and boxes came at about 12 per second.[^cam2] See also:
  [SoC overview technical](soc-overview-technical.md) "E-M1X subject detection".
- So a second network, for example a class-free tracker, would share the image engine with subject detection, not with
  EMS1. Two networks at about 60 ms each would roughly halve each one's rate.[^inf1]

## Tracking limits

- Each tracking area is followed by at most nine blocks. Each block can move up to about 64 pixels of the small picture
  per frame. A subject that is small, fast or changes shape gives few good blocks.[^inf1]
- The unit itself is general. The whole-frame clients use bigger grids. The 3 × 3 limit is in the tracker's data layout,
  not in the hardware.[^fw1] The layout is read in the code. The conclusion is inferred.[^inf1]

## Open questions

- The exact meaning of the `TR1` to `TR3` interrupts and the second summary half.
- The names of the image-pipeline and AF-side clients. The AF-side ones use result slots +`0x40`, +`0x240` and
  +`0x2c0`.
- The measured jobs per second for each client on the camera. A second log with a signature trigger is to measure the
  true rate.
- Which of mask bits `0x01` to `0x40` are on in idle live view, S-AF, C-AF and C-AF+TR. The first camera log covers
  these four modes.

## Address reference

OM-5 II 1.1 block0 addresses unless a body is named.

| function | address | role |
|---|---|---|
| `ems1_drv_open`, `_close` | `0x60174767`, `0x6017483b` | registers `0x880`–`0x8ac` |
| `ems1_drv_iocontrol` | `0x60174919` | writes the job's register image |
| channel setters | `0x60174a93` (ch0 + common), `0x60174eff`, `0x6017512b`, `0x6017535a`, `0x60175589` | per-channel registers |
| area setters | `0x601758e9`, `0x60175aa2`, `0x60175b77`, `0x60175cf7`, `0x60175dfd`, `0x60175eae` | registers `0x160`–`0x334`, `0x3cc`, `0x3d0`, `0x4ac` |
| `ems1_drv_start` | `0x60175ee1` | register `0x14` |
| `ems1_drv_if_init` | `0x6017660e` | clears queue state `0x620b6134`–`0x620b613c` |
| `ems1_drv_if_iocontrol` | `0x601766d1` | public entry |
| `ems1_drv_if_iocontrol_sub` | `0x601767cd` | enqueue, start if idle |
| `ems1_drv_if_call_back`, `_cpun` | `0x60176906`, `0x60176c21` | completion, next job |
| `ems1_drv_if_enq`, `_deq` | `0x60176dc8`, `0x60176ed2` | FIFO |
| result readers | `0x601761c2`, `0x6017622c`, `0x601762a2`, `0x601762ae`, `0x6017633a`, `0x601763d1` | wrappers `0x601772b8`–`0x601772ee` |
| summary record reader | `0x601762ae` | 24-byte summary |
| cross-core call | `0x60056380` | |
| interrupt name strings | `0x607a7301`–`0x607a73d5` | |

*EMS1 driver.*

| item | address |
|---|---|
| preset records | `0x600844f8` (stock E-M5 III `0x6007e028`) |
| `get_ems_param_ems1top_address` | `0x6066c8f2` |
| `get_ems_param_proems1_address` string | `0x607a1939` |
| `set_param_ems1_drv_reg`, `set_param_ems1_drv_area_reg` | `0x6066cd5e`, `0x6066cf76` |
| `take_mov` job submission, dumps | `0x602b50b2`, `0x602b57b9`, dumps `0x602b4b59`–`0x602b6115` |
| tracker core (`mdet_calc_flame_vector.c`) | `0x6062b030`, `0x6062ba44` |
| subject detection (MDET DL) | `0x6063d178` |
| tracker helper under image processing | `0x60642e27` (called from `0x60399e03`) |
| motion AF job, `mdet_mvaf_ems1_callback` | `0x6066b45d`, `0x6066b779` |
| image pipeline client, job builder area | `0x60394f43`, `0x6034xxxx`–`0x6036xxxx` |
| AF-side state machine jobs, loop | `0x6059ce72`, `0x6059d1cc`, `0x6059d571`, loop `0x60596d08`–`0x6059798e` |

*Presets and clients.*

| item | address |
|---|---|
| `read_data` | `0x6065d089` |
| tracker grid columns, rows | `0xa273693b`, `0xa273693c` |
| vector records, flag records, summaries | `0xa2736738`, `0xa2736812`, `0xa27366ee` |
| `judge_mdet_block_trust`, set selector bytes | `0x6065e069`, `0x607ab59c`, `0x607ab59e` |
| `calc_trvec_a` override flag | `0xa2736b8c` |
| `calc_quantity_movement`, `calc_trvec_a`, `calc_trvec_b` | `0x6065da92`, `0x6065dba7`, `0x6065df71` |
| `mdet_laf_ems1_start`, `set_track_area_a`, window tables | `0x6065bf37`, `0x6065e2b7`, `0xa2736a38`, `0xa2736a60` |
| `get_bayer_resize_datasize`, `get_rsz` | `0x60661899`, `0x60661583` |

*Tracker reading of the results.*

| item | address |
|---|---|
| `take_mov` client mask | `0x620caa98` |
| start handler, DL flag | `0x60596a16`, `0x620caba4` |
| stop handler, mask update | `0x602b2792`, `0x602b2af2`, `0x602b2907` |
| AF frame handler, chain | `0x6059a8e9` → `0x6059a8f5`, then `0x602b4d1f` → `0x602b4dd1` → `0x602b50b2` |
| tracking request block, control word, completion | `0x620cdd8c`, `0x620ce1d4`, `0x602b5186` |
| buffer allocation, buffer manager, release | `0x602b500b` → `0x6059dbd2`, `0x6059dbc5` → `0x60412932`, `0x6059daf1` |
| fixed result slot pointer | `0x620ce828` |
| AF-side slot user, tracking slot user | `0x6059d1cc`, `0x6059db4a` |
| completion message | `0x602b2e16` → `0x602b2f55` |
| `mdet_laf_chase_object`, `mdet_laf_chase_object_task` | `0x606303db`, `0x6064a387` |
| `mdet_mvaf_notice_frame_data` call, request block, callback | `0x6059aafc`, `0x62146dd4`, `0x6066b88e` |
| mvaf reader, `mdet_mvaf_get_vector_value` | `0x6066de3e`, `0x6066dc4e` |
| AF point store, `mdet_mvaf_fcs_coordinates_change`, AF point | `0x6078270c`, `0x6066ad74`, `0x62146d70`, `0x62146d72` |
| `mdet_calc_coordinates` | `0x6066db7d` |
| `mdet_mvaf_get_ems_info`, caller, flag | `0x6066aeb5`, `0x60782777`, *(`0xa2766058`)+`0x57` |

*Result path and motion AF.*

| item | address |
|---|---|
| OM-1 1.9: reliability pause | `0x6085aefe`, `0x6085a954` |
| OM-1 1.9: moving-object list | `0xa3376b58` |
| OM-1 1.9: whole-frame job handler | `0x6082d053` |
| whole-frame job submission | `0x6059a9de` |
| MOD message path | `0x6064a462` → `0x606602d1` |
| moving-shield and moving-correction functions | `0x60652c57` to `0x60653d79` |

*Moving object detection.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the OM-5 II 1.1 firmware, 2026-11-25.
[^fw2]: Traced in the OM-5 II 1.1 firmware with Ghidra, 2026-11-25.
[^fw3]: Read in the OM-1 1.9 and OM-5 II 1.1 firmware, 2026-11-26.
[^fw4]: Counted in the E-M5 III 1.7, E-M1X 2.4 and OM-5 II block0, 2026-11-25.
[^inf1]: Inferred, 2026-11-25.
[^inf2]: Inferred from the first camera log, 2026-11-26.
[^cam1]: Seen on our E-M5 III using test firmware, 2026-11-26, first card log of the client mask and the tracker variables.
[^cam2]: Measured on our camera, see the SoC overview's subject-detection section.
[^fix1]: Corrected 2026-11-25. A non-zero 4-bit value means the set is not usable.
[^fix2]: Corrected 2026-11-26. Moving object detection had been thought missing in the OM-5 II firmware.

## History

- 2026-11-25 · The tracker's per-set 4-bit value was first read the other way round. Non-zero means not usable.
- 2026-11-26 · Moving object detection was first thought missing in the OM-5 II firmware. It is there, and only the OM-1's
  pause consumer is missing.

