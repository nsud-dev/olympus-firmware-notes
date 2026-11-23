# Saved settings and menu rows

> **Technical notes.** This page is the dense reference. For a readable introduction, start with [Settings and menus](../guides/settings-and-menus.md).

A feature added to the camera's firmware needs somewhere to keep its settings, and a menu entry to change them. This
page describes a method that does both on the E-M5 Mark III (firmware 1.7):

- **Native menu rows.** New rows and a new menu page that look and behave like the camera's own. The first use is a
  **Live ND Shooting** row in Shooting Menu 2, right after High Res Shot, where the OM-5 has it. Pressing right opens
  a page with Live ND Shooting (Off/On), ND Number (ND2/4/8/16) and LV Simulation (Off/On).
- **Settings kept across power-off.** The values sit in an unused part of the camera's own saved settings, so the
  camera saves and reloads them itself. There is no card file and no new flash writer.

**Status: works on the camera** (2026-11-19). The rows appear in the right place, the page opens, and values set on
the page are still there after power-off and power-on. One camera, one owner so far.

Tags: **[code]** read in the firmware, **[camera]** seen on a real E-M5 III, **[emu]** seen in an emulator,
**[inferred]** not traced or tested. Addresses are runtime addresses in block 0 (load base 0x60021020).

Terms used here:
- **Store 50**: the camera's store of user settings, a 256 KB image in RAM that is saved to flash as one piece.
- **Setting id**: the number the menu code uses to name one setting (Live ND on the OM-5 is 1681).
- **Section**: one of the ten parts of the main program that load in the background after power-on
  ([boot and sections](../firmware/boot-and-sections.md)).

## Where the values live

The store-50 live image is at RAM **0x623d1000**, 0x40000 bytes. At boot the camera loads the whole saved bank into
it, and at power-off the save routine (0x6005aaaf) compares the **whole** image with the bank and writes it if
anything differs. The stock records end well before the end of the image, and stock code never reads the rest. So
bytes written into that unused tail are saved and restored by the camera itself. [code] [camera]

The block used here starts at image offset **+0x39F00 (RAM 0x6240af00)**:

| offset | size | meaning |
|---|---|---|
| +0 | 4 | marker `MOD\x01` (0x4d4f4401); anything else means "not set up yet" |
| +4 | 1 | Live ND on/off (1 = on) |
| +5 | 1 | ND number, 1-4 = ND2/ND4/ND8/ND16 |
| +6 | 1 | LV Simulation (1 = on) |
| +8..+0x47 | 64 | 16 words reserved for tuning values |

On the first menu use after a flash, if the marker is missing, the code writes the defaults (Off, ND8, Off), zeroes
the reserved words and writes the marker. Code that reads the block range-checks every value, because the tail of a
camera that never ran this code holds leftover bytes. [code] [camera]

Why not add new settings to the store's record list? Values in the store are packed in record order without ids, so
inserting a record shifts every later one. Appending at the end is safe, but the property table the store uses sits in
memory that loads before everything else and has no room left. Moving it means changing the earliest boot copy. The
unused tail needs none of that. [code]

Limits: [inferred]
- A battery pull loses changes made since the last save (the camera saves at power-off).
- A settings reset or the stock restore file does not clear the tail; the marker and range checks cover that.
- Firmware without this code ignores the block.

## How the menu rows are added

The E-M5 III menu is built from data tables: tab lists, page records, screen and controller tables, value lists and a
string table. The new rows are mostly new copies of these tables in free space, with the counts and base pointers in
the stock code changed to point at the copies. [code]

- **Tab placement.** A tab page holds at most 7 rows. To fit Live ND Shooting after High Res Shot in Shooting Menu 2,
  RC Mode moves to the end of Shooting Menu 1. [code] [camera]
- **New page.** One more page record, controller and submenu entry (counts 124->125, 169->170, 146->147), so the
  row's RIGHT key opens a native page. [code] [camera]
- **New setting ids 16000-16002.** The menu getter (0x602e6a02) and setter (0x602e6f11) get a short hook: ids
  16000-16002 read or write the bytes in the saved block; every other id runs the stock code. [code] [camera]
- **Value pickers.** Option-value records (Off/On, ND2-ND16) go into the menu's option hash at 0x62118d08 on first use.
  [code] [camera]
- **New text.** A hook on the string lookup (0x60c9350c) answers string ids 4000-4015 from a new table, so rows,
  titles and help lines show new text. [code] [camera]

Where a row sits and where its value is stored are independent: a row reaches its value through its setting id, so a
row can go where the OM-5 has it while the value lives at the end of the store. [code]

## Where the code goes: the boot lesson

The menu getter and setter are already called during boot, before the menu is ever opened. That decides where the new
code may sit. [camera]

Sections are **read** in the order 1, 7, 2, 3, 4, 5, 6, 8, 9, 10 but become **ready** in number order, 1 to 10.
Until a section is ready, the loader keeps a memory access monitor over it and everything after it, and any access
there stops the boot. [code]

- First placement: code in the gap after section 7, called from hooks in section 2. Section 7 is read early but ready
  late, so the boot-time hook reached it too soon. The camera boot-looped (the stabiliser starts, then stops,
  repeatedly) and was recovered by flashing the previous firmware from the card. An emulator that does not model the
  monitor ran it fine. [camera]
- Working placement: code and tables in the free space after **section 3** (0x605d4000-0x605da000; the section-3 end
  constant at 0x60045e1d raised from 0x605d4000 to 0x605da000). The getter and setter hooks first go to a small guard
  at the end of section 2. The guard tests the ready bit for section 3 (bit 0x04 of 0xa26565c0) and runs the stock
  code until that bit is set. The string hook sits in section 6, which is ready after section 3, so it needs no guard.
  The option records are linked on first use rather than from a boot hook. Boots normally. [camera]

Rule that came out of this: a hook may reach code in another section only if that section becomes **ready** before
the hook can run, or if the hook tests the section's ready bit first. Checking the read order is not enough. [camera]

## A new Custom Menu letter (2026-11-22)

The mod loader adds a letter **K. Mods** after J2 in the Custom Menu (gear tab): one row per mod found on the card plus
a Wi-Fi Shell row, each with the stock Off/On list. It works in om-emu; not yet run on the camera. [emu]
A new letter needs one entry in each of these tables. Each is a copy of the stock table plus one entry, in free space,
with the stock code's pointer and count moved to the copy. [code]+[emu]

- **Letter id lists** at 0x6106a6f4 and 0x6106a6fc (u16 ids, 21 letters): add letter id 3293, which the firmware
  already knows but never shows. [code]+[emu]
- **Letter glyphs** 0x610974aa {id, glyph, selected glyph} (22 entries), **letter -> page key** 0x61097456 (21; K gets
  the unused key 103), **preview records** 0x61097270 and **open-page records** 0x610780e0 (24 each, 20 B
  {id, rows, title kind, title, items, aux}). Title kind 5 takes 8-bit text, not UTF-16. [code]+[emu]
- **Page row lists** 0x6106a824 {key, n, -> {cond, n, -> ids}} (24): the row count is written at run time, after the
  card scan. [code]+[emu]
- **Letter -> controller** 0x61070d04 {id, controller, 0} (24): the value is a controller id, not an index. The
  controller table 0x61064b98 (169 x 36 B) gets controller 86 for key 103. Without it the page opens empty. [code]+[emu]
- **Row kinds** 0x610783d8 {id, kind} (90): kind 1 gives the Off/On list. A row id missing here gets a +2..-2 level
  slider. [code]+[emu]
- **Letter pictures.** The letter cell draws one picture per letter from 32 picture lists of 16 B entries (21 used,
  padded with zero entries) and 32 widget templates whose count byte goes 21 -> 22. K uses two retired picture ids
  (0x129e, 0x1289) whose slots in the RAM picture table (pointer 0x61eb7628) the loader fills at start-up. Without the
  22nd entry the cell shows the A1 picture. [code]+[emu]
- **Values and text** use the same getter, setter and string hooks as the Live ND rows (setting ids 16100-16106,
  string ids 4100-4109). Row names come from the mods' file headers at run time. [code]+[emu]
- **First camera run (2026-11-22):** the loader worked, but MENU reset the camera. The cause was extending the
  letter-cell picture lists (see [gotchas](../reference/gotchas.md)); without that edit the menu works. [camera]

- **Scrolling page (2026-11-22):** one letter page holds more rows than fit on screen and scrolls natively:
  the K page has 1 + 2 x 10 static row ids, the shown count (Wi-Fi + m mod rows + m "Load:" rows) is written at run
  time, and the getter, setter and string hooks map row r to its mod at run time, so the shown rows are always a prefix
  of the static list. In om-emu the page opens with the cursor on its last row. A second letter (3295/3292) shows its
  rows but RIGHT does not open it; 3296 is not shown at all. [emu]
- **Page opens on its last row: cause and fix (2026-11-22).** A page's controller needs an entry in the
  controller-init table 0x6105e7fc (49 x {u16 ctl, 0, init}, one reader 0x60d59309, count byte 0x60d59330). Without
  one it gets the default init 0x60d5939c, which hands the list constructor 0x60d620e7 the raw controller words
  {key, items}; the list reads items != 0 as "entered from below" ((64) set -> cursor = last shown row). Stock list
  pages (J2, ctl 0x58) use 0x60d5945c, which passes {key, direction}. Adding {ctl, 0, 0x60d5945c} makes the page
  open on its first row. A camera run showed the bug. [code]+[emu]+[camera]

- **Value column and scroll bar:** right-aligned values touch the scroll bar of a page with more than 7 rows (no stock
  custom-menu page scrolls on this body); own "On" / "Off" strings with three trailing spaces clear it. Help strings
  need "\r\n" line breaks (about 30 characters per line). [emu]+[camera]
- **Letter cell:** a letter missing from the letter picture/group table 0x610782c0 (25 x {id, sel pic, normal pic,
  group}; readers 0x60d7552a, 0x60d75749) gets a blank cell; adding it gives a cell with a stand-in picture (no K
  picture without the letter-cell list edit, which reset MENU). A second new letter still never reaches the
  page-open code 0x60d6cbb0 on RIGHT (tried ids 3295/3292, ctl 82/98/103/43, keys 129/107/112, group 10/11). [emu]

## Credits

The idea of keeping mod settings in the unused tail of the camera's own settings image comes from the Caduceus E-P7
project's internal-storage notes, which follow the Caduceus OM-3 port. This page applies it to the E-M5 III, adds
native menu rows, and reports the camera result.

## On the E-M5 II and E-M5 (Mark I) (2026-11-21)

- **E-M5 II 4.1:** same `MODE_*` key-table design (4192 names in block 2) and the same `SubApp`/`OlyApi` layers, so the method carries; the saved-values store differs (no "acc flash write" settings image, as on the PEN-F). New addresses throughout. [code]+[inferred]
- **E-M5 (Mark I) 2.3:** no `MODE_*` key table and an older framework (no Rhapsody OXF); a re-port from scratch. [code]

Full comparison: [older bodies](../bodies/comparison-technical.md#older-bodies-e-m5-ii-and-e-m5-mark-i-2026-11-21).
