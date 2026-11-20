# PEN-F / E-P7 Color / Monochrome Profile Control

The PEN-F and E-P7 have a front dial for Color Profile and Monochrome Profile Control: picture modes where you set the
saturation of 12 hue sectors (colour) or the filter, grain and shading (mono), with three saved slots each. The E-M5 III
doesn't offer them. This page shows that the E-M5 III's firmware already contains the processing and saved settings
for both, and that what's missing is the way to select and edit them.

Tags: **[camera]** seen on our E-M5 III, **[code]** read in the firmware, **[inferred]** not traced or tested.

**Status (2026-11-20): working on our camera in test builds.** Color Profile and Monochrome Profile can be picked in
Picture Mode, edited on the camera with a colour wheel, and the edits show in live view and in photos (see
[On-camera editor](#on-camera-editor)). Not released. The back end was found 2026-11-07.

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

## Back-end test (designed 2026-11-08; built, not run: the editor below made it unnecessary)
- Hook at mode loader 0x602bce58 (11 B → d32 call of a stub 0x600d00e0, section-4 body 0x6079f000): when armed from the card it forces
  picture mode 11 with test saturations (or mode 12 for the mono test), only in the per-shot mode record (nothing saved). Built on our current test base.
  [inferred]
- Saved-settings registry defaults for 63210 are 0 ×12 (0x600bcde4): 0 = neutral, signed ±5 likely. [inferred]

## On-camera editor

Added 2026-11-19/20.

- **Selectable modes.** Color Profile and Monochrome Profile, three slots each, are entries in the Picture Mode carousel;
  the chosen profile and slot survive power-off. The method follows the Caduceus OM-5 II port, which restored the same
  hidden slots on that body. [camera] 2026-11-19
- **Wheels.** The E-M5 III's own wheel drawing routines for these modes are stubs, and the OM-5 has none. The E-M1 III
  1.6 has complete ones, unused on that body: we relocated them, plus the wheel pictures they draw from, which the
  E-M1 III doesn't ship (they come from the PEN-F). [camera] 2026-11-19
- **Why the wheel was first invisible.** The wheels drew correctly into memory, but the screen layer stayed off: the
  stock background routine stops early for these two wheel kinds, which no stock E-M5 III screen uses, and skips the
  display setup. Letting it continue fixed it. A shell dump of the drawing buffers was the check that the renderers
  worked. [camera] 2026-11-19
- **Edits reach photos and live view.** Colour edits (12 hue sectors) and mono edits (filter, level) are applied to
  photos and to live view. Two gaps had to be closed: the mono editor must also write the plain monochrome filter and
  level settings the shooting path reads, and live view only takes the 12 sector values when its parameter message is
  flagged for them. [camera] 2026-11-20
- **Labels, reset, panel.** The editor reuses the Color Creator panel. Its labels are pictures, not text, so new
  labels ("Filter", "Level") are new pictures; hold-OK resets to the stored defaults; the coloured box follows the
  filter. [camera] 2026-11-20
- **Super Control Panel.** Sharpness and contrast per profile slot work from the Super Control Panel. [camera] 2026-11-20
- **Side-bar editor.** The editor has an OM-3 / OM-5 II style side bar (not the PEN-F top bar): rows for the profile's
  values, set with the dials, with the stock bottom slider. Rows and sliders work. [camera] 2026-11-20
- **Pitfall found on the way:** a picture widget holds at most 8 picture states; a ninth state reads a wild pointer
  and reset the camera. See [gotchas](../reference/gotchas.md). [camera]+[code] 2026-11-20
- Every value the editor changes is a per-slot saved setting, so a card look loader of the Caduceus kind can fill the
  same slots later. [inferred]
- Credit: the idea of bringing these profiles and looks to bodies that lack them comes from the Caduceus E-P7, OM-3 and
  OM-5 II projects; the wheel code is Olympus's own, from the E-M1 III.

## What was missing (2026-11-07)
- No way to select mode 11/12 (picture-mode list/dial), no profile editor screen, and the editor's CC2/MONO wheel renderers
  are stubs (0x60c26bdb, 0x60c26beb print "not supported"). The E-M1 III has real renderers (corrected 2026-11-19: the
  OM-5 has none). [code] All three were added on the camera since, see above.

- Nothing seen copies a slot (63226[p]) into the effective 63210 on the shooting path; on E-P7 the editor does it. [inferred]
- Not traced yet: picture-mode setter/validator range, option lists, EXIF tag for 11/12. [inferred]

## Colour looks on the E-M5 III
- The E-M5 III has the colour profile back end, and since 2026-11-20 our test builds add the UI (above). Colour looks of the kind the
  caduceus-ep7 project builds for the E-P7 need the profile slots and the colour wheel; per-sector saturation, the
  hue/lightness hook site and the settings exist here. E-P7 addresses don't carry over (36% signature match, SD loader
  not matched), so each site has to be found again on the E-M5 III. [code]
- Plan in five steps: back-end test, selectable slots, card-loaded looks, on-camera editor, extras. Slots and editor are
  done; card-loaded looks are next. [inferred]

