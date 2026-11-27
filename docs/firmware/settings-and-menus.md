# Settings and menus: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Settings and menus](../guides/settings-and-menus.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

Every camera setting, from ISO to the hidden debug switches, lives in a numbered store. The menus are built from tables
that point into it. This page explains how menu settings map to stored values and how saved settings are kept in flash
(and how not to wipe them). It also covers how menu pages are put together, an approach for keeping our own feature
settings on the card, and where the on-screen text comes from.

Two kinds of number matter, and they are easy to mix up.

- A **setting id** is what a menu row refers to. Setting ids differ between camera models.
- A **property** is the stored value itself, with its own number. Properties line up much better between models. So
    when comparing bodies, always map through the property.

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred, a decision or seen in an emulator, amber = a correction.

## From setting ids to properties

A table maps menu setting ids to properties. On the E-M5 III it covers ids 0 to 1649, checked by 23 `cmp 1649` bounds
checks. On the OM-5 it covers ids 0 to 1892.[^fw1] Setting ids differ between bodies (High Res is 771 on one and 772 on
the other), so map via the property.[^fw1]

- The E-M5 III has 902 properties and the OM-5 956, with 890 shared. The first 760 ids are identical. After that they
    are shifted.[^fw1]
- Settings also have text key names, `MODE_*`. On the E-M5 III they are in a block 2 sub-block, in 0x48-byte records
    with id = 0x10000 + index. The E-M1 III uses 0x34-byte records.[^fw1]
- The OM-5 1.2 has 4,869 `MODE_*` keys and the E-M5 III 3,634. Of these, 1,307 are OM-5-only, mostly `_STILL` and
    `_MOVIE` renames. Real gaps include `EXPANDED_CONTRAST_MODE_LOG`, `FOCUS_STACKING_NUMBER`, `MYMENU*`,
    `AF_AREA_SIZE_*_CUSTOM_1-4`, `BLE_ACCESSORY_REMOCON`, `SYNCHRO_SCAN_STILL` and `ANTI_FLICKER_STILL`.[^fw2]
- The E-M5 III already has the OM-5's focus-stack-count property `0x9842` (E-M5 setting 1448, OM-5 1459), but no menu
    item for it.[^fw2]
- The trailing u32 in the E-M5's block 2 `MODE_*` records is not a reliable setting id. It is off by one for the
    focus-BKT keys, so map ids by how the code uses them.[^fw2]
- Missing on the E-M5 III are the Live ND properties 7745 (on), 7761 (ND number) and 7777 (LV simulation), HHHR method
    7729 and Starry Sky AF `0xb981` to `0xb9c1`.[^fw1]
- Property 36537 exists but belongs to develop and gradation, **not** Live ND. Don't use it.[^fw1]

### One stock row end to end

High Res Shot is traced from its menu row to its stored value.[^fw3]

1. Setting id 772 leads to the table entry `{u16 0xf1a1, u16 0}`. That is property `0xf1a1`, sub-index 0. Its value
   size is `0xf1a1 & 7` = 1, so u8.
2. The property is listed in the store-50 registry, so it is a saved user setting. Its default is 1.
3. In the menu it is the 6th id of the Shooting 2 tab list (603, 471, 266, 682, 5005, 772, 180).
4. The title entry and the help entry are kind 4, with string ids 2438 "High Res Shot" and 2439 (help text).
5. Option-value record id 772 gives 2 one-byte values {0, 1}.

### Same table on every body

The setting-to-property table starts with the same words on all six bodies.[^fw3] The same property has a different
setting id on each.

| body | High Res Shot setting id (property `0xf1a1`) |
|---|---:|
| E-M5 III | 772 |
| OM-5 | 771 |
| OM-5 II | 771 |
| E-M1 III | 770 |
| OM-1 | 770 |
| PEN-F | 779 |

*Setting id of property `0xf1a1` on each body. Table addresses are in the [address reference](#address-reference).*

That `0xf1a1` is High Res on the other bodies is inferred.[^inf1] The "acc flash write" store save is in all but the
PEN-F, where the string was not found.[^fw3]

### No free setting ids

The setting lookup walks these id ranges.[^fw2]

- 0 to 1649, with its own table and RAM handle cache.
- 3000 to 3019, 4000 to 4021, 4500 to 4521, 10000 to 10071 and 15000 to 15267, served by a second table and cache.
- Id 6000 is one RAM u16.

The tables and caches are packed back to back, and every entry has a property. So **there is no free id in any range,
and none can grow in place.**[^fw2]

- 9 `cmp 15267` sites in the settings core walk all the ranges. Menu items already use 3000 to 3003 and 10003.[^fw2]
- The plan is a new range 16000 to 16031, served by hooks at those 9 sites. That keeps the C1 to C4 custom-mode layout,
    which growing 0 to 1649 would break.

## How saved settings are stored

The user settings live in store id `0x32`. Its registry lists 1028 properties, and its backup is 256 KB in two flash
banks.[^fw1]

- A bank is valid if its header u16 equals the store id and its 16-bit sum is 0.
- The newer bank wins, by the counter at +4.
- Otherwise the whole store is reset.

What that means for patches.[^fw1]

- Values are packed in registry order **without ids**.
- **Appending at the end and keeping the id is safe.** Range-check the new value, because the backup's tail isn't
    cleared.
- Custom modes are saved by setting id (property 34260, slot × 3300 + bank × 1650 + id). Ids above 1649 are ignored,
    and there are no free ids at or below 1649.
- Saved settings must not be lost.[^pol1]

> [!WARNING]
> Inserting a setting in the middle of the registry shifts every later value, and changing the store id resets every
> saved setting.

A lead comes from the caduceus project (its `docs/INTERNAL_STORAGE.md`). On the E-P7 the settings image
has about 109 KB unused after its records. A block there is saved by the camera's own settings save, and it survives a
menu reset and the restore file. It was not camera-tested there. Here the backup tail isn't cleared (above), so the
same could keep dev-page and TUNING values across power-off. That needs the record end and a forget action.[^inf2]
See also: Settings kept in the camera.

### When saved settings are written

A store object is 28 bytes.[^fw4]

| offset | field |
|---|---|
| +0 | store id |
| +2 | bank in use |
| +4, +8 | bank addresses |
| +0xc | registry |
| +0x10 | live image |
| +0x14 | size |

*Layout of a store object.*

- Store 50 has one bank. Boot loads the **whole** bank into the live image.[^fw4]
- The save function compares the whole image (from +8, size − 12 bytes) with the bank. It writes only if anything
    differs, with the counter, the 16-bit sum, a cache write-back and the flash write. **Raw bytes in the unused tail
    are saved too.**[^fw4]
- Callers that save store 50 are the power-down path, a "Power ???" path, "acc flash write" (all stores) and the shell
    command "w". The power-down path saves store 50, then spins with interrupts masked until power is cut.[^fw4]
- A battery pull loses changes since the last save.[^inf3]

Other stores sit beside store 50.

- **Store 63 (`0x3f`)** is a separate 64 KB store, the "second store", with its own registry, live image and two
    flash banks. It holds the maintenance counters, shutter count R = `0x8344` among them. Packed values are aligned to
    their own size (u16 on 2, u32 on 4). Strings are byte-packed.[^fw9] See also:
    [Shutter](../hardware/shutter-technical.md#where-r-is-stored).
- **Store 50 also holds the damage (fault) history**, property `0x8072`, 5 × u16 at packed offset 912. The pixel-defect
    maps are stores fd1 (id 2) and fd2 (id 1).[^fw9] See also: [Maintenance](maintenance-technical.md).
- Properties are read with a getter `(prop, index, 0)` and set with a setter `(prop, index, 0, value)`. The setter
    writes both the cached and the uncached alias.[^fw4]
- One global hash has a slot for each prop >> 4 (8 B), filled from every registry at boot. 1318 slots are used on stock
    1.7, none shared. Property ranges `0x1e31` to `0x1e71` and `0xfe00` to `0xfe30` are free.[^fw4]
- Storage order and menu position are independent. A row reaches its value via setting id, then property, then index.
    So a native row can sit where the OM-5 has it while its value is appended at the end of the store.[^fw4]

### Property hash layout

The property hash has 4096 slots of 8 B, `{u16 prop, u16 count, u32 data}`, with slot = prop >> 4.[^fw8]

- Overrides from a CSV import sit in a second table, used while a u16 flag is non-zero.[^fw8]
- On 1.7 in om-emu, 2,257 slots are used (91,086 values). The largest is `0x85d4` with 29,880.[^emu3]
- The getter takes d0 = prop, d1 = index and a0 = 0. The value size is prop & 7, and bit 3 means signed.[^fw8]
- Our DOCS card mod dumps all of them (`PROPS_x.TXT`).[^emu3]

### Per-setting data behind a setting id

Each setting id has more data than its `{prop, sub}` entry.[^fw4]

- A default value per id, from u32 tables for 0 to 1649, for 10000 and up, and for 15000 and up.
- Two per-id RAM arrays, each with a get and a set function.
- Reset loops that fill them per range with explicit bounds.

A new id range needs all of these, plus the `{prop, sub}` entry and the handle cache.[^fw4]

The OM-5 1.2 Shooting Menu 2 is 771 High Res, **1681 Live ND**, 603, 471, 266, 682 and 5005. The E-M5's is 603, 471,
266, 682, 5005, 772 High Res and 180.[^fw4]

- Live ND joins the bracketing-style special-item chain. On the OM-5 one function adds 1681 to it. The E-M5 has a twin
    of that function, with its own dialog.[^fw4]
- 58 OM-5 functions use 1681 to 1683 as immediates, mostly "if Live ND is on" checks in display and interlock
    code.[^fw4]

## How menus are built

**Where the tables are.** The tabs have a table. Its Shooting Menu 2 record points to a list of 7 ids. The submenu table has 146 records. Title and help lists have their counts in the per-tab descriptor. Option
descriptors are 36 bytes each. A separate list holds the special shooting modes that exclude each other.[^fw1] Other
tables are the USB Mode options and the AF mode list (0, 1, 2, 3, 5, 9).[^fw1]

### Submenu pages

- A page record is 24 bytes, `{→ 36 B descriptors, n, 0, → page titles, → per-item 8 B strings, key}`. Focus BKT has
    a record plus a copy, key `0x48`, items 1323, 858, 861 and 1081.[^fw2]
- The page handler table has 12-byte entries `{key, viewer, action}`. Key `0x47` leads to a viewer that is a `cmp`
    chain over the item ids.[^fw2]
- Option kinds are 4 = string id, 5 = inline UTF-16 text and 1 = number + unit.[^fw2]
- Tab page lists hold setting ids **and** menu-only ids (3xxx, 5xxx).[^fw2]
- Most lists exist in 2 copies (3 on the OM-5) and use counts. Patch every copy.[^fw2]

A data-only patch that adds setting 1448 to the Bracketing page renders "Set number of shots 8" in om-emu.[^emu1]

- The **visible rows come from the submenu u16 list** (Bracketing, and Focus BKT with key `0x8a`). Descriptors are found
    by id.[^emu1]
- The new row can't be edited (RIGHT does nothing) until the page's per-item picker code knows the id.[^emu1]

### Row actions and the page screen stack

OK and RIGHT on a Custom-menu row are 24-byte dispatch records per page,
`{u32 level, u16 item, u16 sub, u32 fn, u32 group, u16 target, u32 fn2}`. J2 has an OK table and a RIGHT table. With
fn 0 the matcher opens controller (group, target).[^fw6]

- Each page actuator keeps a two-slot screen stack (depth u16 +0x4c, screens +0x54 and +0x58). At depth 2 every key
    goes to the sub-screen's vt[0].[^fw6]
- The list is drawn from GUI variable `0x38` (`0xc82` B), published with a call `(id, size, buf, 1)`.[^fw6]
- It is the same family as the E-M10 II.[^fw6]

### Adding a row to a top-level tab

These steps add the Live ND Shooting row to a tab. They were worked out in om-emu and in the firmware.[^emu2]

- Tab lists come from the key table, 8-byte records `{u16 key, u16 n, → variant records}` for keys `0x4e` to `0x54`
    (Shooting 1, Shooting 2, Movie, Playback, Custom, Custom-B, Setup). Each variant record is
    `{u16 variant, u16 n, → u16 ids}`. The loader takes the variant-0 record only. Shooting 1 has 6 ids (3357, 111, 10,
    269, 34, 5004), and Shooting 2 has 7.[^fw5]
- **A tab page holds 7 rows at most.** An 8th id is drawn over row 0 and the cursor goes off screen, with no
    scrolling. The OM-5 also keeps Shooting 2 at 7 ids. Moving RC Mode (180) to the end of Shooting 1
    works. The row draws with its value.[^emu2]
- Per-tab descriptors are 28 bytes, `{u16 tab, u16 n, → titles, → help, n_values, → value list (8 B {u16 id, u16 nopts,
    → options}), n2, → list2}`. Title and help entries are 12 bytes, `{u32 id, u16 kind, u16 string, u32 base}`.[^fw5]
- Kind 5 (inline text) crashes the title renderer with an OSD BMP_LUT error. Use kind 4 string ids.[^emu2]
- The **string lookup** has 132 callers. It reads a language byte and per-language arrays. All 34 languages have 3447
    strings.[^fw5]
- A 5-byte `jmp` at the string lookup to a 42-byte handler serves ids 4000 to 4015 from our own table, else the native
    path. That gives new text in every language. It worked in om-emu as a "Live ND Shooting" row with help.[^emu2]
- RC Mode moves to the end of Shooting 1, so Live ND Shooting sits after High Res in Shooting 2, as on the OM-5.[^pol2]

**A new native submenu page works in om-emu.** RIGHT on the row opens "Live ND Shooting" with ND Number and LV
Simulation rows.[^emu2] The chain runs through five tables.[^fw5]

1. The row record (14, screen).
2. The group-`0xe` screen table, 125 × 24 B `{screen, 0x16, ctl, 0x33, key, 0}`, with its group table.
3. The controller table, 169 × 36 B `{ctl, type, key, → items, n, → RIGHT, n, → OK, n}`, with its count read at three
   sites.
4. Rows from the submenu table, 146 × 12 B `{key, → u16 ids, n}`, with its count read at two sites.
5. Page records, in two copies, 124 × 24 B `{key, → 36 B descriptors, n, 0, → page title + help, → per-item 8 B}`,
   with `cmp 124` at two sites.

The page records start with the key.[^fix1]

**Pickers.** A row's picker takes its option count and values from an option-value record per id.[^fw5]

- The records sit in a RAM hash, 128 buckets. It is built at boot from a static table, 1215 × 20 B
    `{u16 id, u16 0x80, → values, 0, u16 size, u16 elem, 0x100}`, and read through a lookup.[^fw5]
- No record means an empty picker. With records for 16001 and 16002 both pickers draw (ND2 to ND16, Off/On).[^emu2]
- Kind-5 option labels are 8-bit text. Option lists inside a page use that page copy's base.[^emu2]

Records can be added at boot.[^emu2]

- The hash builder has one caller, `call ...,[d2,a2,a3],12`, followed by `clr d0; ret [],4`.
- Replacing that call with a `jmp` to a stub that makes the same call fills the pickers with no RAM pokes. The stub
    then prepends nodes `{→ record, → old head}` to the bucket for `id & 127`.
- Only d0 and a0 are free there.
- In native pages a page record's second title entry is kind 0. A kind-4 page help draws over the row help.

**Values stick.** Jumping from the menu getter and setter to a handler that serves ids 16000 to 16031 (else native)
makes the whole flow work in om-emu.[^emu2]

- Live ND Shooting Off/On, ND Number ND2 to ND16 and LV Simulation Off/On are shown on the tab row and the page.
- A Bracketing-style level-2 record (inline Off/On on the tab) opened its picker on row 0. So the On/Off row lives in
    the page.


The working method (values in the settings-image tail, rows and page, where the code may sit) is written up on
[saved settings and menu rows](../features/saved-settings-and-menu-rows.md).[^cam1]

### A new Custom Menu letter

Besides the tables used for the letter K (letter id, glyph, key, preview, open page, page map, controller, controller
init and letter picture), a letter only opens with RIGHT when two more things hold.[^fw8][^emu3]

1. The letter column controller (stock controller entry 102 `{0x3f, 4, 0x52}`) has a record for the letter in its
   RIGHT and OK lists. The two lists are identical, 22 × 24 B `{1, letter id, fn, 0xf, 1, 0}`. The check returns 0 for
   a letter not listed.
2. The letter's page key is in the key-to-row-list function table, 51 × `{u16 key, 0, fn}`, with a reader, a count
   and a generic list function. Key 103 is there and 129 is not. A page whose key is missing opens with its title and
   no rows.

Our mod loader adds letter 3295 (key 129) as K2 this way.[^fw8]

### The OM-5 II's menus

The OM-5 II's UI is the OM-1-style menu. So porting the whole UI would be a rewrite, with 1.4 to 1.65 MB of new GUI code
and a settings model with +917/−393 keys. Reorganising menus or porting single screens is realistic.[^fw1][^inf1]

As booted in om-emu, the OM-5 II 1.1 menu has these tabs.[^emu1]

- Shooting 1 (8 pages).
- Shooting 2 (Computational Modes, Other Shooting Functions, Bracketing).
- AF (7 pages), Movie, Playback, Custom, Setup and My Menu.

## Setting restriction rules

One table maps one setting's value when another setting has a given value. This is what greys menu options.[^fw7]

- The table proper has **305 records**. It is walked by one function and by the hash builder (`cmp 305`, hash of 32
    buckets).[^fix2]
- A record is `{u16 sid, u16 flags, u32 rules, u32 nrules, u32 0, u32 fn}`, where fn is a check routine on one
    record. There are 3,039 rules.[^fix2]
- Rules are `{u32 cond, u16 n, u32 map, u16 n}`. Cond terms are `{u16 sid, u16 value, u32 0}`, and maps are
    `{s16 from, s16 to}`.[^fw7]
- Rule lists and value maps are **shared** between rules and records (654 shared rule entries). So lifting one rule by
    editing its map lifts every sharer.[^fix2]
- Cond value bit 15 is set on some terms. Its meaning is not traced.[^fix2]
- The format comes from the E-M1 III Mod Builder (`tools/patch_hhrs_flash.py`), where a repointed map was
    camera-checked on the E-M1 III.[^fw7]
- The sids are not yet named.[^fw7]

## AE bracketing options

The AE BKT picker's entries are 64-byte option structs `{u32 frames, u32 step 1/256 EV, u32 type (1 AE, 4 HDR)}`. There
is one list per EV step (setting 64).[^fw12]

| EV step | entries |
|---|---:|
| 1/3 EV | 19 |
| 1/2 EV | 15 |
| 1 EV | 11 |

*AE BKT option lists by EV step. List addresses are in the [address reference](#address-reference).*

- The lists are reached through option-value records `{u16 id, u16 key, structs, codes, u16 size, u16 elsize,
    u32 0x600}`.[^fw12]
- Picking one writes setting **5 = frames**, 1480 = step and 1502 = 1 through a wrapper. The wrapper is the setter,
    which only stages into prop `0x8b54`, plus an apply step.[^fw12]
- The getter returns the frame count. om-emu's `setting:` token shows the entry code.[^emu4]
- A 9 in an entry is taken as is. But the shooting-screen bracket info then overruns its 7-entry buffers, and om-emu
    shows a GUI stop on leaving the menu. A clamp fixes it.[^emu4]
- Our nine-frame AE bracketing mod puts that clamp in the base firmware and the rest in card mod MOD13.[^fw12]

## Keeping feature settings in a card file

Adding settings to the internal store is risky (see above). So we looked at how the caduceus project (E-P7 patches)
avoids it.[^fw10]

- caduceus keeps feature settings out of the internal store. A validated card file (magic, version, firmware build,
    main SHA prefix, CRC-32, per-byte ranges) is read once on the first half-press.[^inf4]
- Edits made on the camera are written back as `.NEW` (read back). The old file is renamed to `.BAK`, then `.BIN` is
    written (read back), and the dirty flag is cleared last.[^inf4]
- This is camera-proven on the E-P7. For us it is inferred.[^inf4]

The E-M5 III has the same file API layout and message codes, with **ftell** on message `0x10007` and **fseek** on
`0x10008`, and a caller classifier.[^fw10] It also has the same HLS_EVENT task: priority 54, stack 16360, task id at
mgr+172 and an appevent get.[^fw10]

The half-press hook site matches too.[^fw5]

- The E-M5 III appevent loop has only one caller, the HLS_EVENT task.
- After every receive it calls one function with d0 = the received event (from (36,sp)).
- That is the same place as the E-P7's tracker call that caduceus hooks for its first-half-press card load.
- Half-press is event `0x02000100`, which is also tested in a second function.

Other findings from the same study follow.

- The E-M5 III has **no** E-P7-style settings facade vtable. The candidate is 85 "not implemented" tag stubs. There is
    also no 20-byte validator table in a scan of the settings area.[^fw10]
- Allowed values probably live in per-setting class objects, such as the one for 1448.[^inf4]
- The plan is CS0 to CS4: trace, card config loader, write-back, card names via kind-5 labels and settings
    backup.[^inf4]
- caduceus is not a reusable UI framework. It is 444 E-P7-only byte edits, about 43 KB of new bytes. Its ports are
    separate per-body repos that share only the look format and the Control Panel.[^fw11]
- Most of its UI hangs off the Colour Profile wheel, which the E-M5 III lacks on screen.[^fw11]
- About 12 KB of their code sits in dead EVF gamma tables, because the E-P7 has no EVF. On the E-M5 III those tables
    are live.[^inf5]
- The verdict is to build our own feature hub (CS0 to CS3, plus M1 and M2) with their patterns. One half-press
    dispatcher and one label-builder hook are shared by all consumers.[^inf5]
- A lesson from their Lowest S/S row (MIN_SHUTTER m2 to m4, E-P7) applies to our first menu step. Adding a row for a
    hidden stock setting needs both the page's row-info records and the drawn row list. Their m2 patched only the
    records and got no row. A long inline value column overflows, so open the stock picker screen instead, as their m4
    does.[^inf6]
- The fenykl project by atx (E-M10 II) does the card-settings idea as one stock menu row (Eye-Fi). The row opens its
    own page that the stock list view draws (copied GUI data slot, kind-5 text, `gui_data_set`). Values are kept in two
    CRC'd card text files, with no settings store.[^inf7]

## On-screen text (GUI strings)

All menu text lives in block 1. Entries 1 to 34 of its directory are languages. **English is 8** on the E-M5 III and
E-M1 III, and **5** on the OM-5 and OM-5 II.[^fw1]

- Each language has an index of UTF-16LE strings, and code refers to a string by its **index**.[^fw1]
- The E-M5's English has 3447 strings with 177 bytes of slack.[^fw1]
- Block 1 ends with about 6.7 MB of zeros.[^fw1]

## Open questions

- What cond value bit 15 means in the restriction rules, and the names of the sids.

## Address reference

E-M5 III 1.7 block0 addresses unless a body is named.

| item | address |
|---|---|
| setting → property table, ids 0–1649 | `0x604de68c`, RAM handle cache `0xa25b8cf0` |
| same table, OM-5 (ids 0–1892) | `0x60514fec` |
| same table, E-M1 III, OM-5 II, PEN-F | `0x604e4d90`, `0x605193e8`, `0x603fa158` |
| same table, OM-1 | block0 offset `0x6007c4` |
| table for ids 3000 and up, ids 15000–15267 | `0x604e021c`, cache `0xa25ba8d8` |
| setting lookup over all ranges | `0x602e6b2a` |
| `MODE_*` key names | block 2 sub-block `0x45e20000` |
| default value per id | `0x602d364d`, tables `0x604b20ac` (0–1649), `0x604b3a74` (10000+), `0x604b3b94` (15000+) |
| per-id RAM arrays: get, set | `0x602e6f35` / `0x602e6fe1`, `0x602e7088` / `0x602e7134` |
| per-id RAM arrays for 0–1649 | `0x62123030`, `0x62125048` |
| reset loops | `0x602cd3b0`, `0x602d2e0c` |
| menu getter, setter | `0x602e6a02`, `0x602e6f11` |
| getter that returns the AE BKT frame count | `0x602e69f9` |

*Setting ids and their tables.*

| item | address |
|---|---|
| store `0x32` (50) registry | `0x60098998` to `0x600bd004` |
| High Res Shot entry in that registry | `0x600bcc48` |
| store 50 pointer, live image, bank | `0xa2637870`, `0x623d1000`, `0xa294e000` |
| boot load of the bank | `0x6005aa15` → `0x6005ad45` |
| save, flash write | `0x6005aaaf`, `0x6005a177` |
| save callers: power-down, "Power ???", "acc flash write", shell "w" | `0x60128eb1`, `0x601fc9a7`, `0x60062e44`, `0x6005bad0` |
| store 63 registry, live image | `0x60094134`, `0x623c1000` |
| store 63 flash banks | `0x402c0000`, `0x402e0000` |
| fd1 (store id 2), fd2 (store id 1) flash | `0x40080000`, `0x400e0000` |
| property get, set | `0x6005ce6b`, `0x6005cf1c` |
| property hash, lookup | `0xa262585c`, `0x6005be20` |
| CSV-import override table, its flag (u16) | `0xa262d85c`, `0xa2625858` |

*Stores and the property hash.*

| item | address |
|---|---|
| tab table, Shooting Menu 2 record | `0x6106a6d4`, `0x6106a6dc` |
| Shooting 2 tab list | `0x6106a644` |
| High Res Shot title entry, help entry | `0x61092af0`, `0x61092d84` |
| title list, help list | `0x61092a24`, `0x61092cb8` |
| per-tab descriptors | `0x610938b0` |
| option descriptors (36 B each) | from `0x610d02b8` |
| option-value records (static table) | `0x604d4ee4` |
| special shooting modes that exclude each other | `0x60e7162c` |
| USB Mode options, AF mode list | `0x61074fd2`, `0x6107e27c` |
| submenu table (146 records) | `0x61069f60`, counts at `0x60d61d08`, `0x60d62555` |
| Bracketing and Focus BKT row lists | `0x6106a110`, `0x6106a458` |
| Focus BKT page record and copy | `0x610d5e58`, `0x610e35e0` |
| page handler table, key `0x47` viewer | `0x610e4268`, `0x60e096d7` |
| page records (two copies) | `0x610d5794`, `0x610e2f1c`, `cmp 124` at `0x60e03f65`, `0x60e06aaa` |
| tab key table, loader | `0x6106a714`, `0x60d6211d` |
| J2 OK and RIGHT dispatch tables | `0x6106242c`, `0x610623e4` |
| dispatch matcher | `0x60d5af27` |
| GUI variable publish | `0x60c8165d` |
| group-`0xe` screen table, group table | `0x610b166c`, `0x610b4264` |
| controller table | `0x61064b98`, count at `0x60d593f6`, `0x60d594ca`, `0x60d5b5a6` |
| option-value RAM hash, nodes | `0x62118d08`, from `0x62118f08` |
| hash builder, its one call site | `0x602d3f34`, at `0x602d2da0` |
| option-value lookup | `0x602d3b93` → `0x602d3f8b` |
| string lookup, language byte, per-language arrays | `0x60c9350c`, `0x61ea1dac`, `0x61eb7424` |
| letter column RIGHT and OK lists | `0x61060bfc`, `0x61060e0c` |
| letter check | `0x60d59bfd` |
| key → row-list function table | `0x6106a8e4`, reader `0x60d61c3a`, count at `0x60d61c4f` |
| generic list function | `0x60d62264` |

*Menu tables and functions.*

| item | address |
|---|---|
| Live ND special-item chain, OM-5 | `0x6097ad2d` |
| its E-M5 twin, dialog | `0x608d5b33`, `0x608d671c` |
| OM-5 1.2 Shooting Menu 2 list | `0x6122e41c` (OM-5) |
| restriction rules, area first read | `0x60477dbc` |
| restriction table proper (305 records) | `0x60477dd0` |
| its walker, hash builder, hash | `0x602cc943`, `0x602cc9e7`, `0x621173ac` |
| record check routine | `0x602d0dcf` |
| E-M1 III 1.6 restriction table | `0x604920dc` (E-M1 III) |
| AE BKT lists: 1/3, 1/2, 1 EV | `0x604bbca4`, `0x604bc164`, `0x604bc524` |
| AE BKT option-value records | from `0x604d5024` |
| AE BKT pick, setting writer | `0x602c62da`, `0x602c606f` |
| apply step | `0x602e6a4c` |
| GUI stop in om-emu, the clamp | `0x60dbad56`, `0x6030871b` |

*Restriction rules, the Live ND chain and AE bracketing.*

| item | address |
|---|---|
| fopen, fclose, fwrite, fread | `0x60631f63`, `0x60631f6c`, `0x60631fe8`, `0x606320f2` |
| ftell, fseek | `0x60632180`, `0x606321ea` |
| caller classifier | `0x606401e0` |
| HLS_EVENT task creation, manager pointer | `0x607ca795`, `0x61e99b90` |
| appevent get loop, its only caller | `0x602e2f49`, `0x607cac65` |
| half-press hook site | call to `0x602e34e5` at `0x602e2fb5` |
| second half-press test | `0x602e35b0` |
| E-P7 tracker call hooked by caduceus | `0x602c805f` (E-P7) |
| caduceus edit base | `0x60020020` (E-P7) |
| facade vtable candidate (85 stubs) | `0x60afd564` |
| validator scan range | `0x604a1020` to `0x60521020` |
| class object for setting 1448 | `0x608febd4` |

*Card file study.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware.
[^fw2]: Read in the firmware, 2026-11-05.
[^fw3]: Read in the firmware, 2026-11-20.
[^fw4]: Read in the firmware, 2026-11-18.
[^fw5]: Read in the firmware, 2026-11-19.
[^fw7]: Read in the firmware, 2026-11-21.
[^fw6]: Read in the firmware and checked in om-emu, 2026-11-17.
[^fw8]: Read in the firmware, 2026-11-22.
[^fw12]: Read in the firmware, 2026-11-22 to 2026-11-23.
[^fw9]: Read in the firmware, 2026-11-25.
[^fw10]: Read in the firmware, 2026-11-08, while studying the caduceus project's card settings.
[^fw11]: Read in the caduceus project and our firmware, 2026-11-11.
[^emu1]: Seen in om-emu, 2026-11-05.
[^emu2]: Seen in om-emu, 2026-11-19.
[^emu3]: Seen in om-emu, 2026-11-22.
[^emu4]: Seen in om-emu, 2026-11-22 to 2026-11-23.
[^cam1]: Seen on our E-M5 III using test firmware, 2026-11-19.
[^inf1]: Inferred.
[^inf2]: Inferred from the caduceus project's `docs/INTERNAL_STORAGE.md`, 2026-11-18.
[^inf3]: Inferred from the save callers, 2026-11-18.
[^inf4]: Inferred for us from the caduceus project, 2026-11-08.
[^inf5]: Inferred, 2026-11-11.
[^inf6]: Reported by the caduceus project on the E-P7, 2026-11-11.
[^inf7]: Inferred from the fenykl project by atx, 2026-11-17.
[^pol1]: Project decision, 2026-10-30.
[^pol2]: Project decision, 2026-11-19.
[^fix1]: Corrected 2026-11-19. The older reading is in [History](#history).
[^fix2]: Corrected 2026-11-22. The older reading is in [History](#history).

## History

- 2026-11-19: earlier notes read the page records one field off. They start with the key.
- 2026-11-19: the E-M5 III half-press hook site matching caduceus's was first listed as open. The match was found.
- 2026-11-21: the restriction table was first read as starting at `0x60477dbc`, about 280 20-byte records
  `{u16 sid, u16 flags, u32 rules, u16 count}`. Corrected 2026-11-22: it starts at `0x60477dd0` with 305 records, and
  the record at `0x60477dbc` is not part of it.
- The older candidate `0x6096bc89` for the Live ND special-item chain is a 603/471 interlock, not this chain.

