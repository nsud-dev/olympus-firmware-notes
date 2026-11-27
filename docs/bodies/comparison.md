# Body comparison

<!-- human page -->
<!-- house style -->

## Key points

- Every body here uses the same firmware file format and the same family of control processor, so our tools work on
  all of them.
- The OM-5 is our main source of features, because most of its code matches the E-M5 III's and its memory layout fits
  the E-M5 III's 1 GB.
- Our patches and methods carry over to the newer bodies with new addresses, but only the methods carry over to the
  PEN-F and E-M5 II.
- The project ports features one at a time, because a whole OM-5 firmware image differs from the E-M5 III's in too many
  places.

This page puts the cameras we have looked at side by side. It explains why the OM-5 is our main source of features for
the E-M5 III, how far our work carries to other bodies, and why the OM-5's firmware can't simply be put onto an
E-M5 III as it is.

Every body here uses the same firmware file format and the same family of control processor. So our unpacking tools
and disassembly tools work on all of them. What differs is the chip generation around that processor.

## Families

| family | cameras | chip | notes |
|---|---|---|---|
| current | E-M5 III, OM-5, OM-5 II, E-M1 III | TruePic VIII and IX, the same silicon as far as firmware can tell | about 1 GB of memory (2 GB on the E-M1 III) |
| newest | OM-1, OM-1 II, OM-3 | TruePic X | four control cores, new image engine, AI block |
| older | PEN-F, E-M5 II | TruePic VII | no ARM co-processor, an older image engine with the same program format |
| oldest | E-M5 (Mark I) | TruePic VI | an older framework, no Wi-Fi |

*Camera families by chip generation.*

## OM-3

The OM-3 is built on the OM-1 II, not on the OM-5. Its firmware has the same layout, the same four control cores and
the same AI block. Its image-engine programs and AI data are byte-for-byte the OM-1 II's. Its ARM co-processor is the
same pair of Cortex-A53 cores. Only the Wi-Fi chip differs. It uses the OM-5 II's chip.

It has Live ND up to ND128, Live GND, hand-held High Res, Starry Sky AF, subject detection and the USB webcam built in.
Its new code is mostly for its own controls, such as a picture-mode dial.

For the E-M5 III it is a donor in the same way as the OM-1 II. Its control logic can be studied, but its image-engine
programs and AI features most likely need hardware the E-M5 III lacks.

See also: [OM-3 in the technical notes](comparison-technical.md#om-3-11).

## Features by body

| feature | E-M5 III | OM-5 | OM-5 II | E-M1 III | OM-1 | OM-1 II | PEN-F | E-M5 II | E-M5 I |
|---|---|---|---|---|---|---|---|---|---|
| Live ND | our port | ND2-16 | ND2-16 | yes | ND2-64 | ND2-128 | no | no | no |
| Live GND | no | no | menu only | no | no | yes | no | no | no |
| hand-held High Res | being ported | yes | yes | yes | yes | yes | tripod only | tripod only | no |
| Starry Sky AF | test build | yes | yes | yes | yes | yes | no | no | no |
| subject detection | no | no | no | no | yes | yes | no | no | no |
| USB webcam | partly ported | yes | yes | no | no | yes | no | no | no |
| USB-C power delivery | no | code only | yes | yes | yes | yes | no | no | no |

*Features each body has in its own firmware. The E-M5 III column shows the state of our own ports.*

## Donor choice

About 82% of the OM-5's functions match the E-M5 III's. Its memory layout fits the E-M5 III's 1 GB, and its image-engine
jobs run unchanged on the E-M5 III. The E-M1 III is just as close in code, but its Live ND and High Res layouts expect
2 GB. So we take code from the OM-5 and use the E-M1 III to decide where hooks go. The OM-1 generation serves only as a
reference for logic and maths.

## Reach of our work

**To the OM-5, OM-5 II, E-M1 III and OM-1 family.** Live ND, High Res and Starry Sky AF are already built in. Four
things carry over:

- the any-lens focus stacking patch, which is the same one branch on every body
- our way of adding menu rows with saved values
- the card console and the Wi-Fi shell
- the profile editor

Addresses differ on every body.

**To the PEN-F and E-M5 II.** These two share a chip and most of their code, so the PEN-F is the natural donor for the
E-M5 II. Our E-M5 III code and addresses do not carry over. The methods do, meaning where to look, how to hook and how
to test. A Color and Monochrome Profile port from the PEN-F to the E-M5 II looks promising. Hand-held High Res is
impossible there, because it needs the ARM co-processor.

**To the original E-M5.** Little beyond the file tools and the processor tools.

As a rule of thumb for any body, "present" in a scan means the code or text exists. It does not mean it was tried or
behaves the same.

## Whole-image swaps

The two cameras are close enough that people ask whether the OM-5's whole firmware would do. Both have a micro-USB port.
The OM-5's firmware carries USB-C power-delivery code from the E-M1 III, but the port itself arrives with the OM-5 II.
The firmware shows no difference in the display controller, sensor, Wi-Fi module or ARM side.

Even so, putting the whole OM-5 image on an E-M5 III is a bad idea, for these reasons.

- The E-M5 III's card updater checks the model number and refuses an OM-5 file before writing anything.
- The stabiliser's own firmware differs, and its command numbers are shifted.
- Five factory calibration entries the OM-5 expects were never written on an E-M5 III.
- The settings store is laid out differently.
- Worst of all, the card updater lives inside the main program. A camera running OM-5 firmware would run the OM-5's
  updater, which would most likely refuse the E-M5 III's own firmware. That leaves no card route back.

Porting deals with these differences piece by piece, which is why the project ports features rather than whole images.

## Further reading

- [Body comparison: technical notes](comparison-technical.md) has the per-body tables, the feature scans and the
  older-body comparison.
- [SoC overview](../hardware/soc-overview.md) explains the chip generations.
- [Recovery](../firmware/recovery.md) covers the card updater's checks.
- [Feature ports](../guides/port-anatomy.md) shows a port from the OM-5 step by step.
