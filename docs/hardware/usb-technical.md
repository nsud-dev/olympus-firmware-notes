# USB: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [USB](usb.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

This page covers the camera's USB hardware and the USB modes it can present to a computer, such as storage, Media
Transfer Protocol (MTP) and remote control. It matters mainly for the webcam work. The OM-5 can act as a USB webcam
through the USB Video Class (UVC). The E-M5 III can't, and this page records what its USB side has and lacks.

A USB device reports a vendor ID (VID) and a product ID (PID) so the computer knows what it is. Olympus's VID is
`0x07b4`, and each USB mode has its own PID.[^cam1] Tethering uses the Picture Transfer Protocol (PTP), which works
through numbered operations. The firmware calls its USB personality classes TPC.

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred.

## Controller

The USB controller is a Synopsys DWC3 (DWC_usb3). It sits at the same address on the E-M5 III, OM-5 and E-M1 III, so
the hardware is not what separates them.[^fw1]

The difference is in the driver.

- The E-M5 III driver supports bulk transfers and the control endpoint (EP0) only. It has no isochronous code.[^fw1]
- The OM-5 adds the isochronous path and the video and audio classes (UVC and UAC). That is about 78 OM-5-only
  functions, about 22 KB of code.[^fw1]
- The OM-5 and E-M1 III also have USB-C power delivery code and registers. The E-M5 III, with its micro-USB port, never
  touches them.[^fw1]
- The E-M5 III's endpoints are EP0, bulk OUT `0x05`, bulk IN `0x86` and interrupt `0x83`.[^fw1]

Video streaming normally uses isochronous transfers, which is why the missing path matters for a webcam.

## USB modes

Each mode reports its own PID under the Olympus VID.

| mode | PID | notes |
|---|---|---|
| Storage | `0x012e` | |
| MTP | `0x012f` | |
| camera control (camecon) | `0x0130` | enumerates as "Olympus E-M1". Every PTP operation returns `0x2005`.[^cam1] |
| hidden USB Mode value 1 | `0x0132` | a HID PC remote (zoom frame, AFL), not tethering[^cam1] |
| OM-5 webcam | `0x0139` | UVC. We made the E-M5 III announce it in webcam test 1.[^cam1] |

*USB modes on the E-M5 III and the PID each one reports.*

### From menu choice to device

A USB Mode menu choice passes through four stages before the computer sees a device.[^fw1]

1. The menu value is stored as an internal setting.
2. It is turned into a TPC class.
3. The TPC class picks a PID.
4. The PID picks a configuration descriptor.

Forcing camecon TPC 6 or 7 fell through to a junk PID, `0xf102`.[^fw1]

### Mode tables

| table | entries |
|---|---|
| USB Mode menu options | Auto 0, Storage 4, MTP 1, icon-only 2, Print 6, PCM Recorder 85 |
| debug console `usb tpc` | storage 0, mtp 4, camecon 7, print 1, pcmlink 8 |

*Mode numbers in the two firmware tables.[^fw1]*

A runtime filter hides some of the menu slots. We never found it.[^fw1]

## Tethering

There is no hidden tethered live view to unlock. Other OM-D bodies use PTP operations in the `0x948x` range for live
view and capture, and none of them are in the E-M5 III's firmware.[^cam2]

- An orphaned DeviceInfo list has vendor operations `0x9116` to `0x9125` and `0x902c` to `0x902f`.[^cam2]
- The PTP responder registers two vendor operations of its own, gated on a session flag. `0x94b5` receives a console
  line and runs it or posts it to the user shell. `0x94b6` returns the captured output. This is a lead only, because USB
  work is parked.[^fw2]

## Firmware update over USB

A USB firmware update is started by the main program itself. So it is not an independent rescue path for a camera that
won't start.[^fw1]

See also: [Recovery](../firmware/recovery.md).

## Tools

On macOS 15 and later, list USB devices with `system_profiler SPUSBHostDataType`. The older `SPUSBDataType` comes back
empty.[^cam1]

## Address reference

E-M5 III 1.7 addresses. Functions are block0 addresses (base `0x60021020`).

| item | address |
|---|---|
| DWC3 controller base | `0x98f0c000` |
| GCTL, DCFG, DCTL, DSTS | base + `0xc110`, `0xc700`, `0xc704`, `0xc70c` |
| DEPCMD for endpoint n | base + `0xc80c` + 16n |
| USB-C power delivery registers (OM-5, E-M1 III) | `0x98f10044` to `0x98f1004c` |
| OM-5 isochronous and UVC/UAC code | `0x60cd0000` to `0x60ce9000` (OM-5) |

*Controller and registers.*

| item | address |
|---|---|
| internal USB mode setting | `0x621de554`, written at `0x60c56ccc` |
| TPC class selection (api_comm) | `0x602d78b0`, `0x602d79b7` |
| PID selection (TPC_ON switch) | `0x6129ece5` |
| configuration descriptor dispatcher | `0x60c31082`, `0x60c31090` |
| USB Mode option table | `0x61074fd2` |
| debug console `usb tpc` table | `0x60e5c868` |
| PTP mode index | `0x6235a002` |
| PTP vendor operation gate flag | `0x62358c58` |
| orphaned DeviceInfo list 6 | `0x613ae1f6` |
| `start_usb_firmup` | `0x609ee601` |

*Functions, tables and variables.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware.
[^fw2]: Read in the firmware, 2026-11-05.
[^cam1]: Seen on our E-M5 III.
[^cam2]: Seen on our E-M5 III in USB test 4.

