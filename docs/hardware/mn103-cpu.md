# MN103 control CPU

<!-- house style -->
> **Technical reading.** The detailed version of [MN103 primer](../guides/mn103-primer.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

The camera's main program runs on Panasonic MN103 cores. This page covers what the CPU is, how functions pass arguments
and build their stack frames (the "calling convention"), which compiler Olympus probably used, a few instruction-set
traps, and a table of firmware routines that are handy when writing your own code.

If you are new to this CPU, two things matter most when patching. Copy the call frame of an existing native call
exactly. Stick to plain MN10300 instructions.

Addresses are E-M5 III firmware 1.7 unless another body is named.

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred or seen in an emulator.

## What the CPU is

The control CPU is a Panasonic MN103, also called MN10300. It is specifically the AM33-2 variant. It is little-endian
and has variable-length instructions, from one byte up to seven.[^fw1]

We identified it with the `cpu_rec` tool and confirmed it by clean disassembly. The project's first patch was made
with an old IDA Pro that has MN103 support.[^fw1]

Every body we have opened uses the same instruction set and the same load base. That covers the E-M5 III, E-M1 III,
OM-5, OM-5 II, PEN-F, OM-1 and OM-1 II.[^fw1]

To disassemble, use GNU binutils built for `--target=mn10300-elf` and run `objdump -m am33-2`.

## How functions are called

A calling convention is the agreement between a caller and a callee about where arguments go, where the result comes
back and which registers survive the call. The MN103 has four data registers (d0 to d3) and four address registers
(a0 to a3).

### What the code does

These rules are read off the firmware.[^fw1]

- The first integer arguments go in **d0, d1** and the first pointer arguments in **a0, a1**, chosen by type. Anything
  else goes on the stack starting at **(4,sp)**.
- Integers come back in d0. Functions that return a pointer return it in **a0**.
- d2, d3, a2 and a3, and r4 to r7 where used, are callee-saved. A function that uses them must put them back.

The unusual part is the call frame. On this CPU, `call target,[regs],N` builds the **callee's** stack frame at the
call site. It saves the listed registers and reserves N bytes. The callee then ends with `ret [regs],N`, which must
match.[^fw1]

> [!WARNING]
> New code that calls a firmware function must copy `[regs],N` from an existing native call to that function. Guessing
> it corrupts the stack.

Two more rules were learned the hard way.[^fw1]

- A call writes its return address at (0,sp), so keep your own locals from (4,sp) upwards.
- `retf` returns through the **mdr** register. A gate (a small wrapper that calls other code) must save and restore
  mdr.

The Ghidra module models the callee frame through context at the call target. Our GCC port encodes the same ABI.

### What Panasonic's manual says

Panasonic's MN103S C compiler manual (Pub.No.13220-010 §5.4, 2001) documents the same convention in more
detail.[^fw2]

- Ints and floats go to D0, D1 and pointers to A0, A1, left to right.
- **Then leftovers cross-spill.** Extra ints use a free A0/A1, and extra pointers a free D0/D1.
- Doubles take a free D0+D1 or A0+A1 pair.
- Everything else goes on the stack from (4,SP). No stack slots are reserved for register arguments.
- Variadic functions (like printf) put the last named argument and the `...` arguments on the stack.
- A returned struct uses a hidden pointer as the first stack argument.
- Results come back in D0, pointers in A0 and doubles in D0+D1. D2, D3, A2 and A3 are callee-saved.
- Direct calls enter a function at `_0name`. The CALL instruction saves registers and builds the frame from the
  linker-patched FUNCINFO record. Indirect calls (CALLS) enter at `_name`, which has its own movm/add prologue.

The 2001 MN103S EC++ toolchain (v4.0R1, inside `DFBuilder32R_v301B20.exe`) is unpacked but not run. Its library .text
does not occur in block0, so Olympus used a later version.[^fw3][^inf2] Running it sandboxed (Wine or DOSBox) for probes
is a pending decision.

## Which compiler built the firmware

Block0, the main program, was built with **Panasonic's own cc103-family toolchain, in a C++-capable variant, not
GCC**.[^fw3][^inf2] Two things give it away.

- GCC's MN10300 ABI passes the first two argument words in d0/d1 whatever their type, and has no switch to change that
  (Cygnus GNUPro reference). The firmware passes pointers in a0/a1 by type.
- The firmware builds callee frames at the call site, which Panasonic's assembler supports with `.funcinfo`.

The code is C++. 820 `.cpp` and 257 `.c` file names appear in strings, plus the IBM Rhapsody OXF framework. Its vtables
are bare, with no offset-to-top or typeinfo slots and the vptr at +0. There are no RTTI or exception strings. So it is
not the GNU C++ ABI. It looks like Embedded C++ (EC++). There is no compiler version string in block0.[^fw3]

The closest public tool is **cc103S Ver 5.4 Rel 4** in DebugFactory Builder 5 (Nuvoton Japan, Windows, free
registration). It is C only. The C++ compiler Olympus used is not public. It is untested.[^inf2] Nuvoton has since closed
its download portal, leaving a support form only.[^inf4] One public lead is the archive.org `panasonic_dev_tools` item.
It holds Panasonic dev tools from 1998-2002, in Japanese, as a 109 MB zip with unlisted contents.[^inf2]

Block0 also shows two conventions side by side. The bundled Expat 1.95.5 XML library (plain C) passes a 3rd or 4th
pointer in a free d0/d1. Olympus's own code puts it on the stack. So the libraries came from a different compiler,
version or mode.[^fw3]

## What block0's code looks like, by the numbers

These counts cover the 102,113 functions in our symbol table (12.2 MB, 4.80 million instructions), E-M5 III 1.7
block0. They come from an `objdump -m am33-2` disassembly of block0 with our function list.[^fw4]

- **Instruction lengths.** 1 byte 27%, 2 bytes 42%, 3 bytes 13%, 4 bytes 3%, 5 bytes 3%, 6 bytes 6%, 7 bytes 6%. The
  average is 2.55 bytes. Register-to-register moves, `inc4`, `asl2`, `clr` and most short loads are one byte.
- **Most common.** `mov` is 46% of all instructions, then `call` 8.7%, `cmp` 6.8%, `add` 6.0% and `movhu` 5.0%.
- **Calls and returns.** 418,741 `call` (direct, callee frame at the call site), 38,195 `calls` (indirect), 81,692
  `ret`, 17,591 `retf` (return through mdr) and 18,701 `movm` (multi-register save and restore).
- **Hardware loops.** 15,070 `setlb` (set loop buffer) with `Lcc` conditional loop-back instructions. `lne` is the most
  common, with 7,309. The boot stub's copy loop is an example: `setlb; mov (a1),d0; inc4 a1; mov d0,(a0); inc4 a0;
  inc d1; cmp 1536,d1; lcs`.
- **Maths.** 11,114 `udf00` and 7,529 `udfu01` (multiply), 9,898 `div` and 3,466 `divu`, and only 174 `mul` and
  158 `mulu`.
- **Bit operations.** 11,563 `btst`. `bset` and `bclr` are rare (203 and 242). They are a read-modify-write of a memory
  byte, which the MN10300 does as one locked operation.[^inf1]
- **Interrupts.** Almost no `trap` (1) or `rti` (3) sit inside functions. Interrupt entry and exit are in the
  always-ready code.[^inf1]

## AM33-only instructions: don't use them

The AM33 variants add instructions that the plain MN10300 doesn't have. Stock Olympus code **never** uses them. None of
these encodings appear in 4.1 million instructions: F7, FE>02, F9/FB/FD outside the UDF multiply and float forms, F5
mov, and the extended registers r0 to r7.[^fw5]

GCC with `-mam33-2` does emit them, for example a 3-operand add/sub and a 64-bit mulu. The om-emu emulator traps on
them, and our GDB simulator ran them silently. Whether the real core runs them is **unknown**, so compile your code as
plain MN10300. We have a scanner that finds them.[^fw5]

## UDF operations (the maths helper unit)

UDF stands for "user-defined function" unit, an add-on the chip uses for multiply and floating point.

- `udf00`, `udfu00`, `udf01` and `udfu01` are 32-bit multiplies. This matches om-emu's description.[^inf3]
- According to om-emu, udf02 to udf06 are float add, subtract, multiply, divide and compare. udf14 converts between int
  and float, and udf15 reads the HI register.[^emu1]

### No FPU and no SIMD

There is no AM33-2 FPU in the main program, and no SIMD. This was checked on E-M5 III 1.7 and OM-5 II 1.1 block0.
Decoded as plain `mn10300`, there are no FPU instructions at all. The `fadd`, `fmov`, `mac` and `sat16` that
`-m am33-2` shows are the same bytes as UDF ops. The 6 `fmov ...,fpcr` hits carry junk values and sit in data, so
nothing sets up an FPU control register.[^fw6]

### Float library

Single-precision float runs on the UDF unit, through one small library. Each routine is one UDF op and `retf`.[^fw6]

| routine | UDF op |
|---|---|
| fsub | udf03 |
| fadd | udf02 |
| fcmp | udf06 |
| fdiv | udf05 |
| fmul | udf04 |
| int-to-float | `udf14 64` |
| float-to-int | `udf14 128` |

*The float library and the UDF op behind each routine. Addresses are in the [address reference](#address-reference).[^fw6]*

There are about 5,800 call sites on the E-M5 III and 6,100 on the OM-5 II. fmul is the most used, with 1,715 and 1,751.
Other UDF float ops in code are decoding noise. Only 3 symbol-table functions mix udf14 with two other float ops, and
they are data. Doubles are done in software next to these routines.[^fw6]

The OM-1 II has float helpers of its own, for fadd, fdiv, fmul, sin, cos, dsub and dadd.[^fw1]

## Useful firmware routines

These are routines our own code calls. "Task context" means normal code running in an operating-system task, as
opposed to an interrupt handler (ISR). The full list with addresses is in the
[address reference](#useful-routines-by-address).

### Timers

The timer creation routine takes d0 = mode, d1 = ms (halfword), a0 = callback and a1 = argument.[^fw7]

- Mode 0 (one-shot) and 128 (periodic) use 12 hardware-channel slots. They go to the hardware-channel path.
- Modes 1 and 2 use a 32-slot pool. Both enter the pool with d0 = 0. Modes 129 and 130 enter it with d0 = 128.
- A null callback is fatal error level 2. A full pool is fatal error level 2 too, with code `0x19001805`.
- The pool count is (max(ms,2)+1)/2, so 20000 ms = 10000.
- The pool ticks from a periodic 2 ms mode-128 hardware timer created by the pool init. So pool callbacks run in that
  timer's interrupt context.
- Both paths take a lock (id `0x0e0d0e0e`, with a retry) inside critical section enter (1) and leave. So only create
  timers from task context.

The native sequencer wraps it in critical section enter (3) and leave. Its callback defers through a helper.[^fw7]

The hardware behind it is channels 14 to 25 of the timer block.[^fw11] See also:
[Interrupts, timers and DMA](interrupts-timers-dma-technical.md#timers).

### Tasks and keys

- **Create a task.** a0 = name, d0 = 2 (create and start), d1 = exinf, a1 = entry, (4,sp) = priority,
  (8,sp) = stack size, (12,sp) = stack = 0. With 0 the kernel allocates the stack, as at one stock call site. The frame
  is `[d2,d3,a2,a3],56`. It returns the task id.[^fw8][^emu2]
- **Sleep.** Two routines sleep for a number of ms.[^fw1] One takes d0 ms, with frame `[d2],8`.[^fw1][^emu2]
- **Key state.** d0 = key code, frame `[d2,d3,a2,a3],24`. It returns **0 while the key is held**. OK is key 4. The
  boot's own key checks use it. It has the same shape as OMKit's OM-5 II routine.[^fw8][^emu2]
- **FastEndCb**, a late start-up callback. It is registered at start-up and waits for boot stage 13 or later. Its entry
  is `movm [a2],(sp); add -4,sp`, with a resume point after it. It is the mod loader's hook site.[^fw8]

### Cache write-back

One routine writes back and invalidates the **data** cache of the current core (core id register in the address
reference).[^fw9]

1. It enters a critical section.
2. It turns the D-cache off (CHCTR bit 1) and waits on busy (bit 3).
3. It writes back by reading two fixed regions.
4. It drains the core's bus buffer (bit 4 of a per-core register, `0x400` apart).
5. It invalidates the tags in 16-byte lines.
6. It sets CHCTR |= `0x22`.

It does not touch the instruction cache. Its frame is `[d2,d3],16`, and it has 21 stock callers. We use it for code
written at run time, in the mod loader hook helper.[^fw9] See also: [Caches](caches.md).

### File I/O

fopen, fclose, ftell and fseek have the same layout as on the E-P7.[^fw10]

- fopen `[],4`.
- fclose `[d2,a2,a3],16`.
- ftell `[d2,a2,a3],16`, message `0x10007`.
- fseek `[d2,d3,a2,a3],20`, message `0x10008`.

Each is a blocking call to the FILECLBK task with no time-out, made from ordinary tasks.[^fw10] fwrite and fread work
on the camera.[^cam1]

## Address aliases (cached and uncached)

The same RAM is visible at two addresses. `0x6xxxxxxx` is the cached view and `0xaxxxxxxx` the uncached view. For
example the record at `0x61a92e40` is also `0xa1a92e40`. Read structures that only the CPU uses through the cached
address.[^cam1]

> [!WARNING]
> CPU reads of the frame-buffer block at `0xc4000000` **rebooted the camera**, while the image engine could use it fine.
> Treat that block as DMA-only, or as needing a different alias.

## Caches

Each core has its own 8 KB data cache (2 ways, 256 sets, 16-byte lines, write-back), controlled by CHCTR. The
whole-cache routine handles the data cache only, for the current core. The instruction cache is invalidated only at
core start.[^fw1] See also: [Caches](caches.md), with the bus buffers and the boot access monitor.

## Address reference

E-M5 III 1.7 block0 addresses unless a body is named.

### Useful routines by address

<details><summary>Useful firmware routines and their addresses</summary>

| address | what | source |
|---|---|---|
| `0x60022e5c` | hardware tick counter, **1 µs** per count | [^cam1] |
| `0x60036eeb` | sleep (ms) | [^fw1] |
| `0x6006be97` | create a timer (see [Timers](#timers)) | [^fw7] |
| `0x47001024` / `0x47001130` | memcpy / memset (outside block0) | [^fw1] |
| `0x600386ae` | returns 0 in task context, non-zero in an interrupt | [^fw1] |
| `0x600317b4` | current task id | [^fw1] |
| `0x60069e11` / `0x60069e5a` | enter / leave a critical section (returns a token) | [^fw1] |
| `0x60051679` / `0x6005174e` | take a lock (with time-out) / give it back | [^fw1] |
| `0x60045d92`(n) | 1 if block0 section n is loaded and ready (see [Boot](../firmware/boot-and-sections.md)) | [^fw1] |
| `0x60051d55` | create a task | [^fw8][^emu2] |
| `0x60051a24` | sleep d0 ms, frame `[d2],8` | [^fw1][^emu2] |
| `0x60120227` | key state | [^fw8][^emu2] |
| `0x6019c68c` | FastEndCb | [^fw8] |
| `0x600644ae` | write back and invalidate the data cache | [^fw9] |
| `0x600232c5` | malloc d0 bytes, frame `[],4` (returns a0) | [^fw1][^emu2] |
| `0x600590c9` | convert an address for the image engine (`& 0x3fffffff`) | [^fw1] |
| `0x60064634` | check an address is in a valid image range (`0xb0000000`–`0xbfffffff`, `0xc4000000`–`0xdfffffff`) | [^fw1] |
| `0x60631fe8` / `0x606320f2` | fwrite / fread (card file I/O) | [^cam1] |
| `0x60631f63` / `0x60631f6c` / `0x60632180` / `0x606321ea` | fopen / fclose / ftell / fseek | [^fw10] |

*Firmware routines our own code calls.*

</details>

| item | address |
|---|---|
| timer hardware-channel slots | `0xa26405c0` |
| timer hardware-channel path | `0x6006bf5b` |
| timer pool | `0x6006c3ba` |
| fatal error | `0x6005f9c9` |
| pool init, its 2 ms callback | `0x6006c358`, `0x6006c4d7` |
| lock taken, its retry | `0x600587e6`, `0x60023042` |
| sequencer callback deferral | `0x600691c8` (`0x602a5c64`..`0x602a5cb6`) |
| timer block | `0x98900000` |

*Timer internals.*

| item | address |
|---|---|
| stock task creation with stack 0 | `0x60182491` |
| boot key check | `0x60045b29` |
| OMKit's OM-5 II key state routine | `0x60130fb8` (OM-5 II) |
| FastEndCb string, registration | `0x601fbd06`, `0x607c244a` |
| boot stage wait, boot stage word | `0x6019a822`, `0xa265657c` |
| FastEndCb resume | `0x6019c691` |

*Tasks, keys and start-up.*

| item | address |
|---|---|
| core id register | `0x8050` |
| CHCTR | `0x8070` |
| write-back read regions | `0x28a00000`, `0x28a80000` |
| bus buffer, per core | `0x98100000` + `0x400` × core |
| tag regions | `0x28900000`, `0x28980000` |

*Cache registers and regions.*

| routine | E-M5 III 1.7 | OM-5 II 1.1 |
|---|---|---|
| fsub | `0x600e2233` | `0x600ef18c` |
| fadd | `0x600e223a` | `0x600ef193` |
| fcmp | `0x600e2241`, `0x600e2246` | |
| fdiv | `0x600e224d` | `0x600ef1a6` |
| fmul | `0x600e225f` | `0x600ef1b8` |
| int-to-float | `0x600e2308`, `0x600e2311`, `0x600e2350` | `0x600ef261`, `0x600ef26a`, `0x600ef2a9` |
| float-to-int | `0x600e21cf`, `0x600e21d7` | `0x600ef128`, `0x600ef130` |

*Float library.*

| routine | OM-1 II address |
|---|---|
| fadd | `0x6004c188` |
| fdiv | `0x6004c19b` |
| fmul | `0x6004c1ad` |
| sin | `0x600487df` |
| cos | `0x60048162` |
| dsub | `0x6004b9a3` |
| dadd | `0x6004b9af` |

*OM-1 II float helpers.*

| item | address |
|---|---|
| load base | `0x60021020` |
| boot stub copy loop | `0x60021278` |
| frame-buffer block | `0xc4000000` |

*Other addresses.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware.
[^cam1]: Seen on our E-M5 III.
[^inf1]: Inferred, not traced or tested.
[^fw2]: Read in Panasonic's MN103S C compiler manual (a vendor document), 2026-11-08.
[^fw3]: Read in the firmware, 2026-11-08, during the compiler research.
[^inf2]: Inferred, 2026-11-08.
[^inf4]: Checked 2026-11-08. Nuvoton closed its download portal on 2026-03-31.
[^fw4]: Counted in the firmware, 2026-11-19.
[^fw5]: Read in the firmware, 2026-11-05.
[^inf3]: Inferred, then corroborated by om-emu's description.
[^emu1]: From om-emu's documentation, third-party facts only.
[^fw6]: Read in the firmware, 2026-11-24.
[^fw7]: Read in the firmware, 2026-11-06.
[^fw8]: Read in the firmware, 2026-11-21.
[^emu2]: Run in an emulator.
[^fw9]: Read in the firmware, 2026-11-22.
[^fw10]: Read in the firmware, 2026-11-08.
[^fw11]: Read in the firmware, 2026-11-25.

