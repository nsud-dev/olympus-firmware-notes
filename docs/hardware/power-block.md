# Power and watchdog block

<!-- human page -->
> The dense reference for this page is [Power and watchdog block: technical notes](power-block-technical.md).

The E-M5 III has no separate power processor. Its power-on, power-off, clock and watchdog jobs are done by a small
always-on part of the main chip. That part keeps running on a trickle of power while the camera is off. [code] 2026-11-23

We used to call it "the power sub-CPU". The code shows no messages and no answers, only registers. The main program
writes a register, then writes a fixed "commit" value so the always-on part takes the new setting. Nothing in any
update file is a program for it.

## Functions

- **Keeps the time.** A seconds counter runs while the camera is off. When the clock is set, the firmware reads it back
  and leaves a "clock is valid" mark.
- **Keeps 14 small memory words.** They survive power-off. The flash guard uses two of them to record which write it
  blocked before it reset the camera.
- **Wakes the camera.** Five inputs can turn the camera on: the power switch, a memory card going in, and three others
  whose wiring is not yet known. Two alarms can wake it at a set time.
- **Tells the firmware why it woke.** On each start the firmware reads which input or alarm woke it, or whether the
  battery had just gone in, or whether the watchdog had reset it. It turns that into a "power-on factor" number.
- **Turns the camera off.** The firmware writes a fixed key to a power-off register.
- **Runs the watchdog.** The watchdog resets the camera unless it is fed. It is set to 10 at start and fed every
  3 seconds by a task called PER_WDT. The unit is probably seconds.

## Keys

Four fixed numbers unlock these jobs: one to commit, two to feed the watchdog, and one to power off. They read like
dates: 1919-10-12, 1945-08-15, 1972-10-30 and 2004-10-01. The first is the founding date of Olympus. The last is when
Olympus Imaging was set up. The same four numbers appear in the E-M5 III, OM-5, E-M1 III and OM-1 firmware, so they are
not a per-model check.

## Fault handling

When the firmware hits a serious fault, it sets the watchdog to 1 and stops. The camera resets about a second later.
On the next start the "why it woke" flags say "watchdog". A task that only hangs is different. PER_WDT keeps feeding
the watchdog, so the camera freezes until the battery comes out.

## Other bodies

- **OM-5:** the same block, driven the same way, with the same table of wake reasons. The two cameras do not differ
  here.
- **E-M1 III and OM-1:** the same block, plus a real power processor (an STM32 microcontroller) for the battery,
  charging and USB power. Its program ships inside their update files.
- **E-M5 III:** its only separate processor with its own program is the one that drives the [stabiliser](stabiliser.md).

## Where in the firmware

| what | where | known from |
|---|---|---|
| register window | 0x98e00000-0x98e000a4, commit value 0x20041001 at +0xa4 | [code] |
| driver | 0x60063b57-0x6006442d, init at stage 0 | [code] |
| watchdog set / feed | 0x600226e1 / 0x4700101b | [code] |
| power-off | 0x47000afa | [code] |
| power-on factor | word 0xa2652ccc, table 0x601b7e54 | [code] |

Details, the register map and the comparison table: [technical notes](power-block-technical.md).
Related: [Boot](../guides/boot.md), [Recovery](../firmware/recovery-technical.md).
