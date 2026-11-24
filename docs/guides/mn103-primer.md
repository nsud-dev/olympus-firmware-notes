# MN103 primer

*Guide 4 · E-M5 III firmware 1.7 · draft 1, 2026-11-19. New to these guides? Read
[Before you start](before-you-start.md) first. Open questions: research gaps.*

The main program runs on Panasonic MN103 cores. This guide is an introduction
for someone who knows another embedded CPU (ARM, AVR, 68000, MIPS): what the registers are, why the code is so compact,
the unusual way calls build stack frames, the hardware loop instruction, how maths is done, and the address space.
It ends with what all this means when you patch the firmware.

Everything here is read off the firmware or taken from Panasonic's own documentation, unless marked otherwise. Clock
speed, pipeline and caches have not been measured.

## 1. Origins

The MN10300 is a 32-bit CPU family that Matsushita (Panasonic) designed in the 1990s for its own consumer electronics.
The **AM33** is a later member with extra registers and instructions. GNU binutils calls the variant in this camera
`am33-2`. GNU tools still support the family, and Linux once had a port for it.

Olympus's system-on-chip (TruePic) was designed with Panasonic, which is how the MN103 ended up as its control CPU. The
image processing doesn't run on it. That is done by the image engine and other dedicated blocks. The MN103 runs the
camera's logic: menus, the shooting sequence, file writing, talking to the lens and the stabiliser.

Every Olympus and OM System body we have opened (E-M5 III, E-M1 III, OM-5, OM-5 II, PEN-F, OM-1, OM-1 II) uses the
same instruction set and loads its main program at the same address, which is why code from a newer body can run
on the E-M5 III.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| CPU identified | `cpu_rec`, then clean disassembly with `objdump -m am33-2` | [code] |
| same instruction set and load base 0x60021020 on all bodies we hold | [MN103 CPU](../hardware/mn103-cpu.md#what-the-cpu-is) | [code] |
| family history (Matsushita, 1990s, Linux port) | general knowledge, not from the firmware | [inferred] |

Sources: [MN103 CPU](../hardware/mn103-cpu.md), [SoC overview](../hardware/soc-overview.md).
</details>

## 2. Registers

The register set is small and split by purpose, a little like the Motorola 68000:

- **Four data registers, d0 to d3**, for arithmetic.
- **Four address registers, a0 to a3**, for pointers. Loads and stores take their address from these.
- **sp**, the stack pointer.
- **mdr**, the multiply/divide register. It holds the upper half of a multiply result, and it also holds the return
  address after a call (section 4).
- **psw**, the status word: condition flags and the interrupt mask.
- **lir and lar**, the loop registers used by the hardware loop (section 5).

The AM33 adds eight more general registers (r0 to r7) and some three-operand instructions. Stock Olympus code never
uses any of them, not once in 4.1 million instructions, so in practice this is an eight-register machine.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| no AM33-only encodings in stock code | scan of block0 | [code] |
| register roles | Panasonic cc103S manual (Pub.No.13220-010), binutils opcode table | [code: vendor doc] |

Sources: [MN103 CPU](../hardware/mn103-cpu.md#am33-only-instructions-dont-use-them).
</details>

## 3. Small instructions

MN103 instructions are anything from one to seven bytes long. The common ones are short: copying one register to
another, clearing a register, adding 4 to a pointer and shifting left by two are all single bytes. Across the whole main
program, more than a quarter of the instructions are one byte and over two thirds are one or two. The average is 2.55
bytes.

Having only eight registers is part of why. A register needs just two bits, so two of them and an operation fit in
one byte. The cost is that the code moves values around a lot. Almost half of all instructions (46 %) are `mov`.

| instruction | bytes | encoding |
|---|---|---|
| `mov d0,d2` | 1 | `82` |
| `clr d3` | 1 | `0c` |
| `inc4 a1` | 1 | `51` |
| `mov (0x8050),d0` (load from a 16-bit address) | 3 | `30 50 80` |
| `call 0x6005375e,[d2],12` | 5 | `cd fd 1e 80 0c` |
| `mov 0x60074498,a0` (32-bit constant) | 6 | `fc dc 98 44 07 60` |

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| length and instruction counts | 102,113 functions, 4.80 million instructions | [code] |
| encodings above | taken from `OlyTaStCpu` 0x6005185f and the task start code | [code] |

Sources: [MN103 CPU: by the numbers](../hardware/mn103-cpu.md#what-block0s-code-looks-like-by-the-numbers-2026-11-19).
</details>

## 4. Caller-built frames

This is the MN103's most unusual feature, and the one that matters most for patching.

On most CPUs a function sets up its own stack frame when it starts. It saves the registers it will use and makes room
for its locals. On the MN103 the **caller** does it. The `call` instruction names the target, the list of registers to
save, and the size of the frame:

```
call 0x6005375e,[d2],12      ; save d2, reserve a 12-byte frame, jump
...
ret  [d2],12                 ; at the end of 0x6005375e: restore d2, drop the frame, return
```

The callee ends with a `ret` that must list the same registers and size. The frame layout belongs to the callee, but
it is written into every call site. Panasonic's toolchain makes this work by having the linker fill in each call from
a record the compiler writes for each function.

Some other details:

- `call` also puts the return address in **mdr**. A function that calls nothing can then end with `retf`, which returns
  through mdr without reading the stack. About one return in six in the firmware is a `retf`.
- **Indirect calls** (`calls`, through a register: virtual methods, callbacks) can't carry a frame, so a function that
  is called that way has a second entry point with an ordinary prologue.
- Arguments go in registers **by type**: the first two integers in d0 and d1, the first two pointers in a0 and a1, the
  rest on the stack. Integer results come back in d0, pointers in a0.

The firmware has 418,741 direct calls and 38,195 indirect ones.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| call/ret frame rule | every direct call | [code] |
| `_0name` / `_name` entry points, linker-filled FUNCINFO | Panasonic cc103S manual §5.4 | [code: vendor doc] |
| `call` writes the return address to mdr | [gotchas](../reference/gotchas.md) | [code] |
| arguments by type (d0/d1 vs a0/a1) | read off the code, matches the manual | [code] |

Sources: [MN103 CPU: how functions are called](../hardware/mn103-cpu.md#how-functions-are-called).
</details>

## 5. Hardware loops

The MN103 has a small loop buffer. `setlb` (set loop buffer) marks the start of a loop and copies the next few
instruction bytes into the loop registers. At the bottom, a conditional loop instruction (`lne`, `lcs`, `llt` ...)
jumps back to the start if its condition holds, using the saved copy instead of fetching the loop start again. The
compiler uses it a lot: about 15,000 loops in the main program.

The boot stub has a clear example: copying 1,536 words, one at a time.

```
        setlb                 ; loop starts here
        mov  (a1),d0          ; read a word
        inc4 a1
        mov  d0,(a0)          ; write it
        inc4 a0
        inc  d1
        cmp  1536,d1
        lcs                   ; loop while d1 < 1536
```

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| example loop | 0x60021278, boot stub copy 0xa1483000 → 0x47000800 | [code] |
| `setlb` count | 15,070 | [code] |
| how many bytes the buffer holds, and its timing | not measured | [inferred] |

Sources: [MN103 CPU: by the numbers](../hardware/mn103-cpu.md#what-block0s-code-looks-like-by-the-numbers-2026-11-19),
[boot and sections](../firmware/boot-and-sections.md#what-the-boot-stub-does-2026-11-19).
</details>

## 6. Maths

The core has multiply and divide instructions, but the firmware mostly multiplies through a helper unit Panasonic calls
the **UDF** ("user-defined function") unit, using instructions named `udf00`, `udfu01` and so on. There are about
19,000 UDF multiplies against a few hundred native ones. Divides use the core's own `div` and `divu`.

There is no floating-point unit in the core. Floating point is done by UDF operations (add, subtract, multiply,
divide, compare, convert) and by small helper functions. The decoding of the float operations comes from the
third-party om-emu emulator rather than from our own tests.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| `udf00` / `udfu01` as 32-bit multiply | 11,114 / 7,529 uses | [inferred], corroborated by om-emu |
| `div` / `divu` | 9,898 / 3,466 | [code] |
| float UDF operations (udf02-udf06, udf14, udf15) | om-emu's description | [code, third-party] |
| float helpers on the stabiliser path | u2f 0x600e2350, fmul 0x600e225f, f2u 0x600e21de | [code] |

Sources: [MN103 CPU: UDF operations](../hardware/mn103-cpu.md#udf-operations-the-maths-helper-unit).
</details>

## 7. The address space

Addresses are 32 bits, little-endian. These are the main points for reading code.

**The program runs from RAM at 0x6xxxxxxx.** Flash sits at 0x4xxxxxxx. The boot stub copies what's needed into RAM
and the rest loads in the background ([boot](boot.md)).

**Two views of the same RAM.** 0x6xxxxxxx is the cached view and 0xaxxxxxxx the uncached view of the same memory.
The CPU uses the cached addresses. Buffers shared with the image engine or other cores are usually reached through
the uncached ones.

**A small memory at 0x47000000.** The boot stack starts at 0x470007fc, and the boot stub copies 6 KB of code to
0x47000800, which includes memcpy, memset and the watchdog kick. What kind of memory it is hasn't been confirmed.

**Low addresses are control registers.** For example 0x8050 holds the number of the core that reads it, and 0x8000 to
0x801c are set at boot to what look like the interrupt handler addresses.

**Image buffers live high**, at 0xb0000000 and above.

**Misaligned access traps.** A 32-bit read from an address that isn't a multiple of 4 (or 16-bit from an odd
address) is reported to trap on the real chip (seen on a PEN-F, not yet tested on the E-M5 III). Simulators built on the GNU simulator don't check this, so a bug of this kind can
pass simulation and still crash the camera.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| cached / uncached alias | 0x61a92e40 = 0xa1a92e40 | [camera] |
| 0x47000000 memory | sp 0x470007fc; copy to 0x47000800; memcpy 0x47001024, memset 0x47001130, watchdog kick 0x4700101b | [code]; memory type [inferred] |
| core number | (0x8050) | [code] |
| misaligned access traps | PEN-F patch lesson from oly_fw_analysis | [inferred] for the E-M5 III |

Sources: [memory map](../hardware/memory-map.md), [MN103 CPU: address aliases](../hardware/mn103-cpu.md#address-aliases-cached-and-uncached),
[gotchas](../reference/gotchas.md).
</details>

## 8. The compiler

Olympus built the main program with Panasonic's own compiler family (cc103), in a C++ variant, not with GCC. The
evidence is in the code: GCC's MN10300 port passes arguments in d0 and d1 whatever their type, while this firmware
puts pointers in a0 and a1. The call-site frames also need Panasonic's linker. The C++ has plain virtual tables with no
run-time type information or exceptions, which fits Embedded C++, the cut-down C++ dialect common in Japanese embedded
work at the time.

This matters for the decompile. Our rebuild uses GCC modified to follow the Olympus convention, and each
function it produces either matches the original byte for byte or is checked to behave the same.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| not GCC | argument passing by type, call-site frames | [code] + [inferred] |
| 820 `.cpp` and 257 `.c` file names | strings | [code] |
| closest public compiler | cc103S 5.4 (DebugFactory Builder 5); the C++ compiler Olympus used isn't public | [inferred] |

Sources: [MN103 CPU: which compiler](../hardware/mn103-cpu.md#which-compiler-built-the-firmware-research-2026-11-08).
</details>

## Patching notes

- **Copy the call frame.** To call a firmware function, copy `[regs],N` from an existing call to that same function.
  A guess corrupts the stack.
- **Keep (0,sp) free.** A call writes its return address there. Locals start at (4,sp).
- **Save mdr in gates.** A wrapper that makes its own calls overwrites mdr, so a `retf` later in the chain would return
  to the wrong place.
- **Plain MN10300 only.** Our compiler is told not to use AM33 instructions, since stock code never does and nobody
  knows whether the core runs them.
- **Align data.** Keep 32-bit values on 4-byte boundaries.

The full list is in [patching techniques](../firmware/patching-techniques.md).

## Other cameras

Each step checked against the firmware of other bodies. Nothing is assumed. "Not checked" means we don't know.

| step | E-M5 III 1.7 | OM-5 1.2 | E-M1 III 1.6 | OM-5 II 1.1 | OM-1 | PEN-F | other projects |
|---|---|---|---|---|---|---|---|
| MN103 / AM33-2 instruction set | yes | **confirmed** | **confirmed** | **confirmed** | **confirmed** (OM-1 and OM-1 II) | **confirmed** | PEN-F, E-P7: same CPU |
| main program at 0x60021020 | yes | **confirmed** | **confirmed** | **confirmed** | **confirmed** | **confirmed** | — |
| no AM33-only instructions in stock code | yes | not checked | not checked | not checked | not checked | not checked | — |
| pointer arguments in a0/a1 (Panasonic convention) | yes | not checked | not checked | not checked | not checked | not checked | — |
| 6 KB helper block copied to 0x47000800 | yes | not checked | not checked | not checked | not checked | not checked | — |
| misaligned access traps | not tested | not checked | not checked | not checked | not checked | reported | oly_fw_analysis (PEN-F) |

Sources: [MN103 CPU](../hardware/mn103-cpu.md), Atlas-linked projects,
oly_fw_analysis notes.
