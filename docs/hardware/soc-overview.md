# SoC overview

<!-- human page -->
> The dense reference for this page is [SoC overview: technical notes](soc-overview-technical.md).

Every camera in this family is built around one main chip, a system on a chip that holds several different processors.
This page introduces those processors, shows which ones changed between camera models, and explains what that means for
moving features from a newer body to the E-M5 III.

As far as the firmware can tell, the E-M5 III, OM-5, OM-5 II and E-M1 III use the same chip. The OM-1 generation is new
hardware.

## "TruePic" is the whole chip

Olympus advertises each camera as having a TruePic VIII, IX or X processor. That name covers the whole chip, not one
core. Inside it there are several kinds of processor, and they were updated at different times.

- **Control processors** run the camera's main program, which covers menus, buttons, settings and the shooting sequence.
  They are Panasonic MN103 cores. The E-M5 III has three of them.
- **An ARM co-processor** runs Linux, mainly for Wi-Fi and Bluetooth.
- **The image engine** does the heavy pixel work by running small programs.
- **Newer blocks**, such as an AI accelerator, appear only in the OM-1 generation.

## One chip, three names

Olympus sells the E-M5 III as TruePic VIII and the OM-5 and E-M1 III as TruePic IX. In the firmware they look like the
same silicon.

- Almost every hardware register address used by matching code is identical.
- The image-engine data matches, apart from 26 pieces out of about 27,000.
- The E-M5 III runs the OM-5's image-engine jobs unchanged.
- The chip's own description calls it Panasonic "dc13" on all of them. Later bodies use the name of Nuvoton Japan, which
  took over Panasonic's chip business. That looks like a rename rather than a new chip.

Whether it is literally the same die or a small revision cannot be settled from firmware. Either way, control code
taken from a newer body runs unchanged on the E-M5 III, because it is the same processor.

## The OM-1 generation

The OM-1 and OM-1 II still use MN103 control processors with the same instruction set, but four of them. The rest is
new:

- a 64-bit ARM in place of the 32-bit one
- a new image engine whose programs match nothing older
- an AI accelerator, driven from the fourth control processor
- extra detection blocks, a GPU and seven image pipelines

Its memory runs over four channels, most likely LPDDR4 or LPDDR4X, at about 2 GB. The firmware never names the type,
because memory is set up by boot code that is not part of the update file.

## Older generations

The E-M5 II and PEN-F share an older chip, TruePic VII. It has the same family of control processors and the same
image-engine program format, but most hardware registers moved, and there is no ARM co-processor. Wi-Fi runs on the
main processor. The original E-M5 is older again, with no image-engine programs of this kind.

## Memory

The E-M5 III, OM-5 and OM-5 II have about 1 GB of memory. The E-M1 III and OM-1 have about 2 GB. Fitting bigger memory
chips would not be a simple swap. The firmware sets up the memory controller and lays out every buffer for one size, so
both would have to change. The E-M1 III's firmware would be the reference for a 2 GB layout on this chip.

## Why the MN103 stayed

This is a guess. The main program is more than 100,000 functions, built on the same operating system and compiler for
over a decade. Adding hardware blocks around the old control processor costs far less than rewriting all of that for
ARM. The heavy work already runs on dedicated blocks anyway.

## Other processors in the camera

- **The stabiliser** has a processor of its own. See [Image stabiliser](stabiliser.md).
- **A power processor** looks after the battery and charging. The OM-1 and E-M1 III ship its firmware in the update
  file. The E-M5 III does not.
- **The Wi-Fi and Bluetooth module** is a Cypress CYW43455 on the E-M5 III, OM-5, E-M1 III and OM-1, and a CYW43439 on
  the OM-5 II.

## Further reading

- [How the cores talk to each other](../guides/cores.md) explains locks, doorbells and cross-core calls between the
  control processors.
- [An MN103 primer](../guides/mn103-primer.md) introduces the control processors' instruction set.
- [ARM co-processor](arm-coprocessor.md), [Image engine](image-engine.md) and [Memory map](memory-map.md) cover each
  part in more depth.
