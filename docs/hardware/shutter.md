# Shutter

<!-- human page -->
<!-- house style -->

## Key points

- The E-M5 III's mechanical shutter is run by a single driver in the main firmware, which the firmware calls "mec".
- A photo can use the mechanical shutter, an electronic first curtain with a mechanical second curtain, or no
  mechanical shutter at all.
- The shutter count is a stored number that the driver raises at each mechanical release and keeps in its own small
  store in flash.
- The OM-5 and OM-5 II drive this shutter with the same driver and the same steps.

The E-M5 III has a mechanical focal-plane shutter. A small motor winds it, magnets hold the curtains, and sensors
report where the parts are. The main processor drives all of this through one driver, which the firmware calls "mec".
This page describes that driver, how a photo uses it, and where the camera keeps its shutter count.

The shutter has its own hardware block in the main processor, with its own clock. Only the mec driver touches it.

Everything here comes from reading the firmware. Nothing was tested on the camera.

## The parts

The firmware names these parts of the shutter unit.

- **The motor.** It winds (charges) the shutter. The firmware has "open charge" and "close charge" steps and drives
  the motor with pulses.
- **The magnets.** They hold and release the curtains. There is a normal set, a "dark" set for dark frames, and a
  set that is timed to the sensor.
- **Position sensors.** Two light-gate sensors report the motor and curtain positions. The driver waits for them
  between steps.
- **A pulse generator.** It has two channels that follow the sensor's frame timing. The firmware calls it "lsnc".
  The lens code uses it too. It most likely sets the once-per-frame rhythm of the live-view messages to the lens.

## Shutter types

- **Mechanical.** The first curtain opens, the exposure runs, and the second curtain closes. Both curtains are
  mechanical.
- **Electronic first curtain.** The sensor starts the exposure electronically, and the mechanical second curtain ends
  it. The firmware calls this "EFS". There is less shake because the first curtain does not move.
- **Electronic.** The sensor does the whole exposure. The shutter stays open. Silent modes and some computational
  modes work this way.

The still-photo code can also mix these in a burst, for example electronic first curtain on some frames and
mechanical on others.

## Anti-shock and silent

The drive mode list has twenty entries. Each entry has a few flags. One flag means anti-shock (♦) and another means
silent (♥). Anti-shock exists for single shots, sequential low and the self-timers. There is no anti-shock entry for
sequential high.

Anti-shock most likely uses the electronic first curtain, and silent uses the fully electronic shutter. The code that
turns the drive flag into a shutter type is not traced yet.

## Shutter timing

Each camera is adjusted in the factory. The adjustment data holds the time between the shutter trigger and the
curtain run, with separate values for the mechanical first curtain and the electronic first curtain. The firmware uses
these to line the exposure up with the curtains.

## The shutter count

The camera keeps a release count called "R". It is one of seven counters on a hidden maintenance page, named R, S, C,
U, V, B and L. R is the shutter count. The meaning of the others is not traced yet.

- R lives in a small store of its own (64 KB), next to the user settings in flash. Resetting the settings does not
  touch it.
- At start-up the mec driver reads R into memory. Each time it sends certain shutter commands it adds one and writes
  the new value back. In effect it counts each mechanical release.
- The store has two copies in flash and a checksum, like the user settings.


## The step table

The driver keeps the settings of each shutter step in a table. The steps come in groups of eight, and the type of
shutter run (normal, dark, electronic first curtain and a few others) picks the entry inside a group. The E-M5 III
table has one group that appears twice. No code ever uses the second copy. The OM-5 and OM-5 II simply leave it out.
So the newer programs drive this shutter exactly as the stock firmware does.

## Faults

If the driver sees a shutter fault, it marks the shutter as damaged. It refuses further shutter work until the fault
is cleared. The damage state has three values: normal, error or disabled.

- An error is set when the driver reports one of fifteen shutter fault codes.
- Disabled is set at start-up when a flag says so. The flag is most likely fixed in the program.
- In either state the driver refuses new shutter work.

The same fault codes appear in the camera's wider damage list, which the maintenance layer reads. The factory life
tests (for example a shutter endurance test) check that list after each cycle.

## Other bodies

The OM-5 and OM-5 II use the same driver, the same hardware block and the same count. Their step table is eight
entries shorter, but those eight entries are an unused copy in the E-M5 III table. The steps that run are the same.

## Open questions

- What each type of shutter run is, in plain terms. Normal and electronic-first-curtain runs count, dark-frame runs
  do not.
- What the counters S, U and B count. L is the life-test count. C and V are not used on this body.
- Why anti-shock froze the camera once during a Live ND test.

## Further reading

- [Shutter: technical notes](shutter-technical.md) has the hardware block, the step table, the counter store and the
  addresses.
- [Maintenance](../firmware/maintenance.md) covers the damage list, self-adjustment and the life tests.
- [Lens communication](lens-communication.md) uses the shutter block's pulse generator.
