# Color and Monochrome Profiles: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Color and Monochrome Profiles](pen-f-profiles.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

The PEN-F and E-P7 have a front dial for Color Profile and Monochrome Profile Control. These are picture modes where
you set the saturation of 12 hue sectors (colour) or the filter, grain and shading (mono). Each keeps three saved
slots. The PEN-F and E-P7 call them Color Profile Control and Monochrome Profile Control.

The E-M5 III doesn't offer them. Its firmware already contains the processing and saved settings for both. Only the way
to select and edit them was missing, and our test builds now add it. Both modes can be picked, and an on-camera editor
changes them (see [On-camera editor](#on-camera-editor)).

Color Profile and Monochrome Profile work on our camera in test builds.[^pol1] They can be picked in Picture Mode and
edited on the camera with a colour wheel. The edits show in live view and in photos. Nothing is released. The back end
was found first.[^fw2]

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred or seen in an emulator.

## Names and picture-mode ids

- The PEN-F 3.1 firmware uses the same container (`OE 12 20`, 4 blocks) and the same MN103 CPU. Its block0 base is
  listed in [Address reference](#address-reference). It has no LZ4 compression.[^fw1]
- Color Profile Control is called **ColorCreator2** internally. It has 12 hue sliders,
  `chColorCreator2Saturation[0..11]`.[^fw1]
- Monochrome Profile is called **MonochromeCreator** internally, with `ucMonochromeCreatorLevel/Granular` and
  `chMonochromeCreatorShading`.[^fw1]
- The picture-mode ids are the same on the E-M5 III and the E-P7.[^fw2]
    - 9 Color Creator
    - **11 Color Profile** (`COLOR_CREATOR_2`)
    - **12 Monochrome Profile** (`MONOCHROME_CREATOR`)

## Back end on the E-M5 III 1.7

The E-M5 III 1.7 already has the settings, the mode loader and the processing for both profiles.[^fw2]

| setting ids | property | meaning |
|---|---|---|
| 904 | 63153 | colour profile number |
| 911–922 | 63210[0..11] | effective 12-sector saturation |
| 923–958 | 63226[0..35] | **3 slots × 12** |
| 969 | 63281 | mono profile number |
| 970–1002 | mono per-slot properties | |

*Profile settings and the properties they map to. All are in the saved-settings registry.[^fw2]*

The E-P7 has the same block at ids +4.[^fw2]

- **Mode loader.** Mode 11 loads 63153 and mode 12 loads 63281. Property 63210 goes to mode+24952. The mono
  properties 63401, 63337 and 63433 go to mode+24978 to mode+24980. This is the same logic as on the E-P7.[^fw2]
- **Develop.** For mode 11 and 12, the stills develop step copies these values to params+5538 to params+5552. Live
  view does the same.[^fw2]
- **Colour builder.** For mode 11, the image signal processor (ISP) colour builder calls a helper with request+1816
  and the COLOR table. This is the same selector shape as the Caduceus PEN-F hue, saturation and lightness (HSL) hook on the E-P7. The mono path is
  separate.[^fw2]
- **Playback.** Playback RAW develop reads the slot array 63226.[^fw2]
- **Strings.** The GUI strings "Color Profile 1-3" and "Monochrome Profile 1-3" are in block1.[^fw2]

The back end is wired, not dead strings.[^fix2]

### Stock gaps

Stock firmware had three gaps, and all three have since been added on the camera (see
[On-camera editor](#on-camera-editor)).[^fw2]

1. There is no way to select mode 11 or 12, in the picture-mode list or on the dial.
2. There is no profile editor screen.
3. The editor's CC2 and MONO wheel renderers are stubs that print "not supported". The E-M1 III has real
   renderers. The OM-5 has none.[^fix1]

Nothing seen copies a slot (63226[p]) into the effective 63210 on the shooting path. On the E-P7 the editor does
it.[^inf1]

## Back-end test

A back-end test was designed and built but not run, because the on-camera editor made it unnecessary.[^inf2]

- A hook at the mode loader replaces 11 bytes with a d32 call of a stub. The stub's body is in section 4.[^inf2]
- When armed from the card, it forces picture mode 11 with test saturations, or mode 12 for the mono test.[^inf2]
- It changes only the per-shot mode record. Nothing is saved.[^inf2]
- It was built on our current test base.[^inf2]
- The saved-settings registry defaults for 63210 are 0 ×12. 0 is neutral, and the values are likely signed ±5.[^inf2]

## On-camera editor

- **Selectable modes.** Color Profile and Monochrome Profile, three slots each, are entries in the Picture Mode
  carousel. The chosen profile and slot survive power-off. The method follows the Caduceus OM-5 II port, which
  restored the same hidden slots on that body.[^cam1]
- **Wheels.** The E-M5 III's own wheel drawing routines for these modes are stubs, and the OM-5 has none. The E-M1 III
  1.6 has complete ones, unused on that body. We relocated them, plus the wheel pictures they draw from. The E-M1 III
  doesn't ship those pictures. They come from the PEN-F.[^cam1]
- **Why the wheel was first invisible.** The wheels drew correctly into memory, but the screen layer stayed off. The
  stock background routine stops early for these two wheel kinds, which no stock E-M5 III screen uses, and skips the
  display setup. Letting it continue fixed it. A shell dump of the drawing buffers was the check that the renderers
  worked.[^cam1]
- **Edits reach photos and live view.** Colour edits (12 hue sectors) and mono edits (filter, level) are applied to
  photos and to live view. Two gaps had to be closed.[^cam2]
    - The mono editor must also write the plain monochrome filter and level settings the shooting path reads.
    - Live view only takes the 12 sector values when its parameter message is flagged for them.
- **Labels, reset, panel.** The editor reuses the Color Creator panel. Its labels are pictures, not text, so new
  labels ("Filter", "Level") are new pictures. Hold-OK resets to the stored defaults. The coloured box follows the
  filter.[^cam2]
- **Super Control Panel.** Sharpness and contrast per profile slot work from the Super Control Panel.[^cam2]
- **Side-bar editor.** The editor has an OM-3 / OM-5 II style side bar, not the PEN-F top bar. UP and DOWN move
  between rows. Values show as stock ± digits, and slider rows get the stock bottom slider. Holding OK resets the
  selected row.[^cam2] The rows are these.
    - the wheel (Color / Vivid, or Filter / Level)
    - Sharpness
    - Contrast
    - Highlight & Shadow (front dial highlight, rear dial shadow)
    - Midtone
    - on Mono also Shading, Film Grain and Mono Color
- **Per-profile tone curve, PEN-F style.** In Color and Mono Profile, the Highlight & Shadow and Midtone settings edit
  the profile's own curve. They can be set from the side bar, the Super Control Panel tile or the stock curve screen.
  Live view and photos follow the profile's curve. Other picture modes keep the shared curve. The curve rows show the
  stock curve screen's grid, with the live histogram behind it when the live-view histogram display is on. Playback
  RAW edit still uses the shared curve for profile shots.[^cam2]
- **Per-colour hue, saturation and lightness (HSL).** Color Profile gets one HSL row. It is a compact strip of the 12
  colour sectors inside the stock Reset bar. INFO switches between Saturation, Hue and Lightness, and the dials change
  the selected colour. Hue and lightness are applied by hooking the step that builds the profile's colour table. That
  is the same place the stock saturation values go in. It works on the camera.[^cam3]
- **Free tone curve (in progress).** Each profile can switch its tone curve from the Olympus controls (Highlight,
  Shadow, Midtone) to a Free curve. The Free curve has five movable points from black to white and is stored with the
  camera's settings. The editor works in om-emu.[^emu1] On the camera the first version had no effect. The photo
  develop step only builds its curve when an Olympus tone value is non-zero.[^cam4][^fw1] The fix applies the Free
  curve to photos directly. Live view is still being traced. Inspiration: androidfanman.
- **Every value is a saved setting.** Every value the editor changes is a per-slot saved setting. So a card look
  loader of the Caduceus kind can fill the same slots later.[^inf1]
- **Credit.** The idea of bringing these profiles and looks to bodies that lack them comes from the Caduceus E-P7,
  OM-3 and OM-5 II projects. The wheel code is Olympus's own, from the E-M1 III.

> [!WARNING]
> A picture widget holds at most 8 picture states. On our camera, asking for a ninth state read a wild pointer and reset the camera.[^cam2][^fw3]

See also: [gotchas](../reference/gotchas.md).

## Colour looks on the E-M5 III

The E-M5 III has the colour profile back end, and our test builds add the UI.[^cam2] Colour looks of the kind the
Caduceus E-P7 project builds need the profile slots and the colour wheel. Per-sector saturation, the hue and lightness
hook site and the settings exist here.[^fw1]

E-P7 addresses don't carry over. The signature match is 36%, and the SD loader was not matched. So each site has to be
found again on the E-M5 III.[^fw1]

The plan has five steps.[^inf1]

1. Back-end test
2. Selectable slots
3. Card-loaded looks
4. On-camera editor
5. Extras

Slots and editor are done. Card-loaded looks are next.[^inf1]

## On the E-M5 II and E-M5 (Mark I)

- **E-M5 II 4.1.** The `ColorCreator2` / `MonochromeCreator` back end that the E-M5 III kept is absent.[^fw4] The
  PEN-F has the whole feature and is the same chip, with 98% of register constants shared. It has mostly the same code,
  with 971 shared source files. So a PEN-F to E-M5 II port is the natural route there, as the OM-5 is for the
  E-M5 III.[^inf3]
- **E-M5 (Mark I) 2.3.** No back end and no close donor.[^fw4][^inf3]

See also: [older bodies](../bodies/comparison-technical.md#older-bodies-e-m5-ii-and-e-m5-mark-i).

## Open questions

- The picture-mode setter and validator range.[^inf1]
- The option lists.[^inf1]
- The EXIF tag for modes 11 and 12.[^inf1]

## Address reference

E-M5 III 1.7 block0 addresses (base `0x60021020`) unless a body is named.

| item | address |
|---|---|
| saved-settings registry, profile block | `0x600bcdc4` to `0x600bceb4` |
| registry defaults for 63210 | `0x600bcde4` |
| mode loader | `0x602bccd3` |
| stills develop copy | `0x6040289b` |
| live view copy | `0x60343414` |
| ISP colour builder, mode 11 | `0x603d087c` |
| colour builder helper | `0x603d0623` |
| COLOR table | `0x605229cc` |
| mono path | `0x60373551` |
| playback RAW develop, slot array read | `0x612b308d` |
| CC2 wheel renderer stub | `0x60c26bdb` |
| MONO wheel renderer stub | `0x60c26beb` |
| Caduceus PEN-F HSL hook (E-P7) | `0x603b02d9` |
| PEN-F 3.1 block0 base | `0x60021020` |

*Profile back end.*

| item | address |
|---|---|
| back-end test hook at the mode loader (11 bytes) | `0x602bce58` |
| back-end test stub | `0x600d00e0` |
| back-end test body (section 4) | `0x6079f000` |
| hue and lightness hook (colour table step) | `0x603d0894` |
| photo develop tone check | `0x6036f16e` |

*Back-end test and editor hook sites.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware.
[^fw2]: Read in the firmware, traced 2026-11-07.
[^fw3]: Read in the firmware, 2026-11-20.
[^fw4]: Read in the E-M5 II 4.1 and E-M5 Mark I 2.3 firmware, 2026-11-21.
[^cam1]: Seen on our E-M5 III using test firmware, 2026-11-19.
[^cam2]: Seen on our E-M5 III using test firmware, 2026-11-20.
[^cam3]: Seen on our E-M5 III using test firmware, 2026-11-21 to 2026-11-22.
[^cam4]: Seen on our E-M5 III using test firmware.
[^emu1]: Seen in the om-emu emulator, 2026-11-22.
[^inf1]: Inferred. Not traced or tested.
[^inf2]: Inferred from the test design, 2026-11-08. The test was built but not run.
[^inf3]: Inferred, 2026-11-21.
[^pol1]: Status as of 2026-11-20.
[^fix1]: Corrected 2026-11-19. The OM-5 has no real renderers.
[^fix2]: Traced 2026-11-07. An earlier note said "strings only, not traced".

## History

- 2026-10-19: a note said the profile modes were "strings only, not traced". Tracing on 2026-11-07 showed the back
  end is wired.
- 2026-11-19: real wheel renderers were first placed in the OM-5 too. Only the E-M1 III has them.
- 2026-11-20: the back-end test was dropped before it ran, because the on-camera editor made it unnecessary.

