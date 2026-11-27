# C++ shooting layer

<!-- human page -->
<!-- house style -->

## Key points

- The upper half of the shooting code is a tree of about 225 C++ classes, stacked in five layers.
- A shooting component handles still photos, with a small "sequence parts" object for features such as Pro Capture and
  bracketing.
- Taking a picture sends a message to the C shooting sequencer's queue, and the result comes back as an event.
- The OM-5 II has the same framework, and it adds sequence parts for Live ND and Handheld High Res.

The camera's shooting code has two halves. The lower half is hand-written C that drives the shutter, sensor and image
pipeline. The upper half is C++ that was generated from UML models (see [Rhapsody and OXF](../guides/rhapsody-and-oxf.md)).
It decides what the camera should do when you press a button.

This page describes that upper half for the E-M5 III 1.7 firmware and compares it with the OM-5 II 1.1. Everything here
comes from reading the firmware. Nothing was run on the camera.

## Class recovery

C++ objects keep a pointer to a table of their methods, called a vtable. Each class constructor writes its table's
address into the object, after first calling the constructor of the class it inherits from. Following those
constructor calls gives the family tree. All the classes descend from one framework class.

Olympus left the source file name of every class in the firmware for error messages. Those names sit right in front of
each file's tables, which gives every class its name.

## Layers

| layer | example classes | job |
|---|---|---|
| Camera | camera base | the whole application |
| Mode | shoot mode, play mode, function mode | which big mode the camera is in |
| Category | still image shooting, display, function | which group of screens is active |
| Component | still shooting component, player component | one screen's behaviour, such as shooting stills |
| Capability | take, record, buffer manager, flash, AE/AF control, movie recorder | services the components use |

*The five layers of the C++ shooting code, from the top down.*

Each layer has a "switcher" that starts and stops the objects in the layer below. All of them inherit from one
transition base class, which in turn inherits from the framework's reactive object. So every one of them is a small
state machine that reacts to events.

Hundreds of tiny "observer" classes sit next to these. Each one only passes on a single notice, such as "take
complete" or "AF locked".

## Sequence parts

The still shooting component handles the half-press, the full press, continuous shooting, errors and so on. Features
that need different behaviour plug in a sequence parts object. The component picks one by number when the shooting mode
changes. The part replaces only the handlers it needs. Picture bracketing changes about 10, Pro Capture about 150.

| E-M5 III parts | OM-5 II parts |
|---|---|
| plain shooting, one-touch white balance, picture bracketing, panorama, e-Portrait, 3D, multiple exposure, photo session, AF fine tune, Pro Capture | the same without 3D and photo session, plus Live ND and Handheld High Res |

*Sequence parts on the two bodies.*

The part is picked from the current settings in a fixed order. Multiple exposure wins first. Then come AF fine tune,
one-touch white balance, e-Portrait, panorama and picture bracketing. Pro Capture comes last. On the OM-5 II, Handheld
High Res and Live ND are checked after Pro Capture. If nothing matches, the plain part is used.

The numbers that select a part differ between the two firmwares. On the OM-5 II, Live ND and Handheld High Res change
only 14 and 15 handlers. Most of their work is done further down, in the C code.

## Take-picture path

When you take a picture, the C++ side does not call the C code directly.

1. The app event task receives the button press and passes it to the C++ objects.
2. The take capability's "take picture" method builds a request and calls the recording interface written in C.
3. That interface puts the request into the C shooting sequencer's message queue as event 11.
4. The [shooting sequencer](shooting-sequencer.md) picks it up and runs its own states: focus, exposure, capture,
   development and saving.
5. Results come back to the C++ side as app events.

The OM-5 II takes the same route through the same interface. It differs in its feature list. It adds parts for Live ND
and Handheld High Res, and drops 3D and Photo Session.

## Open questions

- The names of three OM-5 II settings that select parts.
- Which events come back to the C++ side.
- What the framework's own table slots do.

## Further reading

- [C++ shooting layer: technical notes](cpp-shooting-layer-technical.md) has the class tree, the part tables and every
  address.
- [Shooting sequencer](shooting-sequencer.md) covers the C half below.
- [Rhapsody and OXF](../guides/rhapsody-and-oxf.md) explains the framework the classes come from.

