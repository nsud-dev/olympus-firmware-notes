# Starry Sky AF: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Starry Sky AF](starry-sky-af.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

Starry Sky AF is an autofocus mode on newer bodies that can focus on stars at night, something normal autofocus can't
do. The E-M5 III doesn't have it. This page records what the feature is made of on the E-M1 III and OM-5, how it would
fit into the E-M5 III, and the first test build. The firmware's internal names are Astro AF and `fcs_astro_*`.

Research is done. A first test build has been built but not run. It sits on an old base, so it needs a rebuild before
it can be tested alongside current builds.[^pol1]

Three terms recur. Single autofocus is S-AF. Phase-detect AF (PDAF) uses the on-sensor AF pixels, and star mode switches
it off in favour of contrast AF. Infinity pre-drive means moving the lens to its stored infinity position before
focusing.

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred.

## Feature on newer bodies

- The feature is absent from the E-M5 III 1.7. It has no strings, settings, properties, AF-mode values or flash
  table for it.[^fw1]
- It is present, identically, in the E-M1 III 1.6 and OM-5 1.2. The OM-5 II only adds start-trigger options.[^fw1]
- It isn't one module. It is woven through the AF stack: settings, the release check, the take_focus sequencer, the
  fcs (focus) task, the AE scene judge, lens drive and GUI.[^fw1]
- The new code is only about 5 to 6 KB. The cost is about 25 to 40 hook sites. No new image-engine job is
  needed.[^fw1]

On the OM-5 the pieces are these.[^fw1]

- AF mode values 11 (Starry Sky AF) and 12 (Starry Sky AF + MF).
- Settings 1839 to 1845, plus 2394 for the enabled lens.
- Properties `0xb981` (3 bytes) to `0xb9c1`. The last is the type, Accuracy 1 or Speed 0.
- A packet with fields +5 and +6, built by one function.
- A block of astro routines.
- A scene judge that works from AE brightness, with BV thresholds −2048, −1024 and 0.
- An infinity pre-drive that uses lens commands 6 and 7.

The contrast-AF calculation library is the same on all three bodies. In the E-M1 III, 691 of 704 functions in that
library are anchor-exact with the E-M5 III. The 7 new ones there are HHHR pixel-shift code. So there is no AF algorithm
to port.[^fw1]

## Star mode

On the E-M1 III, the S-AF branch checks for star mode. When S-AF and star mode are on, it pre-drives the lens to the
stored infinity position. It then sends focus command `0x1b00` (astro) instead of `0x1100`.[^fw1]

In the fcs task, command `0x1b00` changes three things.[^fw1]

1. It skips the phase-detect path.
2. It sets AF-engine mode 4.
3. It uses larger AF areas per target size.

The E-M1 III astro infinity drive is a clone of the native focus-limiter drive. It has the same request layout, wait,
10 s timeout and post callback. Its target falls back to lens info +24 when no learned record matches.[^fw1]

The E-M1 III star S-AF branch is the normal S-AF branch with two differences. Drive(LIMIT) is replaced by the astro
drive, and the command is `0x1b00` instead of `0x1100`. The E-M1 also requires tf[5] == 1 there. Its meaning on the
E-M5 isn't pinned, so the test build skips that test.[^fw1]

On the lens side, the OM-5's lens request types 6 and 7 are tagged copies of types 2 (drive to position) and 3 (stop).
So the E-M5 III can pre-drive with types 2 and 3. The lens request handler and the capability check both have E-M5 III
matches.[^fw1]

## Port plan

### Hooks

The E-M1 III fcs task is a strict superset of the E-M5's, 84 to 99% identical around the hooks. So we use it to place
hooks, and the OM-5 for behaviour, settings and UI.[^fw1] The key E-M5 hook functions are the S-AF sequence, the PD
skip, mode 4, the release check, the AE scene judge and the packet. The [address reference](#address-reference) lists
them.[^fw1]

### Code space

- The section 2 slack is filled with `0xff`. Its only reference is the loader's section-2 end, which must move, as for
  section 4.[^fw1]
- Section 2 is ready before section 4, which holds take_focus and fcs. So these hooks have no boot race.[^fw1]
- The budget is about 75 to 80 KB, including the 62.7 KB table. That is tight.[^fw1]
- One flash range is never referenced by E-M5 code. It is a candidate for the flash-learning step. Dump it read-only
  first.[^fw1]

See also: [Memory map](../hardware/memory-map.md).

### Infinity table

The per-lens infinity table (62,720 bytes) lives in flash on the OM-5. On the E-M5 III that area is the `res` lens-data
resource.[^fw1] The plan is to keep the table in RAM first. Flash writes come only with an explicit go-ahead.[^pol2]

## Test build

The test build makes star S-AF on the E-M5 III out of the native S-AF with four changes.[^fw2] It is armed through the
Live ND request file at M+24. A second setting leaves out change 4.

1. The S-AF start call to drive(LIMIT) becomes an infinity pre-drive. It goes through the native focus-limiter lens
   request (type 2, +4 target pulse, +8 callback) with its wait and sender. The target is lens info +24.
2. PDAF is switched off.
3. The donor AF area table replaces the native one.
4. The AF engine field +96 is set to 4 for command `0x1100`.

The code is 321 bytes, in free space in section 4 with no native references. The simulator passes and the rebuild is
identical.[^emu1]

The free code space is the cave-extended part of section 4. It was `0xff` in our test base and has no native
references. The test build uses part of it.[^fw2]

## Stages

1. Research. Done.
2. Armed engine. Built.
3. Settings and menu.
4. Flash learning.
5. Polish.

## Older bodies

Neither the E-M5 II nor the E-M5 Mark I has astro AF strings.[^fw3] Any port would be new AF code on a different chip.
It was not checked further.[^inf1]

See also: [older bodies](../bodies/comparison-technical.md#older-bodies-e-m5-ii-and-e-m5-mark-i).

## Open questions

- What reads the Accuracy or Speed setting. No MN103 reader of mode 4 or of the Accuracy/Speed byte has been found
  yet.[^fw1]
- The E-M5 match for the E-M1 III's larger AF areas is weak and needs a re-check.[^fw1]
- The meaning of tf[5] on the E-M5.[^fw1]

## Address reference

Block0 addresses (base `0x60021020`) unless noted.

| item | E-M1 III 1.6 | OM-5 1.2 | E-M5 III 1.7 |
|---|---|---|---|
| S-AF star insert / S-AF sequence | `0x60746cfc` | | `0x60701c08`, `0x607081bd` |
| phase-detect skip | | | spot `0x6065c3e3`, function `0x6065c2f9` |
| AF-engine mode 4 | | | set at `0x606e7dbd`, function `0x606e7d8f` |
| larger AF areas | `0x6069d8aa` | | `0x60663543` (weak match) |
| astro infinity drive | `0x60697939` | | |
| learned-record fallback | `0x606bda0b` | | |
| lens request handler | | `0x600fc294` | `0x600ef5b2` |
| capability check | | `0x60217477` | `0x60206b72` |
| packet (+5/+6) | | `0xa2716ba8`, built by `0x60759aa9` | hook `0x607163a2` |
| astro routines | | `0x606d58fa`–`0x606d5ae5` | |
| release check | | | `0x6019ac9d` |
| AE scene judge | | | `0x60411bc7` |
| contrast-AF library | `0x6037c000`–`0x603a8000` | | |

*Star mode sites and their E-M5 III matches.*

| item | address |
|---|---|
| section 2 slack | `0x6056c000`–`0x60582000` |
| loader's section-2 end | `0x60045de3` |
| flash never referenced by E-M5 code | `0x40760000`–`0x4077ffff` |
| OM-5 per-lens infinity table (E-M5 III: `res` lens data) | flash `0x40740000` |
| section 4 cave, free code space | `0x6079d800`–`0x607a0000` |
| test build code (321 bytes) | `0x6079e000`–`0x6079e141` |

*Memory for the port. E-M5 III unless noted.*

| item | address |
|---|---|
| S-AF start call `call 0x60717c73` (drive(LIMIT)) | at `0x60701dcb` |
| focus-limiter lens request | `0x62199b64` |
| request callback | `0x606d3670` |
| wait / sender | `0x606d415b` / `0x600ef5b2` |
| lens info | `0x6020586f(0)` +24 |
| PDAF off | `0x6065c3e3` |
| donor AF area table | `0x606639a6` (w `0xa2681278` / h `0xa268127a`) |
| AF engine +96 = 4 | `0x606e7dbd` |

*The test build's changes on the E-M5 III.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware, 2026-11-05.
[^fw2]: Read in the firmware for the test build, 2026-11-05. The build has not been run.
[^fw3]: Read in the firmware of the E-M5 II and E-M5 (Mark I), 2026-11-21.
[^inf1]: Inferred, 2026-11-21.
[^emu1]: Run in our simulator, 2026-11-05. The rebuild was byte-identical.
[^pol1]: Project status, 2026-11-05. Still true on 2026-11-19.
[^pol2]: Project policy, 2026-11-05.

