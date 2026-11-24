# Firmware files and updates

*Guide 11 · E-M5 III firmware 1.7 · draft 1, 2026-11-19. New to these guides? Read
[Before you start](before-you-start.md) first. Open questions:
research gaps.*

This guide explains the firmware update file Olympus ships (`OLY_E_137_1700_0000_0000.BIN` for the E-M5 III 1.7): how
it is put together, how the camera checks and installs it from an SD card, and what happens when the firmware on the
camera is broken. Anyone patching their camera needs all three, and most of it applies, with different numbers, to
the other bodies in the family.

The file format and the updater are mapped from the code and confirmed by flashing our own builds. What runs before
the main program, and whether there is any rescue path that doesn't need it, are not known.

## 1. The file at a glance

The file is a handful of **blocks** placed back to back. Each block is one thing the camera stores in its flash: the
main program, the menu graphics, the image-engine programs and so on. The E-M5 III file has five:

| block | what it holds | size |
|---|---|---|
| 0 | the main program for the MN103 cores (code, text, menu tables) | 24 MB |
| 1 | user-interface graphics and the language files | 30 MB |
| 2 | resources: image-engine programs, the settings key table, the ARM's Linux image, and more | 50 MB |
| 3 | very likely the stabiliser sub-processor's program ("LUKE") | 256 KB |
| 4 | sample images and other data | 9 MB |

Other bodies have four to six blocks; the OM-1 and E-M1 III carry a sixth (on the OM-1, the power sub-processor's
program).

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| block list with offsets, flash addresses and types | [container format](../firmware/container-format.md#what-is-in-each-block-e-m5-iii-17) | [code] |
| block 3 = LUKE | updater writes it to the IS sub-CPU | [inferred] |
| blocks per body | [container format](../firmware/container-format.md#which-camera-a-file-is-for) | [code] |

Sources: [container format](../firmware/container-format.md).
</details>

## 2. Each block's wrapper

Every block has the same wrapper: a 32-byte header in plain text, the payload, and a 32-byte trailer.

- The **header** says which camera the block is for (a 4-byte "magic", `OE 13 70` for the E-M5 III), where in flash it
  goes, how big it is, and what kind of block it is.
- The **trailer** repeats the header and adds a checksum.
- The **payload** is scrambled, but not encrypted. Every byte is inverted, and the bytes in each group of 16 are put in a
  fixed different order. There is no key: anyone who knows the pattern can undo it.

The checksum is simple: add up the whole block (header, unscrambled payload and trailer) as 32-bit words, and the
total must come to zero. The last word of the trailer is chosen to make that true.

```
unscramble one 16-byte group (base = 0, 4, 8, 12 within the group):
    order = {0: [2,0,3,1], 4: [1,3,0,2], 8: [3,2,1,0], 12: [2,0,1,3]}
    scrambled[base + j] = NOT plain[base + order[base][j]]

checksum: sum of all 32-bit words (header + plain payload + trailer) == 0 (mod 2^32)
```

That's all the protection there is. There is no signature, so a file we build and checksum correctly is accepted like
an Olympus one. That is how all our test builds get onto the camera.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| header and trailer layout (8 words) | [container format: blocks](../firmware/container-format.md#blocks) | [code] |
| scramble pattern and checksum | same | [code] |
| repacked files accepted, also with the same version number | every build we flashed | [camera] |
| our tool | `olyfw.py` lists and unpacks the blocks and checks the checksums | [code] |

Sources: [container format](../firmware/container-format.md), tools.
</details>

## 3. Compressed parts on some bodies

The E-M5 III's main program is stored as is. The E-M1 III, OM-5 and OM-5 II compress two large stretches of theirs
with LZ4. Each is unpacked in place at boot, at the same address it occupies. This matters when you compare bodies:
analyse the unpacked image, or half the code looks missing.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| `olycompress` sections and load table | E-M1 III, OM-5, OM-5 II block0; table 0x60028000 | [code] |
| none on | E-M5 III, PEN-F, OM-1 | [code] |

Sources: [container format: compressed sections](../firmware/container-format.md#compressed-sections-olycompress-lz4).
</details>

## 4. Updating from the card

To update, you put the file on the card as `DCOLYMP/E137xxxx.BIN` (we use `e1379999.bin`), hold **OK** and switch the
camera on. There is no screen: the AF lamp stays lit while the camera works and blinks when it's done.

The updater is not a separate program. It is part of the main program: a pair of tasks (a client and a server) inside
block 0. So the camera starts the main program as usual, the updater sees OK held and the file on the card, and takes
over.

Before it writes anything, the updater **checks the whole file**: every block's camera model, header against trailer,
and checksum. A corrupt, truncated or wrong-camera file is rejected with nothing written, and the lamp blinks fast. It
doesn't check the version number, which is why going back to an older or the same version works.

Then it writes the blocks one by one, each as erase, program, read back. The main program goes **last**:

```
stabiliser program (block 3) → sample data (4) → resources (2) → graphics (1) → main program (0)
```

There is no rollback. If the power fails while the main program is being written, the camera is left without one.

| lamp | meaning |
|---|---|
| solid | working |
| slow blink | done; switch off |
| fast blink | file rejected; nothing written |

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| updater tasks | FIRMUP_CLI 0x60c3a1b3, FIRMUP_SRV 0x60c3a638, FIRMUP_LED | [code] |
| file name pattern | `E137????BIN` in `DCOLYMP` | [code] |
| validator | 0x60c3aa36, run in om-emu: flipped byte, wrong model, truncation all rejected with 0 writes | [code] |
| write order and erase/program/verify | camera's writer run in om-emu on the stock file | [code] |
| lamp states | FIRMUP_LED 0x601fca3a (255 / 250 / 100) | [code]; solid and blink [camera] |

Sources: [recovery: the card updater](../firmware/recovery-technical.md#the-card-updater-hold-ok-at-power-on-dcolympe1379999bin).
</details>

## 5. Why the updater needs a working camera

Because the updater lives inside the main program, the camera has to boot most of the way to run it: the boot copy, all
ten sections of the program, the start-up stages, the file system and the resource reads from the other blocks. The
updates over USB and Wi-Fi need even more (the USB stack, the user interface, the ARM).

So a card update can fix almost any problem **except** one that stops the camera before the updater starts. A patch
that crashes every boot early enough can leave the camera without a card-based rescue. That is the most important
fact in this guide for anyone patching, and it shapes every rule our builds follow.

The flash itself is also guarded while the camera runs normally: only a few data windows (settings, logs) may be
written, and a write anywhere else resets the camera. The boot area at the start of flash is written only by a special
kind of update that our files never contain.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| flash | 128 MB at 0x40000000 | [code] |
| writable windows in normal operation | 0x40060000-0x40780000, 0x41f60000-0x42160000, 0x47a80000-0x48000000; guard 0x600c463a | [code] |
| boot area | 0x40000000-0x40060000, written only by update kind BOOT | [code] |
| what runs before block 0 | not known | open |

Sources: [recovery: flash map](../firmware/recovery-technical.md#flash-map-and-what-an-update-writes), [boot](boot.md).
</details>

## 6. When the firmware is broken

The camera protects itself with a **watchdog**, a timer in an always-on part of the main chip (power block) that resets the camera unless a task kicks
it every few seconds. Any serious fault (an exception, a deliberate "reboot") sets the watchdog to its shortest time
and stops, so the camera resets about a second later. A fault that happens on every start becomes a **bootloop**.

A task that hangs without faulting is different: the watchdog task keeps running, so the camera just sits there
frozen until the battery comes out.

What can be fixed, roughly:

| problem | way out |
|---|---|
| bad file | rejected, camera unchanged |
| crash only when a feature is used | battery out, start normally, flash the stock file |
| crash on every normal start, in shooting, live view, lens or USB code | hold OK at power-on with the stock file; the update start shouldn't reach that code |
| boot fails only sometimes | keep trying with OK held |
| crash early in the boot chain | no card rescue; service or a flash programmer |
| power lost while the main program is written | camera without a main program |

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| watchdog | always-on power block (2026-11-23), set via 0x600226e1; kicked every 3 s by PER_WDT | [code] |
| fault → short watchdog → reset | "COMMON Reboot" 0x6005849f, NMI handler 0x60069f5a | [code] |
| a hang doesn't reset | Live ND test build | [camera] |
| recovery table | [recovery](../firmware/recovery-technical.md#which-failures-are-recoverable) | [code] + [camera] + [inferred] |

Sources: [recovery](../firmware/recovery.md).
</details>

## How our builds use this

- **Builds are shipped as deltas.** We keep a small binary difference against the stock file in the repository, never
  the firmware itself, and rebuild the full file from it.
- **Every build passes a pre-flash check** before it reaches the camera: the wrapper and checksums, the camera's own
  validator (run in an emulator), that the boot path is unchanged, that every new address is backed by stock code, and
  an emulated boot.
- **Nothing of ours runs during boot.** Hooks stay switched off until the camera is up and the user arms the feature, so
  the update start always runs stock code and a card rescue stays possible.
- **A spare card** with only the stock file on it is the first line of recovery.

## Checked on other cameras

Each step checked against the firmware of other bodies. Nothing is assumed: "not checked" means we don't know.

| step | E-M5 III 1.7 | OM-5 1.2 | E-M1 III 1.6 | OM-5 II 1.1 | OM-1 1.9 | PEN-F 3.1 | other projects |
|---|---|---|---|---|---|---|---|
| block wrapper, scrambling and checksum | yes | **confirmed** | **confirmed** | **confirmed** | **confirmed** | **confirmed** | — |
| blocks | 5 | **confirmed** 5 | **different**: 6 | **confirmed** 5 | **different**: 6 (block 5 = sub-CPU) | **different**: 4 | — |
| compressed parts of block 0 | none | **different**: 2 LZ4 sections | **different**: 2 | **different**: 2 | none | none | — |
| card updater in block 0 (FIRMUP_CLI, `DCOLYMP`) | yes | **confirmed** | **confirmed** | **confirmed** | **confirmed** | **confirmed** | E-P7 (caduceus): same task design |
| card file name | `E137????BIN` | `E144????BIN` | `E139????BIN` | not found (in a compressed part?) | `E143????BIN` | `E122????BIN` | — |
| validator checks everything before writing | yes (emulator) | not checked | not checked | not checked | not checked | not checked | — |
| write order, block 0 last | yes (emulator) | not checked | not checked | not checked | not checked | not checked | — |

Sources: [container format](../firmware/container-format.md), [recovery](../firmware/recovery.md),
Atlas-linked projects.
