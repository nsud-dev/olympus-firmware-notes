# Geotagging and the hot shoe

<!-- human page -->
<!-- house style -->

## Key points

- The stock E-M5 III can already geotag photos after the fact, from a GPS track that the phone app records and sends
  over Wi-Fi.
- Real-time geotagging over Bluetooth is a feature of the OM-5 and newer bodies, and bringing it to the E-M5 III is
  feasible but a big job.
- The hot shoe has a data link, but it is the flash's serial bus, not an accessory port.
- A GPS receiver on the hot shoe would be the hardest and riskiest route, and it would take the shoe away from a flash.

This page asks whether the hot shoe can carry a link to a peripheral such as a GPS receiver, so photos get geotagged.
On the way it looks at the GPS support already in the E-M5 III firmware and at how newer bodies get their location
from the phone. It is read-only research, from the firmware. Nothing was built or flashed for it.

## Geotagging today

The E-M5 III already geotags, the slow way. The OI.Share phone app records a GPS track. The phone then sends the track
to the camera over Wi-Fi. The camera matches its photos to the track and writes the location into each
matching photo itself. This works for JPEG, raw (ORF) and MPO files. It needs no changes, so it is the first thing to
try.

The firmware also carries a GPS framework from the Tough series of cameras, which have a GPS module built in. It is
dormant on the E-M5 III, which has no GPS module. It is the camera-side interface a GPS source would feed, not a driver
that can be used as it is.

## Bluetooth location in newer bodies

| body | real-time Bluetooth location |
|---|---|
| E-M5 III | no |
| E-M1 III | no |
| OM-5 | yes |
| OM-5 II | yes |
| OM-1 and OM-1 II | yes |

*Which bodies can take their location from the phone over Bluetooth, read in each body's firmware.*

On the OM-5 the phone app, OM Image Share, sends its position over Bluetooth while the camera shoots. The camera writes
it into each photo when the photo is taken. It records latitude and longitude only, with no altitude and no GPS time.

The OM-5's Bluetooth chip most likely only passes the position along, and the main processor reads it. The E-M5 III already has the
part that writes the location into the photo's metadata. It lacks the part that receives the position and stores it.
The OM-5 has the same main processor and the same Bluetooth chip, so the port is feasible. It shares much of its work
with porting the OM-5's Bluetooth remote control (RM-WR1).

## The hot shoe

The E-M5 III has no accessory port. The original E-M5 and older PENs had an extra connector under the shoe for add-ons
such as the VF-2 viewfinder, the SEMA-1 microphone adapter and the PP-1 Penpal. The E-M5 III, OM-5 and E-M1 III
firmware show no sign of one.

The shoe's flash contacts do carry a two-way serial link. Over it the camera recognises what is attached and reads its
maker, version and serial number. It knows three kinds of device: a flash, an external microphone and an LED video
light. It can even update a flash's firmware over the shoe. The same code is in the OM-5, OM-5 II, E-M1 III, OM-1 and
OM-1 II.

The protocol on the pins is not documented. A GPS on the shoe would need custom hardware that speaks it, and a new
device type in the firmware.

## Routes

| route | what it needs | effort | risk |
|---|---|---|---|
| OI.Share track over Wi-Fi | nothing, it is built in | none | none |
| Bluetooth location from the OM-5 | the OM-5's Bluetooth receiving side, a place to store the position, and writing it at capture | big | medium. The location still depends on the phone. |
| GPS on the hot shoe | custom hardware and the flash protocol worked out | biggest | wrong signal levels on the shoe pins could damage the body, and the shoe is no longer free for a flash |
| matching a GPS track on a computer afterwards | a desktop tool | none in the camera | none |

*Four ways to get geotagged photos from the E-M5 III.*

The Bluetooth route is the one we would take if the Wi-Fi method is not good enough.

## Older bodies

Bluetooth geotagging can't come to the E-M5 II or the original E-M5. The E-M5 II has only an older kind of Bluetooth
and no ARM coprocessor. The original E-M5 has no radio code in its firmware.

## Status

Research. The built-in Wi-Fi method has not been tried on our E-M5 III yet. The Bluetooth port is planned.

## Further reading

- [Geotagging and the hot shoe: technical notes](geotagging-and-hotshoe-technical.md) has the firmware names, the
  Bluetooth trace and the addresses.
- [Flash and hot shoe](../hardware/flash.md) describes the shoe's serial link.
- [ARM coprocessor](../hardware/arm-coprocessor.md) covers the Bluetooth chip.
- [Wi-Fi debug shell](wifi-debug-shell.md) lists the read-only shoe commands.
- [Body comparison](../bodies/comparison.md) covers the older bodies.

