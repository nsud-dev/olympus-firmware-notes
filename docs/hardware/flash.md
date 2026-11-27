# Flash and hot shoe

<!-- human page -->
<!-- house style -->

## Key points

- The camera and a flash on the hot shoe talk over a two-way serial link, which can even carry new flash firmware.
- Automatic flash exposure (TTL) compares a frame without flash with one or two frames lit by a weak pre-flash.
- A small timing block in the main chip fires the flash from the shutter's first-curtain signal or from a timer.
- Everything on this page comes from reading the firmware and has not been tested on the camera yet.

The E-M5 III has no built-in flash. It ships with a small clip-on flash, the FL-LM3, and takes larger flashes on the
hot shoe. This page explains how the program talks to a flash, measures the flash light and fires it in time with the
shutter. Everything here comes from reading the firmware. Nothing was tested on the camera yet.

The flash code is called "strobe" (STB) in the firmware. It has its own tasks for the flash sequence, charging and the
hot-shoe link, and a small timing block in the main chip that fires the flash.

## Parts

| part | what it does |
|---|---|
| Flash sequence task (STB_SEQ) | runs the flash part of each shot: pre-flash metering, the power calculation, the main flash, RC commands |
| Charge task (STB_CHARGE) | starts, pauses and stops charging |
| Hot-shoe task (STB_EXTERNAL) | detects what is on the shoe, sends commands, reads its information |
| Flash timing block | hardware that times the flash pulses and signals the end with an interrupt |
| Serial channel 13 | the data link to the flash on the hot shoe |

*The parts of the flash system and what each one does.*

## Flash sequence

1. The exposure code passes the shutter speed, aperture, ISO, faces and the flash settings to the flash sequence.
2. The sensor captures a frame without flash. Then it captures one or two frames with a small pre-flash.
3. The camera compares the frames over the whole picture, the focus area and any faces.
4. It picks the pre-flash frame that measured best and works out the main flash power from the difference.
5. For a flash on the shoe it sends the power as a number over the serial link.
6. If the flash cannot give enough light, the camera can raise the ISO.
7. The timing block fires the main flash when the first shutter curtain has opened. For second-curtain sync it probably
   fires just before the second curtain.
8. The camera also adjusts white balance for the flash light.

## Hot-shoe link

The flash contacts carry a two-way serial link. The camera wakes the device, powers it and asks what it is. It knows
three kinds of device: a flash, a microphone and an LED video light. For a flash it reads the maker code, firmware and
hardware version and serial number. Commands include start, stop, charge, auto and manual power, and reading or
writing the flash's own memory. The link is fast enough to send a new flash firmware.

The exact electrical details are not in the program. The bit rate is probably about 20,800 bits per second. Watching
the pins with a logic analyser would settle it.

## Wireless RC flash

In RC mode the flash on the shoe is a commander. Before the pre-flash it sends a burst of light pulses with the channel,
the groups A to D and their modes. After metering it sends a second burst with the power for each group. Then the remote
flashes fire with the main exposure. The timing block probably holds a table of up to ten pulse steps for this.

## Debug commands

The camera has a flash debug command, `stbd`, in its maintenance shell. Some parts only read: `stbd state`,
`stbd qlog show`, `stbd fls_inf` and `stb ext 0`. Others fire the flash or write to it, so they are not safe to try.


## Open questions

- The pin-level protocol on the shoe.
- Where the program sets the fastest flash sync speed. The setting lives in the exposure mode record, but its writer
  was not found.
- How the shutter's sync step starts the timing block.

## Further reading

- [Flash and hot shoe: technical notes](flash-technical.md) has the modules, the timing block registers, the shoe
  commands and the address reference.
- [Shutter](shutter.md) covers the curtains the flash is timed against.
