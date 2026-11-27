# Subject detection

<!-- human page -->
<!-- house style -->

## Key points

- Face and eye detection on the E-M5 III is the same as on the OM-5 and OM-5 II, so there is nothing to port.
- A few face and autofocus options from the OM-5 are ordinary code that could be brought over.
- Subject detection for birds, animals and vehicles needs a neural network and hardware the E-M5 III does not have.
- A menu string or setting name alone does not prove that a feature exists.

Newer OM System bodies can recognise birds, animals and vehicles, and they offer more face and eye options than the
E-M5 III. This page sorts those features into three groups. Some are already on the E-M5 III, some could be ported,
and some need newer hardware.

## Already there

Face and eye detection on the E-M5 III is the same as on the OM-5 and OM-5 II. There is nothing to port.

## Could be ported

These OM-5 options are missing from the E-M5 III, but they are ordinary code that could be brought over.

| feature | size of the job |
|---|---|
| Face Selection, picking which face to follow by touch | small to medium |
| Face priority release | small |
| C-AF Center Start and Center Priority | medium, because it touches the autofocus sequence |
| the newer subject tracker | large, it would replace the old tracker in a region of its own |

*OM-5 options missing from the E-M5 III, with the size of each port.*

The plan, if this goes ahead, starts with face selection and face priority, then the C-AF centre options, and only then
a study of the tracker swap.

## Needs newer hardware

Subject detection for birds, animals and vehicles uses a neural network. On the OM-1 it runs on an extra processor
core and a dedicated AI hardware block, with several large files of network weights. The E-M5 III has neither.

The E-M1 III, OM-5 and OM-5 II carry pieces of the subject-detection code, left over from a shared code base. None of
them has the network itself or its weights. Their menus show the subject names because the menu text is shared across
the range. The OM-5 II's menu offers only face and eye detection.

So subject detection cannot be ported to the E-M5 III. Among Olympus and OM System bodies, only the E-M1X and the OM-1
family have it.

## Other cameras

The E-M5 II and the original E-M5 have face and eye detection, as the E-M5 III does. Neither has any subject-detection
code. The portable options above have not been checked on them.

## Menu text and code

A setting name or a menu string is not a feature. Before treating something as portable, confirm there is reachable
code behind it, or run the menu in the emulator.

## Status

Research is done. Nothing has been built.

## Further reading

- [Subject detection: technical notes](af-detect-technical.md) has the code names, the weight search and the address
  reference.
- [Face and eye detection](face-detect.md) explains how the existing face detector works.
- [Body comparison](../bodies/comparison.md) lists what each camera has.
