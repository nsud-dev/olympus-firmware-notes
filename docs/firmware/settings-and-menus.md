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

- **One stock row traced end to end (High Res Shot, 2026-11-20).** Setting id 772 → table entry `{u16 0xf1a1, u16 0}`
  (property 0xf1a1, sub-index 0; value size `0xf1a1 & 7` = 1, so u8) → listed in the store-50 registry at 0x600bcc48, so
  it is a saved user setting. Default (table 0x604b20ac) 1. Menu: 6th id of the Shooting 2 tab list 0x6106a644
  (603, 471, 266, 682, 5005, 772, 180); title entry 0x61092af0 and help entry 0x61092d84 are kind 4 with string ids
  2438 "High Res Shot" and 2439 (help text); option-value record id 772 in 0x604d4ee4 → 2 one-byte values {0, 1}. [code]
- **Same table on every body (2026-11-20).** The setting → property table starts with the same words on all six bodies:
  E-M5 III 0x604de68c, OM-5 0x60514fec, E-M1 III 0x604e4d90, OM-5 II 0x605193e8, PEN-F 0x603fa158, OM-1 block0 offset
  0x6007c4. Property 0xf1a1 (High Res Shot on the E-M5 III) is setting 772 on the E-M5 III, 771 on the OM-5 and OM-5 II,
  770 on the E-M1 III and OM-1, 779 on the PEN-F: same property, different id. [code] (that 0xf1a1 is High Res on the
  other bodies is [inferred]). The "acc flash write" store save is in all but the PEN-F (string not found). [code]

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
- Saved settings must not be lost (2026-10-30).
- Lead (caduceus-ep7 `docs/INTERNAL_STORAGE.md`, 2026-11-18): on the E-P7 the settings image has ~109 KB unused after
  its records; a block there is saved by the camera's own settings save, survives menu reset and the restore file.
  Not camera-tested there. Here the backup tail "isn't cleared" (above), so the same could keep dev-page/TUNING values
  across power-off; needs the record end and a forget action. [inferred] details

### When saved settings are written (2026-11-18)

- Store object (28 B): +0 store id, +2 bank in use, +4/+8 bank addresses, +0xc registry, +0x10 live image, +0x14 size.
  Store 50 (pointer 0xa2637870): live image 0x623d1000, one bank at 0xa294e000. Boot loads the **whole** bank into the
  live image (0x6005aa15 -> 0x6005ad45). [code]
- Save 0x6005aaaf compares the whole image (+8, size-12 bytes) with the bank and writes it only if anything differs
  (counter, 16-bit sum, cache write-back, flash write 0x6005a177). **Raw bytes in the unused tail are saved too.** [code]
- Callers with store 50: the power-down path 0x60128eb1 (saves store 50, then spins with interrupts masked until power
  is cut), 0x601fc9a7 ("Power ???"), 0x60062e44 "acc flash write" (all stores), shell "w" 0x6005bad0. A battery pull
  loses changes since the last save. [code]/[inferred]
- Property get 0x6005ce6b(prop, index, 0), set 0x6005cf1c(prop, index, 0, value) (writes cached and uncached alias);
  one global hash, slot = prop >> 4 (8 B), filled from every registry at boot. 1318 slots used on stock 1.7, none
  shared; 0x1e31-0x1e71 and 0xfe00-0xfe30 free. [code]
- Storage order and menu position are independent: a row reaches its value via setting id -> property -> index, so a
  native row can sit where the OM-5 has it while its value is appended at the end of the store. [code]

### Per-setting data behind a setting id (2026-11-18)
- Default value per id: 0x602d364d (u32 tables 0x604b20ac for 0-1649, 0x604b3a74 for 10000+, 0x604b3b94 for 15000+).
  Two per-id RAM arrays (get/set 0x602e6f35/0x602e6fe1, 0x602e7088/0x602e7134; 0-1649 at 0x62123030 / 0x62125048);
  reset loops 0x602cd3b0 / 0x602d2e0c fill them per range with explicit bounds. A new id range needs all of these plus
  the {prop, sub} entry and the handle cache. [code] private notes 7.4
- OM-5 1.2 Shooting Menu 2 = 771 High Res, **1681 Live ND**, 603, 471, 266, 682, 5005 (list 0x6122e41c); E-M5 = 603, 471,
  266, 682, 5005, 772 High Res, 180. Live ND joins the bracketing-style special-item chain (OM-5 0x6097ad2d adds 1681;
  E-M5 twin **0x608d5b33**, dialog 0x608d671c; the older "0x6096bc89" is a 603/471 interlock, not this chain). 58 OM-5 functions use 1681-1683 as immediates, mostly "if Live ND is on" checks in display and
  interlock code. [code]

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

**Trying a menu change in the emulator (om-emu, 2026-11-05).** A data-only patch that adds setting 1448 to the
Bracketing page renders "Set number of shots 8". The **visible rows come from the submenu u16 list** (table 0x61069f60,
Bracketing 0x6106a110, Focus BKT 0x6106a458 key 0x8a), and descriptors are found by id. The new row can't be edited
(RIGHT does nothing) until the page's per-item picker code knows the id. [code]

Other tables: USB Mode options 0x61074fd2; AF mode list 0x6107e27c (0,1,2,3,5,9). [code]

**Row actions and the page screen stack (2026-11-17).** OK and RIGHT on a Custom-menu row are 24-byte dispatch records
`{u32 level, u16 item, u16 sub, u32 fn, u32 group, u16 target, u32 fn2}` per page (J2: OK table 0x6106242c, RIGHT table
0x610623e4); with fn 0 the matcher 0x60d5af27 opens controller (group, target). Each page actuator keeps a two-slot
screen stack (depth u16 +0x4c, screens +0x54/+0x58); at depth 2 every key goes to the sub-screen's vt[0]. The list is
drawn from GUI variable 0x38 (0xC82 B), published with 0x60c8165d(id, size, buf, 1). Same family as the E-M10 II.
[code]+[emu]

**Adding a row to a top-level tab (Live ND Shooting, 2026-11-19).** [emu]+[code]

- Tab lists come from the key table 0x6106a714: 8-byte records `{u16 key, u16 n, → variant records}` for keys 0x4e-0x54
  (Shooting 1, Shooting 2, Movie, Playback, Custom, Custom-B, Setup). Each variant record is `{u16 variant, u16 n,
  → u16 ids}`; the loader 0x60d6211d takes the variant-0 record only. Shooting 1 has 6 ids (3357, 111, 10, 269, 34, 5004),
  Shooting 2 has 7. [code]
- **A tab page holds 7 rows at most.** An 8th id is drawn over row 0 and the cursor goes off screen (no scrolling). The
  OM-5 also keeps Shooting 2 at 7 ids. Moving RC Mode (180) to the end of Shooting 1 works: the row draws with its value. [emu]
- [code] Per-tab descriptors at 0x610938b0, 28 bytes: `{u16 tab, u16 n, → titles, → help, n_values, → value list (8 B
  {u16 id, u16 nopts, → options}), n2, → list2}`. Title/help entries are 12 bytes `{u32 id, u16 kind, u16 string,
  u32 base}`. Kind 5 (inline text) crashes the title renderer (OSD BMP_LUT error); use kind 4 string ids. [emu]
- **String lookup** 0x60c9350c(id) (132 callers): language byte 0x61ea1dac, per-language arrays 0x61eb7424. All 34
  languages have 3447 strings. A 5-byte jmp at 0x60c9350c to a 42-byte handler that serves ids 4000-4015 from our own
  table (else the native path) gives new text in every language. Worked in om-emu: "Live ND Shooting" row with help. [emu]+[code]
- Decision (2026-11-19): move RC Mode to the end of Shooting 1 so Live ND Shooting sits after High Res in
  Shooting 2, as on the OM-5. [decision]
- **A new native submenu page works in om-emu** (RIGHT on the row opens "Live ND Shooting" with ND Number and LV
  Simulation rows). The chain: row record (14, screen) → group-0xe screen table 0x610b166c (125 × 24 B
  `{screen, 0x16, ctl, 0x33, key, 0}`, group table 0x610b4264) → controller table 0x61064b98 (169 × 36 B
  `{ctl, type, key, → items, n, → RIGHT, n, → OK, n}`, count at 0x60d593f6/0x60d594ca/0x60d5b5a6) → rows from the
  submenu table 0x61069f60 (146 × 12 B `{key, → u16 ids, n}`, count at 0x60d61d08/0x60d62555) → page records
  0x610d5794 / 0x610e2f1c (124 × 24 B `{key, → 36 B descriptors, n, 0, → page title + help, → per-item 8 B}`,
  `cmp 124` at 0x60e03f65/0x60e06aaa). Correction: the page records start with the key (earlier notes read them one
  field off). [emu]+[code]
- **Pickers:** a row's picker takes its option count and values from an option-value record per
  id: RAM hash 0x62118d08 (128 buckets, nodes from 0x62118f08) built at boot by 0x602d3f34 from the static table
  0x604d4ee4 (1215 × 20 B `{u16 id, u16 0x80, → values, 0, u16 size, u16 elem, 0x100}`), read via 0x602d3b93 →
  0x602d3f8b. No record = empty picker. With records for 16001/16002 both pickers draw (ND2-ND16, Off/On). Kind-5
  option labels are 8-bit text. Option lists inside a page use that page copy's base. [emu]+[code]
  Adding records at boot (2026-11-19 evening): 0x602d3f34 has one caller, `call 0x602d3f34,[d2,a2,a3],12` at
  0x602d2da0 followed by `clr d0; ret [],4`; replacing it with a jmp to a stub that makes the same call and then prepends
  nodes `{→ record, → old head}` to buckets 0x62118d08+4*(id&127) fills the pickers with no RAM pokes (only d0/a0 are
  free there). Page records' second title entry is kind 0 in native pages; a kind-4 page help draws over the row help.
  [emu]+[code]
- **Values stick (om-emu, 2026-11-19):** jumping from the menu getter 0x602e6a02 and setter 0x602e6f11 to a handler
  that serves ids 16000-16031 (else native) makes the whole flow work: Live ND Shooting Off/On, ND Number ND2-ND16,
  LV Simulation Off/On, shown on the tab row and page. A Bracketing-style level-2 record (inline Off/On on the tab)
  opened its picker on row 0, so the On/Off row lives in the page. [emu]


The working method (values in the settings-image tail, rows and page, where the code may sit) is written up on
[saved settings and menu rows](../features/saved-settings-and-menu-rows.md). [camera] 2026-11-19

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
- **Setting restriction rules** [code] 2026-11-21: the table that maps one setting's value when another has a given
  value (what greys menu options) is at **0x60477dbc** (about 280 20-byte records `{u16 sid, u16 flags, u32 rules,
  u16 count}`; rules `{u32 cond, u16 n, u32 map, u16 n}`, cond terms `{u16 sid, u16 value, u32 0}`, maps
  `{s16 from, s16 to}`). Format from the E-M1 III Mod Builder (`tools/patch_hhrs_flash.py`, E-M1 III 1.6 table
  0x604920dc, a repointed map camera-checked there). Sids not yet named.
- The E-M5 III has **no** E-P7-style settings facade vtable (0x60afd564 is 85 "not implemented" tag stubs) and no 20-byte
  validator table (scan of 0x604a1020-0x60521020). Allowed values probably live in per-setting class objects (0x608febd4
  for 1448). [code]/[inferred]
- Plan CS0-CS4 (trace, card config loader, write-back, card names via kind-5 labels, settings backup):
. [inferred]
- A lesson from their Lowest S/S row (MIN_SHUTTER m2-m4, E-P7): adding a row for a hidden stock setting needs both the
  page's row-info records and the drawn row list (m2 patched only the records and got no row); a long inline value column
  overflows, so open the stock picker screen instead (m4). This applies to our first menu step. [theirs]

- 2026-11-17 atx/fenykl (E-M10 II) does the card-settings idea as one stock menu row (Eye-Fi) opening its own page that the
  stock list view draws (copied GUI data slot, kind-5 text, `gui_data_set`), values in two CRC'd card text files; no settings
  store. [inferred]

## On-screen text (GUI strings)

All menu text lives in block 1. Entries 1-34 of its directory are languages: **English is 8** on the E-M5 III and
E-M1 III and **5** on the OM-5 and OM-5 II. Each language has an index of UTF-16LE strings, and code refers to a string
by its **index**. The E-M5's English has 3447 strings with 177 bytes of slack, and block 1 ends with ~6.7 MB of zeros.
[code]


