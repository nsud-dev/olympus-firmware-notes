# Settings, properties, menus and GUI strings

## Settings → properties
- Menu **setting IDs** map to **properties** through a table: E-M5 III **0x604de68c** (IDs 0-1649, 23 `cmp 1649`
  bound checks), OM-5 0x60514fec (0-1892). Setting IDs differ between bodies (High Res 771 vs 772); map via property. [code]
- E-M5 III 902 properties, OM-5 956, 890 shared. First 760 IDs identical, the rest shifted. [code]
- `MODE_*` key names: E-M5 III block 2 sub 0x45e20000 (0x48-byte records, id = 0x10000+index); E-M1 III 0x34-byte. [code]
- 2026-11-05: OM-5 1.2 has 4,869 `MODE_*` keys, E-M5 III 3,634; 1,307 OM-5-only (mostly `_STILL`/`_MOVIE` renames). Real gaps
  include `EXPANDED_CONTRAST_MODE_LOG`, `FOCUS_STACKING_NUMBER`, `MYMENU*`, `AF_AREA_SIZE_*_CUSTOM_1-4`, `BLE_ACCESSORY_REMOCON`,
  `SYNCHRO_SCAN_STILL`, `ANTI_FLICKER_STILL`. [code]
- 2026-11-05: E-M5 III already has the OM-5 focus-stack-count property 0x9842 (E-M5 setting 1448, OM-5 1459), with no menu
  item. The trailing u32 in E-M5 block-2 `MODE_*` 0x48-byte records is not a reliable setting id (off by one for the focus-BKT
  keys); map ids by code use. [code]
- Missing on E-M5 III: Live ND props 7745 (on), 7761 (ND number), 7777 (LV simulation); HHHR method 7729; Star AF
  0xb981-0xb9c1. Prop 36537 exists but belongs to develop/gradation, **not** Live ND: don't use it. [code]

- **Setting ID ranges (2026-11-05):** lookup 0x602e6b2a walks 0-1649 (table 0x604de68c, RAM handle cache 0xa25b8cf0),
  3000-3019, 4000-4021, 4500-4521, 10000-10071, 15000-15267 (table 0x604e021c, cache 0xa25ba8d8); id 6000 is one RAM u16.
  Tables and caches are packed back to back, every entry has a property: **no free id in any range, none can grow in
  place.** 9 `cmp 15267` sites in the settings core walk all ranges. Menu items already use 3000-3003 and 10003. Plan: a
  new range 16000-16031 served by hooks at those 9 sites (keeps C1-C4 layout, which growing 0-1649 would break). [code]

## Saved-settings store
- User-settings store id 0x32: registry 0x60098998..0x600bd004 (1028 props), backup 0x623d1000, 256 KB, two flash banks.
  Valid if header u16 == store id and 16-bit sum == 0; newer by counter at +4; else whole store reset. [code]
- Values are packed in registry order **with no ids**: inserting mid-list shifts every later setting; changing the id resets
  all. **Append at the end and keep the id** = safe (range-check the new value; the backup tail isn't cleared). [code]
- Custom modes are saved by setting id (prop 34260, slot×3300 + bank×1650 + id); ids > 1649 are ignored. No free ids ≤ 1649. [code]
- The maintainer doesn't want to lose saved settings (2026-10-30).

## Menus
- Tabs E-M5 0x6106a6d4; Shooting Menu 2 record 0x6106a6dc → 0x6106a644 (7 ids). Submenu table 0x61069f60 (146
  records). Title/help lists 0x61092a24/0x61092cb8 with counts in per-tab descriptor 0x610938b0. Option descriptors
  36 B at 0x610d02b8+. Special-shooting exclusivity list 0x60e7162c. [code]
- **Submenu page records (2026-11-05):** 24 B `{→ 36 B descriptors, n, 0, → page titles, → per-item 8 B strings, key}`;
  Focus BKT = 0x610d5e58 (+ copy 0x610e35e0), key 0x48, items 1323/858/861/1081. Page handler table 0x610e4268:
  12 B `{key, viewer, action}`, key 0x47 → viewer 0x60e096d7 (a `cmp` chain over the item ids). Option kinds: 4 = string
  id, 5 = inline UTF-16 text, 1 = number + unit. Tab page lists hold setting ids **and** menu-only ids (3xxx, 5xxx).
  Most lists exist in 2 copies (OM-5: 3) and use counts: patch every copy. [code]
- **om-emu M0 (2026-11-05):** a data-only patch adding setting 1448 to the Bracketing page renders "Set number of shots 8".
  The **visible rows come from the submenu u16 list** (table 0x61069f60, Bracketing 0x6106a110, Focus BKT 0x6106a458 key
  0x8a), descriptors are found by id; the new row can't be edited (RIGHT does nothing) until the page's per-item picker code
  knows the id. [code]
- USB Mode option table 0x61074fd2; AF mode list 0x6107e27c (0,1,2,3,5,9). [code]
- OM-5 II UI is the OM-1-style menu: a full UI port is a rewrite (1.4-1.65 MB new GUI code, settings model +917/−393
  keys); menu reorganisation or per-screen ports are realistic. [code]+[inferred]
- OM-5 II 1.1 menu as booted in om-emu: tabs Shooting 1 (8 pages), Shooting 2 (Computational Modes, Other Shooting Functions, Bracketing), AF (7 pages), Movie, Playback, Custom, Setup, My Menu; screenshots and page-title list in. 2026-11-05 [code]

## Card files for settings (2026-11-08)
- caduceus (E-P7) keeps feature settings out of the internal store: a validated card file (magic, version, fw build,
  main SHA prefix, CRC-32, per-byte ranges) is read once on the first half-press; on-camera edits are written back as
  `.NEW` (read back) → old file to `.BAK` → `.BIN` (read back), dirty flag cleared last. Camera-proven on the E-P7. [inferred] for us
- E-M5 III has **no** E-P7-style settings facade vtable (0x60afd564 is 85 "not implemented" tag stubs) and no 20-byte
  validator table (scan of 0x604a1020-0x60521020); allowed values likely live in per-setting class objects (0x608febd4 for
  1448). [code]/[inferred]
- Plan CS0-CS4 (trace, card config loader, write-back, card names via kind-5 labels, settings backup) in. [inferred]
- Their Lowest S/S row (MIN_SHUTTER m2-m4, E-P7): adding a row for a hidden stock setting needs both the page's row-info records and the drawn row list (m2 patched only records: no row); a long inline value column overflows, so open the stock picker screen instead (m4). Applies to our M1. [theirs]

## GUI strings
- Block 1 directory; entries 1-34 = languages; **English = 8** on E-M5 III / E-M1 III, **5** on OM-5 / OM-5 II.
  Each language has an index of UTF-16LE strings; code uses the **index**. E-M5 English: 3447 strings, 177 B slack;
  block 1 has ~6.7 MB zero tail. [code]

