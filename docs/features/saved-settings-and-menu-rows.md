# Saved mod settings and native menu rows

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

## Credits

The idea of keeping mod settings in the unused tail of the camera's own settings image comes from the Caduceus E-P7
project's internal-storage notes, which follow the Caduceus OM-3 port. This page applies it to the E-M5 III, adds
native menu rows, and reports the camera result.

## On the E-M5 II and E-M5 (Mark I) (2026-11-21)

- **E-M5 II 4.1:** same `MODE_*` key-table design (4192 names in block 2) and the same `SubApp`/`OlyApi` layers, so the method carries; the saved-values store differs (no "acc flash write" settings image, as on the PEN-F). New addresses throughout. [code]+[inferred]
- **E-M5 (Mark I) 2.3:** no `MODE_*` key table and an older framework (no Rhapsody OXF); a re-port from scratch. [code]

Full comparison: [older bodies](../bodies/comparison.md#older-bodies-e-m5-ii-and-e-m5-mark-i-2026-11-21).
