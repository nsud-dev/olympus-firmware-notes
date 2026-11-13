# PEN-F / E-P7 Color / Monochrome Profile Control

The PEN-F and E-P7 have a front dial for Color Profile and Monochrome Profile Control: picture modes where you set the
saturation of 12 hue sectors (colour) or the filter, grain and shading (mono), with three saved slots each. The E-M5 III
doesn't offer them. This page shows that the E-M5 III's firmware already contains the processing and saved settings
for both, and that what's missing is the way to select and edit them.

Tags: **[code]** read in the firmware, **[inferred]** not traced or tested.

**Status: back end found 2026-11-07; port plan proposed, not started** (paused 2026-10-19; resumed 2026-11-07).

- PEN-F 3.1: same container (`OE 12 20`, 4 blocks), MN103, base 0x60021020, no LZ4. [code]
- Internal names: Color Profile Control = **ColorCreator2** (12 hue sliders, `chColorCreator2Saturation[0..11]`),
  Monochrome Profile = **MonochromeCreator** (`ucMonochromeCreatorLevel/Granular`, `chMonochromeCreatorShading`). [code]
- 2026-11-07: picture-mode ids are the same on E-M5 III and E-P7: 9 Color Creator, **11 Color Profile (COLOR_CREATOR_2)**,
  **12 Monochrome Profile (MONOCHROME_CREATOR)**. [code]

## What the E-M5 III 1.7 already has (2026-11-07)
- Settings 904 → prop 63153 (colour profile no.), 911-922 → 63210[0..11] (effective 12-sector saturation), 923-958 →
  63226[0..35] (**3 slots × 12**), 969 → 63281 (mono profile no.), 970-1002 mono per-slot props; all in the saved-settings
  registry (0x600bcdc4..0x600bceb4). E-P7 has the same block at ids +4. [code]
- Mode loader 0x602bccd3: mode 11 → 63153, mode 12 → 63281, 63210 → mode+24952, mono 63401/63337/63433 → mode+24978..80
  (same logic as E-P7). Stills develop 0x6040289b copies them to params+5538..5552 for mode 11/12; live view 0x60343414
  likewise. [code]
- ISP colour builder for mode 11: 0x603d087c → call 0x603d0623 with request+1816 and COLOR table 0x605229cc, the same
  selector shape caduceus/PEN-F HSL hook on E-P7 (0x603b02d9). Mono path at 0x60373551. [code]
- Playback RAW develop reads slot array 63226 (0x612b308d). GUI strings "Color Profile 1-3", "Monochrome Profile 1-3" in
  block1. [code]
- A 2026-10-19 note said "strings only, not traced"; traced 2026-11-07, the back end is wired, not dead strings. [code]

## Back-end test (designed 2026-11-08, not built)
- Hook at mode loader 0x602bce58 (11 B → d32 call of a stub 0x600d00e0, section-4 body 0x6079f000): when armed from the card it forces
  picture mode 11 with test saturations (or mode 12 for the mono test), only in the per-shot mode record (nothing saved). Built on our current test base.
  [inferred]
- Saved-settings registry defaults for 63210 are 0 ×12 (0x600bcde4): 0 = neutral, signed ±5 likely. [inferred]

## What is missing
- No way to select mode 11/12 (picture-mode list/dial), no profile editor screen, and the editor's CC2/MONO wheel renderers
  are stubs (0x60c26bdb, 0x60c26beb print "not supported"). OM-5 1.2 and E-M1 III have real renderers. [code]

- Nothing seen copies a slot (63226[p]) into the effective 63210 on the shooting path; on E-P7 the editor does it. [inferred]
- Not traced yet: picture-mode setter/validator range, option lists, EXIF tag for 11/12. [inferred]

## caduceus-ep7 (E-P7) colour features vs E-M5 III
- caduceus PORT_EM5III.md says the E-M5 III has no profile system; wrong, only the UI is missing. Their looks need the
  slots + wheel; per-sector saturation, the hue/lightness hook site and the settings exist here, but their addresses don't
  carry over (36% signature match, SD loader not matched). [code]
- Plan in five steps (back-end test → selectable slots → card-loaded looks → on-camera editor → extras), effort and risk in
. [inferred]

