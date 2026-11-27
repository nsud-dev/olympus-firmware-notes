# om-emu additions

<!-- human page -->
<!-- house style -->

## Key points

- We added eleven small patches to om-emu, an emulator for Olympus and OM System cameras written by the om-emu contributors.
- The patches draw more of the camera's screens and add checks that fail a build the real camera would crash on.
- Each check was added after a real crash on the camera, and had to fail that build and pass its fix and the stock firmware.
- The emulator has no sensor, image pipeline or memory protection, so the shooting path is not tested.

[om-emu](https://github.com/flatpanda/om-emu) is an emulator for Olympus and OM System cameras, written by the om-emu
contributors. It boots the E-M5 III firmware 1.7 through its menus, half-press, shutter and playback. We added eleven
small patches to it. They ship as plain patch files in `tools/om-emu-c3d/patches/` with om-emu's MIT licence and
credit, and apply to a fixed om-emu commit.

## Purpose

om-emu is built to show the camera's screens. We also use it as a safety net before a test build goes on the camera.
That needs two things it didn't have. The first is more of the camera's hardware, so that new features draw and run.
The second is checks that fail a build the real camera would crash on. Each check was added after a real crash on the
camera. Each one had to fail that build and pass the fixed build and the stock firmware.

## Screen drawing

- **The GPU picture layer.** The E-M5 III's vector GPU draws into a 32-bit layer that om-emu didn't show. Menus,
  histograms and overlays drawn there now appear in emulator screenshots.
- **A stand-in for live view.** om-emu has no sensor. A still picture can sit under the overlays instead of plain
  black. By default it is a generated lake at dusk.
- **Bitmaps without a colour table.** Some pictures, such as the tone-curve grid, were refused. They now draw.
- **A log of display-controller writes.** It shows what a build does to the screen hardware, register by register.

## Crash checks

- **Stale memory between the cache and RAM.** This catches code that writes through one view of memory and reads
  through the other.
- **Code that runs before its section is loaded.** The camera loads its program in ten sections, one after another.
  A hook that jumps into a section too early made one test build restart at every power-on. The emulator now flags
  that.
- **Fields nobody set.** The emulator's heap can hand out filled blocks instead of zeroed ones. A read of an unset
  field then shows up.
- **Kernel misuse.** Two checks watch the camera's operating system. One catches a waiting call made from an
  interrupt. The other catches an object lookup on another CPU's kernel.
- **Writes into the program itself.** The camera resets when code writes into its own program through the cached view
  of memory. The emulator now fails such a build. One test build kept its data inside the program and gave a black
  screen. This check fails it and passes its fix, which boots on the camera.
- **Messages with no address.** Every message the firmware sends to a chip over its serial bus is logged. A message
  with no device address fails. A run can also be compared with the stock firmware's. One test build used a driver
  copied from another camera and sent empty messages to the port expander, so USB never worked. Both checks fail
  that build and pass its fix.

## Second and third CPUs

The camera's main processor runs three CPUs. om-emu ran only the first one on the E-M5 III. The second and third can
now run their own firmware beside it, one at a time. Each starts its tasks and reaches its idle loop, and the stock
firmware still reaches the menus. This ruled out their start-up as the cause of one power-on restart.

## Sleeping tasks

The emulator keeps many firmware tasks asleep, because it can't serve their hardware. A run can now start one of them
on purpose. This woke a port-expander driver, so that its first writes could be checked.

## Limits

- The second CPUs start only after the first one has booted. On the camera they start together.
- Only one of the second CPUs runs at a time.
- There is no sensor, image pipeline, DSP or Wi-Fi chip. So the shooting path and image processing aren't tested.
- There is no real memory protection. The code-write check stands in for it.

## Further reading

- [om-emu additions: technical notes](om-emu-additions-technical.md) lists each patch with its switch, what it adds
  and what it found.
- [Failure patterns](../reference/failure-patterns.md) lists the camera failures these checks were built from.
- [om-emu](https://github.com/flatpanda/om-emu) is the emulator itself.
