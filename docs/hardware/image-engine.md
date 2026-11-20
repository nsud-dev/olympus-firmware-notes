# Image engine ("DSP") and its job programs

Next to the control CPUs, the SoC has an image engine: hardware built for heavy pixel work such as developing raw
frames, resizing and merging. It doesn't run the main program. Instead, the control CPU loads a small program for it
(a "job"), fills in a parameter record and submits it. We call this engine "the DSP" and its programs "jobs"; the
programs themselves are wide microcode words. Their instruction set isn't decoded yet; the word format and the branch
target field are known (see [Program format](#program-format-2026-11-19)).

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
  camera resets. [camera]
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
| 10 | 0xa4265540 | 0x11c00 | fixed-coefficient filter or resampler, **not a gain map** (2026-11-19): record = input 0x10, output 0x14, mode class 0x18 (from caller record +40); the setter 0x60319cfd copies static tables from 0x604e22dc.. by mode: 3-tap weights summing to 1024 (614/205/205, 410/614/...), a monotonic index ramp (0,1,3,4,6,8,...), and 102 phase weights in steps of 71 = 853/12. No per-pixel or per-row gain input, so it can't give a smooth GND. (still task 0x6056175a, caller 0x60561eb2) [code]/[inferred] |

Jobs 3 to 7 together are the **in-camera focus-stack merge** (2026-11-06). That is shot kind 19: 3-15 frames plus a
reference; the motion detector (MDET) estimates motion vectors coarse then fine, job 4 warps each frame, then jobs
5, 3, 6 and 7 run in that order. [inferred, strong] In the same kind table, 11 = HDR1/HDR2 and 14 = Hand-held
Starlight; both also use `MDET_CALC_FLAME_VECTOR` but merge through the IPCR command path `0x603741e0`. [code]

What this means for reuse: job 8 gives fast frame copies; job 2 gives lighten-style raw stacking (mode not yet proven);
job 4 plus the motion vectors give native frame alignment, the missing piece for handheld multi-frame noise reduction or
handheld Live ND. No native average, minimum or subtract job was found, so Live ND still needs the OM-5's job 11.
[inferred]

## Program format (2026-11-19)

Worked out by comparing the job programs of the E-M5 III, OM-5 1.2, OM-5 II 1.1, E-M1 III 1.6 and PEN-F 3.1 byte for
byte.

- **A program is an array of 64-byte lines.** In a code line only the first 40 bytes (one **320-bit** instruction
  word, little-endian) are used and the last 24 bytes are zero. Lines whose last 24 bytes aren't zero are data (the
  defaults that jobs 1, 2, 3, 5, 7, 9 and 14 read from the end of their own program, 2 to 22 lines). [code]
- Identical instructions encode identically at every position (the placeholder program repeats lines), so the words
  aren't scrambled or encrypted. [code]
- The words are dense: 31,148 code words over the OM-5's 19 programs, 27,993 different. Every bit position varies
  except bits 133-140 and 233-239, which are always 1. So this is horizontal (VLIW-style) microcode with many fields
  per word, not a compact opcode stream. [code]
- Every program starts with the same 10-11 words (a shared start sequence). The 0x600 "empty" program (E-M5 jobs
  11-17, job 13 everywhere) is that start sequence plus an end: a stub that does nothing. [code]
- **Branch targets are absolute word indexes**, 13 bits: low 8 bits in bits 15-22, high 5 bits in bits 128-132.
  Where one version of a program inserts or removes words, exactly this field moves by the size of the change in
  every word that points past it (OM-5 vs OM-5 II job 14: +35/+37/+68 in ~75 words; OM-5 vs E-M1 III job 17: -19;
  OM-5 vs OM-5 II job 15: -117; PEN-F job 7 vs job 2: -2/+4). Example: word 2845 of OM-5 job 14 targets 2844 (a
  loop). [inferred, strong: every changed branch fits]
- The same bits mean other things in non-branch words. **Branch format marker:** words with bits 315-319 = 0 and
  bit 229 = 0 are branch words. In OM-5's programs 1,013 words match, and 1,012 of them have a target inside their own
  program. 159 of the 231 branches confirmed by diffs have this form. Most of the rest have bits 315-319 = 2, a second
  format that sometimes carries a target (perhaps conditional or loop control). Bits 315-319 look like the word's
  format/opcode selector (31 = the most common, non-branch). Script `cls.py`. [inferred, strong]
- **Control ops (first pass, 2026-11-19):** bits 315-319 take values 0-18 and 31 (31 = no control op, 15,024 of
  31,148 OM-5 words). Op 0 = jump. **Op 1 with bit 229 = 0 ends the job**: it is the last real word of every program
  (job 8 word 79, job 11 word 264, the stub's word 12), always with field value 256, followed by a few padding words.
  [inferred, strong]
- **Jump conditions:** bits 224-228 = 31 on the one jump that must be unconditional (word 0, "skip to the setup at
  word 10" in every job). All other jumps have small values there (2, 4, 5, 6, 7), together with a selector in bits
  120-127. So bits 224-228 are the condition code, 31 = always. Self- and near-loops such as job 11 word 127 → 126
  look like wait loops. [inferred]
- **Job 11 skeleton** (OM-5, 272 words): entry jump to 10, setup 10-69 (word 65 can exit straight to the end), main loop
  70-259 (word 259 jumps back to 70), end at 264. Job 8 (memcpy, 88 words): loop 50-53, exit jump 27 → 79, end 79.
  First-pass listings: private notes (made by `ddis.py`). [inferred]
- **Field boundaries** (bits that change together between consecutive words; horizontal fields keep their value until
  rewritten; `chg.py`): bits 0-14 are small fields of 1-3 bits; 15-22 branch low; 23-30 one 8-bit field; 33-104 mostly
  4-bit fields (nibbles), likely lane A register/operand selects; 109-119 window/address; 120-127 condition selector;
  128-132 branch high; 133-140 constant; 141-208 again mostly 4-bit fields (lane B); 224-228 condition; 229 branch flag;
  then 1-2-bit control bits up to 291 and wider fields 292-312; 315-319 control op. [inferred]
- **Constants:** apart from branch targets, the commonest change between versions of the same job (OM-5 vs OM-5 II /
  E-M1 III jobs 14, 15, 17; PEN-F job 7 vs job 2) is bits 0-14 alone: 3584 → 4096, 3072 → 3584 (OM-5 vs OM-5 II job
  14 words 1792-1793), 8 → 16 (job 15, with bits 105-108 1 → 2 in the same words). So bits 0-14 carry an immediate
  (sizes, counts) in some word formats. In others they hold flag bits (128 is common), so the meaning depends on the
  format. Script `nonbr.py`. [inferred]
- **Lane fields:** the 4-bit fields of both lanes (bits 33-104 and 141-208) use 15 as "idle" and 0-14 as values. Most
  of them use nearly all of 0-14, which fits 15-entry register or operand selects. Jobs share no code apart from the
  start sequence and the end, even with the address, constant and branch fields masked, so the meaning of these fields
  can't be read off by comparing jobs. [inferred]

### Camera tests on job 11 (2026-11-19)

A first test build ran OM-5 job 11 382 times on 80 × 64 test images (A = 256 + 32x, B = 1280), each time with lane A
or lane B of one main-loop word made idle.
- **No change stalled or crashed the engine**: all 382 passes ended cleanly. Each run took 10.5-11 ms whatever the
  change, so at this size the time is fixed overhead. [camera]
- Job 11's output is exactly (A + B) / 2, black level included. [camera]
- 95 changes altered the output (49 lane A, 46 lane B); 285 did nothing visible. [camera]
- Most effects hit only the start of a line or only its end, and the start and end words repeat at a fixed offset
  (lane A 116-122 ↔ 129-135, 155-161 ↔ 172-178): the main loop holds copies of one block per line segment. [inferred]
- Word groups [camera result, meaning inferred]: input B fetch or add (w151 B, w155 A, w130/172/173/213/228 B: output
  becomes (A + 256) / 2); black-level add-back (w194 B: −256); weights (w129 B: A + B − 640, w171 B: A at full
  weight, w198 A: slope 20 instead of 16); clip (w211 A → 4095); constants (w128 B → 640, w199 B → 256).
- **Second test (2026-11-19) [camera]:** flipped single bits in the active lane of the 8 words above, 474 passes, all
  clean (10.1-10.9 ms). Baseline is exactly (A + B) / 2 with A = 256 + 32x, B = 1024 + 16x. 40 bits change the output:
  w155 A 45-52, w198 A 77/79 (weight), w211 A 41-44 and 79 (79 = saturate to 4095), w151 B and w194 B 147-150,
  w129 B and w171 B 155-158, w171 B 179-181, w199 B 163-164/167-170 (output becomes 256).
- **Operand-select fields [inferred]:** 4-bit fields, 8 bits apart, in both lanes: lane A bits 41-44 and 49-52, lane B
  147-150 and 155-158 (+106 bits), plus 167-170 (w199, likely the output/destination select). Stock values in job 11's
  main loop are 0-3, or 15 = none (idle lane), so there is a small register/tap set 0-3. One flipped bit reads an empty
  register (0) or the black-level constant.

### Lane field map, offline after the camera tests (2026-11-19)
- **Two identical lanes.** Over all 19 OM-5 jobs (35,496 word pairs), bits that change together split each lane into
  the same run of 4-bit fields: lane A 37-40, 41-44, 45-48, 49-52, 53-56, 57-60, 61-64, 65-68, 72-75, 76-79, 84-87
  (plus 69-71, 80-83); lane B is the same layout **106 bits later** (147-150, 151-154, 155-158 ... 190-193). Bits 23-36
  of lane A and 133-146 of lane B hold all ones in job 11's main loop. [code]
- **15 registers + "none".** These fields hold 0-14, or 15 for unused, in every job (jobs 0, 1, 9, 14-16 use up to 14).
  Job 11 uses only 0-5 (main loop mostly 0-3); jobs 6, 11 and 17 are the small ones. Fits the second test's result: one flipped
  bit selects another register, which is empty (0) or holds the black-level constant. [code]/[inferred]
- **Values are held.** A field keeps its value over long runs of words (10-60 in job 11) and changes only where the
  program needs it, like mux or register selects that stay set. Camera-test effects concentrate on the words where the
  pattern changes (116-135, 154-178, 198-212, 222-229). [code]/[inferred]
- **Job 11 control flow:** entry 0 → 10; setup 11-69; branch 65 → 264 (end); main part 70-259 with a loop 97-140 (back
  jump at 140, condition c07), a skip 92 → 145, short waits 85/87 → 86, 127 → 126, 169 → 168, 221/224 → 223, and 259 → 70
  per line; END at 264. Words 230-251 changed nothing in either camera test at Number 2: they likely serve other inputs (more
  frames) or another segment not sampled. [code]/[inferred]
- **Not settled offline:** which 4-bit field is a destination and which a source. The values alone do not say it, and
  the semantics of fields 53-87 are unknown. Settling it needs a camera test that writes chosen values (D3: all 16 values
  in a few fields of w151, w194, w199, w211, reading the result each time). [inferred]
- Correction to "106 bits later": the first fields line up exactly (41-68 ↔ 147-174), but the tail does not: lane A
  69-71, 72-75, 76-79, 80-83, 84-87 vs lane B 175-178, 179-181, 182-185, 186-189, 190-193 (co-change boundaries). [code]
- **Third camera test (2026-11-19):** every value of 84 fields (register fields of w211 A and w151/w194/w199 B, operation
  fields of w198/w211 A and w171 B, each middle bit 88-127 of w151), 746 passes, all clean, even with bits 88-127 changed.
  10 fields matter. [camera]
  - **Destination:** w199 B 167-170 (stock 1): any other value leaves the output at the black level (256). [camera]/[inferred]
  - **Source:** w151 / w194 B 147-150 (stock 0): any other value reads an empty register (input B lost / black-level
    add-back lost). [camera]/[inferred]
  - **Register contents**, read through w211 A 41-44 at the line start: r0 = 256 (black level), r1 = the result,
    r2 = 4095 (clip level), r5 = a value that changes along the line, r14 = 3515, r15 = 181, the rest 0. The black level and
    clip level most likely come from the window (W+388, W+420). [camera]/[inferred]
  - **Gain stage:** w198 A 76-79 scales around the black level, (x - OB) * g + OB. Stock g = 1.0; other values pick 1.25,
    1.18 or 1.01 (constants not in job 11's data lines). The natural place for per-ND brightness. [camera]/[inferred]
  - **Saturate:** w211 A bit 79 (values 8-15) forces 4095. w171 B 179-181 (stock 1): values 2-7 set the middle segment to
    the black level. [camera]
  - **Middle bits of w151:** 106-109 replace or break input A, 110-116 act like a read offset (middle/end segments),
    123-127 drop input B in the middle/end segments; 88-105 and 117-122 no effect. [camera]/[inferred]
- **Fourth camera test (2026-11-19):** only the record changed (black level 0-512 per input, clip 1000-4095), 73
  passes, all clean. [camera]
  - **Black level:** each input's own black level is subtracted, and input 0's is added back to the output (r0 = input
    0's black level). Values below the black level go negative and still average correctly. [camera]
  - **Clip:** WBClip clips **each input before the merge**, at black level + clip. The gain comes after the clip.
    [camera]
  - **Fixed constants:** r2 = 4095 whatever the clip, r14 = 3514, r15 = 181. The gains of w198 A 76-79 (1.25, about
    1.177, about 1.013) do not follow the black level, so an earlier guess (g = 1 + black level / 1024) was wrong.
    r5 changes between runs (likely not set). [camera]/[inferred]
  - **Meaning:** the record sets black levels and clips but not brightness. Live ND does not need a gain: the merge is
    an average, so ND32 needs more inputs. The record has room for 32 inputs (32 × 12 bytes before the output address
    at +384); our guard and the native callers stop at 16 today. Live GND (a gain across the frame) has no ready
    mechanism. [inferred]
- **Fifth test built 2026-11-19** (not run yet): job 11 unchanged, record only. 1-32 inputs (ND32; our guard's limit
  raised from 16 to 32 for it), black frames among the inputs (darkening by an exact fraction, a possible stepped Live
  GND), bands of rows and narrower widths. [code]
  Its first run stopped at the first 3-input pass: our harness bridge refuses Number > (its input-size words) / 12
  with 0xa124, and the harness had left them at 2 inputs. A fixed build replaces it. [camera]/[code]
  The fixed build's run (2026-11-19) merged 2, 3, 4, 8, 15 and 16 inputs: every value is the per-pixel mean above black,
  **rounded to nearest** (3 and 15 inputs only fit rounding), in the same ~10 ms for 2 or 16 inputs. [camera]
  17 inputs was refused before the engine ran (0xa224) by a second 16-input check in our own Live ND code (job-11
  completion gate); a build with both checks raised to 32 is next. [camera]/[code]
- **Fifth test results (2026-11-19, all 36 passes):** job 11 merges **up to 32 inputs** unchanged, ~10 ms whatever N,
  rows or width. Exact rule (fits every printed value): out = OB + round_half_even(Σ(in − OB) × ceil(2^19/N) / 2^19)
  [camera]/[inferred]. Input order does not matter. Black inputs darken by exactly k/N. A record can cover a band of
  rows (1-row granularity); width is written in 10-pixel groups (Hw 45 writes 50). So ND32 is a frame-count and memory
  question, not microcode, and a stepped Live GND can be built from job 11 runs on row bands with black inputs. [camera]

### Static analysis limit (2026-11-19)

Control flow, field boundaries, constants and the host side are readable from the code alone. **What the lane fields
compute is not:** no shared code, no documentation, and no simulator. The fastest way to settle it is differential
testing on the camera (see the camera tests above).
- **Window offsets appear as immediates.** In OM-5 job 11, the 11-bit field from bit 109 holds the job's window byte
  offsets far more often than in any other job: 396 (pitch) 30 times, 400 (Hw) 28, 384 (output) 18, 398, 392, 390, and
  12 (the stride of the input table) 27 times. So that field is (part of) a load address/offset into the window.
  Exact field edges not settled. Script `imm.py`. [inferred]
- **Rough unit layout** (bytes of the 40-byte word; "idle" = byte 0xff, the value an unused field holds): bytes 0-2
  change in every word (sequencer: branch target low bits, next-word control). Bytes 3-10 and 17-23 behave as a matched
  pair: both stay idle in job 8 (memcpy) and the stub, both are lightly used in jobs 6 and 12, and both are busy in the
  heavy jobs. That looks like two parallel datapath lanes. Bytes 12-16 are busy in every job, including job 8: these
  carry the window and memory address fields (bits 104-120) and the branch high bits (128-132). Bytes 29-39 hold
  further control fields, including the always-1 bits. This is a first sketch from per-byte idle rates,
  not a decode. [inferred]
- **PEN-F has the same engine.** Its job programs are in block 2 resource 5 (not 6), with fewer jobs: its job 16 is
  byte-identical to job 8 (hardware memcpy), its job 7 is 88% the same as job 2 (Live Composite; the end part, words
  1411-1589, differs), and its jobs 13, 15 and 17 match nothing in the newer bodies. So PEN-F (2016) to OM-5 II (2023)
  share one microcode generation; only the OM-1 class differs. [code]

### Is it a known commercial core? (2026-11-19)

- No vendor or core name appears in any E-M5 III block. Searched for: Milbeaut, Socionext, Fujitsu, CEVA, Tensilica/Xtensa,
  Synopsys, VLIW, microcode, Venus. The only vendor strings are Panasonic device-tree names (`panasonic,dc13`,
  `panasonic,irqcon`, ...). [code]
- The SoC is Panasonic's (later Nuvoton Japan's) "dc13" family, which is the same lineage as the Lumix Venus Engine.
  The control CPU is Panasonic's own MN103, and the 320-bit horizontal microcode with a per-job parameter window looks
  like an in-house Panasonic image engine, not licensed DSP IP. So a published instruction set is unlikely.
  [inferred]
- Public Panasonic sources (searched 2026-11-19) give no instruction set for this engine. The closest descriptions:
  Matsushita patent US6671708 (1998) describes a program-controlled image processor with a sequencer, **two address
  generators, two data memories and two pipeline units**, plus fixed-function pipelines. That matches our sketch of a
  sequencer, an address field group and two matched datapath lanes. Panasonic's UniPhier media SoCs (Panasonic
  Technical Journal 58-1, 2012) pair an "Instruction Parallel Processor" (IPP) with a "Data Parallel Processor" (DPP2:
  128-bit SIMD, some 256-bit). Other hits were unrelated (MPEG decoders, ARM NEON, a Ricoh SIMD patent). Treat these as
  hints only: none names this chip. [inferred]
- Lumix bodies of the same era probably run the same engine, but **we don't use Lumix firmware**.
  Panasonic's download licence forbids reverse engineering, and our five Olympus bodies are enough to compare. [policy]

## The parameter window at 0x9d000000

The address range from 0x9d000000 is how the CPU hands parameters to a job: a **parameter window** of the job engine,
not separate hardware. Each job has a setter function in a per-job table (E-M5 III **0x60257b88**, OM-5
**0x6025f8e8**, indexed by job number). A setter writes the job's parameter words, and writes the job's program address
to **0x9d200010**. [code]

- On the E-M5 III, job 8 uses 0x00-08, job 10 uses 0x10-18 and job 7 uses 0xac-c0; 0x1c-0x54 is unused. [code]
- The OM-5's job 12 setter 0x6032a739 writes 15 words at 0x1c-0x54, including **65536/N and log2(N)** from field +36
  (N = number of frames). The job 18 setter 0x603292c0 writes 0x1c-0x3c. [code] Porting the Live ND live-view preview
  needs job 12's setter. [inferred]
- **Correction (2026-11-19):** the job 11 setter (OM-5 0x6032a626) *does* write window words. It reaches the window
  through a computed base (0x9d000000 + slot<<24), which is why a search for absolute 0x9d addresses missed it. It copies
  the record into the window (layout under [The job 11 record](#the-job-11-record-420-bytes)). [code]
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

How the setter hands the record to the microcode (OM-5 0x6032a626; W = 0x9d000000 + slot<<24): [code]

| window | value |
|---|---|
| W+12i, i < Number | input i address |
| W+12i+4 / +8 | input i OB pairs, each u16 >> 2 (mask 0x3ffc3ffc, so OB 1025 becomes 256) |
| W+384 | output address |
| W+388 / +392 | output OB = max(OB0, OB3) >> 2, both halves (the setter also writes this back into record +388/+392) |
| W+396 | MemHw / 10 × 16: line pitch in bytes, because the packed format stores **10 pixels per 16 bytes** (12-bit, padded) |
| W+400 / +404 / +408 | Hw, Vw, Number |
| W+412 / +416 | engine slot, constant 2 |
| W+420 / +424 | WBClip pairs |
| W+0x200010 | program address (OM-5 0xa4297540) |

So the microcode reads its parameters from the window, at fixed word offsets. Those offsets (for example Number at
word 102) are the first thing to look for inside the job 11 program. [inferred]

## How the worker drives the engine (E-M5 III, 2026-11-19)

Read in the E-M5 III worker code 0x603185eb-0x60319646. Per engine slot s (0 or 1, the low nibble of packet byte +71),
E = 0x9d000000 + s<<24. [code]

- **Submit** 0x603185eb(d0=job, d1, a0=record, a1=flags) allocates a 76-byte packet, copies 17 words, stores job at
  +68, a global mode byte (0x8050) at +69, d1 at +70 and a1 at +71 (low nibble = slot, high nibble = chained-job
  flag), then either runs it at once (mode 1) or posts it to the worker queue. [code]
- **Lock:** each slot has a semaphore (4103 for slot 0, 4104 for slot 1; table 0x604e1f08) and an event flag (4132 /
  4133; table 0x604e1efc). [code]
- **Start** (0x60319559): memory-port select words at 0x99200264 / 0x99300264 / 0x99b00264 + 4s (16 on the port named
  by packet +69, else 0); interrupt enable 0x98800148 = 1<<(21+s); E+0x800000 = 0, E+0x800040 = 1, E+0x603404 = 15;
  call the job's setter (it fills the window and E+0x200010 = program address); E+0x200004 = 0; E+0x200000 |= 0x400 |
  8 | 2; E+0x80000c = 1; then **E+0x800004 = 1 starts the program**. [code]
- **Status:** E+0x200000 bit 5 (0x60319485). **Stop:** E+0x800040 = 0, E+0x800000 = 1, interrupt clear 0x988001c4 =
  1<<(21+s). **Reset:** E+0x800004 = 0, E+0x800000 = 2, then wait for E+0x800008 bit 2. [code]
- **Completion:** the worker waits on the slot's event flag (set from the slot's interrupt, bit 21+s) with a per-job
  timeout in ms (table 0x604e1f98): job 0 20, 1 13, 2-4 2000, 5-7 1000, 8 100, 9 4000, 10 4, 11 600, 12 18, 13 100,
  14 2000, 15 500, 16 3500, 17 500. The E-M5 III already has entries for jobs 11-17, so the framework was never cut
  down for the missing programs. A wait result of -50 is a timeout. [code]
- Besides the setter table, each job has four more hook tables in RAM, called around the run (0x61e92ff0,
  0x61e93038, 0x61e93080, 0x61e930c8, 0x61e93110, indexed by job). [code]

## Submitting a job safely (learned on the camera)

- Submit with 0x603185eb(d0=job, d1=1, a0=packet, a1=16). The worker then sets C+4: 2 = done, 3 = worker failed.
  [code]
- A bridge function checks every record (capacity = min(BC+12, BC+16)/12, limits on Number). **If it refuses a record,
  the worker parks and the camera hangs the next time anything uses the image processor, until you pull the battery**
  Read the bridge's checks for every change you make to a record. [camera]
- Running job 12 without its setter "executes, output unverified". [camera]

