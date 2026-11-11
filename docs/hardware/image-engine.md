# Image engine ("DSP") and its job programs

The image engine runs small **job programs** (microcode) that the MN103 loads and submits. We call it "the DSP".
Live ND's merge and HHHR's compose are jobs.

## Where the programs live
- Block 2, resource **0x8007** ("bank 6"): one entry per job number, index = job number. [code]
- E-M5 III payloads end at flash 0x45c77400; Live ND staging used 0x45c77400-0x45c86e00; 0x45c86e00-0x45d60000
  (868 KB, zero) is free for HHHR jobs. [code]
- Native job programs run from RAM 0xa411f540 (job 0) to 0xa4277140 (end of job 10). 0xa4277140-0xa42bf540
  (296 KB) has no code references. [code] Donor job load addresses (e.g. OM-5 job 14 0xa42a7d40) overlap E-M5
  job 9 (0xa422d140-0xa4265140), so donor jobs must be loaded elsewhere. [code]
- Program load: 0x6005a177(a0=dst, a1=flash, d0=size, d1=258); dest must be in 0xa0000000-0xbfffffff or the
  camera resets (M1d/M1e). [camera]
- Jobs don't need native addresses: job 11 ran from section-4 slack RAM and from a descriptor pool slot. [camera]

## Job table across bodies
| job | E-M5 III | E-M1 III 1.6 | OM-5 1.2 | OM-5 II | use |
|---|---|---|---|---|---|
| 0-10 | yes | same | same | same | native; purposes mostly unidentified |
| 11 | empty (0x600 placeholder) | 0x4400 | same | same | **Live ND photo merge** (average of N raw frames) |
| 12 | empty | 0xb600 | same | same | **Live ND live-view accumulator** (start/add/roll) |
| 13 | empty | empty | empty | empty | placeholder everywhere |
| 14 | empty | 0x48000 | 0x41800 | 0x42a00 (changed) | HHHR compose into 4 planes |
| 15 | empty | 0xe000 | 0xd600 | 0x9000 (changed) | HHHR hole fill |
| 16 | empty | 0x29c00 | same | same | HHHR RGB |
| 17 | empty | 0x7200 | 0x7600 | same | HHHR resize |
| 18 | absent | 0x4400 | same | same | unknown (OM-5 setter 0x603292c0) |

OM-1 / OM-1 II: **no job program matches** any of the above (sha256 per entry), so OM-1 jobs can't be used. [code]

## Native jobs 0-10 (mapped 2026-11-06)
Detail, layouts and callers:.
- Wrappers 0x60318301..0x603185c3 reload the program if bit `1<<job` of 0x8ff001b8 is set (jobs 2-7, 9), then call
  0x603185eb(job, 0, rec, flags), which copies 17 record words; records start {callback, context, ...}. [code]
- Setter table 0x60257b88: setters for jobs 3-6 and 9 pick the window slot from record byte +0x3f: window =
  0x9d000000 + slot<<24, so **0x9e000000 is slot 1 of the same engine** (job 0 always uses it). [code]
- Jobs 2, 3, 5, 7, 9, 10 read their default words from the tail of their own program blob (like job 14). [code]

| job | RAM program | size | purpose |
|---|---|---|---|
| 0 | 0xa411f540 | 0x51400 | AF image processing (FCS_IP cluster, caller 0x606aff4c) [inferred] |
| 1 | after job 0 | 0x5b200 | unknown (no setter; frame + rectangle; callers 0x602aaa89, 0x6056281e) |
| 2 | 0xa41cc140 | 0x19000 | full-sensor raw combine of 2-3 frames, used by **Live Composite** (0x602a7745 → 0x602bf7b4 → 0x603720a9) [inferred]. One 0/1 option (record word 10); natively only 0 runs. The blend is in the microcode: 0 = lighten [inferred], 1 unknown; needs a camera run to prove. [code] |
| 3 | 0xa41e5540 | 0x14400 | focus-stack merge step (6 buffers) [inferred] |
| 4 | 0xa41f9d40 | 0x11400 | **motion-compensated warp**: aligns a 4736×3616 YC frame using a 22×16 motion-vector field (buffer 0x36016 from `MDET_CALC_FLAME_VECTOR` 0x605de1f5) → 4480×3360 planar (caller 0x60381776) [code]; part of a native multi-frame align+merge pipeline (shot kind 19, maybe in-camera HDR) [inferred] |
| 5 | 0xa420b540 | 0xb600 | resize to full + half size [inferred] |
| 6 | 0xa4217540 | 0x4800 | focus-stack merge step (3 buffers) [inferred] |
| 7 | 0xa421c540 | 0xe800 | focus-stack merge step (3 buffers, also the final pass) [inferred] |
| 8 | 0xa422b540 | 0x1600 | **hardware memcpy** (`CAvpiPcomMemToMemHwcpy`, 0x603f43b8: 128 KB chunks, waits on flag 0x60041200; window 0x00 src, 0x04 dst, 0x08 len) [code] |
| 9 | 0xa422d140 | 0x38000 | raw development in 8 strips (14-bit OB/WB clip) [inferred] |
| 10 | 0xa4265540 | 0x11c00 | unknown; mode-selected coefficient tables (still task 0x6056175a) |

- 2026-11-06: jobs 3-7 are the **in-camera focus-stack merge** (shot kind 19: 3-15 frames + reference; MDET motion vectors
  coarse then fine, job 4 warp per frame, then jobs 5 → 3 → 6 → 7). [inferred, strong] Kind table: 11 = HDR1/HDR2,
  14 = Hand-held Starlight; both also use `MDET_CALC_FLAME_VECTOR` but merge via the IPCR command path `0x603741e0`. [code]
Reuse: job 8 (fast frame copies), job 2 (lighten-style raw stacking, mode not yet proven), job 4 + motion vectors
(native frame alignment: the missing piece for handheld multi-frame NR / handheld Live ND). No native average, min or subtract job was found, so Live ND still needs OM-5 job 11. [inferred]

## Parameter window 0x9d000000
- 0x9d000000+ is the job-engine **parameter window**, not new hardware. Each job has a setter in a per-job
  table (E-M5 III **0x60257b88**, OM-5 **0x6025f8e8**, index = job number). A setter writes its parameter words
  and **0x9d200010 = the job's program address**. [code]
- E-M5 use: job 8 0x00-08, job 10 0x10-18, job 7 0xac-c0. 0x1c-0x54 unused on E-M5 III. [code]
- OM-5 job 12 setter 0x6032a739 writes 15 words 0x1c-0x54 incl. **65536/N and log2(N)** from field +36 (N frames).
  Job 18 setter 0x603292c0 writes 0x1c-0x3c. [code] The LV-preview port needs job 12's setter. [inferred]
- Job 11 setter (OM-5 0x6032a626) writes **no** window words: everything is in the record. [code]
- HHHR setters (OM-5 0x6032a094 / a26f / a2d6 / a419) are leaf functions; job 14's writes 610 words and reads
  defaults from the last 0x100 bytes of its own blob (prog+0x41700): move that pointer with the program. [code]

## Job 11 record (420 bytes)
| offset | field |
|---|---|
| 0 | 32 × 12-byte inputs: u32 address + 4 × u16 OB (black level) |
| 384 | output address |
| 396 / 400 / 404 / 408 | Number, MemHw (pitch), Hw (width), Vw (height) |
| 412 | 4 × u16 WBClip |
OB observed 1025 (= 256<<2). Full frame: Number N, 5240/5240/3912, stride 0x1f47600. [camera]
- Output = average of inputs in the same packed 12-bit format (80/80 sampled px). Repeated input addresses are
  accepted (ND2/ND4 via `input i = frame (i mod K)`). [camera]
- Timing: 2 frames 32.5 ms, 8 frames ~87 ms, 16 frames 142.5 ms. [camera]
- Output can go in place into an input frame, which then becomes the saved photo. [camera]

## Submitting a job safely (from M1 / E5)
- Submit 0x603185eb(d0=job, d1=1, a0=packet, a1=16); worker sets C+4: 2 = done, 3 = worker fail. [code]
- The bridge checks every record (capacity = min(BC+12, BC+16)/12, Number limits). **Any refusal parks the worker
  and hangs the camera at the next image-processor use until the battery is pulled** (E5a). Read the bridge
  checks for every record change. [camera]
- Running job 12 without its setter "executes, output unverified". [camera]

