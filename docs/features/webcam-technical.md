# USB webcam: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [USB webcam](webcam.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

The OM-5 has a built-in USB webcam mode, and the older E-M5 II could be used as a webcam. The E-M5 III can't. This was
the first feature the project tried to bring over.

The work is parked.[^pol1] Webcam test 1 passed, so the camera enumerates as a webcam. Test 2c passed too, so it
streams its own picture and survives a replug. Streaming the real live view failed, because the camera turns its
shooting pipeline off while USB is connected.[^cam3] Fixing that would be a large change. The lower
part of section 9 stays reserved for it (see [Address reference](#address-reference)).[^pol1]

A webcam speaks the USB Video Class (UVC), the standard webcam protocol. Sound uses the USB Audio Class (UAC). USB has
several transfer types. Webcams normally stream with isochronous (iso) transfers, and files use bulk transfers. The
movie recorder module (MVR) records movies. The product ID (PID) tells the computer which kind of USB device it sees.

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred or a decision.

## Starting point

The E-M5 III never had USB webcam support, so it has to be ported.[^cam1]

- camecon (PID `0x130`) has no command handler.[^cam1]
- The orphaned PTP mode 6 does file and remote operations only.[^cam1]
- There are no OM-D live-view operations (`0x948x`).[^cam1]

See also: [USB: technical notes](../hardware/usb-technical.md).

## The OM-5 webcam

The donor is the OM-5 1.2. Its native webcam is UVC 1.0, sending Motion JPEG (MJPEG) at 1280 × 720 and 29.97 or
25 fps.[^fw1]

- Video goes out on isochronous endpoint `0x85` (3 × 1024).[^fw1]
- Sound is UAC1 stereo at 48 kHz on endpoint `0x86`.[^fw1]
- The link protocol is `LINK_PROTOCOL_WEB_CAMERA = 8`, and the PID is `0x139`.[^fw1]
- The frames come from the movie recorder through a ring of 6 slots.[^fw1]

## Streaming over bulk

The E-M5 III's DWC3 USB driver has no isochronous path. So the tests streamed over bulk IN endpoint `0x86`, which UVC
allows.[^fw1]

## Tests and results

Tests 2 to 2d were built with another tool. We reviewed them and checked the bytes.

| test | what | result |
|---|---|---|
| webcam test 1 | PID `0x139` and a UVC configuration descriptor, through a wrapper | **passed**. The Mac lists a UVC camera.[^cam3] |
| tests 2, 2b and 2c | probe and commit, SET_INTERFACE, bulk stream of a fixed 160 × 120 JPEG. 2b fixes the status mask. 2c ends the transfer on reset. | **2c passed**. The camera's own picture comes over UVC and survives a replug.[^cam3] |
| test 2d | pacing with a native 34 ms timer | 21.6 fps[^cam3] |
| live-view test 2 | the native movie USB output, 320 × 240 JPEG | **failed**. Photo Booth froze, and the camera shows "One moment...". The USB-connected state turns the shooting pipeline off.[^cam3] |

*The webcam tests on our E-M5 III and their results.*

The host log shows what the Mac did.[^cam2]

- On the first open the camera streams unpaced, at about 2,400 fps. Many packets are dropped as `MissingFIDFlip`.
- When Photo Booth is reopened, the host never calls startStream. So the black picture is on the host side.
- An app restart or a sleep needs the camera deselected and reselected.
- The picture appeared only in movie mode.

Review found three bugs, which were then fixed.[^cam3] They were the DEPEVT status mask, the missing EndTransfer on
reset or disconnect, and the pacing gate, which has to equal the period.

See also: [Gotchas](../reference/gotchas.md).

## Timing

- The firmware clock counts in 1 µs steps.[^fw1]
- The timer create call takes milliseconds.[^fw1]
- In test 2d, a native periodic timer of type 128 sends USB message `0x03fe0001`, which reaches a detour in the USB
    worker.[^fw1]

## What a fix would need

A fix would need the camera to stay in shooting mode while USB is connected. That is large work on the user interface
and its states. The best states flashed so far are test 2d and test 2c.[^cam3]

Without a firmware change, the Wi-Fi live view (OI.Share `remocon`) could feed a virtual webcam on the Mac.[^inf1]

## Other bodies

UVC interface descriptors (video control and streaming) are in block0 of the OM-5 1.2, the OM-5 II 1.1 and the
OM-1 II 1.3, with `WEB_CAMERA` strings.[^fw2] The E-M1 III 1.6, OM-1 1.9 and PEN-F 3.1 have neither. Any webcam use
on those goes another way, which has not been checked.[^fw2]

The E-M5 II 4.1 has no UVC descriptors, the same as the PEN-F. Its PC tether code (`camecon`) is present.[^fw3] See
[older bodies](../bodies/comparison-technical.md#older-bodies-e-m5-ii-and-e-m5-mark-i).

See also: [Body comparison](../bodies/comparison-technical.md#our-features-on-the-other-bodies).

## Address reference

E-M5 III 1.7 addresses unless the OM-5 is named. Functions are block0 addresses (base `0x60021020`).

| item | address |
|---|---|
| reserved for the webcam (lower section 9) | `0x613bb000` to `0x613d4000` |
| test 1 descriptor wrapper | `0x613bb000` |
| clock, 1 µs | `0x60022e5c` |
| timer create | `0x6006be97` |
| USB worker detour (test 2d) | `0x60c2e2d6` |

*E-M5 III addresses used by the webcam tests.*

| item | address |
|---|---|
| UVC descriptors | `0x60f76da4` |
| descriptor builder | `0x60cdb87f` |
| movie recorder frame ring | `0x60ce02cb`, `0x60ce0304`, `0x60ce0374` |

*OM-5 1.2 webcam addresses.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^pol1]: Project decision, 2026-10-20.
[^cam1]: Seen on our E-M5 III in USB tests 1 to 4.
[^cam2]: Seen on our E-M5 III, host log `uvc.log`, 2026-10-20.
[^cam3]: Seen on our E-M5 III.
[^fw1]: Read in the firmware.
[^fw2]: Read in the firmware, 2026-11-20.
[^fw3]: Read in the firmware, 2026-11-21.
[^inf1]: Inferred, not tried.

