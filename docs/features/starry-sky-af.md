# Starry Sky AF (internal: Astro AF, `fcs_astro_*`)

**Status 2026-11-05:** S0 research done; **S1 built over E10f, not run** (`STARAF-S1-test.zip`).

- **Absent** from E-M5 III 1.7 (no strings, settings, props, AF-mode values, flash table). Present identically in E-M1 III 1.6
  and OM-5 1.2; OM-5 II only adds start-trigger options. [code]
- Not a module: woven into the AF stack (settings, release check, take_focus sequencer, fcs task, AE scene judge, lens drive,
  GUI). New code ~5-6 KB; the cost is ~25-40 hook sites. No new DSP job. [code]
- OM-5: AF mode values 11 Starry Sky AF / 12 + MF; settings 1839-1845 (+2394 enabled lens); props 0xb981 (3 B) .. 0xb9c1
  (type: Accuracy 1 / Speed 0); packet 0xa2716ba8 +5/+6 built by 0x60759aa9; astro routines 0x606d58fa-0x606d5ae5; scene
  judge from AE BV (thresholds −2048/−1024/0); infinity pre-drive = lens commands 6/7. [code]
- **Risk:** per-lens infinity table (62,720 B) lives in **flash** at 0x40740000 on OM-5; on E-M5 III that area is the `res`
  lens-data resource. Plan: RAM-only table first; flash writes only with the maintainer's go-ahead. [code]
- Placement: E-M1 III `fcs` is a strict superset of E-M5's (84-99% identical around the hooks), so use it to place hooks;
  OM-5 for behaviour/settings/UI. Key E-M5 hook fns: S-AF seq 0x60701c08/0x607081bd, PD skip 0x6065c2f9, mode-4 0x606e7d8f,
  release 0x6019ac9d, AE scene 0x60411bc7, packet 0x607163a2. RAM: section 2 slack. [code]
- What star mode does (E-M1 III S-AF insert 0x60746cfc): when S-AF and star are on, pre-drive the lens to the stored
  infinity position, then send focus command **0x1b00** (astro) instead of 0x1100. In fcs, 0x1b00 skips the phase-detect
  path (E-M5 spot 0x6065c3e3), sets AF-engine mode 4 (E-M5 0x606e7dbd) and uses larger AF areas per target size
  (E-M1 0x6069d8aa; E-M5 match 0x60663543 is weak, re-check). 2026-11-05 [code]
- The contrast-AF calculation library is the same on all three bodies (E-M1 III 0x6037c000-0x603a8000: 691/704 functions
  anchor-exact with E-M5 III; the 7 new ones there are HHHR pixel-shift code). No AF algorithm to port. No MN103 reader of
  mode 4 or of the Accuracy/Speed byte found yet. 2026-11-05 [code]
- Lens: OM-5 lens request types 6/7 (handler 0x600fc294 = E-M5 0x600ef5b2) are tagged copies of types 2 (drive to
  position) and 3 (stop), so the E-M5 III can pre-drive with 2/3. Capability check 0x60217477 = E-M5 0x60206b72. 2026-11-05 [code]
- RAM: section 2 slack 0x6056c000-0x60582000 is 0xFF-filled; only reference is the loader section-2 end at 0x60045de3
  (move it, as for section 4). Section 2 is ready before section 4 (take_focus/fcs), so no boot race for these hooks.
  Budget ~75-80 KB incl. the 62.7 KB table: tight. Flash 0x40760000-0x4077ffff is never referenced by E-M5 code (S3
  candidate; dump it read-only first). 2026-11-05 [code]
- **S1 build (2026-11-05, over E10f, not run):** star S-AF on the E-M5 III = native S-AF with four changes, armed by
  Live ND request letter **A** (all) or **B** (no mode 4) at M+24. (1) The S-AF start `call 0x60717c73` (drive(LIMIT),
  0x60701dcb) becomes an infinity pre-drive through the native focus-limiter lens request (0x62199b64: type 2, +4
  target pulse, +8 callback 0x606d3670; wait 0x606d415b; sender 0x600ef5b2); target = lens info (0x6020586f(0)) +24.
  (2) PDAF off at 0x6065c3e3. (3) Donor AF area table at 0x606639a6 (w 0xa2681278 / h 0xa268127a). (4) AF engine
  +96 = 4 for command 0x1100 at 0x606e7dbd. Code 321 B at 0x6079e000 (free in section 4, no native refs). Sim pass,
  rebuild identical. 2026-11-05 [code]
- E-M1 III astro infinity drive (0x60697939) is a clone of the native focus-limiter drive (same request layout, wait,
  10 s timeout, post callback); its target falls back to lens info +24 when no learned record matches (0x606bda0b).
  The E-M1 III star S-AF branch (0x60746cfc) is the normal S-AF branch with drive(LIMIT) replaced by that drive and
  command 0x1b00 for 0x1100. E-M1 also requires tf[5] == 1 there; meaning on E-M5 not pinned, S1 skips that test.
  2026-11-05 [code]
- Free code space: 0x6079d800..0x607a0000 (the cave-extended part of section 4, 0xFF in E10f, no native refs);
  S1 uses 0x6079e000..0x6079e141. 2026-11-05 [code]
- Stages: S0 research ✓, S1 armed engine (built), S2 settings/menu, S3 flash learning, S4 polish. Open: Accuracy/Speed consumer.
