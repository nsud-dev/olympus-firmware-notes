# USB

<!-- human page -->
<!-- house style -->

## Key points

- The E-M5 III, OM-5 and E-M1 III have the same USB controller. The difference is in the software.
- The E-M5 III's driver can't stream video, so it can't act as a webcam the way the OM-5 can.
- There is no hidden tethered live view to unlock on the E-M5 III.
- We study the USB side but don't build changes to it.

This page covers the camera's USB hardware and the different devices it can appear as when plugged into a computer. It
matters mainly for the webcam work, because the OM-5 can act as a USB webcam and the E-M5 III cannot.

## Controller

The USB controller is a standard Synopsys design, at the same address on the E-M5 III, OM-5 and E-M1 III. The difference
is in the software. The E-M5 III's driver handles only bulk transfers, the kind used for files. Video normally uses a
different kind, isochronous transfers, and the OM-5's driver adds that, along with the webcam and audio classes.

The OM-5 and E-M1 III also have code for USB-C power delivery. The E-M5 III has a micro-USB port and never uses it.
The OM-5 has a micro-USB port too, so its copy is inherited from the E-M1 III. The OM-5 II adds the USB-C hardware.

## USB modes

Each USB mode makes the camera report a different product number, so the computer knows what kind of device it is.

| mode | what the computer sees |
|---|---|
| Storage | a memory card reader |
| MTP | a media device |
| camera control | a camera, but it answers no commands |
| a hidden mode | a simple PC remote control, not tethering |
| OM-5 webcam | a webcam. We made the E-M5 III announce itself this way in the webcam tests. |

*The USB modes and what a computer sees for each.*

There is no hidden tethered live view to unlock. The commands other OM-D bodies use for it are not in the E-M5 III's
firmware.

A firmware update over USB is started by the main program itself, so it is not an independent rescue path.

## Status

Read-only. We analyse the USB side but do not build changes to it.

## Further reading

- [USB: technical notes](usb-technical.md) has the controller registers, the product numbers and the mode tables.
- [USB webcam](../features/webcam.md) describes the webcam tests.
- [Recovery](../firmware/recovery.md) explains why USB updates are no rescue for a camera that will not start.
