# Starry Sky AF (internal: Astro AF, `fcs_astro_*`)

Starry Sky AF is an autofocus mode on newer bodies that can focus on stars at night, something normal autofocus can't
do. The E-M5 III doesn't have it. This page records what the feature is made of on the E-M1 III and OM-5, how it would
fit into the E-M5 III, and the first test build.

**Status 2026-11-05:** S0 research done; **S1 built over E10f, not run** (`STARAF-S1-test.zip`).

Terms: **S-AF** = single autofocus; **PDAF** = phase-detect AF (the on-sensor AF pixels), which star mode switches off in
favour of contrast AF; **infinity pre-drive** = moving the lens to its stored infinity position before focusing.

Tags: **[code]** read in the firmware, **[inferred]** not traced or tested.

## What the feature is

- It is **absent** from E-M5 III 1.7: no strings, settings, properties, AF-mode values or flash table. It is present,
  identically, in the E-M1 III 1.6 and OM-5 1.2; the OM-5 II only adds start-trigger options. [code]
- It isn't one module. It is woven through the AF stack: settings, release check, the take_focus sequencer, the fcs
  (focus) task, the AE scene judge, lens drive and GUI. The new code is only ~5-6 KB; the cost is ~25-40 hook sites.
  No new image-engine job is needed. [code]
- On the OM-5: AF mode values 11 Starry Sky AF / 12 + MF; settings 1839-1845 (+2394 enabled lens); properties 0xb981
  (3 B) .. 0xb9c1 (type: Accuracy 1 / Speed 0); packet 0xa2716ba8 +5/+6 built by 0x60759aa9; astro routines
  0x606d58fa-0x606d5ae5; the scene judge works from AE brightness (BV thresholds −2048/−1024/0); infinity pre-drive uses
  lens commands 6/7. [code]
- The contrast-AF calculation library is the same on all three bodies (E-M1 III 0x6037c000-0x603a8000: 691/704
  functions anchor-exact with E-M5 III; the 7 new ones there are HHHR pixel-shift code), so there is no AF algorithm to
  port. No MN103 reader of mode 4 or of the Accuracy/Speed byte has been found yet. 2026-11-05 [code]


## What star mode actually does

On the E-M1 III (S-AF insert 0x60746cfc): when S-AF and star mode are on, it pre-drives the lens to the stored infinity
position, then sends focus command **0x1b00** (astro) instead of 0x1100. In fcs, 0x1b00 skips the phase-detect path (E-M5
spot 0x6065c3e3), sets AF-engine mode 4 (E-M5 0x606e7dbd) and uses larger AF areas per target size (E-M1 0x6069d8aa; the
E-M5 match 0x60663543 is weak, re-check). 2026-11-05 [code]

The E-M1 III astro infinity drive (0x60697939) is a clone of the native focus-limiter drive (same request layout, wait,
10 s timeout, post callback). Its target falls back to lens info +24 when no learned record matches (0x606bda0b). The
E-M1 III star S-AF branch (0x60746cfc) is the normal S-AF branch with drive(LIMIT) replaced by that drive and command
0x1b00 instead of 0x1100. The E-M1 also requires tf[5] == 1 there; its meaning on the E-M5 isn't pinned, so S1 skips that
test. 2026-11-05 [code]

Lens side: the OM-5's lens request types 6/7 (handler 0x600fc294 = E-M5 0x600ef5b2) are tagged copies of types 2 (drive
to position) and 3 (stop), so the E-M5 III can pre-drive with 2/3. The capability check 0x60217477 = E-M5 0x60206b72.
2026-11-05 [code]

## Fitting it into the E-M5 III

- **Where to hook:** the E-M1 III `fcs` is a strict superset of the E-M5's (84-99% identical around the hooks), so we
  use it to place hooks, and the OM-5 for behaviour, settings and UI. Key E-M5 hook functions: S-AF sequence
  0x60701c08/0x607081bd, PD skip 0x6065c2f9, mode-4 0x606e7d8f, release 0x6019ac9d, AE scene 0x60411bc7, packet
  0x607163a2. [code]
- **Where the code goes:** section 2 slack 0x6056c000-0x60582000 is 0xFF-filled; its only reference is the loader's
  section-2 end at 0x60045de3 (move it, as for section 4). Section 2 is ready before section 4 (take_focus/fcs), so these
  hooks have no boot race. The budget is ~75-80 KB including the 62.7 KB table: tight. Flash 0x40760000-0x4077ffff is
  never referenced by E-M5 code (an S3 candidate; dump it read-only first). 2026-11-05 [code]

- **The risk:** the per-lens infinity table (62,720 B) lives in **flash** at 0x40740000 on the OM-5, and on the E-M5 III
  that area is the `res` lens-data resource. Plan: keep the table in RAM first; flash writes only with the maintainer's go-ahead.
  [code]

## Test build S1 (2026-11-05, over E10f, not run)

S1 makes star S-AF on the E-M5 III out of the native S-AF with four changes, armed through the Live ND request file (with a
second setting that leaves out change 4) at M+24: [code]

1. The S-AF start `call 0x60717c73` (drive(LIMIT), 0x60701dcb) becomes an infinity pre-drive through the native
   focus-limiter lens request (0x62199b64: type 2, +4 target pulse, +8 callback 0x606d3670; wait 0x606d415b; sender
   0x600ef5b2); target = lens info (0x6020586f(0)) +24.
2. PDAF off at 0x6065c3e3.
3. The donor AF area table at 0x606639a6 (w 0xa2681278 / h 0xa268127a).
4. AF engine +96 = 4 for command 0x1100 at 0x606e7dbd.

The code is 321 bytes at 0x6079e000 (free in section 4, no native references). The simulator passes and the rebuild is
identical. 2026-11-05

Free code space: 0x6079d800..0x607a0000 (the cave-extended part of section 4, 0xFF in E10f, no native references); S1
uses 0x6079e000..0x6079e141. 2026-11-05 [code]

## Stages

S0 research ✓, S1 armed engine (built), S2 settings/menu, S3 flash learning, S4 polish. Open: what reads the
Accuracy/Speed setting.
