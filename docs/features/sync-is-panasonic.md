# Sync IS with Panasonic lenses

Olympus bodies can combine their in-body stabiliser with the lens's own stabiliser ("Sync IS") on Olympus lenses.
Panasonic lenses use Panasonic's own scheme instead (Dual IS), so on an E-M5 III you get one or the other. This page
records why a simple patch can't switch Sync IS on for Panasonic lenses, and what routes might work.

**Status:** study of the idea done (2026-11-01); nothing built. Doc: (private link)

Tags: **[code]** read in the firmware, **[inferred]** not traced or tested.

## Why a body-only flag patch won't work

Sync IS ("copt", short for cooperative, internally) is reported **by the lens**. The body asks with lens command 41
(0x600fd973 calls 0x6020d42e) and stores the reply in the copt flag 0x620a688e (get 0x602075ce / set 0x602075d7).
Panasonic lenses speak Panasonic Dual IS, not copt, so there's nothing in the body to flip. [code]

How the body spots a Panasonic lens: the test at 0x6020d782 checks lens_info+0x444 byte0 ∈ {2,3} and byte1 ≠ 0 (the
meaning is guessed). The Panasonic status is 0x6020d094 (`L_STAT_PANA`). Non-Panasonic lenses branch off at 0x6021012d.
[code] The stabiliser side of the body/lens split is on [stabiliser](../hardware/stabiliser.md).

## Possible routes [inferred]

- **A.** Force the flag. Very low odds.
- **B.** Split the work: the lens's OIS does yaw and pitch, the body does roll. The best bet.
- **C.** Implement Panasonic Dual IS. A long project.

A separate aperture-ring hack exists in azqeurio/om-c-firmware (dbv0.3.0). Read it to learn only, never copy; credit it
and point users there.
