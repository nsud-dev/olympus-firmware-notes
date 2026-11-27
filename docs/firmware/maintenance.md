# Maintenance layer

<!-- human page -->
<!-- house style -->

## Key points

- The E-M5 III keeps factory calibration, two pixel-defect maps, the user settings and a small counter store in its
  flash.
- The camera keeps a short history of the last five fault codes, and a serious fault turns the camera off.
- The factory self-adjust, pixel mapping and endurance tests change calibration or wear the camera, so they should not
  be run.
- The same data can be read safely from a flash backup with a small script.

The E-M5 III keeps a set of service data next to its settings. This page describes what that data is, where it lives
and how the camera records faults. It also covers the service menus that use it.

Everything here comes from reading the firmware. Nothing was tested on the camera, and nothing was written to flash.

## Service data

About 2.6 MB at the start of the camera's data area in flash holds factory and service data. That is the calibration,
two pixel-defect maps, the user settings and a small counter store.

| store | what it holds |
|---|---|
| Calibration | Serial numbers, sensor black levels and gains, white balance, stabiliser centre, accelerometer, eye sensor, audio trims |
| Defect map 1 | The factory list of defective pixels, defective focus pixels, sensor saturation levels and the phase-detect AF tables |
| Defect map 2 | Twelve more defect lists and a vertical-line correction |
| User settings | Every menu setting, and the fault history |
| Counters | The shutter count and three other counters (see [Shutter](../hardware/shutter.md)) |

*The five service data stores in flash and what each holds.*

The pixel-defect maps also hold the calibration for the sensor's phase-detect autofocus.

Each store has a check value and a save count. The camera ignores a store that fails its check and starts that store
from its defaults. It writes the calibration, settings and counters only when something in them has changed. The two
defect maps are rewritten every time the service code saves calibration, even if nothing changed.

## Fault history

The firmware calls faults "damage". Each fault has a four-digit code.

- The camera has a list of 342 codes it cares about. Any other code is ignored.
- 290 of those codes are only noted in the history.
- The other 52 are serious. Shutter faults are among them. A serious fault shows the damage screen and turns the
  camera off.
- The history keeps the last five codes. A repeat of the newest code is not added twice. When the history is full
  the oldest code drops out.
- The history is saved with the user settings when the camera turns off.

The debug shell has a `damage` command that prints the history. A hidden maintenance page shows it too.

## Self-adjust

Self-adjust is the factory and service adjustment menu. It has 45 steps. They cover the AF illuminator, the
stabiliser, the sensor (ISO, dark noise, defect maps), the accelerometer, the dust-reduction filter, audio, the touch
panel, loading and saving parameters, and final checks of buttons, dials and lights. It can also enter a serial
number.

Running a step rewrites calibration. It is for service centres only.

> [!WARNING]
> Self-adjust steps rewrite the factory calibration. The life tests below wear the camera on purpose. Don't run
> either on a camera you want to keep.

## Pixel mapping

Pixel mapping finds pixels that are stuck bright and adds them to the defect maps. The camera then hides those
pixels in every photo. The menu item most likely uses the same code as the self-adjust defect steps.

## Life tests

The factory endurance tests run a part over and over. There are tests for the shutter, flash, aperture, focus,
stabiliser, sensor, AF illuminator, battery and more. After each cycle the test checks the fault list and stops if
anything went wrong. These tests wear the camera on purpose. They are started from a debug menu and should never be
run on a camera you want to keep.

## Read-only health checks

These ways only read data.

- A flash backup made by the backup card mod, decoded with the `health.py` script. It prints the calibration and
  defect map headers, the fault history and the counters.
- The debug shell commands `damage`, `mec info` and `sdk`.

## Open questions

- What each fault code means.
- How a defect-map entry is laid out.
- Whether the camera maps pixels by itself. No sign of it was found.

## Further reading

- [Maintenance layer: technical notes](maintenance-technical.md) has the store layouts, the fault codes and the
  addresses.
- [Shutter](../hardware/shutter.md) covers the shutter count and the other counters.

