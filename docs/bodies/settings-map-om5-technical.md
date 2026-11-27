# Settings map E-M5 III ↔ OM-5: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Settings map E-M5 III ↔ OM-5](settings-map-om5.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

This page maps the menu settings and the saved properties of the E-M5 III 1.7 and the OM-5 1.2, id by id. It also gives
the rules for converting a saved user-settings image between them, both ways. Background on setting ids, properties and
store 50 is in [settings and menus](../firmware/settings-and-menus.md). Nothing here was tried on a camera.

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: blue = read in the firmware, grey = inferred, not traced or
tested.

## Setting tables

Each setting id maps to a `{u16 prop, u16 sub}` pair. A main table covers the low ids. Five range tables follow it, back
to back in both bodies, in the order 3000, 4500, 4000, 10000 and 15000.[^fw1] The 4000 and 4500 ranges hold a bare u16
property with sub 0. An id lookup walks the ranges. Its limits were read in the code (`cmp 3032`, `cmp 4022`,
`cmp 10110` and `cmp 15280` on the OM-5).[^fw1]

| table | entry | E-M5 III 1.7 ids | OM-5 1.2 ids |
|---|---|---|---|
| main | `{prop, sub}` | 0-1649 | 0-1892 |
| range 3000 | `{prop, sub}` | 3000-3019 | 3000-3032 |
| range 4500 | u16 prop only | 4500-4521 | 4500-4521 |
| range 4000 | u16 prop only | 4000-4021 | 4000-4022 |
| range 10000 | `{prop, sub}` | 10000-10071 | 10000-10110 (2-byte aligned) |
| range 15000 | `{prop, sub}` | 15000-15267 | 15000-15280 |

*Setting id tables in each body.[^fw1] The [Address reference](#address-reference) has where each one sits.*

Per-id u32 defaults sit in three tables in each body.[^fw1]

Option-value records are 20 bytes each. The E-M5 III has 1,215 (`cmp 1215`) and the OM-5 has 1,439
(`cmp 1439`).[^fw1] A record is `{u16 id, u16 key, → values, → codes, u16 bytes, u16 elsize, u32 flags}`.

- `key` picks a variant. `0x55`, `0x80` and `0x100` are the 1/3, 1/2 and 1 EV step lists.[^fw1]
- `elsize` 1, 2 and 4 are plain values. 64 are option structs.[^fw1]

## Key names

The `MODE_*` key names live in block 2.[^fw1]

- The E-M5 III has 0x48-byte records, `{u16 id, u16 kind, name[48], u32, u32 off, u32 n, ...}`.
- The OM-5 has dense 0x34-byte names. The index is the setting id.

The leading u16 of an E-M5 III record is an id from another numbering.[^fix1] It is shifted against the E-M5 III's own
table in runs. The shift is 0 up to 252, then −1, −2, −1, −2, −3, −4, −6, −7, and +27..+32 past 1447. 1,129 names were
placed by a property match (`confirmed`). The rest were placed by their neighbours (`aligned`) or at a run boundary
(marked `?`, a guess).

The OM-5 list is dense, and its index is the setting id. This was checked at 1459 `MODE_FOCUS_STACKING_NUMBER`, by a
code log, and at 1681-1683 `MODE_DIGITAL_ND*`, which the sequencer reads (7745).[^fw1] Ids past 1892 in the OM-5 list
(73 names, from `MODE_RESET_MY_STATE_1` on) do not follow the 3000+ ranges and were left out.

## Custom modes

Property `0x85d4` holds 9 slots of u32 per setting id.[^fw1]

- E-M5 III index = slot × 3300 + bank × 1650 + id, 29,880 values.
- OM-5 index = slot × 3786 + bank × 1893 + id, 34,200 values. The copy loop has `cmp 3786`, and a single read uses
  `slot*3786 + bank*1893`.
- The working copy `0x8b64` (3,320 / 3,800 values) uses bank × 1650 / 1893 + id.
- `0x8b54` (1,660 / 1,900) is one value per id.[^inf1]

Which 9 slots these are beyond C1-C4 is not traced.

## Store image

The user settings are saved as one 256 KB image in each body.[^fw1]

| offset | content |
|---|---|
| +0 | u16 layout id |
| +2 | u16 check word |
| +4 | u32 save counter |
| +8 | values in registry order |

*Layout of the store image.[^fw1]*

The check word makes all u16 words of the 256 KB image sum to 0. The function that computes it is byte-identical in the
OM-5. The counter is incremented before each save.[^fw1] The user-settings registry of the E-M5 III has layout id
**`0x32`**, and the OM-5's has layout id **`0x0a`**.[^fw1]

### Foreign images

A foreign image is reset, not misread.[^fw1] Boot accepts a bank only if its u16 header equals the registry's layout
id. The E-M5 III's `0x32` and the OM-5's `0x0a` differ. So each body would reset the whole store to defaults on the
other's bank, rather than read values from wrong offsets. The OM-5 check makes the same header compare.[^fw1] That the
compared id is the registry's first word on the OM-5 too is inferred from the identical store set-up.[^inf2]

## Map

Pairing is by `{property, sub}`, since that is what the camera stores. Ids are only labels.

| result | count | meaning |
|---|---:|---|
| same | 993 | same id, property, default and choices |
| moved | 831 | renumbered, otherwise identical. The ids agree up to 760 and shift from 761 (E-M5 III 761 = OM-5 760) |
| changed | 209 | same property, but the default (62), the choices (108) or the element count (90) differs |
| prop | 2 | same key name, other property: `MODE_AF_AREA_TYPE_CHANGE` `0x87a1` → `0x99a1`, `MODE_AF_FRAME_POS_CHANGE` `0x5971` → `0x5961` |
| E-M5 III only | 18 | 760 `MODE_RAW_EDIT_PIXSHIFT_SR` (OM-5 keeps `0xf0f1` under 15250), 1631-1649 (unnamed, mostly default 255), 10005 |
| OM-5 only | 327 | 313 of them saved. 79 read a property the E-M5 III also has, at a sub-index it has no menu id for |
| unused | 2 | id 4502 has no property on either body |

*Every setting id of both bodies, paired by stored property.[^fw1]*

- **OM-5-only groups.**[^fw1]
    - Live ND 1681-1683 (`0x1e41`/`0x1e51`/`0x1e61`), hand-held High Res 1680, subject detection 1684
    - Starry Sky AF 1839-1845 (`0xb981`-`0xb9c1`), My Menu 1515-1549 (`0x1b14` × 35)
    - still/movie splits of aperture, shutter, ISO, ISO limits, WB and AF area (1550-1607, 1669-1679)
    - custom AF area sizes and steps (1625-1663), lock lever and joystick (1493-1514), extra custom buttons 22-28
    - interval shooting, colour creator for RAW edit, temperature unit, GPS logger
    - the 10071-10110 block (`0xcc42`-`0xccd2`)
- **Values that are setting ids.** 20 settings store another setting's id as their value. They are the dial
  assignments (70-77, 1269-1276), the colour-tone dial (898, 1075) and two menu cursors (619, 1624). The OM-5 lists
  name the still variant where the E-M5 III names the single setting. For the S-mode main dial, E-M5 III
  {3200, 4, 2, 17, 6, 9, 107} becomes OM-5 {3200, 1671, 2, 17, 1673, 1550, 1604}. A converter must translate these
  values, not copy them. They were detected per pair by asking "does the id map explain the other body's choices better
  than the raw numbers".[^inf3]
- **Element counts.** 28 saved properties change size.[^fw1] They are the still/movie splits (count 1 → 3), AF area
  and AF home variants (1 → 6 or 8), custom buttons 13 → 20, image quality sets 10 → 11, info pattern lists and the
  three id-indexed arrays. 4 shrink (`0x1ea1`, `0x1ee1`, `0x1f01`, `0x1f31`: 2 → 1). The E-M5 III reads them from
  1632-1641 but the OM-5 from 3015-3019, so they don't have the same meaning.
- **User store.** The E-M5 III has 1,028 properties (packed `0x22cd4` B) and the OM-5 1,105 (`0x27eb8` B).[^fw1] 996
  are identical, 28 resized, 4 E-M5 III only (`0x4c22`, `0x50d2`, `0xe321`, `0xf0f1`) and 81 OM-5 only. Registry
  defaults of the shared properties are identical. The factory values that differ live in the per-id default tables.
  That is 62 settings, for example `MODE_RECVIEW` 5 vs 0, `MODE_LOCK` 0 vs 1 and `MODE_HDMI_TYPE` 16 vs 18.

## Conversion rules

The conversion rules were checked with a PC converter of our own, which is not published.[^inf4] It works on the store
image, the only copy that holds every saved value including the custom modes.

1. Decode with the source registry, checking layout id and check word.
2. Start from the target's factory settings. These are the registry defaults overlaid with the per-id defaults. The
   order in which the camera applies them after a reset is not traced.[^inf5]
3. Copy every shared property. Check each element a menu setting reads. A value outside the target's choices falls
   back to the target default. An id-valued setting is translated (id map, then the `_STILL` name rule).
4. For resized properties, copy the common elements. A new element that is a split of element 0 (OM-5
   `MODE_APERTURE_STILL` / `_MOVIE` beside `MODE_APERTURE`) gets element 0's value. An element read by settings that
   don't pair (`0x1ee1` and friends) keeps the target default.
5. Re-index `0x85d4`, `0x8b64` and `0x8b54` through the id map, with each body's slot and bank strides.
6. Source-only properties are dropped and target-only ones keep their defaults, all listed in the report.
7. Encode with the target registry, layout id, counter + 1 and a fresh check word.

The converter was tested three ways.[^fw2]

- Default images round-trip byte-identical on both bodies.
- Factory settings converted either way end up different from the target's own factory settings only in the ~30
  properties whose factory value differs.
- A synthetic E-M5 III image went to the OM-5 and back with one loss, `MODE_PIXELSIZE_SR2` 21, which is not an OM-5
  choice. The image had High Res on, ISO, aperture and the S-mode main dial set to ISO, and the same in custom-mode
  slot 0.

A checklist mode lists, by key name, every setting whose converted value differs from the target's factory value. An
owner of a stock camera can set those by hand. It needs no flashing at all.

## Open questions

- The camera's own reset order (registry defaults, then per-id defaults) and the meaning of the 9 custom-mode slots.
- The 19 E-M5 III ids 1631-1649 have no key name. Their properties are mostly the default 255.
- The `?` names at run boundaries (155) are guesses. Use the property columns, not the names, for those.
- Not tried on a camera.

## Address reference

E-M5 III 1.7 and OM-5 1.2 block0 addresses.

| what | E-M5 III 1.7 | OM-5 1.2 |
|---|---|---|
| setting id → `{u16 prop, u16 sub}`, main table | `0x604de68c` | `0x60514fec` |
| range 3000 | `0x604e0054` | `0x60516d80` |
| range 4500 | `0x604e00a4` | `0x60516e04` |
| range 4000 | `0x604e00d0` | `0x60516e30` |
| range 10000 | `0x604e00fc` | `0x60516e5e` |
| range 15000 | `0x604e021c` | `0x6051701a` |
| id lookup (walks the ranges) | `0x602e6b2a` | `0x602f18d1` |
| per-id u32 defaults | `0x604b20ac` / `0x604b3a74` / `0x604b3b94` | `0x604d8f38` / `0x604daccc` / `0x604dae88` |
| option-value records, 20 B | `0x604d4ee4` (`cmp 1215` at `0x602d3f82`) | `0x6050a2a0` (`cmp 1439` at `0x602deb04`) |
| `MODE_*` key names, block 2 | `0x45e20400` | `0x44ae03f0` |
| key name check, setting 1459 code log | | `0x60e4ebaa` |

*Setting tables and lookups.[^fw1]*

| what | E-M5 III 1.7 | OM-5 1.2 |
|---|---|---|
| user-settings registry (layout id) | `0x60098998` (`0x32`) | `0x6009f030` (`0x0a`) |
| user-settings live image / bank RAM / size | `0x623d1000` / `0xa294e000` / 256 KB | `0x623de800` / `0xa29d7000` / 256 KB |
| other registries | 17 adjust `0x600925c8`, `0x60079294`, `0x3f` `0x60094134`, fd1 `0x600bd008`, fd2 `0x600bd038` | `0x60098544`, `0x6007dc8c`, `0x48` `0x6009a138`, `0x600c8a40`, `0x600c8a70` |
| property setter | `0x6005cf1c` | `0x6005fb3e` |
| check word | `0x6005ace4` | `0x6005c694` (byte-identical) |
| save counter increment | `0x6005ad02` | `0x6005d920` |
| layout id check at boot | `0x6005ac7b` | `0x6005d899` |
| custom-mode copy | `0x602e6ded` | copy loop `cmp 3786` at `0x602f1bc7`, single read at `0x602f1c20` |

*Settings store and custom modes.[^fw1]*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware, 2026-11-23.
[^fw2]: Read in the firmware and tested with our converter on a PC, 2026-11-23.
[^inf1]: Inferred layout, 2026-11-23.
[^inf2]: Inferred from the identical store set-up, 2026-11-23.
[^inf3]: Inferred per pair, 2026-11-23.
[^inf4]: Read in the firmware and partly inferred, 2026-11-23.
[^inf5]: Inferred, not traced, 2026-11-23.
[^fix1]: A correction to how the E-M5 III key names were placed, 2026-11-23. See [History](#history).

## History

- 2026-11-23: corrected the reading of the leading u16 of an E-M5 III `MODE_*` record. It is an id from another
  numbering.

