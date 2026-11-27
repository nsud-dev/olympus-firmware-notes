# Small body devices

<!-- human page -->
<!-- house style -->

## Key points

- Most small chips in the camera talk to the main processor over a few shared serial buses.
- The touch panel's controller recognises taps, slides and other gestures itself, and the firmware only translates
  them.
- The battery has no fuel-gauge chip, so the camera works out the battery level from its voltage.
- The OM-5 II firmware drives nearly all of these chips the same way, but it expects a newer accelerometer.

This page covers the small chips around the main processor. These are the eye sensor, the touch panel, the
accelerometer, the battery charger, a power chip, the temperature readings and the buttons. It covers the E-M5 III 1.7
firmware and notes where the OM-5 II firmware differs. All of it comes from reading the firmware. Nothing here was run
on the camera.

## Connections

Most of these chips talk to the main processor over serial buses. The processor has eight serial ports. The firmware
gives each device a channel number, and a table turns the channel number into a port. Several devices share one port.

- The main two-wire bus (I2C) carries the touch controller, the accelerometer, a power chip and the I/O expander.
- A second I2C bus carries the eye sensor and the battery charger.
- A third port carries the links to the rear monitor, the EVF panel and the audio chip.

The OM-5 II firmware uses the same channel table.

## Eye sensor

The eye sensor next to the EVF is a proximity sensor. Its register layout matches a ROHM chip that measures both
distance and ambient light. The firmware uses only the distance reading.

The chip raises an interrupt when the reading crosses a threshold. The firmware then decides near or far and tells the
display code to switch between monitor and EVF. The thresholds come from a factory calibration value stored in the
camera. The OM-5 II firmware drives the eye sensor the same way.

## Touch panel

The touch controller does the gesture work itself. It reports a code for each gesture, such as tap, double tap, long
press, slide or flick, plus up to two touch points.

The firmware only translates these codes. It drops gestures the current screen has turned off. It mirrors the
coordinates when the monitor is swivelled round. It also ignores a few follow-ups that make no sense, such as a long
press right after a tap. There is no tap or double-tap timing in the firmware. That timing lives in the controller,
which the firmware sets up with 15 tuning values when the panel opens.

The OM-5 II firmware uses the same touch code and tuning values.

## Accelerometer

The accelerometer feeds the level gauge and the camera's sense of which way up it is. Its register layout and ID match
an ST six-axis motion chip. The firmware reads temperature and acceleration from it and corrects the readings with
factory values for temperature.

The OM-5 II firmware expects a newer chip with a different ID. The OM-5 firmware expects the same chip as the E-M5 III.

## Battery and charging

The battery pack has no fuel-gauge chip. The camera measures the pack's voltage and its temperature sensor through the
main chip's analogue inputs, and works out the battery level from the voltage.

Charging is done by a separate charger chip on the second I2C bus. The firmware sets the charge current, the charge
voltage for the two-cell pack and how much current it may draw from USB. The register layout matches a Renesas USB
charger family.

The OM-5 II charger code is larger. It adds a few more current limits, which fits its USB-C power handling.

## Power chip

A small power chip on the main I2C bus is switched on in steps during power-on. The firmware runs it through six
steps and then sets one output line. At power-off it runs the last two steps back down. The steps are numbers inside
the chip's own sequence, so which supplies they feed is not visible in the firmware.

## Temperatures

The camera watches several temperatures. These are the image sensor, a body sensor, the battery and the accelerometer.
Each has levels for a warning and for shutting down. The body and battery readings come through the analogue inputs.

## Buttons, dials and lights

The buttons are covered in the [button guide](../guides/button-press.md).

The dials use a hardware pulse counter in the main chip. The counter has four channels. The E-M5 III firmware opens
three of them. The OM-5 II firmware opens only two. The extra channel belongs to a dial on an accessory grip. The
firmware calls it the grip 1 sub dial. It only switches that channel on when it detects the grip. The body's own front
and rear dials use the other two channels.

The lamps are set up as eight slots. Each slot is either a plain output pin or a pulse output. The table that says
which pin each lamp uses is filled in at start-up and is not in the unpacked program file. The OM-5 II firmware uses
the same lamp code.

## HDMI

HDMI is handled by a block inside the main chip, not by the serial buses. The block reads the TV's description data
(EDID) itself. The firmware checks that data and reads the TV's maker and capabilities from it. The block also does
CEC, the remote-control link over HDMI. Buttons pressed on a TV remote reach the camera as ordinary key events. The
OM-5 II firmware uses the same HDMI code.

## Further reading

- [Small body devices: technical notes](small-devices-technical.md) has the channel map, the chip registers and the
  addresses.
- [Button guide](../guides/button-press.md) covers the buttons.
- [Interrupts, timers and DMA](interrupts-timers-dma.md) covers the serial ports.
- [Power and watchdog block](power-block.md) covers power-on and power-off.
