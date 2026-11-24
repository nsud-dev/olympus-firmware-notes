# I/O expander driver swap

<!-- human page -->

This page reports one bug of our own making. In an experiment, a driver was moved from one firmware version into
another, and one of its functions was left behind. The same mistake is easy to make with any moved driver. The
hardware background is in [E-M5 III, OM-5 and OM-5 II hardware compared](om5-family-hardware.md).

The fault was in our change. The stock firmware of every body involved is correct.

## Summary

The moved driver never sent a valid message to its chip. Every message went out as zeros. That one fault caused
three symptoms in different parts of the camera. It took about three hours and six flashes to find. Copying the
missing function fixed all of them.

## Background

The I/O expander is a small chip that gives the processor extra input and output lines over a serial bus. It carries
the line that senses a USB cable, and lines used at power-off.

The OM-5 II has a different expander chip from the E-M5 III, with a rewritten driver. The OM-5 has the same chip as
the E-M5 III. Its driver matches the E-M5 III's in all 56 functions.

In our experiment the OM-5's driver was put into a copy of the OM-5 II program in place of the new one, to see
whether the two drivers present the same interface. The driver is a closed module of
about 6 KB with 16 entry points.

## Symptoms

| symptom | explanation |
|---|---|
| Holding OK at power-on no longer reached the card updater | The expander was not shut down at power-off. This most likely left the OK key line in a state the start-up loader could not read. |
| Plugging in USB did nothing | The cable-sense line is an expander input. The driver never read the chip. |
| Starting Wi-Fi reset the camera within about 2.5 seconds | The driver waits one second for the chip to answer a power request. With no answer it calls its fatal-error routine, which resets the camera on purpose. |
| Start-up took about five seconds | The driver was waiting for a chip that never answered. |

## Root cause

The driver builds each message in a buffer of its own and then sends that buffer. The function that fills the buffer
sat directly after the copied block, so it was not copied.

Calls from the copied driver to functions outside the block were redirected to the matching function in the host
program. A table gave the match for each one. For the message builder, the table pointed at the host program's
builder, which is written for the other chip.

That function ran without an error. It built a message with the other chip's bus address, in the other driver's
buffer. The copied driver then sent its own buffer, which was still empty.

## Earlier fault

The first test did not start at all, for a different reason. The copied driver's working memory had been placed in
a free gap inside the program code. The processor reads code through its cache. Writing data there left the cache
and the memory out of step, and the screen stayed black.

## Leads that were wrong

- **A flag in the always-on power block.** The start-up loader skips its key check when the flag is set. Clearing
  the flag at every power-off did not restore the card update.
- **A state check in the USB code.** Bypassing it did not make USB respond.
- **The Wi-Fi module start-up.** The reset happened with every version of the Wi-Fi software.
- **"The bus works because the Wi-Fi processor powers up."** This was wrong. The Wi-Fi power does not go through
  this driver. The note kept the driver off the list of suspects for about 45 minutes.

## Reasons it was missed

- **The copied block ended one function early.** A function that writes the driver's own buffer is part of the
  driver.
- **The check after the copy was circular.** It confirmed that every redirected call reached the function the table
  named. It did not confirm that the named function did the same job. A comparison of every pair was run later. This
  pair was the only one that differed.
- **The driver had not run before the camera test.** The emulator has no expander chip and does not start that
  task.
- **The other checks cover other things.** They cover start-up paths, section loading, free space and whether each
  address is a real one. The wrong address was a real function.

## Checks

Two static rules catch this bug.

- Compare every function a copied module calls in the host program with the one it called in its original program.
  They must match, or have a written reason.
- Copy any function that writes the copied module's own memory.

The emulator catches it without a model of the chip. A tap on the serial bus driver logs the bytes of every message
the firmware starts. A message whose address byte is zero fails. A run can also be checked against the stock program's
first messages. The faulty program sends `00 00 01` where the stock driver sends `1c 08 1d`. This is patch 0011 in
our [om-emu additions](../tools/om-emu-additions.md).

Patch 0010 catches the earlier fault. It fails any write into the always-loaded code.

## Lessons

- A copied module is correct only if every function it calls behaves like the one it called before. Compare the
  code, not the names or positions.
- Code that has never run is untested.
- When one program shows several unrelated faults, check for a shared lower layer first.
- One part working is evidence for another part only if the first depends on the second.

Related: [E-M5 III, OM-5 and OM-5 II hardware compared](om5-family-hardware.md),
[Failure patterns](../reference/failure-patterns.md), [Recovery](../firmware/recovery.md).
