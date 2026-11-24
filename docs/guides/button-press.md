# Buttons

*Guide 7 · E-M5 III firmware 1.7 · draft 1, 2026-11-19. New to these guides? Read
[Before you start](before-you-start.md) and [Operating system](operating-system.md) first. Open questions:
research gaps.*

This guide follows a button from the moment its contact closes to the moment the camera's application code hears
about it: the interrupt, the key image, the task that decodes it into an event, and the queue that carries the event to
the application. It ends with a stock way to press buttons over Wi-Fi, which we use for testing.

The path up to the application's event queue is traced in the code. What happens after that depends on the screen
you're on, and the step from "half-press event" to the shooting sequencer is still open.

## Overview

```
key contact ──► key-line interrupt ──► callback updates the key image, wakes UI_IN
                                                         │
                                       UI_IN task: compare old and new image
                                                         │
                                  app event "key 0x100 pressed" (half-press)
                                                         │
                                 app event queue ──► HLS_EVENT task ──► application
                                                                       (menu, playback, shooting)
```

## 1. Key lines and groups

The buttons are not scanned one at a time. They are wired to several kinds of inputs, and the firmware treats each kind
as a **group** with its own bit image, one bit per key:

| group | what it covers |
|---|---|
| gio | most push buttons, on general-purpose input lines (three bytes of bits) |
| adc | keys read through an analogue input (several keys share a line, told apart by voltage) |
| dial | the mode dial position |
| ext | keys on an external input chip |
| power | the power switch, read through the always-on [power block](../hardware/power-block.md) (wake input 0) |

Each key has a 4-letter name and a number in a table. Some examples: `Trg1` (0x100) is the shutter button half-pressed,
`Trg2` (0x101) fully pressed, `Ok` (0x4), `Menu` (0x89), `Play` (0x87), `Info` (0x1205). Cables, card doors and the
lens show up as "keys" too (`UsbC`, `Hdmi`, `LnsC`), which is why the same module also reports a lens change.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| group table | 0x601b8320, 12-byte records {entry lists, image, bytes, bits, count} | [code] |
| bit images | power 0xa2652f38, gio 0xa2652f34, adc 0xa2652f2c, dial 0xa2652f2d, ext 0xa2652f30 | [code] |
| key names and codes | 0x60251248 | [code] |
| which physical button each `Cut` code is | needs `ui key debug` on the camera | open |

Sources: [Wi-Fi debug shell: simulated button presses](../features/wifi-debug-shell-technical.md#simulated-button-presses).
</details>

## 2. The interrupt

When a key line changes, the hardware raises an interrupt. The handler reads which channel fired, clears it, and calls
the function that was registered for that channel. For the push buttons, that function belongs to the key module
(called UI_IN). It updates the group's bit image and sets a bit in UI_IN's event flag.

That is all it does. The interrupt doesn't decide what the key means, doesn't log, and doesn't wait for anything. It
records the new state and wakes the task that will deal with it (see [interrupt context](operating-system.md#5-interrupts)).

The analogue keys and the power switch use their own drivers, but they end the same way: a callback that updates the
group's image and sets UI_IN's flag. Registering the power-switch callback takes one of the
[cross-core lock bits](cores.md#3-lock-bits), so that driver is shared between cores.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| key-line interrupt block | 0x9bd00000 (channels at +0x00 and +0x80, status +0x08 / +0x88) | [code]; GPIO edge block [inferred] |
| interrupt handler | 0x601231e0, callbacks from table 0x620b2860 | [code] |
| register a callback | 0x601230ab | [code] |
| UI_IN's push-button callback | 0x60120011 (registered at 0x6011faf1) | [code] |
| analogue key callbacks | 0x60121305 / 0x601213bd | [code]; "adc" [inferred] |
| power key callback | 0x60121f0d (via 0x60063d13, lock 8) | [code] |
| UI_IN event flag | u16 at 0x60040dd4, bit 0 | [code] |

Sources: [Wi-Fi debug shell: from the key line to the app](../features/wifi-debug-shell-technical.md#simulated-button-presses).
</details>

## 3. The UI_IN task

UI_IN is an ordinary task that spends its life waiting on its event flag. When the interrupt sets the bit, the task
wakes, clears the flag, and runs the key decoder. Then it handles the dials, and goes back to waiting.

The decoder compares each group's new image with the previous one. Every bit that changed becomes an **app event**,
a 32-bit number made of a kind and the key code:

| event | meaning |
|---|---|
| 0x2000000 + code | key pressed |
| 0x2010000 + code | key released |
| 0x2020000 + code | value changed (the mode dial: the code plus its new position) |

One rule is built in here. If a full press of the shutter button (`Trg2`) arrives without a half-press before it, the
decoder sends the half-press (`Trg1`) first. So the rest of the camera can assume a full press always comes after a
half-press, however quickly the button was pushed.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| UI_IN task loop | 0x6011f9d8 (wait, clear, decoder 0x6012092f, jog 0x6011fb2d) | [code] |
| key dispatcher (events, half-press first) | 0x60120ad3 | [code] |
| event kinds | 0x2000000 / 0x2010000 / 0x2020000 + code | [code] |

Sources: [Wi-Fi debug shell](../features/wifi-debug-shell-technical.md#simulated-button-presses).
</details>

## 4. Dials

The front and rear dials don't have on/off contacts. They produce pulses as they turn. A separate jog driver counts the
pulses and sends an app event of a fourth kind (0x2030000 + dial code, with the step count). UI_IN's loop services the
jog driver after the keys.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| send a dial event | `JOG_SendEvent` 0x6011fe86 (0x2030000 + 0x1902 / 0x1903) | [code] |
| how the pulses are counted (timer, interrupt) | not traced | open |

Sources: [Wi-Fi debug shell](../features/wifi-debug-shell-technical.md#simulated-button-presses).
</details>

## 5. The app event queue

Every app event, from keys, dials or elsewhere, goes out through one function. It packs the event into a small
12-byte message and writes it to the **app event queue**, an operating-system queue. A task called HLS_EVENT reads that queue
and hands each event to the application layer.

From here the meaning depends on what the camera is doing. In a menu, `Up` moves the cursor. In playback, it may step
through images. In shooting mode, a half-press starts focusing and metering.

```
pseudocode, written from the disassembly (0x60046008, 0x602e39b9; byte-matching C waits for the decompile)

post_app_event(event, argument):
    (a few events are dropped in one special mode; meaning open)
    message = allocate 12 bytes: {source, event, argument}
    write the message to the app event queue, no timeout
```

The same queue is used by many of the application's service modules (recording, playback, display), so a key event
waits its turn among other kinds of events.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| post an app event | 0x60046008 → 0x602e39b9 (`OlyQeWrCpu`) | [code] |
| app event queue | queue id u16 at 0x60040f24 | [code] |
| reader | `appevent::Wait_Event` 0x602e2f49, `Wait_ExecuteEvent` 0x602e32f6 (HLS_EVENT task) | [code] |
| dropped events | 0x40d00b5 / 0x40d00b6 while byte 0xa25b897e = 119 | [code]; meaning open |

Sources: [Wi-Fi debug shell](../features/wifi-debug-shell-technical.md#simulated-button-presses).
</details>

## 6. After a half-press

In shooting mode, the half-press is where [Taking a photo](taking-a-photo.md) begins. The shooting sequencer leaves Idle,
runs the focus and exposure states, and then waits in **RdyTrig2Wait** for the full press, which moves it on to the
capture.

The exact route from the half-press app event to the sequencer's first state change (which component sends what, on
which queue) hasn't been traced yet. It is the same open question as the hand-over from the generated C++ layer to the
sequencer in the photo guide.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| sequencer waits for the full press | state RdyTrig2Wait (5), event 18 | [code] |
| release seen during capture prep | byte 0x62110640 | [code] |
| app event → sequencer route | not traced | open |

Sources: [shooting sequencer](../firmware/shooting-sequencer.md), [Live ND](../features/live-nd.md).
</details>

## 7. Simulated key presses

The user shell has a `ui key` command that works at the key-image level. `ui key skey <code> 1` sets the key's bit in
its group image and wakes UI_IN, exactly as the interrupt would. `ui key skey <code> 0` releases it. Everything from
section 3 onwards then runs as for a real press. `ui key debug 1` prints every app event as it is sent, which is the
easiest way to find out which code a physical button makes.

Since the shell is reachable over Wi-Fi from a stock card file, this gives a way to press buttons remotely for testing.
Always send the release. Never send the codes for power, cables, the card or the lens, which would
fake those events.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| `ui` command / `key` sub-commands | 0x61408cf3 / 0x61408f79 | [code] |
| set a key | 0x60120327(code, state) | [code] |
| tried on the camera | not yet | open |

Sources: [Wi-Fi debug shell](../features/wifi-debug-shell-technical.md#simulated-button-presses), remote test rig.
</details>

## Our features

- **Live ND quick tap.** An armed Live ND shot that was released too early hung in the capture-prep state. The release
  arrived before the "full press seen" event the port expected. The fix handles the release events in that state. Lesson:
  any feature that hooks the shutter path must handle a press that ends sooner than expected.
- **Loading on the first half-press.** The planned looks feature loads its card file on the first half-press after
  power-on, in the HLS_EVENT task's event loop, where blocking on a file is allowed.
- **Our own settings page** receives the menu key events through the screen's handlers, the same way a stock menu page
  does.

## Other cameras

Each step checked against the firmware of other bodies. Nothing is assumed. "Not checked" means we don't know.

| step | E-M5 III 1.7 | OM-5 1.2 | E-M1 III 1.6 | OM-5 II 1.1 | OM-1 1.9 | PEN-F 3.1 | other projects |
|---|---|---|---|---|---|---|---|
| key names (`Trg1`, `Trg2`, ...) | yes | **confirmed** | **confirmed** | **confirmed** | **confirmed** | **confirmed** | fenykl: same key codes on E-M10 II |
| key-line interrupt block 0x9bd00000 | yes | **confirmed** (address used) | **confirmed** (address used) | **confirmed** (address used) | **different**: not used | **confirmed** (address used) | — |
| jog driver (`JOG_SendEvent`) | yes | **confirmed** | **confirmed** | **confirmed** | **confirmed** | **different**: name not found | — |
| HLS_EVENT task, `appevent::Wait_Event` | yes | **confirmed** | **confirmed** | **confirmed** | **confirmed** | **confirmed** | OM-5 II (Atlas-linked project): first-half-press work done in the HLS_EVENT task |
| half-press sent before a lone full press | yes | not checked | not checked | not checked | not checked | not checked | — |

"Confirmed" here means the names or the address are present. The code around them wasn't checked.
[Wi-Fi debug shell](../features/wifi-debug-shell.md), fenykl notes,
Atlas-linked projects.
