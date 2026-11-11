# MN103 / AM33-2 control CPU

## Identity
- Panasonic MN103 family (MN10300), AM33-2 variant, little-endian, variable-length instructions. Identified with
  cpu_rec, confirmed by clean disassembly. [code]
- Same ISA and load base on every body we've opened: E-M5 III, E-M1 III, OM-5, OM-5 II, PEN-F, OM-1, OM-1 II. [code]
- Disassemble with GNU binutils `--target=mn10300-elf`, `objdump -m am33-2`. See tools.

## Calling convention: vendor spec (cc103S manual, 2026-11-08)

## Calling convention (Olympus ABI, read off the code)
- Integer args in **d0, d1**, pointer args in **a0, a1** (by class), the rest on the stack from **(4,sp)**.
  Return in d0 (ints) or **a0** (pointer getters). [code]
- d2, d3, a2, a3 (and r4-r7 where used) are callee-saved. [code]
- `call target,[regs],N` builds the **callee's** frame at the call site; the callee's `ret [regs],N` must match.
  New code calling firmware must copy `[regs],N` from an existing native call site. [code]
- A call writes its return address at (0,sp); save your own locals from (4,sp). (Lesson from E9a.) [code]
- `retf` returns through **mdr**: a gate that makes calls must save and restore mdr. [code]

## Original compiler (research 2026-11-08)
- Block0 was built with **Panasonic's own cc103-family toolchain (C++-capable variant), not GCC**: GCC's MN10300 ABI
  passes the first two argument words in d0/d1 whatever their type and has no ABI switches (Cygnus GNUPro ref), while
  stock passes pointers in a0/a1 by type; stock builds callee frames at the call site, which Panasonic's assembler
  supports with `.funcinfo`. [code]+[inferred]
- Code is C++ (820 `.cpp`, 257 `.c` file names; IBM Rhapsody OXF framework) with bare vtables (no offset-to-top or
  typeinfo slots, vptr at +0) and no RTTI/exception strings: not the GNU C++ ABI; EC++-style. No compiler version
  string in block0. [code]

## AM33-only instructions: don't emit them
- Stock Olympus code **never** uses AM33-only encodings (F7, FE>02, F9/FB/FD outside the UDF mul/float forms,
  F5 mov, r0-r7 extended regs): none in 4.1 M instructions. [code] (2026-11-05)
- GCC `-mam33-2` emits them (3-operand add/sub, 64-bit mulu). om-emu traps on them; our GDB sim ran them
  silently. Whether the real core runs them is **unknown**, so compile as plain MN10300.
  Scanner:. [code]

## UDF (user-defined function unit) ops
- `udf00/udfu00/udf01/udfu01` = 32-bit multiply (matches om-emu's spec). [inferred → corroborated]
- om-emu spec: udf02-06 float add/sub/mul/div/cmp, udf14 int↔float, udf15 read HI. [code, third-party]
- Float helpers seen in OM-1 II: 0x6004c188 fadd, 0x6004c19b fdiv, 0x6004c1ad fmul, 0x600487df sin,
  0x60048162 cos, 0x6004b9a3 dsub, 0x6004b9af dadd (OM-1 II addresses). [code]

## Useful fixed routines (E-M5 III 1.7)
| addr | what | tag |
|---|---|---|
| 0x60022e5c | hardware tick, **1 µs** | [camera] |
| 0x60036eeb | sleep (ms) | [code] |
| 0x6006be97 | timer create: d0 mode, d1 ms (halfword), a0 callback, a1 arg; mode 0 one-shot / 128 periodic = 12 hw-channel slots (0xa26405c0), mode 1/2 = 32-slot pool (0x6006c3ba); full pool -> fatal error 0x6005f9c9 level 2. Native sequencer wraps it in 0x60069e11(3)/0x60069e5a and its callback defers via 0x600691c8 (0x602a5c64..0x602a5cb6). 2026-11-06 private notes | [code] |
| 0x6006be97 (detail) | modes 1 and 2 both enter the pool 0x6006c3ba with d0 = 0, modes 129/130 with d0 = 128; mode 0/128 go to 0x6006bf5b. A null callback is fatal (0x6005f9c9 level 2). Pool count = (max(ms,2)+1)/2 (so 20000 ms = 10000). The pool ticks from a periodic mode-128 hardware timer of 2 ms created by pool init 0x6006c358 (callback 0x6006c4d7), so pool callbacks run in that timer's interrupt context; no free slot -> fatal 0x6005f9c9 code 0x19001805 level 2. Both paths take lock 0x600587e6 (id 0x0e0d0e0e, retry via 0x60023042) inside 0x60069e11(1)/0x60069e5a, so create only from task context. 2026-11-06 private notes 0x6006be97..0x6006c4d3 | [code] |
| 0x47001024 / 0x47001130 | memcpy / memset (outside block0) | [code] |
| 0x600386ae | returns 0 in task context (non-zero in ISR) | [code] |
| 0x600317b4 | current task id | [code] |
| 0x60069e11 / 0x60069e5a | critical section enter / leave (token) | [code] |
| 0x60051679 / 0x6005174e | lock take (with timeout) / give | [code] |
| 0x60045d92(n) | 1 if block0 section n is ready (see [boot](../firmware/boot-and-sections.md)) | [code] |
| 0x600590c9 | DSP address conversion (`& 0x3fffffff`) | [code] |
| 0x60064634 | valid image-address ranges check (b0000000-bfffffff, c4000000-dfffffff) | [code] |
| 0x60631fe8 / 0x606320f2 | fwrite / fread (card file I/O) | [camera] (M1d) |
| 0x60631f63 / 0x60631f6c / 0x60632180 / 0x606321ea | fopen `[],4` / fclose `[d2,a2,a3],16` / ftell `[d2,a2,a3],16` (msg 0x10007) / fseek `[d2,d3,a2,a3],20` (msg 0x10008); same layout as E-P7. Each call is a blocking RPC to FILECLBK (no timeout) from ordinary tasks. 2026-11-08 private notes | [code] |

## Address aliases
- 0x6xxxxxxx = cached view, 0xaxxxxxxx = uncached view of the same RAM (e.g. record 0x61a92e40 ↔ 0xa1a92e40).
  Read CPU-only structs through the cached pointer. [camera] (M3D-R1)
- CPU reads of the 0xc4000000 frame block **rebooted the camera** (E6e) while DSP access worked: treat that block as
  DMA-only or a different alias. [camera]

