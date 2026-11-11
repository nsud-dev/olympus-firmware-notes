# Image engine ("DSP") and its job programs

Next to the control CPUs, the SoC has an image engine: hardware built for heavy pixel work such as developing raw
frames, resizing and merging. It doesn't run the main program. Instead, the control CPU loads a small program for it
(a "job"), fills in a parameter record and submits it. We call this engine "the DSP" and its programs "jobs"; the
programs themselves are microcode we can't read, only load and run.

This page explains where the job programs are stored, which jobs exist on which camera, what we have worked out about
the E-M5 III's own jobs 0 to 10, and how to submit a job without hanging the camera. Two of our feature ports depend on
jobs: Live ND's frame merge is job 11 and Handheld High Res (HHHR) uses jobs 14 to 17.

Tags: **[code]** read in the firmware, **[camera]** seen on a real E-M5 III, **[inferred]** not traced or tested.

## Where the programs live

In flash, the job programs sit in block 2 of the firmware file, in resource **0x8007** (we call it "bank 6"), one entry
per job, indexed by job number. [code]

- The E-M5 III's own programs end at flash 0x45c77400. Our Live ND staging used 0x45c77400-0x45c86e00, and
  0x45c86e00-0x45d60000 (868 KB of zeros) is free for HHHR jobs. [code]

At run time the programs are copied into RAM:

- Native programs run from RAM 0xa411f540 (job 0) to 0xa4277140 (end of job 10). The next 296 KB,
  0xa4277140-0xa42bf540, has no code references. [code]
- Jobs from another body (the "donor") can't use their own load addresses: OM-5 job 14 loads at 0xa42a7d40, which
  overlaps E-M5 job 9 (0xa422d140-0xa4265140). Load them elsewhere. [code]
- The loader is 0x6005a177(a0=dst, a1=flash, d0=size, d1=258). The destination must be in 0xa0000000-0xbfffffff or the
  camera resets (builds M1d/M1e). [camera]
- Jobs don't need their native address: job 11 ran from spare RAM after section 4 and from a descriptor pool slot.
  [camera]

## Which jobs each camera has

| job | E-M5 III | E-M1 III 1.6 | OM-5 1.2 | OM-5 II | use |
|---|---|---|---|---|---|
| 0-10 | yes | same | same | same | the camera's own jobs; see the next section |
| 11 | empty (0x600 placeholder) | 0x4400 | same | same | **Live ND photo merge** (average of N raw frames) |
| 12 | empty | 0xb600 | same | same | **Live ND live-view accumulator** (start/add/roll) |
| 13 | empty | empty | empty | empty | placeholder everywhere |
| 14 | empty | 0x48000 | 0x41800 | 0x42a00 (changed) | HHHR compose into 4 planes |
| 15 | empty | 0xe000 | 0xd600 | 0x9000 (changed) | HHHR hole fill |
| 16 | empty | 0x29c00 | same | same | HHHR RGB |
| 17 | empty | 0x7200 | 0x7600 | same | HHHR resize |
| 18 | absent | 0x4400 | same | same | unknown (OM-5 setter 0x603292c0) |

Sizes are in bytes. The OM-1 and OM-1 II have a new engine: **none** of their job programs match any of the above
(compared by sha256 per entry), so OM-1 jobs can't be used. [code]

## The E-M5 III's own jobs 0 to 10 (mapped 2026-11-06)

Detail, layouts and callers:.

How the firmware runs them: [code]

- Wrapper functions 0x60318301..0x603185c3 reload a job's program if bit `1<<job` of 0x8ff001b8 is set (jobs 2-7 and
  9), then call 0x603185eb(job, 0, rec, flags), which copies 17 record words. Records start {callback, context, ...}. [code]
- A table of "setter" functions at 0x60257b88 writes each job's parameters. Setters for jobs 3-6 and 9 choose a window
  slot from record byte +0x3f: window = 0x9d000000 + slot<<24, so **0x9e000000 is slot 1 of the same engine** (job 0
  always uses it). [code]
- Jobs 2, 3, 5, 7, 9 and 10 read default values from the end of their own program (job 14 does the same).

What each job does:

| job | RAM program | size | purpose |
|---|---|---|---|
| 0 | 0xa411f540 | 0x51400 | AF image processing (FCS_IP cluster, caller 0x606aff4c) [inferred] |
| 1 | after job 0 | 0x5b200 | unknown (no setter; frame + rectangle; callers 0x602aaa89, 0x6056281e) |
| 2 | 0xa41cc140 | 0x19000 | full-sensor raw combine of 2-3 frames, used by **Live Composite** (0x602a7745 → 0x602bf7b4 → 0x603720a9) [inferred]. One 0/1 option (record word 10); natively only 0 runs. The blend mode is inside the microcode: 0 = lighten [inferred], 1 unknown; proving it needs a camera run. [code] |
| 3 | 0xa41e5540 | 0x14400 | focus-stack merge step (6 buffers) [inferred] |
| 4 | 0xa41f9d40 | 0x11400 | **motion-compensated warp**: aligns a 4736×3616 YC frame using a 22×16 motion-vector field (buffer 0x36016 from `MDET_CALC_FLAME_VECTOR` 0x605de1f5) into 4480×3360 planar (caller 0x60381776) [code]; part of a native multi-frame align-and-merge pipeline (shot kind 19, maybe in-camera HDR) [inferred] |
| 5 | 0xa420b540 | 0xb600 | resize to full and half size [inferred] |
| 6 | 0xa4217540 | 0x4800 | focus-stack merge step (3 buffers) [inferred] |
| 7 | 0xa421c540 | 0xe800 | focus-stack merge step (3 buffers, also the final pass) [inferred] |
| 8 | 0xa422b540 | 0x1600 | **hardware memcpy** (`CAvpiPcomMemToMemHwcpy`, 0x603f43b8: 128 KB chunks, waits on flag 0x60041200; window 0x00 src, 0x04 dst, 0x08 len) [code] |
| 9 | 0xa422d140 | 0x38000 | raw development in 8 strips (14-bit OB/WB clip) [inferred] |
| 10 | 0xa4265540 | 0x11c00 | unknown; mode-selected coefficient tables (still task 0x6056175a) |

Jobs 3 to 7 together are the **in-camera focus-stack merge** (2026-11-06). That is shot kind 19: 3-15 frames plus a
reference; the motion detector (MDET) estimates motion vectors coarse then fine, job 4 warps each frame, then jobs
5, 3, 6 and 7 run in that order. [inferred, strong] In the same kind table, 11 = HDR1/HDR2 and 14 = Hand-held
Starlight; both also use `MDET_CALC_FLAME_VECTOR` but merge through the IPCR command path `0x603741e0`. [code]

What this means for reuse: job 8 gives fast frame copies; job 2 gives lighten-style raw stacking (mode not yet proven);
job 4 plus the motion vectors give native frame alignment, the missing piece for handheld multi-frame noise reduction or
handheld Live ND. No native average, minimum or subtract job was found, so Live ND still needs the OM-5's job 11.
[inferred]

## The parameter window at 0x9d000000

The address range from 0x9d000000 is how the CPU hands parameters to a job: a **parameter window** of the job engine,
not separate hardware. Each job has a setter function in a per-job table (E-M5 III **0x60257b88**, OM-5
**0x6025f8e8**, indexed by job number). A setter writes the job's parameter words, and writes the job's program address
to **0x9d200010**. [code]

- On the E-M5 III, job 8 uses 0x00-08, job 10 uses 0x10-18 and job 7 uses 0xac-c0; 0x1c-0x54 is unused. [code]
- The OM-5's job 12 setter 0x6032a739 writes 15 words at 0x1c-0x54, including **65536/N and log2(N)** from field +36
  (N = number of frames). The job 18 setter 0x603292c0 writes 0x1c-0x3c. [code] Porting the Live ND live-view preview
  needs job 12's setter. [inferred]
- The job 11 setter (OM-5 0x6032a626) writes **no** window words: everything is in the record. [code]
- The HHHR setters (OM-5 0x6032a094 / a26f / a2d6 / a419) don't call other functions. Job 14's writes 610 words and
  reads defaults from the last 0x100 bytes of its own program (prog+0x41700), so if you move the program, move that
  pointer with it. [code]

## The job 11 record (420 bytes)

Job 11 (the Live ND merge) takes everything from one record in memory:

| offset | field |
|---|---|
| 0 | 32 × 12-byte inputs: u32 address + 4 × u16 OB (black level) |
| 384 | output address |
| 396 / 400 / 404 / 408 | Number, MemHw (pitch), Hw (width), Vw (height) |
| 412 | 4 × u16 WBClip |

What we saw on the camera: [camera]

- OB (black level) read 1025 (= 256<<2). For a full frame: Number N, 5240/5240/3912, stride 0x1f47600. [camera]
- The output is the average of the inputs, in the same packed 12-bit format (checked on 80/80 sampled pixels).
- The same input address may appear more than once, which is how ND2 and ND4 work (input i = frame (i mod K)).
- Timing: 2 frames 32.5 ms, 8 frames ~87 ms, 16 frames 142.5 ms.
- The output can be written in place into one of the input frames, which then becomes the saved photo.

## Submitting a job safely (learned in builds M1 and E5)

- Submit with 0x603185eb(d0=job, d1=1, a0=packet, a1=16). The worker then sets C+4: 2 = done, 3 = worker failed.
  [code]
- A bridge function checks every record (capacity = min(BC+12, BC+16)/12, limits on Number). **If it refuses a record,
  the worker parks and the camera hangs the next time anything uses the image processor, until you pull the battery**
  (build E5a). Read the bridge's checks for every change you make to a record. [camera]
- Running job 12 without its setter "executes, output unverified". [camera]

