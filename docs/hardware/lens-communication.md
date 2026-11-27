# Lens communication

<!-- human page -->
<!-- house style -->

## Key points

- The body talks to the lens through a serial controller in the main chip that does nothing else.
- Every message starts with two bytes, one for the kind of message and one for the command.
- When a lens is attached, the body keeps a record of about 113 KB about it, with Olympus's own field names.
- The OM-5 II uses the same lens commands and the same lens record.

A Micro Four Thirds lens has its own small processor. The camera body talks to it through the contacts on the lens
mount. The body asks the lens what it is and how it behaves. It then tells the lens where to focus, how far to close
the aperture and, on power zoom lenses, where to zoom.

This page explains how the E-M5 III does that. The link, the command list and the lens record are mapped. The focus,
aperture and zoom calls are named, from the camera's own debug help. Nothing was tested on the camera yet.

## Link

The main chip has a serial controller that does nothing but talk to the lens. Only one small group of functions
touches it.

- The same controller also talks to a lens adapter, such as a Four Thirds adapter. The body switches between the two.
- Each message starts with two bytes. The first byte says what kind of message it is. The second says which command
  it is.
- The kind decides the message format. Some messages only send. Some send and wait for a reply. Some ask the lens for
  a block of data.

## Requests

A part of the camera that needs the lens fills in a small request form. It puts the form in the lens queue. The lens
code sends it and calls back when the lens has answered.

Two lens tasks run all the time. One answers requests from the rest of the camera. The other reads data from the
lens.

## Commands

The firmware has a table of 130 lens commands for its debug shell. It is the best list we have. The commands fall into
these groups.

- **Ask data.** Read the lens status or a block of its stored data.
- **Focus.** Move to an absolute position, move by an amount, or scan.
- **Aperture.** Open fully or set a target value.
- **Power zoom.** Zoom in or out at one of eight speeds, or to a set focal length.
- **Live view packet.** One message per live view frame that carries the next focus move.
- **Private commands.** Extra commands for Olympus lenses, used for lens stabilisation and Sync IS.

Focus has more than one style. In live view the body moves focus a little on every frame, in step with the sensor.
Outside that rhythm it sends single moves. Some lenses have two focus groups, and these get their own commands.

## Lens record

When a lens is attached, the body fills in a large record about it. It is about 113 KB. The debug shell can print it
in 38 sections. Each field has the name Olympus gave it.

- **Identity.** The lens ID, name, serial number and firmware version.
- **Optics per zoom step.** Focal length and the widest and smallest aperture.
- **Focus.** Where the focus limits are, how fast focus can move, and how focus shifts as you zoom.
- **Stabilisation.** Data that the body's stabiliser needs, and whether the lens can share the work (Sync IS).
- **Image correction.** Distortion, chromatic aberration, shading and sharpness data. The camera uses these to
  correct photos and writes some of them into the EXIF.
- **Feature flags.** One byte or word per feature the lens offers, such as power zoom.

The first two bytes of the lens ID tell the body which family the lens belongs to. One value means Olympus. Two other
values mean Panasonic. The body uses this to choose Olympus or Panasonic extras.

## Corrections to earlier notes

- The lens ID bytes in the lens record are the start of the lens ID. Earlier notes called their meaning a guess.
- The Sync IS question the body asks is a private function number, 41. It is not a plain lens command. The body only
  asks it when the lens says it supports it.

## Status

The OM-5 II uses the same lens code. Its command list and lens record are identical. No camera test has been run yet.
A read-only check over the Wi-Fi debug shell is the next step.

## Further reading

- [Lens communication: technical notes](lens-communication-technical.md) has the wire commands, the request types, the
  lens record layout and the address reference.
- [Image stabiliser](stabiliser.md) covers how body and lens share stabilisation.
- [Autofocus](../features/autofocus.md) covers how AF decides where to focus.
- [Sync IS with Panasonic lenses](../features/sync-is-panasonic.md) uses the lens family check.
