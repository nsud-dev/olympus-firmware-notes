# MN103 / AM33-2 control CPU

The camera's main program runs on Panasonic MN103 cores. This page covers what the CPU is, how functions pass arguments
and build their stack frames (the "calling convention"), which compiler Olympus probably used, a few instruction-set
traps, and a table of firmware routines that are handy when writing your own code.

If you are new to this CPU, the two things that matter most when patching are: copy the call frame of an existing
native call exactly, and stick to plain MN10300 instructions.

Tags: **[code]** read in the firmware, **[camera]** seen on a real E-M5 III, **[inferred]** not traced or tested.
Addresses are E-M5 III firmware 1.7 unless another body is named.

## What the CPU is

The control CPU is a Panasonic MN103 (also called MN10300), specifically the AM33-2 variant. It is little-endian and
has variable-length instructions, from one byte up to seven. We identified it with the `cpu_rec` tool and confirmed it
by clean disassembly; the maintainer had used an old IDA Pro with MN103 support for the first patch. [code]

Every body we have opened uses the same instruction set and the same load base: E-M5 III, E-M1 III, OM-5, OM-5 II,
PEN-F, OM-1 and OM-1 II. [code]

To disassemble, use GNU binutils built for `--target=mn10300-elf` and run `objdump -m am33-2`. See
tools.

## How functions are called

A calling convention is the agreement between a caller and a callee about where arguments go, where the result comes
back and which registers survive the call. The MN103 has four data registers (d0 to d3) and four address registers
(a0 to a3).

### What the code does (read off the firmware)

- The first integer arguments go in **d0, d1** and the first pointer arguments in **a0, a1**, chosen by type. Anything
  else goes on the stack starting at **(4,sp)**. [code]
- Integers come back in d0; functions that return a pointer return it in **a0**. [code]
- d2, d3, a2 and a3 (and r4 to r7 where used) are callee-saved: a function that uses them must put them back. [code]

The unusual part is the call frame. On this CPU, `call target,[regs],N` builds the **callee's** stack frame at the call
site: it saves the listed registers and reserves N bytes. The callee then ends with `ret [regs],N`, which must match.
So new code that calls a firmware function must copy `[regs],N` from an existing native call to that function; guessing
it corrupts the stack. [code]

Two more rules learned the hard way:

- A call writes its return address at (0,sp), so keep your own locals from (4,sp) upwards.
  [code]
- `retf` returns through the **mdr** register. A gate (a small wrapper that calls other code) must save and restore mdr.
  [code]

The Ghidra module models the callee frame through context at the call target; see
. Our GCC port encodes the same ABI.

### What Panasonic's manual says (cc103S manual, 2026-11-08)

Panasonic's MN103S C compiler manual (Pub.No.13220-010 §5.4, 2001) documents the same convention in more detail:
[code: vendor doc]

- Ints and floats go to D0, D1 and pointers to A0, A1, left to right.
- **Then leftovers cross-spill:** extra ints use a free A0/A1, extra pointers a free D0/D1.
- Doubles take a free D0+D1 or A0+A1 pair.
- Everything else goes on the stack from (4,SP); no stack slots are reserved for register arguments.
- Variadic functions (like printf) put the last named argument and the `...` arguments on the stack.
- A returned struct uses a hidden pointer as the first stack argument.
- Results: D0, pointers in A0, doubles in D0+D1. D2, D3, A2, A3 are callee-saved.
- Direct calls enter a function at `_0name`: the CALL instruction saves registers and builds the frame from the
  linker-patched FUNCINFO record. Indirect calls (CALLS) enter at `_name`, which has its own movm/add prologue.


## Which compiler built the firmware (research 2026-11-08)

Block0 (the main program) was built with **Panasonic's own cc103-family toolchain, in a C++-capable variant, not GCC**.
Two things give it away: GCC's MN10300 ABI passes the first two argument words in d0/d1 whatever their type and has no
switch to change that (Cygnus GNUPro reference), while the firmware passes pointers in a0/a1 by type; and the firmware
builds callee frames at the call site, which Panasonic's assembler supports with `.funcinfo`. [code]+[inferred]

The code is C++ (820 `.cpp` and 257 `.c` file names appear in strings, plus the IBM Rhapsody OXF framework). Its
vtables are bare (no offset-to-top or typeinfo slots, vptr at +0) and there are no RTTI or exception strings, so it is
not the GNU C++ ABI; it looks like Embedded C++ (EC++). There is no compiler version string in block0. [code]

The closest public tool is **cc103S Ver 5.4 Rel 4** in DebugFactory Builder 5 (Nuvoton Japan, Windows, free
registration), which is C only; the C++ compiler Olympus used is not public. Untested; the plan to check it is in
. [inferred] Nuvoton closed its download portal on 2026-03-31
(support form only). One public lead is the archive.org `panasonic_dev_tools` item (Panasonic dev tools 1998-2002,
Japanese, a 109 MB zip with unlisted contents). Details in the same file. [inferred]

Block0 also shows two conventions side by side (2026-11-08). The bundled Expat 1.95.5 XML library
(plain C) passes a 3rd or 4th pointer in a free d0/d1, while Olympus's own code puts it on the stack. So the libraries
came from a different compiler, version or mode. [code]

## AM33-only instructions: don't use them

The AM33 variants add instructions that the plain MN10300 doesn't have. Stock Olympus code **never** uses them: none of
these encodings (F7, FE>02, F9/FB/FD outside the UDF multiply and float forms, F5 mov, the extended registers r0 to r7)
appear in 4.1 million instructions. [code] (2026-11-05)

GCC with `-mam33-2` does emit them (3-operand add/sub, 64-bit mulu). The om-emu emulator traps on them, and our GDB
simulator ran them silently. Whether the real core runs them is **unknown**, so compile your code as plain MN10300.
[code]

## UDF operations (the maths helper unit)

UDF stands for "user-defined function" unit, an add-on the chip uses for multiply and floating point.

- `udf00`, `udfu00`, `udf01`, `udfu01` are 32-bit multiplies (this matches om-emu's description).
  [inferred → corroborated]
- According to om-emu: udf02 to udf06 are float add, subtract, multiply, divide and compare; udf14 converts between
  int and float; udf15 reads the HI register. [code, third-party]
- Float helper functions seen in the OM-1 II (OM-1 II addresses): 0x6004c188 fadd, 0x6004c19b fdiv, 0x6004c1ad fmul,
  0x600487df sin, 0x60048162 cos, 0x6004b9a3 dsub, 0x6004b9af dadd. [code]

## Useful firmware routines (E-M5 III 1.7)

These are routines our own code calls. "Task context" means normal code running in an operating-system task, as opposed
to an interrupt handler (ISR).

| addr | what | tag |
|---|---|---|
| 0x60022e5c | hardware tick counter, **1 µs** per count | [camera] |
| 0x60036eeb | sleep (ms) | [code] |
| 0x6006be97 | create a timer: d0 mode, d1 ms (halfword), a0 callback, a1 argument. Mode 0 (one-shot) and 128 (periodic) use 12 hardware-channel slots (0xa26405c0); modes 1 and 2 use a 32-slot pool (0x6006c3ba); a full pool is fatal error 0x6005f9c9 level 2. The native sequencer wraps it in 0x60069e11(3)/0x60069e5a and its callback defers via 0x600691c8 (0x602a5c64..0x602a5cb6). 2026-11-06 private notes | [code] |
| 0x6006be97 (detail) | Modes 1 and 2 both enter the pool 0x6006c3ba with d0 = 0, modes 129/130 with d0 = 128; modes 0/128 go to 0x6006bf5b. A null callback is fatal (0x6005f9c9 level 2). Pool count = (max(ms,2)+1)/2, so 20000 ms = 10000. The pool ticks from a periodic 2 ms mode-128 hardware timer created by pool init 0x6006c358 (callback 0x6006c4d7), so pool callbacks run in that timer's interrupt context; no free slot is fatal 0x6005f9c9 code 0x19001805 level 2. Both paths take lock 0x600587e6 (id 0x0e0d0e0e, retry via 0x60023042) inside 0x60069e11(1)/0x60069e5a, so only create timers from task context. 2026-11-06 private notes 0x6006be97..0x6006c4d3 | [code] |
| 0x47001024 / 0x47001130 | memcpy / memset (outside block0) | [code] |
| 0x600386ae | returns 0 in task context, non-zero in an interrupt | [code] |
| 0x600317b4 | current task id | [code] |
| 0x60069e11 / 0x60069e5a | enter / leave a critical section (returns a token) | [code] |
| 0x60051679 / 0x6005174e | take a lock (with timeout) / give it back | [code] |
| 0x60045d92(n) | 1 if block0 section n is loaded and ready (see [boot](../firmware/boot-and-sections.md)) | [code] |
| 0x600590c9 | convert an address for the image engine (`& 0x3fffffff`) | [code] |
| 0x60064634 | check an address is in a valid image range (b0000000-bfffffff, c4000000-dfffffff) | [code] |
| 0x60631fe8 / 0x606320f2 | fwrite / fread (card file I/O) | [camera] |
| 0x60631f63 / 0x60631f6c / 0x60632180 / 0x606321ea | fopen `[],4` / fclose `[d2,a2,a3],16` / ftell `[d2,a2,a3],16` (msg 0x10007) / fseek `[d2,d3,a2,a3],20` (msg 0x10008); same layout as the E-P7. Each is a blocking call to the FILECLBK task with no timeout, made from ordinary tasks. 2026-11-08 private notes | [code] |

## Address aliases (cached and uncached)

The same RAM is visible at two addresses: 0x6xxxxxxx is the cached view and 0xaxxxxxxx the uncached view (for example
the record at 0x61a92e40 is also 0xa1a92e40). Read structures that only the CPU uses through the cached address.
[camera] (M3D-R1)

One exception to be careful with: CPU reads of the frame-buffer block at 0xc4000000 **rebooted the camera**,
while the image engine could use it fine. Treat that block as DMA-only, or as needing a different alias. [camera]

