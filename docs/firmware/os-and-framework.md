# Operating system and framework: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Operating system](../guides/operating-system.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

This page describes the software layers the main program is built on. They are the real-time operating system, the
framework that generates most of the camera's state machines, the tasks that run, how parts of the program send each
other events, and the built-in debug consoles. Knowing these makes the disassembly much easier to read, because a lot
of the code follows these patterns.

Terms used here:

- **RTOS**: a real-time operating system, here μITRON, a Japanese standard common in cameras and appliances.
- **Task**: a unit of work scheduled by the RTOS. The camera has dozens, each with a short name such as FCS (focus) or
  STB_SEQ.
- **Property**: a numbered value in the camera's settings store (drive mode, ISO, a debug switch and so on).
- **Interrupt context**: code running inside a hardware interrupt, which must not wait for anything.

Addresses are E-M5 III 1.7 block0 addresses (base `0x60021020`) unless a body is named. They are listed in the
[Address reference](#address-reference).

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred.

## The operating system: μITRON

The MN103 runs μITRON. The firmware uses its standard calls (`cre_tsk`, `acre_tsk`, `twai_sem`), has a "uITRON Error
Code" table and an `itronos.cpp` layer.[^fw2]

Olympus wraps it in its own API (`OlySemaphoreWait`, `OlyQueueWrite` and so on), and most code calls that.[^fw1] The
ARM also has a small μITRON image ("load arm itron") alongside Linux.[^fw1]

## The framework: Rhapsody OXF

On top of μITRON sits the Object Execution Framework (OXF) of IBM Rhapsody (`rhapsody/oxf/itronos.h`). Rhapsody is a
UML tool that generates C++ state machines from diagrams. That explains why the shooting states and component code look
so regular.[^fw1]

The binary shows these parts of it in the strings of the E-M5 III 1.7 block0.[^fw4]

- Header paths `base_framework/include/rhapsody/oxf/OMUList.h`, `omulist.h` and `itronos.h`. They appear in about 290
  assert strings, from inlined list templates. The runtime sources `omreactive.cpp` and `omthread.cpp` also appear.
- OXF's limit messages for the reactive-object pool, "overflow in OMREactive too many active" and "underflow in
  OMREactive".
- Rhapsody's generated state-entry naming, `<state>_entdef`, for example
  `CmpPCom_PlayCommonComponent::draw_folder_frames_entdef`.
- The Observer and Factory classes it is often used with, in about 300 `*Observer` strings.
- The shooting sequencer itself (its state table, `takepic.c`) is plain C, not Rhapsody.[^fw4]

### Naming patterns

These names recur through the code.[^fw1]

- Components start with `Cmp` (CmpPli and CmpPls for playback, CmpSqp for sequence parts, CmpShc, CmpCCom).
- GUI classes are named `*_Viewer`, `*_Actuator`, `Menu_*`, `SubApp*` and `userGui*`.
- `OlyApiShooting` is the shooting API object. Its GND methods are stubs on the OM-5 II.[^fw1]
- **Class tree.** About 225 classes descend from OXF's `OMReactive` through `Com_TransitionBase` and a linear layer
  chain, camera → mode → category → component → capability (`Lyb_*LayerBase`).[^fw5] The shooting component, the
  sequence parts and the take-picture route to the sequencer are on [C++ shooting layer](cpp-shooting-layer-technical.md).

### Older bodies

The PEN-F 3.1 and E-M5 II 4.1 have the same μITRON and OXF stack (`itronos`, `rhapsody/oxf`, `omreactive`).[^fw3]
The E-M5 (Mark I) 2.3 has μITRON but no OXF.[^fw3] It has an older `ntos.cpp` layer and only 76 C++ source names,
against about 820 on the E-M5 III. The `OlyApi*`, `SubApp*` and `Cmp*` naming already exists there.[^fw3]

See also: [Older bodies](../bodies/comparison-technical.md#older-bodies-e-m5-ii-and-e-m5-mark-i).

## Tasks

Some examples of tasks follow.[^fw1]

- STB_SEQ, the strobe and flash sequencer.[^fix1] See [Exposure](exposure-technical.md#flash-metering-is-separate).
- TAKE_EXPOSE, DSP0 and DSP1, MVR_* (movie), ZOOM_MAIN, UI_OUT, FCS (focus).
- TSK_FACE_FD and TSK_FACE_MAIN, REC_*, PC3 and PC4 (USB), ISEQ_* (image sequencer), LENS_FLASH, FILECLBK.
- FIRMUP_CLI (the SD card updater).
- TSK_CA9PWR_MNGR, a CPU1 task (`SYS_CA9_PWR_MNG`, `0x101c`).[^fw5]
- TPC_CAMC_MAIN and TPC_CAMC_FADD (USB camera control).

Boot creates them in stages. See also: [Boot and sections](boot-and-sections.md).

## Kernel objects and the static task table

### Kernel objects

The kernel objects are the μITRON 4.0 set.[^fw4]

- The system shell's `od` (object dump) command accepts `tsk stk sem flg dtq mbx mtx cnd mbf mpf mpl cyc alm`. These are
  tasks, stacks, semaphores, event flags, data queues, mailboxes, mutexes, condition variables, message buffers, fixed
  and variable memory pools, cyclic handlers and alarm handlers. Each also takes a `1` or `2` suffix for CPU1 and CPU2.
- `oserr` prints the error-code legend. Its codes (E_RLWAI −49, E_DLT −51, E_CLS −52, E_WBLK −57, E_NOID −34 and
  others) are the μITRON 4.0 set.
- `chgpri` changes a task's priority.

### The CPU0 task table

The static task table for CPU0 holds 28-byte records, 144 of them (0 to 143), then a zero record.[^fw4] Each record
starts with its u16 task id.[^fix2] Read from the entry field of record 0, the table is a run of 28-byte steps of
{entry, priority, stack bytes, word, u16 field, 0, 0}.[^fw4] In that reading the u16 field at +16 is the next record's
id.[^fix2]

- **Task id N uses record N.** This was checked with the ids that stages 0 and 1 pass to `OlyTaStCpu`. Id 25 is
  PER_WDT, id 142 is Tsk_USHL and id 143 is a third task (its entry is in the address reference).[^fw4]
- Record 0 differs from the rest. Its entry and +12 word are in the address reference, and its +20 value is 2.[^fw4]
- Priorities run from 1 to 66. A lower number is more urgent, as μITRON's rule has it.[^inf1] 82 tasks run at 55,
  28 at 25 and 8 at 53. Record 1 runs at 1 and record 139 at 15.[^fw4]
- Stacks are 1 to 4 KB, with 40 tasks at 4 KB. They total `0x67e88` bytes, about 416 KB.[^fw4]
- The sequencer task is record 117, priority 25, with a 4 KB stack.[^fw4]

### CPU ids and the CPU1 and CPU2 tables

Task ids carry the CPU. An id is `cpu << 12 | index` (see [Task table route](#task-table-route)). Stage 1 starts ids
4120 and 8213, that is task 24 on CPU1 and task 21 on CPU2.[^fw4] Task 24 is USRSTART_LOAD_1 and task 21 is
USRSTART_LOAD_2, the section loaders.[^fw5]

CPU1's table holds 73 tasks and CPU2's holds 29.[^fw5] See also: [CPU1 and CPU2](../hardware/cpu1-cpu2-technical.md),
which has the full tables.

### The Oly* layer

The Oly* names come from strings. Each has a `...Cpu` variant that takes a CPU-qualified id.[^fw4]

- Tasks: `OlyTaSt`, `OlyTaSp`, `OlyTaWu` and `OlyTaDl` (start, suspend?, wake up, delete).
- Semaphores: `OlySmWt`, `OlySmSi` and `OlySmDl` (wait, signal).
- Event flags: `OlyEvSt`, `OlyEvWt`, `OlyEvCl` and `OlyEvDl` (set, wait, clear).
- Queues: `OlyQeRd`, `OlyQeWr` and `OlyQeDl` (read, write).

Eight of the `...Cpu` variants are identified in our symbols: `OlyEvStCpu`, `OlyEvWtCpu`, `OlyEvClCpu`, `OlyQeRdCpu`,
`OlyQeWrCpu`, `OlySmWtCpu`, `OlySmSiCpu` and `OlyTaStCpu`.[^fw4] The meanings of the two-letter verbs are from the
names.[^inf1]

### Two task loops

- The sequencer task waits forever on an event flag (`OlyEvWtCpu`, with a u16 flag id and a wait pattern). When bit 0
  is set, it takes its pending event and runs the handler for the current state. The states are 20-byte
  records.[^fw4]
- The watchdog task blocks on a queue (`OlyQeRdCpu`, with a u16 queue id).[^fw4]

### Task table route

`ps` walks the u16 task-id list at the start of the CPU0 table, which ends with a 0. For each id it calls the task
query (d0 = id, a0 = out).[^fw10]

1. The query takes the per-CPU kernel object from a shared word array, indexed by 4 × the CPU number.
2. It splits the id as id = `cpu << 12 | index`.
3. The record is `*(*(kobj + 204) + 4 × (index − 1))`.
4. It copies out record +12 (the u16 state), +20 (a byte) and +8 (a u16).

The kernel-object words sit in a block shared by all CPUs. The block also holds a lock word and the UART state used
by putc. Native code reads the base of the kernel-object words at 330 places.[^fw10] The card console's admitted
ranges exclude the block, so its dumps can't reach the task records yet.[^fw10]

### Task tables on other bodies

A scan of block0 for the record pattern finds the same task table layout on other bodies.[^fw6] The places are in the
address reference. The μITRON error legend and the `od` object list are in all six bodies scanned.[^fw6]

## Source-file and module names

Trace and error calls pass Olympus's own source file names, such as `iseq_nd_main.c`, `iseq_ndlv.c`,
`stb_seq_flash.c`, `take_lv_comp_mem.c`, `api_firmup.c`, `mvr_if_buff.c`, `CapThr_ThroughImage.cpp` and `sd_asic.c`.
Our symbols tool uses them to group functions into modules.[^fw1]

### The live-view object CapThr_ThroughImage

`CapThr_ThroughImage` is a `0x2a0`-byte singleton, with a `getInstance` function and a pointer word. It runs as a state
machine.[^fw7]

- **State word.** `entryStateAll` logs `[CapThr] (all) entryState[0x%08x]` (spaces added). The values run from
  `0x01010100` to `0x02030203`.
- **Exec bits.** 1 = start, 2 = stop, `0x10` = update, 4 and 8 = pause and restart wait.
- **Trace flag.** A value of 1 enables the `[CapThr]` logs.
- **Triggers.** Start, ThrPause, RestartDone, StartError, StartBufferingOperation and UpdateThrough dispatch on the
  state through {state, handler} tables.
- **Highlight and shadow blink.** The Highlight&Shadow blink settings for rec view and live view live at object
  +`0x190` to +`0x1ce`. There are two setters. The field names come from their log strings.[^fw7]

### The iseq function-id table

The iseq function-id table of the E-M1 III is made of {u32 id, char *name} pairs. Reading it as {name, id} shifts
everything by one.[^fw1] The E-M5 III's {name, id} table holds `iseq_nd_*` names.[^fw1]

## Messages, events and locks

- Shooting events are (event, handler) pairs in a table. Examples are events 63, 65 and 85.[^fw1] See
  [Shooting sequencer](shooting-sequencer.md).
- Properties have a get function and an address function. The drive mode is property 3265, read through its own
  function.[^fw1]
- Some completions run in interrupt context, the StlUhs frame completion for example. No file I/O or locks
  there.[^cam1]

## Debug consoles

The MN103 has a debug console. Its commands include `usb tpc ...`, `arm ...`, `fcs seq set2 6` (the handheld HR debug
flag) and `help dbg` (in block 3).[^fw1] The [Wi-Fi debug shell](../features/wifi-debug-shell.md) below is one way to
reach it on a retail camera.

### Two shells

There are two shells, both in the static task tables.[^fw2]

- The **system shell `S_SHELL`** is always ready and reads the serial port (UART). Its line executor (a0 = line)
  splits up to 4 words and calls the dispatcher (d0 = argc, a0 = argv). The commands include mdump, mem_get and
  mem_put, od, ps, arm and isc.[^fw2]
- The **user shell `Tsk_USHL`** sits in section 1. It reads lines from a message buffer with a u16 id. Its line
  executor (a0 = line) uses a 58-command table (lens, take, fcs, iseq, file, prm, usb and others). Many of the handlers
  are in sections 4 to 10.[^fw2]

### Capturing console output

Console text from `puts` can be copied ("teed") into a 16 KB buffer, which has open, read and close functions. It can
also go into an 8 KB log when property 63873 is non-zero.[^fw2] The stock `dbgterm` writer saves that log as
`C:\dbgterm\<time>.txt`. No stock code reads console commands from the card.[^fw2]

### Shell output and the console log

We looked at whether the output of shell commands could be read back through the 8 KB console log. Mostly it
can't.[^fw10]

- `ps` rows are printed by a row function that calls the tee writer and then sends the characters straight to the
  UART through putc. The 8 KB console log is fed only by `puts`, so it never sees them.[^fw10]
- `puts` advances the log's write index before copying the bytes. So a reader can't tell when a line is
  complete.[^fw10]
- The `od` variants write a shared init byte. The listing of `heaplist` is a "NotSupport" stub. `oserr` prints a fixed
  uITRON error legend, not a log.[^fw10]
- All of them busy-wait on the UART with no time-out.[^fw10]

### Console over USB

The `tpc` Picture Transfer Protocol (PTP) responder has two operations for the console. `0x94b5` runs a console line
and `0x94b6` reads its output. Both are gated on that responder's session flag.[^fw2] Which USB mode exposes them is
unchecked, because USB work is parked.

### Wi-Fi shell from a card file

A stock card file can switch on a Wi-Fi shell.[^fw8]

1. The parameter importer reads `PARAMDT/CP??????.CSV` as RAM overrides.
2. A line `Wifi shell,0xF971,1,1` sets property 63857 (`0xf971`).
3. A function reads that property through the property getter. If it is non-zero, the function waits for
   readiness 7 and calls the Wi-Fi request.
4. It then reads property 63873 (the 8 KB log switch above) and `0x7b64` bit 31.

An external report says that on an E-M5 III 1.7 this brings up an open Wi-Fi network with the user shell on port
23.[^inf3] It works on our E-M5 III 1.7, and we use it to trace Live ND runs (`take dbgmode 1`).[^cam2]

> [!WARNING]
> The report says a battery pull was sometimes needed.[^inf3]

The same project's PEN-F audit says the shell's `flash` dump can remap flash blocks. So the shell is not
read-only.[^inf1] The full page is [Wi-Fi debug shell](../features/wifi-debug-shell.md).

### Other projects

The external caduceus-ep7 project (E-P7) documents a non-maskable interrupt (NMI) monitor and bootloop behaviour. It
is not checked on the E-M5 III.[^inf1]

## Debug serial port

### The port and its set-up

The system shell and every `putc` use one UART.[^fw9] putc busy-waits on the status register and writes the byte to the
data register. It picks the port through a pointer table, indexed by a shared word that is set to 0.[^fw9]

The block0 stub sets the port up in its first step, before any section is copied. The set-up function is called from
the stub's start and leaves the trace marks `RCS` and `RCE`.[^fw9] It writes these registers, listed with their values
in the [address reference](#serial-port-set-up).

- Two registers of the block that holds interrupt registers. Their role is unknown.[^fw9]
- Two pads, set to `0x01000001`. These are the `siodbg` pins (see below).[^fw9]
- Four UART registers. One is set to `0xc083`, likely the baud divisor.[^fw9]

The OM-5 1.2 stub does the same writes with the same values.[^fw9]

### What is not known

- The baud rate is unknown, because the UART clock is not known. Measuring it needs a scope or a logic analyser on the
  pin.[^inf2]
- Nothing in block0 polls this port for a command during boot. Its input is read only by the shell task, after the OS
  is up.[^fw9] Whether the boot-area loader in flash listens is unknown until the flash dump is read.[^fw9]
- Where the pins come out on the board is not documented anywhere we found.[^inf2] We looked at the iFixit E-M10 II
  board guide, hidden-menu pages and an E-100RS service manual. That manual used a serial cable on the camera's USB
  port and jumpered test pads.

### Moving the port to other pins

The system shell can move the port to other pins.[^fw9]

- `am shell sd3` sets two pads to `0x01030101`, sets a route register to 1 and prints "siodbg setting sd3".
- `am shell siodbg` sets the two `siodbg` pads to `0x01000001`, as at boot.

The `sd3` pads are SD channel 3 of the SD pad routine. Channel 0 is the card slot[^inf2] and channel 2 is Wi-Fi.[^fw9]
So the main console can go to channel 3's data 0 and data 1 pins, not to the card slot.[^fw9] What channel 3 is wired
to on this body is unknown. A second slot on two-slot bodies or a factory connector are guesses.[^inf2]

### The ARM side's ports

The same `arm` command routes the ARM's serial ports and its JTAG.[^fw9] The pads and route registers of each are in
the [address reference](#arm-port-routes).

- Likely `arm start1` or `arm shell siodbg` puts ARM uart0 on the `siodbg` pins.
- `arm shell sd3c` puts ARM uart1 on channel 3 ("set sd3clk+cmd").
- `arm shell sd3d` puts ARM uart0 on channel 3.
- `arm shell sd0` puts ARM uart1 on channel 0, the card slot ("sd0clk+cmd").
- `arm jtag` routes five pads of channel 0, the card slot.

So the card slot can carry the ARM's serial port and its JTAG.[^fw9] Five pins fit TCK, TMS, TDI, TDO and
TRST.[^inf2] No route puts the main processor's console or a JTAG for it there.[^fw9] All of these need the main
program running and a shell command, so none helps a start that fails early.[^fw9][^inf2]

### Use

A serial tap would show the boot trace marks and the NMI register dumps of a start that fails before the Wi-Fi shell is
up. It would not by itself be a way to rewrite the flash.[^inf2]

## Address reference

E-M5 III 1.7 addresses unless a body is named. Functions are block0 addresses (base `0x60021020`).

### Framework and tasks

| item | address |
|---|---|
| shooting sequencer state table (`takepic.c`), 20-byte records | `0x6044f9e4` |
| `OlyApiShooting` (OM-5 II) | `0x608f0a26`, vtable `0x60bb6cc4` |
| `od` object-list strings | `0x600771c4` |
| `oserr` error-code legend | `0x61443c20` |
| CPU0 static task table, from the u16 id | `0x60038b5c` |
| CPU0 static task table, first reading (entry field of record 0) | `0x60038b68` |
| CPU1 static task table (73 tasks) | `0x6003c460` |
| CPU2 static task table (29 tasks) | `0x6003d544` |
| record 0 entry, +12 word | `0x60101ac6`, `0x62078f40` |
| record 1 entry (priority 1) | `0x60052147` |
| record 139 entry (priority 15) | `0x6005365e` |
| record 143 entry | `0x6005f871` |

*Framework objects and task tables.*

| item | address |
|---|---|
| `OlyEvStCpu` | `0x60051078` |
| `OlyEvWtCpu` | `0x60051143` |
| `OlyEvClCpu` | `0x6005123a` |
| `OlyQeRdCpu` | `0x600513d2` |
| `OlyQeWrCpu` | `0x600514a2` |
| `OlySmWtCpu` | `0x60051679` |
| `OlySmSiCpu` | `0x6005174e` |
| `OlyTaStCpu` | `0x6005185f` |

*Oly* layer functions.*

| item | address |
|---|---|
| sequencer task (record 117) | `0x602a0f90` |
| its event flag id (u16), wait pattern | `0x60040dc0`, `0x62107750` |
| its pending-event function | `0x60227f32` |
| its current state | `0x62107744` |
| watchdog task PER_WDT (record 25) | `0x600741c0` |
| its queue id (u16) | `0x60040f9e` |
| user shell task Tsk_USHL (record 142) | `0x6019c924` |

*The two task loops.*

| item | address |
|---|---|
| `ps` | `0x6005991e` |
| task id list | `0x60038b5c` |
| task query | `0x60034bab` |
| per-CPU kernel object | `0x8ff00004 + 4 × (0x8050)` |
| CPU number | `0x8050` |
| block shared by all CPUs | `0x8ff00000`-`0x8ff000bc` |
| kernel-object base, read at 330 places | `0x8ff00004` |
| lock word | `0x8ff00000` |
| UART state used by putc | `0x8ff0005c` |

*Task table route.*

| body | task table |
|---|---|
| OM-5 1.2, E-M1 III 1.6, OM-5 II 1.1 | `0x60038b68` |
| PEN-F 3.1 | `0x600396d0` |
| OM-1 1.9 | block0 offset `0x180b0` |

*The same record pattern on other bodies, found by scanning each block0.[^fw6]*

### Source names, events and properties

| item | address |
|---|---|
| `CapThr_ThroughImage::getInstance` | `0x608ca1b8` |
| its instance pointer | `0x61e9cda0` |
| state word | `0x61e9cd1c` |
| `entryStateAll` | `0x608cbdbb` |
| exec bits | `0x61e9cd10` |
| trace flag | `0x61e9cd14` |
| {state, handler} trigger tables | `0x60b30808`-`0x60b30f38` |
| Highlight&Shadow blink setters | `0x608ccc05`, `0x608ccd97` |
| iseq function-id table (E-M1 III) | about `0x6078d608` |
| iseq {name, id} table (E-M5 III) | `0x6073dbd0` |
| shooting event table | `0x6044e8a4` |
| event 63, 65, 85 handlers | `0x602b4f16`, `0x602b5062`, `0x602b50e4` |
| property get, property address | `0x6005ce6b`, `0x6005ce41` |
| drive mode (property 3265) read | `0x602c5159` |

*Source names, events and properties.[^fw1][^fw7]*

### Consoles

| item | address |
|---|---|
| `usb tpc` command | `0x60c30320` |
| system shell `S_SHELL` task | `0x600570bd` |
| its line executor (a0 = line) | `0x60056e5f` |
| its dispatcher (d0 = argc, a0 = argv) | `0x60055d99` |
| user shell message buffer id (u16) | `0x600410cc` |
| user shell line executor (a0 = line) | `0x6019c8d8` |
| user shell 58-command table | `0x601fbe38` |
| `puts` | `0x60023042` |
| 16 KB tee buffer open, read, close | `0x6010189a`, `0x601018c6`, `0x60101932` |
| 8 KB console log | `0xa264deb0` |
| `dbgterm` writer | `0x6010194d` |
| `ps` row printer, and the function it calls | `0x60055947` → `0x60056f8f` |
| tee writer | `0x60022f61` |
| UART send from the row printer | `0x60056f5e` |
| `od` shared init byte, written at | `0x61f26468`, `0x6005627e` |
| UART busy-wait loop | `0x6002144a`-`0x60021459` |
| PTP vendor operation session flag | `0x62358c58` |
| `PARAMDT/CP??????.CSV` strings | `0x6073e6c8` |
| Wi-Fi shell property reader | `0x6005bafb` |
| readiness wait (readiness 7) | `0x60045d92` |
| Wi-Fi request | `0x6122e9b6`, `0x6122e9f6` |
| E-P7 NMI monitor (caduceus-ep7) | `0x99700000` |

*Console functions and data.*

### Serial port

| item | address |
|---|---|
| UART | `0x98700000` |
| putc | `0x60021436` |
| status register | `0x9870001c` |
| data register | `0x98700018` |
| port pointer table | `0x60024298` |
| port index (shared word, set to 0) | `0x8ff0005c` |
| port set-up function | `0x600213a9` |
| called from | `0x60021145` |
| OM-5 1.2 set-up function | `0x6002139c` |
| boot-area loader | flash `0x40000000` |
| SD pad routine | `0x6064acab` |
| SD channel 0 pads (card slot) | `0x9b80174c`-`0x9b8017f0` |
| SD channel 3 pads | `0x9b801bd0`-`0x9b801c70` |
| `am shell sd3` | `0x600569a7` |
| `am shell siodbg` | `0x600569e8` |
| `arm` command | `0x60059000`-`0x60059420` |

*Serial port functions and pads.*

#### Serial port set-up

| register | value |
|---|---:|
| `0x98800150` | 8 |
| `0x98800158` | `0x80` |
| `0x9b801990`, `0x9b8019b0` (`siodbg` pads) | `0x01000001` |
| `0x98700004` | 25 |
| `0x98700000` | 3 |
| `0x98700040` (likely the baud divisor) | `0xc083` |
| `0x98700020` | 8 |

*Writes of the block0 stub's port set-up, in order. The `0x988001xx` block holds interrupt registers.[^fw9]*

| command | pads written | value | route register |
|---|---|---|---|
| `am shell sd3` | `0x9b801c10`, `0x9b801c30` (channel 3) | `0x01030101` | `0x9b802030` = 1 |
| `am shell siodbg` | `0x9b801990`, `0x9b8019b0` | `0x01000001` | |

*Main console pad routes.[^fw9]*

#### ARM port routes

| command | pads written | route register |
|---|---|---|
| likely `arm start1` / `arm shell siodbg` (`0x60059142`, ARM uart0 on the siodbg pins) | `0x9b801990`, `0x9b8019b0` | `0x9b802020` |
| `arm shell sd3c` (ARM uart1, "set sd3clk+cmd") | `0x9b801bd0`, `0x9b801bf0` (channel 3) | `0x9b802024` |
| `arm shell sd3d` (ARM uart0) | `0x9b801c10`, `0x9b801c30` (channel 3) | `0x9b802020` |
| `arm shell sd0` (ARM uart1 on "sd0clk+cmd") | `0x9b801750`, `0x9b801770` (channel 0, card slot) | `0x9b802024` |
| `arm jtag` | `0x9b801750`-`0x9b8017d0`, five pads (channel 0, card slot) | `0x9b80202c` |

*ARM serial and JTAG routes of the `arm` command.[^fw9]*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware.
[^fw2]: Read in the firmware, 2026-11-05.
[^fw3]: Read in the firmware, 2026-11-21.
[^fw4]: Read in the firmware, 2026-11-19. Strings and disassembly of the E-M5 III 1.7 block0.
[^fw5]: Read in the firmware, 2026-11-25.
[^fw6]: Read in the firmware, 2026-11-19, by scanning block0 of each body for the record pattern.
[^fw7]: Read in the firmware, 2026-11-18, in a naming pilot.
[^fw8]: Read in the firmware, 2026-11-11.
[^fw9]: Read in the firmware, 2026-11-23. Block0 listings of stock E-M5 III 1.7 and OM-5 1.2.
[^fw10]: Read in the firmware, 2026-11-06.
[^cam1]: Seen on our E-M5 III.
[^cam2]: Seen on our E-M5 III, 2026-11-12.
[^inf1]: Inferred, not traced or tested.
[^inf2]: Inferred, not traced or tested, 2026-11-23.
[^inf3]: Reported in fishcu's oly_fw_analysis project and in a forum post by enduity, on an E-M5 III 1.7, 2026-11-01.
[^fix1]: Corrected 2026-11-25. See [History](#history).
[^fix2]: Corrected 2026-11-25. The older reading is in [History](#history).

## History

- STB_SEQ was first read as the standby sequencer. It is the strobe and flash sequencer. Corrected 2026-11-25.
- 2026-11-19: the CPU0 task table was read as starting at the entry field, with the u16 field at +16 "mostly N+1 but
  not always (record 143 holds 0), so it is not the id, meaning unknown". Each record starts with its u16 id, and that
  field is the next record's id. Corrected 2026-11-25.
- 2026-11-19: where the CPU1 and CPU2 task tables live was open. Found 2026-11-25.
- When the debug console was first described, how to reach it on a retail camera was unknown. The Wi-Fi debug shell,
  found 2026-11-11, is one way.

