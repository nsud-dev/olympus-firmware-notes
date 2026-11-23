# Body comparison

<!-- human page -->
> The dense reference for this page is [Body comparison: technical notes](comparison-technical.md).

This page puts the cameras we have looked at side by side. It explains why the OM-5 is our main source of features for
the E-M5 III, how far our work carries to other bodies, and why you cannot simply flash OM-5 firmware onto an E-M5 III.

Every body here uses the same firmware file format and the same family of control processor. So our unpacking tools
and disassembly tools work on all of them. What differs is the chip generation around that processor.

## The families

| family | cameras | chip | notes |
|---|---|---|---|
| current | E-M5 III, OM-5, OM-5 II, E-M1 III | TruePic VIII and IX, the same silicon as far as firmware can tell | about 1 GB of memory (2 GB on the E-M1 III) |
| newest | OM-1, OM-1 II | TruePic X | four control cores, new image engine, AI block |
| older | PEN-F, E-M5 II | TruePic VII | no ARM co-processor, an older image engine with the same program format |
| oldest | E-M5 (Mark I) | TruePic VI | an older framework, no Wi-Fi |

## Which features each body has

| feature | E-M5 III | OM-5 | OM-5 II | E-M1 III | OM-1 | OM-1 II | PEN-F | E-M5 II | E-M5 I |
|---|---|---|---|---|---|---|---|---|---|
| Live ND | our port | ND2-16 | ND2-16 | yes | ND2-64 | ND2-128 | no | no | no |
| Live GND | no | no | menu only | no | no | yes | no | no | no |
| hand-held High Res | being ported | yes | yes | yes | yes | yes | tripod only | tripod only | no |
| Starry Sky AF | test build | yes | yes | yes | yes | yes | no | no | no |
| subject detection | no | no | no | no | yes | yes | no | no | no |
| USB webcam | partly ported | yes | yes | no | no | yes | no | no | no |
| USB-C power delivery | no | code only | yes | yes | yes | yes | no | no | no |

## Why the OM-5 is the donor

About 82% of the OM-5's functions match the E-M5 III's. Its memory layout fits the E-M5 III's 1 GB, and its image-engine
jobs run unchanged on the E-M5 III. The E-M1 III is just as close in code, but its Live ND and High Res layouts expect
2 GB. So we take code from the OM-5, use the E-M1 III to decide where hooks go, and use the OM-1 generation only as a
reference for logic and maths.

## How far our work carries

**To the OM-5, OM-5 II, E-M1 III and OM-1 family.** Live ND, High Res and Starry Sky AF are already built in. What
carries over is the any-lens focus stacking patch, which is the same one branch on every body, our way of adding menu
rows with saved values, the card console and the Wi-Fi shell, and the profile editor. Addresses differ on every body.

**To the PEN-F and E-M5 II.** These two share a chip and most of their code, so the PEN-F is the natural donor for the
E-M5 II. Our E-M5 III code and addresses do not carry over. The methods do, meaning where to look, how to hook and how
to test. A Color and Monochrome Profile port from the PEN-F to the E-M5 II looks promising. Hand-held High Res is
impossible there, because it needs the ARM co-processor.

**To the original E-M5.** Very little beyond the file tools and the processor tools.

A rule of thumb for any body: "present" in a scan means the code or text exists. It does not mean it was tried or
behaves the same.

## Why not flash the OM-5's firmware?

The two cameras are close enough that people ask. Both have a micro-USB port. The OM-5's firmware carries USB-C
power-delivery code from the E-M1 III, but the port itself arrives with the OM-5 II. The firmware shows no difference
in the display controller, sensor, Wi-Fi module or ARM side.

Even so, a whole-image cross-flash is a bad idea.

- The E-M5 III's card updater checks the model number and refuses an OM-5 file before writing anything.
- The stabiliser's own firmware differs, and its command numbers are shifted.
- Five factory calibration entries the OM-5 expects were never written on an E-M5 III.
- The settings store is laid out differently.
- Worst of all, the card updater lives inside the main program. A camera running OM-5 firmware would run the OM-5's
  updater, which would most likely refuse the E-M5 III's own firmware. That leaves no card route back.

Porting fixes these piece by piece, which is why the project ports features rather than whole images.

## Further reading

- [SoC overview](../hardware/soc-overview.md) explains the chip generations.
- [Recovery](../firmware/recovery.md) covers the card updater's checks.
- [Anatomy of a feature port](../guides/port-anatomy.md) shows a port from the OM-5 step by step.
