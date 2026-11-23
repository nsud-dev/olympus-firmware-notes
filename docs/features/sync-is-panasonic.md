# Sync IS with Panasonic lenses

<!-- human page -->
> The dense reference for this page is [Sync IS with Panasonic lenses: technical notes](sync-is-panasonic-technical.md).

With an Olympus stabilised lens, the E-M5 III can run the lens's stabiliser and its own in-body stabiliser together.
Olympus calls this Sync IS. Panasonic lenses use Panasonic's own scheme, called Dual IS. So on an E-M5 III with a
stabilised Panasonic lens you get one stabiliser or the other, never both.

This page explains why a simple patch cannot change that, and which routes might.

## Status

The idea has been studied. Nothing has been built.

## Why a simple patch will not work

It is the lens that tells the body whether it can do Sync IS. At start-up the body asks the lens, and stores the answer.
An Olympus lens answers yes. A Panasonic lens does not understand the question in that form, because it speaks Dual IS.

So there is no switch in the body to flip. Forcing the answer to "yes" would make the body try to cooperate with a lens
that does not know how.

## Possible routes

1. **Force the flag.** The body would believe the lens can cooperate. Very unlikely to work.
2. **Split the work.** Let the lens's stabiliser handle up-down and left-right tilt, and let the body handle rotation.
   This is the most promising route.
3. **Speak Dual IS.** Teach the body Panasonic's protocol. That would be a long project.

## Other cameras

The E-M5 II and the original E-M5 do not have the lens-communication code this study relied on, so any attempt there
would need its own study.

## Related work

A separate project, om-c-firmware by azqeurio, has an aperture-ring hack for Panasonic lenses. It is worth reading for
ideas.

## Further reading

- [Image stabiliser](../hardware/stabiliser.md) explains how the body and lens share the stabilising work.
