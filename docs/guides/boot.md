# Boot

*Guide 2 · E-M5 III firmware 1.7 · draft 1, 2026-11-19. New to these guides? Read
[Before you start](before-you-start.md) first. Open questions: research gaps.*

This guide follows the main program from the moment it gets control until the camera is up: the first instructions,
the copy into RAM, the operating system starting, the first tasks, and the background loading of the rest of the
program. It ends with what can go wrong, because the way this camera boots is the main reason a patch can work most of
the time and still fail now and then.

The early part (first instructions, copies, first tasks, section loading) is mapped from the code. What runs before
the main program, and the last stretch up to the first live-view frame, are not.

## The shape of it

The main program (block 0 of the firmware file, about 24 MB) runs from RAM, not from flash. But it is not copied into
RAM all at once. The boot code copies a small part straight away, starts the operating system from that part, and
leaves the rest to a loader task that brings it in as ten **sections** while the camera is already starting up.
Every later stage waits for the sections it needs.

```
 power on
   │  (a loader we can't see)
   ▼
 entry point ──► boot stub ──► copy the always-ready code and the initialised data
                                   │
                                   ▼
                            start the OS (runs from the always-ready code)
                                   │
                                   ▼
                stage 0: drivers, watchdog, power, battery, buttons
                                   │
                                   ▼
                stage 1: start the loader tasks ──► sections 1, 7, 2, 3, 4, 5, 6, 8, 9, 10
                                   │                    load in the background
                                   ▼
                stages 2-5: wait for each section, start the tasks that live in it
                (sequencer and exposure after section 2; focus, recording, USB after section 4)
                                   │
                                   ▼
                       camera ready; card updater available after section 10
```

## 1. Before the main program

Something runs before the main program and jumps to its entry point in flash. We have never seen that code: it is
either in a boot area at the start of flash, which our firmware files never touch, or in mask ROM inside the chip.
Whether it checks the main program before starting it is unknown.

The main program does not check itself either. Nothing on the boot path verifies a checksum or signature. A read error
while loading is only logged. The checksum in the firmware file is checked only by the updater, before it writes
anything.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| entry point | flash 0x40780020 = VMA 0x60021020 | [code] |
| boot area (never written by our files) | flash 0x40000000-0x40060000 | [code] |
| no self-check on the boot path | boot stub, loader 0x60045e2e | [code] |
| updater checks every component first | validator 0x60c3aa36 | [code] |

Sources: [recovery](../firmware/recovery-technical.md#what-checks-what-at-power-on),
[boot and sections](../firmware/boot-and-sections.md#addresses).
</details>

## 2. The first instructions

The entry point does the minimum to get to C code: it masks interrupts, sets up a couple of CPU registers, points the
interrupt vectors at handlers in the part of the program that is about to be copied, prepares two RAM ranges, sets
the stack pointer into a small block of on-chip memory, and jumps to the boot stub.

Pointing the vectors at code that is not in RAM yet is safe because interrupts stay masked until the copy is done.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| mask interrupts | `and 0xf0ff,psw` at 0x60021020 | [code] |
| vector words | eight half-words to 0x8000-0x801c = low halves of handlers 0x60030020-0x60030080 | [code]; that they are vectors [inferred] |
| RAM set-up | 0x60021486 over 0x61f22900-0x61f27670 and 0x62527100-0x626b0888 | [code]; "clears them" [inferred] |
| stack | sp = 0x470007fc | [code] |

Source: [what the boot stub does](../firmware/boot-and-sections.md#what-the-boot-stub-does-2026-11-19).
</details>

## 3. The boot stub

The boot stub copies everything that every later step depends on from flash into RAM, then starts the operating
system. It runs four steps:

1. **Memory and clock set-up**, by writing hardware registers.
2. **The copy.** Six blocks go from flash to RAM:
   - the **always-ready code**, 642 KB, which holds the operating system, the section loader, the interrupt handlers
     and the start-up stages;
   - four blocks of **initialised data** (global variables with starting values), about 230 KB in total;
   - one small 6 KB block.
3. Two more initialisation steps, whose purpose isn't known yet.
4. **Start the operating system**, by jumping into the code just copied.

From here on the CPU runs from RAM. Everything outside the always-ready code is still only in flash.

The stub prints a short trace mark at the start and end of each step, which is how we can follow it. Each mark is
two letters naming the step plus S (start) or E (end): RCS/RCE, F0S/F0E, GIS/GIE, DSS/DSE, and OIS (the jump to the OS
has no end mark). Olympus doesn't spell out the abbreviations. We matched steps to marks by what the code between them
does: F0 is the copy, and OI is the operating system start. RC, GI and DS are not known yet, so the steps above are
described by what their code touches, not by their names.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| boot stub | 0x600210f9 | [code] |
| trace print | 0x60023bbc | [code] |
| step 1, debug serial port set-up (marks RCS/RCE) | 0x600213a9; registers 0x8ff0005c, 0x988001xx, 0x987000xx | [code] (corrected 2026-11-23: it sets up the debug UART, see os-and-framework) |
| step 2, the copy (marks F0S/F0E) | copy routine 0x60022180 | [code] |
| always-ready code | flash 0x4078f000 → RAM 0xa0030000 (VMA 0x60030000-0x600d0800); length immediate at 0x600211af | [code] |
| initialised data | 0x409af000 → 0xa1e8b540 (0x32d10), 0x409e7000 → 0xa1ec3540 (0x48c4), 0x409ef000 → 0xa1ecb540 (4), 0x409f3000 → 0xa1ecf540 (0x2d2c) | [code]; "initialised data" [inferred] |
| small block | 0x41be2000 → 0xa1483000 (0x1800) | [code] |
| step 3 (marks GIS/GIE, DSS/DSE) | 0x6006783d, 0x600547de | [code]; purpose [open] |
| step 4, OS start (mark OIS) | `jmp` 0x6003009c → 0x60032696 | [code]; "OS start" [inferred] |

Source: [what the boot stub does](../firmware/boot-and-sections.md#what-the-boot-stub-does-2026-11-19).
</details>

## 4. The operating system and the first tasks

The main program runs **μITRON**, a real-time operating system, with Olympus's own layer on top
([OS and framework](../firmware/os-and-framework.md)). Start-up is done in numbered stages. Each prints numbered trace tags as it goes (`0_1`, `0_3`, ... for stage 0,
`1_1`, `1_2`, ... for stage 1), which is how they can be told apart.

**Stage 0** initialises the drivers and debug support, then starts the first tasks. Their names say what they are
for:

- **PER_WDT**, the watchdog keeper. The watchdog itself lives in a small always-on part of the main chip (the [power block](../hardware/power-block.md)) and resets the camera if it
  isn't "kicked" regularly. Boot sets its timeout (the value 10; the unit isn't confirmed) and PER_WDT kicks it every 3 seconds.
- **PER_PCONT**, power control.
- **BCHK_MAIN**, battery check.
- **PER_IN**, the buttons and dials.

**Stage 1** starts the loader tasks (named USTART_L, USTART_L1 and USTART_L2) and then waits for section 1 to be ready
before going on.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| stage 0 | 0x60045103 (tags `0_1` ... `0_v`) | [code] |
| task start call | `OlyTaStCpu` 0x6005185f | [code] |
| watchdog set-up and task | 0x600741b2; PER_WDT task id 25, entry 0x600741c0, kick every 3 s; timeout set to 10 | [code] |
| watchdog hardware | always-on power block (not a sub-CPU, 2026-11-23), 0x98e0008c via 0x600226e1 | [code] |
| stage 1 | 0x60045841 (tags `1_1` ... `1_8`); waits with 0x60045eb3(1) | [code] |
| which task is which loader | ids at 0x60040b68, 0x60041132, 0x60041294 | [inferred] |

Sources: [start-up stages 0 and 1](../firmware/boot-and-sections.md#start-up-stages-0-and-1-2026-11-19),
[recovery](../firmware/recovery-technical.md#what-checks-what-at-power-on).
</details>

## 5. Sections load in the background

The rest of the main program is ten sections, loaded from flash by a loader task in a fixed order: 1, 7, 2, 3, 4, 5, 6,
8, 9, 10. For each section the loader copies it into RAM, sets up memory and cache for it, and then sets the section's
**ready bit**. Code that needs a section waits on that bit.

While a section is still loading, the loader also programs a hardware access monitor over the address range of the
sections not yet loaded, and turns it off after the last one. What exactly it traps isn't known, but it is one more
reason never to touch a later section before it is ready.

Each section ends in a stretch of unused space (0xFF bytes) up to the next one. That slack is where our own code goes:
raising a section's end value in the loader table makes the loader copy our code along with the section.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| loader | `boot_ram_section_loader` 0x60045e2e; table 0x600272a4; end switch 0x60045dc5 | [code] |
| loader task | entry 0x60045513 (tags `M_0`, `M_e`, `M_*`) | [code] |
| ready / loaded bits | 0xa26565c0 / 0xa26565c4; section n is bit n-1 | [code] |
| wait for a section / test it | 0x60045eb3(n) / 0x60045d92(n) | [code] |
| access monitor | 0x99700040.., driver 0x60065a6a, built at 0x60045f0c..0x60045f40, off at 0x60065f63 | [code] |
| section ranges | table on the reference page | [code] |

Source: [sections load in the background](../firmware/boot-and-sections.md#sections-load-in-the-background).
</details>

## 6. Stages 2 to 5: the camera comes up

Code in section 1 continues the start-up in stages 2 to 5. Each stage waits for the sections it needs and then starts
the tasks whose code lives there:

1. When section 2 is ready: the shooting sequencer (STB_SEQ), exposure (TAKE_EXPOSE), the image-engine tasks (DSP0 and
   DSP1), movie recording and the display output.
2. Section 3.
3. When section 4 is ready: focus (FCS), face detection, recording (REC), USB and the image sequencer (ISEQ).
4. Sections 5 and 6.
5. Sections 7 to 10.

The "user start" steps (USRSTART2 to USRSTART5) run along the way. The card updater's server task starts in USRSTART5,
after all ten sections are ready, so updating from the card needs almost the whole boot.

How the camera gets from here to the first live-view frame on the screen is not traced yet.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| stage 2 | 0x6019c9b9 (tag `2_1`) | [code] |
| stages 3-5 | 0x6019cdfe (tags `3_4` at 0x6019cf39, `4_1`, `5_1`, `5_4`) | [code] |
| section 4 ready point | trace `3_4`, 0x6019cf48 | [code] |
| card updater server | FIRMUP_SRV id 18, entry 0x60c3a638, started in USRSTART5 (0x6019de8a) | [code] |
| card updater client | FIRMUP_CLI id 88, entry 0x60c3a1b3 | [code] |

Sources: [boot order](../firmware/boot-and-sections.md#boot-order-and-why-hooks-need-a-guard),
[card updater](../firmware/recovery-technical.md#the-card-updater-hold-ok-at-power-on-dcolympe1379999bin).
</details>

## 7. What can go wrong

**Racing the loader.** A patch that sits in an early section and jumps into code in a later section can run before
that code is in RAM. On our Live ND builds this gave intermittent "dead at power-on" and "live view, then reset" failures.
The stock firmware never does this. The fix is a **boot guard**: a few instructions in the always-ready code that test
the target section's ready bit and fall back to the original instructions if it isn't set. With guards, ten out of ten
boots succeeded.

**Faults turn into boot loops.** Any fault (a bad address, an illegal instruction) raises a non-maskable interrupt.
The handler sets the watchdog to one second and spins, so the camera resets about a second later and leaves no trace.
If the fault happens on every boot, the camera loops. A task that merely hangs doesn't reset, because the watchdog
task keeps kicking; that needs a battery pull.

**Writing into the program.** Other projects found that storing into the loaded program's own memory restarted the
E-P7 and OM-5 II, and kept restarting them if the change was saved as a setting. We keep state out of the program
image.

**Recovery needs the boot.** The card updater lives in the main program and starts late, so a build that can't boot
that far can't be fixed from the card. That is why we keep the boot path stock and run a pre-flash check suite on
every build ([recovery](../firmware/recovery.md)).

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| guard test | 0x60045d92(n), guards in 0x600d06a4-0x600d0800 | [code]; 10/10 boots [camera] |
| deliberate reboot | "COMMON Reboot" 0x6005849f; NMI handlers → 0x60069f5a | [code] |
| writes outside data windows reset the camera | flash guard 0x600c4680 | [code] |
| stores into the program image (other bodies) | E-P7, OM-5 II | [camera] (their reports) |

Sources: [boot and sections](../firmware/boot-and-sections.md#boot-order-and-why-hooks-need-a-guard),
[recovery](../firmware/recovery.md), Atlas-linked projects.
</details>

## Checked on other cameras

Each step checked against the firmware of other bodies. Nothing is assumed: "not checked" means we don't know. The
last column holds what other projects (linked from the OM Firmware Atlas) report for their bodies, which we have not
re-checked ourselves.

| step | E-M5 III 1.7 | OM-5 1.2 | E-M1 III 1.6 | OM-5 II 1.1 | OM-1 | PEN-F | other projects |
|---|---|---|---|---|---|---|---|
| main program at VMA 0x60021020 | yes | **confirmed** | **confirmed** | **confirmed** | **different** entry: header address 0x50000000, jumps to 0x600210c5 | **confirmed** (same base) | — |
| boot stub copies always-ready code | yes | not checked | not checked | not checked | not checked | not checked | — |
| ten background sections + ready bits | yes | not checked | not checked | **confirmed**: same access-monitor step in the loader | not checked | not checked | OM-3: section 6 end word 0x60045e9c raised and run on camera |
| watchdog reset on any fault | yes | not checked | not checked | not checked | not checked | not checked | E-P7: same NMI → 1 s watchdog pattern |
| card updater inside the main program | yes (FIRMUP_CLI) | not checked | not checked | not checked | not checked | reported (FIRMUP_CLI) | E-P7: same task design |

Sources: [boot and sections](../firmware/boot-and-sections.md), Atlas-linked projects,
oly_fw_analysis notes.
