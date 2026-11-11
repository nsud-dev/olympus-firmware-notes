# Settings, properties, menus and GUI strings

Every camera setting, from ISO to the hidden debug switches, lives in a numbered store, and the menus are built from
tables that point into it. This page explains how menu settings map to stored values, how saved settings are kept in
flash (and how not to wipe them), how menu pages are put together, an approach for keeping our own feature settings on
the card, and where the on-screen text comes from.

Two kinds of number matter, and they are easy to mix up:

- A **setting id** is what a menu row refers to. Setting ids differ between camera models.
- A **property** is the stored value itself, with its own number. Properties line up much better between models, so
  when comparing bodies, always map through the property.

Tags: **[code]** read in the firmware, **[camera]** seen on a real E-M5 III, **[inferred]** not traced or tested.

## From setting ids to properties

- A table maps menu **setting ids** to **properties**: E-M5 III **0x604de68c** (ids 0-1649, checked by 23 `cmp 1649`
  bounds checks), OM-5 0x60514fec (0-1892). Setting ids differ between bodies (High Res is 771 on one and 772 on the
  other), so map via the property. [code]
- The E-M5 III has 902 properties and the OM-5 956, with 890 shared. The first 760 ids are identical; after that they
  are shifted. [code]
- Settings also have text key names, `MODE_*`. On the E-M5 III they are in block 2 sub-block 0x45e20000 (0x48-byte
  records, id = 0x10000+index); the E-M1 III uses 0x34-byte records. [code]
- 2026-11-05: the OM-5 1.2 has 4,869 `MODE_*` keys and the E-M5 III 3,634; 1,307 are OM-5-only, mostly `_STILL`/`_MOVIE`
  renames. Real gaps include `EXPANDED_CONTRAST_MODE_LOG`, `FOCUS_STACKING_NUMBER`, `MYMENU*`,
  `AF_AREA_SIZE_*_CUSTOM_1-4`, `BLE_ACCESSORY_REMOCON`, `SYNCHRO_SCAN_STILL` and `ANTI_FLICKER_STILL`. [code]

- 2026-11-05: the E-M5 III already has the OM-5's focus-stack-count property 0x9842 (E-M5 setting 1448, OM-5 1459), but
  no menu item for it. The trailing u32 in the E-M5's block-2 `MODE_*` records is not a reliable setting id (it is off by
  one for the focus-BKT keys), so map ids by how the code uses them. [code]

- Missing on the E-M5 III: Live ND properties 7745 (on), 7761 (ND number) and 7777 (LV simulation); HHHR method 7729;
  Starry Sky AF 0xb981-0xb9c1. Property 36537 exists but belongs to develop/gradation, **not** Live ND: don't use it.
  [code]

### No free setting ids (2026-11-05)

The lookup 0x602e6b2a walks these ranges: 0-1649 (table 0x604de68c, RAM handle cache 0xa25b8cf0), 3000-3019, 4000-4021,
4500-4521, 10000-10071, 15000-15267 (table 0x604e021c, cache 0xa25ba8d8); id 6000 is one RAM u16. [code]


- The tables and caches are packed back to back and every entry has a property, so **there is no free id in any range,
  and none can grow in place.**
- 9 `cmp 15267` sites in the settings core walk all the ranges. Menu items already use 3000-3003 and 10003.
- Plan: a new range 16000-16031 served by hooks at those 9 sites. That keeps the C1-C4 custom-mode layout, which growing
  0-1649 would break.

## How saved settings are stored

The user settings live in store id 0x32: registry 0x60098998..0x600bd004 (1028 properties), backup 0x623d1000, 256 KB,
in two flash banks. A bank is valid if its header u16 equals the store id and its 16-bit sum is 0; the newer bank wins by
the counter at +4; otherwise the whole store is reset. [code]

What that means for patches: [code]

- Values are packed in registry order **without ids**. Inserting a setting in the middle shifts every later one, and
  changing the store id resets everything. **Appending at the end and keeping the id is safe** (range-check the new
  value, because the backup's tail isn't cleared).
- Custom modes are saved by setting id (property 34260, slot×3300 + bank×1650 + id), and ids above 1649 are ignored.
  There are no free ids at or below 1649.
- The maintainer doesn't want to lose saved settings (2026-10-30).

## How menus are built

**Where the tables are.** Tabs: E-M5 0x6106a6d4. The Shooting Menu 2 record 0x6106a6dc points to 0x6106a644 (7 ids).
The submenu table is 0x61069f60 (146 records). Title and help lists are at 0x61092a24 / 0x61092cb8, with counts in the
per-tab descriptor 0x610938b0. Option descriptors are 36 bytes each from 0x610d02b8. The list of special shooting modes
that exclude each other is 0x60e7162c. [code]

**Submenu pages (2026-11-05).** [code]

- A page record is 24 bytes: `{→ 36 B descriptors, n, 0, → page titles, → per-item 8 B strings, key}`. Focus BKT is
  0x610d5e58 (plus a copy at 0x610e35e0), key 0x48, items 1323/858/861/1081. [code]
- The page handler table 0x610e4268 has 12-byte entries `{key, viewer, action}`; key 0x47 → viewer 0x60e096d7, a `cmp`
  chain over the item ids. [code]
- Option kinds: 4 = string id, 5 = inline UTF-16 text, 1 = number + unit.
- Tab page lists hold setting ids **and** menu-only ids (3xxx, 5xxx).
- Most lists exist in 2 copies (3 on the OM-5) and use counts: patch every copy.

**Trying a menu change in the emulator (om-emu M0, 2026-11-05).** A data-only patch that adds setting 1448 to the
Bracketing page renders "Set number of shots 8". The **visible rows come from the submenu u16 list** (table 0x61069f60,
Bracketing 0x6106a110, Focus BKT 0x6106a458 key 0x8a), and descriptors are found by id. The new row can't be edited
(RIGHT does nothing) until the page's per-item picker code knows the id. [code]

Other tables: USB Mode options 0x61074fd2; AF mode list 0x6107e27c (0,1,2,3,5,9). [code]

**The OM-5 II's menus.** Its UI is the OM-1-style menu, so porting the whole UI would be a rewrite (1.4-1.65 MB of new
GUI code, a settings model with +917/−393 keys); reorganising menus or porting single screens is realistic.
[code]+[inferred] As booted in om-emu, the OM-5 II 1.1 menu has tabs Shooting 1 (8 pages), Shooting 2 (Computational
Modes, Other Shooting Functions, Bracketing), AF (7 pages), Movie, Playback, Custom, Setup and My Menu; screenshots and
the page-title list are in. 2026-11-05 [code]

## Keeping feature settings in a card file (2026-11-08)

Adding settings to the internal store is risky (see above), so we looked at how the caduceus project (E-P7 patches)
avoids it.

- caduceus keeps feature settings out of the internal store: a validated card file (magic, version, firmware build,
  main SHA prefix, CRC-32, per-byte ranges) is read once on the first half-press. Edits made on the camera are written
  back as `.NEW` (read back), the old file is renamed to `.BAK`, then `.BIN` is written (read back), and the dirty flag
  is cleared last. Camera-proven on the E-P7. [inferred] for us
- The E-M5 III has **no** E-P7-style settings facade vtable (0x60afd564 is 85 "not implemented" tag stubs) and no 20-byte
  validator table (scan of 0x604a1020-0x60521020). Allowed values probably live in per-setting class objects (0x608febd4
  for 1448). [code]/[inferred]
- Plan CS0-CS4 (trace, card config loader, write-back, card names via kind-5 labels, settings backup):
. [inferred]
- A lesson from their Lowest S/S row (MIN_SHUTTER m2-m4, E-P7): adding a row for a hidden stock setting needs both the
  page's row-info records and the drawn row list (m2 patched only the records and got no row); a long inline value column
  overflows, so open the stock picker screen instead (m4). This applies to our M1. [theirs]


## On-screen text (GUI strings)

All menu text lives in block 1. Entries 1-34 of its directory are languages: **English is 8** on the E-M5 III and
E-M1 III and **5** on the OM-5 and OM-5 II. Each language has an index of UTF-16LE strings, and code refers to a string
by its **index**. The E-M5's English has 3447 strings with 177 bytes of slack, and block 1 ends with ~6.7 MB of zeros.
[code]


