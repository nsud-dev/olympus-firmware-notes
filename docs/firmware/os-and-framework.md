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

What the binary shows of it (2026-11-19, strings in E-M5 III 1.7 block0): [code]

- Header paths `base_framework/include/rhapsody/oxf/OMUList.h`, `omulist.h` and `itronos.h` (~290 assert strings, from
  inlined list templates), and the runtime sources `omreactive.cpp` and `omthread.cpp`.
- OXF's reactive-object pool limit messages: "overflow in OMREactive too many active" / "underflow in OMREactive".
- Rhapsody's generated state-entry naming (`<state>_entdef`, e.g. `CmpPCom_PlayCommonComponent::draw_folder_frames_entdef`)
  and the Observer and Factory classes it is often used with (~300 `*Observer` strings).
- The shooting sequencer itself (state table 0x6044f9e4, `takepic.c`) is **plain C**, not Rhapsody. [code]

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

### Kernel objects, the static task table and the Oly* layer (2026-11-19)

- **μITRON 4.0 objects.** The system shell's `od` (object dump) command accepts `tsk stk sem flg dtq mbx mtx cnd mbf mpf
  mpl cyc alm` (tasks, stacks, semaphores, event flags, data queues, mailboxes, mutexes, condition variables, message
  buffers, fixed and variable memory pools, cyclic handlers, alarm handlers), each also with a `1` or `2` suffix for
  CPU1 and CPU2 (strings at 0x600771c4). `oserr` prints the error-code legend at 0x61443c20; its codes (E_RLWAI −49,
  E_DLT −51, E_CLS −52, E_WBLK −57, E_NOID −34, ...) are the μITRON 4.0 set. `chgpri` changes a task's priority. [code]
- **Static task table (CPU0)** at **0x60038b68**: 28-byte records {entry, priority, stack bytes, word, u16 field, 0, 0},
  144 records (0-143) then a zero record. **Task id N uses record N**: checked with the ids stage 0/1 pass to
  `OlyTaStCpu` 0x6005185f (25 → 0x600741c0 PER_WDT, 142 → 0x6019c924 Tsk_USHL, 143 → 0x6005f871). The +16 field is
  mostly N+1 but not always (record 143 holds 0), so it is not the id; meaning unknown. Record 0 (entry 0x60101ac6,
  +12 = 0x62078f40, +20 = 2) differs from the rest. [code]
- Priorities 1-66 (lower number = more urgent, the μITRON rule [inferred]): 82 tasks at 55, 28 at 25, 8 at 53; record 1
  (0x60052147) runs at 1 and record 139 (0x6005365e) at 15. Stacks are 1-4 KB (40 tasks at 4 KB), 0x67e88 bytes
  (~416 KB) in all. The sequencer task 0x602a0f90 is record 117, priority 25, 4 KB stack. [code]
- **Ids carry the CPU** (id = cpu<<12 | index, see the task table route below): stage 1 starts ids 4120 and 8213, i.e.
  task 24 on CPU1 and task 21 on CPU2. Where the CPU1/CPU2 task tables live is open. [code]
- **The Oly* layer** (names from strings, each with a `...Cpu` variant that takes a CPU-qualified id): tasks
  `OlyTaSt/Sp/Wu/Dl` (start, suspend?, wake up, delete), semaphores `OlySmWt/Si/Dl` (wait, signal), event flags
  `OlyEvSt/Wt/Cl/Dl` (set, wait, clear), queues `OlyQeRd/Wr/Dl` (read, write). Identified in symbols: OlyEvStCpu
  0x60051078, OlyEvWtCpu 0x60051143, OlyEvClCpu 0x6005123a, OlyQeRdCpu 0x600513d2, OlyQeWrCpu 0x600514a2, OlySmWtCpu
  0x60051679, OlySmSiCpu 0x6005174e, OlyTaStCpu 0x6005185f. Meanings of the two-letter verbs are from the names. [inferred]
- **Two task loops, as examples.** The sequencer task 0x602a0f90 waits forever on an event flag (`OlyEvWtCpu`, flag id
  u16 at 0x60040dc0, wait pattern 0x62107750), and when bit 0 is set takes its pending event (0x60227f32) and runs the
  handler for the current state (state 0x62107744, 20-byte records from 0x6044f9e4). The watchdog task 0x600741c0
  blocks on a queue (`OlyQeRdCpu`, queue id u16 at 0x60040f9e). [code]
- **Same layout on other bodies** (2026-11-19, scan of block0 for the record pattern): task table at 0x60038b68 on OM-5
  1.2, E-M1 III 1.6 and OM-5 II 1.1; 0x600396d0 on PEN-F 3.1; block0 offset 0x180b0 on OM-1 1.9. The μITRON error legend
  and the `od` object list are in all six. [code]

Source: disassembly of E-M5 III 1.7 block0.

## Source-file and module names

Trace and error calls pass Olympus's own source file names, such as `iseq_nd_main.c`, `iseq_ndlv.c`, `stb_seq_flash.c`,
`take_lv_comp_mem.c`, `api_firmup.c`, `mvr_if_buff.c`, `CapThr_ThroughImage.cpp` and `sd_asic.c`. Our symbols tool
groups functions into modules using them. [code]

- **Live-view object CapThr_ThroughImage** (2026-11-18, naming pilot): a 0x2a0-byte singleton (`getInstance` 0x608ca1b8,
  pointer at 0x61e9cda0) run as a state machine: state word 0x61e9cd1c (`entryStateAll` 0x608cbdbb logs
  `[CapThr] (all) entryState[0x%08x]` (spaces added), values 0x01010100..0x02030203), exec bits 0x61e9cd10 (1 start, 2 stop, 0x10 update,
  4/8 pause/restart wait), trace flag 0x61e9cd14 (==1 enables `[CapThr]` logs). Triggers (Start, ThrPause, RestartDone,
  StartError, StartBufferingOperation, UpdateThrough) dispatch on the state through {state, handler} tables at
  0x60b30808-0x60b30f38. The Highlight&Shadow blink settings for rec view and live view live at object +0x190..+0x1ce
  (setters 0x608ccc05 / 0x608ccd97, field names from their log strings). [code]

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
network with the user shell on port 23; a battery pull was sometimes needed. It works on an E-M5 III 1.7 (2026-11-12) and we use it to trace
Live ND runs (`take dbgmode 1`). [camera] Their PEN-F audit says the
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

