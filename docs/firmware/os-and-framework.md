# OS and software framework (MN103 side)

This page describes the software layers the main program is built on: the real-time operating system, the framework
that generates most of the camera's state machines, the tasks that run, how parts of the program send each other
events, and the built-in debug consoles. Knowing these makes the disassembly much easier to read, because a lot of the
code follows these patterns.

Terms used here:

- **RTOS**: a real-time operating system, here μITRON, a Japanese standard common in cameras and appliances.
- **Task**: a unit of work scheduled by the RTOS. The camera has dozens, each with a short name such as FCS (focus) or STB_SEQ.
- **Property**: a numbered value in the camera's settings store (drive mode, ISO, a debug switch...).
- **Interrupt context**: code running inside a hardware interrupt, which must not wait for anything.

Tags: **[code]** read in the firmware, **[camera]** seen on a real E-M5 III, **[inferred]** not traced or tested.

## The operating system: μITRON

The MN103 runs **μITRON**. The firmware uses its standard calls (`cre_tsk`, `acre_tsk`, `twai_sem`), has a "uITRON
Error Code" table and an `itronos.cpp` layer. [code] (2026-11-05)

Olympus wraps it in its own API (`OlySemaphoreWait`, `OlyQueueWrite`, ...), and most code calls that. [code] The ARM also
has a small μITRON image ("load arm itron") alongside Linux. [code]

## The framework: Rhapsody OXF

On top of μITRON sits **IBM Rhapsody's OXF** framework (`rhapsody/oxf/itronos.h`). Rhapsody is a UML tool that
generates C++ state machines from diagrams, which explains why the shooting states and component code look so regular.
[code]

Naming patterns you'll see: [code]

- Components start with `Cmp` (CmpPli/CmpPls playback, CmpSqp sequence parts, CmpShc, CmpCCom).
- GUI classes are named `*_Viewer`, `*_Actuator`, `Menu_*`, `SubApp*`, and `userGui*`.
- `OlyApiShooting` (OM-5 II 0x608f0a26, vtable 0x60bb6cc4) is the shooting API object; its GND methods are stubs on the
  OM-5 II. [code]

## Tasks

Some examples: STB_SEQ (standby sequencer), TAKE_EXPOSE, DSP0/DSP1, MVR_* (movie), ZOOM_MAIN, UI_OUT, FCS (focus),
TSK_FACE_FD/MAIN, REC_*, PC3/PC4 (USB), ISEQ_* (image sequencer), LENS_FLASH, FILECLBK, FIRMUP_CLI (SD updater),
TSK_CA9PWR_MNGR, TPC_CAMC_MAIN/FADD (USB camera control). Boot creates them in stages ([boot](boot-and-sections.md)).
[code]

## Source-file and module names

Trace and error calls pass Olympus's own source file names, such as `iseq_nd_main.c`, `iseq_ndlv.c`, `stb_seq_flash.c`,
`take_lv_comp_mem.c`, `api_firmup.c`, `mvr_if_buff.c`, `CapThr_ThroughImage.cpp` and `sd_asic.c`. Our symbols tool
groups functions into modules using them. [code]

- The iseq function-id table ~0x6078d608 (E-M1 III) is made of **{u32 id, char *name}** pairs (reading it as {name,id}
  shifts everything by one). The E-M5's {name,id} table at 0x6073dbd0 holds `iseq_nd_*` names. [code]

## Messages, events and locks

- Shooting events are (event, handler) pairs in a table starting at 0x6044e8a4 (for example ev63 0x602b4f16, ev65
  0x602b5062, ev85 0x602b50e4). Details: [shooting sequencer](shooting-sequencer.md). [code]
- Properties: get 0x6005ce6b, address 0x6005ce41; the drive mode is property 3265, via 0x602c5159. [code]
- Some completions run in **interrupt context** (the StlUhs frame completion, for example): no file I/O or locks there.
  [camera]

## Debug consoles

The MN103 has a debug console with commands such as `usb tpc ...` (0x60c30320), `arm ...`, `fcs seq set2 6` (the
handheld HR debug flag) and `help dbg` (in block 3). How to reach it on a retail camera was unknown when this was
written; the [Wi-Fi debug shell](../features/wifi-debug-shell.md) below is one way. [code]

**There are two shells** (2026-11-05), both in the static task tables: [code]

- The **system shell `S_SHELL`** (task 0x600570bd, always ready) reads the serial port (UART). Its line executor
  **0x60056e5f(a0 = line)** splits up to 4 words and calls the dispatcher **0x60055d99(d0 = argc, a0 = argv)** (mdump,
  mem_get/put, od, ps, arm, isc, ...). [code]
- The **user shell `Tsk_USHL`** (0x6019c924, section 1) reads lines from a message buffer (id u16 at 0x600410cc). Its
  line executor **0x6019c8d8(a0 = line)** uses the 58-command table at **0x601fbe38** (lens, take, fcs, iseq, file, prm,
  usb, ...; many handlers are in sections 4-10). [code]

**Capturing console output** (2026-11-05): console text (`puts` 0x60023042) can be copied ("teed") into a 16 KB buffer
(open 0x6010189a, read 0x601018c6, close 0x60101932) and into an 8 KB log at 0xa264deb0 when property 63873 is non-zero.
The stock `dbgterm` writer 0x6010194d saves that log as `C:\dbgterm\<time>.txt`. No stock code reads console commands
from the card. [code]

**Over USB** (2026-11-05): the `tpc` PTP responder has operations **0x94B5** (run a console line) and **0x94B6** (read
its output), gated on that responder's session flag 0x62358c58. Which USB mode exposes it is unchecked (USB work is
parked). [code]

**A stock card-file switch for a Wi-Fi shell** (2026-11-11): the parameter importer reads `PARAMDT/CP??????.CSV`
(strings 0x6073e6c8) as RAM overrides, and a line `Wifi shell,0xF971,1,1` sets property 63857 (0xF971). 0x6005bafb
reads it via 0x6005ce6b and, if non-zero, waits for readiness 7 (0x60045d92) and calls 0x6122e9b6 / 0x6122e9f6 (the
Wi-Fi request); it then reads 63873 (the 8 KB log switch above) and 0x7B64 bit 31. [code] An external report
(fishcu/oly_fw_analysis, enduity on forum, 2026-11-01) says that on an E-M5 III 1.7 this brings up an **open** Wi-Fi
network with the user shell on port 23; a battery pull was sometimes needed. Not tried by us. Their PEN-F audit says the
shell's `flash` dump can remap flash blocks, so the shell is not read-only. [inferred] Full page: [Wi-Fi debug shell](../features/wifi-debug-shell.md).


The external caduceus-ep7 project (E-P7) documents a 0x99700000 NMI monitor and bootloop behaviour; not checked on the
E-M5 III. [inferred]


### Why shell output can't simply be captured from the console log (audit, 2026-11-06) [code]

We looked at whether shell commands' output could be read back through the 8 KB console log. Mostly it can't:

- `ps` rows are printed by 0x60055947 → 0x60056f8f, which calls the tee writer 0x60022f61 and then sends characters
  straight to the UART (0x60056f5e → putc 0x60021436). The 8 KB console log (fed only by `puts` 0x60023042) never sees
  them. [code]
- `puts` advances the log's write index before copying the bytes, so a reader can't tell when a line is complete.
- `od` variants write a shared init byte 0x61f26468 (at 0x6005627e); `heaplist`'s listing is a "NotSupport" stub;
  `oserr` prints a fixed uITRON error legend, not a log. All of them busy-wait on the UART with no timeout
  (0x6002144a-0x60021459). [code]

**The task table route** (2026-11-06) [code]: `ps` 0x6005991e walks the u16 task-id list at **0x60038b5c**
(0-terminated) and calls the task query **0x60034bab**(d0 = id, a0 = out). The query takes the per-CPU kernel object
from **0x8ff00004 + 4 × (0x8050)** (the CPU number is at 0x8050); id = cpu<<12 | index; record =
*(*(kobj+204) + 4×(index−1)); record +12 u16 state, +20 byte, +8 u16 copied out. 0x8ff00000-0x8ff000bc is a block shared
by all CPUs (lock word 0x8ff00000, UART state 0x8ff0005c used by putc); native code reads 0x8ff00004 at 330 places.
The card console's admitted ranges exclude it, so its dumps can't reach the task records yet.

