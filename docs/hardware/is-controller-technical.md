# Image-stabiliser controller: technical notes

> **Technical notes.** This page is the dense reference. For a readable introduction, start with [Stabiliser controller](is-controller.md).

The program of the IS controller (block 3, "LUKE", block kind 0x10e) read end to end on 2026-11-23: memory layout, the
two cores, the maths extension ops, the I/O blocks, the command path from the main processor, and the OM-5 differences.
How the main program drives the stabiliser is on [Image stabiliser: technical notes](stabiliser-technical.md).

Tags: **[code]** read in the program, **[inferred]** not traced to the end. Addresses are core 0 addresses (LUKE file
offset + 0x40002400) unless core 1 is named. E-M5 III 1.7 unless the OM-5 1.2 is named.

## Disassembling it

- Use `mn10300-elf-objdump -b binary -m mn10300 --adjust-vma=0x40002400 --start-address=0x40009000`. **Plain
  `mn10300`, not `am33-2`**: LUKE's extension ops share encodings with AM33 instructions, so `-m am33-2` shows
  `fadd`, `mcst48` and similar ops LUKE never uses. This corrects an earlier note. [code] 2026-11-23
- File offset 0x400 is address 0x40002800 (load address in the header at file 0x3e0: `OE 13 70`, load 0x40002800, size
  0x35800, kind 0x0e). The OM-5's header says `OE 14 40`. [code] 2026-11-23

## Layout

| range | what | where it runs |
|---|---|---|
| 0x40002800 | magic 0x12345678, then 0xff up to 0x40009000 | |
| 0x40009000-0x4000fb74 | shared library (maths helpers, `memcpy` 0x4000acdf, spinlocks, mailboxes) | core 0 in place, and copied to core 1 at the same address |
| 0x4000fb74-0x40023424 | core 0 code and read-only data | core 0 in place |
| 0x40023424-0x400235e4 | core 1 initial data | core 1 RAM 0xa74 |
| 0x400235e4-0x40023701 | core 1 vectors and reset code | core 1 0x40000000 |
| 0x40023701-0x4002b95d | core 1 program | core 1 0x40000120 (3 bytes later than contiguous) |
| 0x4002b95d-0x4002bb29 | core 0 initial data | core 0 RAM 0 |

[code] 2026-11-23, copy plan in core 0's start-up task 0x4001826c (copy helper 0x400183cc).

- The boot program below 0x40002800 is not in the update file. The update commands 0xf0-0xf4 have no handler in LUKE,
  so the boot program most likely serves them. [inferred] 2026-11-23
- Factory parameters sit above the program in the controller's flash. Command 0x89 ("read parameter from flash",
  numbers 18-211, switch 0x40010760) reads words such as 0x4003f42c. [code] 2026-11-23

## Two cores

- **Core number:** each core reads the half-word at 0x8050 (0 = core 0). [code] 2026-11-23
- **Memory per core:** RAM from 0 (stack top 0x7ffc). Vector registers at 0x8000-0x801c hold the low half-words of the
  vectors, base 0x40000000. The same register addresses as the main processor's boot stub. [code] 2026-11-23
- **Core 1 start:** core 0 copies core 1's pieces through 0x10000000 (core 1 RAM) and 0x10010000 (core 1 program
  memory), then starts its kernel (0x4001898c). Core 1's reset at its 0x40000000 jumps to 0x40000090: stack, a
  0xdeadbeef fill of 0x7800-0x7fff, kernel start, then a loop on its message queue. [code]; that the two windows are core
  1's memory is [inferred] 2026-11-23
- **Kernel:** µITRON style (`snd_dtq`, `rcv_dtq`, `get_mem`, `set_flg`, `wai_flg`, `dis_dsp`, `ena_dsp`), like the main
  program's. Core 0 tasks (table 0x40023090): `task_cmd` 0x40012a6f, `task_comm` 0x400144ba, `task_detect` 0x40014808,
  start-up 0x4001826c, shell 0x40018947. Core 1 runs `task_drive`. [code] 2026-11-23
- **Division of work:** core 0 talks to the main processor, decodes commands and reads the gyros and accelerometer
  (`task_detect`). Core 1 runs the servo filters and drives the coils (`task_drive`). [code] for the code each core
  holds, [inferred] for the roles.
- **Debug shells:** one per core (`Usr0`, `Usr1`) with `mdump4 <addr> <size>`, `mput <addr> <value>`, `per`
  (adc, timer8, timer16), `stack`, `nmi`, `tcmd`, `tdet`, `tdrv`, `dbg <block> on|off`, `dbglog`. Most likely on a UART
  that only a service jig reaches. [code] for the commands, [inferred] for the access.

### How the cores talk

| address | what |
|---|---|
| 0x98000000-0x98000006 | hardware semaphores, 4 half-word registers with 8 lock bits each. Take 0x4000b4a2 (spins), give 0x4000b4ed |
| 0x99000000-0x990007ff | shared RAM. 0x99000000-0x14a is a 40-field block core 1 copies in and out. 0x99000400 + 256 × n: 3 mailbox slots (busy bytes 0x9900015c-15e). 0x99000700 + 64 × n: 4 small slots (busy bytes 0x9900015f-162). 0x99000164/168: one word per core. 0x990007f0/7f4: read by the NMI report |
| 0x9c080000, 0x9c090000 | doorbells. Core 0 writes 1 to 0x9c080000, core 1 writes 1 to 0x9c090000 (0x4000b5c6) |

[code] for the accesses, [inferred] for the names. 2026-11-23

## Same chip or separate

The IS controller is a **separate chip**, not more cores inside the main SoC. [code]+[inferred] 2026-11-23

- The main program reaches it only through `bc_sio`, a serial link with reset, chip-select, ready and request lines
  (see [Image stabiliser: technical notes](stabiliser-technical.md)).
- LUKE runs from its own flash at 0x40002800, which the main program writes over that link during an update. The main
  SoC's own boot area also sits at 0x40000000 and holds different code. [code]
- LUKE never touches main-SoC DRAM (0x6xxxxxxx, 0xa-0xf), the main CPUs' doorbells (0x99200400 and nearby) or the ISC.
  Its 0x98/0x99/0x9c blocks are its own. [code]
- LUKE calls the main chip the "ASIC" (`rs_data_num_2_asic`).

So the main SoC has three MN103 cores (CPU0-CPU2) and the camera has **five** MN103-family cores across two chips. The
power and watchdog block is not a processor (see [Power and watchdog block](power-block.md)).

## Rates and the servo loop

[code] 2026-11-23, rates from the timer reloads at 50 ticks per µs.

| what | core | timer | period | handler |
|---|---|---|---|---|
| kernel tick | 0 | 16-bit ch 0 | 50000 ticks = 1 ms | 0x400183bf |
| gyro / detection tick | 0 | 16-bit ch 2 | 12500 ticks = 250 µs (4 kHz). Set in the detect init 0x4001df0c, which also enables IRQ 21 (0x4001dfee) | 0x4001dfc3 |
| servo loop | 1 | 16-bit ch 1 | 2083 ticks ≈ 41.7 µs (about 24 kHz). Set up at core 1 0x400053e5 (create 0x40009a22, start 0x40009ac2, stop 0x40009b44) | core 1 0x40000abc |

One servo step (core 1): 0x40000abc reads the three ADC positions, 0x40000ff6 runs the filters (0x4000243a,
0x40003c32, 0x400001c7, 0x40000c37) and 0x40005192 writes the three coil duty registers.

- **Interrupts:** the dispatcher 0x4000a4f5 reads the IRQ number at 0x8a00 and calls the handler from a RAM table at
  0xabc + 8 × n. Register 0x4000a3e4, enable 0x4000a46e, disable 0x4000a4a9. Known IRQs: 19 link, 21 detection, 34-39
  16-bit timers. [code] 2026-11-23

## The gyro

- SPI channel 1 (0x9c020000). Register write 0x4001e1da(reg, value), read 0x4001e201(reg | 0x80). [code] 2026-11-23
- Start-up writes 6 (or 2) to registers 0x22, 0x42 and 0x62 and checks that they read back 6 (0x4001e230), and writes 5
  to 0x0b. Three identical register blocks 0x20 apart suggest one control block per axis. [code]; the chip is not
  identified [open].

## The drives (constant speed and rotation)

Core 1 moves the servo target through a "trajectory hook": `0x40000a3c(step_fn, done_fn)` stores both at core 1
0x1074/0x1078, sets 0x107c and starts the servo timer if it is stopped. The servo loop then asks the hook for each
axis's target. Axes are 0, 1, 2. [code] 2026-11-23

- **Constant speed (wire 0x73, message 9).** Handler core 1 0x400005f2 → 0x400042c6 stores axis and speed, 0x400042d3
  starts it through 0x40003ea9. Speed is a signed 16-bit number. Its sign picks the direction (0x1e5c) and its size is
  kept at 0x1e5a. The start position and centre of each axis are snapshotted. Step function 0x40003f2f:
  `target = start ± speed × t / 800`, where `t` (0x1e70) is a step counter. The move stops at the axis limit
  `centre ± stroke` (stroke table 0x1e80) and sets a done flag (0x1e78). So units are sensor position counts per 800
  steps per unit of speed. The step's wall-clock rate is not pinned yet. [code]; units [inferred]
- **Rotation (wire 0x77, message 21).** Handler core 1 0x400004be → 0x40005dd2 stores a signed 16-bit amount,
  0x40005ddc starts it through 0x40005c8c. That estimates the current roll angle from the three axis positions
  (0x40009079), adds the amount, and converts the new angle to three axis targets with 0x40009000. The converter uses
  small-angle maths (θ and θ²) and fixed geometry constants (18301, 1536, 1920, 1408, 3000). Step function 0x40005d22
  moves along a half-cosine (S-curve) profile: the phase runs 0 → 16384 over counter values 0-161 and 16384 → 32768
  over 162-321 (`× 13026 >> 7`, sine helper 0x4000ab85), then holds the final targets (0x24f8). The relative amount is
  therefore an angle. 18301/32768 equals π/180 × 32, which fits an amount in fixed-point degrees, but the exact unit
  is [inferred]. After the move core 1 sends message 20 back with the three positions (0x400008a2). [code]

Both drives are relative to where the sensor is now, both clamp to the mechanical range, and neither takes a target in
sky coordinates. A star-tracking feature would have to send a stream of constant-speed or rotation commands from the
main processor. [inferred] 2026-11-23

## Maths extension ops

LUKE uses MN10300 `udf` (user-defined function) instructions, which run on an extension unit next to each core. The
main program's block0 does not use them. Counts are from a linear disassembly. [code] for counts and uses, [inferred]
for the meanings. 2026-11-23

| op | core 0 | core 1 | meaning, from how it is used |
|---|---|---|---|
| `udf00` | 115 | 27 | signed multiply (Q15 pattern: `x * 18301`, then the rounding shift 0x4000aacc) |
| `udfu01` | 281 | 21 | unsigned multiply (array strides) |
| `udf02` | 53 | 18 | signed divide |
| `udf03` | 10 | 8 | unsigned divide (`100000000 / f - 1` for timer reloads) |
| `udf35` | 5 | 594 | multiply into the unit's product register |
| `udf06` | 5 | 623 | add the product, shifted right by the operand, to the destination |
| `udf14 n` / `f9 e8 nn` | 6 | 30 | read / write unit register n. The interrupt entry 0x40021102 saves registers 0-3, 22 and 23 |
| `udf09`, `udf33` | few | 21 / 15 | used with registers 22/23 in core 1's filters |

Core 1's servo code is long chains of `udf35` + `udf06` pairs over coefficient tables, which is how its IIR filters are
written.

## I/O blocks

[code] for which core and function uses each block, [inferred] for the names unless a string names them. 2026-11-23

| block | core | what |
|---|---|---|
| 0x9c000000 | 0 | serial port for the accelerometer (`accel read error!!`, 0x40017a69 / 0x40017c2c). A register read sends the address with bit 7 set. Corrects the earlier "accelerometer and gyro" label |
| 0x9c010000 | 0 | SPI/serial channel 0: the link to the main processor (`ms_comm`, IRQ 19, handlers 0x40015953 / 0x40015be8) |
| 0x9c020000 | 0 | SPI/serial channel 1: the gyro. Channel table 0x40020c28 (80 B per channel), transfers 0x40016ffd / 0x40017267. Corrects the earlier "8-bit timers" label. The shell's `per adc` and `per timer8` handlers (0x4000a10a, 0x40016b71) are stubs |
| 0x9c030000 | 0 | set up once at start, likely the debug UART |
| 0x9c050000 | 0, 1 | 16-bit timers, 6 channels at +0x20 × n (+0 control, +8 period, +0x10/+0x14 count), IRQs 34-39. 50 ticks per µs: the delay helper 0x400052f6 loads µs × 50 − 1 into channel 5 |
| 0x9c060000 | 0, 1 | ADC. Core 1's servo interrupt reads 0x9c060038/3c/40 (most likely the three hall position sensors). Command 0x0a "HW status" returns 0x9c060024/28 |
| 0x9c070000 | 0 | I/O port bits (sensor chip selects, link lines). The gyro chip select is 0x9c070004 bit 1 for phase 3 or more, 0x9c070001 bit 0 below (0x4001e2ba) |
| 0x9c0c0000, 0x9c0d0000, 0x9c100000, 0x9c110000 | 1 | four identical timer/PWM channels: +0x20 duty, +0x24 period, +0x2c control. Three duty registers are written together at the end of each servo step (core 1 0x40005192), likely the Y, X1 and X2 coils. Init 0x40004ec2 |
| 0x9c040000, 0x9c0a0000, 0x9c0b0000, 0x9c0f1020 | 0, 1 | not identified |

## Command path

1. The main processor sends a packet. Its first byte is the **wire command**. The main program's table (E-M5 III
   0x601b6598, 58 entries of 16 bytes: u16 wire, u16 type, encoder, aux, decoder) maps each `bc` id to it: id = table
   index + 1. [code] 2026-11-23
2. `task_comm` receives it. It answers wire 0xa0 itself, from a 4-entry queue of 44-byte replies (0x40014661). The rest
   goes to `task_cmd`. [code] 2026-11-23
3. `task_cmd` (0x40012c82) indexes a 248-entry handler table (0x4001ee70) with the wire byte. 49 wire codes have a
   handler. The others hit the default 0x40014365, a bare `retf`, so LUKE does nothing and sends no reply. [code] 2026-11-23
4. Drive and IS handlers become internal messages to core 1, whose `task_drive` has a 22-entry message table (core 1
   0x40005e14). Examples: constant-speed drive 0x73 → message 9 (axis, speed), rotation 0x77 → message 21, prototype
   phase 0x02 → message 22 (core 1 keeps its own copy at its 0x5c8), IS parameters 0x40-0x43 → messages 15-18. [code] 2026-11-23

Wire groups: 0x01-0x0a set-up and status, 0x10-0x12 detection and mode, 0x20-0x27 drives and IS start/stop, 0x30-0x36
state reads, 0x40-0x43 parameters, 0x70-0x77 test drives, 0x80-0x8c parameters, memory, zero tables and flash reads,
0xf0-0xf9 update and adjustment.

**Commands LUKE ignores.** [code] 2026-11-23

| wire | `bc` id | what | note |
|---|---|---|---|
| 0x22 | 11 | drive to a target position (x, y, roll) | encoded by the main program, no handler in either body's LUKE |
| 0x36 | 23 | level gauge / horizontal correction state | E-M5 III host only, no handler in either LUKE |
| 0xf0-0xf4 | 50-54 | firmware update | most likely the boot program's [inferred] |

So the target-position drive the 2026-11-06 notes listed for star tracking cannot work with this LUKE. The
constant-speed drive (0x73, id 31) and the rotation drive (0x77, id 35) do have handlers. [code]+[inferred] 2026-11-23

## The prototype phase

The main program sends a phase with command 0x02: 4 when the board byte 0x8ff0019c is 7 or more, otherwise the byte
itself. Core 0 keeps it at 0x5c8 and forwards it to core 1. Core 1 loads different filter coefficient tables
(120-byte blocks) when the phase is 2 or more (core 1 0x40000ee8). [code] 2026-11-23

## E-M5 III vs OM-5

- Same layout, kernel, tasks, shared library address and handler table. The 49 handled wire codes use the same handler
  addresses in both. [code] 2026-11-23
- Core 0 is the same apart from the prototype-phase branches the OM-5 dropped (for example the 0x9c070001 port set-up at
  0x4001e3c3). [code] 2026-11-23
- Core 1: the OM-5's is 4 KB smaller (ends at 0x400073cc against 0x4000837c) and has 230 fewer multiply pairs. The two
  large E-M5 III-only stretches an earlier compare found (core 1 0x400019ca and 0x4000243a) are filter code. The
  second rescales coefficient tables by gains at core 1 0x1e34-0x1e3c and runs only for phase 2 or more with flag
  0x126f set. They are **not** handlers of commands 22 and 23, which corrects an earlier guess.
  [code]+[inferred] 2026-11-23
- Main program: the OM-5 host table has no wire 0x36 and keeps 0x35 (ICT log state). So `bc` ids match through 22, and
  from 23 up the OM-5's are one lower. This refines the 2026-11-06 "above 18" note, which came from the `bc com` parser.
  [code] 2026-11-23

## Open

- [open] The link framing on SPI channel 0 (0x9c010000). The block is settled (2026-11-23), the packet format is not.
- [open] The wall-clock rate of the drive step counters, and the exact unit of the rotation amount.
- [open] Names of the 22 core 1 message types and of 0x9c040000, 0x9c0a0000, 0x9c0b0000.
- [open] Proof that 0x9c0c0000-0x9c110000 drive the coils and that 0x9c060038-40 are the hall sensors. The servo step
  reads the one and writes the other, so both are likely.
- [open] The gyro chip.
- [open] The boot program, which the update file does not carry.
