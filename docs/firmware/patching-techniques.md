# Patching techniques (what's proven on the camera)

This page lists the ways we have changed the E-M5 III's firmware and seen them work on a real camera, and the rules we
now follow for every build. Most of the rules were learned from a build that failed, and the failure is noted next to
the rule.

Terms used here:

- **Byte patch**: change a few bytes in place, for example turn a branch into a no-op.
- **Code cave**: unused space in the firmware where our own code can live. Here that is mostly **slack**, the 0xFF
  bytes after the end of a block0 section (see [memory map](../hardware/memory-map.md#spare-space-for-our-code)). [code]
- **Hook**: redirect a native instruction (a jump or call) into our code, which then returns to the original path.
  A **trampoline** is the small piece of code that saves registers, calls our code and restores them.
- **Boot guard**: a check that the section our hook jumps into has finished loading (see
  [boot](boot-and-sections.md)).
- **Armed**: our features only act when the user has asked for them (a request file on the card plus a shooting
  mode); otherwise every hook falls straight through to stock behaviour.
- **Donor**: the newer body we port code from (the OM-5).

Tags: **[code]** read in the firmware, **[camera]** seen on a real E-M5 III, **[inferred]** not traced or tested.

## What has worked on the camera

| technique | first proof | tag |
|---|---|---|
| Byte patch + repack + re-checksum + flash | focus stacking any lens: 0x6065e5ec `c9 04` → `cb cb` (2026-10-19) | [camera] |
| Call into our code in section-0 tail | cave test 1: 0x6065e5e2 → 0x600d0100 `mov 1,d0; ret [],4` | [camera] |
| Enable section slack by raising the loader end constant | cave test 2: section 4 end 0x6079d800 → 0x607b6800 at 0x60045deb, code at 0x607a0000 | [camera] |
| Change USB personality (PID, TPC class, PTP index) | USB tests 1-4 | [camera] |
| Relocate the shooting-state table and add states | state test 1 (state 34) | [camera] |
| Inject USB descriptors | webcam test 1 (UVC enumerates) | [camera] |
| Hook native code via jmp/call retarget with trampolines saving all regs + MDR | Live ND E2-E10 | [camera] |
| Hold native frames, run donor DSP job on them, save as the photo | Live ND E5c-E8c | [camera] |
| Card-file request / RAM log written by the next silent single | Live ND (LNDM3.ARM, LND3B7) | [camera] |
| Boot guards on out-of-section hooks | 10/10 boots | [camera] |
| Run donor C/asm relocated from OM-5 | relocation script for the OM-5 DigitalNd functions | [code]; ran on the camera [camera] |

## Rules we follow (each learned the hard way)

The build checks in [recovery](recovery.md#pre-flash-check-suite-every-build-2026-11-07) test most of these automatically.

1. **Every absolute address needs native evidence** (an operand in Olympus code or a documented derivation). Run
   `check_addrs.py`. Sims must not use note values as
   ground truth. (E2c-E2j pool-table typo cost 4 flashes.)
2. **Guard every hook whose site is outside the target's section**: test the ready bit (0xa26565c0 bit for that section,
   or call 0x60045d92(n)) in always-ready code; if not ready, run the displaced instructions and return.
3. **Act only when armed.** Builds must preserve all other functionality: hooks fall through to native
   unless the card request + mode match.
4. **Context checks before touching native objects**: 0x600386ae == 0 (task), (0x8050) == 0 (core 0), lock with a
   timeout (never forever); on failure record a code and fall through with registers and SP unchanged.
5. **No file I/O, locks or waits in interrupt context** (StlUhs completion is an ISR).
6. **Card I/O only from the silent-single gate** (drive 30): bursts set state; the next silent single writes the log.
7. **Copy native call frames** (`call f,[regs],N`) exactly; save locals from (4,sp); save/restore mdr in gates that call.
8. **Ask pools for addresses** (two-block main pool); pool key = class << 8.
9. **Read the DSP bridge checks** before any record change: a refusal hangs the camera.
10. **Compile C as plain MN10300**, never AM33-only encodings.
11. Builds get a descriptive name, SHA-256, a `.md`/PROCEDURE with base, bytes changed, test and recovery; post a readout of
    each camera run before building the next.
12. Research the OM-5 behaviour statically before designing a test; camera runs confirm designs, they don't find them. Faithful ports of OM-5 branches, with "armed" standing in for the missing property.
13. **Join points: re-derive arguments from native callers, never from the donor.** When ported donor code calls a
    helper and we retarget the call to the E-M5's native counterpart, the native helper may take different arguments
    even when it builds the same thing. For each retargeted call, read at least two native callers and the callee's
    first use of every register and stack slot, then write an adapter at the call site. Copy frames from the callee's
    `ret` (rule 7). Re-check every event number the donor posts against the port's table renumbering, including reply
    events in request messages. (Example: our state 37 passed the donor's boolean as the native builder 0x602b97bf's record
    pointer -> reset; callback posted donor event 81 where the port table has 83.) [code] 2026-11-06
; join-point list in `firmware/live-nd-port-layers.md`.

## Build infrastructure

What we build with:

- Assembler: bundled binutils `as`/`objdump`/`objcopy` only (**no `ld`**); our `link.py`/`roundtrip.py` apply relocs.
  gas keeps PC-relative relocs for same-section labels and rejects branches to absolute `.set` symbols
  (define as `region_start + off`). A silently ignored SYM_DIFF reloc once produced a self-jump; builds now assert
  only PCREL relocs and that every `nc/nj` resolved. [code]
- Simulator: GDB mn10300 sim (eqsim) for gate/diff tests on real images. [code]
- Store builds as deltas vs stock 1.7 (SHA-guarded). [code]
