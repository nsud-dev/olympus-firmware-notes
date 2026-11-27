# Sync IS with Panasonic lenses: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Sync IS with Panasonic lenses](sync-is-panasonic.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

Olympus bodies can combine their in-body stabiliser with the lens's own stabiliser on Olympus lenses. This is called
Sync IS. Panasonic lenses use Panasonic's own scheme instead, called Dual IS. So on an E-M5 III you get one or the
other. This page records why a simple patch can't switch Sync IS on for Panasonic lenses, and what routes might work.

The study of the idea is done. Nothing has been built.[^pol1]

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred.

## Patch limits

Sync IS is called "copt" internally, short for cooperative. It is reported by the lens, so a body-only flag patch
won't work.[^fw1]

1. The body checks that the lens sets function flag page 2 bit 3.[^fw1]
2. Only then does it ask the lens with Olympus private function 41.[^fw1]
3. It stores the reply in the copt flag.[^fw1]

Function 41 is a private function number, not a wire command.[^fix1] See
[lens communication](../hardware/lens-communication-technical.md#focus-aperture-zoom-and-is-drive) for the difference.

Panasonic lenses speak Panasonic Dual IS, not copt. So there's nothing in the body to flip.[^fw1]

## Panasonic lens detection

The body spots a Panasonic lens by its lens ID.[^fw1]

- The test reads the lens ID, `L_ID[6]`, at offset `0x444` in `lens_info`.[^fw2]
- It checks that byte 0 is 2 or 3 and byte 1 is 0.[^fw1]
- An ID of {0,0} selects the Olympus private function set. An ID of {2 or 3,0} selects the Panasonic one.[^fw2]
- The Panasonic status is `L_STAT_PANA`, bit 0 at offset `0x24d8` in `lens_info`.[^fw1]
- Non-Panasonic lenses branch off to a separate path.[^fw1]

See also: [lens_info](../hardware/lens-communication-technical.md#lens_info-what-the-body-knows-about-the-lens).

The stabiliser side of the body and lens split is on [stabiliser](../hardware/stabiliser.md).

## Possible routes

- **A.** Force the flag. Very low odds.[^inf1]
- **B.** Split the work. The lens's optical stabiliser (OIS) does yaw and pitch, and the body does roll. The best
  bet.[^inf1]
- **C.** Implement Panasonic Dual IS. A long project.[^inf1]

## Related work

A separate aperture-ring hack exists in azqeurio/om-c-firmware (dbv0.3.0). We read it to learn only and never copy it.
We credit it and point users there.[^pol2]

## Older bodies

The lens-communication strings this analysis used (`copt`, `L_STAT_PANA`) are absent from the E-M5 II 4.1 and the
E-M5 Mark I 2.3 firmware.[^fw3] So the E-M5 III findings here don't carry over. Any route would need its own study.

See also: [older bodies](../bodies/comparison-technical.md#older-bodies-e-m5-ii-and-e-m5-mark-i).

## Address reference

E-M5 III 1.7 block0 addresses (base `0x60021020`).

| item | address |
|---|---|
| private function 41 request | `0x600fd973` |
| send path | `0x602072f5` |
| function flag page 2 bit 3 check | `0x6020d42e` |
| copt flag | `0x620a688e` |
| copt flag get / set | `0x602075ce` / `0x602075d7` |
| Panasonic lens test | `0x6020d782` |
| Panasonic status `L_STAT_PANA` | `0x6020d094` |
| non-Panasonic branch | `0x6021012d` |

*Sync IS query, flags and Panasonic detection.*

| field | offset in `lens_info` |
|---|---|
| lens ID `L_ID[6]` | `0x444` |
| `L_STAT_PANA` (bit 0) | `0x24d8` |

*Lens fields the Panasonic test reads.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware.
[^fw2]: Read in the firmware, decoded 2026-11-25.
[^fw3]: Read in the E-M5 II and E-M5 Mark I firmware, 2026-11-21.
[^inf1]: Inferred. Not traced or tested.
[^pol1]: Study done 2026-11-01.
[^pol2]: Project decision, 2026-11-01.
[^fix1]: Corrected 2026-11-25.

## History

- 2026-11-25: function 41 was first read as a wire command. It is a private function number.

