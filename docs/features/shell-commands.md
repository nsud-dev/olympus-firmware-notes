# User shell commands

<!-- human page -->
<!-- house style -->

## Key points

- The E-M5 III's hidden debug shell has 58 commands, and we now know what every one of them does.
- Most commands only print information, but a few write to the camera's flash memory and must never be used.
- Some forgotten commands turned out to be whole small tools, such as a BASIC script engine and a GPS log matcher.
- The OM-5 II's firmware keeps the same list in the same order and adds five commands of its own.

The E-M5 III has a hidden debug console, the user shell, with the prompt `USR>`. The
[Wi-Fi debug shell](wifi-debug-shell.md) page explains how to reach it from a laptop. This page explains what its
commands do and which ones are safe.

Everything here was found by reading the firmware. None of the commands on this page were run on the camera for this
survey.

## What the commands cover

Each command belongs to one part of the camera. There are commands for the lens, the sensor, the shutter, the flash,
the stabiliser, the battery charger, USB, Wi-Fi, focus, exposure, playback, movies and the display. Most of them print
the state of that part or switch its debug log on and off.

A few have no code behind them at all. Two are empty templates that only print their own name, and a third returns at
once.

## Commands that were unknown

Several command names gave no clue to what they do. Reading their code showed this.

| command | what it turned out to be |
|---|---|
| `olis` | the list of pictures marked for sharing, which OI.Share later transfers |
| `albm` | the store behind playback's movie albums |
| `pos` | a tool that matches a GPS log on the card to pictures by time |
| `sdk` | the console of the camera's high-level service layer, with a key-press recorder |
| `sc` | heap lists and timing measurements |
| `spc` | control of a Wi-Fi SD card (Toshiba FlashAir) |
| `iseq` | traces of the computational modes, such as High Res and a digital ND filter |
| `bas` | a small BASIC interpreter that can press keys and call camera functions |

*Commands whose purpose was unknown before this survey.*

The digital ND filter entry is interesting for our [Live ND](live-nd.md) work. It shows that the stock E-M5 III still
keeps a place for a digital ND sequence in its tables.

The BASIC engine can load a script from the card and store it in the camera's flash memory. The names suggest it was
meant for factory or service scripts.

## Safety

> [!WARNING]
> A few commands write to the camera's flash memory. Some of that data, such as the factory calibration, can't be
> restored. Never run `flash`, the writing words of `bas`, `res` and `prm`, or the damage-reset words of `mec`.

The commands fall into four groups.

- **Never run.** Commands that write flash or delete files, and the lens firmware update.
- **Changes the camera's state.** Commands that drive the shutter, a motor, the flash, the charger, USB or Wi-Fi, or
  press buttons. They don't write flash, but they should only be used with a clear plan.
- **Writes the card.** Commands that save logs, macros or album and share files. They are safe for the camera. Use a
  spare card.
- **Read-only.** Commands such as `help`, `echo`, `buff` and `take dbginfo`, which only print.

## OM-5 II

The OM-5 II's firmware has 63 commands. The first 57 are the E-M5 III's list in the same order. The new ones cover the
motion search unit used for AF tracking, the system shell's commands, a usage log, Bluetooth and location from a phone.
Several existing commands gain new words.

## Status

Desk research is complete for all 58 commands. Open questions remain on where the BASIC engine stores its script and
on the OM-5 II's usage log.

## Further reading

- [User shell commands: technical notes](shell-commands-technical.md) has every command with its sub-commands, what it
  can change, and the addresses.
- [Wi-Fi debug shell](wifi-debug-shell.md) explains how to reach the shell and what it is good for.
