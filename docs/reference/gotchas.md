# Gotchas

<!-- human page -->
<!-- house style -->

## Key points

- Each lesson here cost a flash, a battery pull or a day of work, and each comes with the rule we follow now.
- The lessons cover addresses, start-up, memory, the image engine, the ARM co-processor and testing.
- The emulator is not a boot test, and a static check of the start-up path catches what it misses.
- Some ideas were tried and dropped, and they are listed so nobody repeats them without a new idea.

Each lesson on this page cost a flash, a battery pull or a day of work. They are grouped by theme, with the rule we
follow now. Read them before designing a build.

## Addresses

- **Check every address against the stock firmware.** A one-digit typo in a table address reset the camera across four
  flashes. The same typo had been copied into the simulators, so they agreed with it. Every address now goes through a
  checking script.
- **Check what a function is.** We once called the card read function, thinking it was the write function, and
  every log came out empty.

## Start-up

- **Never jump into code that has not loaded yet.** The main program loads in ten sections. A hook that jumps into a
  later section before it is ready crashes the camera now and then at power-on. Every such hook needs a guard.
- **Leave a gap after a section's end.** A section end raised right up to memory another core uses reset the camera at
  every power-on. Keep at least one cache line free, and better a 4 KB page.
- **Do not act on a card file at start-up.** A request file left on the card fired at every start and caused a bootloop.
  Consume request files before doing anything risky, and read them only on a user action.

## Memory

- **Write only into buffers you were given.** Image buffers share memory between modes. The unused end of one buffer
  is someone else's buffer in another mode.
- **Ask the pool for an address.** The main frame pool is split into two blocks, so working out addresses by stepping
  through it put 32 MB of data in the wrong place.
- **Keep patch state out of program memory.** Storing a byte into code memory restarted the camera on two other bodies.
  Keep state on the heap.
- **Write code through the uncached view.** Writing code through the cached view resets the camera. This also
  applies to data words kept in a code section. Write them through the uncached view, then flush the cache.
- **Keep data aligned.** The processor faults on a misaligned word, but the simulators do not. A 4-byte field must sit
  on a 4-byte boundary.

## The image engine

- **Check a job's record against the firmware's own rules.** If the check refuses it, the engine's worker stops for
  good, and the camera freezes the next time anything uses the engine.
- **Load programs into the right memory range,** or the camera resets.

## The ARM co-processor

- **Do not start or stop it in the middle of a shot.** Both reset the camera. Switch it only when the camera is idle.
- **Check it is running before sending it a message.** The mailbox calls wait forever otherwise.

## Testing

- **The emulator is not a boot test.** It skips the real start-up chain and the shooting state machine. A build can
  pass every emulator script and still fail on the camera. A static check of the start-up path catches what it misses.
- **A menu string is not a feature.** Newer bodies carry text for features they do not have. Confirm there is
  reachable code, or run the menu in the emulator.
- **One photo is not a result.** We once mistook motion blur for a successful merge and had to retract it.

## Dead ends

These were tried and dropped. Please do not repeat them without a new idea.

- Switching hidden features on with debug flags. The engines are compiled out.
- Merging raw frames on the main processor. It took about 14 seconds per frame, so the image engine does it instead.
- Streaming webcam video while USB is connected. The camera leaves shooting mode.
- Flashing a whole OM-5 or OM-5 II image, or transplanting the OM-5 II's whole menu system.
- Porting subject detection. It needs OM-1 hardware.

## Further reading

- [Gotchas: technical notes](gotchas-technical.md) has every case with its cause, the addresses and the evidence.
- [Recovery](../firmware/recovery.md) explains what to do when a build does go wrong.
- [Modifying the firmware](../firmware/patching-techniques.md) has the build rules these lessons led to.
