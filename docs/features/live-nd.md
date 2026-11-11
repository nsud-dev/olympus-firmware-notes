# Live ND (internal: DIGITAL_ND / DigitalNd / iseq_nd)

Live ND is a "digital ND filter": instead of one long exposure through a dark filter, the camera takes several shorter
exposures and averages them into one photo. Moving water or clouds blur as if you had used an ND filter, without the
filter. The OM-5 has it; the E-M5 III, which has the same chip and sensor, doesn't. Bringing it over is this project's
main goal.

**Where it stands (2026-11-07):**

- **Works on the camera:** merged ND2, ND4, ND8 and ND16 photos, made from the camera's own burst frames and merged by
  the OM-5's image-engine job 11. Since build E10g each frame is at the set shutter speed.
- **Not working yet:** ending the capture cleanly. Our port of the OM-5's own Live ND states (the E11 builds) still hangs
  or resets the camera at capture end. The latest bisect build, E11a5d, is waiting for a camera run.
- **Not user-ready:** it is switched on by a request file on the card, not a menu.

How to read this page: the first sections explain how Olympus built Live ND and how our version works. The build log
further down is the detailed record of every E11 build and camera run, kept for whoever picks this up next.

Terms used here:

- **ND2, ND4 ... ND16**: the strength of the effect, 1 to 4 stops. ND8 means 8 frames merged.
- **Job 11 / job 12**: image-engine programs from the OM-5 that merge frames (photo) and accumulate the live-view
  preview. See [image engine](../hardware/image-engine.md).
- **Route 4 / StlUhs**: the burst capture path we use to get frames (see
  [shooting sequencer](../firmware/shooting-sequencer.md)).
- **Armed**: the user has asked for Live ND (a request file on the card plus S or M mode). Unarmed, every hook falls
  through to stock behaviour.
- **E2 ... E11a5d**: our test builds in order; **[camera]** results come from the maintainer flashing them.
- **Tv**: shutter time. **N**: number of frames.

Tags: **[code]** read in the firmware, **[camera]** seen on a real E-M5 III, **[inferred]** not traced or tested.
Earlier status line (2026-11-05): E10f (OM-5 DigitalNd sensor request, so frames follow the set Tv) built and waiting
for a camera run:.

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

## How our version works (E-series builds, on the OM-5 base)

Each row is one piece of the feature and the build that proved it on the camera:

| piece | how | proven |
|---|---|---|
| Trigger | request file `C:\LNDM3.ARM` (1 byte choosing the ND level/mode) + silent H burst; S/M modes only, B excluded | [camera] |
| Frames | force route 4 (StlUhs) at Standby; retain frames in the ev63 handler (task context) | [camera] E2l |
| Merge | job 11 in place into the last held frame, which becomes the saved photo; only the merged photo is developed (rows released + refilled per frame) | [camera] E7a4 |
| Levels | ND2/4/8 via repeated inputs (E8a), ND16 = 16 frames, program in a descriptor slot (E8c) | [camera] |
| Exposure | E10b: OM-5 real↔digital Tv conversions, AE switches, armed gates, boot guards | [camera] (10/10 boots; set Tv = per-frame Tv as on OM-5) |
| Long frames | E10f: kind 0x400 + fps 0 request at sites K 0x602ba50c, R 0x602b4cc7, S 0x602ba117, guards 0x600d0736/0758/0775, code 0x607a9f60 | **[camera] failed 2026-11-05**: the arm single hung the camera (LV slowed, UI gone). Kind 0x400 was given to every caller while armed. Fix: only during the armed route-4 burst private notes |
| Arm fix | E10g: kind 0x400 only when armed AND continue_mode 4 AND caller Standby 0x602b30e5 / StlUhs 0x602b4c5d / sub-6 0x602ba103 (the burst's request builders); all other callers native. 2026-11-05 [code] private notes | **[camera] passed 2026-11-05**: arm single normal, frames 125.0 ms apart at Tv 1/8 (was 16.7 ms), ND8 merge OK. Tripod run: merged ND8 (8 x 1/8 s) has the same brightness as a 1/8 single, within 0.03 EV. Code difference to check: our WBClip = 4095, while the OM-5 computes per-channel clips (0x6067dcb5) [code]. Live view slows to the set Tv once armed (E10b AE switch) [camera] private notes |
| Logs | RAM M block 0xa07b4800, dumped as LND3B7 by the next silent single | [camera] |

## What the camera showed along the way

- Route-4 burst is 60 fps (16.6-16.7 ms) at every set Tv; at Tv 1/60, 1/30, 1/15 the merged photo has the same brightness as a
  1/60 single, so frames clamp to ~1/60. 2026-10-30 [camera] (runs `E2-camera-runs/e8tv_*`)
- E10b: with Live ND armed, AE id 299 engages; the set Tv is the per-frame Tv and the "digital" time (N × Tv) is derived, as on the
  OM-5. HSSC asked 30 fps at 1 s and LV went dark/freezing; burst stayed 60 fps. 2026-11-04 [camera]
- E10p: LV MSPD 120 fps = AE id 323, half-press HSSC = AE 270; Live Composite sends no type-7 request. 2026-11-04 [camera]
- The merged JPEG gets smaller as N rises (3.96/3.23/2.64 MB for ND2/4/8): less noise. [camera]
- Testing a T/N exposure needs no firmware: set Tv = T/N in M. Donor Tv step tables are byte-identical in E-M5 (0x604d32ae/3328/337a). [code]
- Decisions (the maintainer 2026-10-31): silent H hold is the trigger until all functions are in; ND level from the card file until the menu stage. The maintainer 2026-11-04: faithful OM-5 port, "armed" only stands in for prop 7745.

The milestones: E5c first merged photo (2 frames) → E6d first real ND8 → E8a ND2/4/8 → E8c ND16 (16 frames over 250 ms,
job 142.5 ms).

## E11: porting the OM-5's own Live ND states

**The idea.** Up to E10g we merge frames ourselves after a native burst. The OM-5 instead runs three dedicated shooting
states (DigitalNd, DarkRdy, End) that capture exactly N frames, hand each to its merge engine and finish the shot. E11
ports those states into ours (35-37) so one press behaves like the OM-5.

**What happened, in short.** E11a captured but never stopped (battery pull). Forcing a stop (E11a2, E11a3) made the
camera reset itself after 1-2 s. An audit of the ported end states found the likely reason: a call into a native helper
with arguments in the wrong places (F1) and a wrong event number (F5). With those fixed (E11a4) the reset was gone but
capture again never finished. Adding a watchdog timer and breadcrumbs to find where it stops (E11a5, 5b, 5c) brought the
~1 s reset back, and showed that no RAM log survives that reset. E11a5d removes the timer to tell the two suspects apart.
The seams between ported and native code are tracked on [Live ND port layers](../firmware/live-nd-port-layers.md).

### E11 build log

The full record, oldest first. Each entry gives the build or finding, its SHA-256 where built, and the camera result.

- E11 (full DigitalNd port, the maintainer's choice 2026-11-05): the image already holds the October E-M1 port of states 35-37. It matches OM-5 states 31-33 at 0.955/0.911/0.985 instruction-shape, and 34 of its 99 call sites agree with an independent OM-5→E-M5 matcher (16 still to check). DigitalNd supplies its own frames (≤3 queued, the count is independent of the button), passes each to iseq add, and develops jobs whose +6 byte is 1 through 0x602c1f3a. [code]
- E11 design traced, 2026-11-05 evening: the OM-5 reserves an output frame first (job byte +6 = 1), so the first sensor frame lands in it; only that job is paired with develop (0x602c1f3a) and kept, other frames go back to the pool after iseq add, and the finish callback posts event 90 (stats, then the sequence continues). The merge target is therefore the first frame. [code] / target inferred. Other findings: the capture callback table is 17 words on the OM-5 and 16 on the E-M5 (the OM-5 +48 Live ND progress callback lands in an E-M5 {callback, mask} pair with mask 0, so it never fires); the image's frame-supply helper is E-M1 logic without the OM-5 "no pool frames past N" rule; the mode-7 pool site is the one byte at 0x607a1508; all 16 open call sites are E-M5 versions of the same functions. [code].3-§5
- E11 extra mapping, 2026-11-05 ~20:00 (before the E11a build): the image has 8 dormant October prep hooks keyed on G+20 (0x602b29f7, 0x602b2cd3, 0x602b2db5, 0x602b2ee1 via 0x607b2000, 0x602b3254, 0x602b437b, 0x602b5c69, 0x602b5d39) and ported state-37 handlers for events 61/81/83; the arm flag is set at the force_tap exit 0x607b4725; chooser 0x602b3454; type-5 wrapper site 0x607a0976. The frame-supply helper 0x607a14e9 requests the output frame with mode 1 (OM-5 uses 0) and lacks the OM-5 "no pool frame when ≤3 of N remain" rule; N is OM-5 S+2228 (no E-M5 field), so take it from the armed level; S+1652 is a native counter. The OM-5 DigitalNd ignores event 20 (release). OM-5 entry 0x602b91a5, capture queue 0x620cfe48, pending list 0x620cfe6c; capture start OM-5 0x602bbb77 = E-M5 0x602b0a5a; OM-5 0x602bc77f has no E-M5 counterpart (leave out). [code] private notes (tools)
- E11a step 1 done, 2026-11-05 ~20:05: `flag.s` (Live ND flag G+20 = 0x607a0114 set at the forced-press route store, cleared at every other route store, chooser 0x602b344e → state 35 when route 4 and flag 1, via boot guard at 0x600d079e) written on the maintainer's build box from the STEPS.md spec and reviewed; `sim/flag_sim.py` runs it on the real E10g bytes: force_tap identical to E10g in 5184 cases except the flag byte, chooser native in all 36 cases but (route 4, flag 1, section ready) → 35, 5 mutants caught. E11a code region 0x6079d800-0x607a0000 (10 KB free in the raised section 4). Pin patterns occur once each (0x607b469d, 0x607b470c). [code] private notes (flag.s, sim/flag_sim.py, STEPS.md)
- E11a step 2 done, 2026-11-05 ~20:20: `edits_e11a.py` (pool mode byte 0x607a1508 07→00; the 51 bytes 0x607a0b12..0x607a0b44 of the state-35 entry rewritten to zero callback-table words +16/+20/+32/+36/+48 and the two pairs, keeping the dark-pass test on G+21 = 0x607a0115 and its ctx+1260 |= 0x8000). Found while specifying: the (20,sp) flag the entry tests is the DARK-PASS flag (OM-5 ctx+2197 → image G+21 via hook 0x607a0156), not the Live ND flag; the OM-5 progress callback is stored only on the dark pass; the object word (ctx+1148)+112 is the one set to 8192 just before. `sim/edits_sim.py` passes (dark 0/1, pool site, byte identity, 4 mutants caught). [code] private notes (edits_e11a.py, sim/edits_sim.py, STEPS.md)
- E11a step 3 done, 2026-11-05 ~20:50: `supply.s` = literal port of the OM-5 frame-supply helper 0x602b9faf (modes 0 output / 1 top-up / 2 per-frame refill; refill gets no frame when N − ((done−1) mod N) ≤ 3; pool mode 0; N from the armed request at M+24 since ctx+2228 has no E-M5 field). Found: the image's three callers pass the E-M1 numbering (1 = output, 0 = supply), so the builder repoints the three 5-byte calls (0x607a14c1/0x607a15ab/0x607a0eb4) at per-site stubs; the current-frame-id word *(0x607b6000) (OM-5 *(0x620cfe08)) is written for supply jobs and no-frame jobs, NOT for the output job (my first spec had it inverted; the differential sim caught it). Variable map OM-5→image: 0x620cfe0c→0x607a96e0 ctx, 0x620cfe6c→0x607a9740 pending list, 0x620cfe08→0x607b6000 id pointer, 0x620cfe48→0x607a971c capture queue. `sim/supply_sim.py`: 864 cases identical to the OM-5 helper. [code]
- E11a OM-5 audit, 2026-11-05 ~21:40 (the maintainer: OM-5 behaviour everywhere): the October state-35..37 port follows OM-5 31..33 but carries E-M1 struct offsets. Native E-M5 pairs give: frame-header pointer table 4930/5068/5644/5740/14478/5076 (image had 4934/5072/5648/5744/15610/5080; OM-5 7298/7436/8012/8108/18250/7444; getter E-M5 0x602b1695 ids 1..64 vs OM-5 0x602bc9eb ids 1..32), header +24874 / +24892 (OM-5 28654/28672, image 26014/26032; the 28xxx block is -3780 on the E-M5), ctx byte 2352 = prop 35873 (OM-5 2287, image 2363 which no E-M5 code writes). Right as ported: 1926 (capture-start error, OM-5 0x602bfe21 ~ E-M5 0x602b48f1), 2108/2116, 24864, 1658/1686/2332. ctx = native E-M5 0x6210fb74 (getter 0x602bbb9f); the OM-5 DigitalNd block ctx+2196..2207 lives in the image G block 0x607a0114 (+2196 flag, +2197 dark, +2198 abort, +2200 id, +2204 prep frame). Event mask d1 = 0x40000020 (OM-5 31 for events 64/90) is a native E-M5 value (0x602b7136 registers event 64 with it); the image passed 0. Prep hook W8 (0x602b2cd3 → 0x607aa600) is not OM-5: OM-5 0x602c749d returns 0 under the flag, so ctx+1656 (E-M5 1658 = 0x621101ee, the native long-exposure NR decision) is 0 under Live ND; the October rewrite can return 1, which sends the finish chooser to state 36. W1-W7 match OM-5. Job free 0x607a1569 lacks OM-5 id!=0, top-up 0x607a15d5 lacks the id-word check. The prep frame is released by the state-37 entry (not a leak). Pending-list capacity 64 = E-M5 native. Parked: 4 develop/metadata flag sites (E11b), dark-pass descriptor slot (E11c), Tv class 5 (UI). [code]
- E11a step 4 done, 2026-11-05 ~22:10: `dry.s` (begin/add/finish stand-ins; finish posts event 46 via the callback with status 0, then the native finish runs; OM-5 job free and top-up id check) and the 12-row AUDIT table in `edits_e11a.py`; `sim/dry_sim.py` passes (job free/top-up identical to OM-5, W8 returns 0 under the flag). Found for step 5: the E10g arm check needs ARMED = 0 and the StlUhs hand-over is what set ARMED = 2, so state 37 must set it; M+1536..2303 (E8b StlUhs frame records) is free in state 35. [code]
- E11a step 5 done, 2026-11-05 ~22:00: `log.s` (597 B at 0x6079da10) swaps the eight state-35/36/37 main and event-handler pointers (0x600d04c4/d8/ec, 0x600d056c/9c/a4, 0x600d0670/80) for logging stubs that jump on to the original with every register and the stack intact; ring of 64 records + start/end snapshots in an E11A block at M+1536; state 37 sets ARMED 1 -> 2 (N+36 = 3) so the E10g dump path ends as before; log version 44 (0x607b20e1 2b -> 2c). Gotcha found by the sim: on MN10300 `call`/`calls` write the return address to mdr, so a stub that jumps on to a handler must save mdr before its own call. Main-handler records carry bit 7 (0x2380/0x2480/0x2580 + event). `decode_e11a.py` prints a run-A verdict. Step 6 (builder) spec written. [code]
- E11a step 6 done, 2026-11-05 ~22:10: builder `build_e11a.py` + `link_e11a.py` + `check_addrs.py` (desktop 6e7ae4b; address check PASS on all four sources); cloud `sim/build_sim.py` shows construct equals the sims' composed image: 1284 block0 bytes in 66 runs 0x600d04c4..0x607b4713, HHHR and other blocks unchanged, expected E11a SHA-256 623039e0812c1ebb7d9b7ef82cc57f931ecaf75eaf43f909f653268fdd040a87. Design summary for the maintainer before step 7: `DESIGN-CHOICES.md`. [code]
- E11a built 2026-11-05 ~22:16 (step 7, the maintainer's desktop `make e11a`, 5c412c9): SHA-256 623039e0812c1ebb7d9b7ef82cc57f931ecaf75eaf43f909f653268fdd040a87 = the cloud in-memory build; delta 62,425 B; verified from the delta (step 8). PROCEDURE.md: run A Tv 1/8 silent H tap, run B unarmed. [code]
- E11a run A try 1, 2026-11-06 07:30 (camera time): shots out of order (silent H tap before the arming silent single; route tap [3, 0]), so the tap was an unarmed native press and no LND3B7 was written. Shows only that E11a boots and arms as E10g. Rerun pending. [camera]
- E11a run A try 2, 2026-11-06 ~07:34: armed silent-H tap entered state 35 (black screen, continuous capture) but never stopped; battery pull, no LND3B7 (RAM log lost), boots fine after. [camera] Cause [inferred]: the image's finish 0x607a0bcc is a message handler (messages 0x200000/0x210000 registered via 0x602a1e60 at 0x607a08e5/0x607a0928), so capture end is signalled from outside state 35 (OM-5 iseq engine or sensor sequence); the dry add never signals N frames. Next: trace the OM-5 senders + frame-count stop; add a hard frame cap and a hang-proof log.
- E11a2 built 2026-11-06 ~07:20 (the maintainer chose a diagnostic after static OM-5 stop-path tracing found no difference): E11a + stub stop_e63 (199 B at 0x6079dc70, via event-63 pointer 0x600d056c) that, when flagged+armed, counts event 63 (L+60) and at count 2N and 3N sends the native sensor stop exactly as StlUhs release 0x602b4ecb (post 0x2000 via 0x602a1b6e, then 0x602b98de), logging 0x23ff and L+62; log v45. stop_sim + in-memory build_sim PASS; SHA a85469f96f9f98ef9d925be1a914c317ae4dc9e4b759d69acc29f55ac813b560 (desktop 768d1e5 = cloud delta apply). Tool note: gas relaxes an out-of-range bne via a `.L0^A_0` label that the link scripts can't resolve; write `beq; jmp` explicitly. [code]
- E11a2 run A try 1, 2026-11-06 ~08:20: armed silent-H tap captured ~2 s, no photo (the maintainer; fits the stop at frame 16 at 1/8) then the camera RESTARTED by itself; no LND3B7; LND311 = arm dump only (v45, block empty). [camera] Inference: the native stop pair sent from inside the state-35 event-63 handler ends the capture but faults/resets the camera (OM-5 sends it from state 33 after the finish) [inferred]. The RAM log at 0xa07b4e00 is lost on reset (inside the block0 image). Next: log outside block0 image (survives a warm reset) and/or raise the OM-5 finish at N.
- Native capture end [code] 2026-11-06: per-frame completion 0x602b0ceb asks the state's template supplier (0x6210f5ec via 0x602b0b8a); a null next buffer sets 0x8000 on the descriptor, 0x602b1036 zeroes the record and 0x602b1041 raises end flag 0x6210f59c -> sequence end (events 56/66) -> finish. State-35 supplier 0x607a0c83 returns null when its queue 0x607a971c is empty (template built at 0x607a0ad7). So the OM-5 capture ends by its queue running dry; in E11a it never ran dry. 0x602a1b6e = flag-word bookkeeping (clear bits in 0x62107768, error-log 171 if not set), not an event post; 0x602b98de = async camera-task message {type 2, code 47, sub 3}.
- E11a3 built 2026-11-06 ~10:28 (the maintainer chose it): E11a + count_e63 (ev63 count, ctx+1652 snapshots) + sup_e11a3 supplier wrapper that returns null from count 2N (forced run-dry), stats in block X = M+2112; log v46. Sims PASS (sim interpreter gained rets/retf); SHA 8137eaa6a5ee9f4a7a0e46fa4eb60d01b4ae26bd855721960a07155ce941d1a8 (desktop 15e83fc = cloud delta apply); zip the project folder Tool gotchas: `mov imm32,aN` with an ABS-listed value gets rewritten by the ABS pass (load via dN); gas relaxed-branch labels need `as -L`. [code]
- E11a3 run A try 1, 2026-11-06 ~14:30: black screen ~1 s then camera RESET; no LND3B7; LND311 = arm dump (v46, block X empty). [camera] Resets earlier than E11a2 (2 s) with the same cut-off count, so the reset likely comes from the native end path / finish / our state 37, or the stubs on the camera, not our cut-off [inferred]. Blocker: a reset-proof log (mirror into RAM not reloaded at boot, dump on next arm). Empty 00000000.C11/00001800.W11 files are the dump writer markers (close result 0, write result 0x1800 = 6144 B).
- E11a end-states audit 2026-11-06 (other tool, handoff PR #5, reviewed in our Live ND work): **likely reset cause found**. F1: state-37 main 0x607a12c5 keeps the donor's boolean stack argument (`clr d2` 0x607a130a, `mov d2,(4,sp)` 0x607a1337) for native builder `call 0x602b97bf,[d2,d3,a2,a3],20` (0x607a133d), which reads (24,sp) as a record pointer (`mov (24,sp),a0; mov (60,a0),a1` 0x602b9816) -> null+0x3c dereference; native callers 0x602b5990/0x602b9665 pass a pointer, output layout also differs from donor 0x602c520b. F5: callback 0x607a1982 posts event 81 (0x607a1989); native 0x602b8806 and our table want 83. F3: native finish 0x602ba0a9 sets command mask 0x500 when ctx+2000 is clear (donor skips 0x400 when ND active). F2 (swap loses row bit 0) and F4 (event 82 inner calls) are later. State 37 is reached only when the capture ends, which fits E11a (no end, no reset) vs E11a2/E11a3 (reset). [code], `results/REVIEW.md`
- F1 contract (2026-11-06): native builder 0x602b97bf takes d1 = boolean (donor: stack) and stack = record pointer, out+4 = ((rec+60))+6 (donor: d1 halfword). Port passes d1 = (12,a2) (wrong flag) and stack 0 (reset). Fix: d1 = 0, stack R with (R+60) = a2+6. [code]
- E11a join points (port code -> native helpers) and the layer split: see `firmware/live-nd-port-layers.md` (2026-11-06). [code]
- E11a4 built 2026-11-06 (the maintainer chose fixes + reset-proof log): E11a3 + F1 builder args (f1_args 0x6079ddd8: d1=0, stack=(0x607b6000)) + reply events 81/82/83 + mirror of L/X to P 0xa19ff000 (count, ev46, state-37 entry) restored into the next dump by dump_wrap (11 call sites, incl. 0x607b4658 = post-run LND3B7). build_sim PASS; SHA 5d5bb53425c507215618802f7741f0f316558be5f2fe7d39a99753fed48080fd (desktop 56d9db7 = cloud in-memory = delta apply); log v47. [code]
- E11a4 run A try 1, 2026-11-06 ~15:45: silent H tap -> black screen (battery icon shown), quiet burst whirr ~60 s, power switch ignored, battery pull, no photo; LND311 = arming dump (P can't survive a pull). [camera] The fixes removed E11a3's ~1 s reset, so E11a3 likely did reach state 37 and died at F1; state 37 now gets further but never completes. Suspects: the 1537 request to native task (0x60040fda) (payload 0x607a96ec, same layout as native 0x62110c7c), F3 0x400, command 80 at 0x607a17fa, dry iseq stand-ins. A hang needs its own exit (timeout -> self-restart, or card write). [inferred]
- State-37 audit round 3 (2026-11-06, handoff PR #5, reviewed): state 37 exits on low mask 0x9000 (ev47 sensor-stop ack, ev87 descriptor-151 callback), then state 19 gates on high bits 61/81/82/83 (native handlers there). Synchronous waits with timeout -1: kind-7 output 0x602bc2c1 (wait 0x602bc52e), command-38 RPC 0x602bacb3, queue sends; 151 prepare/submit errors leave 0x1000 pending. 1537 receiver 0x6044605d reads only +0x29/+0x2c (match). No single static cause: needs runtime breadcrumbs (E11a5 spec). Current state halfword (0x62107744), next (0x62107746); banks 0x62107768/0x6210776c. [code];
- E11a5 built 2026-11-06 ~19:10 (the maintainer chose): breadcrumbs (bset stubs) at 17 state-37 calls and 8 handler words into Y = M+2144; 20 s native timer (0x6006be97 mode 0) armed at the first armed event 63, wd_cb snapshots state/banks, mirrors and forces a restart via a 0xc4000000 read. build_sim PASS; SHA fb15b98229eb8eee49af4080367fa7e632fb9fd6ee43930886434e6b083f39aa (desktop c5f5398 = cloud = delta apply). [code]
- E11a5 run A try 1, 2026-11-06 ~18:50: silent H tap -> capture, self-reset after ~1 s (no pull); post-reset LND311 not restored (L/X/Y zero). [camera] E11a4 hung instead, so the reset likely comes from E11a5's additions: the timer create from the event-63 handler, an early timer fire (then P lost on reset), or a stub. The restore can't show an invalid P, so the next build must report P's raw state. [inferred]
- E11a5b built 2026-11-06 ~19:15 (the maintainer: "go for it"): timer create now copies the native sequencer 0x602a5c64..8b (0x60069e11(3), 0x6006be97 mode 1 = 32-slot pool, 20000 ms, 0x60069e5a); Y+4 bit3 + mirror before the create, bit4 after; wd_cb5b stores the event-63 count in Y+6; block Z (M+2176, 48 B) = raw P header + P copy of Y before every dump, so a non-restored LND311 still shows whether P survived. build_sim PASS; SHA c1f8080c9ded140f5ec3043d2759b494111e714cb3f8df41653e6620312f8964 (desktop 8bc2811 = cloud sim = delta apply). [code]
- E11a5b run A try 1, 2026-11-06 ~19:20: arming single slower than usual; silent H tap -> ~1 s black screen with some UI over it, then self-reset (as E11a5). LND311 v49 not restored; block Z = raw P (0xa19ff000) all ones with 10 zero bits in 48 B, no magic = power-on/decayed DRAM pattern, not our data. [camera] The native mode-1 create did not remove the ~1 s reset, so the mode-0 pool is not the (only) cause. Open: whether this LND311 is the pre-tap single (then P is just not zeroed at boot) or post-reset (then P does not survive the reset). Next: bisect crumbs vs timer on E11a4 + P read-back self-test. [inferred]
- E11a5b run A answer (the maintainer 19:25): the LND311 was the post-reset single, so P (0xa19ff000) does NOT survive the ~1 s self-reset; it reads as a power-on pattern. No RAM log survives this reset; a hang log must reach the card first. New suspect for the reset: our own watchdog firing early (its forced 0xc4000000 read); E11a4 without it hung instead. [camera]/[inferred]
- E11a5c built 2026-11-06 ~19:50 (the maintainer chose "Watchdog without restart"): E11a5b with wd_cb5b's forced restart read (0x6079e6b2) nopped, plus block T (M+2224) = P+1016/1020 before and read back of LNDT/0xabbbb2b3 before every dump. No dump runs between boot and the arming LND311 (all 11 writer calls behind arm_gate, desktop check), so T "before" there = what survived the previous boot. build_sim PASS; SHA 454bee91757adc647edc289b93ba52552254a9510e39d5591113afe58b3df2d4 (desktop c542b1f = cloud sim = delta apply). [code]
- E11a5c run A try 1, 2026-11-06 ~19:45: still self-reset ~1 s after the silent H tap. Post-reset LND311 block T: P before = ffffffff/ffffffff, read back = LNDT/0xabbbb2b3. So P (0xa19ff000) is writable but does NOT survive the self-reset (the arming dump wrote the marks in the same boot); no RAM log survives it. The watchdog's forced restart is not the cause (removed, still resets). Remaining suspects shared by E11a5/5b/5c and absent in E11a4: breadcrumb stubs, timer create at the first armed event 63. [camera]/[inferred]
- Static research 2026-11-06 ~20:00 (the maintainer chose research first): no defect found in the E11a5 timer setup or the 25 breadcrumb stubs. The 20 s timer cannot fire early (2 ms pool tick); its create is fatal only if the pool is full (two different pools in E11a5 vs 5b/5c, so unlikely); bset abs32 is a native encoding; stubs touch no stack/regs. Bisect build E11a5d (timer setup skipped, 2-byte branch at 0x6079e54c) specced. [code]/[inferred]
- E11a5d built 2026-11-06 ~20:10 (the maintainer: "go"): E11a5c with the timer setup skipped (bra at 0x6079e54c), log v51. SHA 31739d8fa6ddcd534a2715b898859598b2f0ba0837cc3095d319077e4141b0c8 (cloud in-memory = desktop 0fd2c09 = delta apply). Hang -> the timer caused the reset; reset -> the breadcrumbs. [code]
- Preflash 2026-11-07 (recovery work): E11a5d FAILS R1: the E10g-era boot guards 0x600d06a4-0x600d07b9 overlap the HHHR guard area 0x600d079e-0x600d07b9 by 27 B (HHHR P2c has different code there). Safe alone, but Live ND and HHHR lines cannot be stacked until the Live ND guard tail moves. Every later Live ND build must pass preflash.py (REPORT.md in the zip). [code]

- E11a end path vs OM-5 [code] 2026-11-06: state-35 table 0x600d0528 (ev56 -> 0x607aa187, ev66 -> 0x607a0f34); ev56/ev66/finish 0x607a0bcc/ev46 0x607a10cb match OM-5 0x602b9b13/0x602b99b9/0x602b963f/0x602b9b86 instruction for instruction with verified target pairs (0x602a1b6e = OM-5 0x602aa55b = wait-mask clear on 0x62107768, not a post; ev46 struct offsets shifted by 3780). Only difference: dry_fin calls the finish callback synchronously. End states 36/37 audited in private notes #5.

## How it compares with caduceus's Live ND (E-P7)

- External comparison 2026-11-11: caduceus-ep7 (E-P7, public) "early alpha Live ND" is stock Multiple Exposure with Auto
  Gain forced (1/N average), ND3/ND4 only, AP mode only, one frame per press; their one-press attempts (continuous drive,
  burst limit, custom self-timer) hung or crashed and are parked. Ours does ND2-ND16 in one press with job-11 merge, but
  isn't user-ready (card-file trigger, E11 end path open). Same blocker on both sides: ending a multi-frame capture
  cleanly. [code] (their repo, read-only)

## Limits and open items

- Main pool = 20 slots: 16 held + 2 stream at ND16. **ND32 has no native code to port** on OM-5/OM-5 II; plan is a
  two-pass merge (or running accumulator), as OM-1 does natively. [code]+[inferred]
- Single-drive trigger cuts the stream after 1 frame (cause unfound); trigger stays silent H burst until the menu stage. [camera]
- Antishock while a log dump is pending froze the camera once (E7b); unexplained. [camera]
- The E2r base (so every build since, E10f included) has a copied state table at 0x600d0200 with 38 entries: 34 StlTakeCave = native StlTake (0x602b34c6) and 35-37 DigitalNd/DarkRdy/End (0x607a07f2/1245/12c5). The range check at 0x602a1347 is cmp 37 and the chooser default at 0x602b3464 is mov 34, so every single shot runs through state 34. HHHR will take state 38. 2026-11-05 [code]
- E10f with Live ND disarmed matches stock 1.7 in om-emu: boot, S1/S2 to card, playback and menus. om-emu doesn't run the shooting state machine, burst or block2, so state 34 and the E10f sites weren't exercised. 2026-11-05 [code]
- OM-5 II 1.1 menu path (om-emu): Shooting Menu 2 > 1. Computational Modes > Live ND Shooting (greyed in P, enabled in S/M) > page with Live ND Shooting Off/On, ND Number, LV Simulation; ND Number lists ND2-ND16 and wraps (stand-in lens). 2026-11-05 [code]
- Card I/O rule: only a silent single shot (drive 30) may read the request or write logs. A burst writes nothing. Live ND gotchas for other hooks:. 2026-11-05 [code]
- LV preview needs job 12 **and** its setter (0x9d window words). [code]
- Menu: U1 on/off via appended prop + setting id > 1649, U2 ND number, U3 full OM-5 polish (the maintainer: U3 essential, not urgent).

## Paths we tried and dropped (don't repeat)

- E-M1 III-based stages 1-3U (the maintainer's tool, 2026-10-20..22): replaced by the OM-5 base (memory fit). M0-M3E2a (other tool):
  DSP gate and memory ownership proofs, then superseded by native StlUhs capture.
- E10c/d/e fps caps: wrong model (OM-5 never caps fps), dropped. "Longer frames from the burst" was wrong until E10f.

camera runs, build archive,
