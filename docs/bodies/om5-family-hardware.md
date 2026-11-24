# E-M5 III family hardware

<!-- human page -->

This page compares the hardware of the E-M5 Mark III, the OM-5 and the OM-5 Mark II, as read from their firmware.
The three cameras are built on one platform. The firmware shows how much of it is carried forward from one model
to the next.


## Status

The comparison is read from the three firmware files. Parts of it were confirmed in an emulator and on an
E-M5 III.

## Shared hardware

These parts are the same on all three bodies.

- **Main chip.** The processor cores, the image engine and the register addresses are the same. About 99.8% of the
  hardware registers the OM-5 program uses are also used by the E-M5 III program.
- **Sensor.** The sensor and its readout modes are the same.
- **Memory.** The memory size and the frame buffer layout are the same.
- **Stabiliser controller.** This is a separate chip with its own program. The newer programs for it use the same
  hardware registers.
- **Power and watchdog block.** See [Power and watchdog block](../hardware/power-block.md).
- **Keys and dials.** The key tables and the OK key path match function for function.
- **Start-up code and update file checks.** Only the model number differs.

## Differences

| part | E-M5 III | OM-5 | OM-5 II |
|---|---|---|---|
| USB socket | micro-USB | micro-USB | USB-C, with new power-source logic |
| I/O expander chip | type A | type A, same driver function for function | a different chip and a rewritten driver |
| Wi-Fi and Bluetooth module | CYW43455 | CYW43455 | CYW43439, with a new power-up sequence |
| flash layout | its own | other addresses, same scheme | a third set of addresses, one block 1 MB larger |
| factory adjustment table | its own order | entries added, most offsets moved | one more entry |
| saved settings layout | its own | different, see the [settings map](settings-map-om5.md) | a third layout |
| menu system | older | older | new |

Each body marks its saved settings with its own layout number. A program that finds another body's number resets the
settings and does not misread them.

## Design

The differences sit in two places, which are board support and storage layout. The image pipeline, the autofocus
and the menus are written against the platform and not against one board.

Each model changes the parts its new hardware needs and leaves the rest alone. Code that has been proven on one
model is reused on the next.

It also explains why knowledge transfers. Most of what these notes describe for the E-M5 III applies to the OM-5
with only the addresses changed.

## Model-specific parts

Each program is built for its own body. Four things tie it there.

1. **Flash addresses.** The program expects its resources, settings and adjustment data at its own body's
   addresses.
2. **Factory adjustment data.** Every camera carries values measured at the factory for the sensor, the stabiliser
   and other parts. Each program reads them in its own order. This data cannot be recreated, so it must never be
   overwritten.
3. **Board-level drivers.** The card slot pads and two USB transceiver routines are driven differently. On the
   OM-5 II the I/O expander is too.
4. **Wi-Fi module.** The OM-5 II program only carries firmware for its own module.

The update file check also refuses another body's file by its model number.

Features are developed, tuned and tested for the body they ship on. The sensor calibration, the stabiliser tuning
and the thermal limits are measured per model. A feature being present in a newer program says nothing about
whether it was validated on older hardware.


## Lessons

- Storage layout and board drivers are where the bodies differ. Check those first when comparing two models.
- An emulator is a useful first test of a comparison. It cannot test a driver for a chip it does not model.
- Leave the factory adjustment data untouched in any experiment.

## Credits

The emulator runs used [om-emu](https://github.com/flatpanda/om-emu) by the om-emu contributors.

Related: [Body comparison](comparison.md), [Settings map](settings-map-om5.md), [Recovery](../firmware/recovery.md).
