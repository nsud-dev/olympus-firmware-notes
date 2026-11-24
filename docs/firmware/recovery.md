# Recovery

<!-- human page -->
> The dense reference for this page is [Recovery: technical notes](recovery-technical.md).

Flashing your own firmware always carries a risk. The camera might not start, or it might crash and restart over and
over, which is called a bootloop. This page explains what you can recover from with just an SD card, and what you
cannot. It ends with the steps to follow when a camera will not start.

## Summary

- **A bad file is harmless.** The camera checks the whole update file before it writes anything. A corrupt, truncated
  or wrong-model file is refused, and the camera is left as it was.
- **The card rescue does not need the main program.** A small loader at the start of flash memory has its own card
  updater. Holding OK at power-on runs that one. It does not need the main program to work.
- **The rescue depends on that loader staying intact.** Normal firmware files never write there.
- **Still keep new code quiet during start-up.** Anything we add stays switched off until the camera has fully
  started. Keep a spare card with the stock firmware on it.

## Power-on

A small loader at the start of flash memory runs first. It is not part of any update file. It looks at the OK key.
If OK is not held, it starts the main program from flash memory. The main program then copies its parts into memory
one after another. None of those steps checks a checksum or a signature. A damaged main program runs as it
is.

A **watchdog** timer guards the camera. The software has to reset it every few seconds. If it stops doing so, the
watchdog restarts the camera. The camera also restarts itself on purpose after any serious fault, within about a
second. That is why a fault that happens on every start-up turns into a bootloop.

A hang is different. If one task freezes but the rest keeps running, the watchdog is still being reset, so the camera
stays in that state. Taking the battery out is the only way out of that.

## Start-up loader

The first 384 KB of flash memory hold the loader. It has two stages. We read them from a flash backup of one
E-M5 III.

The first stage runs at power-on. It sets up the clocks and reads the OK key. With OK released it copies the start of
the main program into memory and runs it. With OK held it loads the second stage instead.

The second stage is a small system of its own. It has its own flash driver, its own SD card code and its own card
updater. It looks for the same file in the same folder as the main program's updater does. It checks the file,
writes it and reads it back. It needs nothing from the main program.

We confirmed on the camera that the pin this loader reads is the OK key. A read-only watch of the pin showed it
change only while OK was held.

The loader also reads a flag in the always-on [power block](../hardware/power-block.md). When
the flag is set, the loader skips the key check and starts the main program. The stock main program sets the flag
only in one power-off case. A main program that set it at every power-off would lock the rescue out until the
battery is pulled.

## Update contents

The firmware file holds five parts. The updater writes them in a fixed order, with the main program last. Each part is
erased, written and read back. There is no rollback.

Our firmware files never touch the camera's start-up area or its factory adjustment data. Those are written only by
special update types that we never make.

Cutting the power while the main program is being written is the one moment that can leave a camera that no card can
rescue. Always start a flash with a full battery, and never open the battery door while the lamp is lit.

## Card updater

You start it by holding OK while switching the camera on, with the file `DCOLYMP/e1379999.bin` on the card.

Before writing anything, it checks the model number, the file type and a checksum over the whole file. We ran the
camera's own checking code in an emulator. A good file passed. A file with one changed byte, a file for the OM-5 and a
truncated file were all refused, and nothing was written. One gap is worth knowing about. It does not check the
checksums of smaller pieces nested inside each part, so our own checks do that instead.

The lamp tells you what happened.

| lamp | meaning |
|---|---|
| steady | writing, do not touch the camera |
| slow blink | finished, switch off |
| fast blink | file refused, nothing written |

## Recoverable failures

| problem | way back |
|---|---|
| Bad file (corrupt, wrong camera, cut short) | refused before writing, camera unchanged |
| Crash only when a new feature is switched on | switch off, battery out if needed, then flash the last good file |
| Crash on every start-up in shooting, live view, lens or USB code | hold OK at power-on with the stock file. The start-up loader runs the update, so the main program is not needed. |
| A crash that only happens on some start-ups | keep trying with OK held, because it gets through some of the time |
| Crash in the earliest part of the main program's start-up | hold OK at power-on with the stock file, as above |
| Damage to the start-up loader itself | no card rescue. This needs a service centre or a flash programmer. |
| Power cut while the main program is written | probably beyond a card rescue |
| A bad setting or a trigger file on the card | survives a reflash. Remove the card files and reset settings from the menu. |

## Recovery steps

1. Keep a spare card with only `DCOLYMP/e1379999.bin` on it, holding the stock firmware for your camera.
2. If the camera is frozen, take the battery out, wait ten seconds and put it back.
3. Remove anything that could wake a feature at start-up, such as feature files on the card, USB or HDMI cables and the
   lens.
4. Switch on normally. If the camera starts, flash the stock firmware or the last good file the usual way.
5. If it loops or stays dark, put the spare card in and hold OK while switching on. Keep holding until the lamp is
   steady. Try several times if the failure comes and goes.
6. If there is no lamp at all with OK held, the update start-up cannot run. Stop and write down exactly what happened.

## Pre-flash checks

Every build we make goes through a script of checks before it goes anywhere near a camera. It takes about a minute
and a half. A build is handed over only when the script passes. It checks that:

- the file is well formed, and the camera's own checker accepts it in the emulator
- the start-up code and the parts of the firmware the rescue needs are unchanged
- new code sits inside memory the camera loads, and is never reached before it is loaded
- every address the code uses has evidence in the stock firmware
- the build starts in the emulator and behaves like stock with nothing switched on

We test the script itself by feeding it deliberately broken files, including a real build that bootlooped on the
camera. Each one has to fail the check it was made to fail.

The script cannot see everything. It misses bugs that only appear once a feature is switched on, and parts of the
real start-up that the emulator does not model.

## Other cameras

Every Olympus and OM System body we have looked at has the same card updater, with its own model number in the file
name.

| camera | update file name |
|---|---|
| E-M5 III | `E137????.BIN` |
| E-M1 III | `E139????.BIN` |
| OM-5 | `E144????.BIN` |
| OM-1 | `E143????.BIN` |
| PEN-F | `E122????.BIN` |

## Open questions

- Does the start-up loader also offer a rescue over USB or the serial port? We found none so far.
- The loader's own updater has not been watched refusing a bad file on a camera. A safe test would be a stock file
  with its last byte changed. The camera should refuse it and write nothing.
- Does memory survive a watchdog restart? If it does, a crash record could be kept and written to the card on the next
  start-up.

## Further reading

- [Boot](../guides/boot.md) follows the camera from power-on to live view.
- [Firmware files and updates](../guides/firmware-file.md) explains what is inside an update file.
- [Modifying the firmware](patching-techniques.md), section 13, covers recovering from a bad flash.
