# Live ND port: layers and join points

Live ND is a newer-body feature that blends many short exposures into one, like a neutral-density filter; see
[Live ND](../features/live-nd.md) for the feature and its results. This page is the engineering log for one specific
problem in that port: the places where code we brought over from the OM-5 meets the E-M5 III's own code, and what is
known at each of those seams. It is the page to read when a Live ND build resets and you want to know which call to
suspect.

Terms used here:

- **Port / donor**: we take code from the OM-5 (the donor) and run it on the E-M5 III.
- **Join point**: a place where ported code calls a native E-M5 III function, or native code enters ported code.
- **State 35-37**: the sequencer states we added for Live ND (see [shooting sequencer](shooting-sequencer.md)).
- **F1-F5**: findings from an audit of the ported end-of-capture states, numbered in the order found.

Tags: **[code]** read in the firmware, **[camera]** seen on a real E-M5 III, **[inferred]** not traced or tested.

## The three layers

The port is easiest to think about as three layers stacked on each other:

1. **Native E-M5 III code, unchanged.** State-machine framework, capture engine (frame queue, end-of-sequence path),
   frame pools, develop pipeline, camera task. We only hook into it. The OM-5 has the same design with Live ND awareness
   built in (flag ctx+2196 tested in 22 places); the E-M5 has the plumbing compiled in but switched off. [code]
2. **Ported Live ND state logic.** OM-5 DigitalNd states 31/32/33 are our states 35/36/37. First exported from the
   E-M1 III in October, then audited instruction by instruction against the OM-5 1.2 (the OM-5 runs the E-M1 III
   software branch on E-M5 III-class hardware, see `bodies/comparison.md`). [code]

3. **Our glue.** Arming by request file, the chooser change into state 35, logs, and dry stand-ins for the OM-5's
   iseq ND engine (no merge in the first version).

The seams that matter are between layers 2 and 1: every call the ported code makes into a native helper. The two sides
come from different software branches, so a native helper that does the same job can take different arguments.
Rule: `firmware/patching-techniques.md` rule 13.

## Join points: ported code calling native helpers (status 2026-11-06)

Each row is a call from ported code into a native helper, and whether the arguments match what the native helper
expects. "Wrong" rows were real bugs.

| port site | native target (OM-5 original) | status |
|---|---|---|
| 0x607a133d state-37 output builder | 0x602b97bf (0x602c520b) | **wrong (F1)**: native wants d1 = boolean, stack = record pointer with out+4 = ((rec+60))+6; port passes d1 = halfword, stack = 0 -> null dereference, likely the early resets. Fix: d1 = 0, stack = saved record (0x607b6000), which gives the donor's out+4 exactly (the donor's halfword is ((rec+60))+6 read at state-31 entry, 0x602b92a4..0x602b92c7; ours 0x607a0842..). private notes |
| 0x607a1989 completion callback event | posts 81 (native 0x602b8806 posts 83) | **wrong (F5)**: port table renumbered donor 81 -> 83. 1-byte fix |
| 0x607a1435 request 1537, reply event | reply 79 (donor 79 = port 81; native E-M5 sends 1537 with reply 81 at 0x602b75fe, 0x602b8784) | **wrong**: port state-37 table has no 79/80, reply dropped; should be 81 |
| 0x607a1896 request 1281, reply event | reply 80 (donor 80 = port 82) | **wrong**: should be 82 |
| 0x607a17fa command 80 to queue (0x60040fe0) | donor 80 to (0x60041896); E-M5's own post there uses 53 (0x602b28e5) | open: does the E-M5 task read 80 the same way |
| 0x607a0bd8 finish descriptor | 0x602ba0a9 (0x602c5ca6) | **differs (F3)**: native sets mask 0x500 when ctx+2000 clear; donor skips 0x400 when ND active. Effect of 0x400 unknown |
| 0x607a13ea buffer swap | 0x602b1e26 (0x602bd249) | **differs (F2)**: native doesn't exchange row flag bit 0. After F1 on the path |
| state-37 ev82 0x607a18d5 / 0x607a18dc | 0x602a9cd0 / 0x602a5ef9 (0x602b316f / 0x602b31be) | **not equivalent (F4)**; 0x602a9cd0 looks like the counterpart of 0x602b31be. Late |
| ev56, ev66, finish 0x607a0bcc, ev46, job_free, trampolines 0x607a6c38.. | | match OM-5 instruction for instruction |

F-numbers are from the end-states audit (private notes #5, `results/ENDSTATES-AUDIT.md`, reviewed in
`results/REVIEW.md`). All [code], 2026-11-06.

## Join points: native code entering ported code
Listed in private notes and `STEPS.md`: the chooser hook into state 35,
the 8 prep hooks (W1-W8), the state/event pointer words 0x600d04c4.., the supplier template 0x607a0ad7 (supplier
0x607a0c83), and the dry iseq stand-ins (begin/add/finish). Capture end, native: per-frame completion 0x602b0ceb ->
supplier null -> 0x602b1041 end flag -> events 56/66 -> finish (see `features/live-nd.md`, 2026-11-06). [code]

## State-37 waits (round-3 audit, 2026-11-06) [code]
Exit: low mask 0x9000 (ev47, ev87) -> state 19, which gates on high 61/81/82/83. Synchronous timeout -1 waits inside native calls: 0x602bc2c1 (kind 7), 0x602bacb3 (command 38), queue sends 0x60227ce5.

## Open questions
- What the 0x400 descriptor command (F3) does on the E-M5. [code]

## Join points found on the camera (2026-11-12)

Tracing runs live over the Wi-Fi debug shell found the places where the ported OM-5 states and the E-M5 III's own
functions disagree. With all of them handled, a full Live ND shot runs and ends cleanly. [camera]/[code]

| seam | OM-5 | E-M5 III | what the port does |
|---|---|---|---|
| Capture start | 0x602bbb77 writes no status words; the builder 0x602b9405 puts N into the request's frame counts | 0x602b0a5a writes -1 through three request pointers (+40, +24 then +8, +44): the N-frame sequence becomes endless, and a zero +44 is a write to address 0 (NMI) | own copy of the start without the writes; +44 points at a real word (native value ctx+964, from the StlUhs builder 0x602b4cea) |
| Run-dry job | the supplier (0x602b9faf) hands out a frame-id-0 job when three or fewer frames remain; the event-63 handler skips the capture call 0x602c82e1 for it (0x602b995e) | 0x602bc619 with id 0 reaches a NULL descriptor (NMI) | keeps the OM-5's id-0 check |
| Stop handshake | stop message on entry to the End state, then waits for events 47 and 87 | native burst states send stop message 0x602b98de from their event-33 handler (reply event 47); stop#req (0x6210f59a) stops in-flight frames from finishing | completes the handshake; stop#req is not used as the end |
| Display release | one "resume live view" handler releases when the Live ND flag (0x620d0dbc) is set | display handler 0x6044605d waits with no timeout for flag 4 on (0x60040e96), set only via the sequencer's event-83 handler (0x602b882f); native StlEnd handler 0x602b8305 releases only when continue_mode is 0 | the Live ND end state handles events 81, 82 and 83 |
| Output frame | the job with +6 = 1 is a reserved buffer the sensor never fills; all N frames go through add (event 63, then 80) | same | merges the held frames into that buffer at finish |
| Button release | | an event with no handler in the state makes the dispatcher 0x602a0f90 print a history dump (0x60227bb0); in a fast series this stalls the frame refill and frames are lost | exec 17 and event 39 get the native no-op handler 0x602a14bb in the Live ND states |

Lesson: when ported code calls an E-M5 III function, compare that function with the OM-5 function it replaces, not
just the arguments.
