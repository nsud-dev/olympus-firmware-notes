# The MN103 operating system

*Guide 3 · E-M5 III firmware 1.7 · draft 1, 2026-11-19. New to these guides? Read
[Before you start](before-you-start.md) first. Open questions: research gaps.*

This guide explains what the main program runs on: the μITRON real-time operating system, the thin Olympus layer over
it, the tasks it schedules, and how those tasks pass work to each other. It ends with the generated-code framework on
top (Rhapsody OXF), the fact that each control core runs its own copy of the kernel, and the debug commands that let
you look at all of this on a running camera.

Most of the structure is clear from the code. The scheduler's own details (time slicing, the idle task, how interrupts
are entered) are not traced yet.

## 1. Overview

μITRON is a Japanese specification for small real-time kernels, written by the TRON project and used in a great many
cameras, printers and appliances. It is a specification, not one product: each vendor writes or licenses its own
kernel to it. Which kernel Olympus used isn't known; its error codes match version 4.0 of the specification.

A μITRON kernel offers a fixed menu of **objects**, and the camera has all the usual ones:

- **Tasks**: threads with a fixed priority and their own stack.
- **Semaphores** and **mutexes**: counting locks and ownership locks.
- **Event flags**: a word of bits a task can wait on ("wake me when bit 0 or bit 3 is set").
- **Data queues**, **mailboxes** and **message buffers**: three ways to hand data from one task to another.
- **Memory pools**: fixed-size and variable-size blocks a task can borrow and return.
- **Cyclic handlers** and **alarm handlers**: short functions the kernel calls on a period or once after a delay.

Every object has a small number, its **id**, and system calls name objects by id (`wai_sem(5)`: wait on semaphore 5).
Calls that can be made from an interrupt handler have their own `i`-prefixed versions (`iloc_cpu` instead of
`loc_cpu`). The usual style is to create the objects once at start-up from a configuration table, which is what this
firmware does for its tasks (section 3).

Scheduling is pre-emptive by priority: the highest-priority task that is ready runs, and it keeps the processor until it
waits for something or a more urgent task becomes ready. In μITRON a **lower number means more urgent**.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| object types (`od` command list: tsk stk sem flg dtq mbx mtx cnd mbf mpf mpl cyc alm, plus `1`/`2` per CPU) | strings 0x600771c4 | [code] |
| μITRON 4.0 error legend (E_RLWAI, E_DLT, E_CLS, E_WBLK, ...), printed by `oserr` | 0x61443c20 | [code] |
| kernel call names in error messages (`wai_sem`, `sig_sem`, `tslp_tsk`, `act_tsk`, `get_tim`, `loc_cpu`/`iloc_cpu`) | strings | [code] |
| lower number = more urgent | μITRON rule, not traced in this kernel | [inferred] |

Sources: [OS and framework](../firmware/os-and-framework.md#kernel-objects-the-static-task-table-and-the-oly-layer-2026-11-19).
</details>

## 2. Olympus's layer

Application code rarely calls the kernel directly. Olympus wrapped it in a small API whose names are two-letter
abbreviations: `OlyTaSt` (task start), `OlySmWt` and `OlySmSi` (semaphore wait and signal), `OlyEvSt`, `OlyEvWt` and
`OlyEvCl` (event flag set, wait and clear), `OlyQeRd` and `OlyQeWr` (queue read and write), and a `Dl` (delete) for
each. Each has a `...Cpu` version that takes an id which also says which core the object belongs to (section 7).

The ids themselves are kept as 16-bit constants in one block of the program, so a call usually looks like "load
the id from a fixed address, then call `OlyEvWtCpu`". That makes the ids easy to follow in the disassembly: two pieces
of code that load the same constant are talking to the same object.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| `OlyEvStCpu` / `OlyEvWtCpu` / `OlyEvClCpu` | 0x60051078 / 0x60051143 / 0x6005123a | [code] |
| `OlyQeRdCpu` / `OlyQeWrCpu` | 0x600513d2 / 0x600514a2 | [code] |
| `OlySmWtCpu` / `OlySmSiCpu` | 0x60051679 / 0x6005174e | [code] |
| `OlyTaStCpu` | 0x6005185f | [code] |
| meanings of the two-letter verbs | from the names | [inferred] |
| object ids (u16 constants) | around 0x60040b00-0x60041300, e.g. 0x60040dc0, 0x60040f9e | [code] |

Sources: [OS and framework](../firmware/os-and-framework.md#kernel-objects-the-static-task-table-and-the-oly-layer-2026-11-19),
[useful routines](../hardware/mn103-cpu.md).
</details>

## 3. Tasks: a table built into the program

The tasks for the main core are not created one by one in code. They are listed in a table compiled into the program,
one 28-byte record per task: the function the task runs, its priority, and its stack size. There are 144 of them. Task
id N is simply record N, so starting a task is "start id 25" and the kernel finds the rest in the table. Start-up
(see [boot](boot.md#4-the-operating-system-and-the-first-tasks)) walks through its stages starting tasks by id.

Some things the table shows:

- **Priorities cluster.** Most tasks (82) run at priority 55, a large group (28) at 25, and a few elsewhere between 1
  and 66. The shooting sequencer runs at 25, so it can interrupt the many ordinary tasks at 55. Two tasks run far above
  everything else (priorities 1 and 15); what they do isn't identified yet.
- **Stacks are small.** 1 to 4 KB each, about 416 KB for all 144. Code that runs on a task's stack (a patch's hook, for
  instance) has little room to spare.
- **Names live elsewhere.** The table has no names. Names such as PER_WDT, STB_SEQ or FCS come from log strings printed
  next to the code that starts the task, which is how most of the task names on the reference pages were found.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| static task table (main core) | 0x60038b68, 28-byte records {entry, priority, stack, word, u16, 0, 0}, 144 records then zero | [code] |
| id N = record N | checked: 25 → 0x600741c0 (PER_WDT), 142 → 0x6019c924 (Tsk_USHL), 143 → 0x6005f871 | [code] |
| record +16 | mostly N+1, not the id; meaning unknown | [code] |
| sequencer task | 0x602a0f90, record 117, priority 25, 4 KB | [code] |
| system shell task S_SHELL | 0x600570bd, record 141, priority 65, 4 KB | [code] |
| priority 1 and 15 tasks | 0x60052147 (record 1), 0x6005365e (record 139) | [code] |
| total stack | 0x67e88 bytes | [code] |

Sources: [OS and framework](../firmware/os-and-framework.md#kernel-objects-the-static-task-table-and-the-oly-layer-2026-11-19).
</details>

## 4. How a task spends its life

Almost every task has the same shape: a loop that waits for something, handles it, and waits again. While it waits, it
uses no processor time. This is what makes a camera with 144 tasks practical: at any moment nearly all of them are
blocked on a queue, a flag or a semaphore.

Two examples from the main core:

The **watchdog task** (PER_WDT) blocks reading a queue, and kicks the watchdog every 3 seconds.

The **shooting sequencer** waits on an event flag. Other parts of the camera set a bit in that flag when they have an
event for it (a button half-pressed, a frame finished). The sequencer then takes the event and hands it to the
handler for its current state:

```
pseudocode, written from the disassembly (0x602a0f90; byte-matching C waits for the decompile), simplified

sequencer_task:
    loop forever:
        wait on the sequencer's event flag, no timeout
        if the "event pending" bit is set:
            take the pending event
            find the record for the current state in the state table
            run that state's handler for this event
```

This one pattern, "wait on a flag or queue, then dispatch by state", covers a large part of the firmware. The
[sequencer's state tables](../firmware/shooting-sequencer.md) are one instance; the generated components in section 6
are another.

If a handler gets an event its state has no entry for, the sequencer logs it and prints a history of recent events
(this is how our Live ND work found its missing handlers; see the end section).

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| sequencer wait | `OlyEvWtCpu` at 0x602a0fc4, flag id u16 at 0x60040dc0, wait pattern 0x62107750, timeout −1 | [code] |
| take pending event | 0x60227f32 | [code] |
| state table / current state | 0x6044f9e4 (20-byte records) / 0x62107744 | [code] |
| watchdog task wait | `OlyQeRdCpu`, queue id u16 at 0x60040f9e | [code] |
| watchdog kick period | 3 s | [code] |

Sources: [OS and framework](../firmware/os-and-framework.md#kernel-objects-the-static-task-table-and-the-oly-layer-2026-11-19),
[shooting sequencer](../firmware/shooting-sequencer.md), [recovery](../firmware/recovery.md).
</details>

## 5. Interrupts: the other context

Code runs in one of two contexts. **Task context** is ordinary code on a task's stack: it may wait, take locks and call
anything. **Interrupt context** is code run by a hardware interrupt, borrowing whatever was running at the time. It
must finish quickly and must never wait, because nothing else on that core can run until it returns. That rules out
semaphores, file access and anything that might block.

The usual way out is to do the minimum in the interrupt (note what happened, set an event flag bit or post to a
queue with the `i`-prefixed calls) and let a task do the real work. The camera follows this widely. A few completion
routines do more than that inside the interrupt, which matters when you hook them: the burst-capture frame completion,
for example, runs in interrupt context.

The firmware has a function that tells the two apart (it returns 0 in task context). Native code calls it in 163
places, including inside the Olympus layer, which appears to use it to pick the interrupt-safe kernel call.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| "am I in an interrupt?" check | 0x600386ae, returns 0 in task context; 163 call sites | [code] |
| Olympus layer branching on it | e.g. 0x6005370e (reached from `OlyTaStCpu`) | [code]; purpose [inferred] |
| current task id | 0x600317b4 | [code] |
| interrupt vectors | written to 0x8000-0x801c at boot, handlers 0x60030020-0x60030080 | [code] (see [boot](boot.md#2-the-first-instructions)) |
| burst frame completion runs in an interrupt | StlUhs completion | [camera] |

Sources: [useful routines](../hardware/mn103-cpu.md), [patching techniques](../firmware/patching-techniques.md).
</details>

## 6. Rhapsody OXF on top

Much of the application layer is C++ generated by IBM Rhapsody from state diagrams
([background](rhapsody-and-oxf.md)). That code runs on Rhapsody's small runtime, OXF, and OXF reaches the kernel
through one adapter file, `itronos.h`, which maps its threads, queues and timers onto μITRON objects.

In OXF terms, an **active object** is a task with an event queue, and it owns a number of **reactive objects**, each a
state machine that handles one event at a time. So the generated components follow the same "wait, then dispatch by
state" pattern as the hand-written sequencer, only produced by a tool. `CapThr_ThroughImage` (live view) is a readable
example: a state word, and tables of {state, handler} pairs for each trigger such as Start or Pause.

How exactly a generated active object is laid out once compiled (where its queue is, which task runs it) has not been
traced yet.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| OXF OS adapter | string `base_framework/include/rhapsody/oxf/itronos.h` | [code] |
| reactive-object pool limit | "overflow in OMREactive too many active" | [code] |
| live-view state machine | `CapThr_ThroughImage`, state word 0x61e9cd1c, handler tables 0x60b30808-0x60b30f38 | [code] |

Sources: [OS and framework](../firmware/os-and-framework.md#the-framework-rhapsody-oxf).
</details>

## 7. One kernel per core

The system-on-chip has several MN103 cores, and each runs its own copy of the kernel with its own tasks and objects.
The debug commands show this directly: every object type exists three times, plain for the main core (CPU0) and with a
`1` or `2` suffix for CPU1 and CPU2.

An id says which core it belongs to: the core number sits in the top bits (id = core × 4096 + index). That is why the
API has `...Cpu` versions. During start-up the main core starts tasks 4120 and 8213, which are task 24 on CPU1 and task
21 on CPU2. Each core finds its own kernel data through a small table in memory shared by all cores, indexed by a
word at a fixed low address that holds the core's number.

How the cores pass messages to each other, and to the ARM, is the subject of
[How the cores talk to each other](cores.md). What CPU1 and CPU2
run, and where their task tables are, is still open (research gaps).

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| core number | (0x8050) | [code] |
| per-core kernel object | 0x8ff00004 + 4 × core | [code] |
| shared block (lock word, UART state) | 0x8ff00000-0x8ff000bc | [code] |
| cross-core task starts in stage 1 | ids 4120, 8213 (0x60045894, 0x600458af) | [code] |

Sources: [OS and framework](../firmware/os-and-framework.md#debug-consoles) (task table route).
</details>

## 8. Looking at it on a running camera

The firmware keeps μITRON's debugging aids. The system shell, which reads the serial port, has `ps` (list the tasks
and their states), `od` (dump any kernel object, or all of one type), `oserr` (print the error-code legend) and
`chgpri` (change a task's priority). A second, user-level shell carries most of the camera's own commands. On a retail
camera the user shell is reachable through a stock card-file switch that brings up a Wi-Fi network with the shell on
port 23. We use it on our camera: `take dbgmode 1` streams the sequencer's states and events live to a laptop, which
is how the Live ND runs are traced. A `:` prefix should reach the system shell from there; that part hasn't been
tried.

One catch: `ps` writes its rows straight to the serial port, so its output can't be read back from the console log.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| system shell S_SHELL, command dispatcher | 0x600570bd, 0x60055d99 | [code] |
| `ps` and the task-id list it walks | 0x6005991e, 0x60038b5c | [code] |
| task query | 0x60034bab | [code] |
| user shell Tsk_USHL, 58-command table | 0x6019c924, 0x601fbe38 | [code] |
| Wi-Fi shell switch | `PARAMDT/CP??????.CSV` line `Wifi shell,0xF971,1,1`; camera at 192.168.0.10, port 23 | [code] + [camera] (2026-11-12) |

Sources: [debug consoles](../firmware/os-and-framework.md#debug-consoles), [Wi-Fi debug shell](../features/wifi-debug-shell.md).
</details>

## What this means for our patches

The rules our builds follow (see [patching techniques](../firmware/patching-techniques.md)) come straight from this
picture:

- **Know which context a hook runs in.** A hook in an interrupt-context completion may not take locks or touch files.
  Our hooks check the "am I in an interrupt?" function and the core number before touching native objects.
- **Use the native objects, don't invent new ones.** Patches post to the sequencer the same way native code does, so
  its event tables decide what happens. When Live ND sent the sequencer an event its current state had no entry for,
  the result was the history dump from section 4, which is how the missing handlers were found.
- **Mind the stack.** Tasks have 1-4 KB stacks. Hook code copies the native call frame exactly and keeps its own frame
  small.
- **Don't hold up a fast task.** The sequencer runs at priority 25 above most of the camera; work done in its handlers
  delays everything at 55.

## Checked on other cameras

Each step checked against the firmware of other bodies. Nothing is assumed: "not checked" means we don't know.

| step | E-M5 III 1.7 | OM-5 1.2 | E-M1 III 1.6 | OM-5 II 1.1 | OM-1 1.9 | PEN-F 3.1 | other projects |
|---|---|---|---|---|---|---|---|
| μITRON 4.0 error legend and `od` object list (3 CPUs) | yes | **confirmed** | **confirmed** | **confirmed** | **confirmed** | **confirmed** | — |
| `Oly*Cpu` API names | yes | **confirmed** | **confirmed** | **confirmed** | **confirmed** | **confirmed** | — |
| static task table, 28-byte records | 0x60038b68 | **confirmed** 0x60038b68 | **confirmed** 0x60038b68 | **confirmed** 0x60038b68 | **confirmed** (block0 offset 0x180b0) | **confirmed** 0x600396d0 | — |
| S_SHELL and Tsk_USHL shells | yes (Wi-Fi shell used on camera) | **confirmed** (strings) | **confirmed** (strings) | **confirmed** (strings) | **confirmed** (strings) | **confirmed** (strings) | E-M5 III: Wi-Fi shell reported (oly_fw_analysis) |
| OXF runtime names (`omreactive.cpp`) | yes | not found | not found | not found | **confirmed** | **confirmed** | — |
| sequencer task waits on an event flag | yes | not checked | not checked | not checked | not checked | not checked | — |
| task id N = record N | yes | not checked | not checked | not checked | not checked | not checked | — |

"Not found" means the string search found nothing; the framework may still be there under other strings.
[OS and framework](../firmware/os-and-framework.md#kernel-objects-the-static-task-table-and-the-oly-layer-2026-11-19),
oly_fw_analysis notes.
